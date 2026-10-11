"""B-23：部署时网关同源发前端和场景包、叙事者的服务间身份（`ZJ_NARRATOR_AUTH=iam`）。不联网。"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Literal

import httpx
import pytest
from fastapi.testclient import TestClient
from zoujin_backend.config import ConfigError, Settings
from zoujin_backend.gateway import app as gateway_app
from zoujin_backend.gateway.core import HttpNarrator, IdToken
from zoujin_backend.gateway.web import IMMUTABLE, NO_CACHE
from zoujin_backend.narrator import app as narrator_app

from .conftest import Env
from .test_manifest import SLICE, packs


def dist(tmp: Path) -> Path:
    d = tmp / "dist"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_text("<!doctype html><title>t</title>", encoding="utf-8")
    (d / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (d / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (tmp / "secret.txt").write_text("no", encoding="utf-8")
    return d


def test_env_parsing(tmp_path: Path) -> None:
    base = {"DATABASE_URL": "postgresql://x"}
    s = Settings.from_env(base)
    assert s.web_dist is None and s.narrator_auth == "none"
    s = Settings.from_env({**base, "ZJ_WEB_DIST": str(tmp_path), "ZJ_NARRATOR_AUTH": "iam"})
    assert s.web_dist == tmp_path and s.narrator_auth == "iam"
    with pytest.raises(ConfigError):
        Settings.from_env({**base, "ZJ_NARRATOR_AUTH": "yes"})
    with pytest.raises(ConfigError):
        Settings.from_env({**base, "ZJ_WEB_DIST": str(tmp_path / "missing")})


def test_gateway_serves_the_web_build_and_scene_packs(env: Env, tmp_path: Path) -> None:
    pk = packs(tmp_path)
    settings = replace(env.settings, dev=True, world=SLICE, scene_packs=pk, web_dist=dist(tmp_path))
    app = gateway_app.create_app(settings)
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200 and r.text.startswith("<!doctype html>")
        assert r.headers["cache-control"] == NO_CACHE and r.headers["x-robots-tag"] == "noindex, nofollow"
        assert c.get("/play/some/route").text == r.text  # 前端自己的路由
        a = c.get("/assets/index-abc123.js")
        assert a.status_code == 200 and a.headers["cache-control"] == IMMUTABLE
        assert a.headers["content-type"].startswith("text/javascript")
        assert c.get("/robots.txt").headers["cache-control"] == NO_CACHE
        for missing in ("/assets/nope.js", "/favicon.ico", "/../secret.txt", "/%2e%2e/secret.txt"):
            assert c.get(missing).status_code == 404, missing
        # API 的 404 照旧是第 5 节的形状，不回页面；接口照旧
        n = c.get("/v1/nothing-here")
        assert n.status_code == 404 and n.json()["error"]["code"] == "not_found"
        assert c.get("/v1/me").status_code == 401
        # 场景包：只发 manifest 引用的版本和目录
        url = app.state.gw.manifest.doc["scenes"][0]["assetUrl"]
        s = c.get(url)
        assert s.status_code == 200 and s.headers["cache-control"] == IMMUTABLE
        assert s.content == (pk / "syracuse-square" / "scene.json").read_bytes()
        version = url.split("/")[2]
        for bad in (
            url.replace(version, "00000000"),
            f"/scenes/{version}/other/scene.json",
            f"/scenes/{version}/syracuse-square/../../secret.txt",
        ):
            assert c.get(bad).status_code == 404, bad


def test_no_web_build_no_pages(env: Env) -> None:
    with TestClient(gateway_app.create_app(replace(env.settings, dev=True))) as c:
        r = c.get("/")
        assert r.status_code == 404 and "x-robots-tag" not in r.headers


def test_narrator_accepts_only_dev_or_iam(env: Env) -> None:
    cases: tuple[tuple[bool, Literal["none", "iam"], int], ...] = (
        (False, "none", 401),
        (False, "iam", 200),
        (True, "none", 200),
    )
    for dev, auth, code in cases:
        settings = replace(env.settings, dev=dev, narrator_auth=auth)
        with TestClient(narrator_app.create_app(settings)) as c:
            assert c.post("/internal/v1/playthroughs/pt_none/run").status_code == code, (dev, auth)


def test_http_narrator_sends_the_id_token() -> None:
    seen: list[str | None] = []
    fetched: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"processed": 2})

    def fetch(audience: str) -> str:
        fetched.append(audience)
        return f"tok-{len(fetched)}"

    async def go() -> None:
        token = IdToken("https://narrator.internal", fetch=fetch)
        n = HttpNarrator("https://narrator.internal", transport=httpx.MockTransport(handler), token=token)
        assert await n.run("pt_1") == 2
        assert await n.run("pt_1") == 2
        token._at -= IdToken.REFRESH_S + 1  # 过了 50 分钟：换新
        await n.run("pt_1")
        await n.close()
        plain = HttpNarrator("http://127.0.0.1:8002", transport=httpx.MockTransport(handler))
        await plain.run("pt_1")
        await plain.close()

    asyncio.run(go())
    assert fetched == ["https://narrator.internal", "https://narrator.internal"]
    assert seen == ["Bearer tok-1", "Bearer tok-1", "Bearer tok-2", None]


def test_real_gateway_password_gate_covers_pages_resources_api_and_socket(env: Env, tmp_path: Path) -> None:
    from starlette.websockets import WebSocketDisconnect
    from zoujin_backend.gateway.site_access import PATH

    from .test_gateway import invite
    from .test_manifest import Direct, voices, world

    password = "local-only-gateway-test-password"
    pk, web = packs(tmp_path), dist(tmp_path)
    (pk / "syracuse-square" / "hero.glb").write_bytes(b"private-model")
    (web / "cast").mkdir()
    (web / "cast" / "hero.glb").write_bytes(b"private-cast")
    settings = replace(
        env.settings,
        dev=False,
        world=SLICE,
        scene_packs=pk,
        web_dist=web,
        voices=voices(tmp_path, world(SLICE)),
        site_password=password,
    )
    narrator = narrator_app.build(settings)
    gw = gateway_app.build(settings, Direct(narrator))
    assert gw.manifest is not None
    scene = gw.manifest.doc["scenes"][0]["assetUrl"]
    model = scene.rsplit("/", 1)[0] + "/hero.glb"
    voice = "/assets/voice/hashire-merosu/" + next(iter(gw.manifest.files))
    paths = ["/", "/assets/index-abc123.js", scene, model, "/cast/hero.glb", voice, "/v1/books"]
    with TestClient(gateway_app.create_app(settings, gw), base_url="https://testserver") as c:
        for target in paths:
            blocked = c.get(target)
            assert blocked.status_code == 401 and blocked.headers["x-site-access"] == "required", target
        assert c.get("/healthz").status_code == 204
        with pytest.raises(WebSocketDisconnect), c.websocket_connect("wss://testserver/v1/playthroughs/unknown/live"):
            pass
        origin = {"Origin": "https://testserver"}
        assert c.post(PATH, data={"password": password}, headers=origin).status_code == 200
        # 站点密码不等于邀请码账号；内层 API 仍然拒绝。
        assert c.get("/v1/books").status_code == 401
        for target in paths[:-1]:
            allowed = c.get(target)
            assert allowed.status_code == 200 and allowed.headers["cache-control"] == "private, no-store", target
        assert c.post("/v1/auth/login", json={"inviteCode": invite(env)}, headers=origin).status_code == 200
        assert c.get("/v1/books").status_code == 200
        made = c.post(
            "/v1/playthroughs",
            json={"bookId": "hashire-merosu", "roleId": "role.traveler"},
            headers={**origin, "Idempotency-Key": "site-gate-create"},
        )
        assert made.status_code == 201
        pid = made.json()["playthroughId"]
        with c.websocket_connect(f"wss://testserver/v1/playthroughs/{pid}/live", headers=origin) as ws:
            ws.send_json({"type": "hello", "lastSeq": 0, "clientVersion": "test"})
            assert ws.receive_json()["type"] == "welcome"
        c.portal.call(narrator.engine.dispose)  # type: ignore[union-attr]
