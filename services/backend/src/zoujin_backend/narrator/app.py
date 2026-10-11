"""叙事者服务（`zoujin-narrator`）：只有网关调的内部接口，形状按以后 Cloud Run 服务间调用的样子（B-0 第 7 条第 7 步）。

`POST /internal/v1/playthroughs/{pid}/run`：把这一局排着的任务按顺序做完，回 `{"processed": n}`。别的进程正在做
这一局时直接回 0（那边做完会接着取）。调用方的身份校验（OIDC）是部署时的事：开发开关打开时不查；关着时 B-0 一律
回 401，免得没配好就对外开着。
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import create_async_engine
from zoujin_backend import logs
from zoujin_backend.config import Settings
from zoujin_backend.models.text import text_model
from zoujin_backend.narrator.core import Narrator
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.world import Library

log = logging.getLogger("zoujin.narrator")


def build(settings: Settings) -> Narrator:
    engine = create_async_engine(settings.database_url, pool_size=5)
    return Narrator(
        engine=engine,
        library=Library(settings.worlds, settings.scenes, settings.world),
        text=text_model(settings.model, fake_rules=settings.fake_text, replays=settings.replays, settings=settings),
        schemas=SchemaBook(settings.schemas),
        deadlines=settings.deadlines,
        on_rate_limit="degrade",  # 服务玩家：429、529 不停服，按时限的规则处理（B-8）
    )


def create_app(settings: Settings, narrator: Narrator | None = None) -> FastAPI:
    n = narrator or build(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await n.engine.dispose()

    app = FastAPI(title="zoujin narrator", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.narrator = n

    @app.get("/healthz")
    async def healthz() -> Response:
        return Response(status_code=204)

    @app.post("/internal/v1/playthroughs/{pid}/run")
    async def run(request: Request, pid: str) -> Response:
        if not settings.dev:
            log.warning("没有开发开关，调用方的身份校验（OIDC）还没做，拒绝")
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        done = await n.run(pid)
        return JSONResponse({"processed": len(done)})

    return app


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="zoujin-narrator", description="叙事者（B-0）：只给网关调")
    p.add_argument("--host", default="127.0.0.1", help="默认只听本机；容器里用 0.0.0.0")
    p.add_argument("--port", type=int, default=8002)
    p.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])
    args = p.parse_args(argv)
    settings = Settings.from_env()
    logs.setup(args.log_level, dev=settings.dev)
    uvicorn.run(create_app(settings), host=args.host, port=args.port, log_level=args.log_level, log_config=None)
