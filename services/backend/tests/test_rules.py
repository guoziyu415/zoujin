"""叙事者第 3 步（B-2 验收第 1 组）：对照 `evals/s2_check.py` 的 `judge()`，每条规则自己写的正反例，不在场的人物。

不要数据库：起点用和 `eval_api.setup()` 同一个 `play_setup()` 在内存里推出来。例子都是为测试写的，不取自任何留出样本。
"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
from collections.abc import Mapping, Sequence
from dataclasses import replace
from functools import cache
from types import ModuleType
from typing import Any

import pytest
from zoujin_backend.config import DEFAULT_WORLD, REPO
from zoujin_backend.eval_api import _scenarios, play_setup
from zoujin_backend.ids import IdGen
from zoujin_backend.narrator import rules
from zoujin_backend.narrator.rules import Turn
from zoujin_backend.narrator.writer import Writer
from zoujin_backend.projection import snapshot
from zoujin_backend.world import Book, Library
from zoujin_worldsim import SimState, activity, initial_state

from .conftest import SCHEMAS

Json = Any

LIBRARY = Library(REPO / "worlds", REPO / "assets" / "scenes", DEFAULT_WORLD)
BOOK: Book = LIBRARY.book("hashire-merosu")  # type: ignore[assignment]
W = BOOK.world
SLICE = REPO / "worlds" / "hashire-merosu" / "1.0.0-slice" / "world.json"
S2_DEV = [json.loads(x) for x in (REPO / "evals" / "s2" / "s2_dev.jsonl").read_text(encoding="utf-8").splitlines()]
SQUARE = {"role": "role.traveler", "checkpoint": "sc.canon@t=1080", "place": "place.syracuse-square"}
OLD = "char.old-man"


@cache
def s2_check() -> ModuleType:
    """数据的最简判法（evals/s2_check.py）。它 import 参考实现的 check_evals，路径照它的 README 加。"""
    ref = str(REPO / "packages" / "worldsim" / "reference")
    if ref not in sys.path:
        sys.path.insert(0, ref)
    spec = importlib.util.spec_from_file_location("s2_check", REPO / "evals" / "s2_check.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@cache
def data_judge() -> Any:
    scen = json.loads((DEFAULT_WORLD.parent / "scenarios.json").read_text(encoding="utf-8"))
    return s2_check().S2(W, scen)


def start(setup: Mapping[str, Json], book: Book = BOOK) -> SimState:
    """和 eval_api.setup() 同样推到起点（内存里，不写库）。"""
    w = Writer(
        book, "pt_test", initial_state(book.world, setup["role"]), key_base="k", turn_id=None, ids=IdGen(), now=""
    )
    play_setup(w, _scenarios(DEFAULT_WORLD.parent), setup)
    return w.state


def cand(state: SimState, effects: Sequence[Json], **kw: Any) -> Json:
    c: Json = {
        "t": state["t"],
        "actor": "player",
        "type": "say",
        "origin": "turn",
        "dt": 10,
        "place": state["vars"]["var.player.location"],
        "summary": "旅人が老爺と話した",
        "causes": [],
        "effects": list(effects),
    }
    c.update(kw)
    return c


def codes(state: SimState, c: Json, turn: Turn = rules.NO_TURN, world: Json = W) -> set[tuple[str, str]]:
    return {(h.rule, h.code) for h in rules.judge(world, state, c, turn=turn)}


def at(setup_events: Sequence[Json] = (), **kw: Any) -> SimState:
    return start({**SQUARE, **kw, "events": [{"effects": list(setup_events)}] if setup_events else []})


# —— 对照 judge() ——


@pytest.mark.parametrize("item", S2_DEV, ids=lambda x: x["id"])
def test_s2_dev_matches_the_data_judge(item: Json) -> None:
    """judge() 报的第 3 步都报；标成 rules 的报出主规则；合规的和标成 model 的一条都不报。"""
    state = start(item["setup"])
    turn = Turn(said=item["turn"].get("player", ""), act=item["turn"].get("act"))
    mine = {h.rule for h in rules.judge(W, state, item["candidate"], turn=turn)}
    theirs, _, errs = data_judge().judge(item)
    assert not errs
    assert theirs <= mine
    label = item["label"]
    if label["verdict"] == "pass" or label["stage"] == "model":
        assert mine == set()
    else:
        assert label["failedRules"][0] in mine
        assert mine <= set(label["failedRules"]) | set(label.get("acceptAlso", []))


def test_random_candidates_never_miss_what_the_data_judge_catches() -> None:
    """随机候选（S-2 公开样例和评测种子的起点 × 随机效果）：judge() 报的规则一定在第 3 步报的里面。"""
    rnd = random.Random(20261010)
    setups = [x["setup"] for x in S2_DEV] + [SQUARE]
    states = [(s, start(s)) for s in setups]
    beats = [b["id"] for b in W["beats"]]
    chars = [c["id"] for c in W["characters"]]
    places = [p["id"] for p in W["places"]]
    facts = W["facts"]
    items = [x["id"] for x in W["items"] if x.get("portable")]
    svars = [v for v in W["stateVars"] if v["type"] in ("enum", "bool", "place")]

    def effect() -> Json:
        k = rnd.choice(["beat", "set", "set", "relocate", "learn", "improv", "hold"])
        if k == "beat":
            to = rnd.choice(["prevented", "delayed", "hastened", "altered", "happened"])
            e: Json = {"op": "beat", "beat": rnd.choice(beats), "to": to}
            if to in ("delayed", "hastened"):
                e["minutes"] = rnd.choice([5, 30, 120])
            if to == "altered":
                e["outcomes"] = []
            return e
        if k == "set":
            v = rnd.choice(svars)
            vals = {"enum": v.get("values"), "bool": [True, False], "place": places}[v["type"]]
            return {"op": "set", "var": v["id"], "value": rnd.choice(vals)}
        if k == "relocate":
            return {"op": "relocate", "character": rnd.choice(chars), "place": rnd.choice(places)}
        if k == "learn":
            return {"op": "learn", "character": rnd.choice(chars), "fact": rnd.choice(facts)["id"]}
        if k == "improv":
            terms = rnd.choice(facts).get("spoilerTerms") or ["昔の話"]
            return {"op": "improv", "factId": "rf_01J00000000000000000000000", "character": rnd.choice(chars),
                    "statement": "ふと、" + rnd.choice(terms) + "のことを話した"}  # fmt: skip
        e = {"op": "hold", "item": rnd.choice(items), "to": rnd.choice([*chars, "player", None])}
        if rnd.random() < 0.4:
            e["from"] = rnd.choice(["player", *chars])
        return e

    judged = 0
    for _ in range(400):
        setup, state = rnd.choice(states)
        ppl = state["vars"]["var.player.location"]
        here = [c for c in chars if state["locations"].get(c) == ppl]
        c = cand(state, [effect() for _ in range(rnd.choice([1, 2]))], actor=rnd.choice(["player", *here]))
        c["dt"] = rnd.choice([0, 10, 60, 200])
        theirs, why, errs = data_judge().judge({"setup": setup, "turn": {"player": "テスト"}, "candidate": c})
        if errs:
            continue
        judged += 1
        mine = {h.rule for h in rules.judge(W, state, c)}
        assert theirs <= mine, (why, c["effects"])
    assert judged > 300


# —— 每条规则的正反例（自己写的） ——


def test_r1_anchor_beats_and_anchor_results() -> None:
    s = at()
    assert ("R1-anchor", "anchor-beat") in codes(s, cand(s, [{"op": "beat", "beat": "beat.02", "to": "prevented"}]))
    assert not codes(s, cand(s, [{"op": "beat", "beat": "beat.10", "to": "delayed", "minutes": 30}]))
    rain = start({**SQUARE, "checkpoint": "sc.canon@t=3700"})  # beat.12 大雨之后
    assert ("R1-anchor", "anchor-var") in codes(
        rain, cand(rain, [{"op": "set", "var": "var.weather", "value": "clear"}])
    )
    assert not codes(s, cand(s, [{"op": "set", "var": "var.weather", "value": "clear"}]))  # 雨还没下


def test_r2_beat_results_happened_and_value_requires() -> None:
    s = at()
    happened = codes(s, cand(s, [{"op": "beat", "beat": "beat.03", "to": "happened"}]))
    assert ("R2-precondition", "beat-happened") in happened
    later = start({**SQUARE, "checkpoint": "sc.canon@t=1300"})  # beat.03 已经发生
    has = codes(later, cand(later, [{"op": "beat", "beat": "beat.03", "to": "delayed", "minutes": 10}]))
    assert ("R2-precondition", "beat-has-result") in has
    king = cand(s, [{"op": "set", "var": "var.king.disposition", "value": "wavering"}])
    assert ("R2-precondition", "value-requires") in codes(s, king)
    trusted = at([{"op": "set", "var": "var.king.trust", "value": 45}])
    assert not codes(trusted, king)
    reason = rules.judge(W, s, king)[0].reason
    assert reason.startswith("王の心が揺れるのは")  # valueRequires 的 note（日语）原样


def test_r2_the_dead_stay_dead() -> None:
    dead = at(
        [
            {"op": "set", "var": "var.hostage.who", "value": "char.selinuntius"},
            {"op": "set", "var": "var.hostage.fate", "value": "executed"},
        ]
    )
    back = cand(dead, [{"op": "set", "var": "var.hostage.fate", "value": "spared"}])
    moved = cand(dead, [{"op": "relocate", "character": "char.selinuntius", "place": "place.syracuse-square"}], dt=600)
    assert ("R2-precondition", "no-resurrection") in codes(dead, back)
    assert ("R2-precondition", "no-resurrection") in codes(dead, moved)


def test_r3_clock_and_travel() -> None:
    s = at()
    assert ("R3-time", "time-backwards") in codes(s, cand(s, [], t=s["t"] - 5))
    far = cand(s, [{"op": "relocate", "character": OLD, "place": "place.village"}], dt=10)
    assert ("R3-time", "travel") in codes(s, far)
    assert not any(r == "R3-time" for r, _ in codes(s, {**far, "dt": 10_000}))
    # 同一场景里走动 0 分（S-038）
    assert not codes(
        s, cand(s, [{"op": "set", "var": "var.player.location", "value": "place.stonemason-workshop"}], dt=0)
    )


def test_r4_facts_knowledge_and_spoilers() -> None:
    s = at()
    promise = cand(s, [{"op": "learn", "character": OLD, "fact": "fact.promise"}])
    assert ("R4-knowledge", "fact-not-yet") in codes(s, promise)
    shepherd = cand(s, [{"op": "learn", "character": OLD, "fact": "fact.melos-shepherd"}])
    assert ("R4-knowledge", "actor-unaware") in codes(s, shepherd)  # 旅人不知道那个牧人是メロス
    assert not codes(s, cand(s, [{"op": "learn", "character": OLD, "fact": "fact.city-silent"}]))  # 旅人开局就知道

    def improv(text: str) -> Json:
        return cand(
            s, [{"op": "improv", "factId": "rf_01J00000000000000000000001", "character": OLD, "statement": text}]
        )

    assert ("R4-knowledge", "spoiler") in codes(s, improv("老爺は、友が身代わりになると話した"))
    assert not codes(s, improv("老爺は、きょう六人が殺されたと嘆いた"))  # 老爺は開局から知っている


def test_r6_patterns_verbatim_and_flags() -> None:
    s = at()
    base = cand(s, [{"op": "learn", "character": OLD, "fact": "fact.city-silent"}])
    pii = (
        "連絡先は090-1234-5678だと話した",
        "連絡先は０９０－１２３４－５６７８だと話した",
        "a@example.jp に書くと言った",
    )
    for text in (*pii, "〒のある紙を渡した", "3丁目に住んでいると話した"):
        assert ("R6-safety", "pii-pattern") in codes(s, {**base, "summary": text}), text
    said = "あの若者は村の牧人だと言っていました"
    copied = {**base, "summary": "旅人は、若者は村の牧人だと言っていましたと話した"}
    assert ("R6-safety", "verbatim") in codes(s, copied, Turn(said=said))
    assert not codes(s, {**base, "summary": "旅人は、村の若者の話をした"}, Turn(said=said))
    assert ("R6-safety", "flag-injection") in codes(s, base, Turn(flags=frozenset({"injection"})))
    assert not codes(s, cand(s, []), Turn(flags=frozenset({"injection"})))  # 只推进时钟的不看标记


def test_r7_access_hands_presence_and_values() -> None:
    s = at()
    castle = cand(s, [{"op": "set", "var": "var.player.location", "value": "place.castle"}], dt=60)
    assert ("R7-capability", "no-access") in codes(s, castle)
    taken = at(
        [
            {"op": "set", "var": "var.player.companionOf", "value": "char.melos"},
            {"op": "set", "var": "var.melos.custody", "value": "arrested"},
        ]
    )
    assert not any(r == "R7-capability" for r, _ in codes(taken, castle))  # conditionalAccess：跟着被抓的メロス
    lantern = cand(
        s, [{"op": "hold", "item": "item.lantern", "to": OLD, "from": "player"}], type="action", origin="action"
    )
    assert ("R7-capability", "not-holding") in codes(s, lantern)
    cloak = cand(s, [{"op": "hold", "item": "item.cloak", "to": OLD, "from": "player"}], type="action", origin="action")
    assert not codes(s, cloak)  # 旅人开局带着斗篷，老爺就在旁边
    away = cand(s, [{"op": "hold", "item": "item.cloak", "to": "char.groom", "from": "player"}])
    assert ("R7-capability", "target-away") in codes(s, away)
    told = cand(s, [{"op": "learn", "character": "char.groom", "fact": "fact.city-silent"}])
    assert ("R7-capability", "target-away") in codes(s, told)
    assert ("R7-capability", "bad-value") in codes(
        s, cand(s, [{"op": "set", "var": "var.melos.custody", "value": "flying"}])
    )
    assert ("R7-capability", "unknown-id") in codes(
        s, cand(s, [{"op": "relocate", "character": "char.nobody", "place": "place.village"}])
    )


def test_r7_situational_actions() -> None:
    s = at()
    home = cand(s, [{"op": "set", "var": "var.player.walkedOldManHome", "value": True}], type="action", origin="action")
    walk = Turn(act={"kind": "help", "target": OLD, "affordance": "aff.walk-old-man-home"})
    assert not codes(s, home, walk)
    done = at([{"op": "set", "var": "var.player.walkedOldManHome", "value": True}])
    assert ("R7-capability", "affordance-when") in codes(done, home, walk)
    workshop = at([{"op": "set", "var": "var.player.location", "value": "place.stonemason-workshop"}])
    assert ("R7-capability", "affordance-place") in codes(workshop, home, walk)
    water = Turn(act={"kind": "give", "target": "char.melos", "affordance": "aff.village-water"})
    got = codes(s, cand(s, []), water)
    assert {("R7-capability", "affordance-place"), ("R7-capability", "affordance-role")} <= got


def test_absent_characters_cannot_act_or_be_told() -> None:
    """S-077 ⑩ 的判法：开局 absent、还在 initialPlace 的人物不在场（完整版里第一幕广场上的群众和少女）。"""
    s = at()
    ix = rules.index(W)
    assert rules.absent(ix, s, "char.crowd") and rules.absent(ix, s, "char.maiden")
    assert activity(W, s, OLD) == "idle" and not rules.absent(ix, s, OLD)
    told = cand(s, [{"op": "learn", "character": "char.crowd", "fact": "fact.city-silent"}])
    assert ("R7-capability", "target-away") in codes(s, told)
    spoke = cand(s, [{"op": "improv", "factId": "rf_01J00000000000000000000002", "character": "char.maiden",
                      "statement": "少女は、この市の生まれだと言った"}], actor="char.maiden")  # fmt: skip
    assert ("R7-capability", "actor-away") in codes(s, spoke)
    ground = start({**SQUARE, "checkpoint": "sc.canon@t=5410", "place": "place.execution-ground"})  # beat.s1 之后
    assert not rules.absent(ix, ground, "char.maiden")  # beat.s1 把少女移到刑场
    assert not rules.absent(ix, ground, "char.crowd")  # 群众是 beat.s1 的参与人物，节拍发生时被移到刑场
    told_there = cand(ground, [{"op": "learn", "character": "char.crowd", "fact": "fact.city-silent"}])
    assert "R7-capability" not in {r for r, _ in codes(ground, told_there)}
    shown = {c["id"]: c for c in snapshot(BOOK, "pt_test", "role.traveler", "active", s, 0)["characters"]}
    assert (shown["char.crowd"]["activity"], shown["char.crowd"]["talkable"]) == ("absent", False)  # 快照照样列出
    assert shown[OLD]["activity"] == "idle"


def test_absent_characters_take_spots_last() -> None:
    """看得见的人先排位置点，不在场的排在最后（前端 #47）：不在场的人排在前面，也不挤掉看得见的人的点。"""
    s = at()
    chars = W["characters"]
    away = [c for c in chars if c["id"] in ("char.crowd", "char.maiden")]
    first = replace(BOOK, world={**W, "characters": away + [c for c in chars if c not in away]})
    shown = {c["id"]: c for c in snapshot(first, "pt_test", "role.traveler", "active", s, 0)["characters"]}
    sq = BOOK.scenes[BOOK.scene_of("place.syracuse-square", BOOK.act_of(s["vars"]))]
    seen = [(c["id"], c["place"]) for c in shown.values() if c["activity"] != "absent"]
    assert (OLD, "place.syracuse-square") in seen and len(seen) < len(shown)
    alone = sq.character_spots(seen, {sq.player_spot("place.syracuse-square")})
    assert {c: shown[c]["spot"] for c, _ in seen} == alone


