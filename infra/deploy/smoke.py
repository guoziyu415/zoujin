"""部署后的探测（B-23），由 deploy.sh 在 zg 的 Mac 上跑。地址和邀请码只从环境变量读，不打印。

    python smoke.py smoke   用冒烟专用的邀请码：页面、登录、manifest、开一局（叙事者写开局 = 一次叙事提交，
                            也验了网关调叙事者的身份）、带 Cookie 的 WebSocket 握手过关，最后删掉这一局
    python smoke.py anon    匿名访问被拒：REST 401、WebSocket 握手以 4001 关闭

环境变量：ZJ_SMOKE_URL（https://…，不带结尾的 /）、ZJ_SMOKE_CODE（smoke 用）、ZJ_SMOKE_BEARER（可选：服务还是私有时，
zg 的身份令牌，给 Cloud Run 的 IAM 看；应用自己不读它）。过了退出码 0，不过打印哪一条、退出码 1。
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from typing import Any

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

BOOK = "hashire-merosu"
WS_WAIT_S = 3.0
LOCAL = os.environ.get("ZJ_SMOKE_LOCAL") == "1"  # 只给在本机试这个脚本：允许 http、不查 Secure


class Failed(Exception):
    pass


def expect(ok: bool, what: str) -> None:
    if not ok:
        raise Failed(what)
    print(f"  ✓ {what}")


def ws_url(base: str, pid: str) -> str:
    return base.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + f"/v1/playthroughs/{pid}/live"


async def ws_close_code(url: str, headers: dict[str, str]) -> int | None:
    """连上以后等一会儿：被关了回关闭码，一直开着回 None。握手本身被拒（HTTP 4xx）回 -1。"""
    try:
        async with websockets.connect(url, additional_headers=headers, open_timeout=15) as ws:
            try:
                await asyncio.wait_for(ws.recv(), timeout=WS_WAIT_S)
            except TimeoutError:
                return None
            except ConnectionClosed as e:
                return e.rcvd.code if e.rcvd else -1
            try:  # 收到了消息：服务端没关，再确认一下
                await asyncio.wait_for(ws.wait_closed(), timeout=0.5)
            except TimeoutError:
                return None
            return ws.close_code
    except websockets.InvalidStatus:
        return -1


async def delete(c: httpx.AsyncClient, origin: dict[str, str], pid: str) -> int:
    headers = {**origin, "Content-Type": "application/json", "Idempotency-Key": str(uuid.uuid4())}
    return (await c.delete(f"/v1/playthroughs/{pid}", headers=headers)).status_code


async def anon(base: str, bearer: dict[str, str]) -> None:
    origin = {"Origin": base}
    async with httpx.AsyncClient(base_url=base, timeout=30, headers=bearer) as c:
        for path in (
            "/",
            "/assets/unknown.js",
            "/cast/unknown.glb",
            "/scenes/old/scene/geo.glb",
            "/assets/voice/book/audio.m4a",
            "/v1/books",
        ):
            blocked = await c.get(path)
            expect(
                blocked.status_code == 401 and blocked.headers.get("x-site-access") == "required",
                "匿名页面、资产及目录先通过密码门禁",
            )
        me = await c.get("/v1/me")
        expect(me.status_code == 401, "匿名 GET /v1/me 回 401")
        m = await c.get(f"/v1/books/{BOOK}/manifest")
        expect(m.status_code == 401, "匿名拿 manifest 回 401")
        p = await c.post("/v1/playthroughs", json={}, headers={**origin, "Idempotency-Key": str(uuid.uuid4())})
        expect(p.status_code == 401, "匿名开局回 401")
    code = await ws_close_code(ws_url(base, "pt_00000000000000000000000000"), {**bearer, **origin})
    expect(code in (4001, 4401, -1), f"匿名 WebSocket 握手被拒（关闭码 {code}）")


async def smoke(base: str, bearer: dict[str, str], code: str) -> None:
    origin = {"Origin": base}
    async with httpx.AsyncClient(base_url=base, timeout=60, headers=bearer) as c:
        password = os.environ.get("ZJ_SMOKE_PASSWORD", "")
        expect(bool(password), "已配置站点密码（不输出）")
        unlocked = await c.post("/site-access", data={"password": password}, headers=origin)
        expect(unlocked.status_code == 303, "站点密码通过")
        expect("HttpOnly" in unlocked.headers.get("set-cookie", ""), "通行 Cookie 不对脚本开放")
        health = await c.get("/healthz")
        expect(health.status_code == 204, "健康探测返回空 204")
        page = await c.get("/")
        expect(page.status_code == 200 and "<html" in page.text.lower()[:500], "首页是前端的页面")
        expect(page.headers.get("x-robots-tag", "").startswith("noindex"), "页面不让搜索引擎收")
        login = await c.post("/v1/auth/login", json={"inviteCode": code}, headers=origin)
        expect(login.status_code == 200, f"冒烟邀请码登录（{login.status_code}）")
        cookie = login.headers.get("set-cookie", "")
        secure = "Secure" in cookie or LOCAL
        expect(secure and "HttpOnly" in cookie, "会话 Cookie 带 Secure、HttpOnly")
        me = await c.get("/v1/me")
        expect(me.status_code == 200, "登录后 GET /v1/me 回 200")
        active = (me.json() or {}).get("activePlaythrough") or {}
        if active.get("playthroughId"):  # 上一次冒烟没删掉的：先删
            await delete(c, origin, active["playthroughId"])
        m = await c.get(f"/v1/books/{BOOK}/manifest")
        expect(m.status_code == 200, "manifest 回 200")
        doc: dict[str, Any] = m.json()
        scene = doc["scenes"][0]["assetUrl"] if doc.get("scenes") else None
        if scene:
            s = await c.get(scene)
            expect(s.status_code == 200, "场景包的入口文件能拿到")
        role = doc["roles"][0]["roleId"]
        p = await c.post(
            "/v1/playthroughs",
            json={"bookId": BOOK, "roleId": role},
            headers={**origin, "Idempotency-Key": str(uuid.uuid4())},
        )
        expect(p.status_code == 201, f"开一局（叙事者写了开局，{p.status_code}）")
        pid = p.json()["playthroughId"]
        try:
            jar = "; ".join(f"{k}={v}" for k, v in c.cookies.items())
            closed = await ws_close_code(ws_url(base, pid), {**bearer, **origin, "Cookie": jar})
            expect(closed is None, f"带 Cookie 的 WebSocket 握手过关（关闭码 {closed}）")
        finally:
            expect(await delete(c, origin, pid) == 202, "删掉冒烟的这一局")
    await anon(base, bearer)


def main(argv: list[str]) -> None:
    if len(argv) != 2 or argv[1] not in ("smoke", "anon"):
        sys.exit(__doc__)
    base = os.environ.get("ZJ_SMOKE_URL", "").rstrip("/")
    if not base.startswith("https://") and not LOCAL:
        sys.exit("ZJ_SMOKE_URL 要是 https:// 地址")
    token = os.environ.get("ZJ_SMOKE_BEARER", "")
    bearer = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        if argv[1] == "smoke":
            code = os.environ.get("ZJ_SMOKE_CODE", "")
            if not code:
                sys.exit("没有 ZJ_SMOKE_CODE")
            asyncio.run(smoke(base, bearer, code))
        else:
            asyncio.run(anon(base, bearer))
    except Failed as e:
        print(f"  ✗ {e}")
        sys.exit(1)
    print("全部通过")


if __name__ == "__main__":
    main(sys.argv)
