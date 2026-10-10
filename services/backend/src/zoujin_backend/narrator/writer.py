"""一次提交里的事件：分配 eventId、seq、幂等键，按 seq 用 W-1 的 apply 应用（B-0 第 7 条第 4 步）。

到点的节拍和期限用 W-1 的 settle 结算，草稿补成完整的事件再 apply，所以 world_state 缓存和「初值 + 按 seq 应用
全部事件」的重放逐字段相同（data-design 4.4）。同一时刻先节拍、再期限、最后事件：调用方先 settle 到事件的 t。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from zoujin_backend.ids import IdGen
from zoujin_backend.world import Book
from zoujin_worldsim import OCCURRED, SimState, apply, settle

Json = Any

SCHEMA_VERSION = "1.6"  # 写入时的数据契约版本
CHECKER_SYSTEM = "w1-settle"


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
        self.state = apply(self.book.world, self.state, ev)
        self.events.append(ev)
        return ev

    def settle(self, t2: int | None, *, stop_after: str | None = None) -> list[Json]:
        """结算到 t2（None = 到底）。stop_after 给了节拍时，写完它的系统事件就停（评测的检查点「刚发生之后」）。"""
        drafts, _ = settle(self.book.world, self.state, t2)
        out = []
        for d in drafts:
            out.append(self.add(self.from_draft(d)))
            if stop_after is not None and d["beat"] == stop_after:
                break
        self.system.extend(out)
        return out

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