def test_candidates_in_one_turn_see_the_ones_before() -> None:
    """同一轮的几个候选按顺序判：前面通过的先试算进状态。"""
    s = at()
    give = cand(s, [{"op": "hold", "item": "item.cloak", "to": OLD, "from": "player"}], type="action", origin="action")
    first, again = rules.check_candidates(W, s, [give, give], IdGen())
    assert first.check["status"] == "passed" and first.check["checker"] == rules.CHECKER
    assert again.check["status"] == "rejected" and again.check["failedRules"] == ["R7-capability"]
    assert again.check["reason"] == "外套は、プレイヤーの手もとにない" or again.check["reason"].endswith("手もとにない")
    rows = {r["rule"]: r["status"] for r in again.rules}
    assert rows["R7-capability"] == "fail" and rows["R1-anchor"] == "pass" and rows["R5-persona"] == "skipped"


def test_rejected_reasons_are_japanese_without_ids() -> None:
    """reason 是一句日语，用世界模型里的名字，不露 ID。"""
    s = at()
    for c in (
        cand(s, [{"op": "beat", "beat": "beat.02", "to": "prevented"}]),
        cand(s, [{"op": "relocate", "character": OLD, "place": "place.village"}]),
        cand(s, [{"op": "learn", "character": OLD, "fact": "fact.melos-shepherd"}]),
        cand(s, [{"op": "hold", "item": "item.lantern", "to": OLD, "from": "player"}]),
    ):
        for h in rules.judge(W, s, c):
            assert "." not in h.reason and "_" not in h.reason, h.reason


