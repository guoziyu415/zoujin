"""`uv run zoujin-admin`: operations commands (B-0 items 3 and 8). Connects only to `DATABASE_URL`, never touches any
cloud service.

- `invite create [--count N]`: generate invite codes. The plaintext is printed only this once; the DB stores only the
  hash.
- `replay <playthroughId>`: rebuild SimState from W-1's initial_state plus all events in seq order using apply, and
  compare it with the one in the world_state table. Exits 0 if they match, 1 if not (prints the mismatching field
  names, not the values), 2 if there is no such playthrough.
- `voice off|on|status` (B-14): global voice switch (the circuit breaker in backend-design 5.3). Once off, the gateway
  picks it up within 30 seconds and every new session is text mode (`degraded { reason: "service" }`).

`uv run zoujin-admin`：運用向けのコマンド（B-0 第 3・8 項）。`DATABASE_URL` にだけ接続し、
クラウドサービスには一切触れない。

- `invite create [--count N]`：招待コードを生成する。平文はこの 1 回だけ表示し、DB にはハッシュだけを保存する。
- `replay <playthroughId>`：W-1 の initial_state に全イベントを seq 順に apply して SimState を再構築し、
  world_state テーブルのものと比べる。一致なら 0、不一致なら 1（不一致のフィールド名を表示し、値は表示しない）、
  そのプレイがなければ 2 で終了する。
- `voice off|on|status`（B-14）：全体の音声スイッチ（backend-design 5.3 のサーキットブレーカー）。
  オフにするとゲートウェイが 30 秒以内に読み取り、新しいセッションはすべてテキストモード
  （`degraded { reason: "service" }`）になる。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from zoujin_backend import budget
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
    """Top-level field names that differ (empty when they match); None if there is no such playthrough or it has not
    started yet.

    一致しないトップレベルのフィールド名（一致すれば空）。そのプレイがない、またはまだ開始していなければ None。
    """
    async with engine.connect() as c:
        pt = await store.playthrough(c, pid)
        cached = await store.sim_state(c, pid)
        if pt is None or cached is None:
            return None
        book = library.version(pt["world_model_version"])
        log = await store.event_log(c, pid, book.version)
    rebuilt = store.replay(book, pt["role_id"], log)
    return diff(dict(rebuilt), dict(cached))


async def voice_switch(engine: AsyncEngine, action: str) -> bool:
    """Change (off / on) or just read (status) the global voice switch; returns whether it is on now.

    全体の音声スイッチを変更（off / on）または確認だけ（status）し、現在オンかどうかを返す。
    """
    async with engine.begin() as c:
        if action != "status":
            await budget.set_voice_enabled(c, action == "on")
        return await budget.voice_enabled(c)


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
        if args.cmd == "voice":
            print("Voice / 音声: " + ("on / オン" if await voice_switch(engine, args.action) else "off / オフ"))
            return 0
        library = Library(settings.worlds, settings.scenes, settings.world, settings.released_worlds)
        fields = await replay(engine, library, args.playthrough_id)
        if fields is None:
            print(
                "No such playthrough, or its start has not finished / "
                f"そのプレイがない、または開始処理が終わっていない: {args.playthrough_id}",
                file=sys.stderr,
            )
            return EXIT_NOT_FOUND
        if fields:
            print(f"Mismatch / 不一致: {', '.join(fields)}", file=sys.stderr)
            return EXIT_MISMATCH
        print("Match / 一致")
        return 0
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="zoujin-admin", description="Operations commands (B-0) / 運用コマンド（B-0）")
    sub = p.add_subparsers(dest="cmd", required=True)
    inv = sub.add_parser("invite", help="Invite codes / 招待コード")
    inv_sub = inv.add_subparsers(dest="action", required=True)
    create = inv_sub.add_parser(
        "create",
        help="Generate invite codes; the plaintext is printed only this once / "
        "招待コードを生成する。平文はこの 1 回だけ表示する",
    )
    create.add_argument("--count", type=int, default=1)
    rp = sub.add_parser(
        "replay",
        help="Rebuild world state from events and compare with the cache / "
        "イベントから世界状態を再構築し、キャッシュと比べる",
    )
    rp.add_argument("playthrough_id")
    vo = sub.add_parser("voice", help="Global voice switch (B-14) / 全体の音声スイッチ（B-14）")
    vo.add_argument("action", choices=("off", "on", "status"))
    args = p.parse_args(argv)
    if args.cmd == "invite" and args.count < 1:
        p.error("--count must be at least 1 / --count は 1 以上")
    sys.exit(asyncio.run(_main(args)))
