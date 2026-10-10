"""`uv run zoujin-admin`：运维用的命令（B-0 第 3、8 条）。只连 `DATABASE_URL`，不碰任何云服务。

- `invite create [--count N]`：生成邀请码。明文只打印这一次，库里只存哈希。
- `replay <playthroughId>`：从 W-1 的 initial_state 加全部事件按 seq 用 apply 重建 SimState，和 world_state 表里的比。
  一致退出 0，不一致退出 1（打印不一致的字段名，不打印值），没有这一局退出 2。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from zoujin_backend.config import Settings
from zoujin_backend.db import store
from zoujin_backend.gateway import auth
from zoujin_backend.world import Library

EXIT_MISMATCH = 1
EXIT_NOT_FOUND = 2


async def create_invites(engine: AsyncEngine, count: int) -> list[str]:
    async with engine.begin() as c:
        return [await auth.add_invite(c) for _ in range(count)]


async def replay(engine: AsyncEngine, library: Library, pid: str) -> list[str] | None:
    """不一致的顶层字段名（一致时为空）；没有这一局或还没开局时 None。"""
    async with engine.connect() as c:
        pt = await store.playthrough(c, pid)
        cached = await store.sim_state(c, pid)
        if pt is None or cached is None:
            return None
        book = library.version(pt["world_model_version"])
        log = await store.event_log(c, pid, book.version)
    rebuilt = store.replay(book, pt["role_id"], log)
    return diff(dict(rebuilt), dict(cached))


def diff(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    return sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))


async def _main(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    engine = create_async_engine(settings.database_url)
    try:
        if args.cmd == "invite":
            for code in await create_invites(engine, args.count):
                print(code)
            return 0
        library = Library(settings.worlds, settings.scenes)
        fields = await replay(engine, library, args.playthrough_id)
        if fields is None:
            print(f"没有这一局，或开局还没做完：{args.playthrough_id}", file=sys.stderr)
            return EXIT_NOT_FOUND
        if fields:
            print(f"不一致：{', '.join(fields)}", file=sys.stderr)
            return EXIT_MISMATCH
        print("一致")
        return 0
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="zoujin-admin", description="运维命令（B-0）")
    sub = p.add_subparsers(dest="cmd", required=True)
    inv = sub.add_parser("invite", help="邀请码")
    inv_sub = inv.add_subparsers(dest="action", required=True)
    create = inv_sub.add_parser("create", help="生成邀请码，明文只打印这一次")
    create.add_argument("--count", type=int, default=1)
    rp = sub.add_parser("replay", help="用事件重建世界状态，和缓存比")
    rp.add_argument("playthrough_id")
    args = p.parse_args(argv)
    if args.cmd == "invite" and args.count < 1:
        p.error("--count 至少 1")
    sys.exit(asyncio.run(_main(args)))
