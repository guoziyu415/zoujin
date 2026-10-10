"""api-contract 第 3、4 节的 WebSocket（B-0 第 5 条做的那些消息）。

一轮语音：`activity_start` → 上行音频 → `activity_end` → 假 Live 回玩家字幕、人物音频和字幕、`turn_complete`
→ 写原话和这一轮的任务 → 叫叙事者 → 叙事者提交后 NOTIFY → 推 `commit` 和 `turn_settled`。文字一轮把前半段换成 `text`。

打断（3.2）：人物还在说的时候来了新的一轮，旧的一轮停下（`interrupted`、说到一半的定稿），照样交给叙事者；
人物已经 `turn_complete`、定稿还没到的，不算打断，等定稿到了照常交。断线时人物还没说完的一轮记成 `lost`
（第 4 节 `lastTurn.status`），不交给叙事者；已经说完的照常交。

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
from sqlalchemy import func, select
from starlette.websockets import WebSocketState

from zoujin_backend import audio
from zoujin_backend.config import COOKIE
from zoujin_backend.db import store
from zoujin_backend.db.tables import events, playthroughs, turns, utterances
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
    text: str | None = None  # 文字一轮的原话
    ended: bool = False  # activity_end / text 收到了
    heard: str | None = None  # 玩家字幕：最新的半句，或定稿
    said: str | None = None  # 人物字幕：最新的半句，或定稿
    first_audio: float | None = None
    complete: bool = False  # turn_complete 发了（人物说完了）
    final: bool = False  # 人物的定稿发了
    lost: bool = False  # 断线时人物还没说完
    stream: asyncio.Task[None] | None = None  # 转发 Live 的回答；打断、断线时取消
    quiet: asyncio.Event = field(default_factory=asyncio.Event)  # 这一轮不会再往下发字幕和音频了
    prev: Turn | None = None  # 同一条连接上的前一轮：它交上去以后这一轮才交，叙事者按玩家说的顺序判
    submitted: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def speaking(self) -> bool:
        return self.stream is not None and not self.stream.done() and not self.complete


@dataclass
class Conn:
    gw: Gateway
    ws: WebSocket
    pid: str
    user_id: str
    sent_seq: int = -1  # 推到的 seq；hello 之前不推
    characters: dict[str, Json] = field(default_factory=dict)  # 这一局的人物（hello 时读）
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
        """判完的轮次推 turn_settled。这一轮的事件还有没推出去的（commit 在读事件日志之后才落地）就留到下一次，
        保证 turn_settled 在它自己的 commit 之后（3.4）。"""
        upto = func.max(events.c.seq).label("upto")
        async with self.gw.engine.connect() as c:
            rows = (
                await c.execute(
                    select(turns.c.turn_id, turns.c.outcome, turns.c.minutes, upto)
                    .select_from(
                        turns.outerjoin(
                            events,
                            (events.c.playthrough_id == turns.c.playthrough_id) & (events.c.turn_id == turns.c.turn_id),
                        )
                    )
                    .where(
                        turns.c.playthrough_id == self.pid,
                        turns.c.kind == "talk",
                        turns.c.status.in_(("done", "failed")),
                        turns.c.settled_at.is_not(None),
                    )
                    .group_by(turns.c.turn_id, turns.c.outcome, turns.c.minutes, turns.c.settled_at)
                    .order_by(turns.c.settled_at)
                )
            ).all()
        for r in rows:
            if r.turn_id in self.settled or (r.upto is not None and r.upto > self.sent_seq):
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
            pt = await self.gw.pt(c, self.pid)
        if pt is not None:
            self.characters = pt.book.characters
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
            "status": "settled" if row.status in ("done", "failed") else "lost" if row.status == "lost" else "pending",
            "playerText": texts.get("player"),
            "characterText": texts.get(row.character),
        }

    async def focus(self, character: str) -> None:
        if not self.characters.get(character, {}).get("talkable"):
            log.info("focus 的人物不存在或不能说话")
            await self.send(error_msg("invalid_request", "この人とは話せません。"))
            return
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

    async def _start(self, msg: Json, mode: str) -> Turn | None:
        if self.focused is None:
            log.info("%s 没有 focus 的人物", msg["type"])
            await self.send(error_msg("invalid_request", "話す相手を選んでください。"))
            return None
        await self._cut()
        prev = self.turn if self.turn is not None and self.turn.ended else None
        self.turn = Turn(msg["turnId"], msg["turnSeq"], self.focused, mode, self.sessions[self.focused], prev=prev)
        return self.turn

    async def _cut(self) -> None:
        """新的一轮打断还在说的人物（3.2 activity_start）：不再转发旧轮次的分片，旧轮次的 interrupted 和
        说到一半的定稿先发完，新的一轮再开始。旧轮次照样交给叙事者。"""
        old = self.turn
        if old is not None and old.speaking:
            assert old.stream is not None
            old.stream.cancel()
            await old.quiet.wait()

    def drop(self) -> None:
        """连接断了：人物还没说完的一轮记成 lost；已经说完、等定稿的照常交。"""
        old = self.turn
        if old is not None and old.speaking:
            assert old.stream is not None
            old.lost = True
            old.stream.cancel()

    def audio_in(self, frame: bytes) -> None:
        t = self.turn
        if len(frame) < 5 or frame[0] != FRAME_MIC or t is None or t.ended or t.mode != "voice":
            return
        if int.from_bytes(frame[1:5], "big") != t.turn_seq:
            return  # 已结束轮次的上行分片丢掉（3.1）
        for ev in t.session.audio_in(frame[5:]):
            if ev.kind == "input_partial":
                t.heard = ev.text
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
        if t.mode == "text":
            t.heard = t.text
        t.stream = asyncio.ensure_future(self._stream(t))
        self.gw.spawn(self._finish(t))

    async def _stream(self, t: Turn) -> None:
        """假 Live 的回答转成下行消息。被打断、断线时这个任务被取消，停在哪就是哪。"""
        released = time.monotonic()
        async for ev in t.session.respond(t.text):
            if ev.kind == "input_final":
                t.heard = ev.text
                await self.send(
                    {"type": "transcript", "turnId": t.turn_id, "speaker": "player", "text": ev.text, "final": True}
                )
            elif ev.kind == "audio":
                if t.first_audio is None:
                    t.first_audio = time.monotonic()
                await self.send_bytes(audio.frame(t.turn_seq, ev.pcm))
            elif ev.kind == "output_partial":
                t.said = ev.text
                await self.send(
                    {"type": "transcript", "turnId": t.turn_id, "speaker": t.character, "text": ev.text, "final": False}
                )
            elif ev.kind == "turn_complete":
                ms = None if t.first_audio is None else round((t.first_audio - released) * 1000)
                t.complete = True
                await self.send(
                    {
                        "type": "turn_complete",
                        "turnId": t.turn_id,
                        "audio": t.first_audio is not None,
                        "metrics": {"serverReleaseToFirstAudioMs": ms},
                    }
                )
            elif ev.kind == "output_final":
                t.said = ev.text
                await self._final(t)

    async def _final(self, t: Turn) -> None:
        t.final = True
        await self.send(
            {
                "type": "transcript",
                "turnId": t.turn_id,
                "speaker": t.character,
                "text": t.said,
                "final": True,
                "source": "live",
            }
        )

    async def _finish(self, t: Turn) -> None:
        """等人物说完（或被打断、断线），再把这一轮交给叙事者。被打断的补 interrupted 和说到一半的定稿（3.3）；
        断线时还没说完的记成 lost。"""
        assert t.stream is not None
        await asyncio.wait({t.stream})
        failed = not t.stream.cancelled() and t.stream.exception() is not None
        if failed:
            log.error("Live 的回答中途出错（%s）", t.turn_id, exc_info=t.stream.exception())
        if not t.lost:
            if t.stream.cancelled() and not t.complete:
                await self.send({"type": "interrupted", "turnId": t.turn_id})
            if not t.final and t.said is not None:  # 人物还没出字就被打断的，没有定稿（同「没回答」的轮）
                await self._final(t)
        t.quiet.set()
        if t.prev is not None:
            await t.prev.submitted.wait()
            t.prev = None
        try:
            await self._submit(t)
        finally:
            t.submitted.set()

    async def _submit(self, t: Turn) -> None:
        """原话和这一轮的任务同一个事务写进去，再叫叙事者（turn_complete 之后）。lost 的只留记录，不叫叙事者。"""
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
                status="lost" if t.lost else "pending",
            )
            await store.add_utterance(c, self.gw.ids, self.pid, t.turn_id, speaker="player", text=t.heard, t=now_t)
            await store.add_utterance(
                c, self.gw.ids, self.pid, t.turn_id, speaker=t.character, text=t.said, t=now_t, source="live"
            )
        if not t.lost:
            self.gw.kick(self.pid)

    async def handle(self, msg: Json) -> None:
        t = msg["type"]
        if t == "hello":
            await self.hello(msg)
        elif t == "ping":
            await self.send({"type": "pong"})
        elif self.sent_seq < 0:
            log.info("hello 之前的 %s", t)
            await self.send(error_msg("invalid_request", "うまく送れませんでした。"))
        elif t == "focus":
            await self.focus(msg["character"])
        elif t == "unfocus":
            self.focused = None
        elif t == "activity_start":
            await self._start(msg, "voice")
        elif t == "activity_end":
            turn = self.turn
            if turn is not None and turn.turn_id == msg["turnId"] and not turn.ended:
                self.respond(turn)
        elif t == "text":
            turn = await self._start(msg, "text")
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
        conn.drop()
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
        errs = ["不是 JSON"] if msg is None else conn.gw.schemas.client_errors(msg)
        if errs:
            log.info("客户端消息不合 Schema：%s", "; ".join(errs[:3]))
            await conn.send(error_msg("invalid_request", "うまく送れませんでした。"))
            continue
        try:
            await conn.handle(msg)
        except Exception:
            log.exception("处理 %s 出错", msg["type"])
            err = error_msg("internal", "エラーが起きました。")
            err["error"]["retryable"] = True
            await conn.send(err)
