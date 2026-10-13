"""Assembles the gateway into an ASGI app, plus the `zoujin-gateway` command.

- REST calls that change data (POST, DELETE) need a JSON content type and the right Origin, otherwise 403 (section 0);
- unmounted `/v1` endpoints answer with the section 5 404 not_found;
- when the session is renewed, a Set-Cookie is added (sliding 30 days);
- on SIGTERM: first push goaway to every connection and close it with 1012, then stop the server (section 4).

ゲートウェイを 1 つの ASGI アプリにまとめたものと、`zoujin-gateway` コマンド。

- データを変える REST（POST、DELETE）は JSON のコンテントタイプと正しい Origin が必要で、なければ 403（第 0 節）；
- マウントされていない `/v1` エンドポイントは第 5 節の 404 not_found を返す；
- セッションが延長されたら Set-Cookie を付け足す（30 日のスライディング）；
- SIGTERM を受けたら：まず各接続に goaway を送って 1012 で閉じ、それからサーバーを止める（第 4 節）。
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
from zoujin_backend.gateway import rest, web, ws
from zoujin_backend.gateway.core import Gateway, HttpNarrator, IdToken, NarratorClient
from zoujin_backend.gateway.hub import Hub
from zoujin_backend.gateway.site_access import SiteAccess
from zoujin_backend.manifest import generate
from zoujin_backend.models.live import FakeLive
from zoujin_backend.origin import csrf_problem
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.voice.spec import read_spec
from zoujin_backend.world import Library

log = logging.getLogger("zoujin.gateway")

GOAWAY_MS = 1000  # the frontend reconnects after this / フロントエンドはこの後に再接続する
# How many seconds at most to wait for in-flight tasks (submitting turns, calling the narrator) before stopping.
# サーバー停止前に処理中のタスク（ターンの提出、ナレーターの呼び出し）を待つ最大秒数。
SHUTDOWN_GRACE_S = 5


def build(settings: Settings, narrator: NarratorClient | None = None) -> Gateway:
    """If generating the manifest fails (`ManifestError`, naming the file and field), the gateway won't start.

    manifest の生成でエラー（`ManifestError`。どのファイルのどのフィールドかを示す）が出たら起動しない。
    """
    library = Library(settings.worlds, settings.scenes, settings.world, settings.released_worlds)
    schemas = SchemaBook(settings.schemas)
    manifests = {
        bid: generate(book, schemas, packs=settings.packs, voices=settings.voice_dir, release=settings.release)
        for bid, book in library.available.items()
    }
    gw = Gateway(
        settings=settings,
        engine=create_async_engine(settings.database_url, pool_size=10),
        library=library,
        schemas=schemas,
        live=FakeLive(settings.fake_voice, speed=settings.speed),
        narrator=narrator or http_narrator(settings),
        manifest=manifests[library.current.book_id],
        manifests=manifests,
    )
    if settings.live == "real":  # pragma: no cover - Mac only (B-10) / Mac 上のみ（B-10）
        real_live(gw, settings)
    return gw


def http_narrator(settings: Settings) -> HttpNarrator:
    token = IdToken(settings.narrator_url) if settings.narrator_auth == "iam" else None
    return HttpNarrator(settings.narrator_url, token=token)


def voices_of(book: str = "hashire-merosu") -> dict[str, str]:
    """Character → voice (D-025): defined in one place only, B-6's source file.

    登場人物 → 声（D-025）：B-6 のソースファイルの 1 か所だけで決める。
    """
    spec = read_spec(book)
    return {k: v["voice"] for k, v in spec["speakers"].items() if v.get("voice")}


def real_live(gw: Gateway, settings: Settings) -> None:  # pragma: no cover - Mac only / Mac 上のみ
    """`ZJ_LIVE=real`: real Live, real fallback transcription, and the Live ledger (the Google one, with the same cap
    settings as B-2).

    `ZJ_LIVE=real`：本物の Live、本物の補完の文字起こし、Live の台帳（Google の台帳。上限設定は B-2 と同じ）。
    """
    import os

    from zoujin_backend.config import ConfigError
    from zoujin_backend.gateway.fallback import VertexTranscriber
    from zoujin_backend.models import gemini_live
    from zoujin_backend.models.ledger import Ledger
    from zoujin_backend.voice.models import LIVE_MODEL, real_models

    if settings.ledger is None or settings.max_google_usd is None:
        raise ConfigError(
            "ZJ_LIVE=real needs a ledger and a total Google cap: ZJ_LEDGER, ZJ_MAX_GOOGLE_USD, with no defaults"
            " / ZJ_LIVE=real には台帳と Google の総上限が必要：ZJ_LEDGER、ZJ_MAX_GOOGLE_USD（デフォルト値なし）"
        )
    _, rest = real_models(os.environ)
    tr = VertexTranscriber(rest)
    gw.transcriber = tr
    voices: dict[str, str] = {}
    for book_id in gw.library.available:
        for character, voice in voices_of(book_id).items():
            if character in voices and voices[character] != voice:
                raise ConfigError(
                    f"A character ID is reused with different voices across books: {character}; use separate"
                    f" character IDs / 本ごとに異なる声で同じ登場人物 ID が使われている：{character}。"
                    "別々の登場人物 ID を使うこと"
                )
            voices[character] = voice
    gw.live = gemini_live.real_live(os.environ, voices, tr)
    gw.live_ledger = Ledger(settings.ledger, settings.max_google_usd, settings.max_item_usd, settings.ledger_item)
    gw.live_model_name = LIVE_MODEL


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
            # Drain: turns submitted on disconnect and requests to the narrator; wait a moment before stopping.
            # 排出：切断時に提出されたターンやナレーターへのリクエストを、少し待ってから止める。
            if gw.tasks:
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
    # Deployment (B-23): serve the frontend and scene packs from the same origin, mounted last to catch other GETs.
    # デプロイ（B-23）：フロントエンドとシーンパックを同一オリジンで配信。最後にマウントしてほかの GET を受ける。
    if settings.web_dist is not None:
        app.include_router(web.router(settings.web_dist))

    @app.exception_handler(rest.Fail)
    async def on_fail(request: Request, exc: rest.Fail) -> Response:
        return rest.fail_response(gw, exc)

    @app.exception_handler(Exception)
    async def on_error(request: Request, exc: Exception) -> Response:
        """Uncaught exceptions also get the section 5 JSON (not uvicorn's plain-text 500).

        捕捉されなかった例外にも第 5 節の JSON を返す（uvicorn のプレーンテキストの 500 は返さない）。
        """
        log.error("%s %s failed / エラー", request.method, request.url.path, exc_info=exc)
        return rest.fail_response(gw, rest.Fail("internal"))

    @app.exception_handler(StarletteHTTPException)
    async def on_http(request: Request, exc: StarletteHTTPException) -> Response:
        """Endpoints B-0 doesn't mount: the section 5 shape, 404 not_found (no separate "not implemented").

        B-0 でマウントしていないエンドポイント：第 5 節の形、404 not_found（「未実装」を別に設けない）。
        """
        if exc.status_code in (404, 405):
            return rest.fail_response(gw, rest.Fail("not_found"))
        return rest.fail_response(gw, rest.Fail("internal"))

    @app.middleware("http")
    async def guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if request.method in ("POST", "DELETE") and request.url.path.startswith("/v1/"):
            why = csrf_problem(request, settings.allow_origins)
            if why is not None:
                log.info("%s %s → 403: %s", request.method, request.url.path, why)
                return rest.fail_response(gw, rest.Fail("forbidden"))
        resp = await call_next(request)
        token = getattr(request.state, "slid_token", None)
        if token is not None and "set-cookie" not in resp.headers:
            rest.set_cookie(gw, resp, token)
        # Deployment (B-23): for invited people only; keep search engines out.
        # デプロイ（B-23）：招待された人だけのもの。検索エンジンには収集させない。
        if settings.web_dist is not None:
            resp.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
        if request.url.path.startswith("/v1/"):
            resp.headers["Cache-Control"] = "private, no-store"
        return resp

    # The outermost ASGI middleware covers both HTTP and WebSocket; checking the password only in REST routes is not
    # enough.
    # いちばん外側の ASGI middleware が HTTP と WebSocket の両方を覆う。REST のルートだけでパスワードを確認しては
    # いけない。
    app.add_middleware(SiteAccess, password=settings.site_password, dev=settings.dev)
    return app


class Server(uvicorn.Server):
    """First SIGTERM / SIGINT: push goaway, close every connection with 1012, then stop the uvicorn way. The second one
    behaves as plain uvicorn.

    1 回目の SIGTERM / SIGINT：goaway を送り、各接続を 1012 で閉じてから uvicorn の手順で止める。2 回目は uvicorn の
    ままの動作。
    """

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
    p = argparse.ArgumentParser(
        prog="zoujin-gateway", description="Gateway (B-0): REST and WebSocket / ゲートウェイ（B-0）：REST と WebSocket"
    )
    p.add_argument(
        "--host",
        default="127.0.0.1",
        help="Listens on this machine only by default; use 0.0.0.0 in a container"
        " / 既定ではこのマシンのみで待ち受ける。コンテナでは 0.0.0.0",
    )
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
