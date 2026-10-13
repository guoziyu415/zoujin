"""The slice world model (1.0.0-slice, S-077): the generator script's changes work under the W-1 simulation.

Both act 1 exits jump to the execution ground at 17:30 on 三日目 (contract 2.8.1: the player's act-transition event
carries the exit's effects → settle to the target time → the system's act-transition event), and from there the
timetable runs to the ending.

スライス版の世界モデル（1.0.0-slice、S-077）：生成スクリプトの変更が W-1 のシミュレーションで成り立つ。

第一幕の 2 つの行き先はどちらも三日目 17:30 の刑場へ飛ぶ（契約 2.8.1：プレイヤーの act-transition イベントが行き先の
効果を運ぶ → 目標時刻まで精算 → システムの act-transition イベント）。その後は時刻表どおりに結末まで進む。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from zoujin_worldsim import (
    OCCURRED,
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
    """Choose an exit when closing the act, then jump to the next act's starting point per contract 2.8.1 steps 2〜4.

    幕を閉じるときに行き先を選び、契約 2.8.1 の第 2〜4 段階に従って次の幕の起点へ飛ぶ。
    """
    ex = EXITS[exit_id]
    t = s["t"]
    s = apply(SLICE, s, {"t": t, "dt": 0, "type": "act-transition", "actor": "player", "origin": "act",
                         "exitId": exit_id, "effects": ex["effects"]})  # fmt: skip
    return land(s, ex)


def land(s: SimState, ex: dict[str, Any]) -> SimState:
    """Steps 3 and 4: settle to the target time; a system event changes the act and the player's location.

    第 3、4 段階：目標時刻まで精算し、システムイベントが幕とプレイヤーの所在地を変える。
    """
    s = run_to(s, ex["t"])
    step4 = [
        {"op": "set", "var": "var.act.current", "value": ex["toAct"]},
        {"op": "set", "var": "var.player.location", "value": ex["place"]},
    ]
    return apply(SLICE, s, {"t": ex["t"], "dt": 0, "type": "act-transition", "actor": "system",
                            "origin": "act", "effects": step4})  # fmt: skip


def act1_end() -> SimState:
    """The traveler's act 1 follows the original story until Melos sets off (beat.07 closes the act).

    旅人の第一幕は原作どおり、メロスの出発（beat.07 で幕を閉じる）まで進む。
    """
    return run_to(initial_state(SLICE, ROLE), ACTS["act.1"]["end"]["atLatest"])


def test_slice_opens_only_the_traveler_the_plaza_and_two_exits() -> None:
    assert "1.0.0-slice" in SLICE["worldModelVersion"]
    assert [r["id"] for r in SLICE["roles"]] == [ROLE]
    assert "conditionalAccess" not in SLICE["roles"][0]
    assert ACTS["act.1"]["scenes"] == ACTS["act.4"]["scenes"] == ["scene.syracuse-square"]
    assert list(EXITS) == ["exit.1.city", "exit.1.old-man"]
    assert [e["sub"] for e in EXITS.values()] == ["西の門が見える所で", "老爺があなたを覚えている"]
    # 「保証する」 is not there
    # 「保証する」はない
    assert all(a["place"] in SLICE["roles"][0]["access"] for a in SLICE["affordances"])
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
    """「ほかの考えがある」 works out (contract 1.7 Act.plan, C-19): the fixed effects plus the plan's own (the crowd
    knows the promise), and it also jumps to the execution ground at 17:30.

    「ほかの考えがある」が成立する（契約 1.7 の Act.plan、C-19）：固定の効果にプラン自身のもの（群衆が約束を知る）を
    加え、同じく 17:30 の刑場へ飛ぶ。
    """
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
    """The beats set pieces hang on (contract 2.11, S-080 ④) are at places the traveler can reach; the castle gate
    refuses entry, the workshop can be entered; the workshop light goes out at 23:30 (beat.06); the crowd did not know
    the promise to begin with.

    固定演出（契約 2.11、S-080 ④）を付けるビートは旅人が行ける場所にある。王城の門では拒まれ、工房には入れる。
    工房の灯は 23:30（beat.06）に消える。群衆はもともと約束を知らない。
    """
    beats = {b["id"]: b for b in SLICE["beats"]}
    access = set(SLICE["roles"][0]["access"])
    for p in SLICE["setPieces"]:
        if "beat" in p["on"]:
            assert beats[p["on"]["beat"]]["place"] in access, p["id"]
    assert "place.castle" not in access and "place.stonemason-workshop" in access
    assert beats["beat.06"]["window"]["canonical"] == 1410  # Night before 一日目, 23:30 / 一日目前夜 23:30
    assert [o["id"] for o in SLICE["objects"]] == ["obj.workshop-door"]


def walk_to(place: str, t: int) -> SimState:
    s = initial_state(SLICE, ROLE)
    s = apply(SLICE, s, {"t": 0, "dt": 0, "origin": "turn",
                         "effects": [{"op": "set", "var": "var.player.location", "value": place}]})  # fmt: skip
    return run_to(s, t)


def lines_of(steps: list[tuple[SimState, dict[str, Any]]]) -> list[list[str] | None]:
    """Asks in order which set piece plays at each moment and returns the lines played each time (None when there is
    no set piece).

    各タイミングでどの固定演出を上演するかを順に問い、毎回上演したセリフを返す（固定演出がなければ None）。
    """
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
    """The line the guard says this time (None when there is no set piece).

    今回警吏が言うセリフ（固定演出がなければ None）。
    """
    return None if lines is None else next(x for x in lines if x in (STAND_BACK, NOT_TWICE))


def test_the_guards_say_each_line_once_and_the_arrest_always_plays() -> None:
    """UX 10-10: each of the guard's two lines is said once; the scene of Melos's arrest always plays, and if the
    player was turned away before, that scene uses the second line instead; once both lines have been said, it is left
    to the narrator.

    UX 10-10：警吏の 2 つのセリフはそれぞれ 1 回だけ言う。メロスの捕縛の場面は必ず上演し、以前に追い返されていたら
    その場面では 2 つ目のセリフに変える。両方とも言った後はナレーターに任せる。
    """
    before, after = walk_to(GROUND, 1100), walk_to(GROUND, 1201)
    arrest = (after, {"beat": "beat.04"})
    first = lines_of([arrest, (after, GATE), (after, GATE)])  # Arrested first, then walking up / 先に捕まってから近づく
    # Walking up first, then the arrest
    # 先に近づいてから捕まる
    then_ = lines_of([(before, GATE), arrest, (after, GATE)])
    assert [guard(x) for x in first] == [STAND_BACK, NOT_TWICE, None]
    assert [guard(x) for x in then_] == [STAND_BACK, NOT_TWICE, None]
    assert then_[1] is not None and then_[1][2] == "メロスは、王城の奥へ引かれていった。"
    # Not present
    # 在場していない
    assert lines_of([(walk_to("place.syracuse-square", 1201), {"beat": "beat.04"})]) == [None]


def test_after_the_promise_the_guards_tell_it() -> None:
    """S-077 ⑪: the first time the player walks to the gate after the promise, however many times they were turned
    away before, the guard tells them the promise and the player knows it; after that, 「二度は言わぬ」 is said if it
    has not been said yet.

    S-077 ⑪：約束の後に初めて門まで行くと、それまで何度追い返されていても、警吏が約束を話し、プレイヤーはそれを
    知る。その後は「二度は言わぬ」をまだ言っていなければ言う。
    """
    after, promised = walk_to(GROUND, 1201), walk_to(GROUND, 1231)
    told = ["警吏が、あなたの前に槍を下ろした。", "下がれ。メロスとかいう羊飼いなら、王と約束をした。",
            "三日目の日没までに戻らねば、身代わりの石工セリヌンティウスが磔だ。"]  # fmt: skip
    assert lines_of([(promised, GATE), (promised, GATE), (promised, GATE)]) == [told, [NOT_TWICE], None]
    seen_both = lines_of([(after, {"beat": "beat.04"}), (after, GATE), (promised, GATE), (promised, GATE)])
    # Even with both lines said, the promise is still told; then the narrator takes over
    # 両方言った後でも約束は話し、その後はナレーターに任せる
    assert seen_both[2:] == [told, None]
    just_before = walk_to(GROUND, 1229)  # Before the promise, only turning people away / 約束の前は追い返すだけ
    assert lines_of([(after, {"beat": "beat.04"}), (just_before, GATE)])[1] == [NOT_TWICE]
    p = pick_set_piece(SLICE, promised, GATE, set())
    assert p is not None and p["learns"] == [{"character": "player", "fact": "fact.promise"}]
    assert not knows(SLICE, promised, "player", "fact.promise")
    # B-3 commits it together with the set piece
    # B-3 が演出と同じコミットで書く
    learns = [{"op": "learn", **x} for x in p["learns"]]
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


UNNOTICED = "群衆は、ひとりとして彼の到着に気がつかない。"
SHOVE = "メロスは最後の勇、先刻、濁流を泳いだように群衆を掻きわけ、掻きわけた。"
SHOUT = ["メロスだ！　メロスが帰って来た！", "人々が振り返り、道をあけた。"]


def set_vars(s: SimState, **vs: Any) -> SimState:
    effects = [{"op": "set", "var": f"var.{k.replace('__', '.')}", "value": v} for k, v in vs.items()]
    return apply(SLICE, s, {"t": s["t"], "dt": 0, "origin": "turn", "effects": effects})


def test_the_curtain_follows_the_book_and_the_crowd_makes_way_only_if_told() -> None:
    """S-087: beat.24 plays paragraphs 60〜62 of the original; when the crowd knows the promise (S-080 ④), after
    Melos's first shout a woman in the crowd recognizes him and the crowd makes way.

    S-087：beat.24 は原作の第 60〜62 段落どおりに上演する。群衆が約束を知っている（S-080 ④）ときは、メロスの第一声の
    後に群衆の中の女が彼に気づき、人々が道をあける。
    """
    s = walk_to(GROUND, 5461)
    assert s["beats"]["beat.24"] == "happened" and not knows(SLICE, s, "char.crowd", "fact.promise")
    (plain,) = lines_of([(s, {"beat": "beat.24"})])
    assert plain is not None and plain[2] == "間に合った。" and plain[4:6] == [UNNOTICED, SHOVE]
    assert not set(SHOUT) & set(plain)
    assert plain[-1] == "セリヌンティウスの縄は、ほどかれたのである。"
    s = apply(SLICE, s, {"t": s["t"], "dt": 0, "origin": "turn",
                         "effects": [{"op": "learn", "character": "char.crowd", "fact": "fact.promise"}]})  # fmt: skip
    (told,) = lines_of([(s, {"beat": "beat.24"})])
    # Key piece.crowd-makes-way/5 (B-6)
    # キー piece.crowd-makes-way/5（B-6）
    assert told is not None and told[4:6] == SHOUT and UNNOTICED not in told
    # The crowd makes way, no 掻きわけ
    # 人々が道をあけ、掻きわけない
    assert told[:4] == plain[:4] and told[6:] == plain[6:] and SHOVE not in told


def test_the_curtain_when_you_are_the_hostage_says_you() -> None:
    """B-4 lets the player be the hostage: on the pillar, the legs and the rope become 「あなた」, and Melos does not
    say 「彼を人質にした」.

    B-4 でプレイヤーが人質になれる：柱の上、脚、縄が「あなた」に変わり、メロスは「彼を人質にした」と言わない。
    """
    s = set_vars(walk_to(GROUND, 5461), hostage__who="player")
    (you,) = lines_of([(s, {"beat": "beat.24"})])
    assert you is not None and "あなたの縄は、ほどかれたのである。" in you
    assert not any("セリヌンティウス" in x or "彼を人質にした" in x for x in you)


def test_the_curtain_plays_only_while_the_friend_is_on_the_cross() -> None:
    """UX #107: if the king relented first and the hostage was already released, or the hostage was never brought
    to the execution ground (beat.s1 did not happen), beat.24 does not play 「釣り上げられてゆく」, only the fallback
    line. The condition is evaluated after beat.24 is applied, when hostage.fate is already released, so it looks at
    beat.s1 and the king's heart.

    UX #107：王が先に改心して人質がすでに解放された、または人質が刑場に連れてこられなかった（beat.s1 が起きて
    いない）場合、beat.24 は「釣り上げられてゆく」を上演せず、代わりの一文だけを上演する。条件は beat.24 の適用後に
    評価し、そのとき hostage.fate はすでに released なので、beat.s1 と王の心を見る。
    """
    made_it = [["メロスは疾風の如く刑場に突入した。間に合った。"]]
    s = walk_to(GROUND, 5461)
    assert s["beats"]["beat.s1"] == "happened" and s["vars"]["var.hostage.fate"] == "released"
    assert lines_of([(set_vars(s, king__trust=80, king__disposition="reformed"), {"beat": "beat.24"})]) == made_it
    no_cross = {**s, "beats": {**s["beats"], "beat.s1": "prevented"}}
    assert lines_of([(no_cross, {"beat": "beat.24"})]) == made_it


def test_a_king_who_already_relented_does_not_relent_again() -> None:
    """The king relented before the execution ground (trust over 70): beat.26 does not happen and 「わしの心に勝った」
    does not play either (UX #107); it still counts as a run where the king relents.

    王が刑場より前に改心した（信頼が 70 を超えた）：beat.26 は起きず、「わしの心に勝った」も上演しない（UX #107）。
    それでも王が改心したプレイとして数える。
    """
    s = set_vars(walk_to(GROUND, 5300), king__trust=80, king__disposition="reformed")
    s = run_to(s, 5520)
    assert s["beats"]["beat.24"] == "happened" and s["beats"].get("beat.26") not in OCCURRED
    assert s["vars"]["var.king.disposition"] == "reformed" and classify(SLICE, s) == "canon-reunion"


def test_the_king_looks_at_melos_and_you_when_you_are_the_hostage() -> None:
    s = walk_to(GROUND, 5476)
    assert s["beats"]["beat.26"] == "happened"
    p = pick_set_piece(SLICE, s, {"beat": "beat.26"}, set())
    assert p is not None and p["id"] == "piece.king-asks"
    p = pick_set_piece(SLICE, set_vars(s, hostage__who="player"), {"beat": "beat.26"}, set())
    assert p is not None and p["id"] == "piece.king-asks-you" and "メロスとあなたの様" in p["lines"][0]["narration"]
    assert p["lines"][1:] == pick_set_piece(SLICE, s, {"beat": "beat.26"}, set())["lines"][1:]  # type: ignore[index]


@pytest.mark.parametrize(
    ("melos", "seli", "piece"),
    [
        (True, True, "piece.embrace"),
        (True, False, "piece.embrace-melos-doubted"),
        (False, True, "piece.embrace-selinuntius-doubted"),
        (False, False, "piece.embrace-neither"),
    ],
)
def test_the_embrace_follows_who_doubted(melos: bool, seli: bool, piece: str) -> None:
    """One set piece for each of beat.25's three variants, with the same conditions as the variants: whoever
    doubted asks the other to strike them.

    beat.25 の 3 つのバリアントそれぞれに固定演出が 1 つあり、条件はバリアントと同じ：疑った方が相手に自分を殴れと
    頼む。
    """
    s = set_vars(walk_to(GROUND, 5461), melos__doubted=melos, selinuntius__doubted=seli)
    p = pick_set_piece(SLICE, s, {"beat": "beat.25"}, set())
    assert p is not None and p["id"] == piece
    asks = {x["speaker"] for x in p["lines"] if "私を殴れ" in x.get("line", "")}
    assert asks == ({"char.melos"} if melos else set()) | ({"char.selinuntius"} if seli else set())


@pytest.mark.parametrize(
    ("exit_id", "old_man_spot"), [("exit.1.city", "stake-front"), ("exit.1.old-man", "stake-front-side")]
)
def test_both_exits_land_on_the_execution_ground_at_1730_and_play_to_the_canon_ending(
    exit_id: str, old_man_spot: str
) -> None:
    s = jump(act1_end(), exit_id)
    assert s["t"] == 5370
    # The end-of-act page counts the player as knowing the promise (S-077 ⑫)
    # 幕末ページで約束を知ったとする
    assert knows(SLICE, s, "player", "fact.promise")
    assert s["vars"]["var.act.current"] == "act.4"
    assert s["vars"]["var.player.location"] == GROUND
    assert (s["locations"]["char.old-man"], s["spots"]["char.old-man"]) == (GROUND, old_man_spot)
    assert s["locations"]["char.philostratus"] == "place.road-to-city"
    # At 17:30 the execution ground is still empty; beat.s1 is at 18:00
    # 17:30 の刑場はまだ空、beat.s1 は 18:00
    assert s["locations"]["char.selinuntius"] == "place.castle"

    # beat.s1: the hostage goes up the cross, the king stands behind the crowd, the maiden is at the front of the crowd
    # beat.s1：人質は磔台へ、王は群衆の後ろ、少女は群衆の前列
    s = run_to(s, 5400)
    assert {c: (s["locations"][c], s["spots"].get(c)) for c in ("char.selinuntius", "char.king", "char.maiden")} == {
        "char.selinuntius": (GROUND, "stake"),
        "char.king": (GROUND, "king-west"),
        "char.maiden": (GROUND, "crowd-front"),
    }

    s = run_to(s, None)
    assert classify(SLICE, s) == "canon-reunion"
    assert s["spots"]["char.melos"] == "scaffold"
    assert (s["locations"]["char.old-man"], s["spots"]["char.old-man"]) == (GROUND, old_man_spot)
