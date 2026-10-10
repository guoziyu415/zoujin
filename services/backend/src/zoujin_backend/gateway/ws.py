"""api-contract 第 3、4 节的 WebSocket（B-0 第 5 条做的那些消息）。

一轮语音：`activity_start` → 上行音频 → `activity_end` → 假 Live 回玩家字幕、人物音频和字幕、`turn_complete`
→ 写原话和这一轮的任务 → 叫叙事者 → 叙事者提交后 NOTIFY → 推 `commit` 和 `turn_settled`。文字一轮把前半段换成 `text`。

B-0 没有真 Live，`hello.fakeVoice` 给不给都用假 Live。不在 B-0 里的消息（`near`、`turn_retract`、`action` 等）
忽略，只在日志里记类型名。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from starlette.websockets import WebSocketState

from zoujin_backend import audio
from zoujin_backend.config import COOKIE
from zoujin_backend.db import store
from zoujin_backend.db.tables import playthroughs, turns, utterances
from zoujin_backend.gateway import auth
from zoujin_backend.gateway.core import VOICE_MINUTES, Gateway
from zoujin_backend.models.live import LiveSession
from zoujin_backend.origin import origin_allowed
from zoujin_backend.projection import PENDING
from zoujin_backend.schemas import SchemaError

log = logging.getLogger("zoujin.gateway")

Json = Any

SESSION_ETA_MS = 800  # 预热和切换人物（3.5 的例子）
FRAME_MIC = 0x01
VOICE = {"enabled": True, "degraded": False, "minutesLeftToday": VOICE_MINUTES}


def error_msg(code: str, message: str) -> Json:
    return {"type": "error", "error": {"code": code, "message": message, "retryable": False, "retryAfterSeconds": None}}


@dataclass
class Turn:
    """连接上正在进行的一轮（还没交给叙事者）。"""

    turn_id: str
    turn_seq: int
    character: str
    mode: str  # voice / text
    session: LiveSession
    text: str | None = None
    ended: bool = False
    task: asyncio.Task[None] | None = None


@dataclass
class Conn:
    gw: Gateway
    ws: WebSocket
    pid: str
    user_id: str
    sent_seq: int = -1  # 推到的 seq；hello 之前不推
    focused: str | None = None
    sessions: dict[str, LiveSession] = field(default_factory=dict)
    ready_at: dict[str, float] = field(default_factory=dict)
    turn: Turn | None = None
    settled: set[str] = field(default_factory=set)
    closed: asyncio.Event = field(default_factory=asyncio.Event)
    push_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # —— 发 ——

    async def send(self, msg: Json) -> None:
        """用生成的类型构造、按 Schema 校验后再发；不合契约的不发，记日志。"""
        try:
            out = self.gw.schemas.server_message(msg)
        except SchemaError:
            log.exception("不发 %s：不合契约", msg.get("type"))
            return
        if self.gw.on_send is not None:
            self.gw.on_send(out)
        async with self.send_lock:
            if self.closed.is_set():
                return
            try:
                await self.ws.send_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
            except (RuntimeError, WebSocketDisconnect):
                self.closed.set()

    async def send_bytes(self, data: bytes) -> None:
        async with self.send_lock:
            if self.closed.is_set():
                return
            try:
                await self.ws.send_bytes(data)
            except (RuntimeError, WebSocketDisconnect):
                self.closed.set()

    async def close(self, code: int, reason: str = "") -> None:
        async with self.send_lock:
            if self.closed.is_set():
                return
            self.closed.set()
            with contextlib.suppress(RuntimeError, WebSocketDisconnect):
                if self.ws.application_state == WebSocketState.CONNECTED:
                    await self.ws.close(code, reason)

    # —— 推 commit 和 turn_settled ——

    async def push(self) -> None:
        """把 sent_seq 之后提交了的都推出去（hello 补发、NOTIFY 都走这里），再推判完了的轮次的 turn_settled。"""
        async with self.push_lock:
            if self.sent_seq < 0:
                return
            msgs, self.sent_seq = await self.gw.commits(self.pid, self.sent_seq)
            for m in msgs:
                await self.send(m)
            await self._settled()

    async def _settled(self) -> None:
        async with self.gw.engine.connect() as c:
            rows = (
                await c.execute(
                    select(turns.c.turn_id, turns.c.outcome, turns.c.minutes).where(
                        turns.c.playthrough_id == self.pid,
                        turns.c.kind == "talk",
                        turns.c.status.in_(("done", "failed")),
                        turns.c.settled_at.is_not(None),
                    )
                )
            ).all()
        for r in rows:
            if r.turn_id in self.settled:
                continue
            self.settled.add(r.turn_id)
            ids = await self._visible_ids(r.turn_id)
            await self.send(
                {
                    "type": "turn_settled",
                    "turnId": r.turn_id,
                    "outcome": r.outcome or "no_response",
                    "eventIds": ids,
                    "minutes": int(r.minutes or 0),
                }
            )

    async def _visible_ids(self, turn_id: str) -> list[str]:
        evs = await self.gw.visible_events(self.pid, 0, 10_000)
        return [e["eventId"] for e in evs if e.get("turnId") == turn_id]

    async def on_commit(self, payload: Json) -> None:
        await self.push()

    # —— 收 ——

    async def hello(self, msg: Json) -> None:
        async with self.gw.engine.connect() as c:
            last_seq = int(
                await c.scalar(select(playthroughs.c.last_seq).where(playthroughs.c.playthrough_id == self.pid)) or 0
            )
            settled = (
                await c.execute(
                    select(turns.c.turn_id).where(
                        turns.c.playthrough_id == self.pid,
                        turns.c.kind == "talk",
                        turns.c.status.in_(("done", "failed")),
                    )
                )
            ).scalars()
            self.settled = set(settled)  # 这条连接之前判完的不再推 turn_settled
            last_turn = await self._last_turn(c)
        await self.send(
            {
                "type": "welcome",
                "lastSeq": last_seq,
                "voice": dict(VOICE),
                "lastTurn": last_turn,
                "pending": dict(PENDING),
            }
        )
        async with self.push_lock:
            self.sent_seq = min(int(msg["lastSeq"]), last_seq)
        await self.push()

    async def _last_turn(self, c: Any) -> Json | None:
        row = (
            await c.execute(
                select(turns.c.turn_id, turns.c.character, turns.c.status)
                .where(turns.c.playthrough_id == self.pid, turns.c.kind == "talk")
                .order_by(turns.c.created_at.desc())
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        texts = dict(
            (
                await c.execute(
                    select(utterances.c.speaker, utterances.c.text).where(utterances.c.turn_id == row.turn_id)
                )
            ).all()
        )
        return {
            "turnId": row.turn_id,
            "character": row.character,
            "status": "settled" if row.status in ("done", "failed") else "pending",
            "playerText": texts.get("player"),
            "characterText": texts.get(row.character),
        }

    async def focus(self, character: str) -> None:
        self.focused = character
        if character not in self.sessions:
            self.sessions[character] = await self.gw.live.open(character)
            eta = SESSION_ETA_MS
            await self.send({"type": "session_preparing", "character": character, "reason": "switch", "etaMs": eta})
            self.ready_at[character] = time.monotonic() + eta / 1000 * self.gw.settings.speed

        async def ready() -> None:
            await asyncio.sleep(max(0.0, self.ready_at[character] - time.monotonic()))
            if self.focused == character:
                await self.send({"type": "session_ready", "character": character, "voiceAvailable": True})

        self.gw.spawn(ready())

    def _start(self, msg: Json, mode: str) -> Turn | None:
        self._cut()
        if self.focused is None:
            log.info("%s 没有 focus 的人物，忽略", msg["type"])
            return None
        self.turn = Turn(msg["turnId"], msg["turnSeq"], self.focused, mode, self.sessions[self.focused])
        return self.turn

    def _cut(self) -> None:
        """新的一轮打断正在说的人物：不再转发旧轮次的分片（3.2 activity_start）。"""
        old = self.turn
        if old is not None and old.task is not None and not old.task.done():
            old.task.cancel()

    def audio_in(self, frame: bytes) -> None:
        t = self.turn
        if len(frame) < 5 or frame[0] != FRAME_MIC or t is None or t.ended or t.mode != "voice":
            return
        if int.from_bytes(frame[1:5], "big") != t.turn_seq:
            return  # 已结束轮次的上行分片丢掉（3.1）
        for ev in t.session.audio_in(frame[5:]):
            if ev.kind == "input_partial":
                self.gw.spawn(
                    self.send(
                        {
                            "type": "transcript",
                            "turnId": t.turn_id,
                            "speaker": "player",
                            "text": ev.text,
                            "final": False,
                        }
                    )
                )

    def respond(self, t: Turn) -> None:
        t.ended = True
        t.task = asyncio.ensure_future(self._respond(t))

    async def _respond(self, t: Turn) -> None:
        """假 Live 的回答转成下行消息，说完把这一轮交给叙事者。"""
        released = time.monotonic()
        first_audio: float | None = None
        player_text = t.text
        character_text: str | None = None
        async for ev in t.session.respond(t.text):
            if ev.kind == "input_final":
                player_text = ev.text
                await self.send(
                    {"type": "transcript", "turnId": t.turn_id, "speaker": "player", "text": ev.text, "final": True}
                )
            elif ev.kind == "audio":
                if first_audio is None:
                    first_audio = time.monotonic()
                await self.send_bytes(audio.frame(t.turn_seq, ev.pcm))
            elif ev.kind == "output_partial":
                await self.send(
                    {"type": "transcript", "turnId": t.turn_id, "speaker": t.character, "text": ev.text, "final": False}
                )
            elif ev.kind == "turn_complete":
                ms = None if first_audio is None else round((first_audio - released) * 1000)
                await self.send(
                    {
                        "type": "turn_complete",
                        "turnId": t.turn_id,
                        "audio": first_audio is not None,
                        "metrics": {"serverReleaseToFirstAudioMs": ms},
                    }
                )
            elif ev.kind == "output_final":
                character_text = ev.text
                await self.send(
                    {
                        "type": "transcript",
                        "turnId": t.turn_id,
                        "speaker": t.character,
                        "text": ev.text,
                        "final": True,
                        "source": "live",
                    }
                )
        await self._submit(t, player_text, character_text)

    async def _submit(self, t: Turn, player_text: str | None, character_text: str | None) -> None:
        """原话和这一轮的任务同一个事务写进去，再叫叙事者（turn_complete 之后）。"""
        async with self.gw.engine.begin() as c:
            st = await store.sim_state(c, self.pid)
            now_t = st["t"] if st is not None else 0
            exists = await c.scalar(select(turns.c.turn_id).where(turns.c.turn_id == t.turn_id))
            if exists is not None:
                log.info("这一轮已经交过了（%s）", t.turn_id)
                return
            await store.enqueue(
                c,
                self.gw.ids,
                self.pid,
                kind="talk",
                turn_id=t.turn_id,
                input_mode=t.mode,
                character=t.character,
                turn_seq=t.turn_seq,
            )
            await store.add_utterance(c, self.gw.ids, self.pid, t.turn_id, speaker="player", text=player_text, t=now_t)
            await store.add_utterance(
                c, self.gw.ids, self.pid, t.turn_id, speaker=t.character, text=character_text, t=now_t, source="live"
            )
        self.gw.kick(self.pid)

    async def handle(self, msg: Json) -> None:
        t = msg["type"]
        if t == "hello":
            await self.hello(msg)
        elif t == "ping":
            await self.send({"type": "pong"})
        elif t == "focus":
            await self.focus(msg["character"])
        elif t == "unfocus":
            self.focused = None
        elif t == "activity_start":
            self._start(msg, "voice")
        elif t == "activity_end":
            turn = self.turn
            if turn is not None and turn.turn_id == msg["turnId"] and not turn.ended:
                self.respond(turn)
        elif t == "text":
            turn = self._start(msg, "text")
            if turn is not None:
                turn.text = msg["text"]
                self.respond(turn)
        else:
            log.info("B-0 不处理 %s，忽略", t)


async def gate(gw: Gateway, ws: WebSocket, pid: str) -> tuple[int, str | None]:
    """握手：Cookie（4001）、Origin（4003）、这一局在不在（4004）、是不是你的（4003）。"""
    async with gw.engine.begin() as c:
        found = await auth.session_user(c, ws.cookies.get(COOKIE))
        if found is None:
            return 4001, None
        if not origin_allowed(ws.headers, ws.url.scheme, gw.settings.allow_origins):
            return 4003, None
        if gw.schemas.request_errors("snapshot", "params", {"id": pid}):
            return 4004, None
        owner = await c.scalar(select(playthroughs.c.user_ref).where(playthroughs.c.playthrough_id == pid))
    if owner is None:
        return 4004, None
    if owner != found[0]:
        return 4003, None
    return 0, found[0]


async def endpoint(ws: WebSocket, pid: str) -> None:
    gw: Gateway = ws.app.state.gw
    await ws.accept()
    code, user_id = await gate(gw, ws, pid)
    if user_id is None or gw.draining:
        await ws.close(code or 1012)
        return
    conn = Conn(gw, ws, pid, user_id)
    old = gw.conns.get(pid)
    gw.conns[pid] = conn
    if old is not None:
        await old.close(4009, "opened elsewhere")  # 同一局在别的标签页打开：新连接踢掉旧连接
    reader = asyncio.ensure_future(read_loop(conn))
    closed = asyncio.ensure_future(conn.closed.wait())
    try:
        await asyncio.wait({reader, closed}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        reader.cancel()
        closed.cancel()
        conn._cut()
        if gw.conns.get(pid) is conn:
            del gw.conns[pid]
        for s in conn.sessions.values():
            await s.close()


async def read_loop(conn: Conn) -> None:
    ws = conn.ws
    while True:
        try:
            frame = await ws.receive()
        except (RuntimeError, WebSocketDisconnect):
            break
        if frame["type"] == "websocket.disconnect":
            break
        if frame.get("bytes") is not None:
            conn.audio_in(frame["bytes"])
            continue
        try:
            msg = json.loads(frame.get("text") or "")
        except json.JSONDecodeError:
            msg = None
        if msg is None or conn.gw.schemas.client_errors(msg):
            log.info("客户端消息不合 Schema（%s）", msg.get("type") if isinstance(msg, dict) else "不是 JSON")
            await conn.send(error_msg("invalid_request", "うまく送れませんでした。"))
            continue
        try:
            await conn.handle(msg)
        except Exception:
            log.exception("处理 %s 出错", msg["type"])
            err = error_msg("internal", "エラーが起きました。")
            err["error"]["retryable"] = True
            await conn.send(err)
