"""B-13 记忆和記憶帳删除（验收第 1〜3、6、9、10 组的叙事者和评测入口部分；REST 和 WebSocket 在 test_gateway_b13）。

假模型（`memory` 默认把事件摘要截短当一句）、假 Model Armor，真 PostgreSQL。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest
from sqlalchemy import select
from zoujin_backend import eval_api
from zoujin_backend.db import store
from zoujin_backend.db.tables import playthrough_metrics, turns
from zoujin_backend.gateway import brief
from zoujin_backend.ids import IdGen
from zoujin_backend.models.armor import FakeArmor
from zoujin_backend.models.text import FakeText
from zoujin_backend.narrator import memory
from zoujin_backend.trace import Tracer
from zoujin_worldsim import initial_state

from .conftest import BOOK, OLD, SCHEMAS, Env

pytestmark = pytest.mark.db

Json = Any

MINIMAL = {"role": "role.traveler", "checkpoint": "sc.canon@t=1080", "place": "place.syracuse-square"}
OFFER = "お家まで送りましょう。"
SUMMARY = "旅人は市の老爺を家まで送ると申し出た"
REMEMBERED = "あの人は市の老爺を家まで送ると申し出た"  # 假模型：身份名换成「あの人」
PROMISE = {
    "candidates": [
        {
            "actor": "player",
            "type": "say",
            "origin": "turn",
            "summary": SUMMARY,
            "causes": [],
            "effects": [{"op": "promise", "change": "made", "from": "player", "to": OLD, "text": "家まで送る"}],
            "needsConfirm": False,
        }
    ]
}
EXTRACT = {"kind": "extract", "when": {"playerContains": "送り"}, "output": PROMISE}
MEMORY_ITEM = ("data/memory.schema.json", "#/$defs/MemoryItem")
STATEMENT = "旅人は旅の薬師だという"


def session(env: Env, monkeypatch: pytest.MonkeyPatch, *rules: Json, armor: list[Json] | None = None) -> Any:
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    s = eval_api.setup(MINIMAL, mode="text")
    s.text = FakeText(env.settings.fake_text, rules=[EXTRACT, *rules])
    if armor is not None:
        s.armor = FakeArmor(rules=armor)
    return s


def metrics(env: Env, pid: str) -> Json:
    async def get() -> Json:
        engine = env.engine()
        try:
            async with engine.connect() as c:
                q = select(playthrough_metrics).where(playthrough_metrics.c.playthrough_id == pid)
                return dict((await c.execute(q)).mappings().one())
        finally:
            await engine.dispose()

    return asyncio.run(get())


def result_of(env: Env, turn_id: str) -> Json:
    async def get() -> Json:
        engine = env.engine()
        try:
            async with engine.connect() as c:
                return await c.scalar(select(turns.c.result).where(turns.c.turn_id == turn_id))
        finally:
            await engine.dispose()

    return asyncio.run(get())


# —— 第 1 组：一轮立了约定 ——


def test_a_promise_turn_writes_a_memory_for_the_other_party(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    s = session(env, monkeypatch)
    step = s.say(OLD, OFFER)
    made = next(e for e in step["events"] if e["effects"])
    (m,) = s.memories(OLD)
    assert SCHEMAS.errors(*MEMORY_ITEM, m) == []
    assert m["kind"] == "promise" and m["via"] == "witnessed" and m["fromEvents"][0] == made["eventId"]
    assert set(m["fromEvents"]) == {e["eventId"] for e in step["events"]}  # 这一轮的事件合成一条
    assert m["promiseId"] == made["effects"][0]["promiseId"] and m["text"] == REMEMBERED
    assert s.trust(OLD) == memory.PROMISE_MADE[1]
    assert metrics(env, s.pid)["memories_written"] == 1
    (change,) = result_of(env, step["traceId"])["memories"]
    assert change == {
        "character": OLD,
        "change": "added",
        "memoryId": m["memoryId"],
        "kind": "promise",
        "relationLabel": "様子を見ている",
        "relationLevel": 3,
    }
    # 写记忆的请求只有事件的摘要和结果、人设摘要、via，没有原话
    kinds = [k for k, _ in s.text.calls]
    (req,) = [r for k, r in s.text.calls if k == "memory"]
    assert kinds.index("memory") > kinds.index("check")
    assert req["events"][0]["summary"] == SUMMARY and req["via"] == "witnessed" and OFFER not in str(req)


def test_small_talk_leaves_an_impression_on_the_one_spoken_to(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """闲聊（只推时钟的 say，effects 空）也写一条：只给说话的对象，是 impression、0 分（数据评审，E6-002、E6-004）。"""
    s = session(env, monkeypatch)
    step = s.say(OLD, "こんにちは。")
    (m,) = s.memories(OLD)
    assert m["kind"] == "impression" and m["trustDelta"] == 0 and m["salience"] == memory.IMPRESSION[2]
    assert m["fromEvents"] == [e["eventId"] for e in step["events"]]
    assert s.memories("char.melos") == [] and s.trust(OLD) == 0


def test_a_rejected_turn_writes_nothing(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """被否决的候选：不写记忆，也不调写记忆的模型（E6-009）。"""
    s = session(env, monkeypatch, {"kind": "check", "fail": {"rule": "R5-persona"}})
    step = s.say(OLD, OFFER)  # 检查一直不过：改写、降级都做不到，拒绝
    assert not any(e["effects"] for e in step["events"] if e["check"]["status"] != "rejected")
    assert [m["kind"] for m in s.memories(OLD)] in ([], ["impression"])
    assert all(m["kind"] != "promise" for m in s.memories(OLD))


# —— 第 2 组：三道过滤、模型出错 ——


@pytest.mark.parametrize(
    "text",
    [
        "電話は090-1234-5678だと言った人",
        "あの人は「黙って歩け」と言った",
        "家まで送ると言ってくれた旅の人" * 3,
        "家まで送ると言ってくれた旅人",
    ],
    ids=["pii", "command", "too-long", "role-name"],
)
def test_filtered_memories_are_not_written(env: Env, monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    s = session(env, monkeypatch, {"kind": "memory", "output": {"text": text, "weight": 1}})
    step = s.say(OLD, OFFER)
    assert s.memories(OLD) == [] and any(e["effects"] for e in step["events"])  # 事件照留
    m = metrics(env, s.pid)
    assert (m["memories_filtered"], m["memories_written"]) == (1, 0)
    assert "memories" not in result_of(env, step["traceId"])


def test_model_armor_hit_filters_the_memory(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    hit = {"method": "response", "contains": "老爺", "result": {"sdp": ["PERSON_NAME"]}}
    s = session(env, monkeypatch, armor=[hit])
    s.say(OLD, OFFER)
    assert s.memories(OLD) == [] and metrics(env, s.pid)["memories_filtered"] == 1


def test_model_armor_error_counts_as_no_hit(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    s = session(env, monkeypatch, armor=[{"method": "response", "error": "unavailable"}])
    s.say(OLD, OFFER)
    m = metrics(env, s.pid)
    assert len(s.memories(OLD)) == 1 and m["armor_errors"] == 1


def test_model_error_skips_the_memory_but_not_the_turn(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    s = session(env, monkeypatch, {"kind": "memory", "error": "unavailable"})
    step = s.say(OLD, OFFER)
    assert s.memories(OLD) == [] and step["events"]
    m = metrics(env, s.pid)
    assert (m["memories_failed"], m["memories_written"]) == (1, 0)
    assert [k for k, _ in s.text.calls].count("memory") == 1  # 不重发


def test_a_slow_memory_call_times_out_without_a_retry() -> None:
    text = FakeText(rules=[{"kind": "memory", "latencyMs": 200}])
    m = memory.Memorizer(text, None, IdGen(), Tracer(), deadline=0.01)
    ev = {
        "eventId": "ev_1",
        "t": 1080,
        "summary": SUMMARY,
        "effects": [],
        "actor": "player",
        "type": "say",
        "place": "place.syracuse-square",
        "check": {"status": "passed"},
    }
    seed = memory.Seed(OLD, "help", (ev,), 10, 0.7, "witnessed")
    got = asyncio.run(m.write(BOOK, "pt_1", "role.traveler", [seed]))
    assert got.rows == [] and got.failed == 1 and len(text.calls) == 1


def test_memory_text_and_utterances_stay_out_of_logs_and_spans(
    env: Env, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    s = session(env, monkeypatch)
    s.say(OLD, OFFER)
    s.delete_memory(OLD, 1)
    logged = caplog.text + str([x.attrs for x in s.tracer.spans])
    assert SUMMARY not in logged and OFFER not in logged
    assert s.tracer.named("narrator.memory")


# —— 第 3 组：关系 ——


@pytest.mark.parametrize(
    ("trust", "level"),
    [(-100, 1), (-40, 1), (-39, 2), (-10, 2), (-9, 3), (0, 3), (9, 3), (10, 4), (39, 4), (40, 5), (100, 5)],
)
def test_relation_bands(trust: int, level: int) -> None:
    label, got = memory.relation(trust)
    assert got == level and label == memory.LEVELS[level - 1][2]


def test_trust_starts_from_known_characters_and_is_clamped() -> None:
    known = BOOK.roles["role.apprentice"]["knownCharacters"][0]
    assert memory.initial_trust(BOOK, "role.apprentice", known) == memory.KNOWN_TRUST
    assert memory.initial_trust(BOOK, "role.traveler", "char.melos") == 0
    assert memory.clamp(130) == 100 and memory.clamp(-130) == -100


# —— 对照表 ——


T0 = initial_state(BOOK.world, "role.traveler")["t"]


def _ev(**kw: Any) -> Json:
    base = {
        "eventId": "ev_x",
        "t": T0,
        "dt": 0,
        "summary": "…",
        "effects": [],
        "actor": "player",
        "type": "action",
        "place": "place.syracuse-square",
        "check": {"status": "passed"},
    }
    return {**base, **kw}


def _state(**locations: str) -> Json:
    st = initial_state(BOOK.world, "role.traveler")
    vars_ = {**st["vars"], "var.player.location": "place.syracuse-square"}
    return {**st, "vars": vars_, "locations": locations, "promises": {}}


def _seeds(st: Json, *evs: Json, to: str | None = None) -> list[tuple[str, str, str]]:
    return [(x.character, x.kind, x.via) for x in memory.seeds(BOOK, st, list(evs), to)]


def test_help_goes_to_the_beneficiary_and_witnesses_get_an_impression() -> None:
    st = _state(**{OLD: "place.syracuse-square", "char.melos": "place.syracuse-square"})
    assert _seeds(st, _ev(beneficiary=OLD)) == [
        (OLD, "help", "witnessed"),
        ("char.melos", "impression", "witnessed"),
    ]


def test_absent_characters_and_rejected_events_get_nothing() -> None:
    st = _state(**{OLD: "place.melos-home"})
    assert _seeds(st, _ev(beneficiary=OLD)) == []
    told = _ev(type="say", effects=[{"op": "learn", "character": OLD, "fact": "fact.x"}])
    assert _seeds(st, told) == [(OLD, "claim", "told")]
    rejected = _ev(beneficiary=OLD, check={"status": "rejected"})
    near = _state(**{OLD: "place.syracuse-square"})
    assert _seeds(near, rejected) == []


def test_a_character_helping_the_player_remembers_it() -> None:
    st = _state(**{OLD: "place.syracuse-square"})
    (got,) = memory.seeds(BOOK, st, [_ev(actor=OLD, beneficiary="player")])
    assert (got.kind, got.trust_delta, got.salience) == memory.HELPED_YOU


def test_a_say_leaves_an_impression_only_on_the_one_spoken_to() -> None:
    st = _state(**{OLD: "place.syracuse-square", "char.melos": "place.syracuse-square"})
    assert _seeds(st, _ev(type="say"), to=OLD) == [(OLD, "impression", "witnessed")]


def test_one_memory_per_character_per_turn_takes_the_top_row() -> None:
    """数据评审：同一轮几条事件合成一条，fromEvents 列全，kind 取对照表最靠前的一行；keyMoment 加 0.2。"""
    st = _state(**{OLD: "place.syracuse-square"})
    say = _ev(eventId="ev_1", type="say", t=st["t"], dt=0)
    made = _ev(
        eventId="ev_2",
        type="say",
        t=st["t"],
        dt=0,
        keyMoment=True,
        effects=[{"op": "promise", "change": "made", "promiseId": "pr_1", "from": "player", "to": OLD, "text": "…"}],
    )
    (got,) = memory.seeds(BOOK, st, [say, made], OLD)
    assert (got.kind, got.trust_delta, got.promise_id) == ("promise", memory.PROMISE_MADE[1], "pr_1")
    assert [e["eventId"] for e in got.events] == ["ev_2", "ev_1"]
    assert got.salience == 1.0  # 0.8 + 0.2


def test_lowering_his_trust_is_harm() -> None:
    st = _state(**{"char.king": "place.syracuse-square"})
    hit = _ev(effects=[{"op": "inc", "var": "var.king.trust", "by": -1}])
    assert _seeds(st, hit) == [("char.king", "harm", "witnessed")]


def test_the_model_weight_raises_salience_up_to_one() -> None:
    s = memory.Seed(OLD, "claim", (_ev(),), 0, 0.5, "witnessed")
    assert [memory.weighted(s, w) for w in (1, 2, 3, 9)] == [0.5, 0.6, 0.7, 0.7]
    top = memory.Seed(OLD, "harm", (_ev(),), -15, 0.95, "witnessed")
    assert memory.weighted(top, 3) == 1.0


def test_at_most_three_per_commit_by_salience() -> None:
    st = _state(**{c: "place.syracuse-square" for c in BOOK.characters})
    evs = [_ev(eventId="ev_1", t=st["t"], dt=0, beneficiary=OLD)]  # 帮了老爺，在场的别人都看到了
    got = memory.seeds(BOOK, st, evs)
    assert len(got) == memory.MAX_PER_COMMIT and got[0].kind == "help"
    assert [x.kind for x in got[1:]] == ["impression", "impression"]


@pytest.mark.parametrize(
    ("raw", "tidied"),
    [("「家まで送ってくれた人」", "家まで送ってくれた人"), ("家まで送ってくれた人。", "家まで送ってくれた人")],
)
def test_quotes_and_the_final_period_are_dropped(raw: str, tidied: str) -> None:
    assert memory.tidy(raw) == tidied


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ("老爺の荷車が市に着いたこと", True),
        ("彼が市に着いたこと", False),
        ("老爺が覚えていること", False),
        ("老爺の荷車が市に着いたこと" * 3, False),
    ],
)
def test_keeps_rules(text: str, ok: bool) -> None:
    assert memory.keeps_ok(text) is ok


# —— 第 6 组（评测入口这一侧）：删除 ——


def test_deleting_a_promise_memory_voids_the_promise(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """E6-012 的形状：整轮原话清空、写 forget 事件、约定 voided、信任回到初值；事件还在；删了的带 deletedAt。"""
    s = session(env, monkeypatch)
    step = s.say(OLD, OFFER)
    made = next(e for e in step["events"] if e["effects"])
    promise_id = made["effects"][0]["promiseId"]
    gone = s.delete_memory(OLD, 1)
    (forget,) = gone["events"]
    assert forget["type"] == "forget" and forget["origin"] == "memory" and forget["actor"] == "player"
    assert forget["dt"] == 0 and forget["summary"] == "市の老爺との約束は、なかったことになった"
    assert "覚え" not in forget["summary"] and "忘れ" not in forget["summary"]
    assert forget["effects"] == [{"op": "promise", "promiseId": promise_id, "change": "voided"}]
    assert gone["promiseVoided"] == promise_id
    assert s.state()["promises"][promise_id]["status"] == "voided"
    assert s.utterance_cleared(1) and s.trust(OLD) == 0
    assert made["eventId"] in {e["eventId"] for e in s.events()}  # 世界的后果不撤销
    (m,) = s.memories(OLD)
    assert m["text"] == "" and m["deletedAt"] and SCHEMAS.errors(*MEMORY_ITEM, m) == []
    assert metrics(env, s.pid)["memories_deleted"] == 1
    with pytest.raises(ValueError, match="没有来源于"):  # 删过的不再删，评测报错（不静默成功）
        s.delete_memory(OLD, 1)


def test_a_kept_promise_is_not_voided(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    s = session(env, monkeypatch)
    step = s.say(OLD, OFFER)
    promise_id = next(e for e in step["events"] if e["effects"])["effects"][0]["promiseId"]
    kept = {
        "candidates": [
            {
                "actor": "player",
                "type": "action",
                "origin": "turn",
                "summary": "旅人は市の老爺を家まで送った",
                "causes": [],
                "effects": [{"op": "promise", "change": "kept", "promiseId": promise_id}],
                "needsConfirm": False,
            }
        ]
    }
    s.text.rules.insert(0, s.text._rule({"kind": "extract", "when": {"playerContains": "着き"}, "output": kept}, "t"))
    s.say(OLD, "着きましたよ。")
    assert s.state()["promises"][promise_id]["status"] == "kept"
    assert s.delete_memory(OLD, 1)["events"] == []
    assert [m["kind"] for m in s.memories(OLD) if not m.get("deletedAt")] == ["help"]  # 兑现的那一轮
    assert s.state()["promises"][promise_id]["status"] == "kept"


# —— 第 9 组：评测入口 ——


def test_setup_can_plant_a_memory(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """E6-101 的种记忆：不调模型，来源是布置的那条事件。"""
    monkeypatch.setenv("DATABASE_URL", env.url)
    planted = {
        "effects": [],
        "note": "布置",
        "memory": {"character": OLD, "kind": "help", "text": "家まで送ってくれた人"},
    }
    s = eval_api.setup({**MINIMAL, "events": [planted]}, mode="text")
    (m,) = s.memories(OLD)
    assert m["kind"] == "help" and m["text"] == "家まで送ってくれた人" and s.trust(OLD) == memory.HELPED[1]
    assert m["fromEvents"] == [s.events()[-1]["eventId"]]


def test_a_planted_memory_goes_through_the_filters(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", env.url)
    planted = {"effects": [], "memory": {"character": OLD, "kind": "claim", "text": "電話は090-1234-5678"}}
    with pytest.raises(ValueError, match="过滤"):
        eval_api.setup({**MINIMAL, "events": [planted]}, mode="text")


def test_new_playthrough_forgets_the_last_one(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    s = session(env, monkeypatch)
    s.say(OLD, OFFER)
    first = s.pid
    s.new_playthrough()
    assert s.pid != first and s.memories(OLD) == [] and s.trust(OLD) == 0
    assert s.db_absent(["memory_items"]) == {"memory_items": 0}


def test_delete_playthrough_leaves_nothing(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """E6-010：每张表都是 0；还没建的表（briefs）答 0；不认识的表名不答（评测报「后端没回」）。"""
    s = session(env, monkeypatch)
    s.say(OLD, OFFER)
    tables = [
        "playthroughs",
        "events",
        "utterances",
        "memory_items",
        "world_state",
        "endings",
        "playthrough_metrics",
        "turns",
        "briefs",
    ]
    assert s.db_absent(["memory_items"]) == {"memory_items": 1}
    s.delete_playthrough()
    assert s.db_absent(tables) == dict.fromkeys(tables, 0)
    assert s.db_absent(["memory_itemz"]) == {}


def test_after_deleting_he_no_longer_knows_what_he_learned_in_that_turn(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """UX 评审：删了以后，这个人物的局势说明里没有来源事件里他学到的事、作废的约定、forget 事件的摘要。"""
    told = {
        "candidates": [
            {
                "actor": "player",
                "type": "say",
                "origin": "turn",
                "summary": "旅人は市の老爺に、自分は旅の薬師だと話した",
                "causes": [],
                "effects": [{"op": "improv", "character": OLD, "statement": STATEMENT}],
                "needsConfirm": False,
            }
        ]
    }
    s = session(env, monkeypatch)
    s.text.rules.insert(0, s.text._rule({"kind": "extract", "when": {"playerContains": "薬師"}, "output": told}, "t"))
    step = s.say(OLD, "私は旅の薬師です。")
    (fact,) = [e["factId"] for ev in step["events"] for e in ev["effects"] if e["op"] == "improv"]
    statement = STATEMENT

    async def look() -> tuple[frozenset[str], Any]:
        engine = env.engine()
        try:
            async with engine.connect() as c:
                return await memory.forgotten_facts(c, BOOK, s.pid, OLD), await store.sim_state(c, s.pid)
        finally:
            await engine.dispose()

    gone, st = asyncio.run(look())
    assert gone == frozenset() and statement in "".join(brief.situation_facts(BOOK, st, OLD))
    s.delete_memory(OLD, 1)
    s.say(OLD, OFFER)
    s.delete_memory(OLD, 3)  # 删除本身也算一步
    gone, st = asyncio.run(look())
    assert gone == {fact}
    system = brief.build(BOOK, st, OLD, memories=[], forgotten=gone).system
    assert statement not in system and "家まで送る" not in system and "なかったこと" not in system
