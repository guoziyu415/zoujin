"""网关里的安全筛查（B-12，api-contract 3.12，backend-design 5.5）。`gateway/ws.py` 只在几处调这里。

- 玩家这一句的定稿一到（文字一轮的 `text`，语音一轮 Live 的 `input_final`）就开始筛查（`Guard.start`），人物照常回答。
- 判成 signal、或同一局第二次 ambiguous：`Guard.pause`：停止转发人物的回答（不推 `interrupted`、不推人物定稿），推
  `turn_settled { outcome: "paused" }` 和 `safety_pause`；这一轮写一行 `outcome: "paused"`、不写原话、不叫叙事者；
  玩家这时
  按着说话键的新一轮整个丢掉；关掉这条连接上所有人物的会话；这一局记 `paused`（`welcome.pending.safetyPause`）。
- 一局第一次 ambiguous：推 `safety_hint`（一局最多一次），这一轮带 `ambiguous` 标记照常交给叙事者（不提取事件）。
- 暂停期间对话、动作、幕末都回 `invalid_request`；`focus` 不开会话、不回错误；`safety_resume` → `safety_resumed`。
- 交给叙事者之前等筛查的结果（`Guard.result`），不会先提交再暂停。
- 判定结果不存、不进日志（S-057），`playthrough_metrics` 只记次数。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update

from zoujin_backend.config import Settings
from zoujin_backend.db import store
from zoujin_backend.db.tables import turns
from zoujin_backend.models.armor import armor
from zoujin_backend.models.text import text_model
from zoujin_backend.safety import NOT_SCREENED, SafetyState, Screen, Screener, decide
from zoujin_backend.trace import Tracer

if TYPE_CHECKING:
    from zoujin_backend.gateway.ws import Conn, Turn

log = logging.getLogger("zoujin.gateway")

Json = Any

PAUSED_REFUSED = ("text", "activity_start", "action", "act_choose", "act_propose", "act_landed")
# 暂停期间的 focus（重连时前端自动发）：不开会话、不回错误；safety_resume 以后前端重新 focus（UX 在 #112 的评审）


def build_screener(settings: Settings, tracer: Tracer | None = None) -> Screener:
    """网关用的筛查：文本模型和 Model Armor 按 `ZJ_MODEL`（CI 和容器是假的；真的只在 Mac 上）。"""
    return Screener(
        text=text_model(settings.model, fake_rules=settings.fake_text, replays=settings.replays, settings=settings),
        armor=armor(settings.model, replays=settings.replays),
        tracer=tracer or Tracer(),
    )


def counts_of(s: Screen) -> dict[str, int]:
    out = {}
    if s.unscreened:
        out["safety_unscreened"] = 1
    if s.refused:
        out["safety_refused"] = 1
    if s.armor_failed:
        out["armor_errors"] = 1
    return out


class Guard:
    """一条连接上的安全状态。状态本身在库里（`playthroughs.safety`），这里每次判完读、改、写回。"""

    def __init__(self, conn: Conn) -> None:
        self.conn = conn
        self.paused = False  # 内存里的副本：handle() 先看它
        self.lock = asyncio.Lock()

    @property
    def screener(self) -> Screener:
        return self.conn.gw.screener

    async def load(self) -> None:
        async with self.conn.gw.engine.connect() as c:
            self.paused = SafetyState.of(await store.safety_state(c, self.conn.pid)).paused

    def start(self, t: Turn, said: str | None) -> None:
        """这一轮的玩家定稿到了：开始筛查（一轮只筛一次）。"""
        if t.screen is not None or not said:
            return
        t.screen = asyncio.ensure_future(self._run(t, said))

    async def result(self, t: Turn) -> Screen:
        """交给叙事者之前等筛查的结果；这一轮没有玩家的话（没听清、人物先开口）= 没筛。"""
        if t.screen is None:
            return NOT_SCREENED
        try:
            return await t.screen
        except Exception:
            log.exception("安全筛查出错（%s）", t.turn_id)
            return NOT_SCREENED

    async def _run(self, t: Turn, said: str) -> Screen:
        conn = self.conn
        s = await self.screener.screen(said, playthrough_id=conn.pid, turn_id=t.turn_id)
        decision = await self._decide(s)
        if decision == "pause":
            await self.pause(t)
        elif decision == "hint":
            conn.monitor.calm()
            await conn.send({"type": "safety_hint"})
        return s

    async def _decide(self, s: Screen) -> str:
        conn = self.conn
        async with self.lock, conn.gw.engine.begin() as c:
            st = SafetyState.of(await store.safety_state(c, conn.pid, lock=True))
            if st.paused:  # 已经暂停了（前一句）：这一句不再算
                return "pass"
            decision = decide(s, st)
            await store.set_safety(c, conn.pid, st.to_json())
            by = counts_of(s)
            if decision == "pause":
                by["safety_pauses"] = 1
            elif decision == "hint":
                by["safety_hints"] = 1
            await store.count(c, conn.pid, **by)
        if decision == "pause":
            self.paused = True
        return decision

    async def screen_plan(self, said: str | None) -> Screen:
        """幕末说的打算也筛（玩家的每一句）：signal → 暂停，打算不交给叙事者。没有人物在说，不用等人物的回答。"""
        if not said:
            return NOT_SCREENED
        s = await self.screener.screen(said, playthrough_id=self.conn.pid)
        decision = await self._decide(s)
        if decision == "pause":
            await self.pause(None)
        elif decision == "hint":
            self.conn.monitor.calm()
            await self.conn.send({"type": "safety_hint"})
        return s

    async def pause(self, t: Turn | None) -> None:
        """停下这一轮（和之后还没交上去的几轮）、丢掉按着说话键的新一轮、关掉会话，推 turn_settled 和 safety_pause。"""
        conn = self.conn
        stopped = []
        cur = conn.turn
        for x in (t, cur):
            if x is None or x.paused or x in stopped:
                continue
            if not x.ended:  # 玩家还按着说话键：整个丢掉，之后的音频和 activity_end 都忽略（3.12）
                conn.memory.pop(x.turn_id, None)
                if conn.turn is x:
                    conn.turn = None
                continue
            if x.handing:  # 已经在写进库里（交给叙事者）了：来不及停，叙事者照常判
                continue
            x.paused = True
            stopped.append(x)
            if x.stream is not None and not x.stream.done():
                x.stream.cancel()
        if conn.plan is not None:  # 幕末按着说话键说打算：同样丢掉
            conn.plan.retracted = True
            conn.plan = None
        for x in stopped:
            conn.settled.add(x.turn_id)
            await conn.send(
                {"type": "turn_settled", "turnId": x.turn_id, "outcome": "paused", "eventIds": [], "minutes": 0}
            )
        await conn.send({"type": "safety_pause"})
        await conn.close_sessions()

    async def write_paused(self, t: Turn) -> None:
        """暂停的一轮：写一行 outcome = paused、0 分，不写原话，不叫叙事者（3.12）。"""
        conn = self.conn
        async with conn.gw.engine.begin() as c:
            exists = await c.scalar(select(turns.c.turn_id).where(turns.c.turn_id == t.turn_id))
            if exists is not None:
                return
            await store.enqueue(
                c,
                conn.gw.ids,
                conn.pid,
                kind="talk",
                turn_id=t.turn_id,
                input_mode=t.mode,
                character=t.character,
                turn_seq=t.turn_seq,
                status="done",
            )
            await c.execute(
                update(turns)
                .where(turns.c.turn_id == t.turn_id)
                .values(outcome="paused", minutes=0, settled_at=func.now())
            )

    async def resume(self) -> None:
        conn = self.conn
        async with self.lock, conn.gw.engine.begin() as c:
            st = SafetyState.of(await store.safety_state(c, conn.pid, lock=True))
            st.paused = False
            await store.set_safety(c, conn.pid, st.to_json())
        self.paused = False
        await conn.send({"type": "safety_resumed"})
