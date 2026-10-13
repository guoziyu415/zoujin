"""Database accounts and privileges for the deploy (B-23), run by deploy.sh through the Cloud SQL proxy on zg's Mac.

    python dbsetup.py roles    create database zoujin (owner zj_owner) and the two app accounts (create if missing,
                               otherwise only update login and password)
    python dbsetup.py grants   after migrations: both app accounts get CRUD on all tables and use of sequences;
                               alembic_version is read-only

Connections and passwords are read only from environment variables and never printed: ZJ_OWNER_URL (zj_owner's
postgresql://… to the postgres database), ZJ_GW_URL, ZJ_NR_URL (the two app accounts' DATABASE_URL, from which the
username and password are taken).

Neither account can create or alter tables (only zj_owner runs migrations). The per-table write privileges in
backend-design 2.1 (the narrator is the only writer) do not match the current code (the gateway's memory deletion
also writes events and world_state), so in the first version both accounts have the same privileges; narrowing them
per table is left to the backend.

デプロイ用のデータベースのアカウントと権限（B-23）。zg の Mac 上で deploy.sh が Cloud SQL プロキシ経由で実行する。

    python dbsetup.py roles    データベース zoujin（所有者 zj_owner）と 2 つのアプリ用アカウントを作成
                               （なければ作成し、あればログインとパスワードだけを変更）
    python dbsetup.py grants   マイグレーション後：2 つのアプリ用アカウントに全テーブルの CRUD とシーケンスの使用を
                               許可する。alembic_version は読み取り専用

接続情報とパスワードは環境変数からだけ読み、出力しない：ZJ_OWNER_URL（zj_owner が postgres データベースに
接続する postgresql://…）、ZJ_GW_URL、ZJ_NR_URL（2 つのアプリ用アカウントの DATABASE_URL。ここから
ユーザー名とパスワードを取る）。

どちらのアカウントもテーブルの作成・変更はできない（マイグレーションは zj_owner だけが実行する）。
backend-design 2.1 のテーブルごとの書き込み権限（ナレーターが唯一の書き手）は現在のコードと合わない
（ゲートウェイの記憶削除も events、world_state に書く）ので、最初の版では 2 つのアカウントの権限を同じにし、
テーブルごとに絞るのはバックエンドに任せる。
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
        sys.exit(
            "The app account's DATABASE_URL has no username or password"
            " / アプリ用アカウントの DATABASE_URL にユーザー名かパスワードがない"
        )
    return unquote(parts.username), unquote(parts.password)


def with_db(url: str, db: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=f"/{db}"))


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"{name} is not set / {name} が未設定")
    return value


def roles(owner_url: str, apps: list[tuple[str, str]]) -> None:
    with psycopg.connect(owner_url, autocommit=True) as c:
        if c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB,)).fetchone() is None:
            c.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB)))
            print(f"Created database {DB} / データベース {DB} を作成")
        for user, password in apps:
            exists = c.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (user,)).fetchone() is not None
            # Cloud SQL's zj_owner is not a superuser, so ALTER with attributes like NOSUPERUSER is refused:
            # attributes are given only at creation, and existing accounts only get login and password updated
            # (setup can be rerun)
            # Cloud SQL の zj_owner はスーパーユーザーではないので、NOSUPERUSER などの属性付きの ALTER は拒否される：
            # 属性は作成時にだけ与え、既存のアカウントはログインとパスワードだけを変更する（setup は再実行できる）
            attrs = "LOGIN PASSWORD {}" if exists else "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}"
            verb = "ALTER" if exists else "CREATE"
            c.execute(sql.SQL(f"{verb} ROLE {{}} {attrs}").format(sql.Identifier(user), sql.Literal(password)))
            done = ("Updated", "変更") if exists else ("Created", "作成")
            print(f"{done[0]} account {user} / アカウント {user} を{done[1]}")
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
        print(
            f"Privileges set for both app accounts ({n[0] if n else 0} tables in public)"
            f" / 2 つのアプリ用アカウントの権限を設定済み（public に {n[0] if n else 0} テーブル）"
        )


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
