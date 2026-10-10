"""api-contract 第 1 节和 2.2〜2.4 的 REST。其余 `/v1` 接口 B-0 不挂路由，按第 5 节回 404 not_found（app.py）。

每个响应先用 C-1 生成的类型构造、按 Schema 校验再回；不合契约就回 500 internal，并在日志里记。
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.exc import IntegrityError

from zoujin_backend.config import COOKIE, SESSION_DAYS
from zoujin_backend.db import store
from zoujin_backend.db.tables import idempotency_keys, playthroughs
from zoujin_backend.gateway import auth
from zoujin_backend.gateway.core import RUNS_PER_DAY, VOICE_MINUTES, Gateway
from zoujin_backend.schemas import SchemaError

log = logging.getLogger("zoujin.gateway")

Json = Any

router = APIRouter()

# 给玩家看的日语短句（第 5 节）；和 mock 同一套
MESSAGES = {
    "invalid_request": "うまく送れませんでした。",
    "unauthenticated": "もう一度、招待コードを入力してください。",
    "forbidden": "この操作はできません。",
    "not_found": "見つかりませんでした。",
    "invalid_invite": "招待コードが違います。",
    "active_playthrough_exists": "進行中の物語があります。",
    "idempotency_conflict": "もう一度お試しください。",
    "rate_limited": "少し時間をおいてから、もう一度お試しください。",
    "internal": "エラーが起きました。",
}
STATUS = {
    "invalid_request": 400,
    "unauthenticated": 401,
    "invalid_invite": 401,
    "forbidden": 403,
    "not_found": 404,
    "active_playthrough_exists": 409,
    "idempotency_conflict": 422,
    "rate_limited": 429,
    "internal": 500,
}


class Fail(Exception):
    def __init__(self, code: str, *, active: Json | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.active = active


def gw_of(request: Request) -> Gateway:
    gw: Gateway = request.app.state.gw
    return gw


def error_body(gw: Gateway, code: str, active: Json | None = None) -> Json:
    doc: Json = {
        "error": {
            "code": code,
            "message": MESSAGES[code],
            "retryable": code in ("rate_limited", "internal"),
            "retryAfterSeconds": None,
        }
    }
    if active is not None:
        doc["activePlaythrough"] = active
    return gw.schemas.build("api/error.schema.json", "#/$defs/ErrorResponse", doc)


def fail_response(gw: Gateway, f: Fail) -> JSONResponse:
    return JSONResponse(error_body(gw, f.code, f.active), status_code=STATUS[f.code])


def ok(gw: Gateway, endpoint: str, status: int, doc: Json) -> JSONResponse:
    try:
        body = gw.schemas.response(endpoint, status, doc)
    except SchemaError:
        log.exception("不回 %s %s：不合契约", endpoint, status)
        return fail_response(gw, Fail("internal"))
    return JSONResponse(body, status_code=status)


async def body_of(request: Request) -> Json:
    try:
        return json.loads(await request.body() or b"null")
    except json.JSONDecodeError:
        raise Fail("invalid_request") from None


def check_request(gw: Gateway, endpoint: str, part: str, doc: Json) -> None:
    errs = gw.schemas.request_errors(endpoint, part, doc)
    if errs:
        log.info("%s 的 %s 不合 Schema：%s", endpoint, part, "; ".join(errs[:3]))
        raise Fail("invalid_request")


def set_cookie(gw: Gateway, resp: Response, token: str) -> None:
    resp.set_cookie(
        COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=not gw.settings.dev,  # 本地 http 由开发开关关掉 Secure（B-0 第 3 条）
        path="/",
    )


async def user_of(request: Request) -> str:
    """有效会话的 userId；续期了的话在 request.state 上记下，中间件补 Set-Cookie。"""
    gw = gw_of(request)
    token = request.cookies.get(COOKIE)
    async with gw.engine.begin() as c:
        found = await auth.session_user(c, token)
    if found is None:
        raise Fail("unauthenticated")
    user_id, slid = found
    if slid and token:
        request.state.slid_token = token
    return user_id


async def owned(request: Request, pid: str) -> str:
    """这一局是这个人的：不是合法的局 ID 或没有这一局 404，别人的 403（第 5 节）。"""
    gw = gw_of(request)
    user_id = await user_of(request)
    if gw.schemas.request_errors("snapshot", "params", {"id": pid}):
        raise Fail("not_found")
    async with gw.engine.connect() as c:
        owner = await c.scalar(select(playthroughs.c.user_ref).where(playthroughs.c.playthrough_id == pid))
    if owner is None:
        raise Fail("not_found")
    if owner != user_id:
        raise Fail("forbidden")
    return user_id


# —— 第 1 节 ——


@router.post("/v1/auth/login")
async def login(request: Request) -> Response:
    gw = gw_of(request)
    doc = await body_of(request)
    check_request(gw, "auth-login", "request", doc)
    async with gw.engine.begin() as c:
        user_id = await auth.redeem(c, gw.ids, doc["inviteCode"])
        if user_id is None:
            log.info("邀请码不对")
            raise Fail("invalid_invite")
        token = await auth.new_session(c, user_id)
        me_doc_ = await me_doc(gw, c, user_id)
    resp = ok(gw, "auth-login", 200, me_doc_)
    set_cookie(gw, resp, token)
    return resp


@router.post("/v1/auth/logout")
async def logout(request: Request) -> Response:
    gw = gw_of(request)
    async with gw.engine.begin() as c:
        await auth.end_session(c, request.cookies.get(COOKIE))
    resp = Response(status_code=204)
    resp.delete_cookie(COOKIE, path="/")
    return resp


async def me_doc(gw: Gateway, c: Any, user_id: str) -> Json:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    runs = await c.scalar(
        select(func.count())
        .select_from(playthroughs)
        .where(playthroughs.c.user_ref == user_id, playthroughs.c.started_at >= today)
    )
    active = await active_pt(gw, c, user_id)
    return {
        "user": {"userRef": user_id},
        "limits": {"runsToday": int(runs or 0), "runsPerDay": RUNS_PER_DAY, "voiceMinutesLeft": VOICE_MINUTES},
        "activePlaythrough": active,
    }


async def active_pt(gw: Gateway, c: Any, user_id: str) -> Json | None:
    pid = await c.scalar(
        select(playthroughs.c.playthrough_id).where(
            playthroughs.c.user_ref == user_id, playthroughs.c.status == "active"
        )
    )
    if pid is None:
        return None
    pt = await gw.pt(c, pid)
    return await gw.active_ref(c, pt) if pt is not None else None


@router.get("/v1/me")
async def me(request: Request) -> Response:
    gw = gw_of(request)
    user_id = await user_of(request)
    async with gw.engine.connect() as c:
        doc = await me_doc(gw, c, user_id)
    return ok(gw, "me", 200, doc)


# —— 2.2〜2.4 ——


def fingerprint(request: Request, body: bytes) -> str:
    return hashlib.sha256(f"{request.method} {request.url.path} ".encode() + body).hexdigest()


@router.post("/v1/playthroughs")
async def create_playthrough(request: Request) -> Response:
    gw = gw_of(request)
    user_id = await user_of(request)
    key = request.headers.get("idempotency-key")
    if not key or len(key) > 200:
        log.info("POST /v1/playthroughs 没带 Idempotency-Key")
        raise Fail("invalid_request")
    raw = await request.body()
    fp = fingerprint(request, raw)
    async with gw.engine.begin() as lock:
        # 同一账号、同一个键的请求排队（前端断网重试用同一个键，可能并发）：前一个建完、记下结果，后一个再查，
        # 拿到同样的 201。锁跟着这个事务，出错回滚也会放掉。
        await lock.execute(LOCK_KEY, {"k": f"idem:{user_id}:{key}"})
        return await _create(gw, request, user_id, key, fp)


LOCK_KEY = text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))")


async def _create(gw: Gateway, request: Request, user_id: str, key: str, fp: str) -> Response:
    async with gw.engine.connect() as c:
        seen = (
            await c.execute(
                select(
                    idempotency_keys.c.request_hash, idempotency_keys.c.status_code, idempotency_keys.c.response
                ).where(idempotency_keys.c.user_id == user_id, idempotency_keys.c.key == key)
            )
        ).first()
    if seen is not None:
        if seen.request_hash != fp:
            raise Fail("idempotency_conflict")
        return JSONResponse(seen.response, status_code=seen.status_code)
    doc = await body_of(request)
    check_request(gw, "playthroughs-create", "request", doc)
    book = gw.library.book(doc["bookId"])
    if book is None or doc["roleId"] not in book.roles:
        log.info("没有这个书或身份")
        raise Fail("invalid_request")

    async with gw.engine.begin() as c:
        active = await active_pt(gw, c, user_id)
        if active is not None:
            resp = fail_response(gw, Fail("active_playthrough_exists", active=active))
            await remember(c, user_id, key, fp, resp)
            return resp
        try:
            async with c.begin_nested():
                pid = await store.create_playthrough(c, gw.ids, user_id=user_id, book=book, role_id=doc["roleId"])
        except IntegrityError:
            raise Fail("active_playthrough_exists", active=await active_pt(gw, c, user_id)) from None
    try:
        await gw.narrator.run(pid)  # 开局：叙事者写开局事件，回来就能给快照
        snap = await gw.snapshot(pid)
    except Exception:
        log.exception("开局失败（%s），删掉这一局", pid)
        async with gw.engine.begin() as c:
            await c.execute(delete(playthroughs).where(playthroughs.c.playthrough_id == pid))
        raise Fail("internal") from None
    resp = ok(gw, "playthroughs-create", 201, {"playthroughId": pid, "snapshot": snap})
    async with gw.engine.begin() as c:
        await remember(c, user_id, key, fp, resp)
    return resp


async def remember(c: Any, user_id: str, key: str, fp: str, resp: JSONResponse) -> None:
    await c.execute(
        insert(idempotency_keys).values(
            user_id=user_id,
            key=key,
            request_hash=fp,
            status_code=resp.status_code,
            response=json.loads(bytes(resp.body)),
        )
    )


@router.get("/v1/playthroughs/{pid}/snapshot")
async def get_snapshot(request: Request, pid: str) -> Response:
    gw = gw_of(request)
    await owned(request, pid)
    snap = await gw.snapshot(pid)
    if snap is None:
        raise Fail("not_found")
    return ok(gw, "snapshot", 200, snap)


def int_query(request: Request, name: str) -> Any:
    v = request.query_params.get(name)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return v  # 交给 Schema 报错


@router.get("/v1/playthroughs/{pid}/events")
async def get_events(request: Request, pid: str) -> Response:
    gw = gw_of(request)
    await owned(request, pid)
    query = {k: v for k in ("afterSeq", "limit") if (v := int_query(request, k)) is not None}
    check_request(gw, "events", "query", query)
    evs = await gw.visible_events(pid, query.get("afterSeq", 0), query.get("limit", 50))
    async with gw.engine.connect() as c:
        last_seq = await c.scalar(select(playthroughs.c.last_seq).where(playthroughs.c.playthrough_id == pid))
    return ok(gw, "events", 200, {"events": evs, "lastSeq": int(last_seq or 0)})
