"""B-8 验收第 7 组：没提交的那几次也记进这一局的花费（数据在 #76 的评审里提的）。

假模型给每次调用（含被时限取消的）记一个固定的花费，对 `playthrough_metrics` 里各类花费的合计：一轮在窗口里被作废、
一次调用超时重发、一个任务失败后重来，这些已经花的钱都要在里面。台词都是为测试写的。
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy import select
from zoujin_backend.db import store
from zoujin_backend.db.tables import playthrough_metrics, turns
from zoujin_backend.models.text import FakeText, TextResult
from zoujin_backend.narrator.core import COST_COLUMNS, Narrator

from .conftest import LIBRARY, SCHEMAS, Env
from .test_rules import OLD

pytestmark = pytest.mark.db

Json = Any
COST = 0.01
FAST = {"triage": 0.05, "extract": 0.05, "check": 0.05, "rewrite": 0.05, "reply": 0.05, "narrate": 0.05, "plan": 0.05}


class Priced(FakeText):
    """每次调用记 COST 美元；被时限取消的也记 COST（真客户端按预计记账）。"""

    async def call(self, kind: str, request: Json) -> TextResult:
        return replace(await super().call(kind, request), cost_usd=COST)

    def cancelled_cost(self, kind: str, request: Json) -> float:
        return COST


async def spent(engine: Any, pid: str) -> float:
    async with engine.connect() as c:
        row: Mapping[str, Any] = (
            (await c.execute(select(playthrough_metrics).where(playthrough_metrics.c.playthrough_id == pid)))
            .mappings()
            .one()
        )
    return sum(float(row[col]) for col in COST_COLUMNS.values())


def test_a_retracted_turn_still_costs(env: Env) -> None:
    async def main() -> None:
        engine = env.engine()
        try:
            pid = await env.opened(engine)
            assert await spent(engine, pid) == 0.0  # 开局用的假模型不记钱
            async with engine.begin() as c:
                turn_id = await store.enqueue(
                    c, env.ids, pid, kind="talk", input_mode="text", character=OLD, commit_after=0.6
                )
                await store.add_utterance(c, env.ids, pid, turn_id, speaker="player", text="……", t=0)
                await store.add_utterance(c, env.ids, pid, turn_id, speaker=OLD, text="……", t=0, source="live")

            async def retract_when_leased() -> str | None:
                while True:  # 叙事者判完在等窗口时作废
                    async with engine.connect() as c:
                        status = await c.scalar(select(turns.c.status).where(turns.c.turn_id == turn_id))
                    if status == "leased":
                        break
                    await asyncio.sleep(0.02)
                await asyncio.sleep(0.1)
                async with engine.begin() as c:
                    return await store.retract_queued(c, pid, turn_id)

            priced = Priced()
            n = Narrator(engine=engine, library=LIBRARY, text=priced, schemas=SCHEMAS, ids=env.ids)
            kind, done = await asyncio.gather(retract_when_leased(), n.run(pid))
            assert kind == "talk" and done == []
            assert [k for k, _ in priced.calls] == ["triage", "extract"]
            assert await spent(engine, pid) == pytest.approx(COST * len(priced.calls))
        finally:
            await engine.dispose()

    asyncio.run(main())


def test_timeouts_and_a_failed_attempt_still_cost(env: Env) -> None:
    async def main() -> None:
        engine = env.engine()
        try:
            pid = await env.opened(engine)
            turn_id = await env.talk(engine, pid)
            priced = Priced(rules=[{"kind": "extract", "latencyMs": 300, "times": 1}])  # 第一次提取超时
            failed: list[str] = []

            def fault(step: str) -> None:
                if step == "events" and not failed:  # 第一次提交在写事件时失败：任务放回去重来
                    failed.append(step)
                    raise RuntimeError("注入")

            n = Narrator(
                engine=engine, library=LIBRARY, text=priced, schemas=SCHEMAS, ids=env.ids, deadlines=FAST, fault=fault
            )
            (result,) = await n.run(pid)
            assert result.task.turn_id == turn_id and result.task.attempts == 2
            # 第一次：分流、提取（超时）、提取；重来：分流、提取
            assert [k for k, _ in priced.calls] == ["triage", "extract", "extract", "triage", "extract"]
            assert await spent(engine, pid) == pytest.approx(COST * 5)
        finally:
            await engine.dispose()

    asyncio.run(main())
