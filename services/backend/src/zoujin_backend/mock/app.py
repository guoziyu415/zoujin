"""把 REST、WebSocket 和控制接口装成一个 ASGI 应用（同源：静态资源以外都在这里）。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from zoujin_backend.mock import rest, ws
from zoujin_backend.mock.core import Config, Mock
from zoujin_backend.origin import origin_allowed


def create_app(config: Config | None = None) -> FastAPI:
    app = FastAPI(title="zoujin mock", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.mock = Mock(config or Config())
    app.include_router(rest.router)
    app.include_router(rest.control)
    app.add_api_websocket_route("/v1/playthroughs/{pid}/live", ws.endpoint)

    @app.exception_handler(rest.Fail)
    async def on_fail(request: Request, exc: rest.Fail) -> Response:
        return rest.fail_response(app.state.mock, exc)

    @app.middleware("http")
    async def csrf(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """会改数据的 REST（POST、DELETE）要 JSON 内容类型和对的 Origin，否则 403（第 0 节）。"""
        m: Mock = app.state.mock
        if request.method in ("POST", "DELETE") and request.url.path.startswith("/v1/"):
            json_type = request.headers.get("content-type", "").split(";")[0].strip() == "application/json"
            if not json_type or not origin_allowed(request.headers, request.url.scheme, m.config.allow_origins):
                return rest.fail_response(m, rest.Fail("forbidden"))
        return await call_next(request)

    return app
