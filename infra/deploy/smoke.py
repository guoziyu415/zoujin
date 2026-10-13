"""デプロイ後の検査（B-23）。zg の Mac 上で deploy.sh が実行する。URL と招待コードは環境変数からだけ読み、出力しない。

    python smoke.py smoke   スモークテスト専用の招待コードで：ページ、ログイン、manifest、プレイ開始（ナレーターが
                            開始を書く = ナラティブのコミット 1 回。ゲートウェイがナレーターを呼ぶときの認証も確認）、
                            Cookie 付きの WebSocket ハンドシェイクが通ることを確認し、最後にこのプレイを削除する
    python smoke.py anon    匿名アクセスが拒否されること：REST は 401、WebSocket ハンドシェイクは 4001 で閉じる

環境変数：ZJ_SMOKE_URL（https://…、末尾の / なし）、ZJ_SMOKE_CODE（smoke 用）、ZJ_SMOKE_BEARER（任意：サービスが
まだ非公開のときの zg の ID トークンで、Cloud Run の IAM が見る。アプリ自身は読まない）。合格なら終了コード 0、
不合格ならどの項目かを出力して終了コード 1。
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
# このスクリプトをローカルで試すときだけ：http を許可し、Secure を確認しない
LOCAL = os.environ.get("ZJ_SMOKE_LOCAL") == "1"


class Failed(Exception):
    pass


def expect(ok: bool, what: str) -> None:
    if not ok:
        raise Failed(what)
    print(f"  ✓ {what}")


def ws_url(base: str, pid: str) -> str:
    return base.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + f"/v1/playthroughs/{pid}/live"


async def ws_close_code(url: str, headers: dict[str, str]) -> int | None:
    """接続後しばらく待つ：閉じられたらクローズコードを、開いたままなら None を返す。ハンドシェイク自体が拒否されたら（HTTP 4xx）-1。"""
    try:
        async with websockets.connect(url, additional_headers=headers, open_timeout=15) as ws:
            try:
                await asyncio.wait_for(ws.recv(), timeout=WS_WAIT_S)
            except TimeoutError:
                return None
            except ConnectionClosed as e:
                return e.rcvd.code if e.rcvd else -1
            try:  # メッセージを受信した：サーバーは閉じていないので、もう一度確認する
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
                "匿名のページ、アセット、目録はまずパスワードゲートを通る",
            )
        me = await c.get("/v1/me")
        expect(me.status_code == 401, "匿名の GET /v1/me は 401")
        m = await c.get(f"/v1/books/{BOOK}/manifest")
        expect(m.status_code == 401, "匿名の manifest 取得は 401")
        p = await c.post("/v1/playthroughs", json={}, headers={**origin, "Idempotency-Key": str(uuid.uuid4())})
        expect(p.status_code == 401, "匿名のプレイ開始は 401")
    code = await ws_close_code(ws_url(base, "pt_00000000000000000000000000"), {**bearer, **origin})
    expect(code in (4001, 4401, -1), f"匿名の WebSocket ハンドシェイクは拒否される（クローズコード {code}）")


async def smoke(base: str, bearer: dict[str, str], code: str) -> None:
    origin = {"Origin": base}
    async with httpx.AsyncClient(base_url=base, timeout=60, headers=bearer) as c:
        password = os.environ.get("ZJ_SMOKE_PASSWORD", "")
        expect(bool(password), "サイトのパスワードが設定済み（出力しない）")
        unlocked = await c.post("/site-access", data={"password": password}, headers=origin)
        expect(unlocked.status_code == 303, "サイトのパスワードが通る")
        expect("HttpOnly" in unlocked.headers.get("set-cookie", ""), "通行用 Cookie はスクリプトから読めない")
        health = await c.get("/health")
        expect(health.status_code == 204, "ヘルスチェックは空の 204 を返す")
        page = await c.get("/")
        expect(page.status_code == 200 and "<html" in page.text.lower()[:500], "トップページはフロントエンドのページ")
        expect(page.headers.get("x-robots-tag", "").startswith("noindex"), "ページは検索エンジンにインデックスさせない")
        login = await c.post("/v1/auth/login", json={"inviteCode": code}, headers=origin)
        expect(login.status_code == 200, f"スモークテスト用の招待コードでログイン（{login.status_code}）")
        cookie = login.headers.get("set-cookie", "")
        secure = "Secure" in cookie or LOCAL
        expect(secure and "HttpOnly" in cookie, "セッション Cookie に Secure と HttpOnly が付く")
        me = await c.get("/v1/me")
        expect(me.status_code == 200, "ログイン後の GET /v1/me は 200")
        active = (me.json() or {}).get("activePlaythrough") or {}
        if active.get("playthroughId"):  # 前回のスモークテストで消し残したもの：先に削除する
            await delete(c, origin, active["playthroughId"])
        m = await c.get(f"/v1/books/{BOOK}/manifest")
        expect(m.status_code == 200, "manifest は 200")
        doc: dict[str, Any] = m.json()
        scene = doc["scenes"][0]["assetUrl"] if doc.get("scenes") else None
        if scene:
            s = await c.get(scene)
            expect(s.status_code == 200, "シーンパックのエントリファイルを取得できる")
        role = doc["roles"][0]["roleId"]
        p = await c.post(
            "/v1/playthroughs",
            json={"bookId": BOOK, "roleId": role},
            headers={**origin, "Idempotency-Key": str(uuid.uuid4())},
        )
        expect(p.status_code == 201, f"プレイ開始（ナレーターが開始を書いた、{p.status_code}）")
        pid = p.json()["playthroughId"]
        try:
            jar = "; ".join(f"{k}={v}" for k, v in c.cookies.items())
            closed = await ws_close_code(ws_url(base, pid), {**bearer, **origin, "Cookie": jar})
            expect(closed is None, f"Cookie 付きの WebSocket ハンドシェイクが通る（クローズコード {closed}）")
        finally:
            expect(await delete(c, origin, pid) == 202, "スモークテストのこのプレイを削除する")
    await anon(base, bearer)


def main(argv: list[str]) -> None:
    if len(argv) != 2 or argv[1] not in ("smoke", "anon"):
        sys.exit(__doc__)
    base = os.environ.get("ZJ_SMOKE_URL", "").rstrip("/")
    if not base.startswith("https://") and not LOCAL:
        sys.exit("ZJ_SMOKE_URL は https:// の URL でなければならない")
    token = os.environ.get("ZJ_SMOKE_BEARER", "")
    bearer = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        if argv[1] == "smoke":
            code = os.environ.get("ZJ_SMOKE_CODE", "")
            if not code:
                sys.exit("ZJ_SMOKE_CODE が未設定")
            asyncio.run(smoke(base, bearer, code))
        else:
            asyncio.run(anon(base, bearer))
    except Failed as e:
        print(f"  ✗ {e}")
        sys.exit(1)
    print("すべて合格")


if __name__ == "__main__":
    main(sys.argv)
