"""部署的数据库账号和权限（B-23），由 deploy.sh 经 Cloud SQL 代理在 zg 的 Mac 上跑。

    python dbsetup.py roles    建库 zoujin（属主 zj_owner）、两个应用账号（没有就建，有就改成这次的密码）
    python dbsetup.py grants   迁移以后：两个应用账号对全部表增删改查、序列能用；alembic_version 只读

连接和密码只从环境变量读，不打印：ZJ_OWNER_URL（zj_owner 连 postgres 库的 postgresql://…）、
ZJ_GW_URL、ZJ_NR_URL（两个应用账号的 DATABASE_URL，从里面取用户名和密码）。

两个账号都不能建表、改表（迁移只由 zj_owner 跑）。backend-design 2.1 按表分的写权限（叙事者是唯一写入方）
现在的代码对不上（网关的删除记忆也写 events、world_state），第一版两个账号权限一样，按表收窄留给后端。
"""

from __future__ import annotations

import os
import sys
from urllib.parse import unquote, urlsplit, urlunsplit

import psycopg
from psycopg import sql

DB = "zoujin"
DML = "SELECT, INSERT, UPDATE, DELETE"


def login(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    if not parts.username or not parts.password:
        sys.exit("应用账号的 DATABASE_URL 里没有用户名或密码")
    return unquote(parts.username), unquote(parts.password)


def with_db(url: str, db: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{db}"))


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"没有 {name}")
    return value


def roles(owner_url: str, apps: list[tuple[str, str]]) -> None:
    with psycopg.connect(owner_url, autocommit=True) as c:
        if c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB,)).fetchone() is None:
            c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB)))
            print(f"建了库 {DB}")
        for user, password in apps:
            exists = c.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,)).fetchone() is not None
            verb = "ALTER" if exists else "CREATE"
            c.execute(
                sql.SQL(verb + " ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}").format(
                    sql.Identifier(user), sql.Literal(password)
                )
            )
            print(f"{'改了' if exists else '建了'}账号 {user}")
    with psycopg.connect(with_db(owner_url, DB), autocommit=True) as c:
        c.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
        for user, _ in apps:
            c.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(DB), sql.Identifier(user)))
            c.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(user)))


def grants(owner_url: str, users: list[str]) -> None:
    with psycopg.connect(with_db(owner_url, DB), autocommit=True) as c:
        for user in users:
            u = sql.Identifier(user)
            c.execute(sql.SQL("GRANT " + DML + " ON ALL TABLES IN SCHEMA public TO {}").format(u))
            c.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(u))
            c.execute(sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT " + DML + " ON TABLES TO {}").format(u))
            seq = "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}"
            c.execute(sql.SQL(seq).format(u))
            if c.execute("SELECT to_regclass('public.alembic_version')").fetchone() != (None,):
                c.execute(sql.SQL("REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM {}").format(u))
        n = c.execute("SELECT count(*) FROM pg_tables WHERE schemaname = 'public'").fetchone()
        print(f"两个应用账号的权限已设（public 下 {n[0] if n else 0} 张表）")


def main(argv: list[str]) -> None:
    if len(argv) != 2 or argv[1] not in ("roles", "grants"):
        sys.exit(__doc__)
    owner = env("ZJ_OWNER_URL")
    apps = [login(env("ZJ_GW_URL")), login(env("ZJ_NR_URL"))]
    if argv[1] == "roles":
        roles(owner, apps)
    else:
        grants(owner, [u for u, _ in apps])


if __name__ == "__main__":
    main(sys.argv)
