"""B-21：候选话语（ux-design 7.8，api-contract 3.5 的 `suggestions`）。假文本模型，不花钱。

人物说完一轮、会话刚就绪时推 2〜3 个；不全是问句（全是问句按不合格重发，两次都不行就不出）；节约档不自动推；
生成期间又开始了一轮就不推过时的。
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from sqlalchemy import update
from zoujin_backend.db.tables import playthrough_metrics
from zoujin_backend.ids import IdGen
from zoujin_backend.models.text import FakeText
from zoujin_backend.narrator.pipeline import Pipeline, Spend
from zoujin_backend.world import Library
from zoujin_worldsim import initial_state

from .conftest import OLD, SCHEMAS, Env
from .test_gateway_b4 import InProc, Make, Play, db
from .test_gateway_b4 import inproc as inproc  # noqa: PLC0414 - pytest 的 fixture 按名字找
from .test_gateway_b4 import play as play  # noqa: PLC0414

SPEED = 0.05
Json = Any
ALL_ASK = [{"text": "どうして？", "kind": "ask"}, {"text": "本当に？", "kind": "ask"}]


def suggestions(p: Any) -> list[Json]:
    return [m for m in p.log if m["type"] == "suggestions"]


def pipeline(rules: list[Json]) -> Pipeline:
    return Pipeline(FakeText(rules=rules), SCHEMAS, IdGen())


def slice_book() -> Any:
    from zoujin_backend.config import Settings

    from .test_b3 import SLICE

    st = Settings(database_url="unused")
    return Library(st.worlds, st.scenes, SLICE).current


def test_pipeline_suggests_and_rejects_all_questions() -> None:
    book = slice_book()
    st = initial_state(book.world, "role.traveler")
    got = asyncio.run(pipeline([]).suggest(book, st, OLD, Spend(), player="こんにちは。", reply="……ああ。"))
    assert got is not None and 2 <= len(got) <= 3 and any(x["kind"] != "ask" for x in got)
    p = pipeline([{"kind": "suggest", "output": {"items": ALL_ASK}}])
    assert asyncio.run(p.suggest(book, st, OLD, Spend())) is None  # 两次都全是问句：不出
    (_, req) = p.text.calls[0]  # type: ignore[attr-defined]
    assert "turn" not in req and req["character"] == OLD


@pytest.mark.db
def test_after_a_turn_and_on_ready(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    p.focus(OLD)
    first = p.expect("suggestions", character=OLD)  # 会话刚就绪
    assert "turnId" not in first
    t = p.text("こんにちは。")
    p.expect("turn_settled", turnId=t)
    after = p.find("suggestions", turnId=t)
    assert after["character"] == OLD and 2 <= len(after["items"]) <= 3
    assert any(x["kind"] != "ask" for x in after["items"])
    kinds = [k for k, _ in s.gw.replier.text.calls if k == "suggest"]  # type: ignore[attr-defined]
    assert len(kinds) >= 2


@pytest.mark.db
def test_saving_tier_does_not_push(env: Env, inproc: Make, play: Play) -> None:
    s: InProc = inproc(SPEED)
    p = play(s)

    async def saving(c: Any) -> None:
        await c.execute(
            update(playthrough_metrics)
            .where(playthrough_metrics.c.playthrough_id == p.pid)
            .values(cost_extract_usd=1.7)
        )

    db(env, saving)
    p.focus(OLD)
    t = p.text("こんにちは。")
    p.expect("turn_settled", turnId=t)
    t = p.text("この市は、ずいぶん静かですね。")
    p.expect("turn_settled", turnId=t)
    assert suggestions(p) == []
