"""一次提交里的事件：分配 eventId、seq、幂等键，按 seq 用 W-1 的 apply 应用（B-0 第 7 条第 4 步）。

到点的节拍和期限用 W-1 的 settle 结算，草稿补成完整的事件再 apply，所以 world_state 缓存和「初值 + 按 seq 应用
全部事件」的重放逐字段相同（data-design 4.4）。同一时刻先节拍、再期限、最后事件：调用方先 settle 到事件的 t。

B-3：
- 收幕（api-contract 3.11）：这一幕还开着时，结算只到收幕节拍（`end.onBeats` 有了结果）或 `end.atLatest` 为止，
  之后的留到幕切换的第 3 步。最后一幕（没有 exits）不拦，收幕进结局是结局那张卡的事。
- 固定演出（契约 2.11）：每个节拍的系统事件应用以后问 W-1 的 `pick_set_piece`；演了的记在局上（`run.played`），
  带 `learns` 的写成紧跟着的一条 learn 事件（同一时刻的节拍都结算完以后），`set_piece` 消息留给网关推。
- 幕切换的第 3 步：玩家一律算不在场（`present=False`），不 learn 节拍的 public 事实，也不问固定演出。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from zoujin_backend.db.store import Run
from zoujin_backend.ids import IdGen
from zoujin_backend.projection import Away, is_visible
from zoujin_backend.world import Book
from zoujin_worldsim import OCCURRED, SimState, apply, pick_set_piece, settle

Json = Any

SCHEMA_VERSION = "1.12"  # 写入时的数据契约版本：契约 `SchemaVersion` 里最新的那个（test_world 管着）
CHECKER_SYSTEM = "w1-settle"
CHECKER_PIECE = "set-piece"


def act_closed(book: Book, state: SimState) -> bool:
    """这一幕收了没有：`end.onBeats` 里有一个有了结果（发生、改变、阻止，过了 window.latest 的也是阻止），
    或时钟到了 `end.atLatest`（api-contract 3.11）。"""
    act = book.acts[book.act_of(state["vars"])]
    end = act["end"]
    return any(b in state["beats"] for b in end["onBeats"]) or state["t"] >= end["atLatest"]


def has_exits(book: Book, state: SimState) -> bool:
    return bool(book.acts[book.act_of(state["vars"])].get("exits"))


class Writer:
    def __init__(
        self,
        book: Book,
        pid: str,
        state: SimState,
        *,
        key_base: str,
        turn_id: str | None,
        ids: IdGen,
        now: str,
    ) -> None:
        self.book = book
        self.pid = pid
        self.state = state
        self.key_base = key_base
        self.turn_id = turn_id
        self.ids = ids
        self.now = now
        self.events: list[Json] = []
        self.system: list[Json] = []  # settle 写的系统事件（StepResult 和 Trace 用）
        self.run = Run()  # 局上记的（提交的事务里读进来，写回去）
        self.pieces: list[Json] = []  # 这次提交里节拍时机演的固定演出（set_piece 消息）
        self.seen: list[str] = []  # 玩家可见的事件 ID（turn_settled.eventIds，api-contract 2.4）
        self.away = Away()  # 幕切换第 3 步结算的不算玩家看到（和网关推 commit、补推同一条规则）
        # 这一幕在这次提交开始时还开着（有去处的幕）：结算按收幕拦住
        self.guard = has_exits(book, state) and not act_closed(book, state)
        self.ending: Json | None = None  # B-9：这次提交进了结局（`ending.enter` 的结果）

    @property
    def player_place(self) -> str:
        p: str = self.state["vars"]["var.player.location"]
        return p

    def full(
        self,
        *,
        t: int,
        dt: int,
        actor: str,
        type: str,
        place: str,
        summary: str,
        effects: Sequence[Json],
        check: Mapping[str, Any],
        origin: str | None = None,
        causes: Sequence[str] = (),
        key_moment: bool = False,
        turn_id: str | None = None,
        **extra: Any,
    ) -> Json:
        ev: Json = {
            "schemaVersion": SCHEMA_VERSION,
            "eventId": self.ids.new("ev"),
            "playthroughId": self.pid,
            "seq": self.state["seq"] + 1,
            "idempotencyKey": f"{self.key_base}/{len(self.events) + 1:03d}",
            "worldModelVersion": self.book.version,
            "t": t,
            "dt": dt,
            "recordedAt": self.now,
            "actor": actor,
            "type": type,
            "place": place,
            "summary": summary,
            "causes": list(causes),
            "effects": [dict(e) for e in effects],
            "keyMoment": key_moment,
            "check": dict(check),
        }
        if origin is not None:
            ev["origin"] = origin
        if turn_id is not None:
            ev["turnId"] = turn_id
        ev.update(extra)
        return ev

    def add(self, ev: Json) -> Json:
        """按 seq 应用并记下。ev 由 full() 生成；W-1 的 apply 不收就抛 ValueError（整轮回滚）。"""
        if ev["seq"] != self.state["seq"] + 1:
            raise ValueError(f"seq 不连续：{ev['seq']}，上一个是 {self.state['seq']}")
        if not self.away(ev) and is_visible(self.book, ev, self.player_place):
            self.seen.append(ev["eventId"])
        self.state = apply(self.book.world, self.state, ev)
        self.events.append(ev)
        return ev

    @property
    def closed(self) -> bool:
        """这一幕（开始时还开着的）在这次提交里收了。"""
        return self.guard and act_closed(self.book, self.state)

    def settle(
        self,
        t2: int | None,
        *,
        stop_after: str | None = None,
        present: bool = True,
        guard: bool = True,
        anywhere: bool = False,
    ) -> list[Json]:
        """结算到 t2（None = 到底）。stop_after 给了节拍时，写完它的系统事件就停（评测的检查点「刚发生之后」）。

        guard：这一幕开始时还开着，就只结算到收幕为止（收幕节拍那一刻的都结完）；幕已经收了就不再结算。
        present=False：幕切换的第 3 步，玩家不在场（W-1 settle 的 player_present），不问固定演出。
        anywhere：节拍的固定演出不看玩家在不在节拍的地点（B-9：进结局时收幕的那几段算进结局演出，镜头在刑场）。"""
        if guard and self.guard:
            if self.closed:
                return []
            at_latest = int(self.book.acts[self.book.act_of(self.state["vars"])]["end"]["atLatest"])
            t2 = at_latest if t2 is None else min(t2, at_latest)
        drafts, _ = settle(self.book.world, self.state, t2, player_present=present)
        out: list[Json] = []
        learns: list[Json] = []  # 节拍时机的固定演出带的 learns，同一时刻的都结算完再写
        closed_at: int | None = None
        for d in drafts:
            t = d["event"]["t"]
            if closed_at is not None and t > closed_at:
                break
            if learns and t > learns[0]["t"]:
                self._learns(learns)
            out.append(self.add(self.from_draft(d)))
            if present and d["beat"] is not None:
                self._beat_piece(d["beat"], t, learns, anywhere=anywhere)
            if stop_after is not None and d["beat"] == stop_after:
                break
            if guard and self.closed and closed_at is None:
                closed_at = t
        self._learns(learns)
        self.system.extend(out)
        return out

    def curtain(self, beat: str) -> bool:
        """最后一幕里期限盯的节拍和它之后的节拍（B-9：收幕的固定演出算进结局演出，不看玩家在哪）。"""
        watch = self.book.world["clock"]["deadline"].get("watchBeat")
        if watch is None or has_exits(self.book, self.state):
            return False
        return float(self.book.beats[beat]["order"]) >= float(self.book.beats[watch]["order"])

    def _beat_piece(self, beat: str, t: int, learns: list[Json], *, anywhere: bool = False) -> None:
        state = self.state
        if anywhere or self.curtain(beat):  # W-1 只在玩家在节拍的地点时给：问的时候把玩家当作站在那里
            vars_ = {**state["vars"], "var.player.location": self.book.beats[beat]["place"]}
            state = cast(SimState, {**state, "vars": vars_})
        piece = pick_set_piece(self.book.world, state, {"beat": beat}, self.run.played)
        if piece is None:
            return
        self.play(piece)
        if piece.get("learns"):
            learns.append({"t": t, "piece": piece})

    def play(self, piece: Mapping[str, Any]) -> Json:
        """演一条固定演出：记在局上（once 的不再演），返回 set_piece 消息。"""
        self.run.played.append(piece["id"])
        msg = {"type": "set_piece", "pieceId": piece["id"], "lines": [dict(x) for x in piece["lines"]]}
        if "beat" in piece["on"]:
            self.pieces.append(msg)
        return msg

    def _learns(self, learns: list[Json]) -> None:
        for x in learns:
            self.piece_learn(x["piece"], x["t"], origin=None)
        learns.clear()

    def piece_learn(self, piece: Mapping[str, Any], t: int, *, origin: str | None) -> Json | None:
        """固定演出的 learns 写成一条 learn 事件（契约 2.11）：actor 是第一个说话的人物，只有地の文时是 system；
        动作时机的 origin 是 action，节拍时机的不写（schedule 只给节拍和期限）。已经知道的不再写。"""
        effects = [
            {"op": "learn", "character": k["character"], "fact": k["fact"]}
            for k in piece.get("learns", [])
            if k["fact"] not in self.state["knowledge"].get(k["character"], [])
        ]
        if not effects:
            return None
        speaker = next((x["speaker"] for x in piece["lines"] if x.get("speaker")), None)
        name = self.book.characters[speaker]["name"] if speaker else None
        return self.add(
            self.full(
                t=t,
                dt=0,
                actor=speaker or "system",
                type="learn",
                origin=origin,
                place=self.player_place,
                summary=f"{name}が、そのことを口にした" if name else "そのことが、知らされた",
                effects=effects,
                check={"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER_PIECE},
                turn_id=self.turn_id if origin is not None else None,
            )
        )

    def occurred(self, beat: str) -> bool:
        return self.state["beats"].get(beat) in OCCURRED

    def from_draft(self, d: Json) -> Json:
        """W-1 的 settle 草稿（或 `opening()` 里 source = schedule 的那些）补成完整的系统事件。"""
        e = d["event"]
        check: Json = {"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER_SYSTEM}
        if d.get("reason"):
            check["reason"] = d["reason"]
        if d["beat"] is not None:
            beat = self.book.beats[d["beat"]]
            summary = beat["summary"]
            for v in beat.get("variants", []):
                if v["id"] == d.get("variant") and v.get("summary"):
                    summary = v["summary"]
        else:
            deadline = self.book.world["clock"]["deadline"]
            summary = f"{deadline['label']}の刻限が来た"
        return self.full(
            t=e["t"],
            dt=e["dt"],
            actor=e["actor"],
            type=e["type"],
            origin=e["origin"],
            place=e["place"],
            summary=summary,
            effects=e["effects"],
            check=check,
        )
