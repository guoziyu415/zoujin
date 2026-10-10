"""开局到起点：eval_api 的 setup（api-contract 第 7 节）里只靠推演的那几种起点，B-0 和评测运行器共用。

- `checkpoint`：`"<情景 ID>@<节拍 ID>"` = 推演到该节拍刚发生之后；
  `"<情景 ID>@t=<分钟>"` = 推演到该时刻，含那一刻到点的节拍和期限规则，不含情景里正好在那一刻的事件；
- `scenario`：推演到底（不调用模型）；
- `place`：开局换个地点。

顺序：`place` 在时钟 0 写一个事件；情景的节拍改动在时钟 0 合成一个事件；settle 到身份的 startT；情景的事件按 t 先 settle
再写；最后按起点停下。到某一刻停、而那一刻没有事件时，写一个只推进时钟的事件（契约：时钟只由事件推出）。

只出事件和状态。事件带 seq（从 1 起），其余字段（eventId、playthroughId、schemaVersion、summary、causes、keyMoment、
check…）由 B-0 补上再写库。`setup.events`（评测布置）不在这里，B-0 在起点之后照 api-contract 第 7 节追加。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, NotRequired

from .incremental import Draft, SimState, apply, initial_state, settle
from .sim import OCCURRED, World, role_of

type Until = tuple[Literal["beat"], str] | tuple[Literal["t"], int] | None  # None = 推演到底


class Opened(Draft):
    """开局写出的一个事件。settle 写的照原样（source = schedule），其余 beat、variant、reason 都是 None。"""

    source: Literal["place", "scenario", "schedule", "clock"]  # 开局地点、情景、到点的节拍和期限、只推进时钟
    note: NotRequired[str]  # 给 B-0 写 summary 的一句（日语）；情景事件写了 note 就是它


NOTES = {"place": "開始地点", "scenario": "シナリオの設定", "clock": "時刻を進める"}


def parse_checkpoint(checkpoint: str) -> tuple[str, Until]:
    """ "sc.canon@beat.05" → ("sc.canon", ("beat", "beat.05"))；"sc.canon@t=1200" → ("sc.canon", ("t", 1200))。"""
    sc, sep, at = checkpoint.partition("@")
    if not sep or not sc or not at:
        raise ValueError(f"检查点要写成「情景 ID@节拍 ID」或「情景 ID@t=分钟」：{checkpoint!r}")
    if at.startswith("t="):
        return sc, ("t", int(at[2:]))
    return sc, ("beat", at)


def opening(
    world: World,
    role: str,
    scenario: Mapping[str, Any] | None = None,
    until: Until = None,
    *,
    place: str | None = None,
) -> tuple[list[Opened], SimState]:
    """按上面的顺序推演，返回（事件，状态）。scenario 是 scenarios.json 的一条；原著路径（sc.canon）给 None 或 {}。"""
    run = _Run(world, initial_state(world, role))
    if place is not None:
        run.write("place", {"t": 0, "effects": [{"op": "set", "var": "var.player.location", "value": place}]})
    sc = scenario or {}
    if sc.get("beats"):
        effects = [{"op": "beat", "beat": b, **o} for b, o in sc["beats"].items()]
        run.write("scenario", {"t": 0, "effects": effects})
    if until is not None and until[0] == "beat" and until[1] not in run.world_beats:
        raise ValueError(f"检查点的节拍不存在：{until[1]}")
    stops = [role_of(world, role)["startT"], *sorted(e["t"] for e in sc.get("events", []))]
    events = iter(sorted(sc.get("events", []), key=lambda e: e["t"]))
    for i, t in enumerate(stops):
        if run.settle_until(t, until):
            return run.out, run.s
        if i > 0:
            e = next(events)
            run.write("scenario", {"t": t, "effects": e["effects"]}, e.get("note"))
    if until is None:
        run.settle_to(None)
    elif not run.settle_until(None, until):
        raise ValueError(f"推演到底也没到检查点：{until}")
    return run.out, run.s


class _Run:
    def __init__(self, world: World, s: SimState) -> None:
        self.world = world
        self.world_beats = {b["id"] for b in world["beats"]}
        self.s = s
        self.out: list[Opened] = []

    def write(
        self, source: Literal["place", "scenario", "clock"], e: Mapping[str, Any], note: str | None = None
    ) -> None:
        """note：情景事件自己写了 note 就用它，没写用 NOTES 里的。"""
        loc = self.s["vars"]["var.player.location"]
        event = {"actor": "system", "type": "action", "origin": "action", "dt": 0, "place": loc, **e}
        self._apply(
            {"event": event, "beat": None, "variant": None, "reason": None, "reasonCode": None, "source": source},
            note or NOTES[source],
        )

    def _apply(self, d: Opened, note: str | None = None) -> None:
        d["event"] = {**d["event"], "seq": self.s["seq"] + 1}
        if note is not None:
            d["note"] = note
        self.s = apply(self.world, self.s, d["event"])
        self.out.append(d)

    def settle_to(self, t2: int | None, stop_after: str | None = None) -> bool:
        """结算到 t2；stop_after 给了节拍时，写完这个节拍发生的事件就停，返回停没停。"""
        drafts, _ = settle(self.world, self.s, t2)
        for d in drafts:
            self._apply(_opened(d))
            if stop_after is not None and d["beat"] == stop_after and _occurred(d, stop_after):
                return True
        return False

    def settle_until(self, t2: int | None, until: Until) -> bool:
        """结算到 t2，碰到起点就停；返回停没停。"""
        if until is None:
            self.settle_to(t2)
            return False
        if until[0] == "t":
            x = until[1]
            if t2 is None or t2 >= x:
                self.settle_to(x)
                if self.s["t"] < x:
                    self.write("clock", {"t": x, "effects": []})
                return True
            self.settle_to(t2)
            return False
        return self.settle_to(t2, stop_after=until[1])


def _opened(d: Draft) -> Opened:
    return Opened(
        event=d["event"],
        beat=d["beat"],
        variant=d["variant"],
        reason=d["reason"],
        reasonCode=d["reasonCode"],
        source="schedule",
    )


def _occurred(d: Draft, beat: str) -> bool:
    return any(
        f.get("op") == "beat" and f.get("beat") == beat and f.get("to") in OCCURRED for f in d["event"]["effects"]
    )
