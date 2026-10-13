"""私密预览的最外层访问门禁。包住 HTTP/WS、前端代码、场景和音频，邀请码仍负责内层账号隔离。

生产没有密码时关闭访问，只有显式 dev 模式可不设。密码不进入响应、日志、URL 或数据库。
通行 cookie 只包含随机 nonce、到期时间和 HMAC；换密码立即使全部旧票失效。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import OrderedDict
from http.cookies import SimpleCookie
from urllib.parse import parse_qs

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from zoujin_backend.config import ConfigError
from zoujin_backend.origin import origin_allowed

COOKIE = "zj_site_access"
TTL = 12 * 60 * 60
WINDOW = 15 * 60
MAX_ATTEMPTS = 10
PATH = "/site-access"
NO_STORE = {"Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow, noarchive"}


def page(error: bool = False) -> str:
    message = (
        "パスワードが違います。しばらくしてから、もう一度お試しください。"
        if error
        else "招待された方だけが入れる場所です。"
    )
    return f"""<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>非公開のプレビュー</title><style>
*{{box-sizing:border-box}}body{{margin:0;min-height:100dvh;display:grid;place-items:center;background:#1a1916;
color:#f2e9d5;font:16px/1.7 Georgia,serif;padding:24px}}main{{max-width:390px;width:100%}}
h1{{font-size:28px;font-weight:400}}p{{color:#c1b79f}}label{{display:block;margin-top:24px}}
input,button{{width:100%;padding:14px;border-radius:4px;font:inherit;margin-top:10px}}
input{{border:1px solid #8a795e;background:#25221c;color:#fff}}button{{border:0;background:#dbc39b;color:#211e17}}
</style><main><h1>非公開のプレビュー</h1><p role="status">{message}</p>
<form method="post" action="{PATH}"><label for="password">アクセスパスワード</label>
<input id="password" name="password" type="password" autocomplete="current-password" required maxlength="512">
<button type="submit">入る</button></form></main></html>"""


class SiteAccess:
    def __init__(self, app: ASGIApp, *, password: str | None, dev: bool) -> None:
        if password is not None and len(password) < 16:
            raise ConfigError("ZJ_SITE_PASSWORD は 16 文字以上必要です（値は表示しません）")
        self.app, self.dev = app, dev
        self.enabled = password is not None or not dev
        self.key = hashlib.sha256(password.encode()).digest() if password is not None else None
        self.attempts: OrderedDict[str, tuple[float, int]] = OrderedDict()

    def issue(self) -> str:
        assert self.key is not None
        body = f"{int(time.time()) + TTL}.{secrets.token_hex(16)}"
        return f"{body}.{hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()}"

    def valid(self, token: str) -> bool:
        if self.key is None or len(token) > 256:
            return False
        try:
            expires, nonce, signature = token.split(".")
            until = int(expires)
        except (ValueError, TypeError):
            return False
        body = f"{expires}.{nonce}"
        expected = hmac.new(self.key, body.encode(), hashlib.sha256).hexdigest()
        return time.time() < until <= time.time() + TTL and hmac.compare_digest(expected.encode(), signature.encode())

    def limited(self, scope: Scope) -> bool:
        # 只信 ASGI 已验证的 client，不信随意伪造的 X-Forwarded-For。进程内有界；部署仍应限制最大实例数。
        client = str((scope.get("client") or ("unknown",))[0])
        now = time.monotonic()
        start, count = self.attempts.get(client, (now, 0))
        if now - start >= WINDOW:
            start, count = now, 0
        self.attempts[client] = (start, count + 1)
        self.attempts.move_to_end(client)
        while len(self.attempts) > 4096:
            self.attempts.popitem(last=False)
        return count >= MAX_ATTEMPTS

    async def unlock(self, scope: Scope, receive: Receive) -> Response:
        headers = Headers(scope=scope)
        if not origin_allowed(headers, scope["scheme"], ()):
            return Response(status_code=403, headers=NO_STORE)
        if self.limited(scope):
            return HTMLResponse(page(True), status_code=429, headers={**NO_STORE, "Retry-After": str(WINDOW)})
        if headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
            return Response(status_code=400, headers=NO_STORE)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return Response(status_code=400, headers=NO_STORE)
            body.extend(message.get("body", b""))
            if len(body) > 4096:
                return Response(status_code=413, headers=NO_STORE)
            if not message.get("more_body"):
                break
        try:
            supplied = parse_qs(body.decode(), max_num_fields=2).get("password", [""])[0]
        except (UnicodeDecodeError, ValueError):
            supplied = ""
        if self.key is None or not hmac.compare_digest(hashlib.sha256(supplied.encode()).digest(), self.key):
            return HTMLResponse(page(True), status_code=401, headers=NO_STORE)
        response = RedirectResponse("/", status_code=303, headers=NO_STORE)
        response.set_cookie(COOKIE, self.issue(), max_age=TTL, httponly=True, secure=not self.dev, samesite="strict")
        # 清掉以前公开版本可能留下的浏览器缓存/SW，原邀请码会话不清除。
        response.headers["Clear-Site-Data"] = '"cache", "storage"'
        return response

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not self.enabled or scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        is_http = scope["type"] == "http"
        # Cloud Run reserves some paths ending in z; /health is the cloud probe.
        if is_http and scope["path"] in ("/health", "/healthz") and scope["method"] in ("GET", "HEAD"):
            await Response(status_code=204, headers=NO_STORE)(scope, receive, send)
            return
        headers = Headers(scope=scope)
        cookie = SimpleCookie()
        try:
            cookie.load(headers.get("cookie", ""))
            token = cookie[COOKIE].value if COOKIE in cookie else ""
        except Exception:
            token = ""
        allowed = self.valid(token)
        if not is_http:
            if not allowed or not origin_allowed(headers, scope["scheme"], ()):
                await send({"type": "websocket.close", "code": 4401})
                return
        else:
            if self.key is None:
                await Response("Private preview unavailable", status_code=503, headers=NO_STORE)(scope, receive, send)
                return
            if scope["path"] == PATH:
                if scope["method"] == "POST":
                    response = await self.unlock(scope, receive)
                elif scope["method"] in ("GET", "HEAD"):
                    response = HTMLResponse(page(), headers=NO_STORE)
                else:
                    response = Response(status_code=405, headers=NO_STORE)
                await response(scope, receive, send)
                return
            if not allowed:
                gate_headers = {**NO_STORE, "X-Site-Access": "required", "Clear-Site-Data": '"cache", "storage"'}
                if "text/html" in headers.get("accept", "") and scope["method"] in ("GET", "HEAD"):
                    response = RedirectResponse(PATH, status_code=303, headers=gate_headers)
                else:
                    response = JSONResponse(
                        {
                            "error": {
                                "code": "unauthenticated",
                                "message": "アクセスパスワードを入力してください。",
                                "retryable": False,
                                "retryAfterSeconds": None,
                            }
                        },
                        status_code=401,
                        headers=gate_headers,
                    )
                await response(scope, receive, send)
                return

        async def private_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                out = MutableHeaders(scope=message)
                for key, value in NO_STORE.items():
                    out[key] = value
                out["Vary"] = "Cookie"
                out["Referrer-Policy"] = "no-referrer"
            await send(message)

        await self.app(scope, receive, private_send)
