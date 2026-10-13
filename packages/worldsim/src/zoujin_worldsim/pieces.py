"""Which set piece to play (contract 1.7, 2.11).

pick_set_piece(): which set piece plays at a given moment (a beat happens, or after the player's action is judged).
For one moment, take the first in list order whose conditions all hold and, if `once`, that has not played yet; if none
qualifies, return None and the narrator speaks as usual. Which ones have played in this run (`played`) is recorded by
the server; it is not an event and is not in SimState. `knows` conditions use primitives.knows(), the same as the
narrator's R4. For one with `learns` (1.7, S-077 ⑪), the server writes those learns into events in the same commit as
the set piece (contract 2.11); this module only chooses.

どの固定演出を上演するか（契約 1.7、2.11）。

pick_set_piece()：あるタイミング（ビートが起きたとき、またはプレイヤーのアクションの判定後）にどの固定演出を上演
するか。同じタイミングではリスト順に、条件がすべて満たされ、`once` ならまだ上演していない最初の 1 件を取る。
どれも満たさなければ None を返し、通常どおりナレーターが語る。このプレイで何を上演したか（`played`）はサーバーが
記録する。イベントではなく、SimState には入らない。`knows` 条件は primitives.knows() を使い、ナレーターの R4 と
同じもの。`learns` を持つもの（1.7、S-077 ⑪）は、サーバーがそれらの learn を演出と同じコミットでイベントに書き込む
（契約 2.11）。ここは選ぶだけ。
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
    """Which set piece plays at this moment; None if there is none.

    hook is written like `SetPiece.on`: `{"beat": beat}`, or `{"act": kind, "target": target, "refused": refused?}`
    (target per contract 2.11: a character or a place; for go it is the place the exit leads to, for examine it is the
    examinable). A beat moment plays only when the player can see that beat (`sees()`, contract 1.12 section 3: at the
    beat's place, or the beat has no participants and falls in the same scene); the caller asks after the beat's commit,
    once it has been applied to state (the player's position is the same as before the beat).

    このタイミングでどの固定演出を上演するか。なければ None。

    hook の書き方は `SetPiece.on` と同じ：`{"beat": ビート}`、または `{"act": kind, "target": 対象, "refused": 拒否
    されたか}`（target は契約 2.11 に従う：登場人物、場所。go なら出口の行き先の場所、examine なら調べられる物）。
    ビートのタイミングは、プレイヤーがそのビートを見られるときだけ上演する（`sees()`、契約 1.12 第 3 節：ビートの
    場所にいる、またはビートに参加人物がなく同じシーンに落ちる）。呼び出し側はビートのコミット後、それを state に
    適用してから問い合わせる（プレイヤーの位置はビートの前と同じ）。
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
