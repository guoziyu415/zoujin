"""叙事者骨架（B-0 第 7 条）：按局取任务 → 事务外提取和检查 → 单事务提交 → NOTIFY。

任务就是 turns 表的一行（backend-design 3.4）：
- open：开局。W-1 的 initial_state，settle 到身份的 startT，开局前到点的节拍写成系统事件。
- talk：一轮对话。流水线（`narrator/pipeline.py`：分流 → 提取 → 第 3 步规则 → 第 4 步模型检查 → 改写、降级或拒绝）→
  提交候选事件（被否决的也写，effects 为空）、这一轮的时间（一条只推进时钟的 say 事件）和这段时间里到点的节拍。
  提取或检查两次都超时：只提交时钟事件，候选丢弃，`playthrough_metrics` 记一次。
- advance：快进（只给测试和评测）。
- B-3：action（动作，`narrator/actions.py`）、choose（幕末选去处）、plan（幕末说出打算，`narrator/plans.py`）。
  每次提交以后看这一幕收了没有（`Writer.closed`）：收了就把幕末的去处记在局上，推 `act_ended`。收幕以后、选定之前
  才轮到的对话和动作 0 分、不写事件、不调模型。提交以后要推的消息（固定演出、turn_settled、action_result、
  act_plan_result、act_transition、act_ended）按顺序记在 `turns.result`，网关推完 commit 以后照着推。
- B-4：confirm（回答意图确认，`narrator/confirm.py`）；对话里要确认的候选存成草稿。对话和用声音说的打算有提交窗口
  （`turns.commit_after`）：判完、没到时候就等（不占事务），这期间网关可以把这一轮作废（`status = retracted`），
  提交时发现不是 leased 就丢掉结果、不推任何消息。取任务之前先给到期的草稿写超时的任务。
- B-13：提交的事件里有要写记忆的（`narrator/memory.py`），提交的事务里先不 NOTIFY；事务之后并行调模型写记忆
  （不占事务、不重发），第二个事务存记忆、记计数、把这次的记忆变化记进 `turns.result.memories`，再 NOTIFY。
  写记忆出了任何错也照样 NOTIFY，这一轮的结果不受影响。

同一局严格串行：取任务时锁住这一局的行，有没过期的租约就不取。提交时再锁一次、校验 lastSeq 没变；变了就丢弃，
用新状态从第 3 步重来（不重新提取）。任何一步失败整轮回滚，任务放回队列，用同一个幂等键重试，三次都失败记 no_response。
账本到上限（`BudgetStop`）、第一个 429（`RateLimited`）、回放缺失（`ReplayMissing`）不重试：任务放回队列，异常往上抛。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, cast

from sqlalchemy import and_, delete, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from zoujin_backend.config import DEADLINES
from zoujin_backend.db import store
from zoujin_backend.db.events import recorded_at, to_row
from zoujin_backend.db.store import Run
from zoujin_backend.db.tables import (
    drafts,
    memory_items,
    playthrough_metrics,
    playthroughs,
    turns,
    utterances,
    world_state,
)
from zoujin_backend.db.tables import events as events_t
from zoujin_backend.ids import IdGen
from zoujin_backend.models.armor import Armor
from zoujin_backend.models.text import ReplayMissing, Stop, TextModel
from zoujin_backend.narrator import acts, advance, confirm, ending, memory
from zoujin_backend.narrator.pipeline import Counts, Extracted, Pipeline, Spend, TurnInput, Verified
from zoujin_backend.narrator.rules import Checked
from zoujin_backend.narrator.writer import Writer
from zoujin_backend.projection import is_visible, snapshot
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
    client_msg_id: str | None = None  # B-3：动作、幕末的 clientMsgId
    request: Json | None = None  # B-3：动作和幕末的请求（turns.request）
    window_until: float | None = None  # B-4：提交窗口到什么时候（time.monotonic()）；None = 没有窗口
    flags: frozenset[str] = frozenset()  # B-12：第 0 步安全筛查的标记（turns.flags）
    # 这次处理已经花的钱（B-8 第 7 条）：从检查重来（Stale）的几遍合在一起；提交了就随提交写进 playthrough_metrics，
    # 没提交（作废了、出错了、停下了）由 `Narrator.charge` 补记，每局的花费才和账本对得上
    spend: Spend = field(default_factory=Spend, compare=False)


# 叙事者的事件带 turnId 的任务（契约 Event.turnId：这一轮、这个动作、这次幕末）
TURN_KINDS = ("talk", "action", "choose", "plan")
# 失败时也要给前端一个结果的任务（网关按 turns 补推）
ANSWERED = ("talk", "action", "choose", "plan")


@dataclass
class Planned:
    """一种任务在提交的事务里写了什么之外的结论。"""

    outcome: str | None = None  # talk：turn_settled.outcome
    minutes: int = 0  # 这一轮花了几分钟
    checked: list[Checked] = field(default_factory=list)
    push: list[Json] = field(default_factory=list)  # 提交以后按顺序推的消息（节拍时机的固定演出之后）
    info: dict[str, Any] = field(default_factory=dict)  # 评测入口要的（status、narration、accepted…）
    extra: dict[str, Any] = field(default_factory=dict)  # 记进 turns.result 的（playerSpot、reason）
    snapshot: bool = False  # push 里的 act_transition 要补落地以后的快照
    actions: int = 0
    actions_ended: int = 0
    plans_accepted: int = 0
    plans_refused: int = 0
    # B-4：这一轮要确认的候选（第一个存草稿，其余丢掉）、声音回答了开着的草稿（draftId, yes / no）、
    # 这次关掉的草稿、确认的计数、丢掉的要确认的候选
    proposals: list[confirm.Proposal] = field(default_factory=list)
    answer: tuple[str, str] | None = None
    close_draft: str | None = None
    confirms_asked: int = 0
    confirms_yes: int = 0
    confirms_no: int = 0
    confirms_timeout: int = 0
    confirms_rejected: int = 0
    dropped: int = 0
    world_events: int = 0  # B-16：世界推进写的人物打算的事件、导演事件
    director_events: int = 0


@dataclass
class Result:
    """一次提交写了什么（评测的 StepResult、测试用）。"""

    task: Task
    events: list[Json]
    state: SimState
    outcome: str | None = None
    minutes: int = 0
    checked: list[Checked] = field(default_factory=list)
    push: list[Json] = field(default_factory=list)  # 网关要推的（固定演出、结果、幕末、幕切换）
    info: dict[str, Any] = field(default_factory=dict)
    pieces: list[str] = field(default_factory=list)  # 这次演的固定演出 ID
    memories: list[Json] = field(default_factory=list)  # B-13：这次写的记忆（memory_items 的行）


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
    on_rate_limit: str = "stop"  # 服务玩家的叙事者（narrator/app.py）是 "degrade"，见 Pipeline
    armor: Armor | None = None  # B-13：记忆一句的第二道过滤（None = 不过这一道，只给测试）
    world_advance: bool = True  # B-16：世界推进（幕切换、关键时刻之后、每幕中段）；False = 不调模型、不排任务

    def __post_init__(self) -> None:
        self.pipeline = Pipeline(self.text, self.schemas, self.ids, self.tracer, self.deadlines, self.on_rate_limit)
        self.memorizer = memory.Memorizer(
            self.text,
            self.armor,
            self.ids,
            self.tracer,
            deadline=self.deadlines.get("memory"),
            raise_stops=self.on_rate_limit == "stop",
        )

    # —— 取任务 ——

    async def run(self, pid: str) -> list[Result]:
        """把这一局排着的任务按顺序做完；别的进程正在做这一局时直接返回。"""
        done: list[Result] = []
        while True:
            await self.expire(pid)
            task = await self.claim(pid)
            if task is None:
                return done
            try:
                done.append(await self.process(task))
            except Gone:
                log.info("任务 %s 已经不用做了", task.turn_id)
                await self.charge(task)
            except (Stop, ReplayMissing) as e:  # 不重试：放回队列，整次停下
                log.warning("任务 %s 停下：%s", task.turn_id, type(e).__name__)
                await self.charge(task)
                await self.release(task, failed=False)
                raise
            except Exception:
                log.exception("任务 %s 第 %d 次失败", task.turn_id, task.attempts)
                await self.charge(task)
                await self.release(task, failed=task.attempts >= MAX_ATTEMPTS)

    async def charge(self, task: Task) -> None:
        """这次处理没提交（这一轮被作废、局被删、出错重来、停下），已经花的钱照样记进这一局的 `playthrough_metrics`
        （B-8 第 7 条：作废的一轮在窗口里花的、失败后重来的那几次）。局已经删了就没处记（0 行）。"""
        if not any(task.spend.usd.values()):
            return
        async with self.engine.begin() as c:
            await c.execute(
                update(playthrough_metrics)
                .where(playthrough_metrics.c.playthrough_id == task.pid)
                .values(cost_values(task.spend))
            )
        task.spend.usd.clear()

    async def expire(self, pid: str) -> None:
        """到期的草稿写超时的任务（B-4：网关的 30 秒计时随连接断了也能关掉）。"""
        async with self.engine.begin() as c:
            for draft_id in await store.expire_drafts(c, self.ids, pid):
                log.info("草稿 %s 到期，写超时的任务", draft_id)

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
            window = func.extract("epoch", turns.c.commit_after - func.clock_timestamp()).label("window")
            row = (
                (
                    await c.execute(
                        select(turns, window)
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
            left = float(row["window"]) if row["window"] is not None else 0.0
            return Task(
                turn_id=row["turn_id"],
                pid=pid,
                kind=row["kind"],
                input_mode=row["input_mode"],
                character=row["character"],
                minutes=row["minutes"],
                key=row["idempotency_key"],
                attempts=row["attempts"] + 1,
                client_msg_id=row["client_msg_id"],
                request=row["request"],
                window_until=time.monotonic() + left if left > 0 else None,
                flags=frozenset(row["flags"] or ()),
            )

    async def wait_window(self, task: Task) -> None:
        """提交窗口（B-4）：判完了、还没到 commit_after 就等，不占事务。这期间这一轮可能被作废，提交时会发现。"""
        if task.window_until is not None:
            await asyncio.sleep(max(0.0, task.window_until - time.monotonic()))

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
                .values(
                    status="failed",
                    outcome="no_response",
                    minutes=0,
                    lease_until=None,
                    settled_at=func.now(),
                    flags=None,
                )
                .returning(turns.c.turn_id)
            )
            if res.first() is not None and task.kind in ANSWERED:
                last = await c.scalar(select(playthroughs.c.last_seq).where(playthroughs.c.playthrough_id == task.pid))
                await self._notify(c, task, seq=int(last or 0), outcome="no_response")

    # —— 处理 ——

    async def process(self, task: Task) -> Result:
        if task.kind == ending.KIND:
            return await ending.run_ending(self, task)
        if await self._ended(task.pid):  # 进了结局以后才轮到的：不写事件、不调模型（B-9）
            return await self._commit(task, None, lambda w, book: self._after_end(task))
        if task.kind == "open":
            return await self._commit(task, None, lambda w, book: self._open(w, book))
        if task.kind == "advance":
            minutes = int(task.minutes or 0)
            return await self._commit(task, None, lambda w, book: self._advance(w, minutes))
        if task.kind == "talk":
            return await self._talk(task)
        if task.kind == "action":
            from zoujin_backend.narrator.actions import run_action

            return await run_action(self, task)
        if task.kind == "choose":
            from zoujin_backend.narrator.plans import run_choose

            return await run_choose(self, task)
        if task.kind == "plan":
            from zoujin_backend.narrator.plans import run_plan

            return await run_plan(self, task, (await self._lines(task.turn_id)).get("player"))
        if task.kind == "confirm":
            return await confirm.run_confirm(self, task)
        if task.kind == advance.KIND:
            return await advance.run_world(self, task)
        raise ValueError(f"不认识的任务 {task.kind}")

    async def _ended(self, pid: str) -> bool:
        async with self.engine.connect() as c:
            status = await c.scalar(select(playthroughs.c.status).where(playthroughs.c.playthrough_id == pid))
        if status is None:
            raise Gone(pid)
        return bool(status != "active")

    def _after_end(self, task: Task) -> Planned:
        """结局开始以后才轮到的任务：对话 no_response，动作 refused，幕末 invalid_request，别的什么都不推。"""
        from zoujin_backend.narrator.actions import ended
        from zoujin_backend.narrator.plans import INVALID_REQUEST, invalid

        if task.kind == "talk":
            return self._ended_talk(task)
        if task.kind == "action":
            return ended(dict(task.request or {}))
        if task.kind in ("choose", "plan"):
            return invalid(INVALID_REQUEST, "invalid_request")
        return Planned()

    async def read(self, pid: str) -> tuple[dict[str, Any], SimState]:
        async with self.engine.connect() as c:
            pt = (await c.execute(select(playthroughs).where(playthroughs.c.playthrough_id == pid))).mappings().one()
            st = await c.scalar(select(world_state.c.state).where(world_state.c.playthrough_id == pid))
        if st is None:
            raise Gone(pid)
        return dict(pt), cast(SimState, st)

    async def _talk(self, task: Task) -> Result:
        pt, state = await self.read(task.pid)
        if pt["act_end"] is not None:  # 收幕以后才轮到：no_response、0 分、不调模型
            await self.wait_window(task)
            return await self._commit(task, pt["last_seq"], lambda w, book: self._ended_talk(task))
        book = self.library.version(pt["world_model_version"])
        lines = await self._lines(task.turn_id)
        turn = TurnInput(
            character=task.character,
            player=lines.get("player"),
            reply=lines.get("character"),
            mode=task.input_mode or "voice",
            flags=task.flags,
        )
        spend = task.spend  # 跟着任务走：重来的、没提交的也算（B-8 第 7 条）
        span = {"playthrough_id": task.pid, "turn_id": task.turn_id}
        draft = await self._waiting(task)
        asking = {"prompt": draft["prompt"], "summary": draft["candidate"]["summary"]} if draft else None
        if "ambiguous" in turn.flags and asking is None:  # S-069：似是而非的一句不提取事件，只记时间（B-12）
            extracted = Extracted([], Counts())
        else:
            extracted = await self.pipeline.extract(book, state, turn, spend, span, drafts=True, confirm=asking)
        answer = (draft["draft_id"], extracted.answer) if draft and extracted.answer in confirm.ANSWERS else None
        for _ in range(MAX_STALE):
            if extracted.timed_out:
                verified = Verified([], Counts())
            else:
                minutes = talk_minutes(book, state)
                verified = await self.pipeline.verify(book, state, extracted.candidates, turn, minutes, spend, span)
            await self.wait_window(task)
            if self.before_commit is not None:
                await self.before_commit(task)
            try:
                plan = self._talk_plan(task, verified.checked, extracted.confirm, answer, turn.player)
                counts = extracted.counts + verified.counts
                return await self._commit(task, pt["last_seq"], plan, spend=spend, counts=counts)
            except Stale:
                log.info("lastSeq 变了，%s 从检查重来", task.turn_id)
                pt, state = await self.read(task.pid)
        raise RuntimeError(f"{task.turn_id}：lastSeq 一直在变")

    async def _lines(self, turn_id: str) -> dict[str, str | None]:
        """这一轮玩家和人物的原话。人物的取第一句：意图确认的反问（B-4）也挂在原来那一轮下面，排在回答之后。"""
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
            out.setdefault("player" if speaker == "player" else "character", text)
        return out

    async def _waiting(self, task: Task) -> dict[str, Any] | None:
        """这一轮是对着反问的人物说的、草稿还开着（没到期、还没有回答）：提取要判这句话是不是在回答（B-4）。"""
        async with self.engine.connect() as c:
            draft = await store.open_draft(c, task.pid)
            if draft is None or draft["character"] != task.character:
                return None
            if draft["expires_at"] is not None and draft["expires_at"] <= await c.scalar(select(func.now())):
                return None
            if await store.answered(c, task.pid, draft["draft_id"]):
                return None
        return draft

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
        """结算到 t0 + minutes，再写一个只推进时钟的事件（契约：时钟只由事件推出）。这一幕在这段时间里收了，就停在
        收幕那一刻；收了幕、还没选定时不动。"""
        if w.run.act_end is not None:
            return Planned()
        t0 = w.state["t"]
        t2 = t0 + minutes
        if w.guard:
            t2 = min(t2, int(acts.current_act(w.book, w.state)["end"]["atLatest"]))
        w.settle(t2)
        if not w.closed and w.state["t"] < t2:
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

    def _talk_plan(
        self,
        task: Task,
        checked: list[Checked],
        asks: list[Json | None],
        answer: tuple[str, str] | None,
        said: str | None,
    ) -> Callable[[Writer, Book], Planned]:
        def plan(w: Writer, book: Book) -> Planned:
            p = self._talk_events(w, book, task, checked, asks, said)
            p.answer = answer
            return p

        return plan

    def _talk_events(
        self,
        w: Writer,
        book: Book,
        task: Task,
        checked: list[Checked],
        asks: list[Json | None] | None = None,
        said: str | None = None,
    ) -> Planned:
        w.settle(w.state["t"])
        t0 = w.state["t"]
        place = w.player_place
        proposals: list[confirm.Proposal] = []
        for i, c in enumerate(checked):
            cand = c.candidate
            ask = asks[i] if asks is not None and i < len(asks) else None
            if confirm.proposes(c, ask):  # 要确认：不写进日志，提交时存成草稿（B-4）
                assert ask is not None
                question = confirm.question_of(ask, said)
                proposals.append(confirm.Proposal(c, bool(ask.get("asked")), question, cand.get("place", place)))
                continue
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
        seen = set(w.seen)
        settled = {
            "type": "turn_settled",
            "turnId": task.turn_id,
            "outcome": outcome,
            "eventIds": [e["eventId"] for e in w.events if e.get("turnId") == task.turn_id and e["eventId"] in seen],
            "minutes": minutes,
        }
        return Planned(outcome=outcome, minutes=minutes, checked=checked, push=[settled], proposals=proposals)

    def _ended_talk(self, task: Task) -> Planned:
        settled = {
            "type": "turn_settled",
            "turnId": task.turn_id,
            "outcome": "no_response",
            "eventIds": [],
            "minutes": 0,
        }
        return Planned(outcome="no_response", push=[settled])

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
                turn_id=task.turn_id if task.kind in TURN_KINDS else None,
                ids=self.ids,
                now=recorded_at(),
            )
            w.run = Run.of(dict(pt))
            planned = plan(w, book)
            if planned.close_draft is not None:  # 回答了的草稿关掉就删（B-4）
                await c.execute(delete(drafts).where(drafts.c.draft_id == planned.close_draft))
            trigger = ending.due(book, w.state) if pt["status"] == "active" else None
            if trigger is not None:  # 进结局（B-9）：结算到收幕、分类、站位
                w.ending = ending.enter(w, book, trigger)
            closing, asking = await confirm.in_commit(self, c, task, w, planned)
            push = list(w.pieces) + list(planned.push)
            before: list[Json] = []  # 网关排在这次提交的 commit 前面推的（B-9：ending_started）
            if w.ending is not None:
                push.extend(closing)
                if w.events:
                    before.append(w.ending["message"])
                else:
                    push.insert(0, w.ending["message"])
                await store.enqueue(c, self.ids, task.pid, kind=ending.KIND, request=w.ending["request"])
            if w.closed:  # 这一幕在这次提交里收了：幕末的去处记在局上，推 act_ended（api-contract 3.11）
                start = await c.scalar(
                    select(func.max(events_t.c.seq)).where(
                        events_t.c.playthrough_id == task.pid,
                        events_t.c.type == "act-transition",
                        events_t.c.actor == "system",
                    )
                )
                earlier = await store.event_log(c, task.pid, book.version, after_seq=int(start or 0))
                w.run.act_end = acts.act_end(book, w.state, 0, [*earlier, *w.events])
                w.run.plan_tries = 0
                w.run.plan_alternative = None
                push.extend(closing)  # 开着的草稿按超时关掉，在 act_ended 之前（B-4）
                push.append({"type": "act_ended", **w.run.act_end})
            if planned.snapshot:
                for m in push:
                    if m["type"] == "act_transition":
                        m["snapshot"] = snapshot(
                            book, task.pid, pt["role_id"], pt["status"], w.state, w.state["seq"], w.run
                        )
            pieces = [m["pieceId"] for m in push if m["type"] == "set_piece"]
            todo = memory.seeds(book, state, w.events, task.character)  # B-13：要写的记忆（文字在事务之后由模型写）
            role_id = str(pt["role_id"])
            result = Result(
                task,
                w.events,
                w.state,
                planned.outcome,
                planned.minutes,
                planned.checked,
                [*before, *push],  # 评测和测试看到的顺序就是网关推的顺序（ending_started → commit 之后的）
                planned.info,
                pieces,
            )

            self.fault("validate")
            for ev in w.events:
                self.schemas.event(ev)  # 不合数据契约就抛 SchemaError，整轮回滚

            self.fault("events")
            if w.events:
                await c.execute(insert(events_t), [to_row(e) for e in w.events])
            await self._schedule_world(c, task, dict(pt), w)
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
            ended: dict[str, Any] = {"status": "ended", "ended_at": func.now()} if w.ending is not None else {}
            await c.execute(
                update(playthroughs)
                .where(playthroughs.c.playthrough_id == task.pid)
                .values(last_seq=w.state["seq"], last_active_at=func.now(), **w.run.values(), **ended)
            )
            self.fault("turn")
            stored = {"push": push, "pieces": pieces, "seq": w.state["seq"], **planned.extra}
            if before:
                stored["before"] = before
            if asking is not None:  # 网关推完这一轮的结果以后让人物反问、推 confirm（B-4）
                stored["confirm"] = asking
            await c.execute(
                update(turns)
                .where(turns.c.turn_id == task.turn_id)
                .values(
                    status="done",
                    outcome=result.outcome,
                    minutes=result.minutes,
                    lease_until=None,
                    settled_at=func.now(),
                    result=stored,
                    flags=None,  # B-12：筛查标记只是交给叙事者的，提交的同一个事务里清掉（S-057、S-069 ③）
                )
            )
            self.fault("metrics")
            counts = (counts or Counts()) + Counts(confirm_dropped=planned.dropped)
            values = metrics(task, spend or Spend(), counts, planned)
            if w.ending is not None:
                values["ending_started_at"] = func.now()
            await c.execute(
                update(playthrough_metrics).where(playthrough_metrics.c.playthrough_id == task.pid).values(values)
            )
            self.fault("notify")  # 有记忆要写时 NOTIFY 在写完记忆以后（`_remember`），注入点照旧在提交的事务里
            if not todo:
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
        if todo:
            result.memories = await self._remember(task, book, role_id, todo, result)
        return result

    async def _schedule_world(self, c: AsyncConnection, task: Task, pt: Mapping[str, Any], w: Writer) -> None:
        """B-16：对话、动作、确认提交以后排世界推进（在这次的事件写进库以后、同一个事务里）：有 keyMoment 的事件 →
        `key`；这一幕判完的对话轮次满 8 的倍数 → `mid`。这一幕收了、进了结局、局不在进行中的不排。"""
        if not self.world_advance or task.kind not in ("talk", "action", "confirm"):
            return
        if pt["status"] != "active" or w.ending is not None or w.closed or w.run.act_end is not None:
            return
        reason = None
        if any(e.get("keyMoment") and e["check"]["status"] != "rejected" for e in w.events):
            reason = "key"
        elif task.kind == "talk":
            start = await c.scalar(
                select(func.max(events_t.c.seq)).where(
                    events_t.c.playthrough_id == task.pid,
                    events_t.c.type == "act-transition",
                    events_t.c.actor == "system",
                )
            )
            talks = await c.scalar(
                select(func.count(func.distinct(events_t.c.turn_id)))
                .select_from(events_t.join(turns, turns.c.turn_id == events_t.c.turn_id))
                .where(events_t.c.playthrough_id == task.pid, events_t.c.seq > int(start or 0), turns.c.kind == "talk")
            )
            if talks and int(talks) % advance.MID_EVERY == 0:
                reason = "mid"
        if reason is not None:
            await store.enqueue(c, self.ids, task.pid, kind=advance.KIND, request={"reason": reason})

    async def _remember(
        self, task: Task, book: Book, role_id: str, todo: list[memory.Seed], result: Result
    ) -> list[Json]:
        """B-13：提交以后写记忆，存好再 NOTIFY。出了任何错也 NOTIFY（这一轮的结果照推），`Stop` 推完再往上抛。"""
        rows: list[Json] = []
        stop: Stop | None = None
        try:
            got = await self.memorizer.write(
                book, task.pid, role_id, todo, playthrough_id=task.pid, turn_id=task.turn_id
            )
            async with self.engine.begin() as c:
                rows = await self._store_memories(c, task, book, role_id, got)
                await self._notify(c, task, seq=result.state["seq"], outcome=result.outcome)
            return rows
        except Stop as e:
            stop = e
        except Exception:
            log.exception("写记忆失败（%s），这一轮照常推", task.turn_id)
        async with self.engine.begin() as c:
            await self._notify(c, task, seq=result.state["seq"], outcome=result.outcome)
        if stop is not None:
            raise stop
        return []

    async def _store_memories(
        self, c: AsyncConnection, task: Task, book: Book, role_id: str, got: memory.Written
    ) -> list[Json]:
        """存记忆、记计数和花费；这次的记忆变化（不带文字）记进 turns.result.memories，网关拼 commit 时再取文字。
        局在这期间被删了：一行也不写（外键），只是这一轮的计数没处记。"""
        exists = await c.scalar(
            select(playthroughs.c.playthrough_id).where(playthroughs.c.playthrough_id == task.pid).with_for_update()
        )
        if exists is None:
            return []
        if got.rows:
            await c.execute(insert(memory_items), got.rows)
        changes = []
        for who in dict.fromkeys(r["character"] for r in got.rows):
            label, level = await memory.relation_of(c, book, task.pid, role_id, who)
            changes += [
                {
                    "character": who,
                    "change": "added",
                    "memoryId": r["memory_id"],
                    "kind": r["kind"],
                    "relationLabel": label,
                    "relationLevel": level,
                }
                for r in got.rows
                if r["character"] == who
            ]
        if changes:
            stored = await c.scalar(select(turns.c.result).where(turns.c.turn_id == task.turn_id))
            await c.execute(
                update(turns)
                .where(turns.c.turn_id == task.turn_id)
                .values(result={**(stored or {}), "memories": changes})
            )
        m = playthrough_metrics.c
        values: dict[str, Any] = {
            "cost_memory_usd": m.cost_memory_usd + got.cost_usd,
            "memories_written": m.memories_written + len(got.rows),
            "memories_filtered": m.memories_filtered + got.filtered,
            "memories_failed": m.memories_failed + got.failed,
            "armor_errors": m.armor_errors + got.armor_errors,
            "cost_armor_usd": m.cost_armor_usd + got.armor_usd,
        }
        await c.execute(update(playthrough_metrics).where(m.playthrough_id == task.pid).values(values))
        return got.rows

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
    "narrate": "cost_narrate_usd",
    "plan": "cost_plan_usd",
    "ending": "cost_ending_usd",
    "ending-check": "cost_ending_usd",  # B-17：结局的模型检查算进结局那一列
    "world": "cost_world_usd",  # B-16
}
COUNT_COLUMNS = {
    "triage_skipped": "turns_triage_skipped",
    "timeouts": "turns_timed_out",
    "rewritten": "candidates_rewritten",
    "downgraded": "candidates_downgraded",
    "rejected": "candidates_rejected",
    "confirm_dropped": "candidates_confirm_dropped",
}


PLANNED_COLUMNS = {  # B-3：动作的次数（收幕时队列里回 refused 的另数），打算成行、不成行的次数；B-4：意图确认
    "actions": "actions",
    "actions_ended": "actions_act_ended",
    "plans_accepted": "plans_accepted",
    "plans_refused": "plans_refused",
    "confirms_asked": "confirms_asked",
    "confirms_yes": "confirms_yes",
    "confirms_no": "confirms_no",
    "confirms_timeout": "confirms_timeout",
    "confirms_rejected": "confirms_rejected",
    "world_events": "world_events",  # B-16
    "director_events": "director_events",
}


def cost_values(spend: Spend) -> dict[str, Any]:
    """各类提示的花费加到这一局已有的数上（data-design 第 3 节：每局费用 = 所有 cost_*_usd 之和）。"""
    m = playthrough_metrics.c
    by_col: dict[str, float] = {}
    for kind, usd in spend.usd.items():
        by_col[COST_COLUMNS[kind]] = by_col.get(COST_COLUMNS[kind], 0.0) + usd
    return {col: m[col] + usd for col, usd in by_col.items()}


def metrics(task: Task, spend: Spend, counts: Counts, planned: Planned | None = None) -> dict[str, Any]:
    m = playthrough_metrics.c
    out: dict[str, Any] = {"turns": m.turns + (1 if task.kind == "talk" else 0)}
    for k, col in PLANNED_COLUMNS.items():
        n = getattr(planned, k) if planned is not None else 0
        if n:
            out[col] = m[col] + n
    out |= cost_values(spend)
    for k, col in COUNT_COLUMNS.items():
        n = getattr(counts, k)
        if n:
            out[col] = m[col] + n
    return out
