"""api-contract 第 1 节和 2.1〜2.4 的 REST，加上预录句的录音文件（2.1）、结局（2.8，B-9）、記憶帳（2.7）和删除整局
（2.9，B-13）。其余 `/v1` 接口不挂路由，按第 5 节回 404 not_found（app.py）。

每个响应先用 C-1 生成的类型构造、按 Schema 校验再回；不合契约就回 500 internal，并在日志里记。
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError

from zoujin_backend import memory_delete
from zoujin_backend.config import COOKIE, SESSION_DAYS
from zoujin_backend.db import store
from zoujin_backend.db.tables import endings, idempotency_keys, memory_items, playthrough_metrics, playthroughs, turns
from zoujin_backend.gateway import auth, memory_book
from zoujin_backend.gateway.core import RUNS_PER_DAY, VOICE_MINUTES, Gateway
from zoujin_backend.manifest import CACHE, FILE_CACHE, media_type
from zoujin_backend.narrator import ending as ending_mod
from zoujin_backend.narrator import memory
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


# —— 2.1 ——


@router.get("/v1/books/{book_id}/manifest")
async def manifest(request: Request, book_id: str) -> Response:
    """开进程时生成好的那一份（B-7）。地址不带版本：ETag 是 manifestVersion，对上了回 304。"""
    gw = gw_of(request)
    await user_of(request)
    m = gw.manifest
    if m is None or book_id != m.book_id:
        raise Fail("not_found")
    headers = {"ETag": m.etag, "Cache-Control": CACHE}
    if m.fresh(request.headers.get("if-none-match")):
        return Response(status_code=304, headers=headers)
    resp = ok(gw, "manifest", 200, m.doc)
    resp.headers.update(headers)
    return resp


@router.get("/assets/voice/{book_id}/{name}")
async def voice_file(request: Request, book_id: str, name: str) -> Response:
    """预录句的录音：只发 manifest 里列着的文件，文件名带 hash，长缓存；不要登录（同源的静态资源）。"""
    m = gw_of(request).manifest
    path = m.voice_file(book_id, name) if m is not None else None
    if path is None:
        return Response(status_code=404)
    return FileResponse(path, media_type=media_type(path), headers={"Cache-Control": FILE_CACHE})


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
    closed = gw.manifest is not None and not gw.manifest.has_role(doc["roleId"])  # 不在 manifest 里的身份没开放
    if book is None or doc["roleId"] not in book.roles or closed:
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


@router.get("/v1/playthroughs/{pid}/ending")
async def get_ending(request: Request, pid: str) -> Response:
    """2.8：还没进结局 404；结局任务还没好 202（etaSeconds = 30 减去已经过的秒数，最少 5）；好了 200 EndingView。"""
    gw = gw_of(request)
    await owned(request, pid)
    async with gw.engine.connect() as c:
        body = await c.scalar(select(endings.c.body).where(endings.c.playthrough_id == pid))
        if body is not None:
            return ok(gw, "ending", 200, ending_mod.view(body))
        started = await c.scalar(
            select(func.extract("epoch", func.now() - playthrough_metrics.c.ending_started_at)).where(
                playthrough_metrics.c.playthrough_id == pid
            )
        )
        queued = await c.scalar(
            select(turns.c.turn_id).where(turns.c.playthrough_id == pid, turns.c.kind == ending_mod.KIND).limit(1)
        )
    if queued is None:
        raise Fail("not_found")
    elapsed = float(started) if started is not None else 0.0
    return ok(gw, "ending", 202, {"status": "pending", "etaSeconds": ending_mod.eta(0.0, elapsed)})


# —— 2.7 記憶帳、2.9 删除整局（B-13） ——


async def idempotent(request: Request, user_id: str, run: Callable[[], Awaitable[Response]]) -> Response:
    """带 `Idempotency-Key` 的写接口（和 POST /v1/playthroughs 同一套）：同一账号、同一个键排队；见过的键、同样的请求
    回上次的结果，请求不一样回 idempotency_conflict。只记成功的结果（404、403 不记，换个键照样再判）。"""
    gw = gw_of(request)
    key = request.headers.get("idempotency-key")
    if not key or len(key) > 200:
        log.info("%s %s 没带 Idempotency-Key", request.method, request.url.path)
        raise Fail("invalid_request")
    fp = fingerprint(request, await request.body())
    async with gw.engine.begin() as lock:
        await lock.execute(LOCK_KEY, {"k": f"idem:{user_id}:{key}"})
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
            if seen.status_code == 202:
                return Response(status_code=202)
            return JSONResponse(seen.response, status_code=seen.status_code)
        resp = await run()
        if 200 <= resp.status_code < 300:
            async with gw.engine.begin() as c:
                body = bytes(resp.body) if resp.body else b"{}"
                await c.execute(
                    insert(idempotency_keys).values(
                        user_id=user_id,
                        key=key,
                        request_hash=fp,
                        status_code=resp.status_code,
                        response=json.loads(body),
                    )
                )
        return resp


async def memory_of(request: Request, endpoint: str, pid: str, memory_id: str) -> Json:
    """这一局（是这个人的）里没删的这条记忆；没有、删了、ID 不合法 → 404。"""
    gw = gw_of(request)
    await owned(request, pid)
    if gw.schemas.request_errors(endpoint, "params", {"id": pid, "memoryId": memory_id}):
        raise Fail("not_found")
    async with gw.engine.connect() as c:
        row = (
            (
                await c.execute(
                    select(memory_items).where(
                        memory_items.c.memory_id == memory_id,
                        memory_items.c.playthrough_id == pid,
                        memory_items.c.deleted_at.is_(None),
                    )
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        raise Fail("not_found")
    return dict(row)


@router.get("/v1/playthroughs/{pid}/memories")
async def get_memories(request: Request, pid: str) -> Response:
    gw = gw_of(request)
    await owned(request, pid)
    async with gw.engine.connect() as c:
        pt = await gw.pt(c, pid)
        if pt is None:
            raise Fail("not_found")
        doc = await memory_book.view(c, pt.book, pid, pt.role_id)
    return ok(gw, "memories", 200, doc)


@router.get("/v1/playthroughs/{pid}/memories/{memory_id}/impact")
async def get_memory_impact(request: Request, pid: str, memory_id: str) -> Response:
    """删除确认里的「不会撤销的后果」一句：第一次请求时由模型写，缓存在这条记忆上
    （算出 null 也缓存；模型出错不缓存）。"""
    gw = gw_of(request)
    row = await memory_of(request, "memory-impact", pid, memory_id)
    async with gw.engine.connect() as c:
        pt = await gw.pt(c, pid)
        if pt is None:
            raise Fail("not_found")
        state = await store.sim_state(c, pid)
        evs = [e for e in await store.event_log(c, pid, pt.book.version) if e["eventId"] in row["from_events"]]
    promises: dict[str, Json] = dict(state.get("promises") or {}) if state is not None else {}
    promise = promises.get(row["promise_id"] or "")
    voids = promise is not None and promise["status"] == "open"
    keeps = row["keeps"]
    if not row["keeps_done"]:
        keeps, cache, cost = await memory.keeps(
            gw.screener.text, gw.tracer, pt.book, row, evs, promise, playthrough_id=pid, memory_id=memory_id
        )
        async with gw.engine.begin() as c:
            if cache:
                await c.execute(
                    update(memory_items)
                    .where(memory_items.c.memory_id == memory_id, memory_items.c.deleted_at.is_(None))
                    .values(keeps=keeps, keeps_done=True)
                )
            m = playthrough_metrics.c
            await c.execute(
                update(playthrough_metrics)
                .where(m.playthrough_id == pid)
                .values(cost_memory_usd=m.cost_memory_usd + cost)
            )
    return ok(gw, "memory-impact", 200, {"keeps": keeps, "voidsPromise": voids})


@router.delete("/v1/playthroughs/{pid}/memories/{memory_id}")
async def delete_memory(request: Request, pid: str, memory_id: str) -> Response:
    """当场生效（`memory_delete.delete_memory`）；之后这一局开着连接就丢掉那几轮的最近对话、重建这个人物的会话，
    断线寄存的会话和最近对话丢掉。"""
    gw = gw_of(request)
    user_id = await user_of(request)

    async def run() -> Response:
        await memory_of(request, "memory-delete", pid, memory_id)
        try:
            async with gw.engine.begin() as c:
                d = await memory_delete.delete_memory(c, gw.library, gw.ids, gw.schemas, pid, memory_id)
        except memory_delete.NotFound:
            raise Fail("not_found") from None
        conn = gw.conns.get(pid)
        rebuilt = await conn.forgot(d.turn_ids, d.character) if conn is not None else False
        await gw.forget(pid)
        with gw.tracer.span("gateway.memory_delete", playthrough_id=pid, memory_id=memory_id) as sp:
            sp.set(turns=len(d.turn_ids), voided=d.promise_voided is not None, rebuilt=rebuilt)
        return ok(gw, "memory-delete", 200, d.response(rebuilt=rebuilt))

    return await idempotent(request, user_id, run)


@router.delete("/v1/playthroughs/{pid}")
async def delete_playthrough(request: Request, pid: str) -> Response:
    """L2（data-design 5.2）：这一局的行全删，开着的 WebSocket 以 4004 关闭，寄存的会话丢掉。之后这一局都是 404。"""
    gw = gw_of(request)
    user_id = await user_of(request)

    async def run() -> Response:
        await owned(request, pid)
        conn = gw.conns.get(pid)
        if conn is not None:
            await conn.close(4004, "deleted")
        await gw.forget(pid)
        async with gw.engine.begin() as c:
            await memory_delete.delete_playthrough(c, pid)
        return Response(status_code=202)

    return await idempotent(request, user_id, run)
