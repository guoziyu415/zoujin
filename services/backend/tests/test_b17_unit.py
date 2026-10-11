"""B-17（三层结局完整版）里不要数据库的部分：加权排序、关系、生成的世界结局和人物结局的主张、删过记忆的人物、
作废约定的引用、模型检查的请求。走到结局和模型检查的重写在 `test_b9.py`（test_b17_*）。"""

from __future__ import annotations

import copy
from typing import Any

from zoujin_backend.models.claude import api_schema, schema_problems
from zoujin_backend.narrator import ending as E

from .conftest import SCHEMAS
from .test_b9_unit import BOOK, EVENTS, KING, MELOS, OLD, ev, good, make_ctx, rules, state

Json = Any
MEM = "mem_01M4N1PPDZMQ247G9ZNQXDS1"


def mem(n: int, who: str, delta: int = 5, deleted: bool = False, events: list[str] | None = None) -> Json:
    row: Json = {
        "memoryId": f"{MEM}{n:02d}",
        "character": who,
        "kind": "kindness",
        "text": "旅の人が家まで送ってくれた" if not deleted else "",
        "fromEvents": events or [],
        "trustDelta": delta,
    }
    if deleted:
        row["deletedAt"] = "2026-10-11T00:00:00.000Z"
    return row


def ctx_with(memories: list[Json], st: Any = None, events: list[Json] | None = None) -> E.Ctx:
    c = make_ctx(events or EVENTS, st)
    st = c.state
    request = {"trigger": c.trigger, "outcome": c.outcome, "staging": c.stage}
    return E.make_ctx(BOOK, st, c.pid, "role.traveler", request, events or EVENTS, [], memories)


def test_rank_weights_memories_promises_and_aid() -> None:
    st = state()
    st["promises"]["sp_1"] = {"promiseId": "sp_1", "from": "player", "to": KING, "text": "x", "status": "open"}
    st["promises"]["sp_2"] = {"promiseId": "sp_2", "from": MELOS, "to": "player", "text": "y", "status": "voided"}
    events = [ev(1, actor=MELOS, origin="plan", beneficiary="player")]  # 梅洛斯为玩家做的：互助 1
    got = E.rank(BOOK, st, events, [], [mem(1, OLD)], {OLD: 25})
    assert got[KING]["score"] == E.W_PROMISE  # 约定 2；作废的不算
    assert got[MELOS]["score"] == E.W_AID
    assert got[OLD]["score"] == E.W_MEMORY + 2  # 记忆 1 + 信任 25 → 2
    assert [got[c]["rank"] for c in (OLD, KING, MELOS)] == [1, 2, 3]


def test_relationships_come_from_kept_memories() -> None:
    ctx = ctx_with([mem(1, OLD, 30), mem(2, OLD, -5, deleted=True), mem(3, KING, 0)])
    rel = {r["character"]: r for r in E.relationships(ctx)}
    assert rel[OLD]["trust"] == 30 and rel[OLD]["label"] == "気を許している"
    assert rel[OLD]["memoryIds"] == [f"{MEM}01"]  # 删了的不算
    assert rel[KING]["memoryIds"] == [f"{MEM}03"]
    assert ctx.forgot == {OLD}
    out = good(ctx)
    assert E.validate(ctx, out) == []
    ending = E.assemble(ctx, E.from_model(ctx, out), "end_01M4N1PPGW66RMBPQ6RB0MCSPN", 5480)
    SCHEMAS.ending(ending)
    assert ending["player"]["relationships"] == E.relationships(ctx)
    req = E.request_of(ctx)
    assert [m["text"] for m in req["memories"]] == ["旅の人が家まで送ってくれた", "旅の人が家まで送ってくれた"]
    assert {c["character"]: c["forgotYou"] for c in req["characters"]}[OLD] is True


def variant(ctx: E.Ctx, **kw: Any) -> Json:
    ids = [e["eventId"] for e in ctx.events]
    v = {
        "id": "gen.king-joins",
        "title": "王は輪に加わった",
        "summary": "王はふたりの輪に加わった。",
        "claims": [{"var": "var.king.disposition", "value": "reformed"}],
        "cites": ids[:2],
    }
    return {**v, **kw}


