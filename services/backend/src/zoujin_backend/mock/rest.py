"""api-contract 第 1、2 节的 REST，和 mock 专用的控制接口 `/__mock/*`（不进契约）。"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from zoujin_backend.mock import scripts
from zoujin_backend.mock.core import COOKIE, INVITE_CODE, Mock
from zoujin_backend.mock.scripts import ScriptError
from zoujin_backend.mock.state import Playthrough, Session
from zoujin_backend.mock.ws import WsLink, rebuild
from zoujin_backend.schemas import SchemaError

log = logging.getLogger("zoujin.mock")

Json = Any

router = APIRouter()
control = APIRouter(prefix="/__mock")

# 给玩家看的日语短句（第 5 节）；前端也可以按 code 用自己的文案
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
MAX_LOGIN_FAILURES = 5


class Fail(Exception):
    def __init__(self, code: str, *, retry_after: int | None = None, active: Json | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after
        self.active = active


def mock_of(request: Request) -> Mock:
    m: Mock = request.app.state.mock
    return m


def error_body(m: Mock, code: str, retry_after: int | None = None, active: Json | None = None) -> Json:
    doc: Json = {
        "error": {
            "code": code,
            "message": MESSAGES[code],
            "retryable": code in ("rate_limited", "internal"),
            "retryAfterSeconds": retry_after,
        }
    }
    if active is not None:
        doc["activePlaythrough"] = active
    return m.book.build("api/error.schema.json", "#/$defs/ErrorResponse", doc)


def fail_response(m: Mock, f: Fail) -> JSONResponse:
    return JSONResponse(error_body(m, f.code, f.retry_after, f.active), status_code=STATUS[f.code])


def ok(m: Mock, endpoint: str, status: int, doc: Json) -> JSONResponse:
    """用生成的类型构造、按 Schema 校验后再回；不合契约就回 500，并在终端报错。"""
    try:
        body = m.book.response(endpoint, status, doc)
    except SchemaError as e:
        log.error("不回 %s %s：%s", endpoint, status, e)
        if m.config.strict:
            raise
        return fail_response(m, Fail("internal"))
    return JSONResponse(body, status_code=status)


async def body_of(request: Request) -> Json:
    try:
        return json.loads(await request.body() or b"null")
    except json.JSONDecodeError:
        raise Fail("invalid_request") from None


def check_request(m: Mock, endpoint: str, part: str, doc: Json) -> None:
    errs = m.book.request_errors(endpoint, part, doc)
    if errs:
        log.info("%s 的 %s 不合 Schema：%s", endpoint, part, "; ".join(errs))
        raise Fail("invalid_request")


def session_of(request: Request) -> Session:
    s = mock_of(request).session(request.cookies.get(COOKIE))
    if s is None:
        raise Fail("unauthenticated")
    return s


def playthrough_of(request: Request, pid: str) -> Playthrough:
    m = mock_of(request)
    s = session_of(request)
    if m.book.request_errors("snapshot", "params", {"id": pid}):
        raise Fail("not_found")
    pt = m.playthroughs.get(pid)
    if pt is None or pt.status == "deleted":
        raise Fail("not_found")
    if pt.owner != s.sid:
        raise Fail("forbidden")
    return pt


def fingerprint(request: Request, body: bytes) -> str:
    return hashlib.sha256(f"{request.method} {request.url.path} ".encode() + body).hexdigest()


def idempotent(request: Request, s: Session, body: bytes) -> tuple[str, str] | Response:
    """带 Idempotency-Key 的接口：同一个键、同样的请求回上次的结果；内容不同回 422（第 0 节、第 5 节）。"""
    m = mock_of(request)
    key = request.headers.get("idempotency-key")
    if not key:
        log.info("%s %s 没带 Idempotency-Key", request.method, request.url.path)
        raise Fail("invalid_request")
    seen = m.idempotency.get((s.sid, key))
    if seen is not None:
        if seen[0] != fingerprint(request, body):
            raise Fail("idempotency_conflict")
        return Response(seen[2], status_code=seen[1], media_type="application/json" if seen[2] else None)
    return s.sid, key


def remember(m: Mock, slot: tuple[str, str], request: Request, body: bytes, resp: Response) -> Response:
    m.idempotency[slot] = (fingerprint(request, body), resp.status_code, bytes(resp.body))
    return resp


# —— 第 1 节 鉴权 ——


@router.post("/v1/auth/login")
async def login(request: Request) -> Response:
    m = mock_of(request)
    doc = await body_of(request)
    check_request(m, "auth-login", "request", doc)
    if m.login_failures >= MAX_LOGIN_FAILURES:
        raise Fail("rate_limited", retry_after=60)
    if doc["inviteCode"].strip() != INVITE_CODE:
        m.login_failures += 1
        raise Fail("invalid_invite")
    m.login_failures = 0
    s = m.new_session()
    resp = ok(m, "auth-login", 200, me_doc(m, s))
    resp.set_cookie(
        COOKIE,
        s.sid,
        max_age=30 * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",  # 本地 http 下不带 Secure（B-1）
        path="/",
    )
    return resp


@router.post("/v1/auth/logout")
async def logout(request: Request) -> Response:
    m = mock_of(request)
    sid = request.cookies.get(COOKIE)
    if sid:
        m.sessions.pop(sid, None)
    resp = Response(status_code=204)
    resp.delete_cookie(COOKIE, path="/")
    return resp


def me_doc(m: Mock, s: Session) -> Json:
    doc = m.rendered("me.json", userRef=s.user_ref)
    pt = m.active(s)
    doc["activePlaythrough"] = m.active_ref(pt) if pt else None
    if pt is not None:
        doc["limits"]["voiceMinutesLeft"] = pt.voice["minutesLeftToday"]
    return doc


@router.get("/v1/me")
async def me(request: Request) -> Response:
    m = mock_of(request)
    return ok(m, "me", 200, me_doc(m, session_of(request)))


# —— 第 2 节 ——


@router.get("/v1/books/{book_id}/manifest")
async def manifest(request: Request, book_id: str) -> Response:
    m = mock_of(request)
    session_of(request)
    doc = m.manifest(book_id) if not m.book.request_errors("manifest", "params", {"bookId": book_id}) else None
    if doc is None:
        raise Fail("not_found")
    resp = ok(m, "manifest", 200, doc)
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


@router.post("/v1/playthroughs")
async def create_playthrough(request: Request) -> Response:
    m = mock_of(request)
    s = session_of(request)
    raw = await request.body()
    slot = idempotent(request, s, raw)
    if isinstance(slot, Response):
        return slot
    doc = await body_of(request)
    check_request(m, "playthroughs-create", "request", doc)
    book = m.manifest(doc["bookId"])
    if book is None or doc["roleId"] not in {r["roleId"] for r in book["roles"]}:
        log.info("没有这个书或身份：%s %s", doc["bookId"], doc["roleId"])
        raise Fail("invalid_request")
    active = m.active(s)
    if active is not None:
        return remember(
            m, slot, request, raw, fail_response(m, Fail("active_playthrough_exists", active=m.active_ref(active)))
        )
    pt = m.create(s, doc["roleId"])
    resp = ok(m, "playthroughs-create", 201, {"playthroughId": pt.pid, "snapshot": pt.current_snapshot()})
    return remember(m, slot, request, raw, resp)


@router.get("/v1/playthroughs/{pid}/snapshot")
async def snapshot(request: Request, pid: str) -> Response:
    m = mock_of(request)
    return ok(m, "snapshot", 200, playthrough_of(request, pid).current_snapshot())


def int_query(request: Request, name: str, default: int | None = None) -> Any:
    v = request.query_params.get(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return v  # 交给 Schema 报错


@router.get("/v1/playthroughs/{pid}/events")
async def events(request: Request, pid: str) -> Response:
    m = mock_of(request)
    pt = playthrough_of(request, pid)
    query = {
        k: v
        for k, v in {"afterSeq": int_query(request, "afterSeq"), "limit": int_query(request, "limit")}.items()
        if v is not None
    }
    check_request(m, "events", "query", query)
    evs = pt.events_after(query.get("afterSeq", 0), query.get("limit", 50))
    return ok(m, "events", 200, {"events": evs, "lastSeq": pt.last_seq})


@router.get("/v1/playthroughs/{pid}/timeline")
async def timeline(request: Request, pid: str) -> Response:
    m = mock_of(request)
    pt = playthrough_of(request, pid)
    doc = m.rendered("timeline.json", pt)
    doc["lastSeq"] = pt.last_seq
    return ok(m, "timeline", 200, doc)


@router.get("/v1/playthroughs/{pid}/why")
async def why(request: Request, pid: str) -> Response:
    m = mock_of(request)
    pt = playthrough_of(request, pid)
    query = dict(request.query_params)
    check_request(m, "why", "query", query)
    doc = m.rendered("why.json", pt)
    doc["target"] = query["target"]
    known = {ev["eventId"]: ev["seq"] for ev in pt.events}
    for step in doc["chain"]:
        if step.get("eventId") in known:
            step["seq"] = known[step["eventId"]]  # 这一局真的发过这个事件时，序号对上
    return ok(m, "why", 200, doc)


@router.get("/v1/playthroughs/{pid}/memories")
async def memories(request: Request, pid: str) -> Response:
    """固定数据去掉删过的记忆；删了约定的记忆，那个约定变 voided（照给，前端不显示）。"""
    m = mock_of(request)
    pt = playthrough_of(request, pid)
    doc = m.rendered("memories.json", pt)
    for ch in doc["characters"]:
        for deleted in pt.deleted_memories.values():
            if deleted["character"] == ch["character"]:
                ch["relationLabel"], ch["relationLevel"] = deleted["relationLabel"], deleted["relationLevel"]
            for promise in ch["promises"]:
                if promise["promiseId"] == deleted["promiseVoided"]:
                    promise["status"] = "voided"
        ch["memories"] = [x for x in ch["memories"] if x["memoryId"] not in pt.deleted_memories]
    return ok(m, "memories", 200, doc)


def memory_fixture(m: Mock, pt: Playthrough, rel: str, memory_id: str) -> Json:
    """按记忆挑固定数据（文件里以记忆的名字为键）；不认识或删过的记忆回 404。"""
    if m.book.request_errors("memory-impact", "params", {"id": pt.pid, "memoryId": memory_id}):
        raise Fail("not_found")
    names = {v: k.removeprefix("mem:") for k, v in pt.names.items() if k.startswith("mem:")}
    table = m.rendered(rel, pt, memoryId=memory_id)
    if memory_id in pt.deleted_memories or names.get(memory_id) not in table:
        raise Fail("not_found")
    return table[names[memory_id]]


@router.get("/v1/playthroughs/{pid}/memories/{memory_id}/impact")
async def memory_impact(request: Request, pid: str, memory_id: str) -> Response:
    m = mock_of(request)
    pt = playthrough_of(request, pid)
    return ok(m, "memory-impact", 200, memory_fixture(m, pt, "memory-impact.json", memory_id))


@router.delete("/v1/playthroughs/{pid}/memories/{memory_id}")
async def memory_delete(request: Request, pid: str, memory_id: str) -> Response:
    m = mock_of(request)
    pt = playthrough_of(request, pid)
    raw = await request.body()
    slot = idempotent(request, session_of(request), raw)
    if isinstance(slot, Response):
        return slot
    doc = memory_fixture(m, pt, "memory-delete.json", memory_id)
    resp = ok(m, "memory-delete", 200, doc)
    pt.deleted_memories[memory_id] = doc
    if doc["promiseVoided"]:
        await m.live(pt).emit(forget_commit(m, pt, memory_id, doc), source="memory-delete")
    if doc["sessionRebuilt"]:
        await rebuild(m, pt, doc["character"])
    return remember(m, slot, request, raw, resp)


FORGET_SUMMARY = "{name}は、その約束を覚えていない"


def forget_commit(m: Mock, pt: Playthrough, memory_id: str, doc: Json) -> Json:
    """删掉约定类的记忆：追加一条 forget 事件，约定变 voided，经 commit 推送（2.7；contracts 第 4 节删除语义第 4 条）。
    这条事件不进 /timeline，也不进「その頃」；前端收到后什么也不显示。"""
    promise_id = doc["promiseVoided"]
    promise = next(
        (
            {"promiseId": p["promiseId"], "character": ch["character"], "text": p["text"], "direction": p["direction"]}
            for ch in m.rendered("memories.json", pt)["characters"]
            for p in ch["promises"]
            if p["promiseId"] == promise_id
        ),
        None,
    )
    if promise is None:
        raise ValueError(f"memories.json 里没有约定 {promise_id}")
    names = {c["id"]: c["name"] for c in (m.manifest("hashire-merosu") or {"characters": []})["characters"]}
    clock = pt.snapshot["clock"]
    event = {
        "eventId": pt.named_id("ev", f"forget-{memory_id}"),
        "t": clock["t"],
        "dt": 0,
        "tLabel": clock["tLabel"],
        "type": "forget",
        "actor": "player",
        "forPlayer": False,
        "place": pt.snapshot["player"]["place"],
        "summary": FORGET_SUMMARY.format(name=names.get(doc["character"], doc["character"])),
        "causes": [],
        "visibleEffects": [],
        "promise": {"promiseId": promise_id, "change": "voided"},
        "keyMoment": False,
        "supersedes": None,
    }
    return {
        "type": "commit",
        "events": [event],
        "patch": {"clock": {"t": clock["t"], "tLabel": clock["tLabel"]}},
        "memories": [
            {
                "character": doc["character"],
                "change": "deleted",
                "memoryId": memory_id,
                "relationLabel": doc["relationLabel"],
                "relationLevel": doc["relationLevel"],
            }
        ],
        "promises": [{**promise, "status": "voided"}],
        "narration": [],
        "cue": None,
        "reveal": None,
    }


@router.get("/v1/playthroughs/{pid}/ending")
async def ending(request: Request, pid: str) -> Response:
    m = mock_of(request)
    pt = playthrough_of(request, pid)
    if pt.ending_id is None:
        raise Fail("not_found")
    if not pt.ending_ready:
        return ok(m, "ending", 202, {"status": "pending", "etaSeconds": 10})
    doc = m.rendered("ending.json", pt)
    # 删过记忆的人物，结局里不写「他记得你」（contracts 第 4 节删除语义第 2 条）：卡片上去掉他那一行
    forgot = {d["character"] for d in pt.deleted_memories.values()}
    doc["card"]["characterLines"] = [x for x in doc["card"]["characterLines"] if x["character"] not in forgot]
    return ok(m, "ending", 200, doc)


@router.delete("/v1/playthroughs/{pid}")
async def delete_playthrough(request: Request, pid: str) -> Response:
    m = mock_of(request)
    pt = playthrough_of(request, pid)
    raw = await request.body()
    slot = idempotent(request, session_of(request), raw)
    if isinstance(slot, Response):
        return slot
    pt.status = "deleted"
    live = m.lives.pop(pt.pid, None)
    if live is not None:
        live.stop()
        if live.link is not None:
            link, live.link = live.link, None
            await link.close(4004, "deleted")  # 这一局已被删除（第 4 节）
    return remember(m, slot, request, raw, Response(status_code=202))


@router.post("/v1/telemetry")
async def telemetry(request: Request) -> Response:
    """登录前（app_open）也收，所以不查会话。"""
    m = mock_of(request)
    doc = await body_of(request)
    check_request(m, "telemetry", "request", doc)
    log.debug("遥测 %d 条", len(doc["events"]))
    return Response(status_code=204)


@router.post("/v1/test/playthroughs/{pid}/advance")
async def test_advance(request: Request, pid: str) -> Response:
    m = mock_of(request)
    pt = playthrough_of(request, pid)
    doc = await body_of(request)
    check_request(m, "test-advance", "request", doc)
    await m.live(pt).emit(m.advance(pt, doc["minutes"]), source="advance")
    return ok(m, "test-advance", 200, pt.current_snapshot())


# —— /__mock/*：mock 专用，不进契约 ——


@control.get("/scenarios")
async def list_scenarios(request: Request) -> Response:
    m = mock_of(request)
    return JSONResponse({"current": m.scenario, "names": scripts.names(m.config.sessions_dir)})


@control.post("/scenario")
async def set_scenario(request: Request) -> Response:
    m = mock_of(request)
    doc = await body_of(request)
    try:
        m.set_scenario(str(doc["name"]))
    except (KeyError, TypeError, ScriptError) as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    return JSONResponse({"current": m.scenario})


@control.post("/expire-session")
async def expire_session(request: Request) -> Response:
    """当前 Cookie 失效：之后 REST 回 401，WebSocket 以 4001 关闭（开着的也关）。"""
    m = mock_of(request)
    s = m.sessions.get(request.cookies.get(COOKIE) or "")
    if s is None:
        return JSONResponse({"expired": False}, status_code=404)
    s.expired = True
    for pt in m.playthroughs.values():
        live = m.lives.get(pt.pid)
        if pt.owner == s.sid and live is not None and live.link is not None:
            link, live.link = live.link, None
            await link.close(4001, "unauthenticated")
    return JSONResponse({"expired": True})


@control.post("/drop")
async def drop(request: Request) -> Response:
    """断开当前 Cookie 的连接，不发 goaway、不给关闭码，模拟断网。"""
    m = mock_of(request)
    s = m.sessions.get(request.cookies.get(COOKIE) or "")
    dropped = 0
    for pt in m.playthroughs.values():
        live = m.lives.get(pt.pid)
        if s is not None and pt.owner == s.sid and live is not None and live.link is not None:
            link, live.link = live.link, None
            if isinstance(link, WsLink):
                await link.drop()
                dropped += 1
    return JSONResponse({"dropped": dropped})


@control.post("/reset")
async def reset(request: Request) -> Response:
    """清空全部会话和局（e2e 每个测试开头用）。"""
    mock_of(request).reset()
    return JSONResponse({"reset": True})