# —— 切片版（切片世界模型进 main 之前跳过） ——


@pytest.mark.skipif(not SLICE.is_file(), reason="切片世界模型还没进 main（数据 #38）")
def test_slice_player_cannot_be_arrested_and_the_workshop_pair_is_absent() -> None:
    lib = Library(REPO / "worlds", REPO / "assets" / "scenes", SLICE)
    book: Book = lib.current
    s = start(SQUARE, book)
    arrest = cand(s, [{"op": "set", "var": "var.player.custody", "value": "arrested"}])
    assert ("R7-capability", "bad-value") in codes(s, arrest, world=book.world)
    ix = rules.index(book.world)
    yard = start({**SQUARE, "place": "place.stonemason-workshop"}, book)
    for who in ("char.selinuntius", "char.philostratus"):
        assert rules.absent(ix, yard, who)
        talk = cand(yard, [{"op": "learn", "character": who, "fact": "fact.city-silent"}])
        assert ("R7-capability", "target-away") in codes(yard, talk, world=book.world)
    shown = {c["id"]: c for c in snapshot(book, "pt_test", "role.traveler", "active", yard, 0)["characters"]}
    for who in ("char.selinuntius", "char.philostratus"):
        assert (shown[who]["activity"], shown[who]["talkable"]) == ("absent", False)


