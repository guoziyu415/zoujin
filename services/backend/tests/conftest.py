"""Shared pieces for tests that need PostgreSQL (`db` marker; without DATABASE_URL the root conftest.py skips them).

- `alembic upgrade head` runs once at the start of the session; every test starts by emptying all tables.
- `Env`: test configuration (fake model, dev switch, fake Live without waiting) and a few DB-writing shorthands. Each
  `asyncio.run` uses its own connection (NullPool), never reused across event loops.

PostgreSQL が必要なテストの共有部品（`db` マーク。DATABASE_URL がなければルートの conftest.py がスキップさせる）。

- セッションの最初に `alembic upgrade head` を 1 回実行し、各テストの最初に全テーブルを空にする。
- `Env`：テスト用の設定（偽モデル、開発スイッチ、待たない偽 Live）と、
  DB に書くためのいくつかの省略形。`asyncio.run` ごとに専用の接続（NullPool）を使い、
  イベントループをまたいで再利用しない。
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from typing import Any

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from zoujin_backend.config import DEFAULT_WORLD, REPO, Settings, async_url
from zoujin_backend.db import store
from zoujin_backend.db.tables import metadata, users
from zoujin_backend.ids import IdGen
from zoujin_backend.models.text import TextModel, text_model
from zoujin_backend.narrator.core import Narrator
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.world import Book, Library

ALEMBIC_INI = REPO / "services" / "backend" / "alembic.ini"
SCHEMAS = SchemaBook(REPO / "packages" / "contracts" / "schemas")
LIBRARY = Library(REPO / "worlds", REPO / "assets" / "scenes", DEFAULT_WORLD)
BOOK: Book = LIBRARY.book("hashire-merosu")  # type: ignore[assignment]
OLD = "char.old-man"
# fixtures/fake-text/b0-minimal.json recognises 「牧人」 / fixtures/fake-text/b0-minimal.json は「牧人」に反応する
PLAYER_LINE = "さっき、村の牧人だという若い男とすれ違いました。"


def plain_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("No DATABASE_URL / DATABASE_URL がない")
    return url


def alembic_config(url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["url"] = url
    cfg.attributes["configure_logger"] = False  # Leave pytest's logging setup alone / pytest のログ設定に触れない
    return cfg


@pytest.fixture(scope="session")
def migrated() -> str:
    url = plain_url()
    command.upgrade(alembic_config(url), "head")
    return url


def truncate(url: str) -> None:
    names = ", ".join(t.name for t in metadata.sorted_tables)
    with psycopg.connect(url, autocommit=True) as c:
        c.execute(f"TRUNCATE {names} CASCADE")


@dataclass
class Env:
    url: str
    settings: Settings
    ids: IdGen = field(default_factory=IdGen)

    def engine(self) -> AsyncEngine:
        return create_async_engine(self.settings.database_url, poolclass=NullPool)

    def text(self, settings: Settings | None = None) -> TextModel:
        s = settings or self.settings
        return text_model(s.model, fake_rules=s.fake_text, replays=s.replays)

    def narrator(self, engine: AsyncEngine, **kw: Any) -> Narrator:
        return Narrator(engine=engine, library=LIBRARY, text=self.text(), schemas=SCHEMAS, ids=self.ids, **kw)

    async def user(self, engine: AsyncEngine) -> str:
        async with engine.begin() as c:
            user_id = self.ids.new("usr")
            await c.execute(insert(users).values(user_id=user_id))
        return user_id

    async def opened(self, engine: AsyncEngine, role: str = "role.traveler") -> str:
        """Start a playthrough with a new account; the narrator finishes the opening.

        新しいアカウントでプレイを開始し、ナレーターが開始処理を終える。
        """
        user_id = await self.user(engine)
        async with engine.begin() as c:
            pid = await store.create_playthrough(c, self.ids, user_id=user_id, book=BOOK, role_id=role)
        await self.narrator(engine).run(pid)
        return pid

    async def talk(
        self, engine: AsyncEngine, pid: str, text: str = PLAYER_LINE, character: str = OLD, reply: str = "……そうか。"
    ) -> str:
        """Queue one text conversation turn (original words + task) without calling the narrator.

        テキストの会話を 1 ターン（発話の原文 + タスク）キューに入れ、ナレーターは呼ばない。
        """
        async with engine.begin() as c:
            st = await store.sim_state(c, pid)
            t = st["t"] if st is not None else 0
            turn_id = await store.enqueue(c, self.ids, pid, kind="talk", input_mode="text", character=character)
            await store.add_utterance(c, self.ids, pid, turn_id, speaker="player", text=text, t=t)
            await store.add_utterance(c, self.ids, pid, turn_id, speaker=character, text=reply, t=t, source="live")
        return turn_id


@pytest.fixture
def env(migrated: str) -> Iterator[Env]:
    truncate(migrated)
    settings = replace(
        Settings(database_url=async_url(migrated)),
        dev=True,
        speed=0.0,
        allow_origins=(),
    )
    yield Env(migrated, settings)
