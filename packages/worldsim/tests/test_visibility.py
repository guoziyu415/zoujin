"""sees()（契约 1.12）：玩家看不看得到一个事件。settle 给玩家写 learn、后端推事件、节拍上的固定演出算不算在场都用它。"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from zoujin_worldsim import SimState, apply, initial_state, knows, lived, place_at, same_scene, sees, settle

WORLD_DIR = Path(__file__).resolve().parents[3] / "worlds" / "hashire-merosu" / "1.0.0-draft"
WORLD: dict[str, Any] = json.loads((WORLD_DIR / "world.json").read_text(encoding="utf-8"))
ROLE = "role.traveler"
WEDDING = "place.melos-home"  # 婚礼（beat.11、13），scene.village
GROOM = "place.groom-house"  # scene.village
RAIN = "beat.12"  # 大雨：没有参与人物，落在 place.village（scene.village）


def at(place: str) -> SimState:
    s = initial_state(WORLD, ROLE)
    return apply(
        WORLD,
        s,
        {"t": 0, "dt": 0, "origin": "turn", "effects": [{"op": "set", "var": "var.player.location", "value": place}]},
    )


def beat_event(drafts: list[Any], beat: str) -> dict[str, Any]:
    return next(d["event"] for d in drafts if d["beat"] == beat)


def test_the_rain_reaches_the_wedding() -> None:
    """契约 1.12 的例子：玩家在婚礼上（place.melos-home），beat.12 的大雨落在 place.village。两个地点都在
    scene.village，算看见了：settle 在大雨的系统事件里给玩家写 learn，后端照同一条规则把它推给玩家。"""
    drafts, s = settle(WORLD, at(WEDDING), 3660)
    rain = beat_event(drafts, RAIN)
    assert rain["place"] == "place.village" and rain["place"] != WEDDING
    assert sees(WORLD, WEDDING, rain)
    assert {"op": "learn", "character": "player", "fact": "fact.storm"} in rain["effects"]
    assert knows(WORLD, s, "player", "fact.storm")


def test_a_beat_with_people_is_seen_only_at_its_own_place() -> None:
    """有参与人物的节拍照旧只看地点：婚礼在 place.melos-home，玩家在同一场景的花婿家就不算在场。"""
    drafts, _ = settle(WORLD, at(GROOM), 3660)
    wedding = beat_event(drafts, "beat.11")
    assert same_scene(WORLD, GROOM, wedding["place"])
    assert not sees(WORLD, GROOM, wedding)
    assert sees(WORLD, WEDDING, wedding)
    assert sees(WORLD, GROOM, beat_event(drafts, RAIN))  # 雨在花婿家也看得到


def test_places_without_a_scene_are_never_the_same_scene() -> None:
    """sceneRef 两边都要不是空：place.neighbor-village 没有场景，连自己也不算同一场景（地点相同另有第 ② 条）。"""
    assert not same_scene(WORLD, "place.neighbor-village", "place.neighbor-village")
    w = copy.deepcopy(WORLD)
    for p in w["places"]:
        if p["id"] in ("place.river", "place.mountain-pass"):
            p["sceneRef"] = None
    flood = {
        "actor": "system",
        "place": "place.river",
        "effects": [{"op": "beat", "beat": "beat.17", "to": "happened"}],
    }
    assert not sees(w, "place.mountain-pass", flood)
    assert sees(w, "place.river", flood)


def test_the_player_sees_what_they_do_and_nothing_without_a_place() -> None:
    mine = {"actor": "player", "place": "place.castle", "effects": []}
    assert sees(WORLD, "place.village", mine)
    assert not sees(WORLD, None, {"actor": "system", "place": "place.village", "effects": []})


def test_an_act_change_still_counts_the_player_away() -> None:
    """幕切换第 3 步（player_present=False）：同一场景的雨也不写 learn（契约 2.8.1，1.12 不变）。"""
    drafts, s = settle(WORLD, at(WEDDING), 3660, player_present=False)
    assert not any(e.get("character") == "player" for d in drafts for e in d["event"]["effects"])
    assert not knows(WORLD, s, "player", "fact.storm")


def test_lived_counts_the_rain_for_the_wedding_guests() -> None:
    """契约 1.12 补的 lived()：婚礼上的妹妹、花婿没参与 beat.12，但大雨没有参与人物、落在同一个场景（scene.village），
    算亲历；参与的节拍照样算。城里的王、在刑场的警吏不算。"""
    _, s = settle(WORLD, at(WEDDING), 3660)
    assert place_at(WORLD, s, "char.groom", RAIN) == WEDDING  # beat.11 把他带到婚礼上
    assert place_at(WORLD, s, "char.groom", "beat.10") == GROOM  # 节拍之前的地点，不含这个节拍
    for who in ("char.sister", "char.groom", "char.melos"):
        assert lived(WORLD, s, who, RAIN)
    assert lived(WORLD, s, "char.sister", "beat.11")
    assert not lived(WORLD, s, "char.king", RAIN)
    assert not lived(WORLD, s, "char.guards", RAIN)


def test_lived_is_not_presence() -> None:
    """lived() 不算「人在节拍的地点」：人物知道什么按 knows 和 learn，在场却不参与的节拍不给他（契约 2.1 ②）。
    没发生的节拍、玩家都是 False。"""
    _, s = settle(WORLD, at(WEDDING), 3660)
    assert place_at(WORLD, s, "char.sister", "beat.09") == WEDDING  # beat.09 在她家，参与的只有梅洛斯
    assert not lived(WORLD, s, "char.sister", "beat.09")
    assert not lived(WORLD, s, "char.sister", "beat.13")  # 3660 时还没发生
    assert place_at(WORLD, s, "char.sister", "beat.13") is None
    assert not lived(WORLD, s, "player", RAIN)
    assert place_at(WORLD, s, "player", RAIN) is None
