"""api-contract 第 3、4 节的 WebSocket：握手检查、协议上固定的回应、其余交给剧本。

不靠剧本、mock 自己回的：hello → welcome 和补发的 commit；ping → pong；near / focus → session_preparing /
session_ready；turn_retract → turn_retract_result（和 turn_settled）；不合 Schema 的消息 → error invalid_request；
act_choose 选了不存在的去处 → error invalid_choice。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from zoujin_backend.mock.core import COOKIE, Mock
from zoujin_backend.mock.live import Link, Live
from zoujin_backend.mock.origin import origin_allowed
from zoujin_backend.mock.state import Playthrough

log = logging.getLogger("zoujin.mock")

Json = Any

SESSION_ETA_MS = 800  # 预热和切换人物（api-contract 3.5 的例子）
REBUILD_ETA_MS = 1000  # 会话重建约 1 秒（3.6、2.7）


class WsLink(Link):
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.closed = asyncio.Event()
        self.dropped = False

    async def send_json(self, msg: Json) -> None:
        if not self.closed.is_set():
            try:
                await self.ws.send_text(json.dumps(msg, ensure_ascii=False, separators=(",", ":")))
            except (RuntimeError, WebSocketDisconnect):
                self.closed.set()

    async def send_bytes(self, data: bytes) -> None:
        if not self.closed.is_set():
            try:
                await self.ws.send_bytes(data)
            except (RuntimeError, WebSocketDisconnect):
                self.closed.set()

    async def close(self, code: int, reason: str = "") -> None:
        if not self.closed.is_set():
            self.closed.set()
            with contextlib.suppress(RuntimeError, WebSocketDisconnect):
                if self.ws.application_state == WebSocketState.CONNECTED:
                    await self.ws.close(code, reason)

    async def drop(self) -> None:
        """/__mock/drop：不发关闭帧就结束，uvicorn 直接断开 TCP，客户端看到 1006（模拟断网）。"""
        self.dropped = True
        self.closed.set()


def gate(m: Mock, ws: WebSocket, pid: str) -> tuple[int, Playthrough | None]:
    """握手检查 Cookie 和 Origin（第 0 节「跨站防护」），再看这一局（第 4 节的关闭码）。"""
    s = m.session(ws.cookies.get(COOKIE))
    if s is None:
        return 4001, None
    if not origin_allowed(ws.headers, ws.url.scheme, m.config.allow_origins):
        return 4003, None
    pt = m.playthroughs.get(pid)
    if pt is None:
        return 4003, None
    if pt.status == "deleted":
        return 4004, None
    if pt.owner != s.sid:
        return 4003, None
    return 0, pt


async def endpoint(ws: WebSocket, pid: str) -> None:
    m: Mock = ws.app.state.mock
    await ws.accept()
    code, pt = gate(m, ws, pid)
    if pt is None:
        await ws.close(code)
        return
    live = m.live(pt)
    link = WsLink(ws)
    await live.attach(link)
    reader = asyncio.create_task(read_loop(m, pt, live, link))
    closed = asyncio.create_task(link.closed.wait())
    try:
        await asyncio.wait({reader, closed}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        reader.cancel()
        closed.cancel()
        await live.detach(link)


async def read_loop(m: Mock, pt: Playthrough, live: Live, link: WsLink) -> None:
    ws = link.ws
    while True:
        try:
            frame = await ws.receive()
        except (RuntimeError, WebSocketDisconnect):
            break
        if frame["type"] == "websocket.disconnect":
            break
        if frame.get("bytes") is not None:
            continue  # 上行麦克风音频：mock 不听
        try:
            msg = json.loads(frame.get("text") or "")
        except json.JSONDecodeError:
            msg = None
        errs = ["不是 JSON"] if msg is None else m.book.client_errors(msg)
        if errs:
            log.info("客户端消息不合 Schema：%s", "; ".join(errs[:3]))
            await live.emit(error_msg("invalid_request", "うまく送れませんでした。"))
            continue
        await handle(m, pt, live, msg)


def error_msg(code: str, message: str) -> Json:
    return {"type": "error", "error": {"code": code, "message": message, "retryable": False, "retryAfterSeconds": None}}


async def handle(m: Mock, pt: Playthrough, live: Live, msg: Json) -> None:
    t = msg["type"]
    pt.on_received(msg)
    if t == "hello":
        await live.emit(pt.welcome())
        for c in pt.commits_after(msg["lastSeq"]):
            if live.link is not None:
                await live.link.send_json(c)  # 发的时候已经自检过
        if live.task is None:
            m.start_script(pt)  # 第一次 hello 开始剧本；这条 hello 不交给剧本
            return
        pt.warm.clear()  # 重连：会话要重新准备（reason = reconnect）
        pt.reconnected = True
    elif t == "ping":
        await live.emit({"type": "pong"})
    elif t == "near":
        await prepare(m, pt, live, msg["character"], "switch")
    elif t == "focus":
        await focus(m, pt, live, msg["character"])
    elif t == "turn_retract":
        await retract(m, pt, live, msg["turnId"])
    elif t in ("activity_start", "text"):
        await live.interrupt(msg["turnId"])
    elif t == "act_choose" and not choice_ok(pt, msg):
        await live.emit(error_msg("invalid_choice", "その行き先は選べません。"))
        return
    elif t == "confirm_answer" and not answer_ok(pt, msg):
        log.info("confirm_answer 对不上现在的确认（%s），忽略", msg["draftId"])
        return  # 已经结束（超时、回答过）的确认，不交给剧本
    if t not in ("ping",):
        live.deliver(msg)


async def prepare(m: Mock, pt: Playthrough, live: Live, character: str, reason: str) -> float:
    if character in pt.warm:
        return pt.warm[character]
    if pt.reconnected and reason == "switch":
        reason = "reconnect"
        pt.reconnected = False
    eta = REBUILD_ETA_MS if reason == "rebuild" else SESSION_ETA_MS
    await live.emit({"type": "session_preparing", "character": character, "reason": reason, "etaMs": eta})
    pt.warm[character] = time.monotonic() + eta / 1000 * m.config.speed
    return pt.warm[character]


async def focus(m: Mock, pt: Playthrough, live: Live, character: str) -> None:
    ready_at = await prepare(m, pt, live, character, "switch")

    async def ready() -> None:
        await asyncio.sleep(max(0.0, ready_at - time.monotonic()))
        if pt.focused == character:
            await live.emit(
                {"type": "session_ready", "character": character, "voiceAvailable": not pt.voice["degraded"]}
            )

    asyncio.get_running_loop().create_task(ready())


async def rebuild(m: Mock, pt: Playthrough, character: str | None) -> None:
    """作废一轮、删除记忆后重建这个人物的会话（3.6、2.7）。"""
    live = m.lives.get(pt.pid)
    if live is None or character is None:
        return
    pt.warm.pop(character, None)
    await prepare(m, pt, live, character, "rebuild")
    if pt.focused == character:
        await focus(m, pt, live, character)


async def retract(m: Mock, pt: Playthrough, live: Live, turn_id: str) -> None:
    """3.6：判完之前能作废；判完了回 too_late。"""
    if turn_id in pt.settled:
        await live.emit({"type": "turn_retract_result", "turnId": turn_id, "status": "too_late"})
        return
    pt.retracted.add(turn_id)
    await live.emit({"type": "turn_retract_result", "turnId": turn_id, "status": "retracted"})
    await live.emit({"type": "turn_settled", "turnId": turn_id, "outcome": "retracted", "eventIds": [], "minutes": 0})
    character = pt.last_turn.character if pt.last_turn and pt.last_turn.turn_id == turn_id else pt.focused
    await rebuild(m, pt, character)


def answer_ok(pt: Playthrough, msg: Json) -> bool:
    c = pt.confirm
    return c is not None and c["draftId"] == msg["draftId"] and msg["optionId"] in {o["optionId"] for o in c["options"]}


def choice_ok(pt: Playthrough, msg: Json) -> bool:
    if pt.act_end is None:
        return False
    options = {o["optionId"]: o for o in pt.act_end["options"]}
    if msg["optionId"] in pt.plan_options:
        return "enRouteChoice" not in msg
    option = options.get(msg["optionId"])
    if option is None:
        return False
    if "enRouteChoice" in msg:
        en_route = option.get("enRoute")
        return en_route is not None and 0 <= msg["enRouteChoice"] < len(en_route["choices"])
    return True
