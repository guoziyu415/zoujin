"""B-9（切片的简化结局）里不要数据库的部分：站位的状态表、受影响的排序、确定性校验、模板、API 的投影、提示的 Schema。
走到结局、生成、保存、评测入口在 `test_b9.py`，WebSocket 和 REST 在 `test_gateway_b9.py`。"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from zoujin_backend.config import REPO
from zoujin_backend.db.store import Run
from zoujin_backend.models.claude import api_schema, schema_problems
from zoujin_backend.models.prompts import PROMPTS
from zoujin_backend.models.text import DEFAULTS, _ending_broken
from zoujin_backend.narrator import ending as E
from zoujin_backend.world import Book, Library
from zoujin_worldsim import SimState, initial_state

from .conftest import SCHEMAS

Json = Any

SLICE = REPO / "worlds" / "hashire-merosu" / "1.0.0-slice" / "world.json"
BOOK: Book = Library(REPO / "worlds", REPO / "assets" / "scenes", SLICE).book("hashire-merosu")  # type: ignore[assignment]
GROUND = "place.execution-ground"
SQUARE = "place.syracuse-square"
FRIEND, MELOS, KING, OLD = "char.selinuntius", "char.melos", "char.king", "char.old-man"
EV = "ev_01M4N1PPDZMQ247G9ZNQXDS1"  # + 两位数 = 26 位 ULID


def state(**vars_: Any) -> SimState:
    """第四幕刑场上的一个状态：人质是セリヌンティウス、梅洛斯回来了、王改心了（大团圆），按参数改。"""
    st = initial_state(BOOK.world, "role.traveler")
    st = copy.deepcopy(st)
    st["vars"].update(
        {
            "var.act.current": "act.4",
            "var.player.location": GROUND,
            "var.hostage.who": FRIEND,
            "var.hostage.fate": "released",
            "var.melos.custody": "returned",
            "var.king.disposition": "reformed",
        }
    )
    st["vars"].update({k.replace("__", "."): v for k, v in vars_.items()})
    st["locations"].update({FRIEND: GROUND, MELOS: GROUND, KING: GROUND, OLD: GROUND})
    st["t"] = 5480
    return st


def states(stage: Json) -> dict[str, str]:
    return {x["id"]: x["state"] for x in stage["characters"]}


def ev(seq: int, **kw: Any) -> Json:
    base = {
        "eventId": f"{EV}{seq:02d}",
        "seq": seq,
        "t": 5000 + seq,
        "actor": "player",
        "type": "say",
        "origin": "turn",
        "summary": f"出来事{seq}",
        "effects": [],
        "check": {"status": "passed"},
    }
    return {**base, **kw}


# —— 站位（验收第 2 条）——


def test_staging_canon() -> None:
    got = E.staging(BOOK, state(), Run(player_spot="stake-front"))
    assert got["place"] == GROUND
    assert states(got) | {} == {
        FRIEND: "freed",
        MELOS: "arriving",
        KING: "approaching",
        OLD: "in-crowd",
        "player": "in-crowd",
    } | {k: v for k, v in states(got).items() if k not in (FRIEND, MELOS, KING, OLD, "player")}
    assert got["characters"][0]["id"] == FRIEND and got["characters"][-1]["id"] == "player"


@pytest.mark.parametrize(
    ("change", "who", "want"),
    [
        ({"var__hostage__fate": "executed"}, FRIEND, "on-cross"),
        ({"var__melos__custody": "on-parole"}, MELOS, "collapsed"),
        ({"var__king__disposition": "tyrant"}, KING, "present"),
    ],
)
def test_staging_rows(change: dict[str, str], who: str, want: str) -> None:
    assert states(E.staging(BOOK, state(**change), None))[who] == want


def test_staging_absent_and_player_spots() -> None:
    st = state()
    st["locations"][MELOS] = "place.road-to-city"
    assert states(E.staging(BOOK, st, None))[MELOS] == "absent"
    assert states(E.staging(BOOK, state(), Run(player_spot="stake-front")))["player"] == "in-crowd"
    assert states(E.staging(BOOK, state(), Run(player_spot="ground-west")))["player"] == "present"
    away = state(var__player__location=SQUARE)
    assert states(E.staging(BOOK, away, None))["player"] == "absent"


def test_staging_player_hostage_and_friend_not_hostage() -> None:
    st = state(var__hostage__who="player", var__hostage__fate="executed")
    got = states(E.staging(BOOK, st, None))
    assert got["player"] == "on-cross" and E.staging(BOOK, st, None)["characters"][0]["id"] == "player"
    st = state(var__hostage__who="player", var__hostage__fate="released")
    assert states(E.staging(BOOK, st, None))["player"] == "freed"
    # セリヌンティウス不是人质：同一场景 in-crowd，别的场景 absent
    st = state(var__hostage__who="player")
    assert states(E.staging(BOOK, st, None))[FRIEND] == "in-crowd"
    st["locations"][FRIEND] = "place.melos-home"
    assert states(E.staging(BOOK, st, None))[FRIEND] == "absent"


# —— 触发 ——


def test_due_only_in_the_last_act() -> None:
    st = state()
    st["beats"] = {}
    st["deadline"] = False
    assert E.due(BOOK, st) is None
    st["beats"]["beat.24"] = "happened"
    assert E.due(BOOK, st) == "story-closed"
    st["beats"]["beat.24"] = "prevented"
    assert E.due(BOOK, st) == "deadline"
    act3 = state(var__act__current="act.3")
    act3["beats"]["beat.24"] = "happened"
    assert E.due(BOOK, act3) is None
    # 评测 setup：最后一幕的 end（beat.27 有结果，或到了 atLatest）满足了才算收幕，不看玩家在哪一幕
    assert not E.curtain_fell(BOOK, act3)
    act3["beats"]["beat.27"] = "happened"
    assert E.curtain_fell(BOOK, act3)


# —— 排序（验收第 3 条）——


def test_rank_scores_ties_and_unchanged() -> None:
    st = state()
    events = [
        ev(1, actor="player", beneficiary=OLD),
        ev(2, actor="player", effects=[{"op": "hold", "item": "item.x", "from": "player", "to": KING}]),
        ev(3, actor=OLD, origin="plan", effects=[{"op": "learn", "character": KING, "fact": "fact.promise"}]),
        ev(4, actor="system", origin="schedule", effects=[{"op": "learn", "character": OLD, "fact": "fact.x"}]),
        ev(5, origin="action", actor="system", effects=[{"op": "relocate", "character": OLD, "place": GROUND}]),
    ]
    got = E.rank(BOOK, st, events, [])
    assert (got[OLD]["rank"], got[OLD]["score"]) == (1, 2)  # 1（beneficiary）+ 5（relocate，origin action）
    assert (got[KING]["rank"], got[KING]["score"]) == (2, 1)  # hold 的 to；3 是 origin plan，不算
    assert got[MELOS] == {"character": MELOS, "rank": None, "unchanged": True, "score": 0}
    # hold 的 from 也算和他有关：玩家从王手里拿走东西
    took = [ev(1, actor="player", effects=[{"op": "hold", "item": "item.x", "from": KING, "to": "player"}])]
    assert E.rank(BOOK, st, took, [])[KING]["score"] == 1
    # 同分按 endings.characters 的顺序：梅洛斯在老爺前面
    tie = E.rank(BOOK, st, [ev(1, beneficiary=OLD), ev(2, beneficiary=MELOS)], [])
    assert (tie[MELOS]["rank"], tie[OLD]["rank"]) == (1, 2)
    # changedBeats 的参与者
    changed = [{"beat": "beat.24", "to": "prevented", "causedBy": []}]
    assert E.rank(BOOK, st, [], changed)[MELOS]["rank"] == 1


def test_all_unchanged_card_line_is_melos_original() -> None:
    ctx = make_ctx([ev(1, actor="system", origin="schedule")])
    assert all(r["unchanged"] for r in ctx.ranks.values())
    out = good(ctx)
    assert E.card_lines(ctx, out) == [{"character": MELOS, "line": E.original(BOOK, MELOS)}]


# —— 校验（验收第 5 条）——


def make_ctx(events: list[Json], st: SimState | None = None, said: list[str] | None = None) -> E.Ctx:
    st = st or state()
    stage = E.staging(BOOK, st, None)
    request = {"trigger": "story-closed", "outcome": E.outcome_of(BOOK, st)[0], "staging": stage}
    return E.make_ctx(BOOK, st, "pt_01M4N1PP6EZBXRBP89RJ8GSR8S", "role.traveler", request, events, said or [])


def good(ctx: E.Ctx) -> Json:
    """假模型按这一局的请求写的（换回真 ID）：能过校验。"""
    to_alias, back = E.alias_map(ctx.events)
    return E.unalias(DEFAULTS["ending"](E.request_of(ctx)), back)


def rules(ctx: E.Ctx, out: Json) -> set[tuple[str, str]]:
    return {(p.rule, p.field) for p in E.validate(ctx, out)}


EVENTS = [ev(1, beneficiary=OLD, summary="旅人が老爺を家まで送った"), ev(2, summary="旅人が刑場へ移った")]


def test_fake_output_passes() -> None:
    ctx = make_ctx(EVENTS)
    out = good(ctx)
    assert E.validate(ctx, out) == []
    ending = E.assemble(ctx, E.from_model(ctx, out), "end_01M4N1PPGW66RMBPQ6RB0MCSPN", 5480)
    SCHEMAS.ending(ending)
    SCHEMAS.response("ending", 200, E.view(ending))


def test_each_rule_has_a_bad_example() -> None:
    ctx = make_ctx(EVENTS, said=["メロスの代わりに私が柱に立ちます、と言ってみた"])
    base = good(ctx)

    def bad(change: Any) -> set[tuple[str, str]]:
        out = copy.deepcopy(base)
        change(out)
        return rules(ctx, out)

    assert ("cite-empty", "epilogue[0]") in bad(lambda o: o["epilogue"][0].update(cites=[]))
    assert ("cite-unknown", "you.title") in bad(
        lambda o: o["you"]["title"].update(cites=["ev_01M4N1PPDZMQ247G9ZNQXDS199"])
    )
    assert ("count", "epilogue") in bad(lambda o: o.update(epilogue=o["epilogue"][:2]))
    assert ("count", "you.didForYou") in bad(lambda o: o["you"].update(didForYou=o["epilogue"][:3]))
    assert ("characters", "characters") in bad(lambda o: o.update(characters=[]))
    assert ("length", "you.title") in bad(lambda o: o["you"]["title"].update(text="あ" * 15))
    assert ("length", "subtitle") in bad(lambda o: o.update(subtitle="あ" * 27))
    assert ("length", "cardContrast") in bad(lambda o: o.update(cardContrast="あ" * 49))
    assert ("contrast-beat", "contrast.beat") in bad(lambda o: o["contrast"].update(beat="beat.24"))
    copied = "私が柱に立ちます"  # 原话里连续 8 字
    assert ("verbatim", "epilogue[1]") in bad(
        lambda o: o["epilogue"][1].update(sentence=f"あなたは「{copied}」と告げた。")
    )
    assert ("pii", "epilogue[2]") in bad(lambda o: o["epilogue"][2].update(sentence="連絡先は090-1234-5678だった。"))
    # 只有专有名词一样的不算照抄
    assert not {
        r
        for r in bad(lambda o: o["epilogue"][1].update(sentence="メロスの代わりに、市の人が見ていた。"))
        if r[0] == "verbatim"
    }


def test_s067_words_only_when_someone_was_executed() -> None:
    late = state(var__hostage__fate="executed", var__melos__custody="on-parole", var__king__disposition="tyrant")
    ctx = make_ctx(EVENTS, late)
    assert ctx.outcome == "too-late" and E.executed(late)
    base = good(ctx)
    assert E.validate(ctx, base) == []
    for word in ("友は死んだ。", "友は息絶えた。", "友は磔にされた。"):
        out = copy.deepcopy(base)
        out["epilogue"][0]["sentence"] = word
        assert ("s067", "epilogue[0]") in rules(ctx, out)
    out = copy.deepcopy(base)
    out["epilogue"][0]["sentence"] = "磔の柱が、夕日に長い影を落としていた。"
    assert E.validate(ctx, out) == []
    happy = make_ctx(EVENTS)
    out = good(happy)
    out["epilogue"][0]["sentence"] = "死をも恐れず、メロスは走った。"
    assert not [p for p in E.validate(happy, out) if p.rule == "s067"]


def test_request_has_aliases_and_no_utterances() -> None:
    ctx = make_ctx(EVENTS, said=["原話はここにある"])
    req = E.request_of(ctx)
    assert [e["eventId"] for e in req["events"]] == ["e1", "e2"]
    assert "原話" not in str(req) and "forbidden" not in req
    broken = _ending_broken(req)
    _, back = E.alias_map(ctx.events)
    assert ("cite-empty", "epilogue[0]") in rules(ctx, E.unalias(broken, back))


# —— 模板（验收第 6 条）——


@pytest.mark.parametrize(
    ("change", "outcome", "subtitle"),
    [
        ({}, "canon-reunion", "メロスは間に合い、王は仲間に入れてくれと言った。"),
        (
            {"var__king__disposition": "tyrant"},
            "in-time-king-unchanged",
            "メロスは間に合ったが、王の心は変わらなかった。",
        ),
        (
            {"var__melos__custody": "on-parole", "var__hostage__fate": "released"},
            "king-changed-first",
            "王の心は、日没より先に変わった。",
        ),
        (
            {"var__melos__custody": "on-parole", "var__king__disposition": "tyrant", "var__hostage__fate": "executed"},
            "too-late",
            "日は沈んだ。メロスは、間に合わなかった。",
        ),
        (
            {"var__hostage__who": "player", "var__player__custody": "executed", "var__melos__custody": "on-parole"},
            "player-substituted",
            "日は沈んだ。メロスは、間に合わなかった。",
        ),
        ({"var__hostage__who": "player"}, "player-substituted", "メロスは間に合い、あなたの縄はほどかれた。"),
        (
            {"var__hostage__who": "player", "var__melos__custody": "on-parole"},
            "player-substituted",
            "王の心が先に変わり、あなたの縄はほどかれた。",
        ),
    ],
)
def test_templates(change: dict[str, str], outcome: str, subtitle: str) -> None:
    st = state(**change)
    ctx = make_ctx(EVENTS, st)
    assert ctx.outcome == outcome
    body = E.from_template(ctx)
    card = body["card"]
    assert card["subtitle"] == subtitle and body["player"]["epilogue"][0]["sentence"] == subtitle
    assert "{role}" not in card["title"] and card["title"].endswith("旅人") and len(card["title"]) <= E.TITLE_MAX
    assert all(len(x["line"]) <= E.CARD_LINE_MAX for x in card["characterLines"])
    assert len(card["contrast"]) <= E.CARD_CONTRAST_MAX
    t = E.template_of(BOOK, st, outcome)
    fate = body["player"]["fate"]["label"]
    assert fate == (t.get("fate") or BOOK.world["endings"]["fates"]["witness"])
    written = [x["character"] for x in t["lines"]]
    for c in body["characters"]:
        assert c["unchanged"] == (c["character"] not in written)
        if not c["unchanged"]:
            assert c["rank"] == written.index(c["character"]) + 1
    ending = E.assemble(ctx, body, "end_01M4N1PPGW66RMBPQ6RB0MCSPN", 5480)
    SCHEMAS.ending(ending)
    assert "contrast" not in ending["world"]


def test_template_fate_elsewhere() -> None:
    ctx = make_ctx(EVENTS, state(var__player__location=SQUARE))
    assert E.from_template(ctx)["player"]["fate"] == {
        "id": "elsewhere",
        "label": "刑場には行かず、日没を迎えた。",
        "causedBy": E.deciders(BOOK, ctx.state, ctx.outcome, ctx.events),
    }


# —— 投影和 Schema ——


def test_view_drops_internal_fields() -> None:
    ctx = make_ctx(EVENTS)
    ending = E.assemble(ctx, E.from_model(ctx, good(ctx)), "end_01M4N1PPGW66RMBPQ6RB0MCSPN", 5480)
    got = E.view(ending)
    text = str(got)
    for key in ("signature", "finalVars", "changedBeats", "causedBy"):
        assert key not in text
    assert got["card"]["fallbackImageUrl"] == "/endings/canon-reunion.webp"
    assert [c["character"] for c in got["characters"]] == BOOK.world["endings"]["characters"]


def test_eta() -> None:
    assert (E.eta(0, 0), E.eta(0, 5.5), E.eta(0, 12), E.eta(0, 90)) == (15, 10, 5, 5)


def test_prompt_schema_fits_the_claude_limits() -> None:
    assert PROMPTS["ending"].schema
    assert schema_problems(api_schema("ending")) == []
