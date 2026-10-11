"""B-16（世界推进和导演）的单元测试，不要库：导演规则 D1〜D5、候选的筛选、写入时和节拍合并、第 3 步的世界推进口径。"""

from __future__ import annotations

from typing import Any

from zoujin_backend import eval_api
from zoujin_backend.config import DEFAULT_WORLD
from zoujin_backend.ids import IdGen
from zoujin_backend.narrator import advance
from zoujin_backend.narrator.rules import Turn, judge
from zoujin_backend.narrator.writer import Writer
from zoujin_worldsim import SimState, initial_state

from .conftest import LIBRARY

Json = Any

PLAZA = "place.syracuse-square"
WORLD = Turn(act=advance.WORLD_ACT)
PASSED = {"status": "passed", "attempts": 1, "failedRules": [], "checker": "test"}


def at(checkpoint: str, **setup: Any) -> Writer:
    """草稿世界模型（默认）在这个检查点的一局，返回能接着写的 Writer。"""
    book = LIBRARY.book("hashire-merosu")
    assert book is not None
    doc = {"role": "role.traveler", "checkpoint": checkpoint, **setup}
    w = Writer(book, "pt_test", initial_state(book.world, doc["role"]), key_base="k", turn_id=None, ids=IdGen(), now="")
    eval_api.play_setup(w, eval_api._scenarios(DEFAULT_WORLD.parent), doc)
    return Writer(book, "pt_test", w.state, key_base="k2", turn_id=None, ids=IdGen(), now="")


def player_event(w: Writer) -> Json:
    """日志里一件玩家做的事（D5 的原因）。"""
    return w.add(
        w.full(
            t=w.state["t"],
            dt=0,
            actor="player",
            type="say",
            origin="turn",
            place=w.player_place,
            summary="旅人が老爺と話した",
            effects=[],
            check=PASSED,
        )
    )


def cand(**kw: Any) -> Json:
    base = {"actor": "char.groom", "origin": "plan", "type": "action", "place": "place.groom-house", "causes": []}
    return {**base, "summary": "花婿は仕度を急がせた", **kw}


def test_world_mode_lets_characters_act_away_from_the_player() -> None:
    """对话里行为者不在玩家身边是 R7 actor-away；世界推进里不在场以外都碰得到，对象要和他同一个地点。"""
    w = at("sc.canon@beat.02")
    st = w.state
    assert st["vars"]["var.player.location"] == PLAZA and st["locations"]["char.groom"] == "place.groom-house"
    c = cand(t=st["t"], dt=0, effects=[])
    assert [h.code for h in judge(w.book.world, st, c, [], Turn())] == ["actor-away"]
    assert judge(w.book.world, st, c, [], WORLD) == []
    far = {"op": "learn", "character": "char.old-man", "fact": "fact.six-killed-today"}  # 老爺在广场，不在花婿家
    assert "target-away" in [h.code for h in judge(w.book.world, st, c, [far], WORLD)]


def test_candidates_outside_the_window_or_without_effects_are_dropped() -> None:
    w = at("sc.canon@beat.02")
    book, st = w.book, w.state
    win = advance.Window("act", int(st["t"]), int(st["t"]) + 600)
    eff = [{"op": "relocate", "character": "char.groom", "place": "place.village"}]
    ok = cand(t=st["t"] + 10, effects=eff)
    assert advance.candidate(ok, book, st, set(), win) is not None
    assert advance.candidate({**ok, "t": st["t"] + 601}, book, st, set(), win) is None
    assert advance.candidate({**ok, "effects": []}, book, st, set(), win) is None
    assert advance.candidate({**ok, "actor": "system"}, book, st, set(), win) is None  # 环境只能是导演
    assert advance.candidate({**ok, "actor": "system", "origin": "director"}, book, st, set(), win) is not None
    got = advance.candidate({**ok, "causes": ["ev_x", "beat.02", "ev_known"]}, book, st, {"ev_known"}, win)
    assert got is not None and got["causes"] == ["beat.02", "ev_known"]


