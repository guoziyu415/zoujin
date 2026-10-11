#!/usr/bin/env python3
"""受密码保护的本机开发预览；不读部署配置、不访问云端、不种入虚构回忆。

在仓库根目录运行：uv run python infra/deploy/local-preview.py
凭证只写到本机 0600 文件；Ctrl-C 同时关闭网关和假模型叙事者，保留独立预览数据。
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import packs
import psycopg
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy.ext.asyncio import create_async_engine
from zoujin_backend.admin import create_invites
from zoujin_backend.config import async_url

ROOT = Path(__file__).resolve().parents[2]
STATE = Path.home() / ".zoujin" / "local-previews" / "h-1"
DATABASE = "zoujin_home_preview"
DB_URL = f"postgresql://zoujin:zoujin@127.0.0.1:5432/{DATABASE}"


async def invite() -> str:
    engine = create_async_engine(async_url(DB_URL))
    try:
        return (await create_invites(engine, 1))[0]
    finally:
        await engine.dispose()


def prepare() -> dict[str, Any]:
    # 固定本机地址、独立库名，完全不使用调用者的 DATABASE_URL。
    with psycopg.connect("postgresql://zoujin:zoujin@127.0.0.1:5432/postgres", autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DATABASE,)).fetchone():
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE)))
    cfg = Config(str(ROOT / "services/backend/alembic.ini"))
    cfg.attributes.update(url=DB_URL, configure_logger=False)
    command.upgrade(cfg, "head")
    path = STATE / "credentials.json"
    if path.exists():
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as source:
            os.fchmod(source.fileno(), 0o600)
            credentials = json.load(source)
        if (
            not isinstance(credentials, dict)
            or credentials.get("database") != DATABASE
            or len(credentials.get("password", "")) < 16
        ):
            raise ValueError("本机预览凭证文件不符合格式；请人工检查，不会覆盖")
        return dict(credentials)
    credentials = {
        "kind": "local-development-preview-fake-models",
        "database": DATABASE,
        "password": secrets.token_urlsafe(32),
        "inviteCode": asyncio.run(invite()),
    }
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as dest:
        json.dump(credentials, dest, ensure_ascii=False, indent=2)
        dest.write("\n")
    return credentials


def unused(port: int) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))


def wait_ready(child: subprocess.Popen[bytes], url: str) -> None:
    until = time.monotonic() + 30
    with httpx.Client(timeout=1) as client:
        while time.monotonic() < until:
            if child.poll() is not None:
                raise RuntimeError("预览进程启动失败，详情见本机私有日志")
            try:
                if client.get(url + "/healthz").status_code == 204:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.2)
    raise RuntimeError("预览服务未在 30 秒内就绪，详情见本机私有日志")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--narrator-port", type=int, default=8092)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.port == args.narrator_port or not all(1024 <= p <= 65535 for p in (args.port, args.narrator_port)):
        parser.error("两个端口须不同，且均在 1024 至 65535 之间")
    if not (ROOT / "apps/web/dist/index.html").is_file():
        parser.error("缺少 apps/web/dist，请先构建最终前端")
    os.umask(0o077)
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE.chmod(0o700)
    # 文件锁持续到进程退出，避免并行预览互相复用端口、生成重复邀请码。
    with (STATE / "preview.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("这个本机预览已在运行")
        credentials = prepare()
        print(f"开发预览凭证已就绪（仅本机）：{STATE / 'credentials.json'}", flush=True)
        if args.prepare_only:
            return
        pack_root = STATE / "packs"
        problems = packs.scenes(ROOT, ROOT, pack_root)
        if problems:
            raise RuntimeError(f"本机场景包尚未齐备或清单不匹配：{problems}")
        unused(args.port)
        unused(args.narrator_port)
        env = {key: value for key, value in os.environ.items() if not key.startswith("ZJ_") and key != "DATABASE_URL"}
        env.update(
            DATABASE_URL=DB_URL,
            ZJ_MODEL="fake",
            ZJ_LIVE="fake",
            ZJ_DEV="1",  # 仅回环 HTTP 的 cookie 不带 Secure；显式密码仍强制整站门禁。
            ZJ_SITE_PASSWORD=credentials["password"],
            ZJ_WEB_DIST=str(ROOT / "apps/web/dist"),
            ZJ_SCENE_PACKS=str(pack_root / "scenes"),
            ZJ_NARRATOR_URL=f"http://127.0.0.1:{args.narrator_port}",
        )
        children: list[subprocess.Popen[bytes]] = []

        def stop(_signum: int, _frame: object) -> None:
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, stop)
        try:
            for service, port in (("narrator", args.narrator_port), ("gateway", args.port)):
                with (STATE / f"{service}.log").open("ab") as logfile:
                    child = subprocess.Popen(
                        [
                            sys.executable,
                            "-c",
                            f"from zoujin_backend.{service}.app import main; main()",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(port),
                        ],
                        cwd=ROOT,
                        env=env,
                        stdout=logfile,
                        stderr=subprocess.STDOUT,
                    )
                children.append(child)
                wait_ready(child, f"http://127.0.0.1:{port}")
            url = f"http://127.0.0.1:{args.port}"
            with httpx.Client() as client:
                response = client.get(url + "/v1/books")
                if response.status_code != 401 or response.headers.get("x-site-access") != "required":
                    raise RuntimeError("匿名密码门禁检查失败，停止预览")
            print(f"本机开发预览：{url}（假模型、独立数据库、仅本地实际游玩历史；Ctrl-C 停止）", flush=True)
            while all(child.poll() is None for child in children):
                time.sleep(0.5)
            raise RuntimeError("预览进程已退出，详情见本机私有日志")
        except KeyboardInterrupt:
            pass
        finally:
            for child in children:
                if child.poll() is None:
                    child.terminate()
            for child in children:
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


if __name__ == "__main__":
    main()
