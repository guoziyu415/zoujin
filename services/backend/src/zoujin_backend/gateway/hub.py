"""The narrator's NOTIFY after a commit → gateway push (B-0 item 7, step 5).

The gateway process opens an autocommit psycopg connection with `LISTEN zoujin_commit` and hands each notification to
Gateway.on_commit. If the connection drops it reconnects, then pushes to every open connection once (commits made while
disconnected are not lost: pushes read from the database by seq).

ナレーターの commit 後の NOTIFY → ゲートウェイのプッシュ（B-0 第 7 項の第 5 段階）。

ゲートウェイのプロセスは autocommit の psycopg 接続を 1 本開いて `LISTEN zoujin_commit` し、通知を 1 件受け取るたびに
Gateway.on_commit に渡す。接続が切れたら再接続し、再接続後に開いている接続すべてへ 1 回プッシュする（切断中の commit は
失われない：プッシュは seq に従ってデータベースから読む）。
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
    """SQLAlchemy's postgresql+psycopg:// → the postgresql:// that psycopg accepts.

    SQLAlchemy の postgresql+psycopg:// → psycopg が受け付ける postgresql://。
    """
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
                            log.warning("Unreadable NOTIFY / 読めない NOTIFY")
                            continue
                        self.gw.spawn(self.gw.on_commit(payload))
            except asyncio.CancelledError:
                raise
            except Exception:
                self.listening.clear()
                log.exception(
                    "LISTEN connection dropped, reconnecting in %.0f s / LISTEN 接続が切れたので再接続する",
                    RETRY_SECONDS,
                )
                await asyncio.sleep(RETRY_SECONDS)
