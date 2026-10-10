"""整个仓库的 pytest 设置：标了 `db` 的测试要真的 PostgreSQL（`DATABASE_URL`），没设就跳过。

CI 里 `lint & test` 任务没有数据库，这些测试跳过；`tests against PostgreSQL` 任务带 PostgreSQL 服务容器跑
`pytest -m db`。本地：`docker compose up -d db`，再按 services/backend/README.md 设 `DATABASE_URL`。
"""

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("DATABASE_URL"):
        return
    skip = pytest.mark.skip(reason="没有 DATABASE_URL（要 PostgreSQL 的测试在 CI 的 db 任务里跑）")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)
