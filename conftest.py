"""Repo-wide pytest setup: tests marked `db` need a real PostgreSQL (`DATABASE_URL`) and are skipped if it is unset.

The `lint & test` CI job has no database, so these tests are skipped; the `tests against PostgreSQL` job runs
`pytest -m db` with a PostgreSQL service container. Locally: `docker compose up -d db`, then set `DATABASE_URL` per services/backend/README.md.

リポジトリ全体の pytest 設定：`db` マークのテストは実際の PostgreSQL（`DATABASE_URL`）が必要で、未設定ならスキップする。

CI の `lint & test` ジョブにはデータベースがないのでこれらのテストはスキップされ、`tests against PostgreSQL` ジョブが PostgreSQL サービスコンテナ付きで
`pytest -m db` を実行する。ローカルでは `docker compose up -d db` のあと、services/backend/README.md に従って `DATABASE_URL` を設定する。
"""

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("DATABASE_URL"):
        return
    skip = pytest.mark.skip(reason="No DATABASE_URL (tests needing PostgreSQL run in the CI db job) / DATABASE_URL がありません（PostgreSQL が必要なテストは CI の db ジョブで実行）")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)
