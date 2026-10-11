"""网关的总状态：数据库、世界模型、Schema、叙事者的调用、开着的连接。REST（rest.py）和 WebSocket（ws.py）都从这里拿。

推给前端的东西都由数据库里的事件现算（projection.py）：
- 快照 = world_state 缓存的 SimState 的投影，加上局上记的位置点和待处理的（B-3，`store.Run`）；
- commit = 同一次提交写的一段事件（幂等键前一段相同，`commit_key`），patch 是这一段前后两个快照的差。
  意图确认答「是」的那次提交（B-4）：`turnId` 是原来那一轮，重查没过时 `narration` 带一句（`turns.result`）。
  玩家的位置点不进 WorldState（契约 3.1）：做完情境动作、幕切换落地的 `patch.player.spot` 按这次提交的结果给
  （`turns.result.playerSpot`），动作（`move`、`go`）的不带（B-3 第 1 条）。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from zoujin_worldsim import SimState, apply, initial_state

from zoujin_backend.config import Settings
from zoujin_backend.db import store
from zoujin_backend.db.events import commit_key, recorded_at
from zoujin_backend.db.store import Run
from zoujin_backend.db.tables import turns
from zoujin_backend.ids import IdGen
from zoujin_backend.models.live import LiveModel
from zoujin_backend.projection import is_visible, patch, snapshot, visible_event, with_locations
from zoujin_backend.safety import Screener
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.trace import Tracer
from zoujin_backend.world import Book, Library

if TYPE_CHECKING:
    from zoujin_backend.gateway.ws import Conn

log = logging.getLogger("zoujin.gateway")

Json = Any

RUNS_PER_DAY = 5  # 每账号每天开局数（backend-design 5.2）；B-0 只显示，不拦
VOICE_MINUTES = 60  # 预算是 M2 的卡
HANDOFF_WAIT_S = 5.0  # 重连的 hello 最多等旧连接把断线那一轮写完几秒（正常是毫秒级）


class NarratorClient(Protocol):
    async def run(self, pid: str) -> int: ...


class HttpNarrator:
    """本地走 HTTP（两个进程），形状按以后 Cloud Run 服务间调用的样子。transport 给测试接进程内的叙事者。"""

    def __init__(self, base_url: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0, transport=transport)

    async def run(self, pid: str) -> int:
        r = await self.client.post(f"/internal/v1/playthroughs/{pid}/run")
        r.raise_for_status()
        return int(r.json()["processed"])

    async def close(self) -> None:
        await self.client.aclose()


@dataclass
class Pt:
    """一局在网关看来的样子。"""

    pid: str
    user_id: str
    book: Book
    role_id: str
    status: str
    last_seq: int
    last_active_at: Any
    run: Run = field(default_factory=Run)


@dataclass
class Gateway:
    settings: Settings
    engine: AsyncEngine
    library: Library
    schemas: SchemaBook
    live: LiveModel
    narrator: NarratorClient
    ids: IdGen = field(default_factory=IdGen)
    conns: dict[str, Conn] = field(default_factory=dict)  # 一局一条连接（第 4 节 4009）
    draining: bool = False
    tasks: set[asyncio.Task[Any]] = field(default_factory=set)
    # 每局还在交给叙事者的对话轮次（`_finish`）：重连的 hello 先等旧连接的这些写完，lastTurn 才准（第 4 节）
    handing: dict[str, set[asyncio.Task[Any]]] = field(default_factory=dict)
    tracer: Tracer = field(default_factory=Tracer)  # B-4：gateway.retract
    # B-12：玩家每一句的安全筛查（文本模型和 Model Armor 按 ZJ_MODEL；不给就按 settings 建，测试可以换）
    screener: Screener = field(default=None)  # type: ignore[assignment]
    # 测试用：每条发出的服务端消息（已过 Schema）
    on_send: Callable[[Json], None] | None = None

    def __post_init__(self) -> None:
        if self.screener is None:
            from zoujin_backend.gateway.safety import build_screener

            self.screener = build_screener(self.settings, self.tracer)

    # —— 局 ——

    async def pt(self, c: AsyncConnection, pid: str) -> Pt | None:
        row = await store.playthrough(c, pid)
        if row is None:
            return None
        return Pt(
            pid=pid,
            user_id=row["user_ref"],
            book=self.library.version(row["world_model_version"]),
            role_id=row["role_id"],
            status=row["status"],
            last_seq=row["last_seq"],
            last_active_at=row["last_active_at"],
            run=Run.of(row),
        )

    async def snapshot(self, pid: str) -> Json | None:
        """2.3 的快照；开局任务还没做完时先叫叙事者做。"""
        for attempt in range(2):
            async with self.engine.connect() as c:
                pt = await self.pt(c, pid)
                st = await store.sim_state(c, pid)
            if pt is None:
                return None
            if st is not None:
                return snapshot(pt.book, pid, pt.role_id, pt.status, st, st["seq"], pt.run)
            if attempt == 0:
                await self.narrator.run(pid)
        raise RuntimeError(f"{pid}：叙事者没写开局")

    async def active_ref(self, c: AsyncConnection, pt: Pt) -> Json:
        st = await store.sim_state(c, pt.pid)
        t = st["t"] if st is not None else int(pt.book.roles[pt.role_id]["startT"])
        act = pt.book.act_of(st["vars"]) if st is not None else pt.book.act_of({})
        return {
            "playthroughId": pt.pid,
            "roleId": pt.role_id,
            "roleName": pt.book.roles[pt.role_id]["name"],
            "actId": act,
            "tLabel": pt.book.label(t),
            "updatedAt": recorded_at(pt.last_active_at),
        }

    # —— 推送 ——

    async def commits(self, pid: str, after_seq: int, upto_seq: int | None = None) -> tuple[list[Json], int]:
        """after_seq 之后的 commit 消息（3.4），和推到的 seq。按提交分段，每段一条；全是不可见事件的也推一条。"""
        async with self.engine.connect() as c:
            pt = await self.pt(c, pid)
            if pt is None:
                return [], after_seq
            log_ = await store.event_log(c, pid, pt.book.version)
            keys = {commit_key(e["idempotencyKey"]) for e in log_ if e["seq"] > after_seq}
            rows = (
                await c.execute(select(turns.c.turn_id, turns.c.kind, turns.c.result).where(turns.c.turn_id.in_(keys)))
            ).all()
        kinds = {r.turn_id: r.kind for r in rows}
        results = {r.turn_id: r.result or {} for r in rows}
        book = pt.book
        state = initial_state(book.world, pt.role_id)
        segments: list[list[Json]] = []
        for ev in log_:
            if upto_seq is not None and ev["seq"] > upto_seq:
                break
            if ev["seq"] <= after_seq:
                state = apply(book.world, state, ev)
                continue
            if segments and commit_key(segments[-1][-1]["idempotencyKey"]) == commit_key(ev["idempotencyKey"]):
                segments[-1].append(ev)
            else:
                segments.append([ev])
        out = []
        sent = after_seq
        for seg in segments:
            msg, state = self._commit(book, pt, state, seg, kinds, results)
            out.append(msg)
            sent = seg[-1]["seq"]
        return out, sent

    def _commit(
        self,
        book: Book,
        pt: Pt,
        before: SimState,
        seg: Sequence[Json],
        kinds: dict[str, str],
        results: dict[str, Json],
    ) -> tuple[Json, SimState]:
        state = before
        visible = []
        for ev in seg:
            if is_visible(book, ev, state["vars"]["var.player.location"]):
                visible.append(visible_event(book, ev, pt.role_id))
            state = apply(book.world, state, ev)
        from_seq = seg[0]["seq"]
        key = commit_key(seg[0]["idempotencyKey"])
        # 人物的站位按局上现在记的位置点排；玩家的 spot 见模块说明
        snap_before = with_locations(
            snapshot(book, pt.pid, pt.role_id, pt.status, before, from_seq - 1, pt.run), before
        )
        snap_after = with_locations(snapshot(book, pt.pid, pt.role_id, pt.status, state, seg[-1]["seq"], pt.run), state)
        diff = patch(snap_before, snap_after)
        player = diff.pop("player", {})
        if kinds.get(key) == "action":  # move、go 不带 spot（前端收到 spot 会把玩家直接摆过去）
            player.pop("spot", None)
        spot = results.get(key, {}).get("playerSpot")
        if spot is not None:
            player["spot"] = spot
        if player:
            diff["player"] = player
        msg: Json = {
            "type": "commit",
            "fromSeq": from_seq,
            "seq": seg[-1]["seq"],
            "events": visible,
            "patch": diff,
            "memories": [],
            "promises": [],
            "narration": [],
            "cue": None,
            "reveal": None,
        }
        if kinds.get(key) == "talk":
            msg["turnId"] = key
        if kinds.get(key) == "confirm":
            done = results.get(key, {})
            if done.get("turnId"):
                msg["turnId"] = done["turnId"]
            msg["narration"] = list(done.get("narration", []))
        return msg, state

    async def visible_events(self, pid: str, after_seq: int, limit: int) -> list[Json]:
        """2.4：玩家可见的事件。只改时间的、玩家不在场的、被否决的占 seq 但不在这里。"""
        async with self.engine.connect() as c:
            pt = await self.pt(c, pid)
            if pt is None:
                return []
            log_ = await store.event_log(c, pid, pt.book.version)
        state = initial_state(pt.book.world, pt.role_id)
        out = []
        for ev in log_:
            if ev["seq"] > after_seq and is_visible(pt.book, ev, state["vars"]["var.player.location"]):
                out.append(visible_event(pt.book, ev, pt.role_id))
                if len(out) >= limit:
                    break
            state = apply(pt.book.world, state, ev)
        return out

    async def on_commit(self, payload: Json) -> None:
        """叙事者提交后的 NOTIFY（hub.py 转过来）：这一局开着连接就推。"""
        conn = self.conns.get(payload["pid"])
        if conn is not None:
            await conn.on_commit(payload)

    # —— 叙事者 ——

    def kick(self, pid: str) -> None:
        """叫叙事者处理这一局排着的任务（不等）。失败的任务留在队列里，下一次调用时重试。"""
        self.spawn(self._kick(pid))

    async def _kick(self, pid: str) -> None:
        try:
            await self.narrator.run(pid)
        except Exception:
            log.exception("调叙事者失败（%s）", pid)

    def spawn(self, coro: Awaitable[Any]) -> asyncio.Task[Any]:
        task: asyncio.Task[Any] = asyncio.ensure_future(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    def hand(self, pid: str, coro: Awaitable[Any]) -> asyncio.Task[Any]:
        """把一轮交给叙事者（`_finish`），按局记着，写完就去掉。"""
        task = self.spawn(coro)
        mine = self.handing.setdefault(pid, set())
        mine.add(task)

        def done(t: asyncio.Task[Any]) -> None:
            mine.discard(t)
            if not mine and self.handing.get(pid) is mine:
                del self.handing[pid]

        task.add_done_callback(done)
        return task

    async def handed(self, pid: str) -> None:
        """等这一局还在交的轮次写完，最多 `HANDOFF_WAIT_S` 秒。快速重连时旧连接断线那一轮还没写下来，
        hello 算的 lastTurn 会落后一轮，前端照规矩重发，人物就答两次（#100 评审）。"""
        pending = self.handing.get(pid)
        if pending:
            _, late = await asyncio.wait(set(pending), timeout=HANDOFF_WAIT_S)
            if late:
                log.warning("重连时还有 %d 轮没交完（%s）", len(late), pid)

    # —— 关机 ——

    async def goaway(self, reconnect_after_ms: int = 1000) -> None:
        """收到 SIGTERM：每条连接先推 goaway，再以 1012 关闭（第 4 节）。"""
        self.draining = True
        conns = list(self.conns.values())
        for conn in conns:
            await conn.send({"type": "goaway", "reason": "deploy", "reconnectAfterMs": reconnect_after_ms})
        for conn in conns:
            await conn.close(1012, "service restart")
