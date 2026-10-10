"""跨站防护（api-contract 第 0 节）：会改数据的 REST 和 WebSocket 握手都查 Origin。"""

from __future__ import annotations

from collections.abc import Mapping

from starlette.requests import Request

SCHEMES = {"ws": "http", "wss": "https"}


def origin_allowed(headers: Mapping[str, str], scheme: str, extra: tuple[str, ...]) -> bool:
    """同源（Origin 等于这次请求的 scheme://Host），或在 extra（mock 的 --allow-origin、网关的配置）里。
    没有 Origin 不放行。"""
    origin = headers.get("origin")
    if not origin:
        return False
    host = headers.get("host", "")
    own = f"{SCHEMES.get(scheme, scheme)}://{host}"
    return origin == own or origin in extra


def csrf_problem(request: Request, extra: tuple[str, ...]) -> str | None:
    """会改数据的 REST（POST、DELETE）：内容类型不是 JSON、或 Origin 不对时，说是哪一条（只写日志，不回给前端）。"""
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        return "Content-Type 不是 application/json"
    if not request.headers.get("origin"):
        return "没有 Origin"
    if not origin_allowed(request.headers, request.url.scheme, extra):
        return "Origin 不对"
    return None
