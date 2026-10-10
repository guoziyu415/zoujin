"""mock 的内存状态：会话、局、发过的 commit、续玩要的未完成状态。重启就清空。"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from zoujin_backend.mock.ids import IdGen

Json = Any

SERVER_TURN_SEQ_BASE = 0x80000000  # 服务端发起的轮次 turnSeq 最高位为 1（3.1）


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Session:
    sid: str
    user_ref: str
    expired: bool = False


@dataclass
class LastTurn:
    turn_id: str
    character: str | None
    status: str = "pending"  # settled / pending / lost
    player_text: str | None = None
    character_text: str | None = None
    completed: bool = False  # 人物这一轮说完了（turn_complete）

    def to_json(self) -> Json:
        return {
            "turnId": self.turn_id,
            "character": self.character,
            "status": self.status,
            "playerText": self.player_text,
            "characterText": self.character_text,
        }


@dataclass
class Playthrough:
    pid: str
    owner: str  # Session.sid
    role_id: str
    snapshot: Json  # 当前场景的快照；lastSeq、pending、voice 读的时候现填
    ids: IdGen
    status: str = "active"
    updated_at: str = field(default_factory=now_iso)
    commits: list[Json] = field(default_factory=list)
    events: list[Json] = field(default_factory=list)
    last_seq: int = 0
    names: dict[str, str] = field(default_factory=dict)  # 剧本里 {{id:前缀:名字}} → 运行时 ID
    voice: Json = field(default_factory=lambda: {"enabled": True, "degraded": False, "minutesLeftToday": 52})
    confirm: Json | None = None
    confirm_deadline: float = 0.0
    act_end: Json | None = None
    safety_pause: bool = False
    approach: Json | None = None
    last_turn: LastTurn | None = None
    focused: str | None = None
    settled: set[str] = field(default_factory=set)
    retracted: set[str] = field(default_factory=set)
    server_turn_seq: int = SERVER_TURN_SEQ_BASE
    ending_id: str | None = None
    ending_ready: bool = False
    plan_options: set[str] = field(default_factory=set)
    warm: dict[str, float] = field(default_factory=dict)  # 人物 → 会话就绪的时刻（time.monotonic）
    reconnected: bool = False  # 重连后第一次准备会话，reason 是 reconnect
    deleted_memories: dict[str, Json] = field(default_factory=dict)  # 記憶帳删过的记忆 → 删除时的响应

    def named_id(self, prefix: str, name: str) -> str:
        key = f"{prefix}:{name}"
        if key not in self.names:
            self.names[key] = self.ids.new(prefix)
        return self.names[key]

    def touch(self) -> None:
        self.updated_at = now_iso()

    # —— 读 ——

    def pending(self) -> Json:
        confirm = None
        if self.confirm is not None:
            left = max(0, round(self.confirm_deadline - time.monotonic()))
            confirm = {**self.confirm, "remainingSec": min(left, self.confirm["timeoutSec"])}
        return {
            "reveal": None,
            "confirm": confirm,
            "actEnd": self.act_end,
            "safetyPause": self.safety_pause,
            "approach": self.approach,
        }

    def current_snapshot(self) -> Json:
        snap = copy.deepcopy(self.snapshot)
        snap.update(
            playthroughId=self.pid,
            lastSeq=self.last_seq,
            status=self.status,
            pending=self.pending(),
            voice=dict(self.voice),
        )
        return snap

    def welcome(self) -> Json:
        lt = self.last_turn
        if lt is not None and lt.status == "pending" and not lt.completed:
            lt.status = "lost"  # 断线时人物还没说完（第 4 节）
        return {
            "type": "welcome",
            "lastSeq": self.last_seq,
            "voice": dict(self.voice),
            "lastTurn": lt.to_json() if lt else None,
            "pending": self.pending(),
        }

    def commits_after(self, last_seq: int) -> list[Json]:
        return [c for c in self.commits if c["seq"] > last_seq]

    def events_after(self, after_seq: int, limit: int) -> list[Json]:
        return [e for e in self.events if e["seq"] > after_seq][:limit]

    # —— 发出的消息改状态 ——

    def number_commit(self, msg: Json, hidden: int | None) -> None:
        """给 commit 编号：事件按顺序占 seq，再加上不可见的事件（默认：没有可见事件时 1 个）。"""
        start = self.last_seq + 1
        for n, ev in enumerate(msg["events"]):
            ev["seq"] = start + n
        invisible = hidden if hidden is not None else (0 if msg["events"] else 1)
        msg["fromSeq"] = start
        msg["seq"] = start + len(msg["events"]) + invisible - 1
        if msg["seq"] < start:
            raise ValueError("commit 至少占一个 seq")
        # 关键时刻的因果链里，剧本不写 seq 的事件步骤按事件 ID 现填（同一条 commit 里的事件这时才有 seq）
        reveal = msg.get("reveal")
        if reveal:
            known = {ev["eventId"]: ev["seq"] for ev in (*self.events, *msg["events"])}
            for step in reveal["chain"]:
                if "eventId" in step and "seq" not in step:
                    if step["eventId"] not in known:
                        raise ValueError(f"reveal.chain 里的 {step['eventId']} 不是发过的事件")
                    step["seq"] = known[step["eventId"]]

    def fill_snapshot(self, snap: Json) -> None:
        """act_transition 里的快照：局、序号、未完成状态和语音由 mock 现填。幕已经切了，没有待选的幕末。"""
        snap.update(playthroughId=self.pid, lastSeq=self.last_seq, status=self.status, voice=dict(self.voice))
        snap["pending"] = {**self.pending(), "actEnd": None}

    def on_sent(self, msg: Json) -> None:
        t = msg["type"]
        if t == "commit":
            self.commits.append(msg)
            self.events.extend(msg["events"])
            self.last_seq = msg["seq"]
            apply_patch(self.snapshot, msg["patch"])
            self.touch()
        elif t == "confirm":
            self.confirm = {k: v for k, v in msg.items() if k != "type"}
            self.confirm_deadline = time.monotonic() + msg["timeoutSec"]
        elif t == "confirm_closed":
            self.confirm = None
        elif t == "act_ended":
            self.act_end = {k: v for k, v in msg.items() if k != "type"}
        elif t == "act_plan_result":
            if msg.get("alternative"):
                self.plan_options.add(msg["alternative"]["optionId"])
            if self.act_end is not None:
                self.act_end["freeform"] = {"allowed": msg["triesLeft"] > 0, "triesLeft": msg["triesLeft"]}
        elif t == "act_transition":
            self.act_end = None
            self.plan_options.clear()
            self.snapshot = {k: v for k, v in msg["snapshot"].items()}
            self.touch()
        elif t == "safety_pause":
            self.safety_pause = True
        elif t == "safety_resumed":
            self.safety_pause = False
        elif t == "approach":
            self.approach = {"character": msg["character"], "kind": msg["kind"]}
        elif t == "turn_started":
            self.last_turn = LastTurn(msg["turnId"], msg["speaker"])
        elif t == "transcript" and msg["final"]:
            lt = self.last_turn
            if lt is not None and lt.turn_id == msg["turnId"]:
                if msg["speaker"] == "player":
                    lt.player_text = msg["text"]
                else:
                    lt.character_text = msg["text"]
        elif t == "turn_complete":
            if self.last_turn is not None and self.last_turn.turn_id == msg["turnId"]:
                self.last_turn.completed = True
        elif t == "turn_settled":
            self.settled.add(msg["turnId"])
            lt = self.last_turn
            if lt is not None and lt.turn_id == msg["turnId"]:
                lt.status = "settled"
                lt.completed = True
                if msg["outcome"] in ("retracted", "paused"):
                    lt.player_text = lt.character_text = None  # 原话已清空（3.6、3.12）
            self.touch()
        elif t == "degraded":
            self.voice["degraded"] = True
        elif t == "limits":
            self.voice["minutesLeftToday"] = msg["voiceMinutesLeft"]
        elif t == "ending_started":
            self.ending_id = self.ending_id or self.named_id("end", "ending")
        elif t == "ending_ready":
            self.ending_id = msg["endingId"]
            self.ending_ready = True
            self.status = "ended"
            self.touch()

    # —— 收到的消息改状态 ——

    def on_received(self, msg: Json) -> None:
        t = msg["type"]
        if t in ("activity_start", "text"):
            character = None if msg.get("purpose") == "act_plan" else self.focused
            self.last_turn = LastTurn(msg["turnId"], character)
            if t == "text":
                self.last_turn.player_text = msg["text"]
        elif t == "focus":
            self.focused = msg["character"]
        elif t == "unfocus":
            self.focused = None
        elif t in ("approach_arrived", "approach_dismiss"):
            self.approach = None


def _merge_by_id(items: list[Json], patches: list[Json]) -> None:
    by_id = {it["id"]: it for it in items}
    for p in patches:
        if p["id"] in by_id:
            by_id[p["id"]].update(p)
        else:
            items.append(dict(p))
            by_id[p["id"]] = items[-1]


def _add_remove(items: list[Json], patch: Json, key: str) -> None:
    removed = set(patch.get("remove", []))
    added = {a[key]: a for a in patch.get("add", [])}
    items[:] = [it for it in items if it[key] not in removed and it[key] not in added]
    items.extend(added.values())


def apply_patch(snap: Json, patch: Json) -> None:
    """commit.patch（3.4）：快照字段的增量，按 id 合并；actions、interactables 用 add / remove。"""
    if "clock" in patch:
        snap["clock"].update(patch["clock"])
    for key in ("deadline", "forecast"):
        if key in patch:
            snap[key] = patch[key]
    if "places" in patch:
        _merge_by_id(snap["places"], patch["places"])
    if "characters" in patch:
        _merge_by_id(snap["characters"], patch["characters"])
        # 快照只列当前场景在场的；place 变成场景外的地点就是离场
        here = {p["id"] for p in snap["places"]}
        snap["characters"] = [c for c in snap["characters"] if c["place"] in here]
    if "actions" in patch:
        _add_remove(snap["actions"], patch["actions"], "actionId")
    if "interactables" in patch:
        _add_remove(snap["interactables"], patch["interactables"], "id")
    if "player" in patch:
        snap["player"].update(patch["player"])
