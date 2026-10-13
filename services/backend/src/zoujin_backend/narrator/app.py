"""Narrator service (`zoujin-narrator`): an internal API only the gateway calls, shaped like the later Cloud Run
service-to-service calls (B-0 item 7, step 7).

`POST /internal/v1/playthroughs/{pid}/run`: work through this game's queued tasks in order and return
`{"processed": n}`. If another process is already working on this game, return 0 right away (that one picks up the
rest when it is done). Caller authentication (OIDC) is done by Cloud Run (B-23): the service only opens internal
ingress, allows no anonymous calls, and only the gateway's service account may invoke it; `ZJ_NARRATOR_AUTH=iam` says
it is deployed that way. With the dev switch on nothing is checked; with neither, every call gets 401, so a
misconfigured service is never left open.

ナレーターサービス（`zoujin-narrator`）：ゲートウェイだけが呼ぶ内部 API。形は将来の Cloud Run のサービス間呼び出しに
合わせる（B-0 第 7 項第 7 ステップ）。

`POST /internal/v1/playthroughs/{pid}/run`：このゲームに積まれたタスクを順に片づけ、`{"processed": n}` を返す。
別のプロセスがこのゲームを処理中ならすぐ 0 を返す（向こうが終わったら続きを取る）。呼び出し元の認証（OIDC）は
Cloud Run が行う（B-23）：サービスは内部の入口だけを開き、匿名を許さず、ゲートウェイのサービスアカウントだけが
呼び出せる。`ZJ_NARRATOR_AUTH=iam` はそのようにデプロイしたことを示す。開発スイッチがオンなら確認しない。
どちらもなければ常に 401 を返し、設定し損ねたまま外に開いてしまうのを防ぐ。
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import create_async_engine
from zoujin_backend import logs
from zoujin_backend.config import Settings
from zoujin_backend.models.armor import armor
from zoujin_backend.models.text import text_model
from zoujin_backend.narrator.core import Narrator
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.world import Library

log = logging.getLogger("zoujin.narrator")


def build(settings: Settings) -> Narrator:
    engine = create_async_engine(settings.database_url, pool_size=5)
    return Narrator(
        engine=engine,
        library=Library(settings.worlds, settings.scenes, settings.world, settings.released_worlds),
        text=text_model(settings.model, fake_rules=settings.fake_text, replays=settings.replays, settings=settings),
        schemas=SchemaBook(settings.schemas),
        deadlines=settings.deadlines,
        # Serving players: 429/529 don't stop the service; handled by the deadline rules (B-8).
        # プレイヤー向け：429・529 でもサービスを止めず、時間制限の規則で処理する（B-8）。
        on_rate_limit="degrade",
        # B-13: the second filter for memory lines / B-13：記憶の一文に対する 2 段目のフィルター
        armor=armor(settings.model, replays=settings.replays),
    )


def create_app(settings: Settings, narrator: Narrator | None = None) -> FastAPI:
    n = narrator or build(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await n.engine.dispose()

    app = FastAPI(title="zoujin narrator", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.narrator = n

    @app.get("/health")
    @app.get("/healthz")
    async def healthz() -> Response:
        return Response(status_code=204)

    @app.post("/internal/v1/playthroughs/{pid}/run")
    async def run(request: Request, pid: str) -> Response:
        if not settings.dev and settings.narrator_auth != "iam":
            log.warning(
                "No dev switch and not a ZJ_NARRATOR_AUTH=iam deployment; refusing"
                " / 開発スイッチがなく、ZJ_NARRATOR_AUTH=iam のデプロイでもないため拒否"
            )
            return JSONResponse({"error": "unauthenticated"}, status_code=401)
        done = await n.run(pid)
        return JSONResponse({"processed": len(done)})

    return app


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(
        prog="zoujin-narrator",
        description="Narrator (B-0): called only by the gateway / ナレーター（B-0）：ゲートウェイだけが呼ぶ",
    )
    p.add_argument(
        "--host",
        default="127.0.0.1",
        help="Listens on this machine only by default; use 0.0.0.0 in a container"
        " / 既定ではこのマシンだけで待ち受ける。コンテナでは 0.0.0.0",
    )
    p.add_argument("--port", type=int, default=8002)
    p.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error"])
    args = p.parse_args(argv)
    settings = Settings.from_env()
    logs.setup(args.log_level, dev=settings.dev)
    uvicorn.run(create_app(settings), host=args.host, port=args.port, log_level=args.log_level, log_config=None)
