"""api-contract 第 3、4 节的 WebSocket（B-0 第 5 条做的那些消息）。

一轮语音：`activity_start` → 上行音频 → `activity_end` → 假 Live 回玩家字幕、人物音频和字幕、`turn_complete`
→ 写原话和这一轮的任务 → 叫叙事者 → 叙事者提交后 NOTIFY → 推 `commit` 和 `turn_settled`。文字一轮把前半段换成 `text`。

打断（3.2）：人物还在说的时候来了新的一轮，旧的一轮停下（`interrupted`、说到一半的定稿），照样交给叙事者；
人物已经 `turn_complete`、定稿还没到的，不算打断，等定稿到了照常交。断线时人物还没说完的一轮记成 `lost`
（第 4 节 `lastTurn.status`），不交给叙事者；已经说完的照常交。

B-3 加了动作和幕末（3.8、3.11）：`action`、`act_choose`、`act_propose` 各写一行任务（`turns.kind` = action / choose /
plan）再叫叙事者；用声音说打算（`activity_start purpose: "act_plan"`）只转写、人物不回答，松开以后同样写 plan 任务。
叙事者判完把要推的消息按顺序记在 `turns.result.push`，这里推完那次提交的 `commit` 再照着推（`_results`）。
收了幕、还没选定时，`text`、`activity_start`（`act_plan` 除外）、`action` 回 `invalid_request`（第 5 节）。
落地带 `opener` 的，收到 `act_landed` 才让他先开口（`turn_started reason: "arrival"`），这一句不交给叙事者。

B-4 加了作废、识别改正和意图确认（3.6、3.9）：
- `turn_retract`：这一轮还在连接内存里（玩家还在说、人物还没说完、还没交给叙事者）就停下、写一行 `retracted`；
  已经交给叙事者、还没提交的在库里改成 `retracted`、原话清空（和叙事者的提交谁先拿到行锁谁算数）；别的 `too_late`。
  对话的一轮作废以后重建这个人物的会话（`session_preparing reason: "rebuild"` → `session_ready`），新会话只带
  这条连接上和他最近几轮的文字、跳过作废的（`recent`，只在内存里）。会话就绪之前新的一轮等着（`ready`）。
- 对话和用声音说的打算交给叙事者时带提交窗口（`turn_complete`、定稿 + 3 秒，按 `ZJ_SPEED` 缩短）。
- `text { via: "correction" }`：前端先发 `turn_retract`，旧的一轮作废成功时会话已经在重建，新的一轮照常等就绪。
- 意图确认：叙事者在 `turns.result.confirm` 记下要问的，这里推完那一轮的结果以后，人物还没反问的另起一轮说出
  反问（`turn_started reason: "confirm"`，原话挂在原来那一轮下面），再推 `confirm`、开 30 秒的计时（按 `ZJ_SPEED`
  缩短；速度 0 时照 30 秒）。按钮、计时到点都写一行 `kind: "confirm"` 的任务。重连时 `welcome.pending.confirm`
  带剩余秒数，过期的先关掉。

B-0 没有真 Live，`hello.fakeVoice` 给不给都用假 Live。还没做的消息（`near` 等）忽略，只在日志里记类型名。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, cast

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import func, select, update
from starlette.websockets import WebSocketState

from zoujin_backend import audio
from zoujin_backend.config import COOKIE
from zoujin_backend.db import store
from zoujin_backend.db.store import Run
from zoujin_backend.db.tables import drafts, playthroughs, turns, utterances
from zoujin_backend.gateway import auth
from zoujin_backend.gateway.core import VOICE_MINUTES, Gateway
from zoujin_backend.gateway.monitor import Monitor
from zoujin_backend.gateway.safety import PAUSED_REFUSED, Guard
from zoujin_backend.models.armor import cost_usd
from zoujin_backend.models.live import LiveSession, Recent, Transcriber
from zoujin_backend.narrator import confirm
from zoujin_backend.narrator.acts import PLAN_TRIES
from zoujin_backend.narrator.plans import INVALID_REQUEST, NOT_HEARD, REFUSAL_FALLBACK, narrate_fallback
from zoujin_backend.origin import origin_allowed
from zoujin_backend.projection import pending
from zoujin_backend.safety import Screen
from zoujin_backend.schemas import SchemaError

log = logging.getLogger("zoujin.gateway")

Json = Any

SESSION_ETA_MS = 800  # 预热、切换人物、重建会话（3.5 的例子）
FRAME_MIC = 0x01
VOICE = {"enabled": True, "degraded": False, "minutesLeftToday": VOICE_MINUTES}
# 判完要给前端一个结果的任务（narrator/core.py 同名），加上意图确认的回答（confirm_closed，B-4）
ANSWERED = ("talk", "action", "choose", "plan", "confirm")
SERVER_SEQ = 0x80000001  # 服务端发起的轮次的 turnSeq 从这里起，最高位为 1（3.1）
COMMIT_WINDOW_S = 3.0  # 作废的窗口：叙事者最早在 turn_complete（打算是定稿）之后几秒提交（B-4）
RECENT_TURNS = 6  # 会话重建时带进新会话的最近几轮


def error_msg(code: str, message: str) -> Json:
    return {"type": "error", "error": {"code": code, "message": message, "retryable": False, "retryAfterSeconds": None}}


@dataclass
class Turn:
    """连接上正在进行的一轮（还没交给叙事者）。"""

    turn_id: str
    turn_seq: int
    character: str
    mode: str  # voice / text / arrival（落地时人物先开口，B-3）/ confirm（意图确认的反问，B-4）
    session: LiveSession
    text: str | None = None  # 文字一轮的原话；confirm：人物要说的反问
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
    done_at: float | None = None  # 人物说完（turn_complete）或被打断的时刻：提交窗口从这里算（B-4）
    retracted: bool = False  # 还在内存里时被作废了（B-4）
    handing: bool = False  # 正在写进库里（交给叙事者）：之后的作废走库里那条路
    owner: str | None = None  # confirm：原来那一轮（反问的原话挂在它下面）
    asking: Json | None = None  # confirm：说完以后推的 confirm（turns.result.confirm）
    screen: asyncio.Future[Screen] | None = None  # B-12：玩家这一句的安全筛查（定稿一到就开始）
    paused: bool = False  # B-12：被出戏卡停下了（不推人物定稿、不交给叙事者）

    @property
    def retractable(self) -> bool:
        return self.mode in ("voice", "text")

    @property
    def speaking(self) -> bool:
        return self.stream is not None and not self.stream.done() and not self.complete


@dataclass
class PlanTurn:
    """幕末用声音说打算的一轮（3.11）：只转写，没有人物回答，松开以后交给叙事者的 plan。"""

    turn_id: str
    turn_seq: int
    listener: Transcriber
    partials: list[asyncio.Task[Any]] = field(default_factory=list)  # 推出去的半句：定稿要排在它们后面
    retracted: bool = False  # 还在说的时候被作废了（B-4）：丢掉，不推定稿、不写任务


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
    ready: dict[str, asyncio.Event] = field(default_factory=dict)  # 会话就绪了（session_ready 推过）；新的一轮等它
    recent: dict[str, list[tuple[str, Recent]]] = field(default_factory=dict)  # 每个人物最近几轮（只在内存里）
    memory: dict[str, Turn] = field(default_factory=dict)  # 还没交给叙事者的轮次（作废时查）
    timers: dict[str, asyncio.Task[Any]] = field(default_factory=dict)  # 意图确认的 30 秒计时，按 draftId
    turn: Turn | None = None
    plan: PlanTurn | None = None
    served: int = 0  # 这条连接上服务端发起了几轮（turnSeq 用）
    retracted_with: dict[str, str] = field(default_factory=dict)  # 作废的轮次是和谁说的（重建会话用）
    settled: set[str] = field(default_factory=set)  # 结果已经推过（或这条连接之前就判完了）的轮次
    closed: asyncio.Event = field(default_factory=asyncio.Event)
    push_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    guard: Guard = field(init=False)  # B-12：安全筛查（gateway/safety.py）
    monitor: Monitor = field(init=False)  # B-12：人物输出的监控（gateway/monitor.py）

    def __post_init__(self) -> None:
        self.guard = Guard(self)
        self.monitor = Monitor(self.gw.library)

    async def close_sessions(self) -> None:
        """出戏卡：关掉这条连接上所有人物的会话（3.12）；回到故事以后前端重新 focus，开新的会话。"""
        sessions, self.sessions = self.sessions, {}
        self.ready.clear()
        self.ready_at.clear()
        self.focused = None
        for sess in sessions.values():
            with contextlib.suppress(Exception):
                await sess.close()

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
        if msg.get("type") == "act_ended":
            self.monitor.act_ended()
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

    # —— 推 commit 和每一轮的结果 ——

    async def push(self) -> None:
        """把 sent_seq 之后提交了的都推出去（hello 补发、NOTIFY 都走这里），再推判完了的轮次的结果。"""
        async with self.push_lock:
            if self.sent_seq < 0:
                return
            msgs, self.sent_seq = await self.gw.commits(self.pid, self.sent_seq)
            for m in msgs:
                await self.send(m)
            await self._results()

    async def _results(self) -> None:
        """判完的轮次推结果：叙事者记在 `turns.result.push` 里的消息（固定演出、turn_settled、action_result、
        act_plan_result、act_transition、act_ended），按判完的先后。`turns.result.seq` 是这一轮那次提交的最后一个
        seq：commit 还没推到那里（叙事者正好在读提交和读轮次之间提交了）就留到下一次，保证结果在它自己那次的 commit
        之后（3.4、3.8、3.14），这一轮自己没有事件（`wait` 只结算节拍）也一样。三次都没做成的任务按种类补一个
        （`_fallback`）。"""
        async with self.gw.engine.connect() as c:
            rows = (
                await c.execute(
                    select(
                        turns.c.turn_id,
                        turns.c.kind,
                        turns.c.outcome,
                        turns.c.minutes,
                        turns.c.client_msg_id,
                        turns.c.request,
                        turns.c.result,
                    )
                    .where(
                        turns.c.playthrough_id == self.pid,
                        turns.c.kind.in_(ANSWERED),
                        turns.c.status.in_(("done", "failed")),
                        turns.c.settled_at.is_not(None),
                    )
                    .order_by(turns.c.settled_at)
                )
            ).all()
        for r in rows:
            upto = (r.result or {}).get("seq")
            if r.turn_id in self.settled or (upto is not None and upto > self.sent_seq):
                continue
            self.settled.add(r.turn_id)
            if r.result is not None and "push" in r.result:
                for m in r.result["push"]:
                    await self.send(m)
                if r.result.get("confirm"):  # 这一轮留下了草稿：结果推完再反问（B-4）
                    await self._ask(r.turn_id, r.result["confirm"])
            else:
                await self._fallback(r)

    async def _fallback(self, r: Any) -> None:
        """叙事者三次都没做成（`turns.status = "failed"`）：前端还在等这一轮，按种类给一个不改变世界的结果。"""
        if r.kind == "talk":
            await self.send(
                {
                    "type": "turn_settled",
                    "turnId": r.turn_id,
                    "outcome": r.outcome or "no_response",
                    "eventIds": await self._visible_ids(r.turn_id),
                    "minutes": int(r.minutes or 0),
                }
            )
        elif r.kind == "action":
            await self.send(
                {
                    "type": "action_result",
                    "clientMsgId": r.client_msg_id or r.turn_id,
                    "status": "refused",
                    "eventIds": [],
                    "minutes": 0,
                    "narration": narrate_fallback("refused"),
                }
            )
        elif r.kind == "confirm":  # 回答三次都没处理成：草稿还开着，到期以后叙事者再写超时的任务
            return
        elif r.kind == "plan":
            run = await self._run()
            left = max(0, PLAN_TRIES - run.plan_tries)
            to = {"turnId": r.turn_id} if (r.request or {}).get("mode") == "voice" else {"clientMsgId": r.client_msg_id}
            await self.send(
                {"type": "act_plan_result", **to, "accepted": False, "narration": [REFUSAL_FALLBACK], "triesLeft": left}
            )
        else:
            err = error_msg("internal", "エラーが起きました。")
            err["error"]["retryable"] = True
            await self.send(err)

    async def _visible_ids(self, turn_id: str) -> list[str]:
        evs = await self.gw.visible_events(self.pid, 0, 10_000)
        return [e["eventId"] for e in evs if e.get("turnId") == turn_id]

    async def _observe(self, character: str, text: str | None, said: str | None = None) -> None:
        """人物的一句定稿过输出侧监控（B-12，2.11）：剧透、Model Armor、问句比例；连续两句剧透重建会话。
        said = 玩家这一轮的定稿（玩家自己说过的词人物接着说不算剧透）。Span 只有人物 ID、事实 ID 和类别，没有原话。"""
        if not text:
            return
        async with self.gw.engine.connect() as c:
            st = await store.sim_state(c, self.pid)
        o = self.monitor.observe(character, text, st, said=said)
        armor = self.gw.screener.armor
        harmful = False
        failed = False
        try:
            got = await asyncio.wait_for(armor.screen_response(text), self.gw.screener.armor_deadline)
            harmful = got.harmful
        except Exception:  # 第二层：出错、超时当没命中
            failed = True
            log.info("人物输出的 Model Armor 没有结果（%s）", character)
        by = o.counts()
        if armor_usd := cost_usd(armor, text):
            by["cost_armor_usd"] = armor_usd
        if failed:
            by["armor_errors"] = 1
        if o.spoilers:
            facts = [h.fact for h in o.spoilers]
            with self.gw.tracer.span(
                "monitor.hit", playthrough_id=self.pid, character=character, kind="spoiler", fact_ids=facts
            ):
                pass
        if harmful:
            by["output_harmful"] = 1
            with self.gw.tracer.span("monitor.hit", playthrough_id=self.pid, character=character, kind="harmful"):
                pass
        rebuild = o.rebuild and character in self.sessions and not self.guard.paused
        if rebuild:
            by["output_rebuilds"] = 1
        async with self.gw.engine.begin() as c:
            await store.count(c, self.pid, **by)
        if rebuild:
            self.monitor.rebuilt(character)
            await self._rebuild(character)

    async def on_commit(self, payload: Json) -> None:
        await self.push()

    # —— 收 ——

    async def hello(self, msg: Json) -> None:
        await self.gw.handed(self.pid)  # 旧连接断线那一轮先写下来，lastTurn 才是它（lost 或照常交了）
        async with self.gw.engine.connect() as c:
            last_seq = int(
                await c.scalar(select(playthroughs.c.last_seq).where(playthroughs.c.playthrough_id == self.pid)) or 0
            )
            settled = (
                await c.execute(
                    select(turns.c.turn_id).where(
                        turns.c.playthrough_id == self.pid,
                        turns.c.kind.in_(ANSWERED),
                        turns.c.status.in_(("done", "failed")),
                    )
                )
            ).scalars()
            # 这条连接之前判完的不再推结果：固定演出不补发（3.14），幕末和落地由 welcome.pending 补上（第 4 节）
            self.settled = set(settled)
            last_turn = await self._last_turn(c)
            pt = await self.gw.pt(c, self.pid)
        asking = await self._pending_confirm()
        await self.guard.load()
        if pt is not None:
            self.characters = pt.book.characters
            self.monitor.attach(pt.book)
        await self.send(
            {
                "type": "welcome",
                "lastSeq": last_seq,
                "voice": dict(VOICE),
                "lastTurn": last_turn,
                "pending": pending(pt.run if pt is not None else None, asking, safety_pause=self.guard.paused),
            }
        )
        async with self.push_lock:
            self.sent_seq = min(int(msg["lastSeq"]), last_seq)
        await self.push()

    async def _last_turn(self, c: Any) -> Json | None:
        """断线前的最后一轮（第 4 节）。作废的一轮 settled、两段文字都是 null（原话已清空，B-4）；人物的话取第一句
        （意图确认的反问也挂在原来那一轮下面）。"""
        row = (
            await c.execute(
                select(turns.c.turn_id, turns.c.character, turns.c.status)
                .where(turns.c.playthrough_id == self.pid, turns.c.kind.in_(("talk", "plan")))
                .order_by(turns.c.created_at.desc())
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        texts: dict[str, str | None] = {}
        for speaker, text in (
            await c.execute(
                select(utterances.c.speaker, utterances.c.text)
                .where(utterances.c.turn_id == row.turn_id)
                .order_by(utterances.c.recorded_at)
            )
        ).all():
            texts.setdefault(speaker, text)
        if row.status == "retracted":
            texts = {}
        return {
            "turnId": row.turn_id,
            "character": row.character,
            "status": "settled"
            if row.status in ("done", "failed", "retracted")
            else "lost"
            if row.status == "lost"
            else "pending",
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
            self.sessions[character] = await self.gw.live.open(character, notes=self.monitor.notes(character))
            await self._prepare(character, "switch")
            return

        async def ready() -> None:
            await asyncio.sleep(max(0.0, self.ready_at[character] - time.monotonic()))
            if self.focused == character:
                await self.send({"type": "session_ready", "character": character, "voiceAvailable": True})

        self.gw.spawn(ready())

    async def _prepare(self, character: str, reason: str) -> None:
        """新开的会话（切换人物、重建）：推 session_preparing，就绪时推 session_ready（还看着这个人物的话），
        这之前这个人物的新一轮等着（`_stream`）。"""
        eta = SESSION_ETA_MS
        await self.send({"type": "session_preparing", "character": character, "reason": reason, "etaMs": eta})
        self.ready_at[character] = time.monotonic() + eta / 1000 * self.gw.settings.speed
        ev = self.ready[character] = asyncio.Event()

        async def ready() -> None:
            await asyncio.sleep(max(0.0, self.ready_at[character] - time.monotonic()))
            if self.focused == character:
                await self.send({"type": "session_ready", "character": character, "voiceAvailable": True})
            ev.set()

        self.gw.spawn(ready())

    async def _rebuild(self, character: str) -> None:
        """作废以后重建这个人物的会话（backend-design 3.2）：新会话只带最近几轮里没作废的，人物真的没听到那一轮。"""
        old = self.sessions.pop(character, None)
        if old is not None:
            await old.close()
        terms = self.monitor.terms(character)  # 剧透重建：说漏的那几句不带进新会话（UX 在 #112 的评审）
        recent = [r for _, r in self.recent.get(character, []) if not any(x in (r.reply or "") for x in terms)]
        self.sessions[character] = await self.gw.live.open(character, recent, notes=self.monitor.notes(character))
        await self._prepare(character, "rebuild")

    async def _start(self, msg: Json, mode: str) -> Turn | None:
        if self.focused is None:
            log.info("%s 没有 focus 的人物", msg["type"])
            await self.send(error_msg("invalid_request", "話す相手を選んでください。"))
            return None
        await self._cut()
        prev = self.turn if self.turn is not None and self.turn.ended else None
        self.turn = Turn(msg["turnId"], msg["turnSeq"], self.focused, mode, self.sessions[self.focused], prev=prev)
        self.memory[self.turn.turn_id] = self.turn
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
        """连接断了：人物还没说完的一轮记成 lost；已经说完、等定稿的照常交。玩家还按着说话键就断了的一轮
        （没有 activity_end，人物还没开口）也是 lost，不然 lastTurn 是上一轮，前端说不出「もう一度」（#109 评审）。"""
        old = self.turn
        if old is None:
            return
        if old.speaking:
            assert old.stream is not None
            old.lost = True
            old.stream.cancel()
        elif not old.ended and old.mode == "voice" and old.turn_id in self.memory:
            old.ended = old.lost = True
            old.stream = asyncio.ensure_future(asyncio.sleep(0))  # 没有回答可等，_finish 直接写 lost 那一行
            self.gw.hand(self.pid, self._finish(old))

    def audio_in(self, frame: bytes) -> None:
        if self.plan is not None and len(frame) >= 5 and int.from_bytes(frame[1:5], "big") == self.plan.turn_seq:
            self._plan_audio(self.plan, frame)
            return
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
            self.guard.start(t, t.text)
        t.stream = asyncio.ensure_future(self._stream(t))
        self.gw.hand(self.pid, self._finish(t))

    async def _stream(self, t: Turn) -> None:
        """假 Live 的回答转成下行消息。被打断、断线时这个任务被取消，停在哪就是哪。"""
        wait = self.ready.get(t.character)
        if wait is not None and not wait.is_set():  # 会话还在准备（重建）：等就绪再送进去（B-4）
            await wait.wait()
        released = time.monotonic()
        if t.mode == "arrival":
            said = t.session.speak_first()
        elif t.mode == "confirm":
            said = t.session.speak_first(t.text)
        else:
            said = t.session.respond(t.text)
        async for ev in said:
            if ev.kind == "input_final":
                t.heard = ev.text
                self.guard.start(t, ev.text)
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
                t.done_at = time.monotonic()
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
                self.gw.spawn(self._observe(t.character, ev.text, t.heard))

    async def _final(self, t: Turn) -> None:
        if t.paused:  # 出戏卡停下的一轮没有人物定稿（3.3 的例外）
            return
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
        if t.done_at is None:
            t.done_at = time.monotonic()
        if not t.lost and not t.retracted and not t.paused:  # 作废的不补 interrupted 和说到一半的定稿（B-4）
            if t.stream.cancelled() and not t.complete:
                await self.send({"type": "interrupted", "turnId": t.turn_id})
            if not t.final and t.said is not None:  # 人物还没出字就被打断的，没有定稿（同「没回答」的轮）
                await self._final(t)
        t.quiet.set()
        screen = await self.guard.result(t)  # 交给叙事者之前等安全筛查（B-12）：不会先提交再暂停
        if t.prev is not None and not t.retracted:
            await t.prev.submitted.wait()
            t.prev = None
        try:
            if t.paused:
                await self.guard.write_paused(t)
            elif t.retracted:
                await self._write_retracted(t)
            else:
                t.handing = True  # 从这里起作废走库里那条路
                await self._submit(t, screen)
        finally:
            self.memory.pop(t.turn_id, None)
            t.submitted.set()

    async def _submit(self, t: Turn, screen: Screen | None = None) -> None:
        """原话和这一轮的任务同一个事务写进去，再叫叙事者（turn_complete 之后）。lost 的只留记录，不叫叙事者。
        落地时人物先开口的那一句只存原话（那一行任务收到 act_landed 时已经写了），不交给叙事者（3.11）。"""
        async with self.gw.engine.begin() as c:
            st = await store.sim_state(c, self.pid)
            now_t = st["t"] if st is not None else 0
            if t.mode in ("arrival", "confirm"):  # 反问挂在原来那一轮下面（B-4）
                await store.add_utterance(
                    c,
                    self.gw.ids,
                    self.pid,
                    t.owner or t.turn_id,
                    speaker=t.character,
                    text=t.said,
                    t=now_t,
                    source="live",
                )
            else:
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
                    commit_after=self._window(t.done_at),
                    flags=sorted(screen.flags) if screen is not None and not t.lost else None,  # lost 的不交给叙事者
                )
                heard = screen.masked if screen is not None and screen.masked is not None else t.heard
                await store.add_utterance(c, self.gw.ids, self.pid, t.turn_id, speaker="player", text=heard, t=now_t)
                await store.add_utterance(
                    c, self.gw.ids, self.pid, t.turn_id, speaker=t.character, text=t.said, t=now_t, source="live"
                )
        if t.mode == "confirm":
            if t.asking is not None:
                await self._push_confirm(t.asking)
            return
        if t.mode == "arrival":
            return
        if not t.lost:
            kept = self.recent.setdefault(t.character, [])
            kept.append((t.turn_id, Recent(t.heard, t.said)))
            del kept[:-RECENT_TURNS]
            self.gw.kick(self.pid)

    def _window(self, since: float | None) -> float | None:
        """提交窗口还剩几秒（turn_complete、定稿 + 3 秒，按 ZJ_SPEED 缩短）；速度 0 时没有窗口。"""
        full = COMMIT_WINDOW_S * self.gw.settings.speed
        if full <= 0:
            return None
        return max(0.0, full - (time.monotonic() - since)) if since is not None else full

    async def _write_retracted(self, t: Turn) -> None:
        """还在内存里就作废的一轮：写一行 retracted，不写原话，不交给叙事者（3.6）。"""
        async with self.gw.engine.begin() as c:
            exists = await c.scalar(select(turns.c.turn_id).where(turns.c.turn_id == t.turn_id))
            if exists is not None:
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
                status="retracted",
            )
            await c.execute(
                update(turns)
                .where(turns.c.turn_id == t.turn_id)
                .values(outcome="retracted", minutes=0, settled_at=func.now())
            )
            await store.count_retracted(c, self.pid)

    async def handle(self, msg: Json) -> None:
        t = msg["type"]
        if t == "hello":
            await self.hello(msg)
        elif t == "ping":
            await self.send({"type": "pong"})
        elif self.sent_seq < 0:
            log.info("hello 之前的 %s", t)
            await self.send(error_msg("invalid_request", "うまく送れませんでした。"))
        elif t == "safety_resume":
            await self.guard.resume()
        elif self.guard.paused and t in PAUSED_REFUSED:  # 出戏卡开着：故事停着，回到故事之前不收（B-12）
            log.info("暂停期间的 %s", t)
            await self.send(error_msg("invalid_request", INVALID_REQUEST))
        elif t == "focus" and self.guard.paused:
            log.info("暂停期间的 focus：不开会话")
        elif t == "focus":
            await self.focus(msg["character"])
        elif t == "unfocus":
            self.focused = None
        elif t == "activity_start":
            if msg.get("purpose") == "act_plan":
                await self.plan_start(msg)
            elif await self._refuse_if_ended():
                return
            else:
                await self._start(msg, "voice")
        elif t == "activity_end":
            if self.plan is not None and self.plan.turn_id == msg["turnId"]:
                plan, self.plan = self.plan, None
                await self.plan_end(plan)
                return
            turn = self.turn
            if turn is not None and turn.turn_id == msg["turnId"] and not turn.ended:
                self.respond(turn)
        elif t == "text":
            if await self._refuse_if_ended():
                return
            turn = await self._start(msg, "text")
            if turn is not None:
                turn.text = msg["text"]
                self.respond(turn)
        elif t == "action":
            await self.action(msg)
        elif t == "act_choose":
            await self.choose(msg)
        elif t == "act_propose":
            await self.propose(msg)
        elif t == "act_landed":
            await self.landed(msg)
        elif t == "turn_retract":
            await self.retract(msg["turnId"])
        elif t == "confirm_answer":
            await self.confirm_answer(msg)
        else:
            log.info("还不处理 %s，忽略", t)

    # —— 作废（B-4，3.6）——

    async def retract(self, turn_id: str) -> None:
        """作废一轮：按它到了哪一步（卡的那张表）。对话的一轮作废以后推 turn_settled（retracted）、重建会话；
        用声音说的打算不推 act_plan_result 和 turn_settled，不算一次试次。"""
        with self.gw.tracer.span("gateway.retract", playthrough_id=self.pid, turn_id=turn_id) as sp:
            status, kind, stage = await self._retract(turn_id)
            sp.set(status=status)
            if kind is not None:
                sp.set(turn_kind=kind, stage=stage)
        await self.send({"type": "turn_retract_result", "turnId": turn_id, "status": status})
        if status != "retracted" or kind != "talk":
            return
        self.settled.add(turn_id)
        await self.send(
            {"type": "turn_settled", "turnId": turn_id, "outcome": "retracted", "eventIds": [], "minutes": 0}
        )
        for kept in self.recent.values():
            kept[:] = [(x, r) for x, r in kept if x != turn_id]
        character = self.retracted_with.pop(turn_id, None)
        if character is not None and character in self.sessions:
            await self._rebuild(character)

    async def _retract(self, turn_id: str) -> tuple[str, str | None, str | None]:
        """返回（retracted / too_late，talk / plan，memory / queued）。"""
        plan = self.plan
        if plan is not None and plan.turn_id == turn_id:  # 打算还在说：丢掉，不推定稿、不写任务
            plan.retracted = True
            self.plan = None
            async with self.gw.engine.begin() as c:
                await store.count_retracted(c, self.pid)
            return "retracted", "plan", "memory"
        t = self.memory.get(turn_id)
        if t is not None and t.retractable and not t.handing:
            t.retracted = True
            self.retracted_with[turn_id] = t.character
            if t.stream is not None and not t.stream.done():
                t.stream.cancel()  # 停止转发这一轮的下行音频
            if not t.ended:  # 玩家还在说：没有 _finish，这里写那一行
                t.ended = True
                t.quiet.set()
                try:
                    await self._write_retracted(t)
                finally:
                    self.memory.pop(turn_id, None)
                    t.submitted.set()
            else:
                await t.submitted.wait()  # _finish 看到作废，写那一行
            return "retracted", "talk", "memory"
        if t is not None and t.handing:
            await t.submitted.wait()  # 正在写进库里：等写完，走库里那条路
        async with self.gw.engine.begin() as c:
            row = await c.scalar(select(turns.c.character).where(turns.c.turn_id == turn_id))
            kind = await store.retract_queued(c, self.pid, turn_id)
        if kind is None:
            return "too_late", None, None
        if row is not None:
            self.retracted_with[turn_id] = row
        return "retracted", kind, "queued"

    # —— 意图确认（B-4，3.9）——

    async def _ask(self, turn_id: str, asking: Json) -> None:
        """原来那一轮的结果推完以后：人物还没反问的，服务端起一轮说出反问，说完再推 confirm；已经在反问的、
        玩家已经不看着他、或玩家正在说话的，直接推 confirm。"""
        who = asking["character"]
        t = self.turn
        busy = t is not None and (not t.ended or t.speaking)
        if asking.get("asked") or self.focused != who or busy or who not in self.sessions:
            await self._push_confirm(asking)
            return
        turn_seq = SERVER_SEQ + self.served
        self.served += 1
        qid = self.gw.ids.new("turn")
        self.settled.add(qid)
        await self.send(
            {"type": "turn_started", "turnId": qid, "turnSeq": turn_seq, "speaker": who, "reason": "confirm"}
        )
        prev = t if t is not None and t.ended else None
        self.turn = Turn(qid, turn_seq, who, "confirm", self.sessions[who], text=asking["prompt"], prev=prev)
        self.turn.owner = turn_id
        self.turn.asking = asking
        self.respond(self.turn)

    def _timeout_s(self) -> float:
        """确认的计时：30 秒按 ZJ_SPEED 缩短；速度 0（测试里人物不等）时照 30 秒。"""
        return confirm.TIMEOUT_SEC * (self.gw.settings.speed or 1.0)

    async def _push_confirm(self, asking: Json) -> None:
        """推 confirm，在草稿上记到期的时刻，开计时。草稿已经关掉（收幕、别的回答先到）就不推。"""
        draft_id = asking["draftId"]
        seconds = self._timeout_s()
        async with self.gw.engine.begin() as c:
            found = await c.scalar(
                select(drafts.c.draft_id)
                .where(drafts.c.draft_id == draft_id, drafts.c.playthrough_id == self.pid)
                .with_for_update()
            )
            if found is None or await store.answered(c, self.pid, draft_id):
                log.info("草稿 %s 已经关掉，不推 confirm", draft_id)
                return
            await c.execute(
                update(drafts)
                .where(drafts.c.draft_id == draft_id)
                .values(expires_at=func.clock_timestamp() + timedelta(seconds=seconds))
            )
        await self.send(confirm.confirm_msg(draft_id, asking["character"], asking["prompt"]))
        self._start_timer(draft_id, seconds)

    def _start_timer(self, draft_id: str, seconds: float) -> None:
        old = self.timers.pop(draft_id, None)
        if old is not None:
            old.cancel()

        async def expire() -> None:
            await asyncio.sleep(seconds)
            async with self.gw.engine.begin() as c:
                written = await store.answer_draft(c, self.gw.ids, self.pid, draft_id, None, "timeout")
            if written is not None:
                self.gw.kick(self.pid)

        self.timers[draft_id] = self.gw.spawn(expire())

    async def confirm_answer(self, msg: Json) -> None:
        """按钮回答：不是这一局开着的草稿（已经超时、已经答过、收幕关掉了）就忽略，只记日志。"""
        draft_id, option = msg["draftId"], msg["optionId"]
        if option not in confirm.ANSWERS:
            log.info("confirm_answer 的 optionId 不认识，忽略")
            return
        async with self.gw.engine.begin() as c:
            row = (
                (
                    await c.execute(
                        select(drafts.c.expires_at, func.now().label("now"))
                        .where(drafts.c.draft_id == draft_id, drafts.c.playthrough_id == self.pid)
                        .with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            expired = row is not None and row["expires_at"] is not None and row["expires_at"] <= row["now"]
            written = None
            if row is not None and not expired:
                written = await store.answer_draft(c, self.gw.ids, self.pid, draft_id, option, "button")
        if written is None:
            log.info("confirm_answer 不是开着的草稿，忽略")
            return
        timer = self.timers.pop(draft_id, None)
        if timer is not None:
            timer.cancel()
        self.gw.kick(self.pid)

    async def _pending_confirm(self) -> Json | None:
        """重连时还没答的确认（第 4 节 pending.confirm，带 remainingSec）。过期了的先关掉（写超时的任务），给 null；
        还没推出过的（断线时还没轮到）从现在起算 30 秒。"""
        seconds = self._timeout_s()
        async with self.gw.engine.begin() as c:
            draft = await store.open_draft(c, self.pid, lock=True)
            if draft is None or await store.answered(c, self.pid, draft["draft_id"]):
                return None
            now = cast(datetime, await c.scalar(select(func.clock_timestamp())))
            expires: datetime = draft["expires_at"] or now + timedelta(seconds=seconds)
            expired = expires <= now
            if expired:
                await store.answer_draft(c, self.gw.ids, self.pid, draft["draft_id"], None, "timeout")
            elif draft["expires_at"] is None:
                await c.execute(update(drafts).where(drafts.c.draft_id == draft["draft_id"]).values(expires_at=expires))
        if expired:
            self.gw.kick(self.pid)
            return None
        left = (expires - now).total_seconds()
        self._start_timer(draft["draft_id"], left)
        msg = confirm.confirm_msg(draft["draft_id"], draft["character"], draft["prompt"])
        return {k: msg[k] for k in ("draftId", "character", "prompt", "options", "timeoutSec")} | {
            "remainingSec": max(0, math.ceil(left))
        }

    # —— 动作和幕末（B-3）——

    async def _run(self) -> Run:
        async with self.gw.engine.connect() as c:
            row = await store.playthrough(c, self.pid)
        return Run.of(row or {})

    async def _refuse_if_ended(self) -> bool:
        """收了幕、还没选定：对话和动作回 invalid_request，不带 turnId（第 5 节）。"""
        if (await self._run()).act_end is None:
            return False
        await self.send(error_msg("invalid_request", INVALID_REQUEST))
        return True

    async def action(self, msg: Json) -> None:
        """动作（3.8）：写一行任务、叫叙事者，不等。判定、commit 和 action_result 都在叙事者提交以后推。"""
        request = {k: msg[k] for k in ("clientMsgId", "kind", "target", "params", "actionId") if k in msg}
        async with self.gw.engine.begin() as c:
            row = await store.playthrough(c, self.pid)
            ended = row is None or row["act_end"] is not None
            if not ended:
                await store.enqueue(
                    c, self.gw.ids, self.pid, kind="action", client_msg_id=msg["clientMsgId"], request=request
                )
        if ended:
            await self.send(error_msg("invalid_request", INVALID_REQUEST))
            return
        self.gw.kick(self.pid)

    async def choose(self, msg: Json) -> None:
        """选去处（3.11）：叙事者核对它在不在这次的去处里，不在就回 invalid_choice，不写事件。"""
        request = {k: msg[k] for k in ("clientMsgId", "optionId", "enRouteChoice") if k in msg}
        async with self.gw.engine.begin() as c:
            await store.enqueue(
                c, self.gw.ids, self.pid, kind="choose", client_msg_id=msg["clientMsgId"], request=request
            )
        self.gw.kick(self.pid)

    async def _plan_open(self) -> bool:
        """说打算收不收：收了幕、还有试次（3.11）。"""
        run = await self._run()
        return run.act_end is not None and run.plan_tries < PLAN_TRIES

    async def propose(self, msg: Json) -> None:
        """用文字说打算：原话照常存进 utterances（这一轮只有玩家说话），写 plan 任务。"""
        if not await self._plan_open():
            await self.send(error_msg("invalid_request", INVALID_REQUEST))
            return
        screen = await self.guard.screen_plan(msg["text"])
        if self.guard.paused:
            return
        await self._submit_plan(
            None, screen.masked or msg["text"], client_msg_id=msg["clientMsgId"], flags=screen.flags
        )

    async def plan_start(self, msg: Json) -> None:
        if not await self._plan_open():
            await self.send(error_msg("invalid_request", INVALID_REQUEST))
            return
        await self._cut()
        self.plan = PlanTurn(msg["turnId"], msg["turnSeq"], self.gw.live.transcriber())

    def _plan_audio(self, plan: PlanTurn, frame: bytes) -> None:
        if frame[0] != FRAME_MIC:
            return
        for ev in plan.listener.audio_in(frame[5:]):
            if ev.kind == "input_partial":
                task = self.gw.spawn(
                    self.send(
                        {
                            "type": "transcript",
                            "turnId": plan.turn_id,
                            "speaker": "player",
                            "text": ev.text,
                            "final": False,
                        }
                    )
                )
                plan.partials.append(task)

    async def plan_end(self, plan: PlanTurn) -> None:
        """用声音说打算：转写的定稿推给前端，再写 plan 任务；结果（act_plan_result）带这一轮的 turnId。
        提交窗口从定稿推出起算（B-4：玩家看到识别错了，来得及「言い直す」）。"""
        heard = await plan.listener.finish()
        await asyncio.gather(*plan.partials, return_exceptions=True)  # 半句先到，定稿不被半句盖掉
        if plan.retracted:
            return
        if not (heard or "").strip():  # 误按、没出声：不写任务、不算试次（3.11）
            left = max(0, PLAN_TRIES - (await self._run()).plan_tries)
            await self.send(
                {
                    "type": "act_plan_result",
                    "turnId": plan.turn_id,
                    "accepted": False,
                    "narration": [NOT_HEARD],
                    "triesLeft": left,
                }
            )
            return
        await self.send(
            {"type": "transcript", "turnId": plan.turn_id, "speaker": "player", "text": heard, "final": True}
        )
        screen = await self.guard.screen_plan(heard)
        if self.guard.paused:  # 打算的这一句判成了信号：不交给叙事者（B-12）
            return
        await self._submit_plan(plan, screen.masked or heard, flags=screen.flags)

    async def _submit_plan(
        self,
        plan: PlanTurn | None,
        text: str | None,
        *,
        client_msg_id: str | None = None,
        flags: frozenset[str] = frozenset(),
    ) -> None:
        mode = "text" if plan is None else "voice"
        request: Json = {"mode": mode}
        if client_msg_id is not None:
            request["clientMsgId"] = client_msg_id
        async with self.gw.engine.begin() as c:
            st = await store.sim_state(c, self.pid)
            turn_id = await store.enqueue(
                c,
                self.gw.ids,
                self.pid,
                kind="plan",
                turn_id=plan.turn_id if plan is not None else None,
                input_mode=mode,
                turn_seq=plan.turn_seq if plan is not None else None,
                client_msg_id=client_msg_id,
                request=request,
                commit_after=self._window(time.monotonic()) if plan is not None else None,
                flags=sorted(flags) or None,
            )
            await store.add_utterance(
                c, self.gw.ids, self.pid, turn_id, speaker="player", text=text, t=st["t"] if st is not None else 0
            )
        self.gw.kick(self.pid)

    async def landed(self, msg: Json) -> None:
        """落地（3.11）：这一幕的 arrival 带 opener、还没落地时，让他先开口。别的 actId、同一幕第二次的忽略。"""
        async with self.gw.engine.begin() as c:
            row = (
                (
                    await c.execute(
                        select(playthroughs.c.arrival)
                        .where(playthroughs.c.playthrough_id == self.pid)
                        .with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            arrival = row["arrival"] if row is not None else None
            if not arrival or arrival.get("actId") != msg["actId"] or not arrival.get("opener"):
                log.info("act_landed 不是这一幕待落地的，忽略")
                return
            opener = str(arrival["opener"])
            turn_seq = SERVER_SEQ + self.served
            self.served += 1
            turn_id = await store.enqueue(
                c, self.gw.ids, self.pid, kind="arrival", character=opener, turn_seq=turn_seq, status="done"
            )
            await c.execute(update(playthroughs).where(playthroughs.c.playthrough_id == self.pid).values(arrival=None))
        self.settled.add(turn_id)
        await self._cut()
        if opener not in self.sessions:
            self.sessions[opener] = await self.gw.live.open(opener)
            self.ready_at[opener] = time.monotonic()
        self.focused = opener  # arrival 的一轮服务端把 speaker 当作已经 focus 的人物（3.3）
        await self.send(
            {"type": "turn_started", "turnId": turn_id, "turnSeq": turn_seq, "speaker": opener, "reason": "arrival"}
        )
        prev = self.turn if self.turn is not None and self.turn.ended else None
        self.turn = Turn(turn_id, turn_seq, opener, "arrival", self.sessions[opener], prev=prev)
        self.respond(self.turn)


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
        old.drop()  # 先把旧连接上没说完、还按着的那一轮交出去，下面 hello 的 handed() 才等得到它
        await old.close(4009, "opened elsewhere")  # 同一局在别的标签页打开：新连接踢掉旧连接
    reader = asyncio.ensure_future(read_loop(conn))
    closed = asyncio.ensure_future(conn.closed.wait())
    try:
        await asyncio.wait({reader, closed}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        reader.cancel()
        closed.cancel()
        conn.drop()
        for timer in conn.timers.values():  # 断线时计时不在了：重连的 hello、叙事者取任务前关掉过期的
            timer.cancel()
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
