"""H-1：验证私密门禁包住所有内容，猜密码、伪造/过期票、WS 跨站、漏配生产都不能漏出内容。"""

from __future__ import annotations

import pytest
from starlette.responses import Response
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send
from starlette.websockets import WebSocketDisconnect
from zoujin_backend.gateway import site_access as gate

PASSWORD = "local-test-password-only"


async def private_app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] == "lifespan":
        while True:
            msg = await receive()
            kind = msg["type"].removeprefix("lifespan.")
            await send({"type": f"lifespan.{kind}.complete"})
            if kind == "shutdown":
                return
    elif scope["type"] == "websocket":
        await receive()
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.send", "text": "private"})
        await send({"type": "websocket.close", "code": 1000})
    else:
        await Response("private", headers={"Cache-Control": "public, max-age=31536000"})(scope, receive, send)


def test_pages_assets_api_and_websockets_are_blocked_before_password() -> None:
    with TestClient(gate.SiteAccess(private_app, password=PASSWORD, dev=False), base_url="https://testserver") as c:
        for path in ("/", "/assets/app.js", "/scenes/hash/cast/hero.glb", "/assets/voice/book/a.m4a", "/v1/books"):
            r = c.get(path)
            assert r.status_code == 401 and r.headers["x-site-access"] == "required"
            assert "private" not in r.text and "no-store" in r.headers["cache-control"]
        r = c.get("/", headers={"Accept": "text/html"})
        assert r.url.path == gate.PATH and "アクセスパスワード" in r.text
        assert "/assets/" not in r.text and "src=" not in r.text
        assert c.get("/healthz").status_code == 204
        with pytest.raises(WebSocketDisconnect) as e, c.websocket_connect("/v1/playthroughs/id/live"):
            pass
        assert e.value.code == 4401


def test_valid_password_cookie_and_all_private_responses_are_not_cacheable() -> None:
    with TestClient(gate.SiteAccess(private_app, password=PASSWORD, dev=False), base_url="https://testserver") as c:
        r = c.post(
            gate.PATH, data={"password": PASSWORD}, headers={"Origin": "https://testserver"}, follow_redirects=False
        )
        assert r.status_code == 303 and r.headers["location"] == "/"
        cookie = r.headers["set-cookie"]
        assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
        assert PASSWORD not in cookie and "storage" in r.headers["clear-site-data"]
        for path in ("/", "/assets/app.js", "/scenes/hash/cast/hero.glb", "/v1/library"):
            r = c.get(path)
            assert r.text == "private" and r.headers["cache-control"] == "private, no-store"
            assert r.headers["vary"] == "Cookie"
        with c.websocket_connect("wss://testserver/live", headers={"Origin": "https://testserver"}) as ws:
            assert ws.receive_text() == "private"
        with (
            pytest.raises(WebSocketDisconnect),
            c.websocket_connect("wss://testserver/live", headers={"Origin": "https://other.test"}),
        ):
            pass


def test_password_guessing_wrong_origin_and_oversized_body_are_rejected() -> None:
    with TestClient(gate.SiteAccess(private_app, password=PASSWORD, dev=False), base_url="https://testserver") as c:
        assert c.post(gate.PATH, data={"password": PASSWORD}).status_code == 403
        h = {"Origin": "https://testserver"}
        assert c.post(gate.PATH, data={"password": "a" * 5000}, headers=h).status_code == 413
        for _ in range(gate.MAX_ATTEMPTS - 1):
            r = c.post(gate.PATH, data={"password": "wrong"}, headers=h)
            assert r.status_code == 401 and "set-cookie" not in r.headers
        r = c.post(gate.PATH, data={"password": PASSWORD}, headers=h)
        assert r.status_code == 429 and "retry-after" in r.headers


def test_production_missing_password_fails_closed_and_tokens_expire(monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(gate.SiteAccess(private_app, password=None, dev=False)) as c:
        assert c.get("/").status_code == 503 and c.get("/v1/books").status_code == 503
    local = gate.SiteAccess(private_app, password=None, dev=True)
    with TestClient(local) as c:
        assert c.get("/").text == "private"
    locked = gate.SiteAccess(private_app, password=PASSWORD, dev=False)
    token = locked.issue()
    assert locked.valid(token) and not locked.valid(token + "x")
    assert not gate.SiteAccess(private_app, password=PASSWORD + "changed", dev=False).valid(token)
    monkeypatch.setattr("zoujin_backend.gateway.site_access.time.time", lambda: float(token.split(".")[0]) + 1)
    assert not locked.valid(token)
