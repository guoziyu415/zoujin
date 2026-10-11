"""B-9（切片的简化结局）走评测入口的验收：触发（第 1 条）、生成和保存（第 4、6〜8 条）、评测入口（第 11 条）、
日志和 Trace（第 12 条）、迁移。世界模型用切片版，假模型。不要数据库的部分在 `test_b9_unit.py`，
WebSocket 和 REST 在 `test_gateway_b9.py`。"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest
from alembic import command
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from zoujin_backend import eval_api
from zoujin_backend.config import REPO, async_url
from zoujin_backend.db.tables import PER_PLAYTHROUGH, endings, turns, utterances
from zoujin_backend.models.text import FakeText, TextResult, record
from zoujin_backend.narrator import ending as E

from . import test_b3
from .conftest import OLD, SCHEMAS, alembic_config
from .test_b3 import ACCEPTED, CITY, HOME, Game, types

pytestmark = pytest.mark.db

game = test_b3.game  # 同一个 fixture：评测入口的一局，世界模型用切片版

Json = Any

LATE = {
    "effects": [{"op": "set", "var": "var.melos.custody", "value": "free"}],
    "note": "测试造的：梅洛斯没有放出来，beat.24 到不了，日没时期限结算",
}
CURTAIN = ("beat.25", "beat.26", "beat.27")


def ending_turn(g: Game) -> Json:
    async def main() -> Json:
        engine = g._engine()
        try:
            async with engine.connect() as c:
                q = select(turns).where(turns.c.playthrough_id == g.s.pid, turns.c.kind == E.KIND)
                return [dict(r) for r in (await c.execute(q)).mappings()]
        finally:
            await engine.dispose()

    rows = eval_api._run(main())
    assert len(rows) <= 1
    return rows[0] if rows else None


def to_sunset(g: Game) -> Json:
    """第四幕里等到日没（等的动作：beat.s1，再 beat.24）。返回触发结局的那一步。"""
    for _ in range(4):
        step = g.s.act("wait", None, {})
        if g.row()["status"] == "ended":
            return step
    raise AssertionError("没进结局")


def texts(ending: Json) -> list[str]:
    p = ending["player"]
    out = [x["sentence"] for k in ("epilogue", "didForYou", "youDid") for x in p.get(k, [])]
    out += [p["title"]["text"], p["fate"]["label"], *ending["card"].values()]
    out += [x["sentence"] for c in ending["characters"] for x in c.get("yours", [])]
    return [str(x) for x in out]


@pytest.mark.parametrize("exit_id", [CITY, HOME])
def test_both_paths_reach_the_ending(game: Callable[..., Game], exit_id: str) -> None:
    """验收第 1 条：「市に残り」「身を寄せる」各走到 beat.24。"""
    g = game("sc.canon@beat.07", walked=True)
    g.s.choose(exit_id)
    assert g.row()["status"] == "active" and g.s.ending() is None  # 第四幕开头、watchBeat 还没结果：不触发
    step = to_sunset(g)
    row = g.row()
    assert row["status"] == "ended" and row["ended_at"] is not None
    beats = [x["beat"] for e in g.s.events() for x in e["effects"] if x["op"] == "beat"]
    assert set(CURTAIN) <= set(beats)
    result = g.turn(step["traceId"])["result"]
    (started,) = result["before"]
    assert started["type"] == "ending_started" and started["trigger"] == "story-closed"
    assert types(result["push"])[-1] == "action_result" and set(types(result["push"])[:-1]) == {"set_piece"}
    first = min(e["seq"] for e in step["events"])
    assert types(g.commits(first - 1))[:2] == ["ending_started", "commit"]  # 排在它那次提交的 commit 前面
    task = ending_turn(g)
    assert task["status"] == "done" and task["result"]["push"] == [
        {"type": "ending_ready", "endingId": task["result"]["endingId"]}
    ]
    assert task["request"]["outcome"] == "canon-reunion" and task["request"]["staging"] == started["staging"]
    got = g.s.ending()
    assert got is not None and got["world"]["outcome"] == "canon-reunion" and got["trigger"] == "story-closed"
    assert got["world"]["signature"]["beat.24"] is True and got["world"]["finalVars"]
    assert got["endingId"] == task["result"]["endingId"]
    SCHEMAS.ending(got)
    m = g.metrics()
    assert (m["ending_outcome"], m["ending_template"], m["ending_calls"]) == ("canon-reunion", False, 1)
    assert m["ending_started_at"] is not None and m["ending_ms"] is not None


def test_late_melos_is_a_deadline_ending(game: Callable[..., Game]) -> None:
    g = game("sc.canon@beat.07", events=[LATE])
    g.s.choose(CITY)
    step = to_sunset(g)
    (started,) = g.turn(step["traceId"])["result"]["before"]
    assert started["trigger"] == "deadline"
    stage = {x["id"]: x["state"] for x in started["staging"]["characters"]}
    assert (stage["char.selinuntius"], stage["char.melos"]) == ("on-cross", "absent")
    got = g.s.ending()
    assert got["world"]["outcome"] == "too-late"
    assert not [t for t in texts(got) if any(w in t for w in E.FORBIDDEN)]


def test_inputs_after_the_ending(game: Callable[..., Game]) -> None:
    """进了结局以后才轮到的：对话 no_response、动作 refused、选去处 invalid_request，都不写事件。"""
    g = game("sc.canon@beat.07", walked=True)
    g.s.choose(CITY)
    to_sunset(g)
    seq = g.seq
    said = g.s.say(OLD, "終わりましたね")
    assert said["events"] == [] and g.push(said) == [
        {"type": "turn_settled", "turnId": said["traceId"], "outcome": "no_response", "eventIds": [], "minutes": 0}
    ]
    done = g.s.act("wait", None, {})
    assert done["events"] == [] and done["status"] == "refused"
    assert g.s.choose(CITY)["error"] == "invalid_request"
    assert g.seq == seq and ending_turn(g) is not None


def test_texts_are_cleared_but_summaries_stay(game: Callable[..., Game]) -> None:
    """验收第 8 条：结局存好以后这一局的原话全空，打算文字清掉，事件的 summary 不动。"""
    g = game("sc.canon@beat.07", walked=True)
    g.s.propose(ACCEPTED)
    g.s.say(OLD, "メロスは来ますかね")
    before = [e["summary"] for e in g.s.events()]
    to_sunset(g)

    async def main() -> tuple[list[Any], list[Json]]:
        engine = g._engine()
        try:
            async with engine.connect() as c:
                said = list(await c.scalars(select(utterances.c.text).where(utterances.c.playthrough_id == g.s.pid)))
                q = select(turns.c.result).where(turns.c.playthrough_id == g.s.pid, turns.c.kind == "plan")
                return said, list(await c.scalars(q))
        finally:
            await engine.dispose()

    said, plans = eval_api._run(main())
    assert said and all(t is None for t in said)
    assert plans and "町の人々" not in str(plans)
    assert [e["summary"] for e in g.s.events()][: len(before)] == before


def broken(times: int | None) -> list[Json]:
    rule: Json = {"kind": "ending", "broken": True}
    if times is not None:
        rule["times"] = times
    return [rule]


def test_bad_once_is_rewritten(game: Callable[..., Game]) -> None:
    """验收第 5 条：第一次不过就重写一次，带上不过的规则名和字段。"""
    g = game("sc.canon@beat.07", walked=True)
    g.s.choose(CITY)
    fake = FakeText(rules=broken(1))
    g.s.text = fake
    to_sunset(g)
    calls = [r for k, r in fake.calls if k == "ending"]
    assert len(calls) == 2 and "problems" not in calls[0]
    assert {"rule": "cite-empty", "field": "epilogue[0]"} in calls[1]["problems"]
    m = g.metrics()
    assert (m["ending_template"], m["ending_calls"]) == (False, 2)


def test_bad_twice_uses_the_template(game: Callable[..., Game], caplog: pytest.LogCaptureFixture) -> None:
    """验收第 5、6、12 条：还坏就用模板；日志和 Trace 只有 ID、规则名、次数、耗时、花费。"""
    g = game("sc.canon@beat.07", walked=True)
    g.s.choose(CITY)
    g.s.say(OLD, "メロスはきっと来ると信じています")
    g.s.text = FakeText(rules=broken(None))
    with caplog.at_level(logging.DEBUG):
        to_sunset(g)
    got = g.s.ending()
    m = g.metrics()
    assert (m["ending_template"], m["ending_calls"]) == (True, 2)
    assert got["card"]["subtitle"] == "メロスは間に合い、王は仲間に入れてくれと言った。"
    assert got["player"]["epilogue"] and got["card"]["title"] == "友の帰りを見届けた旅人"
    SCHEMAS.ending(got)
    tries = g.s.tracer.named("narrator.ending")
    assert [s["status"] for s in tries] == ["rejected", "rejected"] and tries[0]["failed_rules"] == ["cite-empty"]
    (done,) = g.s.tracer.named("narrator.ending.done")
    assert (done["template"], done["calls"], done["outcome"]) == (True, 2, "canon-reunion")
    logged = caplog.text + str(tries) + str(done)
    for text in [*texts(got), "信じています"]:
        assert text not in logged


def test_timeout_is_resent_then_template(game: Callable[..., Game]) -> None:
    """验收第 7 条：假模型卡住，到时限取消、重发一次；再卡住就用模板（时限调小）。"""
    g = game("sc.canon@beat.07", walked=True)
    g.s.choose(CITY)
    g.s.settings = replace(g.s.settings, deadlines={**g.s.settings.deadlines, E.KIND: 0.05})
    g.s.text = FakeText(rules=[{"kind": "ending", "latencyMs": 500}])
    to_sunset(g)
    assert [s["status"] for s in g.s.tracer.named("narrator.ending")] == ["timeout", "timeout"]
    m = g.metrics()
    assert (m["ending_template"], m["ending_calls"]) == (True, 2) and m["ending_ms"] < 5000


def test_no_ending_before_the_last_act(game: Callable[..., Game]) -> None:
    g = game("sc.canon@beat.03")
    g.s.advance(60)
    assert g.row()["status"] == "active" and g.s.ending() is None and ending_turn(g) is None


def test_migration_0005_goes_down_and_up(migrated: str) -> None:
    cfg = alembic_config(migrated)

    async def tables() -> tuple[set[str], set[str]]:
        engine = create_async_engine(async_url(migrated), poolclass=NullPool)
        try:
            async with engine.connect() as c:
                names = await c.run_sync(lambda s: set(inspect(s).get_table_names()))
                cols = await c.run_sync(lambda s: {x["name"] for x in inspect(s).get_columns("playthrough_metrics")})
                return names, cols
        finally:
            await engine.dispose()

    command.downgrade(cfg, "0004")
    try:
        names, cols = asyncio.run(tables())
        assert "endings" not in names and "cost_ending_usd" not in cols
    finally:
        command.upgrade(cfg, "head")
    names, cols = asyncio.run(tables())
    assert "endings" in names and {"ending_outcome", "ending_template", "cost_ending_usd"} <= cols
    assert "endings" in PER_PLAYTHROUGH and endings.c.playthrough_id.foreign_keys


def test_curtain_pieces_play_wherever_the_player_is(game: Callable[..., Game]) -> None:
    """验收第 10 条：玩家不在刑场，收幕节拍上的固定演出也推（镜头在刑场），排在 ending_started 后面。"""
    here = game("sc.canon@beat.07", walked=True)
    here.s.choose(CITY)
    near = here.s.advance(120)
    away = game("sc.canon@beat.07", walked=True)
    away.s.choose(CITY)
    moved = away.s.act("move", "place.syracuse-square", {})
    assert moved["status"] == "done" and away.s.state()["vars"]["var.player.location"] == "place.syracuse-square"
    far = away.s.advance(120)
    here_r, away_r = here.turn(near["traceId"])["result"], away.turn(far["traceId"])["result"]
    assert types(here_r["before"]) == types(away_r["before"]) == ["ending_started"]
    assert here_r["pieces"] and away_r["pieces"] == here_r["pieces"]
    stage = {x["id"]: x["state"] for x in away_r["before"][0]["staging"]["characters"]}
    assert stage["player"] == "absent"


REPLAYS = REPO / "fixtures" / "model-replays" / "b9-ending.jsonl"


def test_replay_fixture_is_the_fake_ending_recorded(game: Callable[..., Game], monkeypatch: pytest.MonkeyPatch) -> None:
    """b9-ending.jsonl = 「市に残り」走到日没那一局的结局调用，输出取假模型的（真模型的等 Mac 探针）。提示、请求或假模型
    的输出改了，这条不过；重写：
    ZJ_UPDATE_REPLAYS=1 DATABASE_URL=… uv run pytest services/backend/tests/test_b9.py -k fixture
    """
    calls: list[Json] = []

    class Recorder(FakeText):
        async def call(self, kind: str, request: Json) -> TextResult:
            r = await super().call(kind, request)
            calls.append(record(kind, request, r.output, recorded_at="2026-10-11T00:00:00.000Z"))
            return r

    g = game("sc.canon@beat.07", walked=True)
    g.s.text = Recorder()
    g.s.choose(CITY)
    g.s.advance(120)
    text = "".join(json.dumps(c, ensure_ascii=False, sort_keys=True) + "\n" for c in calls)
    if os.environ.get("ZJ_UPDATE_REPLAYS") == "1":
        REPLAYS.write_text(text, encoding="utf-8")
    assert [c["kind"] for c in calls] == ["ending"]
    assert "e1" in str(calls[0]["request"]["events"]) and "ev_" not in str(calls[0]["request"])  # 事件 ID 用别名
    assert REPLAYS.read_text(encoding="utf-8") == text, "回放过期：ZJ_UPDATE_REPLAYS=1 重跑这条测试"

    monkeypatch.setenv("ZJ_MODEL", "replay")
    again = game("sc.canon@beat.07", walked=True)
    again.s.choose(CITY)
    again.s.advance(120)
    got = again.s.ending()
    assert got["player"]["epilogue"][0]["sentence"] == calls[0]["response"]["epilogue"][0]["sentence"]
    assert again.metrics()["ending_template"] is False
