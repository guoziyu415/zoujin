"""Unit tests for B-16 (world advancement and the director), no database: director rules D1-D5, candidate filtering,
merging with beats when writing, and step 3's world advancement scope.

B-16（世界の進行とディレクター）のユニットテスト。データベース不要：ディレクターの規則 D1〜D5、候補の絞り込み、
書き込み時のビートとの統合、第 3 ステップでの世界の進行の範囲。
"""

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
    """A game on the draft world model (the default) at this checkpoint; returns a Writer to keep writing with.

    草稿の世界モデル（既定）でこのチェックポイントにあるゲーム。続けて書ける Writer を返す。
    """
    book = LIBRARY.book("hashire-merosu")
    assert book is not None
    doc = {"role": "role.traveler", "checkpoint": checkpoint, **setup}
    w = Writer(book, "pt_test", initial_state(book.world, doc["role"]), key_base="k", turn_id=None, ids=IdGen(), now="")
    eval_api.play_setup(w, eval_api._scenarios(DEFAULT_WORLD.parent), doc)
    return Writer(book, "pt_test", w.state, key_base="k2", turn_id=None, ids=IdGen(), now="")


def player_event(w: Writer) -> Json:
    """Something the player did in the log (a cause for D5).

    ログにあるプレイヤーがしたこと 1 件（D5 の原因）。
    """
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
    """In dialogue an actor away from the player is R7 actor-away; in world advancement anyone not absent can act, and
    targets must be at the actor's place.

    対話では行為者がプレイヤーのそばにいなければ R7 actor-away。世界の進行では absent 以外は届き、対象は行為者と同じ
    場所にいる必要がある。
    """
    w = at("sc.canon@beat.02")
    st = w.state
    assert st["vars"]["var.player.location"] == PLAZA and st["locations"]["char.groom"] == "place.groom-house"
    c = cand(t=st["t"], dt=0, effects=[])
    assert [h.code for h in judge(w.book.world, st, c, [], Turn())] == ["actor-away"]
    assert judge(w.book.world, st, c, [], WORLD) == []
    # 老爺 is in the square, not at the groom's house / 老爺は広場にいて、花婿の家にはいない
    far = {"op": "learn", "character": "char.old-man", "fact": "fact.six-killed-today"}
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
    # The environment can only be the director / 環境はディレクターだけ
    assert advance.candidate({**ok, "actor": "system"}, book, st, set(), win) is None
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
    # Can't be traced to an action of the player or a character / プレイヤーか登場人物の行動にたどれない
    assert rule({**away, "causes": []}, move) == "D5"
    assert rule(away, move, taken={"present": 0, "absent": 3}) == "D4"
    assert rule(away, move, quota={"present": True, "absent": 0}) == "D4"
    # In front of the player: the environment (system) is fine; a character must walk in from elsewhere, not appear
    # in place; not when the quota is used up or a turn is queued (present false).
    # プレイヤーの目の前：環境（system）はよい。登場人物はよそから歩いてくる必要があり、その場に現れるのはだめ。
    # 枠を使い切った、またはターンが積まれている（present false）ときはだめ。
    bell = {**away, "actor": "system", "place": PLAZA}
    learn = [{"op": "learn", "character": "char.young-man", "fact": "fact.six-killed-today"}]
    assert rule(bell, learn) is None
    young = {**away, "actor": "char.young-man", "place": PLAZA}
    assert rule(young, learn) == "D3"
    assert rule(bell, learn, taken={"present": 1, "absent": 0}) == "D3"
    assert rule(bell, learn, quota={"present": False, "absent": 3}) == "D3"
    # At an act transition the player isn't present, so it uses the away quota.
    # 幕切り替えではプレイヤーはその場にいないので、その場にいない分の枠に数える。
    assert rule(bell, learn, away=True) is None
    # Character plans aren't written in front of the player / 登場人物のプランはプレイヤーの目の前では書かない
    assert rule({**young, "origin": "plan"}, learn) == "plan-in-sight"


def test_world_advance_never_makes_melos_late() -> None:
    """D1, D2: missing sunset after commit and later than before commit → dropped (character plans too); making him
    earlier is fine.

    D1、D2：コミット後に日没に間に合わず、しかもコミット前より遅い → 捨てる（登場人物のプランも同じ）。
    早めるのは構わない。
    """
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
    """Step 3 of an act transition: first settle to this item's time, then judge again against the state at that time;
    items past the target time and those failing before writing are dropped.

    幕切り替えの第 3 ステップ：まずこの件の時刻まで精算し、その時点の状態でもう一度判定する。目標時刻を過ぎたもの、
    書く前に通らなかったものは捨てる。
    """
    w = at("sc.canon@beat.07")
    t0 = int(w.state["t"])
    beat08 = int(w.book.beats["beat.08"]["window"]["canonical"])
    eff = [{"op": "relocate", "character": "char.groom", "place": "place.village"}]
    items = [
        advance.Item(cand(t=beat08 + 30, effects=eff), eff, PASSED),
        advance.Item(cand(t=beat08 + 3000, effects=eff), eff, PASSED),  # past the target time / 目標時刻を過ぎている
        # Judged at the moment of writing: before beat.08, "the wedding is tomorrow" isn't a fact yet (R4).
        # 書く時点で判定する：beat.08 より前は、婚礼が明日だということはまだ事実ではない（R4）。
        advance.Item(
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
