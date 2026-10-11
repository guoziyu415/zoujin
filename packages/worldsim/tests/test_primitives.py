"""knows()（R4）、travel_minutes()（R3 的路程）和 activity()（R7、快照）：叙事者的确定性规则和评测 S-2 用同一份。"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from zoujin_worldsim import SimState, activity, apply, check_effects, initial_state, knows, settle, travel_minutes

WORLD_DIR = Path(__file__).resolve().parents[3] / "worlds" / "hashire-merosu" / "1.0.0-draft"
WORLD: dict[str, Any] = json.loads((WORLD_DIR / "world.json").read_text(encoding="utf-8"))
ROLE = "role.traveler"
GROUND = "place.execution-ground"
RF = "rf_01J00000000000000000000000"


def at(t: int, effects: list[dict[str, Any]] | None = None) -> SimState:
    s = initial_state(WORLD, ROLE)
    if effects:
        s = apply(WORLD, s, {"t": 0, "dt": 0, "origin": "turn", "effects": effects})
    return settle(WORLD, s, t)[1]


def test_since_learn_and_own_improv() -> None:
    s = at(0)
    assert knows(WORLD, s, "char.selinuntius", "fact.friendship")  # since pre
    assert not knows(WORLD, s, "char.selinuntius", "fact.promise")  # since beat.06，还没发生
    s = at(1411)
    assert knows(WORLD, s, "char.selinuntius", "fact.promise")
    assert not knows(WORLD, s, "char.crowd", "fact.promise")
    s = apply(WORLD, s, {"t": s["t"], "dt": 0, "origin": "turn", "effects": [
        {"op": "learn", "character": "char.crowd", "fact": "fact.promise"},
        {"op": "improv", "factId": RF, "character": "char.old-man", "statement": "…"},
    ]})  # fmt: skip
    assert knows(WORLD, s, "char.crowd", "fact.promise")
    assert knows(WORLD, s, "char.old-man", RF)  # 自己的即兴设定
    assert not knows(WORLD, s, "char.melos", RF)  # 别人的，没学到
    s = apply(WORLD, s, {"t": s["t"], "dt": 0, "origin": "turn",
                         "effects": [{"op": "learn", "character": "char.melos", "fact": RF}]})  # fmt: skip
    assert knows(WORLD, s, "char.melos", RF)
    assert not knows(WORLD, s, "char.nobody", "fact.promise")
    assert not knows(WORLD, s, "char.melos", "fact.nothing")


def test_a_fact_that_is_not_true_this_run_is_known_by_nobody() -> None:
    """契约 2.3（1.4）：trueFrom 的节拍没发生，谁的 knows、学到的都不算（S-064）。"""
    early = at(0, [{"op": "learn", "character": "char.crowd", "fact": "fact.promise"}])  # 布置的，R4 本该拒
    assert not knows(WORLD, early, "char.crowd", "fact.promise")
    assert knows(WORLD, settle(WORLD, early, 1411)[1], "char.crowd", "fact.promise")  # beat.05 发生以后才算
    s = at(1411)
    late = {**copy.deepcopy(s), "beats": {**s["beats"], "beat.25": "happened"}}  # Melos 的 since 是 beat.25
    for s2, known in [(None, False), ("prevented", False), ("happened", True)]:  # trueFrom 是 beat.s2
        beats = late["beats"] if s2 is None else {**late["beats"], "beat.s2": s2}
        assert knows(WORLD, {**late, "beats": beats}, "char.melos", "fact.selinuntius-doubted-once") is known


def test_the_player_knows_what_the_role_knows_and_what_they_learn() -> None:
    """玩家 = 身份的 initialKnowledge + 这一局学到的（契约 2.1，1.7）。"""
    s = at(0)
    assert knows(WORLD, s, "player", "fact.city-silent")
    assert not knows(WORLD, s, "player", "fact.king-killings")
    assert check_effects(WORLD, s, [{"op": "learn", "character": "player", "fact": "fact.king-killings"}], "turn") == []
    bad = check_effects(WORLD, s, [{"op": "learn", "character": "char.nobody", "fact": "fact.king-killings"}], "turn")
    assert [p["code"] for p in bad] == ["unknown-id"]
    told = [{"op": "learn", "character": "player", "fact": "fact.king-killings"}]  # 老爺告诉玩家的
    s = apply(WORLD, s, {"t": 0, "dt": 0, "origin": "turn", "effects": told})
    assert knows(WORLD, s, "player", "fact.king-killings")
    assert not knows(WORLD, s, "char.melos", "fact.king-killings")  # 梅洛斯 since beat.03
    boy = settle(WORLD, initial_state(WORLD, "role.shepherd-boy"), 1980)[1]
    assert knows(WORLD, boy, "player", "fact.sister-engaged")
    assert not knows(WORLD, boy, "player", "fact.city-silent")


def test_the_player_learns_public_facts_of_beats_they_see() -> None:
    """节拍发生时玩家在节拍的地点：settle 在那个系统事件里写 learn，只写 public 的（契约 2.1、2.3，1.7）。"""
    drafts, s = settle(WORLD, at(0, [{"op": "set", "var": "var.player.location", "value": GROUND}]), 1201)
    arrest = next(d["event"] for d in drafts if d["beat"] == "beat.04")  # 捕缚在王城前庭
    assert {"op": "learn", "character": "player", "fact": "fact.melos-dagger"} in arrest["effects"]
    assert knows(WORLD, s, "player", "fact.melos-dagger")
    drafts, s = settle(WORLD, s, 1411)  # 立约（beat.05）、人质（beat.06）在王城里，玩家不在
    assert not any(e.get("character") == "player" for d in drafts for e in d["event"]["effects"])
    assert not knows(WORLD, s, "player", "fact.promise")
    away = at(1411)  # 一直在广场
    assert not knows(WORLD, away, "player", "fact.melos-dagger")
    assert not any(e["op"] == "learn" for d in settle(WORLD, at(0), 1201)[0] for e in d["event"]["effects"])


def test_the_player_is_away_while_an_act_change_settles() -> None:
    """幕切换的第 3 步（契约 2.8.1）：玩家的地点还没换，但这一段算不在场，不写 learn；别的照旧。"""
    there = at(0, [{"op": "set", "var": "var.player.location", "value": GROUND}])
    seen, s_seen = settle(WORLD, there, 1201)
    away, s_away = settle(WORLD, there, 1201, player_present=False)
    assert not any(e.get("character") == "player" for d in away for e in d["event"]["effects"])
    assert not knows(WORLD, s_away, "player", "fact.melos-dagger")
    assert knows(WORLD, s_seen, "player", "fact.melos-dagger")

    def unlearned(e: dict[str, Any]) -> dict[str, Any]:
        return {**e, "effects": [x for x in e["effects"] if x.get("character") != "player"]}

    assert [unlearned(d["event"]) for d in seen] == [d["event"] for d in away]
    assert s_away["beats"] == s_seen["beats"]


def test_walking_minutes_take_the_shortest_way() -> None:
    def m(a: str, b: str) -> int | None:
        return travel_minutes(WORLD, f"place.{a}", f"place.{b}")

    assert m("syracuse-square", "syracuse-square") == 0
    # 同一场景里走动 0 分（S-038，api-contract 3.8）：广场、工房、刑场
    assert m("syracuse-square", "execution-ground") == m("stonemason-workshop", "execution-ground") == 0
    assert m("village", "groom-house") == m("melos-home", "groom-house") == 0
    # 跨场景按 adjacent，取最短：广场 → 王城直接 10 分，经刑场 0 + 5 分更短
    assert m("syracuse-square", "castle") == m("stonemason-workshop", "castle") == m("execution-ground", "castle") == 5
    assert m("castle", "syracuse-square") == 5
    assert m("village", "neighbor-village") == 120  # 邻村没有场景（sceneRef null）
    assert m("neighbor-village", "river") == 180
    assert m("road-to-city", "syracuse-square") == 60
    # 归途每个停留点一个场景（S-081 ②：「ひとりで先へ行く」要花路上的时间），按 adjacent 的步行分钟
    assert m("river", "mountain-pass") == 100
    assert m("river", "road-to-city") == 100 + 45 + 120
    assert m("melos-home", "syracuse-square") == 120 + 180 + 100 + 45 + 120 + 60
    assert m("syracuse-square", "nowhere") is None


def test_unreachable_and_no_pacing() -> None:
    w = copy.deepcopy(WORLD)
    w["places"].append({**w["places"][0], "id": "place.island", "adjacent": [], "sceneRef": None})
    assert travel_minutes(w, "place.syracuse-square", "place.island") is None
    assert travel_minutes(w, "place.island", "place.island") == 0
    w["pacing"] = {**w["pacing"], "sceneWalkMinutes": 3}
    assert travel_minutes(w, "place.syracuse-square", "place.execution-ground") == 3
    del w["pacing"]
    assert travel_minutes(w, "place.syracuse-square", "place.execution-ground") == 0


def test_activity_follows_the_beats_until_someone_is_moved() -> None:
    """契约 2.4（1.1）：开局是 initialActivity，节拍给的 activity 持续到下一个给他的节拍或移动为止。"""
    assert activity(WORLD, at(0), "char.sister") == "work"  # initialActivity，在 initialPlace
    assert activity(WORLD, at(0), "char.melos") == "idle"  # 省略 = idle
    assert activity(WORLD, at(2040), "char.sister") == "talk"  # beat.08 给的
    assert activity(WORLD, at(1180), "char.melos") == "talk"  # beat.03
    assert activity(WORLD, at(1200), "char.melos") == "idle"  # beat.04 把他移进王城、没给 activity
    assert activity(WORLD, at(1230), "char.melos") == "talk"  # beat.05
    assert activity(WORLD, at(2070), "char.melos") == "sleep"  # beat.09
    assert activity(WORLD, at(3150), "char.melos") == "talk"  # beat.10，在花婿家
    assert activity(WORLD, at(3600), "char.melos") == "idle"  # beat.11 把参与人物带回家、没给 activity
    assert activity(WORLD, at(3600), "char.sister") == "talk"  # 一直在家，beat.08 给的还算
    assert activity(WORLD, at(0), "player") == "idle"
    assert activity(WORLD, at(0), "char.nobody") == "idle"


def test_absent_lasts_only_while_nobody_moves_them() -> None:
    """S-077 ⑩：absent 的人物被节拍带走（参与人物移到节拍地点，契约 3.1）以后就在场了。"""
    assert activity(WORLD, at(5390), "char.crowd") == "absent"  # 开局 absent，还在广场
    s = at(5400)  # beat.s1：群众是参与人物，移到刑场，节拍没给它 activity
    assert s["locations"]["char.crowd"] == GROUND
    assert activity(WORLD, s, "char.crowd") == "idle"
    assert activity(WORLD, s, "char.maiden") == "idle"  # 不是参与人物，被 outcomes 的 relocate 移过去
    assert activity(WORLD, s, "char.selinuntius") == "idle"  # beat.s1 给的


def test_activity_ends_when_an_event_moves_someone() -> None:
    """叙事者或人物的事件挪了人（不是节拍）：SimState 没有历史，按「此刻不在节拍让他在的地方」判，回到 idle。"""
    s = at(2070)
    assert activity(WORLD, s, "char.melos") == "sleep"
    moved = {"op": "relocate", "character": "char.melos", "place": "place.village"}
    s = apply(WORLD, s, {"t": s["t"], "dt": 0, "origin": "turn", "effects": [moved]})
    assert activity(WORLD, s, "char.melos") == "idle"


def test_activity_uses_the_outcomes_this_run_used() -> None:
    """节拍被玩家事先改了（altered）：按这一局实际的结果算他该在哪，不按原作的 relocate。"""
    canon = at(4590)  # beat.14：原作把梅洛斯移到村里
    assert canon["locations"]["char.melos"] == "place.village"
    assert activity(WORLD, canon, "char.melos") == "run"
    s = at(4590, [{"op": "beat", "beat": "beat.14", "to": "altered", "outcomes": []}])  # 改成不挪他
    assert s["beats"]["beat.14"] == "altered"
    assert s["locations"]["char.melos"] == "place.melos-home"
    assert activity(WORLD, s, "char.melos") == "run"
