"""玩家看不看得到一个事件（契约 1.12，第 3 节「玩家看得到哪些变化」、2.1 ②、2.11）。

规则只写这一份，三处都用它：settle 给玩家写 learn（_occur_draft）、后端推不推这个事件（projection.is_visible）、
节拍上的固定演出算不算玩家在场。三处各写各的，就会出现推了雨却没告诉玩家、或者告诉了玩家却没推雨。

按顺序看：① 事件是玩家做的 ② 玩家在事件的地点 ③ 事件是没有参与人物的节拍（天气、天灾，『走れメロス』的
beat.12 大雨、beat.15 雨が上がる、beat.17 濁流），落在和玩家同一个场景：两个地点的 sceneRef 都不是空、而且相同。
幕切换第 3 步（settle 的 player_present=False）玩家一律算不在场，调用方不问这里。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .sim import World


def same_scene(world: World, a: str, b: str) -> bool:
    """两个地点在同一个场景：两边的 sceneRef 都不是空、而且相同（没有场景的地点不和谁算同一场景，连自己也不算）。"""
    scenes = {p["id"]: p.get("sceneRef") for p in world["places"]}
    sa, sb = scenes.get(a), scenes.get(b)
    return sa is not None and sa == sb


def open_air(world: World, beat: str) -> bool:
    """没有参与人物的节拍（天气、天灾）：同一个场景里的人都看得到。"""
    return any(b["id"] == beat and not b["participants"] for b in world["beats"])


def sees(world: World, player_place: str | None, event: Mapping[str, Any]) -> bool:
    """玩家在 player_place（事件之前的 var.player.location）时，看不看得到 event（要 actor、place、effects）。"""
    if event.get("actor") == "player":
        return True
    place = event.get("place")
    if place is None or player_place is None:
        return False
    if place == player_place:
        return True
    return same_scene(world, place, player_place) and any(
        e.get("op") == "beat" and open_air(world, e.get("beat", "")) for e in event.get("effects", ())
    )
