"""跨站防护（api-contract 第 0 节）：会改数据的 REST 和 WebSocket 握手都查 Origin。"""

from __future__ import annotations

from collections.abc import Mapping

SCHEMES = {"ws": "http", "wss": "https"}


def origin_allowed(headers: Mapping[str, str], scheme: str, extra: tuple[str, ...]) -> bool:
    """同源（Origin 等于这次请求的 scheme://Host），或在 --allow-origin 里。没有 Origin 不放行。"""
    origin = headers.get("origin")
    if not origin:
        return False
    host = headers.get("host", "")
    own = f"{SCHEMES.get(scheme, scheme)}://{host}"
    return origin == own or origin in extra
