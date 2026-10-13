"""In a real eval the connection pool must not land on an already closed event loop at the second step.

本物の評価では、コネクションプールが 2 ステップ目で閉じたイベントループに乗ってはならない。
"""

import asyncio
import contextvars

from zoujin_backend.eval_api import Session


def test_session_reuses_loop_and_copies_each_calls_context() -> None:
    session = object.__new__(Session)
    session.pid = "local-eval"
    session._runner = asyncio.Runner()
    current = contextvars.ContextVar("eval-test", default="unset")
    loops: list[asyncio.AbstractEventLoop] = []

    async def step() -> str:
        loop = asyncio.get_running_loop()
        if loops:
            assert loop is loops[0] and not loops[0].is_closed()
        loops.append(loop)
        return current.get()

    try:
        current.set("first")
        assert session._run(step()) == "first"
        current.set("next")
        assert session._run(step()) == "next"
    finally:
        session.close()
    assert loops[0].is_closed()
