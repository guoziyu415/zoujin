"""要 PostgreSQL 的测试共用的东西（`db` 标记；没有 DATABASE_URL 时根目录的 conftest.py 让它们跳过）。

- 整个会话开始时 `alembic upgrade head` 一次；每个测试开头清空全部表。
- `Env`：测试用的配置（假模型、开发开关、假 Live 不等）和几个写库的简写。每个 `asyncio.run` 里用自己的
  连接（NullPool），不跨事件循环复用。
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
PLAYER_LINE = "さっき、村の牧人だという若い男とすれ違いました。"  # fixtures/fake-text/b0-minimal.json 认「牧人」


def plain_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("没有 DATABASE_URL")
    return url


def alembic_config(url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["url"] = url
    cfg.attributes["configure_logger"] = False  # 不动 pytest 的日志设置
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
        """新账号开一局，叙事者做完开局。"""
        user_id = await self.user(engine)
        async with engine.begin() as c:
            pid = await store.create_playthrough(c, self.ids, user_id=user_id, book=BOOK, role_id=role)
        await self.narrator(engine).run(pid)
        return pid

    async def talk(
        self, engine: AsyncEngine, pid: str, text: str = PLAYER_LINE, character: str = OLD, reply: str = "……そうか。"
    ) -> str:
        """排一轮文字对话（原话 + 任务），不叫叙事者。"""
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
