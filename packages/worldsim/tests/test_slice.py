"""切片版世界模型（1.0.0-slice，S-077）：生成脚本的改动按 W-1 的推演走得通。

第一幕的两个去处都跳到三日目 17:30 的刑场（契约 2.8.1：玩家的 act-transition 事件带去处的效果 → 结算到目标时间 →
系统的 act-transition 事件），之后照时间表到结局。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from zoujin_worldsim import (
    Sim,
    SimState,
    apply,
    check_effects,
    classify,
    flat,
    initial_state,
    knows,
    pick_set_piece,
    settle,
)

REPO = Path(__file__).resolve().parents[3]
SLICE: dict[str, Any] = json.loads((REPO / "worlds/hashire-merosu/1.0.0-slice/world.json").read_text(encoding="utf-8"))
ROLE = "role.traveler"
ACTS = {a["id"]: a for a in SLICE["acts"]}
EXITS = {e["id"]: e for e in ACTS["act.1"]["exits"]}
GROUND = "place.execution-ground"


def run_to(s: SimState, t2: int | None) -> SimState:
    _, after = settle(SLICE, s, t2)
    return after


def jump(s: SimState, exit_id: str) -> SimState:
    """收幕时选去处，按契约 2.8.1 第 2〜4 步跳到下一幕起点。"""
    ex = EXITS[exit_id]
    t = s["t"]
    s = apply(SLICE, s, {"t": t, "dt": 0, "type": "act-transition", "actor": "player", "origin": "act",
                         "exitId": exit_id, "effects": ex["effects"]})  # fmt: skip
    return land(s, ex)


def land(s: SimState, ex: dict[str, Any]) -> SimState:
    """第 3、4 步：结算到目标时间，系统事件改幕和玩家所在地。"""
    s = run_to(s, ex["t"])
    step4 = [
        {"op": "set", "var": "var.act.current", "value": ex["toAct"]},
        {"op": "set", "var": "var.player.location", "value": ex["place"]},
    ]
    return apply(SLICE, s, {"t": ex["t"], "dt": 0, "type": "act-transition", "actor": "system",
                            "origin": "act", "effects": step4})  # fmt: skip


def act1_end() -> SimState:
    """旅人的第一幕照原作走到梅洛斯出发（beat.07 收幕）。"""
    return run_to(initial_state(SLICE, ROLE), ACTS["act.1"]["end"]["atLatest"])


def test_slice_opens_only_the_traveler_the_plaza_and_two_exits() -> None:
    assert "1.0.0-slice" in SLICE["worldModelVersion"]
    assert [r["id"] for r in SLICE["roles"]] == [ROLE]
    assert "conditionalAccess" not in SLICE["roles"][0]
    assert ACTS["act.1"]["scenes"] == ACTS["act.4"]["scenes"] == ["scene.syracuse-square"]
    assert list(EXITS) == ["exit.1.city", "exit.1.old-man"]
    assert [e["sub"] for e in EXITS.values()] == ["西の門が見える所で", "老爺があなたを覚えている"]
    assert all(a["place"] in SLICE["roles"][0]["access"] for a in SLICE["affordances"])  # 「保証する」不在
    chars = {c["id"]: c for c in SLICE["characters"]}
    assert {c for c, x in chars.items() if x["talkable"]} == {"char.melos", "char.old-man"}  # S-050
    assert chars["char.selinuntius"]["initialActivity"] == chars["char.philostratus"]["initialActivity"] == "absent"


def test_the_narrator_cannot_arrest_the_player(world: dict[str, Any]) -> None:
    arrest = [{"op": "set", "var": "var.player.custody", "value": "arrested"}]
    assert check_effects(world, initial_state(world, ROLE), arrest, "turn") == []
    problems = check_effects(SLICE, initial_state(SLICE, ROLE), arrest, "turn")
    assert [p["code"] for p in problems] == ["bad-value"]


def test_the_old_man_exit_needs_the_walk_home() -> None:
    s = act1_end()
    need = EXITS["exit.1.old-man"]["requires"]
    assert not Sim(SLICE).holds(need, flat(s))
    walk = next(a for c in SLICE["characters"] for a in c.get("mutualAid", []) if a["id"] == "aid.old-man.listen")
    s = apply(SLICE, s, {"t": s["t"], "dt": 0, "origin": "turn", "effects": walk["effects"]})
    assert Sim(SLICE).holds(need, flat(s))


def test_a_feasible_plan_lands_where_act_1_plan_says() -> None:
    """「ほかの考えがある」成行（契约 1.7 的 Act.plan，C-19）：固定的效果加上打算自己的（群众知道约定），
    同样跳到 17:30 的刑场。"""
    plan = ACTS["act.1"]["plan"]
    assert (plan["toAct"], plan["place"], plan["t"], plan["spot"]) == ("act.4", GROUND, 5370, "stake-front")
    assert "opener" not in plan["arrival"]
    s = act1_end()
    told = [{"op": "learn", "character": "char.crowd", "fact": "fact.promise"}]
    effects = plan["effects"] + told
    assert check_effects(SLICE, s, effects, "act") == []
    said = {"label": "町の人々にメロスの約束を話して回る", **{k: plan[k] for k in ("toAct", "place", "t")}}
    s = apply(SLICE, s, {"t": s["t"], "dt": 0, "type": "act-transition", "actor": "player", "origin": "act",
                         "plan": said, "effects": effects})  # fmt: skip
    s = land(s, plan)
    assert (s["t"], s["vars"]["var.act.current"], s["vars"]["var.player.location"]) == (5370, "act.4", GROUND)
    assert (s["locations"]["char.old-man"], s["spots"]["char.old-man"]) == (GROUND, "ground-west")
    assert s["locations"]["char.philostratus"] == "place.road-to-city"
    assert classify(SLICE, run_to(s, None)) == "canon-reunion"


def test_set_pieces_hang_where_the_traveler_can_see_them() -> None:
    """固定演出（契约 2.11，S-080 ④）挂的节拍在旅人去得了的地点；王城门口被拒、工房走得进；
    工房的灯在 23:30（beat.06）灭；群众本来不知道约定。"""
    beats = {b["id"]: b for b in SLICE["beats"]}
    access = set(SLICE["roles"][0]["access"])
    for p in SLICE["setPieces"]:
        if "beat" in p["on"]:
            assert beats[p["on"]["beat"]]["place"] in access, p["id"]
    assert "place.castle" not in access and "place.stonemason-workshop" in access
    assert beats["beat.06"]["window"]["canonical"] == 1410  # 一日目前夜 23:30
    assert [o["id"] for o in SLICE["objects"]] == ["obj.workshop-door"]


def walk_to(place: str, t: int) -> SimState:
    s = initial_state(SLICE, ROLE)
    s = apply(SLICE, s, {"t": 0, "dt": 0, "origin": "turn",
                         "effects": [{"op": "set", "var": "var.player.location", "value": place}]})  # fmt: skip
    return run_to(s, t)


def lines_of(steps: list[tuple[SimState, dict[str, Any]]]) -> list[list[str] | None]:
    """按顺序问每个时机演哪一条，返回每次演的台词（没有固定演出是 None）。"""
    played: set[str] = set()
    out: list[list[str] | None] = []
    for s, hook in steps:
        p = pick_set_piece(SLICE, s, hook, played)
        out.append(None if p is None else [x.get("line") or x["narration"] for x in p["lines"]])
        played |= {p["id"]} if p else set()
    return out


GATE = {"act": "go", "target": "place.castle", "refused": True}
STAND_BACK, NOT_TWICE = "下がれ、旅の者。ここから先は、通さぬ。", "二度は言わぬ。下がれ。"


def guard(lines: list[str] | None) -> str | None:
    """这一次警吏说的那句（没有固定演出是 None）。"""
    return None if lines is None else next(x for x in lines if x in (STAND_BACK, NOT_TWICE))


def test_the_guards_say_each_line_once_and_the_arrest_always_plays() -> None:
    """UX 10-10：警吏的两句各说一次；抓梅洛斯那场照演，之前被挡过的话那场改说第二句；两句都说过以后交给叙事者。"""
    before, after = walk_to(GROUND, 1100), walk_to(GROUND, 1201)
    arrest = (after, {"beat": "beat.04"})
    first = lines_of([arrest, (after, GATE), (after, GATE)])  # 先被抓再走上去
    then_ = lines_of([(before, GATE), arrest, (after, GATE)])  # 先走上去再被抓
    assert [guard(x) for x in first] == [STAND_BACK, NOT_TWICE, None]
    assert [guard(x) for x in then_] == [STAND_BACK, NOT_TWICE, None]
    assert then_[1] is not None and then_[1][2] == "メロスは、王城の奥へ引かれていった。"
    assert lines_of([(walk_to("place.syracuse-square", 1201), {"beat": "beat.04"})]) == [None]  # 不在场


def test_after_the_promise_the_guards_tell_it() -> None:
    """S-077 ⑪：立约以后第一次走到门口，不管之前挡过几次，警吏说出约定，玩家知道了；之后「二度は言わぬ」没说过就说。"""
    after, promised = walk_to(GROUND, 1201), walk_to(GROUND, 1231)
    told = ["警吏が、あなたの前に槍を下ろした。", "下がれ。メロスとかいう羊飼いなら、王と約束をした。",
            "三日目の日没までに戻らねば、身代わりの石工セリヌンティウスが磔だ。"]  # fmt: skip
    assert lines_of([(promised, GATE), (promised, GATE), (promised, GATE)]) == [told, [NOT_TWICE], None]
    seen_both = lines_of([(after, {"beat": "beat.04"}), (after, GATE), (promised, GATE), (promised, GATE)])
    assert seen_both[2:] == [told, None]  # 两句都说过了也照样说出约定，之后交给叙事者
    just_before = walk_to(GROUND, 1229)  # 立约以前只赶人
    assert lines_of([(after, {"beat": "beat.04"}), (just_before, GATE)])[1] == [NOT_TWICE]
    p = pick_set_piece(SLICE, promised, GATE, set())
    assert p is not None and p["learns"] == [{"character": "player", "fact": "fact.promise"}]
    assert not knows(SLICE, promised, "player", "fact.promise")
    learns = [{"op": "learn", **x} for x in p["learns"]]  # B-3 和演出同一次提交
    heard = apply(SLICE, promised, {"t": promised["t"], "dt": 0, "origin": "turn", "effects": learns})
    assert knows(SLICE, heard, "player", "fact.promise")


def test_the_workshop_light_goes_out_once() -> None:
    yard = {"act": "move", "target": "place.stonemason-workshop"}
    door = {"act": "examine", "target": "obj.workshop-door"}
    early, late = walk_to("place.stonemason-workshop", 1300), walk_to("place.stonemason-workshop", 1411)
    got = lines_of([(early, yard), (early, door), (early, door), (late, yard), (late, door)])
    assert got[0] and got[0][0].startswith("戸は閉ざされている")
    assert got[1] is not None and got[1][0] == "もう遅い。用があるなら、明日にしてくれ。"
    assert got[2:] == [None, ["工房の灯は、いつのまにか消えていた。"], None]


def test_the_crowd_makes_way_only_if_told() -> None:
    s = walk_to(GROUND, 5461)
    assert s["beats"]["beat.24"] == "happened" and not knows(SLICE, s, "char.crowd", "fact.promise")
    assert lines_of([(s, {"beat": "beat.24"})]) == [None]
    s = apply(SLICE, s, {"t": s["t"], "dt": 0, "origin": "turn",
                         "effects": [{"op": "learn", "character": "char.crowd", "fact": "fact.promise"}]})  # fmt: skip
    (shout,) = lines_of([(s, {"beat": "beat.24"})])
    assert shout == ["メロスだ！　メロスが帰って来た！", "人々が振り返り、道をあけた。"]


@pytest.mark.parametrize(
    ("exit_id", "old_man_spot"), [("exit.1.city", "stake-front"), ("exit.1.old-man", "stake-front-side")]
)
def test_both_exits_land_on_the_execution_ground_at_1730_and_play_to_the_canon_ending(
    exit_id: str, old_man_spot: str
) -> None:
    s = jump(act1_end(), exit_id)
    assert s["t"] == 5370
    assert knows(SLICE, s, "player", "fact.promise")  # 幕末页算玩家知道约定（S-077 ⑫）
    assert s["vars"]["var.act.current"] == "act.4"
    assert s["vars"]["var.player.location"] == GROUND
    assert (s["locations"]["char.old-man"], s["spots"]["char.old-man"]) == (GROUND, old_man_spot)
    assert s["locations"]["char.philostratus"] == "place.road-to-city"
    assert s["locations"]["char.selinuntius"] == "place.castle"  # 17:30 刑场还空着，beat.s1 在 18:00

    s = run_to(s, 5400)  # beat.s1：人质上磔台，王站在群众背后，少女在群众前排
    assert {c: (s["locations"][c], s["spots"].get(c)) for c in ("char.selinuntius", "char.king", "char.maiden")} == {
        "char.selinuntius": (GROUND, "stake"),
        "char.king": (GROUND, "king-west"),
        "char.maiden": (GROUND, "crowd-front"),
    }

    s = run_to(s, None)
    assert classify(SLICE, s) == "canon-reunion"
    assert s["spots"]["char.melos"] == "scaffold"
    assert (s["locations"]["char.old-man"], s["spots"]["char.old-man"]) == (GROUND, old_man_spot)
