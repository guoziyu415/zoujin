"""固定演出选哪一条（契约 1.7，2.11）。

pick_set_piece()：一个时机（节拍发生，或玩家的动作判定之后）上演哪一条固定演出。同一个时机按列表顺序取第一条
条件全满足、`once` 的还没演过的；都不满足返回 None，照常由叙事者说。这一局演过哪些（`played`）由服务端记，
它不是事件，不在 SimState 里。`knows` 条件用 primitives.knows()，和叙事者的 R4 同一份。
带 `learns` 的那条（1.7，S-077 ⑪），服务端把这些 learn 和演出同一次提交写进事件（契约 2.11），这里只负责选。
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from .incremental import SimState, flat
from .primitives import knows
from .sim import OCCURRED, Sim, World
from .visibility import sees


def _matches(on: Mapping[str, Any], hook: Mapping[str, Any]) -> bool:
    if "beat" in on or "beat" in hook:
        return on.get("beat") == hook.get("beat")
    if on["act"] != hook.get("act") or bool(on.get("refused")) != bool(hook.get("refused")):
        return False
    return "target" not in on or on["target"] == hook.get("target")


def pick_set_piece(
    world: World, state: SimState, hook: Mapping[str, Any], played: Collection[str]
) -> dict[str, Any] | None:
    """这个时机演哪一条固定演出；没有就是 None。

    hook 的写法同 `SetPiece.on`：`{"beat": 节拍}`，或 `{"act": kind, "target": 对象, "refused": 是否被拒}`
    （target 按契约 2.11：人物、地点，go 是出口通往的地点，examine 是可调查物）。节拍的时机只在玩家看得到这个节拍时演
    （`sees()`，契约 1.12 第 3 节：在节拍的地点，或者节拍没有参与人物、落在同一个场景），调用方在节拍那次提交之后、
    把它应用到 state 以后再问（玩家的位置和节拍之前一样）。
    """
    if "beat" in hook:
        beat = next((b for b in world["beats"] if b["id"] == hook["beat"]), None)
        event = {
            "actor": "system",
            "place": beat.get("place") if beat else None,
            "effects": [{"op": "beat", "beat": hook["beat"]}],
        }
        if beat is None or not sees(world, state["vars"].get("var.player.location"), event):
            return None
    sim: Sim | None = None
    for p in world.get("setPieces", []):
        if not _matches(p["on"], hook):
            continue
        if p.get("once") and p["id"] in played:
            continue
        if any(state["beats"].get(b) not in OCCURRED for b in p.get("after", [])):
            continue
        if any(state["beats"].get(b) in OCCURRED for b in p.get("before", [])):
            continue
        if not all(knows(world, state, k["character"], k["fact"]) for k in p.get("knows", [])):
            continue
        if p.get("played") and not any(x in played for x in p["played"]):
            continue
        if any(x in played for x in p.get("notPlayed", [])):
            continue
        if p.get("when"):
            sim = sim or Sim(world)
            if not sim.holds(p["when"], flat(state)):
                continue
        return dict(p)
    return None
