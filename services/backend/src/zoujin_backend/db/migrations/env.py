"""Alembic entry point: the connection string is read only from DATABASE_URL (sync driver; migrations need no async).

Alembic のエントリーポイント：接続文字列は DATABASE_URL からのみ読む（同期ドライバー。マイグレーションに非同期は不要）。
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from zoujin_backend.config import async_url
from zoujin_backend.db.tables import metadata

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)


def url() -> str:
    given = config.attributes.get("url") or os.environ.get("DATABASE_URL")
    if not given:
        raise RuntimeError("No DATABASE_URL / DATABASE_URL がない")
    return async_url(str(given))


def run_migrations_offline() -> None:
    context.configure(url=url(), target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