def test_director_rules() -> None:
    w = at("sc.canon@beat.02")
    ev = player_event(w)
    book, st = w.book, w.state
    by_id = {ev["eventId"]: ev}
    q = {"present": True, "absent": 3}
    t = int(st["t"])
    away = cand(origin="director", t=t, causes=[ev["eventId"]])
    move = [{"op": "relocate", "character": "char.groom", "place": "place.groom-house"}]

    def rule(c: Json, effects: list[Json], quota: Json = q, taken: Any = None, **kw: Any) -> str | None:
        return advance.fairness(book, st, c, effects, by_id, quota, taken or {"present": 0, "absent": 0}, **kw)[0]

    assert rule(away, move) is None
    assert rule({**away, "causes": []}, move) == "D5"  # 追不到玩家或人物的举动
    assert rule(away, move, taken={"present": 0, "absent": 3}) == "D4"
    assert rule(away, move, quota={"present": True, "absent": 0}) == "D4"
    # 在玩家面前：环境（system）可以；人物要从别处走来，原地出现不行；名额用完、有排着的轮次（present false）不行
    bell = {**away, "actor": "system", "place": PLAZA}
    learn = [{"op": "learn", "character": "char.young-man", "fact": "fact.six-killed-today"}]
    assert rule(bell, learn) is None
    young = {**away, "actor": "char.young-man", "place": PLAZA}
    assert rule(young, learn) == "D3"
    assert rule(bell, learn, taken={"present": 1, "absent": 0}) == "D3"
    assert rule(bell, learn, quota={"present": False, "absent": 3}) == "D3"
    assert rule(bell, learn, away=True) is None  # 幕切换时玩家不在场，算不在场的名额
    # 人物的打算不在玩家面前写
    assert rule({**young, "origin": "plan"}, learn) == "plan-in-sight"


def test_world_advance_never_makes_melos_late() -> None:
    """D1、D2：提交后到不了日没、而且比提交前晚 → 丢（人物的打算也一样）；让他早到不管。"""
    w = at("sc.canon@beat.14")
    book, st = w.book, w.state
    deadline = int(book.world["clock"]["deadline"]["t"])
    before = advance.arrival(book, st)
    assert before is not None and before <= deadline
    late = [{"op": "beat", "beat": "beat.19", "to": "delayed", "minutes": deadline - before + 30}]
    early = [{"op": "beat", "beat": "beat.19", "to": "hastened", "minutes": 20}]
    c = cand(actor="char.bandits", place="place.mountain-pass", t=int(st["t"]))
    by_id: dict[str, Json] = {}
    q = {"present": False, "absent": 3}
    assert advance.fairness(book, st, c, late, by_id, q, {"present": 0, "absent": 0})[0] == "D1"
    assert advance.fairness(book, st, c, early, by_id, q, {"present": 0, "absent": 0})[0] is None


def test_write_merges_with_the_beats_and_rechecks() -> None:
    """幕切换的第 3 步：先结算到这一件的时刻，再按当时的状态重判；超过目标时刻的、写之前不过的丢掉。"""
    w = at("sc.canon@beat.07")
    t0 = int(w.state["t"])
    beat08 = int(w.book.beats["beat.08"]["window"]["canonical"])
    eff = [{"op": "relocate", "character": "char.groom", "place": "place.village"}]
    items = [
        advance.Item(cand(t=beat08 + 30, effects=eff), eff, PASSED),
        advance.Item(cand(t=beat08 + 3000, effects=eff), eff, PASSED),  # 超过目标时刻
        advance.Item(  # 按写的那一刻判：beat.08 之前，婚礼是明天这件事还不是事实（R4）
            cand(t=t0 + 5),
            [{"op": "learn", "character": "char.groom", "fact": "fact.wedding-tomorrow"}],
            PASSED,
        ),
    ]
    st: SimState = w.state
    assert st["beats"].get("beat.08") is None
    written = advance.write(w, items, until=beat08 + 600, away=True)
    assert [(e["actor"], e["t"], e["origin"], e["dt"]) for e in written] == [("char.groom", beat08 + 30, "plan", 0)]
    beats_before = [e for e in w.events if e["type"] == "beat" and e["t"] <= beat08 + 30]
    assert beats_before and w.events.index(beats_before[-1]) < w.events.index(written[0])
    assert w.state["locations"]["char.groom"] == "place.village"
    assert advance.counts(written) == (1, 0)
