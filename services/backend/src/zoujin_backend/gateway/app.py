"""把网关装成一个 ASGI 应用，和 `zoujin-gateway` 命令。

- 会改数据的 REST（POST、DELETE）要 JSON 内容类型和对的 Origin，否则 403（第 0 节）；
- 没挂的 `/v1` 接口回第 5 节的 404 not_found；
- 会话续期了就补一个 Set-Cookie（滑动 30 天）；
- 收到 SIGTERM：先给每条连接推 goaway、以 1012 关闭，再停服务（第 4 节）。
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from types import FrameType

import uvicorn
from fastapi import FastAPI, Request, Response
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.exceptions import HTTPException as StarletteHTTPException

from zoujin_backend import logs
from zoujin_backend.config import Settings
from zoujin_backend.gateway import rest, ws
from zoujin_backend.gateway.core import Gateway, HttpNarrator, NarratorClient
from zoujin_backend.gateway.hub import Hub
from zoujin_backend.manifest import generate
from zoujin_backend.models.live import FakeLive
from zoujin_backend.origin import csrf_problem
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.world import Library

log = logging.getLogger("zoujin.gateway")

GOAWAY_MS = 1000  # 前端在这之后重连
SHUTDOWN_GRACE_S = 5  # 停服务前等手上的任务（交轮次、叫叙事者）最多几秒


def build(settings: Settings, narrator: NarratorClient | None = None) -> Gateway:
    """生成 manifest 出错（`ManifestError`，写着是哪个文件、哪个字段）就起不来。"""
    library = Library(settings.worlds, settings.scenes, settings.world)
    schemas = SchemaBook(settings.schemas)
    manifest = generate(
        library.current, schemas, packs=settings.packs, voices=settings.voice_dir, release=settings.release
    )
    return Gateway(
        settings=settings,
        engine=create_async_engine(settings.database_url, pool_size=10),
        library=library,
        schemas=schemas,
        live=FakeLive(settings.fake_voice, speed=settings.speed),
        narrator=narrator or HttpNarrator(settings.narrator_url),
        manifest=manifest,
    )


def create_app(settings: Settings, gw: Gateway | None = None) -> FastAPI:
    gw = gw or build(settings)
    hub = Hub(gw)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        hub.start()
        await asyncio.wait_for(hub.listening.wait(), timeout=10)
        try:
            yield
        finally:
            await hub.stop()
            if gw.tasks:  # 排空：断线时交上去的轮次、叫叙事者的请求，等一会儿再停
                await asyncio.wait(set(gw.tasks), timeout=SHUTDOWN_GRACE_S)
            for task in list(gw.tasks):
                task.cancel()
            if isinstance(gw.narrator, HttpNarrator):
                await gw.narrator.close()
            await gw.engine.dispose()

    app = FastAPI(title="zoujin gateway", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.gw = gw
    app.state.hub = hub
    app.include_router(rest.router)
    app.add_api_websocket_route("/v1/playthroughs/{pid}/live", ws.endpoint)

    @app.exception_handler(rest.Fail)
    async def on_fail(request: Request, exc: rest.Fail) -> Response:
        return rest.fail_response(gw, exc)

    @app.exception_handler(Exception)
    async def on_error(request: Request, exc: Exception) -> Response:
        """没接住的异常也回第 5 节的 JSON（不回 uvicorn 的纯文本 500）。"""
        log.error("%s %s 出错", request.method, request.url.path, exc_info=exc)
        return rest.fail_response(gw, rest.Fail("internal"))

    @app.exception_handler(StarletteHTTPException)
    async def on_http(request: Request, exc: StarletteHTTPException) -> Response:
        """B-0 没挂的接口：第 5 节的形状，404 not_found（不另加「未实现」）。"""
        if exc.status_code in (404, 405):
            return rest.fail_response(gw, rest.Fail("not_found"))
        return rest.fail_response(gw, rest.Fail("internal"))

    @app.middleware("http")
    async def guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.method in ("POST", "DELETE") and request.url.path.startswith("/v1/"):
            why = csrf_problem(request, settings.allow_origins)
            if why is not None:
                log.info("%s %s 回 403：%s", request.method, request.url.path, why)
                return rest.fail_response(gw, rest.Fail("forbidden"))
        resp = await call_next(request)
        token = getattr(request.state, "slid_token", None)
        if token is not None and "set-cookie" not in resp.headers:
            rest.set_cookie(gw, resp, token)
        return resp

    return app


class Server(uvicorn.Server):
    """第一次 SIGTERM / SIGINT：推 goaway、以 1012 关掉每条连接，再按 uvicorn 的流程停。第二次照 uvicorn 原样。"""

    def __init__(self, config: uvicorn.Config, gw: Gateway) -> None:
        super().__init__(config)
        self.gw = gw
        self.loop: asyncio.AbstractEventLoop | None = None

    async def serve(self, sockets: list[object] | None = None) -> None:  # type: ignore[override]
        self.loop = asyncio.get_running_loop()
        await super().serve(sockets)  # type: ignore[arg-type]

    def handle_exit(self, sig: int, frame: FrameType | None) -> None:
        if self.gw.draining or self.loop is None:
            super().handle_exit(sig, frame)
            return
        self.gw.draining = True
        self.loop.call_soon_threadsafe(lambda: self.gw.spawn(self._drain(sig, frame)))

    async def _drain(self, sig: int, frame: FrameType | None) -> None:
        try:
            await self.gw.goaway(GOAWAY_MS)
        finally:
            super().handle_exit(sig, frame)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="zoujin-gateway", description="网关（B-0）：REST 和 WebSocket")
    p.add_argument("--host", default="127.0.0.1", help="默认只听本机；容器里用 0.0.0.0")
    p.add_argument("--port", type=int, default=8001)
    p.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])
    args = p.parse_args(argv)
    settings = Settings.from_env()
    logs.setup(args.log_level, dev=settings.dev)
    gw = build(settings)
    config = uvicorn.Config(
        create_app(settings, gw),
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        log_config=None,
        ws="websockets-sansio",
    )
    Server(config, gw).run()
