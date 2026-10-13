"""Cross-site protection (api-contract section 0): data-changing REST calls and WebSocket handshakes both check Origin.

クロスサイト対策（api-contract 第 0 節）：データを変更する REST と WebSocket ハンドシェイクは、
どちらも Origin を確認する。
"""

from __future__ import annotations

from collections.abc import Mapping

from starlette.requests import Request

SCHEMES = {"ws": "http", "wss": "https"}


def origin_allowed(headers: Mapping[str, str], scheme: str, extra: tuple[str, ...]) -> bool:
    """Same origin (Origin equals this request's scheme://Host), or listed in extra (mock's --allow-origin, the
    gateway's config). A missing Origin is not allowed.

    同一オリジン（Origin がこのリクエストの scheme://Host と等しい）か、extra（mock の --allow-origin、
    ゲートウェイの設定）に含まれていれば通す。Origin がなければ通さない。
    """
    origin = headers.get("origin")
    if not origin:
        return False
    host = headers.get("host", "")
    own = f"{SCHEMES.get(scheme, scheme)}://{host}"
    return origin == own or origin in extra


def csrf_problem(request: Request, extra: tuple[str, ...]) -> str | None:
    """Data-changing REST (POST, DELETE): when the content type is not JSON or the Origin is wrong, say which (logged
    only, never returned to the frontend).

    データを変更する REST（POST、DELETE）：コンテンツタイプが JSON でない、または Origin が正しくないとき、
    どれに当たるかを返す（ログにだけ書き、フロントエンドには返さない）。
    """
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        return "Content-Type is not application/json / Content-Type が application/json ではない"
    if not request.headers.get("origin"):
        return "No Origin / Origin がない"
    if not origin_allowed(request.headers, request.url.scheme, extra):
        return "Wrong Origin / Origin が正しくない"
    return None
