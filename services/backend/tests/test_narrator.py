"""叙事者骨架（B-0 验收第 3、4、5 组和最小剧本）：单事务提交、注入失败、并发、重放。真 PostgreSQL，进程内调。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import pytest
from sqlalchemy import func, select, update
from zoujin_backend.admin import replay
from zoujin_backend.db import store
from zoujin_backend.db.tables import events, playthrough_metrics, playthroughs, turns, world_state
from zoujin_backend.models.text import FakeText
from zoujin_backend.narrator.core import Narrator, Task
from zoujin_backend.trace import Tracer

from .conftest import BOOK, LIBRARY, OLD, PLAYER_LINE, SCHEMAS, Env

pytestmark = pytest.mark.db

Json = Any

STEPS = ("lock", "apply", "validate", "events", "world_state", "playthrough", "turn", "metrics", "notify", "commit")


def shape(ev: Json) -> tuple[Any, ...]:
    """比较两次运行写的事件：去掉每次不同的 ID、时间戳和分配的约定 ID。"""
    effects = [{k: v for k, v in e.items() if k not in ("promiseId", "factId")} for e in ev["effects"]]
    return (ev["seq"], ev["t"], ev["dt"], ev["actor"], ev["type"], ev["summary"], effects, ev["check"]["status"])


async def log_of(env: Env, pid: str) -> list[Json]:
    engine = env.engine()
    try:
        async with engine.connect() as c:
            return await store.event_log(c, pid, BOOK.version)
    finally:
        await engine.dispose()


def test_minimal_script(env: Env) -> None:
    """B-0 第 10 条（B-2 走整条流水线）：旅人在广场对老爺说一句话 → 两个候选事件：老爺的即兴设定过了第 3、4 步；
    让节拍直接发生的那个第 3 步不过，改写原样、降级做不到 → 被否决 → 提交。"""

    async def main() -> None:
        engine = env.engine()
        pid = await env.opened(engine)
        opened = await log_of(env, pid)
        assert [e["origin"] for e in opened] == ["schedule", "act"]  # beat.01 先到点，再是开局
        assert opened[-1]["t"] == BOOK.roles["role.traveler"]["startT"]
        turn_id = await env.talk(engine, pid)
        (result,) = await env.narrator(engine).run(pid)
        assert result.task.turn_id == turn_id and result.outcome == "rejected" and result.minutes == 10
        evs = result.events
        assert [(e["actor"], e["check"]["status"], bool(e["effects"])) for e in evs] == [
            (OLD, "passed", True),
            (OLD, "rejected", False),
            ("player", "passed", False),  # 这一轮的 10 分钟：只推进时钟的 say
        ]
        assert evs[0]["check"]["checker"].startswith("rules@") and "+gemini-3.8-flash/p" in evs[0]["check"]["checker"]
        assert evs[1]["check"]["failedRules"] == ["R2-precondition"] and evs[1]["check"]["attempts"] == 3
        assert evs[1]["check"]["checker"] == "rules@b2.1"  # 第 3 步就没过，没跑第 4 步
        assert [e["seq"] for e in evs] == [3, 4, 5] and evs[-1]["dt"] == 10
        assert all(e["turnId"] == turn_id for e in evs)
        for e in await log_of(env, pid):
            SCHEMAS.event(e)  # 读回来的也过数据契约
        async with engine.connect() as c:
            assert await c.scalar(select(turns.c.status).where(turns.c.turn_id == turn_id)) == "done"
        assert await replay(engine, LIBRARY, pid) == []
        await engine.dispose()

    asyncio.run(main())


def test_replay_reports_a_tampered_cache(env: Env) -> None:
    async def main() -> None:
        engine = env.engine()
        pid = await env.opened(engine)
        await env.talk(engine, pid)
        await env.narrator(engine).run(pid)
        assert await replay(engine, LIBRARY, pid) == []
        async with engine.begin() as c:
            st = await store.sim_state(c, pid)
            assert st is not None
            st["vars"]["var.player.location"] = "place.castle"
            await c.execute(update(world_state).where(world_state.c.playthrough_id == pid).values(state=st))
        assert await replay(engine, LIBRARY, pid) == ["vars"]
        assert await replay(engine, LIBRARY, "pt_00000000000000000000000000") is None
        await engine.dispose()

    asyncio.run(main())


async def counts(env: Env, pid: str) -> tuple[int, int, int]:
    engine = env.engine()
    try:
        async with engine.connect() as c:
            n = await c.scalar(select(func.count()).select_from(events).where(events.c.playthrough_id == pid))
            last = await c.scalar(select(playthroughs.c.last_seq).where(playthroughs.c.playthrough_id == pid))
            cached = await c.scalar(select(world_state.c.as_of_seq).where(world_state.c.playthrough_id == pid))
    finally:
        await engine.dispose()
    return int(n or 0), int(last or 0), int(cached or 0)


@pytest.mark.parametrize("step", STEPS)
def test_failure_at_each_step_leaves_no_half_turn(env: Env, step: str) -> None:
    """每一步注入失败：库里没有半轮数据；重试（同一个幂等键）后的结果和一次成功的一样。"""

    async def main() -> None:
        engine = env.engine()
        clean = await env.opened(engine)
        await env.talk(engine, clean)
        await env.narrator(engine).run(clean)
        want = [shape(e) for e in await log_of(env, clean)]

        pid = await env.opened(engine)
        before = await counts(env, pid)
        turn_id = await env.talk(engine, pid)
        seen: list[tuple[int, int, int]] = []

        def fault(at: str) -> None:
            if at == step and not seen:
                seen.append((0, 0, 0))
                raise RuntimeError(f"注入：{at}")

        n = env.narrator(engine, fault=fault)
        task = await n.claim(pid)
        assert task is not None
        with pytest.raises(RuntimeError):
            await n.process(task)
        assert await counts(env, pid) == before  # 什么都没写进去
        await n.release(task, failed=False)
        (result,) = await n.run(pid)  # 重试：同一个任务、同一个幂等键
        assert result.task.turn_id == turn_id and result.task.key == task.key and result.task.attempts == 2
        assert [shape(e) for e in await log_of(env, pid)] == want
        assert {e["idempotencyKey"].rsplit("/", 1)[0] for e in result.events} == {task.key}
        assert await replay(engine, LIBRARY, pid) == []
        await engine.dispose()

    asyncio.run(main())


def test_third_failure_gives_up_with_no_response(env: Env) -> None:
    async def main() -> None:
        engine = env.engine()
        pid = await env.opened(engine)
        before = await counts(env, pid)
        turn_id = await env.talk(engine, pid)

        def always(at: str) -> None:
            if at == "events":
                raise RuntimeError("注入")

        assert await env.narrator(engine, fault=always).run(pid) == []
        async with engine.connect() as c:
            row = (await c.execute(select(turns).where(turns.c.turn_id == turn_id))).mappings().one()
        assert (row["status"], row["outcome"], row["attempts"], row["minutes"]) == ("failed", "no_response", 3, 0)
        assert await counts(env, pid) == before
        await engine.dispose()

    asyncio.run(main())


def test_two_turns_in_one_playthrough_commit_in_order(env: Env) -> None:
    async def main() -> None:
        engine = env.engine()
        pid = await env.opened(engine)
        first = await env.talk(engine, pid)
        second = await env.talk(engine, pid, text="この市は、ずいぶん静かですね。")
        a, b = env.narrator(engine), env.narrator(engine)
        done = [*await asyncio.gather(a.run(pid), b.run(pid))]
        order = [r.task.turn_id for rs in done for r in rs]
        assert sorted(order) == sorted([first, second])
        log = await log_of(env, pid)
        assert [e["seq"] for e in log] == list(range(1, len(log) + 1))
        turn_order = [e["turnId"] for e in log if "turnId" in e]
        assert turn_order.index(first) < turn_order.index(second)
        assert await replay(engine, LIBRARY, pid) == []
        await engine.dispose()

    asyncio.run(main())


def test_two_playthroughs_do_not_block_each_other(env: Env) -> None:
    async def main() -> None:
        engine = env.engine()
        slow_pid = await env.opened(engine)
        fast_pid = await env.opened(engine)
        await env.talk(engine, slow_pid)
        await env.talk(engine, fast_pid)
        holding = asyncio.Event()
        release = asyncio.Event()

        async def hold(task: Task) -> None:
            holding.set()
            await release.wait()

        slow = asyncio.ensure_future(env.narrator(engine, before_commit=hold).run(slow_pid))
        await holding.wait()
        (fast,) = await asyncio.wait_for(env.narrator(engine).run(fast_pid), timeout=10)
        assert fast.outcome is not None and not slow.done()
        release.set()
        (done,) = await slow
        assert done.task.pid == slow_pid
        await engine.dispose()

    asyncio.run(main())


def test_stale_result_is_discarded_and_rechecked(env: Env) -> None:
    """检查完、提交前，到点的节拍先提交了（lastSeq 变了）：这次结果作废，用新状态重来。"""

    async def main() -> None:
        engine = env.engine()
        pid = await env.opened(engine)
        turn_id = await env.talk(engine, pid)
        other = env.narrator(engine)
        calls: list[int] = []

        async def interleave(task: Task) -> None:
            calls.append(1)
            if len(calls) > 1:
                return
            # 别的提交抢先：快进 120 分钟（beat.02、beat.03 到点）
            async with engine.begin() as c:
                adv = await store.enqueue(c, env.ids, pid, kind="advance", minutes=120)
                await c.execute(update(turns).where(turns.c.turn_id == adv).values(status="leased", attempts=1))
            await other._commit(
                Task(adv, pid, "advance", None, None, 120, adv, 1), None, lambda w, b: other._advance(w, 120)
            )

        n: Narrator = env.narrator(engine, before_commit=interleave)
        (result,) = [r for r in await n.run(pid) if r.task.turn_id == turn_id]
        assert len(calls) == 2  # 第一次的结果丢了，从检查重来
        log = await log_of(env, pid)
        assert [e["seq"] for e in log] == list(range(1, len(log) + 1))
        mine = [e for e in log if e.get("turnId") == turn_id]
        assert mine[0]["seq"] > max(e["seq"] for e in log if e["idempotencyKey"].startswith("turn_") and e not in mine)
        assert mine[0]["t"] >= 1050 + 120
        assert result.outcome == "rejected"
        assert await replay(engine, LIBRARY, pid) == []
        await engine.dispose()

    asyncio.run(main())


def test_two_extract_timeouts_commit_only_the_clock(env: Env) -> None:
    """B-2 第 3 组：提取两次都超时 → 这一轮只提交时钟事件，候选丢弃，指标加一，库里没有半轮。"""

    async def main() -> None:
        engine = env.engine()
        pid = await env.opened(engine)
        before = await counts(env, pid)
        turn_id = await env.talk(engine, pid)
        slow = FakeText(rules=[{"kind": "extract", "latencyMs": 300}])
        fast = dict.fromkeys(("triage", "extract", "check", "rewrite"), 0.05)
        n = Narrator(engine=engine, library=LIBRARY, text=slow, schemas=SCHEMAS, ids=env.ids, deadlines=fast)
        (result,) = await n.run(pid)
        assert [kind for kind, _ in slow.calls] == ["triage", "extract", "extract"]  # 第一次超时重发一次，没有检查
        assert [(e["actor"], e["type"], e["effects"], e["dt"]) for e in result.events] == [("player", "say", [], 10)]
        assert (result.outcome, result.minutes) == ("no_change", 10)  # 客户端收到的和提取没有候选时一样
        n_events, last, cached = await counts(env, pid)
        assert (n_events, last, cached) == (before[0] + 1, before[1] + 1, before[2] + 1)
        async with engine.connect() as c:
            row = (await c.execute(select(turns).where(turns.c.turn_id == turn_id))).mappings().one()
            m = (
                (await c.execute(select(playthrough_metrics).where(playthrough_metrics.c.playthrough_id == pid)))
                .mappings()
                .one()
            )
        assert (row["status"], row["minutes"]) == ("done", 10)
        assert (m["turns_timed_out"], m["candidates_rejected"], m["candidates_rewritten"]) == (1, 0, 0)
        assert await replay(engine, LIBRARY, pid) == []
        await engine.dispose()

    asyncio.run(main())


def test_logs_and_spans_carry_no_words(env: Env, caplog: pytest.LogCaptureFixture) -> None:
    """B-2 第 9 组：原话、人物的回答、摘要、即兴设定、否决理由都不进日志和 Span（data-design 第 8 节）。"""
    said, answer = "ゆびきりマーカー", "かえりみちマーカー"
    caplog.set_level(logging.DEBUG)

    async def main() -> list[str]:
        engine = env.engine()
        pid = await env.opened(engine)
        await env.talk(engine, pid, text=f"{said}。{PLAYER_LINE}", reply=answer)
        tracer = Tracer()
        (result,) = await env.narrator(engine, tracer=tracer).run(pid)
        await engine.dispose()
        assert tracer.spans and [e["check"]["status"] for e in result.events[:2]] == ["passed", "rejected"]
        words = [e["summary"] for e in result.events[:2]] + [str(result.events[1]["check"]["reason"])]
        words += [x["statement"] for x in result.events[0]["effects"]]
        return [*words, json.dumps([s.attrs for s in tracer.spans], ensure_ascii=False)]

    *words, spans = asyncio.run(main())
    assert "R2-precondition" in spans and "R2-precondition" in caplog.text  # 规则名照写
    for w in [said, answer, *words]:
        assert w not in caplog.text and w not in spans, w
