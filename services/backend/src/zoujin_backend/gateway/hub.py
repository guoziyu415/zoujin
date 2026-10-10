"""叙事者提交后的 NOTIFY → 网关推送（B-0 第 7 条第 5 步）。

网关进程开一条 autocommit 的 psycopg 连接 `LISTEN zoujin_commit`；收到一条就交给 Gateway.on_commit。
连接断了就重连，重连后把开着的连接都推一遍（断开期间的提交不会丢：推送按 seq 从库里读）。
"""

from __future__ import annotations

import asyncio
import json
import logging

import psycopg

from zoujin_backend.gateway.core import Gateway
from zoujin_backend.narrator.core import CHANNEL

log = logging.getLogger("zoujin.gateway")

RETRY_SECONDS = 1.0


def plain_url(url: str) -> str:
    """SQLAlchemy 的 postgresql+psycopg:// → psycopg 认的 postgresql://。"""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


class Hub:
    def __init__(self, gw: Gateway) -> None:
        self.gw = gw
        self.task: asyncio.Task[None] | None = None
        self.listening = asyncio.Event()

    def start(self) -> None:
        self.task = asyncio.ensure_future(self._run())

    async def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        first = True
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(
                    plain_url(self.gw.settings.database_url), autocommit=True
                ) as conn:
                    await conn.execute(f"LISTEN {CHANNEL}")
                    self.listening.set()
                    if not first:
                        for c in list(self.gw.conns.values()):
                            self.gw.spawn(c.push())
                    first = False
                    async for note in conn.notifies():
                        try:
                            payload = json.loads(note.payload)
                        except json.JSONDecodeError:
                            log.warning("看不懂的 NOTIFY")
                            continue
                        self.gw.spawn(self.gw.on_commit(payload))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.listening.clear()
                log.exception("LISTEN 连接断了，%.0f 秒后重连", RETRY_SECONDS)
                await asyncio.sleep(RETRY_SECONDS)
