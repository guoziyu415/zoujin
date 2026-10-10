"""叙事者骨架（B-0 第 7 条）：按局取任务 → 事务外提取和检查 → 单事务提交 → NOTIFY。

任务就是 turns 表的一行（backend-design 3.4）：
- open：开局。W-1 的 initial_state，settle 到身份的 startT，开局前到点的节拍写成系统事件。
- talk：一轮对话。流水线（`narrator/pipeline.py`：分流 → 提取 → 第 3 步规则 → 第 4 步模型检查 → 改写、降级或拒绝）→
  提交候选事件（被否决的也写，effects 为空）、这一轮的时间（一条只推进时钟的 say 事件）和这段时间里到点的节拍。
  提取或检查两次都超时：只提交时钟事件，候选丢弃，`playthrough_metrics` 记一次。
- advance：快进（只给测试和评测）。

同一局严格串行：取任务时锁住这一局的行，有没过期的租约就不取。提交时再锁一次、校验 lastSeq 没变；变了就丢弃，
用新状态从第 3 步重来（不重新提取）。任何一步失败整轮回滚，任务放回队列，用同一个幂等键重试，三次都失败记 no_response。
账本到上限（`BudgetStop`）、第一个 429（`RateLimited`）、回放缺失（`ReplayMissing`）不重试：任务放回队列，异常往上抛。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, cast

from sqlalchemy import and_, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from zoujin_backend.config import DEADLINES
from zoujin_backend.db.events import recorded_at, to_row
from zoujin_backend.db.tables import events as events_t
from zoujin_backend.db.tables import playthrough_metrics, playthroughs, turns, utterances, world_state
from zoujin_backend.ids import IdGen
from zoujin_backend.models.text import ReplayMissing, Stop, TextModel
from zoujin_backend.narrator.pipeline import Counts, Pipeline, Spend, TurnInput, Verified
from zoujin_backend.narrator.rules import Checked
from zoujin_backend.narrator.writer import Writer
from zoujin_backend.projection import is_visible
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.trace import Tracer
from zoujin_backend.world import Book, Library
from zoujin_worldsim import SimState, initial_state, role_of

log = logging.getLogger("zoujin.narrator")

Json = Any

CHANNEL = "zoujin_commit"  # 提交后 NOTIFY，网关 LISTEN
LEASE = timedelta(seconds=30)
MAX_ATTEMPTS = 3
MAX_STALE = 5
CHECKER_CLOCK = "b0:clock"
PASSED = {"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER_CLOCK}


class Stale(Exception):
    """读取后 lastSeq 变了（中间提交了别的东西）：这次结果作废，从第 3 步重来。"""


class Gone(Exception):
    """任务已经不归这次处理了（判完了、被作废了、局被删了）。"""


@dataclass(frozen=True)
class Task:
    turn_id: str
    pid: str
    kind: str
    input_mode: str | None
    character: str | None
    minutes: int | None
    key: str
    attempts: int


@dataclass
class Planned:
    """一种任务在提交的事务里写了什么之外的结论。"""

    outcome: str | None = None  # talk：turn_settled.outcome
    minutes: int = 0  # 这一轮花了几分钟
    checked: list[Checked] = field(default_factory=list)


@dataclass
class Result:
    """一次提交写了什么（评测的 StepResult、测试用）。"""

    task: Task
    events: list[Json]
    state: SimState
    outcome: str | None = None
    minutes: int = 0
    checked: list[Checked] = field(default_factory=list)


def talk_minutes(book: Book, state: SimState) -> int:
    """一来一回的故事时间：第一〜三幕 10 分，第四幕 15 分（api-contract 3.7）。"""
    act4 = max(book.world["acts"], key=lambda a: a["order"])["start"]["t"]
    key = "talkTurnMinutesAct4" if state["t"] >= act4 else "talkTurnMinutes"
    return int(book.world["pacing"][key])


@dataclass
class Narrator:
    engine: AsyncEngine
    library: Library
    text: TextModel
    schemas: SchemaBook
    ids: IdGen = field(default_factory=IdGen)
    # 测试用：提交的每一步之前调用（步骤名），抛异常就是在这一步失败
    fault: Callable[[str], None] = field(default=lambda step: None)
    # 测试用：检查完、提交前调用（模拟中间有别的提交）
    before_commit: Callable[[Task], Awaitable[None]] | None = None
    tracer: Tracer = field(default_factory=Tracer)
    deadlines: Mapping[str, float] = field(default_factory=lambda: dict(DEADLINES))

    def __post_init__(self) -> None:
        self.pipeline = Pipeline(self.text, self.schemas, self.ids, self.tracer, self.deadlines)

    # —— 取任务 ——

    async def run(self, pid: str) -> list[Result]:
        """把这一局排着的任务按顺序做完；别的进程正在做这一局时直接返回。"""
        done: list[Result] = []
        while True:
            task = await self.claim(pid)
            if task is None:
                return done
            try:
                done.append(await self.process(task))
            except Gone:
                log.info("任务 %s 已经不用做了", task.turn_id)
            except (Stop, ReplayMissing) as e:  # 不重试：放回队列，整次停下
                log.warning("任务 %s 停下：%s", task.turn_id, type(e).__name__)
                await self.release(task, failed=False)
                raise
            except Exception:
                log.exception("任务 %s 第 %d 次失败", task.turn_id, task.attempts)
                await self.release(task, failed=task.attempts >= MAX_ATTEMPTS)

    async def claim(self, pid: str) -> Task | None:
        async with self.engine.begin() as c:
            live = await c.execute(
                select(playthroughs.c.playthrough_id).where(playthroughs.c.playthrough_id == pid).with_for_update()
            )
            if live.first() is None:
                return None
            now = func.now()
            busy = await c.execute(
                select(turns.c.turn_id).where(
                    turns.c.playthrough_id == pid, turns.c.status == "leased", turns.c.lease_until > now
                )
            )
            if busy.first() is not None:
                return None
            row = (
                (
                    await c.execute(
                        select(turns)
                        .where(
                            turns.c.playthrough_id == pid,
                            or_(
                                turns.c.status == "pending",
                                and_(turns.c.status == "leased", turns.c.lease_until <= now),
                            ),
                        )
                        .order_by(turns.c.created_at, turns.c.turn_id)
                        .limit(1)
                        .with_for_update(skip_locked=True)
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            await c.execute(
                update(turns)
                .where(turns.c.turn_id == row["turn_id"])
                .values(status="leased", lease_until=now + LEASE, attempts=turns.c.attempts + 1)
            )
            return Task(
                turn_id=row["turn_id"],
                pid=pid,
                kind=row["kind"],
                input_mode=row["input_mode"],
                character=row["character"],
                minutes=row["minutes"],
                key=row["idempotency_key"],
                attempts=row["attempts"] + 1,
            )

    async def release(self, task: Task, *, failed: bool) -> None:
        async with self.engine.begin() as c:
            if not failed:
                await c.execute(
                    update(turns)
                    .where(turns.c.turn_id == task.turn_id, turns.c.status == "leased")
                    .values(status="pending", lease_until=None)
                )
                return
            res = await c.execute(
                update(turns)
                .where(turns.c.turn_id == task.turn_id, turns.c.status == "leased")
                .values(status="failed", outcome="no_response", minutes=0, lease_until=None, settled_at=func.now())
                .returning(turns.c.turn_id)
            )
            if res.first() is not None and task.kind == "talk":
                last = await c.scalar(select(playthroughs.c.last_seq).where(playthroughs.c.playthrough_id == task.pid))
                await self._notify(c, task, seq=int(last or 0), outcome="no_response")

    # —— 处理 ——

    async def process(self, task: Task) -> Result:
        if task.kind == "open":
            return await self._commit(task, None, lambda w, book: self._open(w, book))
        if task.kind == "advance":
            minutes = int(task.minutes or 0)
            return await self._commit(task, None, lambda w, book: self._advance(w, minutes))
        if task.kind == "talk":
            return await self._talk(task)
        raise ValueError(f"不认识的任务 {task.kind}")

    async def read(self, pid: str) -> tuple[dict[str, Any], SimState]:
        async with self.engine.connect() as c:
            pt = (await c.execute(select(playthroughs).where(playthroughs.c.playthrough_id == pid))).mappings().one()
            st = await c.scalar(select(world_state.c.state).where(world_state.c.playthrough_id == pid))
        if st is None:
            raise Gone(pid)
        return dict(pt), cast(SimState, st)

    async def _talk(self, task: Task) -> Result:
        pt, state = await self.read(task.pid)
        book = self.library.version(pt["world_model_version"])
        lines = await self._lines(task.turn_id)
        turn = TurnInput(
            character=task.character,
            player=lines.get("player"),
            reply=lines.get("character"),
            mode=task.input_mode or "voice",
        )
        spend = Spend()
        span = {"playthrough_id": task.pid, "turn_id": task.turn_id}
        extracted = await self.pipeline.extract(book, state, turn, spend, span)
        for _ in range(MAX_STALE):
            if extracted.timed_out:
                verified = Verified([], Counts())
            else:
                minutes = talk_minutes(book, state)
                verified = await self.pipeline.verify(book, state, extracted.candidates, turn, minutes, spend, span)
            if self.before_commit is not None:
                await self.before_commit(task)
            try:
                plan = self._talk_plan(task, verified.checked)
                counts = extracted.counts + verified.counts
                return await self._commit(task, pt["last_seq"], plan, spend=spend, counts=counts)
            except Stale:
                log.info("lastSeq 变了，%s 从检查重来", task.turn_id)
                pt, state = await self.read(task.pid)
        raise RuntimeError(f"{task.turn_id}：lastSeq 一直在变")

    async def _lines(self, turn_id: str) -> dict[str, str | None]:
        async with self.engine.connect() as c:
            rows = (
                await c.execute(
                    select(utterances.c.speaker, utterances.c.text)
                    .where(utterances.c.turn_id == turn_id)
                    .order_by(utterances.c.recorded_at)
                )
            ).all()
        out: dict[str, str | None] = {}
        for speaker, text in rows:
            out["player" if speaker == "player" else "character"] = text
        return out

    # —— 每种任务写哪些事件（在提交的事务里、锁着这一局时调用）——

    def _open(self, w: Writer, book: Book) -> Planned:
        role = role_of(book.world, w.state["role"])
        start = int(role["startT"])
        w.settle(start)
        if w.state["t"] < start:
            act = book.acts[role.get("startAct") or book.act_of(w.state["vars"])]
            w.add(
                w.full(
                    t=start,
                    dt=0,
                    actor="system",
                    type="action",
                    origin="act",
                    place=w.player_place,
                    summary=f"{act['title']}、物語が始まった",
                    effects=[],
                    check=PASSED,
                )
            )
        return Planned()

    def _advance(self, w: Writer, minutes: int) -> Planned:
        """结算到 t0 + minutes，再写一个只推进时钟的事件（契约：时钟只由事件推出）。"""
        t0 = w.state["t"]
        t2 = t0 + minutes
        w.settle(t2)
        if w.state["t"] < t2:
            w.add(
                w.full(
                    t=t2,
                    dt=0,
                    actor="system",
                    type="action",
                    place=w.player_place,
                    summary="時が過ぎた",
                    effects=[],
                    check=PASSED,
                )
            )
        return Planned(minutes=w.state["t"] - t0)

    def _talk_plan(self, task: Task, checked: list[Checked]) -> Callable[[Writer, Book], Planned]:
        return lambda w, book: self._talk_events(w, book, task, checked)

    def _talk_events(self, w: Writer, book: Book, task: Task, checked: list[Checked]) -> Planned:
        w.settle(w.state["t"])
        t0 = w.state["t"]
        place = w.player_place
        for c in checked:
            cand = c.candidate
            extra = {k: cand[k] for k in ("beneficiary", "confirmed") if k in cand}
            ev = w.add(
                w.full(
                    t=t0,
                    dt=0,
                    actor=cand.get("actor", "player"),
                    type=cand.get("type", "say"),
                    origin=cand.get("origin", "turn"),
                    place=cand.get("place", place),
                    summary=cand["summary"],
                    effects=c.effects if c.passed else [],
                    causes=cand.get("causes", []),
                    check=c.check,
                    turn_id=task.turn_id,
                    **extra,
                )
            )
            c.candidate = {**cand, "eventId": ev["eventId"]}
        minutes = talk_minutes(book, w.state)
        role = book.roles[w.state["role"]]["name"]
        who = book.characters.get(task.character or "", {}).get("name", "誰か")
        w.add(
            w.full(
                t=t0,
                dt=minutes,
                actor="player",
                type="say",
                origin="turn",
                place=place,
                summary=f"{role}が{who}と話した",
                effects=[],
                check=PASSED,
                turn_id=task.turn_id,
            )
        )
        w.settle(w.state["t"])
        visible = [e for e in w.events if e.get("turnId") == task.turn_id and is_visible(book, e, place)]
        outcome = "committed" if visible else "rejected" if any(not c.passed for c in checked) else "no_change"
        return Planned(outcome=outcome, minutes=minutes, checked=checked)

    # —— 单事务提交 ——

    async def _commit(
        self,
        task: Task,
        read_seq: int | None,
        plan: Callable[[Writer, Book], Planned],
        *,
        spend: Spend | None = None,
        counts: Counts | None = None,
    ) -> Result:
        async with self.engine.begin() as c:
            self.fault("lock")
            pt = (
                (
                    await c.execute(
                        select(playthroughs).where(playthroughs.c.playthrough_id == task.pid).with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            if pt is None:
                raise Gone(task.pid)
            if read_seq is not None and pt["last_seq"] != read_seq:
                raise Stale(task.turn_id)
            status = await c.scalar(select(turns.c.status).where(turns.c.turn_id == task.turn_id).with_for_update())
            if status != "leased":
                raise Gone(task.turn_id)
            book = self.library.version(pt["world_model_version"])
            row = (
                await c.execute(
                    select(world_state.c.state, world_state.c.as_of_seq).where(world_state.c.playthrough_id == task.pid)
                )
            ).first()
            state: SimState = cast(SimState, row[0]) if row else initial_state(book.world, pt["role_id"])
            if state["seq"] != pt["last_seq"]:
                raise RuntimeError(f"{task.pid}：world_state 的 seq {state['seq']} 和 lastSeq {pt['last_seq']} 不一致")

            self.fault("apply")
            w = Writer(
                book,
                task.pid,
                state,
                key_base=task.key,
                turn_id=task.turn_id if task.kind == "talk" else None,
                ids=self.ids,
                now=recorded_at(),
            )
            planned = plan(w, book)
            result = Result(task, w.events, w.state, planned.outcome, planned.minutes, planned.checked)

            self.fault("validate")
            for ev in w.events:
                self.schemas.event(ev)  # 不合数据契约就抛 SchemaError，整轮回滚

            self.fault("events")
            if w.events:
                await c.execute(insert(events_t), [to_row(e) for e in w.events])
            self.fault("world_state")
            if row is None:
                await c.execute(
                    insert(world_state).values(playthrough_id=task.pid, as_of_seq=w.state["seq"], state=w.state)
                )
            else:
                await c.execute(
                    update(world_state)
                    .where(world_state.c.playthrough_id == task.pid)
                    .values(as_of_seq=w.state["seq"], state=w.state)
                )
            self.fault("playthrough")
            await c.execute(
                update(playthroughs)
                .where(playthroughs.c.playthrough_id == task.pid)
                .values(last_seq=w.state["seq"], last_active_at=func.now())
            )
            self.fault("turn")
            await c.execute(
                update(turns)
                .where(turns.c.turn_id == task.turn_id)
                .values(
                    status="done",
                    outcome=result.outcome,
                    minutes=result.minutes,
                    lease_until=None,
                    settled_at=func.now(),
                )
            )
            self.fault("metrics")
            await c.execute(
                update(playthrough_metrics)
                .where(playthrough_metrics.c.playthrough_id == task.pid)
                .values(metrics(task, spend or Spend(), counts or Counts()))
            )
            self.fault("notify")
            await self._notify(c, task, seq=w.state["seq"], outcome=result.outcome)
            self.fault("commit")
        log.info(
            "提交 %s %s：seq %d〜%d，%d 个事件",
            task.kind,
            task.turn_id,
            state["seq"] + 1,
            w.state["seq"],
            len(w.events),
        )
        return result

    async def _notify(self, c: AsyncConnection, task: Task, *, seq: int, outcome: str | None) -> None:
        payload = {"pid": task.pid, "seq": seq, "kind": task.kind, "turnId": task.turn_id, "outcome": outcome}
        await c.execute(select(func.pg_notify(CHANNEL, json.dumps(payload))))


# 一轮写进 playthrough_metrics 的：轮数、各类提示的花费（data-design 第 3 节：每局费用 = 所有 cost_*_usd 之和）、计数
COST_COLUMNS = {
    "triage": "cost_triage_usd",
    "extract": "cost_extract_usd",
    "check": "cost_check_usd",
    "rewrite": "cost_rewrite_usd",
    "reply": "cost_reply_usd",
}
COUNT_COLUMNS = {
    "triage_skipped": "turns_triage_skipped",
    "timeouts": "turns_timed_out",
    "rewritten": "candidates_rewritten",
    "downgraded": "candidates_downgraded",
    "rejected": "candidates_rejected",
    "confirm_dropped": "candidates_confirm_dropped",
}


def metrics(task: Task, spend: Spend, counts: Counts) -> dict[str, Any]:
    m = playthrough_metrics.c
    out: dict[str, Any] = {"turns": m.turns + (1 if task.kind == "talk" else 0)}
    for kind, usd in spend.usd.items():
        col = COST_COLUMNS[kind]
        out[col] = m[col] + usd
    for k, col in COUNT_COLUMNS.items():
        n = getattr(counts, k)
        if n:
            out[col] = m[col] + n
    return out
