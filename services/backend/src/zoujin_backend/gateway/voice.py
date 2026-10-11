"""一条连接上的 Live 会话（B-10，backend-design 3.2）：预热、切换、定期重建、GoAway、中途断了、中途更新局势、闲置关闭、
花费。`ws.py` 只调这里；会话放在 `Conn.sessions`（B-4 的作废、意图确认、落地也看它）。

| 情况 | 做法 |
|---|---|
| `near` | 2 秒去抖后预热（不推消息）。一条连接最多 1 个 focus 的 + 1 个预热，预热别人时关掉旧的预热 |
| `far` | 取消还没开始的预热 |
| `focus` | 会话在、活着：照旧就绪；正在开或没有：`session_preparing { switch }`，开好推 `session_ready` |
| 定期重建 | 完成第 N 轮（`ZJ_LIVE_REBUILD_TURNS`，7〜10，默认 8）以后，在停顿处后台开新会话，换上、关旧的。不推消息 |
| GoAway | 同上，立即开始 |
| 中途断了 | 那一轮按被打断收（`ws.py`）；然后 `session_preparing { rebuild }` 重开（玩家不在看他就不推） |
| 开不起来 | 连续 2 次（或配额、账本到上限）：`degraded { voice: false }`，这条连接先不开语音，下一次 `focus` 再试 |
| 叙事者提交了 | 开着的会话里局势变了就 `note()` 送变了的条目；在说话的一轮里不送，等这一轮交上去 |
| 闲置 | 离开人物 2 分钟关掉（按 `ZJ_SPEED` 缩短；速度 0 时不关，测试另设） |

「停顿」= 这个人物没有还没交上去的一轮（`Turn.submitted`）。换会话前一直等停顿；开新会话期间又说了一轮，新会话里没有
那一轮，就丢掉重开。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import update

from zoujin_backend.db import store
from zoujin_backend.db.tables import playthrough_metrics
from zoujin_backend.gateway import brief
from zoujin_backend.models.gemini_live import LiveLostQuota
from zoujin_backend.models.live import LiveEvent, LiveLost, LiveSession

if TYPE_CHECKING:
    from zoujin_backend.gateway.ws import Conn, Turn

log = logging.getLogger("zoujin.gateway")

Json = Any

SESSION_ETA_MS = 800  # 预热、切换人物、重建会话（api-contract 3.5 的例子）
WARM_DEBOUNCE_S = 2.0  # near 的服务端去抖（3.2）
IDLE_S = 120.0  # 离开人物 2 分钟关闭（ux-design 7.2）
MAX_OPEN_FAILS = 2
SWAP_RETRIES = 3  # 开新会话期间又说了一轮：丢掉重开，最多几次
NEXT_TURN_USD = 0.03  # 下一轮的预计（账本到上限的判断，偏高：30 轮时每轮约 0.029 美元，S-073 ⑤）


@dataclass
class Voices:
    conn: Conn
    opening: dict[str, asyncio.Task[LiveSession]] = field(default_factory=dict)
    swapping: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    facts: dict[str, tuple[str, ...]] = field(default_factory=dict)  # 上次送进这个人物会话的局势条目
    stale: set[str] = field(default_factory=set)  # 局势变了、还没送（在说话的一轮里）
    warm_task: asyncio.Task[None] | None = None
    warm_for: str | None = None
    idle: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    fails: int = 0
    off: str | None = None  # 降级的原因（service / budget）；下一次 focus 再试
    idle_s: float | None = None  # None：按 ZJ_SPEED 算；测试直接设

    # —— 小工具 ——

    @property
    def sessions(self) -> dict[str, LiveSession]:
        return self.conn.sessions

    @property
    def speed(self) -> float:
        return self.conn.gw.settings.speed

    @property
    def rebuild_turns(self) -> int:
        return self.conn.gw.settings.live_rebuild_turns

    def busy(self, character: str) -> bool:
        """这个人物有还没交上去的一轮（停顿 = 不 busy）。"""
        t = self.conn.turn
        return t is not None and t.character == character and not t.submitted.is_set()

    def _spawn(self, coro: Any) -> asyncio.Task[Any]:
        return self.conn.gw.spawn(coro)

    async def _brief(self, character: str) -> brief.Brief:
        gw, pid = self.conn.gw, self.conn.pid
        async with gw.engine.connect() as c:
            pt = await gw.pt(c, pid)
            st = await store.sim_state(c, pid)
        if pt is None or st is None:
            raise LiveLost("这一局没有状态")
        recent = [r for _, r in self.conn.recent.get(character, [])]
        return brief.build(pt.book, st, character, recent)

    # —— 开会话 ——

    async def _open(self, character: str, reason: str) -> LiveSession:
        """拼系统指令、开会话、挂上变化的回调。Trace：live.session（不带指令的文字）。"""
        b = await self._brief(character)
        recent = [r for _, r in self.conn.recent.get(character, [])]
        with self.conn.gw.tracer.span(
            "live.session",
            playthrough_id=self.conn.pid,
            character=character,
            reason=reason,
            prompt_version=brief.version(),
            prompt_chars=len(b.system),
        ) as sp:
            try:
                s = await self.conn.gw.live.open(character, recent, b.system)
            except Exception:
                sp.set(status="failed")
                raise
            sp.set(status="ok")
        self.facts[character] = b.facts
        self.stale.discard(character)
        s.on_change = lambda: self._changed(character, s)
        return s

    def _ensure(self, character: str, reason: str) -> asyncio.Task[LiveSession]:
        """正在开的就用那一个；没有就开一个。开好装进 sessions（换下来的旧会话关掉）。"""
        task = self.opening.get(character)
        if task is not None and not task.done():
            return task

        async def run() -> LiveSession:
            s = await self._open(character, reason)
            if self.conn.closed.is_set():  # 开的时候连接断了：不留没人管的会话（B-11 之前断线就全关）
                await s.close()
                raise LiveLost("连接已经断了")
            old = self.sessions.get(character)
            self.sessions[character] = s
            if old is not None and old is not s:
                await old.close()
            return s

        task = asyncio.ensure_future(run())
        self.opening[character] = task

        def forget(done: asyncio.Task[LiveSession]) -> None:
            if self.opening.get(character) is done:
                self.opening.pop(character, None)

        task.add_done_callback(forget)
        return task

    async def prepare(self, character: str, reason: str, *, announce: bool = True) -> None:
        """开会话并推准备、就绪（切换人物、作废后重建、中途断了）。新的一轮等 `ready` 再送进去（ws._stream）。"""
        conn = self.conn
        if announce:
            await conn.send(
                {"type": "session_preparing", "character": character, "reason": reason, "etaMs": SESSION_ETA_MS}
            )
        start = time.monotonic()
        conn.ready_at[character] = start + SESSION_ETA_MS / 1000 * self.speed
        ev = conn.ready[character] = asyncio.Event()

        async def ready() -> None:
            try:
                ok = await self._try_open(character, reason)
                await asyncio.sleep(max(0.0, conn.ready_at[character] - time.monotonic()))
                if ok and conn.focused == character and (announce or reason == "switch"):
                    await conn.send({"type": "session_ready", "character": character, "voiceAvailable": True})
            finally:
                ev.set()

        self._spawn(ready())

    async def _try_open(self, character: str, reason: str) -> bool:
        """开一次，失败再试一次；连续失败到上限或配额就降级。"""
        for _ in range(MAX_OPEN_FAILS):
            try:
                await self._ensure(character, reason)
            except LiveLostQuota:
                await self.degrade("service")
                return False
            except (LiveLost, OSError) as e:
                self.fails += 1
                log.info("开 %s 的会话失败（第 %d 次，%s）", character, self.fails, type(e).__name__)
                if self.fails >= MAX_OPEN_FAILS:
                    await self.degrade("service")
                    return False
                continue
            self.fails = 0
            return True
        return False

    async def degrade(self, why: str) -> None:
        if self.off == why:
            return
        self.off = why
        await self.conn.send({"type": "degraded", "voice": False, "reason": why})
        if self.conn.focused is not None:
            await self.conn.send({"type": "session_ready", "character": self.conn.focused, "voiceAvailable": False})

    async def open_now(self, character: str, reason: str) -> LiveSession | None:
        """落地先开口（B-3）：不推准备，直接开好。"""
        if not await self._try_open(character, reason):
            return None
        self.conn.ready_at[character] = time.monotonic()
        return self.sessions.get(character)

    # —— 前端的 near / far / focus ——

    def near(self, character: str) -> None:
        conn = self.conn
        if not conn.characters.get(character, {}).get("talkable") or self.off:
            return
        s = self.sessions.get(character)
        if (s is not None and s.alive) or character in self.opening:
            return
        if self.warm_task is not None and not self.warm_task.done():
            self.warm_task.cancel()
        self.warm_for = character

        async def warm() -> None:
            await asyncio.sleep(WARM_DEBOUNCE_S * self.speed)
            # 预热别人：关掉旧的预热（不在 focus、也没在说的），最多 1 个 focus + 1 个预热
            for other, sess in list(self.sessions.items()):
                if other not in (character, conn.focused) and not self.busy(other):
                    self.sessions.pop(other, None)
                    await sess.close()
            conn.ready_at[character] = time.monotonic() + SESSION_ETA_MS / 1000 * self.speed
            with contextlib.suppress(LiveLost, OSError):
                await self._ensure(character, "warm")

        self.warm_task = self._spawn(warm())

    def far(self, character: str) -> None:
        if self.warm_for == character and self.warm_task is not None and not self.warm_task.done():
            self.warm_task.cancel()
            self.warm_for = None

    async def focus(self, character: str) -> None:
        conn = self.conn
        prev = conn.focused
        conn.focused = character
        self._cancel_idle(character)
        if prev is not None and prev != character:
            self._schedule_idle(prev)
        if self.off is not None:
            self.off = None  # 再试一次
            self.fails = 0
        s = self.sessions.get(character)
        if s is not None and s.alive and character not in self.opening:

            async def ready() -> None:
                await asyncio.sleep(max(0.0, conn.ready_at.get(character, 0.0) - time.monotonic()))
                if conn.focused == character:
                    await conn.send({"type": "session_ready", "character": character, "voiceAvailable": True})

            self._spawn(ready())
            return
        await self.prepare(character, "switch")

    def unfocus(self) -> None:
        if self.conn.focused is not None:
            self._schedule_idle(self.conn.focused)
        self.conn.focused = None

    # —— 闲置 ——

    def _idle_seconds(self) -> float | None:
        if self.idle_s is not None:
            return self.idle_s
        return IDLE_S * self.speed if self.speed > 0 else None

    def _schedule_idle(self, character: str) -> None:
        secs = self._idle_seconds()
        if secs is None:
            return
        self._cancel_idle(character)

        async def close_later() -> None:
            await asyncio.sleep(secs)
            if self.conn.focused == character or self.busy(character) or self.warm_for == character:
                return
            s = self.sessions.pop(character, None)
            if s is not None:
                log.info("%s 闲置，关掉会话", character)
                await s.close()

        self.idle[character] = self._spawn(close_later())

    def _cancel_idle(self, character: str) -> None:
        task = self.idle.pop(character, None)
        if task is not None:
            task.cancel()

    # —— 作废后重建（B-4）、定期重建、GoAway、中途断了 ——

    async def rebuild(self, character: str) -> None:
        """作废以后：关掉旧的、开新的（没有那一轮），推准备和就绪。"""
        task = self.swapping.pop(character, None)
        if task is not None:
            task.cancel()
        old = self.sessions.pop(character, None)
        if old is not None:
            await old.close()
        await self.prepare(character, "rebuild")

    def _changed(self, character: str, s: LiveSession) -> None:
        """会话叫过来：GoAway 或断了。在说话的一轮里先不动，等这一轮交上去（after_turn）。"""
        if self.sessions.get(character) is not s or self.busy(character):
            return
        self.after_turn(character)

    def after_turn(self, character: str) -> None:
        """这个人物的一轮交上去了（停顿）：送攒着的局势更新；会话断了就重开，轮数到了或 GoAway 就换。"""
        s = self.sessions.get(character)
        if s is None or character in self.opening or self.conn.closed.is_set():
            return
        if not s.alive:
            self.sessions.pop(character, None)
            self._spawn(self.prepare(character, "rebuild", announce=self.conn.focused == character))
            return
        if character in self.stale:
            self._spawn(self._note(character))
        if (s.going_away or s.turns >= self.rebuild_turns) and character not in self.swapping:
            self.swapping[character] = self._spawn(self._swap(character, "goaway" if s.going_away else "turns"))

    async def _swap(self, character: str, reason: str) -> None:
        """先开新会话、再关旧会话，玩家察觉不到（不推消息）。开的时候又说了一轮：新会话里没有那一轮，丢掉重开。"""
        try:
            for _ in range(SWAP_RETRIES):
                old = self.sessions.get(character)
                if old is None:
                    return
                before = old.turns
                try:
                    new = await self._open(character, f"rebuild_{reason}")
                except (LiveLost, OSError) as e:
                    log.info("换 %s 的会话没开起来（%s），下一个停顿再试", character, type(e).__name__)
                    return
                while self.busy(character):
                    t = self.conn.turn
                    assert t is not None
                    await t.submitted.wait()
                if self.sessions.get(character) is not old or self.conn.closed.is_set():  # 期间被作废重建、断线了
                    await new.close()
                    return
                if old.turns != before and old.alive:
                    await new.close()
                    continue
                self.sessions[character] = new
                self.conn.ready_at[character] = time.monotonic()
                await old.close()
                return
        finally:
            if self.swapping.get(character) is asyncio.current_task():
                self.swapping.pop(character, None)

    # —— 中途更新局势 ——

    async def refresh(self) -> None:
        """叙事者提交了：每条开着的会话，局势变了就送变了的条目；在说话的送不了，记下来等这一轮交上去。"""
        for character, s in list(self.sessions.items()):
            if not s.alive:
                continue
            if self.busy(character):
                self.stale.add(character)
                continue
            await self._note(character)

    async def _note(self, character: str) -> None:
        s = self.sessions.get(character)
        if s is None or not s.alive:
            return
        try:
            b = await self._brief(character)
        except LiveLost:
            return
        self.stale.discard(character)
        msg = brief.changes(self.facts.get(character, ()), b.facts)
        self.facts[character] = b.facts
        if msg is None:
            return
        await s.note(msg)
        with self.conn.gw.tracer.span(
            "live.note", playthrough_id=self.conn.pid, character=character, notes=msg.count("\n")
        ):
            pass

    # —— 花费 ——

    async def can_speak(self) -> bool:
        """账本到上限就降级（budget），这一轮不开始。"""
        ledger = self.conn.gw.live_ledger
        if ledger is None:
            return self.off is None
        try:
            ledger.before(NEXT_TURN_USD)
        except Exception:  # noqa: BLE001 - BudgetStop
            await self.degrade("budget")
            return False
        return self.off is None

    async def account(self, t: Turn, ev: LiveEvent, session: LiveSession, before_s: float) -> None:
        """一轮的花费：账本（真 Live 时）、`cost_live_usd`、Trace 的 live.turn（不带原话）。"""
        conn = self.conn
        usage = dict(ev.usage or {})
        first_ms = -1 if t.first_audio is None or t.released is None else round((t.first_audio - t.released) * 1000)
        reply_s = max(0.0, session.audio_seconds - before_s)
        if conn.gw.live_ledger is not None:
            extra = {
                "sessionTurn": session.turns,
                "sessionAudioMsBefore": round(before_s * 1000),
                "replyAudioMs": round(reply_s * 1000),
                "firstAudioMs": first_ms,
            }
            conn.gw.live_ledger.add(
                kind=f"live.turn/{conn.pid}", model=conn.gw.live_model_name, usage=usage | extra, cost=ev.usd
            )
        if ev.usd:
            async with conn.gw.engine.begin() as c:
                m = playthrough_metrics.c
                await c.execute(
                    update(playthrough_metrics)
                    .where(m.playthrough_id == conn.pid)
                    .values(cost_live_usd=m.cost_live_usd + ev.usd)
                )
        with conn.gw.tracer.span(
            "live.turn",
            playthrough_id=conn.pid,
            turn_id=t.turn_id,
            character=t.character,
            mode=t.mode,
            first_audio_ms=first_ms,
            audio_s=round(reply_s, 2),
            session_audio_s=round(before_s, 2),
            session_turn=session.turns,
            cost_usd=round(ev.usd, 6),
        ):
            pass

    async def close_all(self) -> None:
        for task in [*self.opening.values(), *self.swapping.values(), *self.idle.values()]:
            task.cancel()
        if self.warm_task is not None:
            self.warm_task.cancel()
        for s in list(self.sessions.values()):
            await s.close()
        self.sessions.clear()