def test_variant_rules() -> None:
    ctx = make_ctx(EVENTS)
    base = good(ctx)
    ok = copy.deepcopy(base)
    ok["variant"] = variant(ctx)
    assert E.validate(ctx, ok) == []
    body = E.from_model(ctx, ok)
    assert body["world"]["variant"]["causedBy"] == [e["eventId"] for e in EVENTS]
    ending = E.assemble(ctx, body, "end_01M4N1PPGW66RMBPQ6RB0MCSPN", 5480)
    SCHEMAS.ending(ending)
    view = E.view(ending)
    assert (view["world"]["outcomeId"], view["world"]["baseline"]) == ("gen.king-joins", False)
    SCHEMAS.response("ending", 200, view)

    def bad(**kw: Any) -> set[tuple[str, str]]:
        out = copy.deepcopy(base)
        out["variant"] = variant(ctx, **kw)
        return rules(ctx, out)

    assert ("variant-id", "variant.id") in bad(id="King Joins")
    assert ("variant-claim", "variant.claims") in bad(claims=[{"var": "var.king.disposition", "value": "tyrant"}])
    assert ("variant-claim", "variant.claims") in bad(claims=[])
    assert ("variant-claim", "variant.claims") in bad(claims=[{"var": "var.nope", "value": 1}])
    assert ("variant-cites", "variant.cites") in bad(cites=[EVENTS[0]["eventId"]])
    assert ("length", "variant.title") in bad(title="あ" * 27)


def test_character_claims_must_hold() -> None:
    ctx = make_ctx(EVENTS)
    out = good(ctx)
    out["characters"][0]["claims"] = [{"var": "var.hostage.fate", "value": "executed"}]
    who = out["characters"][0]["character"]
    assert ("character-claim", f"characters.{who}") in rules(ctx, out)
    out["characters"][0]["claims"] = [{"var": "var.hostage.fate", "value": "released"}]
    assert E.validate(ctx, out) == []


def test_forgotten_character_is_not_written_as_remembering() -> None:
    ctx = ctx_with([mem(1, OLD, deleted=True)])
    out = good(ctx)
    assert E.validate(ctx, out) == []
    row = next(c for c in out["characters"] if c["character"] == OLD)
    row["yours"][0]["sentence"] = "老爺は、あなたのことを覚えていた。"
    assert ("forgot", f"characters.{OLD}[0]") in rules(ctx, out)
    out = good(ctx)
    out["epilogue"][0]["sentence"] = f"{BOOK.characters[OLD]['name']}は旅人を思い出していた。"
    assert ("forgot", "epilogue[0]") in rules(ctx, out)
    # 没删过记忆的人物可以记得
    ctx2 = ctx_with([])
    out = good(ctx2)
    out["epilogue"][0]["sentence"] = "老爺は旅人を覚えていた。"
    assert not [p for p in E.validate(ctx2, out) if p.rule == "forgot"]


def test_cites_cannot_rest_only_on_a_voided_promise() -> None:
    st = state()
    made = EVENTS[1]["eventId"]
    st["promises"]["sp_1"] = {"promiseId": "sp_1", "from": "player", "to": OLD, "text": "x", "status": "voided"}
    st["promises"]["sp_1"]["madeBy"] = made
    ctx = make_ctx(EVENTS, st)
    out = good(ctx)
    out["epilogue"][0]["cites"] = [made]
    assert ("cite-voided", "epilogue[0]") in rules(ctx, out)
    out["epilogue"][0]["cites"] = [made, EVENTS[0]["eventId"]]
    assert ("cite-voided", "epilogue[0]") not in rules(ctx, out)
    assert E.request_of(ctx)["promises"] == []  # 作废的约定不进请求


def test_check_request_uses_aliases_and_no_utterances() -> None:
    ctx = make_ctx(EVENTS, said=["原話はここにある"])
    req = E.check_request(ctx, good(ctx))
    text = str(req)
    assert "ev_" not in text and "原話" not in text and req["events"][0]["eventId"] == "e1"
    assert req["ending"]["variant"] is None


def test_prompt_schemas_fit_the_claude_limits() -> None:
    for kind in (E.KIND, E.CHECK_KIND):
        assert schema_problems(api_schema(kind)) == []