@pytest.mark.skipif(not SLICE.is_file(), reason="切片世界模型还没进 main（数据 #38）")
def test_slice_snapshot_follows_the_standing_rules() -> None:
    """契约 3.1 的站位规则：relocate 指定的位置点照用（beat.s1：柱上的セリヌンティウス、王、少女），`group` 的人物
    不占位置点、没有 spot，其余的人自动分配时避开玩家和指定的点。"""
    book: Book = Library(REPO / "worlds", REPO / "assets" / "scenes", SLICE).current
    ground = start({**SQUARE, "checkpoint": "sc.canon@t=5410", "place": "place.execution-ground"}, book)
    named = ground.get("spots", {})
    assert named.get("char.selinuntius") and named.get("char.king") and named.get("char.maiden")
    snap = snapshot(book, "pt_test", "role.traveler", "active", ground, 0)
    shown = {c["id"]: c for c in snap["characters"]}
    for who in ("char.selinuntius", "char.king", "char.maiden"):  # 别处的人（村子里的妹）也有位置点，不在这个场景
        assert shown[who]["spot"] == named[who]
    for who in ("char.crowd", "char.guards"):
        assert shown[who]["group"] is True and "spot" not in shown[who]
    auto = [c for c in shown.values() if "spot" in c and c["id"] not in named]
    assert auto and all(c["spot"] not in {snap["player"]["spot"], *named.values()} for c in auto)
    for c in snap["characters"]:
        assert SCHEMAS.errors("api/common.schema.json", "#/$defs/CharacterPresence", c) == [], c
