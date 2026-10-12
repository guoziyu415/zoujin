"""评测入口（api-contract 第 7 节、B-0 第 9 条的最小版）：给数据工程的运行器在 Python 包内调，不开 HTTP，生产环境没有。

    from zoujin_backend import eval_api
    s = eval_api.setup({"role": "role.traveler", "checkpoint": "sc.canon@beat.03"}, mode="text")
    s.say("char.old-man", "…")
    s.state()

- `setup` 每次读 `DATABASE_URL` 和 `ZJ_MODEL`（fake / replay / real；real 只在 Mac 上，账本和上限见
  `models/vertex.py`）。一局是测试库里真的一局：一个新账号、一局、
  起点的事件和 world_state，之后的步骤走和网关同一个叙事者（`Narrator.run`）。
- 做了的：setup 的 `role`、`place`、`budgetTier`（只记下）、`scenario`、`checkpoint`、`events`；步骤 `say`（人物用文字
  回答，再走叙事者整条流水线，B-2）、`advance`；`act`、`propose`、`choose`（B-3：和 WebSocket 同一条路，写任务、
  叫叙事者）；`check`（第 3 步 + 按 `model_checks` 跑第 4 步，不改写、不提交）；查询 `state()`、`events()`；
  B-9：`ending()`（还没进结局返回 None）；情景推到收幕的 setup 起点就进结局，结局任务在 setup 里同步跑完。
  检查点停在这一幕的收幕节拍上（例 `sc.canon@beat.07`）时，setup 之后就是幕末待选。
- B-4：`say(hold=True)` 只写这一轮、拿人物的回答，返回 `held: true`、没有事件（作废的窗口还开着）；下一次调用（任何
  步骤或查询）开始时先让叙事者提交它，事件算在那一次里。`retract(n)` 作废还 hold 着的第 n 步（`retracted`），
  已经提交的 `too_late`；`utterance_cleared(n)`。这一步留下了意图确认的草稿时 `StepResult.confirm` 有值，草稿最多等
  一步：下一步 `confirm(answer)` 按它答，`say` 由叙事者判是不是在回答，别的步骤（或那句 `say` 不是在回答）按超时关掉。
  评测的提交窗口是 0。
- B-5 模拟局：`setup({"role": …, "persona": …, "seed": …})` 照正式开局起一局（和网关 `POST /v1/playthroughs` 同一条
  路：写局和 `open` 任务、叫叙事者做），不用 `opening()` 推演；`persona`、`seed` 只记在 Trace（`eval.setup`）上，
  `seed` 给假模型。AI 玩家只看 `view()`（2.3 的快照和 2.4 的玩家可见事件，和网关同一个投影）、`manifest()`（B-7 的
  生成器）和每一步结果里玩家听得到、看得到的字段。每一步的结果带 `elapsedMs`（进来到返回）。这一局里记的账带
  `playthroughId`（`zoujin_llm.playthrough`）。
- 没做的步骤和查询、带 `memory` 的布置事件、没有布局的场景里的 `move` 抛
  `EvalNotImplemented("<名字>")`；
  回放里查不到抛 `ReplayMissing`。账本到上限抛 `BudgetStop`，模型回 429 抛 `RateLimited`：这两个要整次停下，不是跳过
  这一例。运行器按类名认。
- 一局共用一个事件循环，数据库用不进连接池的连接；运行器的超时（SIGALRM）中途打断时，
  丢下的那一局只是留在测试库里。
"""

from __future__ import annotations

import asyncio
import contextvars
import copy
import json
import time
from collections.abc import Callable, Coroutine, Iterable, Mapping, Sequence
from dataclasses import replace
from functools import cache, wraps
from pathlib import Path
from typing import Any, NoReturn

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from zoujin_llm import mark_playthrough, playthrough
from zoujin_worldsim import Opened, SimState, initial_state, opening, parse_checkpoint, world_state

from zoujin_backend import budget, memory_delete
from zoujin_backend.config import Settings
from zoujin_backend.db import store
from zoujin_backend.db.events import recorded_at, to_row
from zoujin_backend.db.store import Run
from zoujin_backend.db.tables import (
    NOT_BUILT,
    PER_PLAYTHROUGH,
    endings,
    memory_items,
    metadata,
    playthrough_metrics,
    playthroughs,
    users,
    utterances,
)
from zoujin_backend.db.tables import events as events_t
from zoujin_backend.db.tables import turns as turns_t
from zoujin_backend.db.tables import world_state as world_state_t
from zoujin_backend.gateway.monitor import Monitor
from zoujin_backend.gateway.safety import context_of
from zoujin_backend.ids import IdGen
from zoujin_backend.manifest import Manifest, generate
from zoujin_backend.models.armor import Armor, armor
from zoujin_backend.models.text import BudgetStop, RateLimited, ReplayMissing, TextModel, text_model
from zoujin_backend.narrator import acts, ending, memory
from zoujin_backend.narrator.core import Narrator, Result
from zoujin_backend.narrator.pipeline import CallFailed, Pipeline, Spend, TurnInput
from zoujin_backend.narrator.writer import Writer, act_closed
from zoujin_backend.projection import snapshot, visible_events
from zoujin_backend.safety import SafetyState, Screen, Screener, counts_of, decide
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.trace import Tracer
from zoujin_backend.world import Book, Library

__all__ = ["BudgetStop", "CallFailed", "EvalNotImplemented", "RateLimited", "ReplayMissing", "Session", "setup"]

Json = Any

BOOK = "hashire-merosu"
CHECKER = "eval-setup"
SETUP_PASSED: Json = {"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER}


class EvalNotImplemented(Exception):
    """B-0 没做的步骤或查询（运行器按类名认，记「跳过：后端未实现」）。"""


@cache
def _library(worlds: Path, scenes: Path, current: Path) -> Library:
    return Library(worlds, scenes, current)


@cache
def _schemas(root: Path) -> SchemaBook:
    return SchemaBook(root)


@cache
def _scenarios(world_dir: Path) -> dict[str, Json]:
    """`sc.canon` = 原著路径（不在 scenarios.json 里）。"""
    path = world_dir / "scenarios.json"
    listed = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    return {"sc.canon": {"id": "sc.canon"}, **{s["id"]: s for s in listed}}


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    """兼容测试的独立数据库操作；Session 的模型调用使用实例持久循环。"""
    return asyncio.run(coro)


def _timed(step: Callable[..., Json]) -> Callable[..., Json]:
    """每一步的结果加 `elapsedMs`：从调用进来到返回，含叙事者各次模型调用和提交（B-5）。"""

    @wraps(step)
    def timed(*args: Any, **kwargs: Any) -> Json:
        start = time.perf_counter()
        out = step(*args, **kwargs)
        out["elapsedMs"] = round((time.perf_counter() - start) * 1000)
        return out

    return timed


# 带 persona 的模拟局从正式开局玩起，不和这几样一起给
NOT_WITH_PERSONA = ("checkpoint", "scenario", "events")


def setup(setup: Mapping[str, Json], *, mode: str = "text") -> Session:
    """开一局。setup 是用例的 setup 原样，mode 是 text / voice（B-0 两种都走文字的叙事者流程）。"""
    if "persona" in setup:
        mixed = [k for k in NOT_WITH_PERSONA if k in setup]
        if mixed:
            raise ValueError(f"persona 不和 {'、'.join(mixed)} 一起给：模拟局从正式开局玩起")
    settings = Settings.from_env()
    library = _library(settings.worlds, settings.scenes, settings.world)  # ZJ_WORLD 每次 setup() 都读
    book = library.book(setup.get("book", BOOK))
    if book is None:
        raise ValueError(f"没有这本书：{setup.get('book', BOOK)}")
    if setup["role"] not in book.roles:
        raise ValueError(f"没有这个身份：{setup['role']}")
    s = Session(settings, library, book, setup, mode)
    try:
        s._run(s._open() if s.persona is not None else s._setup())
    except BaseException:
        s.close()
        raise
    return s


class Session:
    def __init__(self, settings: Settings, library: Library, book: Book, setup: Mapping[str, Json], mode: str) -> None:
        self.settings = settings
        self.library = library
        self.book = book
        self.setup_doc = copy.deepcopy(dict(setup))
        self.mode = mode
        self.role: str = setup["role"]
        self.budget_tier: str = setup.get("budgetTier", "normal")  # B-14：开局就设成这一档（E6）
        self.persona: str | None = setup.get("persona")  # 模拟局的画像 ID，只进 Trace（B-5）
        self.seed: int | None = setup.get("seed")
        self.ids = IdGen()
        self.text: TextModel = text_model(
            settings.model, fake_rules=settings.fake_text, replays=settings.replays, settings=settings, seed=self.seed
        )
        self.schemas = _schemas(settings.schemas)
        self.tracer = Tracer()
        self.span: dict[str, Any] = {}  # 运行器给这一步的 Span 加的属性（例：S-2 的 trace_id）
        self.pid = ""
        self.user_id = ""
        self.deleted: str | None = None  # B-13：delete_playthrough 删掉的那一局（db_absent 查它）
        self.steps = 0
        self.turns: dict[int, str] = {}  # 第几步 → 那一轮的 turnId（say；retract、utterance_cleared 用）
        self.held: tuple[int, str] | None = None  # say(hold=True) 还没提交的那一步
        self.draft: tuple[int, str] | None = None  # 第几步留下的、还开着的草稿
        # B-12：玩家每一句的安全筛查和人物输出的监控，和网关同一套（Model Armor 按 ZJ_MODEL；回放查不到照样抛）
        self.armor: Armor = armor(settings.model, replays=settings.replays)
        self.safety = SafetyState()
        self.last_reply: dict[str, str] = {}  # B-15：每个人物上一句（安全筛查的上下文）
        self.monitor = Monitor(library)
        self.monitor.attach(book)
        self._manifest: Manifest | None = None
        # 真客户端的连接池跨步骤复用；整局必须共用一个事件循环。
        self._runner = asyncio.Runner()

    def _run[T](self, coro: Coroutine[Any, Any, T]) -> T:
        """一局共用一个事件循环；这期间记的账带这一局的 playthroughId。"""
        with playthrough(self.pid or None):
            return self._runner.run(coro, context=contextvars.copy_context())

    def close(self) -> None:
        """评测运行器在成功、失败、预算停止后都关闭本局的事件循环。"""
        self._runner.close()

    # —— 连接和叙事者：每次调用新建（各自的事件循环） ——

    def _engine(self) -> AsyncEngine:
        return create_async_engine(self.settings.database_url, poolclass=NullPool)

    def _narrator(self, engine: AsyncEngine) -> Narrator:
        return Narrator(
            engine=engine,
            library=self.library,
            text=self.text,
            schemas=self.schemas,
            ids=self.ids,
            tracer=self.tracer,
            deadlines=self.settings.deadlines,
            armor=self.armor,
        )

    @property
    def screener(self) -> Screener:
        """`text` 可能被测试换掉，每次按当前的建。评测里账本到上限、429 照样整次停下。"""
        return Screener(self.text, self.armor, self.tracer, raise_stops=True)

    @property
    def pipeline(self) -> Pipeline:
        """`text` 可能被测试换掉，每次按当前的建。"""
        return Pipeline(self.text, self.schemas, self.ids, self.tracer, self.settings.deadlines)

    # —— 起点 ——

    async def _setup(self) -> None:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                user_id = await self._user(c)
                self.pid = self.ids.new("pt")
                await c.execute(
                    insert(playthroughs).values(
                        playthrough_id=self.pid,
                        user_ref=user_id,
                        book_id=self.book.book_id,
                        world_model_version=self.book.version,
                        role_id=self.role,
                        status="active",
                    )
                )
                await c.execute(insert(playthrough_metrics).values(playthrough_id=self.pid))
                if self.budget_tier != "normal":
                    await budget.set_tier(c, self.pid, self.budget_tier)
                w = Writer(
                    self.book,
                    self.pid,
                    initial_state(self.book.world, self.role),
                    key_base=f"{self.pid}/setup",
                    turn_id=None,
                    ids=self.ids,
                    now=recorded_at(),
                )
                play_setup(w, _scenarios(self._world_dir()), self.setup_doc)
                laid = w.events[len(w.events) - len(self.setup_doc.get("events", [])) :]  # 评测布置的事件在最后
                # 情景模式一口气推到了收幕（B-9 第 11 条）：起点就进结局，和叙事者提交时一样。只看最后一幕收没收，
                # 检查点停在 beat.24 以后、还在前面几幕的不进（数据评审 #124）
                trigger = ending.closed(self.book, w.state) if ending.curtain_fell(self.book, w.state) else None
                if trigger is not None:
                    w.ending = ending.enter(w, self.book, trigger)
                for ev in w.events:
                    self.schemas.event(ev)
                if w.events:
                    await c.execute(insert(events_t), [to_row(e) for e in w.events])
                await self._seed_memories(c, laid)
                await c.execute(
                    insert(world_state_t).values(playthrough_id=self.pid, as_of_seq=w.state["seq"], state=w.state)
                )
                await c.execute(
                    update(playthroughs)
                    .where(playthroughs.c.playthrough_id == self.pid)
                    .values(last_seq=w.state["seq"], act_end=setup_act_end(self.book, w, self.setup_doc))
                )
                if w.ending is not None:
                    await c.execute(
                        update(playthroughs)
                        .where(playthroughs.c.playthrough_id == self.pid)
                        .values(status="ended", ended_at=func.now())
                    )
                    await c.execute(
                        update(playthrough_metrics)
                        .where(playthrough_metrics.c.playthrough_id == self.pid)
                        .values(ending_started_at=func.now())
                    )
                    await store.enqueue(c, self.ids, self.pid, kind=ending.KIND, request=w.ending["request"])
            if w.ending is not None:  # 结局任务在 setup 里同步跑完
                await self._narrator(engine).run(self.pid)
        finally:
            await engine.dispose()

    async def _open(self) -> None:
        """模拟局（B-5）：照正式开局，和网关 `POST /v1/playthroughs` 同一条路（`store.create_playthrough` 写局、指标行
        和 `open` 任务，叙事者做：startT、startAct、到点的节拍）。"""
        engine = self._engine()
        try:
            async with engine.begin() as c:
                user_id = await self._user(c)
                self.pid = await store.create_playthrough(
                    c, self.ids, user_id=user_id, book=self.book, role_id=self.role
                )
                if self.budget_tier != "normal":
                    await budget.set_tier(c, self.pid, self.budget_tier)
            mark_playthrough(self.pid)
            attrs = {"eval.persona": self.persona, "eval.seed": self.seed}
            with self.tracer.span("eval.setup", playthrough_id=self.pid, mode=self.mode, **attrs):
                await self._narrator(engine).run(self.pid)
        finally:
            await engine.dispose()

    async def _user(self, c: Any) -> str:
        """这一局的账号：第一次建，`new_playthrough` 用同一个（E6-008：同一个账号换一局）。"""
        if not self.user_id:
            self.user_id = self.ids.new("usr")
            await c.execute(insert(users).values(user_id=self.user_id))
        return self.user_id

    async def _seed_memories(self, c: Any, laid: Sequence[Json]) -> None:
        """setup 的事件带 `memory: {character, kind, text}`：直接种一条记忆（不调模型，过同样的三道过滤）。"""
        todo = [
            (ev, d["memory"]) for ev, d in zip(laid, self.setup_doc.get("events", []), strict=True) if "memory" in d
        ]
        if not todo:
            return
        m = memory.Memorizer(self.text, self.armor, self.ids, self.tracer)
        rows = []
        for ev, spec in todo:
            text = str(spec["text"]).strip()
            if not (memory.rule_ok(text) and await m._armor_ok(text, memory.Written())):
                raise ValueError(f"setup 种的记忆过不了过滤：{spec['character']}")
            rows.append(memory.seeded(self.ids, self.pid, ev, spec["character"], spec["kind"], text))
        await c.execute(insert(memory_items), rows)

    def _world_dir(self) -> Path:
        """情景 `scenarios.json` 和开局用的 world.json 在同一个目录（setup 只用 `Library.current`）。"""
        return self.settings.world.parent

    # —— 步骤 ——

    @_timed
    def say(self, to: str, text: str, hold: bool = False) -> Json:
        """文字代替语音：人物用文字回答（`reply`），原话和这一轮写进去，走叙事者整条流水线。hold：先不提交（B-4）。"""
        self.steps += 1
        return self._run(self._say(to, text, hold))

    # —— B-4：hold 着的一轮、等回答的草稿 ——

    async def _prelude(self, engine: AsyncEngine, kind: str, retract: int | None = None) -> list[Result]:
        """每次调用开始时：hold 着的那一轮先提交（retract 的正是它就不提交）；草稿等过了一步、这一步又不是
        confirm、say 的，按超时关掉。返回这期间叙事者提交的。"""
        done: list[Result] = []
        if self.held is not None and self.held[0] != retract:
            self.held = None
            done += await self._narrator(engine).run(self.pid)
        if self.draft is not None and (self.steps > self.draft[0] + 1 or kind not in ("say", "confirm")):
            done += await self._close_draft(engine, None, "timeout")
        return done

    async def _close_draft(self, engine: AsyncEngine, option: str | None, by: str) -> list[Result]:
        assert self.draft is not None
        _, draft_id = self.draft
        self.draft = None
        async with engine.begin() as c:
            written = await store.answer_draft(c, self.ids, self.pid, draft_id, option, by)
        return await self._narrator(engine).run(self.pid) if written is not None else []

    async def _flush(self) -> None:
        """查询之前：hold 着的那一轮先提交（草稿不动，查询不算一步）。"""
        if self.held is None:
            return
        engine = self._engine()
        try:
            self.held = None
            await self._narrator(engine).run(self.pid)
        finally:
            await engine.dispose()

    def _events_of(self, done: Sequence[Result]) -> list[Json]:
        return [e for r in done for e in self._step_events(r)]

    @staticmethod
    def _set_pieces(done: Sequence[Result]) -> list[Json]:
        """只给玩家实际收到的固定演出；不从 manifest 或世界模型读未来台词。"""
        return [copy.deepcopy(m) for r in done for m in r.push if m.get("type") == "set_piece"]

    async def _say(self, to: str, text: str, hold: bool = False) -> Json:
        engine = self._engine()
        try:
            pre = await self._prelude(engine, "say")
            async with engine.connect() as c:
                st = await store.sim_state(c, self.pid)
            assert st is not None
            spend = Spend()
            ctx = context_of(self.book, st["vars"]["var.player.location"], to, self.last_reply.get(to))
            screen = await self.screener.screen(text, ctx, **self.span)
            if self.safety.ambiguous >= 1:  # B-15：第二次 ambiguous 先复核
                screen = await self.screener.second_look(screen, text, ctx, **self.span)
            decision = decide(screen, self.safety)
            if decision == "pause":  # 出戏卡（3.12）：人物的回答不出、这一轮不进叙事者、不花时间、原话不存
                return await self._paused(engine, to, pre, screen)
            if decision == "hint":
                self.monitor.calm()
            notes = self.monitor.notes(to)
            turn_in = TurnInput(character=to, player=text)
            reply = await self.pipeline.reply(self.book, st, turn_in, spend, notes=notes)
            watched = self.monitor.observe(to, reply, st, said=text)
            if reply:
                self.last_reply[to] = reply
            async with engine.begin() as c:
                await c.execute(
                    update(playthrough_metrics)
                    .where(playthrough_metrics.c.playthrough_id == self.pid)
                    .values(cost_reply_usd=playthrough_metrics.c.cost_reply_usd + spend.usd.get("reply", 0.0))
                )
                await store.count(c, self.pid, **counts_of(screen, decision), **(watched.counts() if reply else {}))
                turn_id = await store.enqueue(
                    c, self.ids, self.pid, kind="talk", input_mode="text", character=to, flags=screen.flags
                )
                await store.add_utterance(
                    c, self.ids, self.pid, turn_id, speaker="player", text=screen.masked, t=st["t"]
                )
                await store.add_utterance(
                    c, self.ids, self.pid, turn_id, speaker=to, text=reply, t=st["t"], source="live"
                )
            self.turns[self.steps] = turn_id
            card = {"shown": False, "paused": False, "canReturn": True}
            monitor = {"spoilers": [h.fact for h in watched.spoilers], "notes": notes}
            if hold:
                self.held = (self.steps, turn_id)
                return {
                    "safetyCard": card,
                    "safety": screen.self_harm,
                    "safetyHint": decision == "hint",
                    "monitor": monitor,
                    "reply": reply,
                    "characterTextMissing": reply is None,
                    "events": self._events_of(pre),
                    "setPieces": self._set_pieces(pre),
                    "clockMinutes": sum(r.minutes for r in pre),
                    "traceId": turn_id,
                    "held": True,
                }
            done = await self._narrator(engine).run(self.pid)
            self._only(done, turn_id)
            if self.draft is not None:  # 等回答的草稿：这句话不是在回答，按超时关掉
                done += await self._close_draft(engine, None, "timeout")
            asking = await self._draft_of(engine, turn_id)
        finally:
            await engine.dispose()
        out: Json = {
            "safetyCard": card,
            "safety": screen.self_harm,
            "safetyHint": decision == "hint",
            "monitor": monitor,
            "reply": reply,
            "characterTextMissing": reply is None,
            "events": self._events_of([*pre, *done]),
            "setPieces": self._set_pieces([*pre, *done]),
            "clockMinutes": sum(r.minutes for r in [*pre, *done]),
            "traceId": turn_id,
        }
        if asking is not None:
            self.draft = (self.steps, asking["draftId"])
            out["confirm"] = asking
        return out

    async def _paused(self, engine: AsyncEngine, to: str, pre: Sequence[Result], screen: Screen) -> Json:
        """出戏卡停下的一轮（B-12，3.12）：写一行 outcome = paused、0 分，没有原话，不叫叙事者。评测里玩家下一步
        就算选了「物語に戻る」（canReturn），暂停随即解除。"""
        async with engine.begin() as c:
            turn_id = await store.enqueue(
                c, self.ids, self.pid, kind="talk", input_mode="text", character=to, status="done"
            )
            await c.execute(
                update(turns_t)
                .where(turns_t.c.turn_id == turn_id)
                .values(outcome="paused", minutes=0, settled_at=func.now())
            )
            await store.count(c, self.pid, **counts_of(screen, "pause"))
        self.turns[self.steps] = turn_id
        self.safety.paused = False  # 评测的下一步 = 玩家回到了故事
        return {
            "safetyCard": {"shown": True, "paused": True, "canReturn": True},
            "safety": screen.self_harm,
            "outcome": "paused",
            "reply": None,
            "characterTextMissing": False,
            "events": self._events_of(pre),
            "clockMinutes": sum(r.minutes for r in pre),
            "traceId": turn_id,
        }

    async def _count(self, **by: float) -> None:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                await store.count(c, self.pid, **by)
        finally:
            await engine.dispose()

    async def _draft_of(self, engine: AsyncEngine, turn_id: str) -> Json | None:
        """这一轮留下的草稿（StepResult.confirm）。"""
        async with engine.connect() as c:
            draft = await store.open_draft(c, self.pid)
        if draft is None or draft["turn_id"] != turn_id:
            return None
        return {"draftId": draft["draft_id"], "character": draft["character"], "prompt": draft["prompt"]}

    @_timed
    def confirm(self, answer: str | None) -> Json:
        """回答上一步留下的意图确认：yes / no / None（没答、超时）。没有草稿在等时 `error: "no_draft"`。"""
        if answer not in ("yes", "no", None):
            raise ValueError(f"answer 只能是 yes / no / None，得到 {answer!r}")
        self.steps += 1
        return self._run(self._confirm(answer))

    async def _confirm(self, answer: str | None) -> Json:
        engine = self._engine()
        try:
            pre = await self._prelude(engine, "confirm")
            if self.draft is None:
                return {"events": self._events_of(pre), "clockMinutes": 0, "error": "no_draft"}
            done = await self._close_draft(engine, answer, "button" if answer is not None else "timeout")
        finally:
            await engine.dispose()
        out: Json = {
            "events": self._events_of([*pre, *done]),
            "setPieces": self._set_pieces([*pre, *done]),
            "clockMinutes": sum(r.minutes for r in [*pre, *done]),
        }
        mine = [r for r in done if r.task.kind == "confirm"]
        if mine:
            out["traceId"] = mine[-1].task.turn_id
            out["result"] = mine[-1].info.get("result")
            if mine[-1].info.get("narration"):
                out["narration"] = mine[-1].info["narration"]
        return out

    @_timed
    def act(self, kind: str, target: str | None, params: Mapping[str, Json], *, action_id: str | None = None) -> Json:
        """动作（api-contract 3.8）：和 `action` 消息一样写一行任务，叙事者判定。还没有 3D 布局的场景里的 `move`
        （归途、村子：路程和过河跟 S-081 的停靠点一起做，M3）抛 `EvalNotImplemented`，用例记成跳过。`move` 的
        `params.crossing`（过河的走法，E5-008）是评测专用参数：契约 3.8 的 `move` 没有 params，正式客户端不发；走不通时
        记一条被否决的 move（R2-precondition）。"""
        if kind == "move":
            here = self._run(self._state())["vars"]["var.player.location"]
            if self.book.places.get(here, {}).get("sceneRef") not in self.book.scenes:
                raise EvalNotImplemented("move（没有布局的场景）")
        self.steps += 1
        request: Json = {"clientMsgId": f"eval-{self.steps}", "kind": kind, "params": dict(params or {})}
        if action_id is not None:
            request["actionId"] = action_id
        if target is not None:
            request["target"] = target
        r, t0 = self._run(self._task("action", request))
        self.turns[self.steps] = r.task.turn_id  # B-13：delete_memory 按这一步的事件找记忆
        info = r.info
        out: Json = {
            "events": self._step_events(r),
            "clockMinutes": r.minutes,
            "traceId": r.task.turn_id,
            "status": info.get("status"),
            "pieces": list(r.pieces),
            "setPieces": self._set_pieces([r]),
            "aid": info.get("aid"),
        }
        for k in ("narration", "setPiece"):
            if k in info:
                out[k] = info[k]
        return out

    async def _screen_plan(self, text: str) -> Screen:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                st = await store.sim_state(c, self.pid)
        finally:
            await engine.dispose()
        ctx = context_of(self.book, st["vars"]["var.player.location"] if st else None, None, None)
        screen = await self.screener.screen(text, ctx, **self.span)
        if self.safety.ambiguous >= 1:
            screen = await self.screener.second_look(screen, text, ctx, **self.span)
        return screen

    @_timed
    def propose(self, text: str) -> Json:
        """幕末用文字说出打算（3.11）：原话存进 utterances，叙事者的 plan 判能不能成行。收幕以前、试过 2 次以后
        返回 `error: "invalid_request"`、没有事件（网关这时回 invalid_request，不写任务）。"""
        self.steps += 1
        screen = self._run(self._screen_plan(text))  # 幕末的打算也筛（UX 在 #112 的评审）
        decision = decide(screen, self.safety)
        if decision == "pause":  # 不交给叙事者、不算试次；回到故事以后幕末页照原样
            self.safety.paused = False
            self._run(self._count(**counts_of(screen, decision)))
            return {
                "safetyCard": {"shown": True, "paused": True, "canReturn": True},
                "safety": screen.self_harm,
                "outcome": "paused",
                "events": [],
                "clockMinutes": 0,
                "accepted": False,
            }
        if decision == "hint":
            self.monitor.calm()
        self._run(self._count(**counts_of(screen, decision)))
        request = {"clientMsgId": f"eval-{self.steps}", "mode": "text"}
        r, t0 = self._run(self._task("plan", request, said=screen.masked, flags=screen.flags))
        info = r.info
        moved = [e for e in r.events if e["type"] == "act-transition" and e["actor"] == "player"]
        alt = info.get("alternative")
        out: Json = {
            "events": self._step_events(r),
            "clockMinutes": r.state["t"] - t0,
            "traceId": r.task.turn_id,
            "accepted": bool(info.get("accepted")),
            "plan": moved[-1].get("plan") if moved else None,
            "alternative": alt,
            "alternatives": [alt] if alt else [],
            "triesLeft": info.get("triesLeft"),
            "narration": info.get("narration", []),
            "pieces": list(r.pieces),
            "setPieces": self._set_pieces([r]),
        }
        if "error" in info:
            out["error"] = info["error"]
        return out

    @_timed
    def choose(self, exit: str, en_route: int | None = None) -> Json:
        """幕末选去处（3.11）：给定去处，或打算不成行时的替代去处（`plan_…`）。不在选项里返回
        `error: "invalid_choice"`、没有事件（E4-103）。"""
        self.steps += 1
        request: Json = {"clientMsgId": f"eval-{self.steps}", "optionId": exit}
        if en_route is not None:
            request["enRouteChoice"] = en_route
        r, t0 = self._run(self._task("choose", request))
        out: Json = {
            "events": self._step_events(r),
            "clockMinutes": r.state["t"] - t0,
            "traceId": r.task.turn_id,
            "pieces": list(r.pieces),
            "setPieces": self._set_pieces([r]),
        }
        if "error" in r.info:
            out["error"] = r.info["error"]
        else:
            out["toAct"] = r.info.get("toAct")
            self.monitor.act_ended()  # 似是而非之后的提示带到这一幕结束
        return out

    async def _task(
        self, kind: str, request: Json, said: str | None = None, flags: Iterable[str] | None = None
    ) -> tuple[Result, int]:
        """写一行任务（打算还存原话），叫叙事者做完。返回这一步的结果和之前的故事时刻。hold 着的那一轮先提交、
        等回答的草稿按超时关掉，它们的事件放在这一步的前面（B-4）。"""
        engine = self._engine()
        try:
            async with engine.connect() as c:
                before = await store.sim_state(c, self.pid)
            assert before is not None
            pre = await self._prelude(engine, kind)
            async with engine.begin() as c:
                st = await store.sim_state(c, self.pid)
                assert st is not None
                turn_id = await store.enqueue(
                    c,
                    self.ids,
                    self.pid,
                    kind=kind,
                    input_mode="text" if kind == "plan" else None,
                    client_msg_id=request.get("clientMsgId"),
                    request=request,
                    flags=flags,
                )
                if said is not None:
                    await store.add_utterance(c, self.ids, self.pid, turn_id, speaker="player", text=said, t=st["t"])
            done = await self._narrator(engine).run(self.pid)
        finally:
            await engine.dispose()
        return self._merged(pre, self._only(done, turn_id)), int(before["t"])

    @staticmethod
    def _merged(pre: Sequence[Result], r: Result) -> Result:
        """这一步之前提交的（hold 着的那一轮、超时关掉的草稿）的事件并进这一步的结果。"""
        if not pre:
            return r
        return replace(
            r,
            events=[e for p in pre for e in p.events] + r.events,
            push=[m for p in pre for m in p.push] + r.push,
            checked=[c for p in pre for c in p.checked] + r.checked,
            minutes=sum(p.minutes for p in pre) + r.minutes,
        )

    @_timed
    def advance(self, minutes: int) -> Json:
        self.steps += 1
        return self._run(self._advance(minutes))

    async def _advance(self, minutes: int) -> Json:
        engine = self._engine()
        try:
            pre = await self._prelude(engine, "advance")
            async with engine.begin() as c:
                turn_id = await store.enqueue(c, self.ids, self.pid, kind="advance", minutes=minutes)
            done = await self._narrator(engine).run(self.pid)
        finally:
            await engine.dispose()
        result = self._merged(pre, self._only(done, turn_id))
        return {"events": self._step_events(result), "clockMinutes": result.minutes, "traceId": turn_id}

    @staticmethod
    def _only(done: Sequence[Result], turn_id: str) -> Result:
        for r in done:
            if r.task.turn_id == turn_id:
                return r
        raise RuntimeError(f"叙事者没有提交这一步（{turn_id}）")

    @staticmethod
    def _step_events(result: Result) -> list[Json]:
        """这一步写的全部事件；被否决的给候选原本的 effects（日志里那条 effects 是空的，契约第 3 节）。"""
        original = {c.candidate.get("eventId"): c.effects for c in result.checked if not c.passed}
        out = []
        for ev in result.events:
            ev = copy.deepcopy(ev)
            if ev["eventId"] in original:
                ev["effects"] = copy.deepcopy(original[ev["eventId"]])
            out.append(ev)
        return out

    def check(self, candidate: Mapping[str, Json], turn: Mapping[str, Json], model_checks: str = "scoped") -> Json:
        """S-2：候选事件交给第 3 步，再按 `model_checks` 跑第 4 步（`scoped` = 正式范围：过了第 3 步、`effects`
        不为空的；`all` = 都跑），不改写、不提交。没跑第 4 步的 R5 和 R6 其余部分记 skipped。"""
        if model_checks not in ("scoped", "all"):
            raise ValueError(f"model_checks 只能是 scoped / all，得到 {model_checks!r}")
        st = self._run(self._state())
        t = TurnInput(
            character=turn.get("to"),
            player=turn.get("player"),
            reply=turn.get("reply"),
            act=turn.get("act"),
        )
        checked = self._run(
            self.pipeline.check_only(self.book, st, dict(candidate), t, model_checks, Spend(), self.span)
        )
        return {"check": checked.check, "rules": checked.rules}

    # —— 查询 ——

    async def _state(self) -> SimState:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                st = await store.sim_state(c, self.pid)
        finally:
            await engine.dispose()
        assert st is not None
        return st

    def state(self) -> Json:
        """契约 3.1 的 WorldState（W-1 的 world_state()）。"""
        self._run(self._flush())
        return world_state(self.book.world, self._run(self._state()), self.pid)

    def events(self) -> list[Json]:
        """这一局的全部事件（含评测布置的、被否决的），按 seq。"""
        self._run(self._flush())
        return self._run(self._events())

    def view(self, after_seq: int = 0) -> Json:
        """AI 玩家看的（B-5）：2.3 的快照和 2.4 的玩家可见事件（seq 大于 after_seq 的），和网关 `GET …/snapshot`、
        `GET …/events` 同一个投影。没有变量、节拍结果、不可见的事件。"""
        self._run(self._flush())
        return self._run(self._view(after_seq))

    async def _view(self, after_seq: int) -> Json:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                row = await store.playthrough(c, self.pid)
                st = await store.sim_state(c, self.pid)
                log_ = await store.event_log(c, self.pid, self.book.version)
                draft = await store.open_draft(c, self.pid)
        finally:
            await engine.dispose()
        assert row is not None and st is not None
        snap = snapshot(self.book, self.pid, self.role, row["status"], st, st["seq"], Run.of(row))
        if draft is not None:
            snap["pending"]["confirm"] = {
                "draftId": draft["draft_id"],
                "character": draft["character"],
                "prompt": draft["prompt"],
            }
        return {"snapshot": snap, "events": visible_events(self.book, self.role, log_, after_seq)}

    def manifest(self) -> Json:
        """2.1 的 manifest（B-7 的生成器），和正式网关 `GET /v1/books/{id}/manifest` 一样：身份的说明、人物的名字
        和读法。"""
        if self._manifest is None:
            s = self.settings
            self._manifest = generate(self.book, self.schemas, packs=s.packs, voices=s.voice_dir, release=s.release)
        return copy.deepcopy(self._manifest.doc)

    @_timed
    def retract(self, step: int) -> Json:
        """作废第 step 步那一轮（B-4）：还 hold 着就作废（原话清空、不产生事件），已经提交了 `too_late`。"""
        self.steps += 1
        return self._run(self._retract(step))

    async def _retract(self, step: int) -> Json:
        engine = self._engine()
        try:
            held = self.held
            pre = await self._prelude(engine, "retract", retract=step)
            kind = None
            if held is not None and held[0] == step:
                self.held = None
                async with engine.begin() as c:
                    kind = await store.retract_queued(c, self.pid, held[1])
        finally:
            await engine.dispose()
        out: Json = {
            "retract": "retracted" if kind is not None else "too_late",
            "events": self._events_of(pre),
            "clockMinutes": sum(r.minutes for r in pre),
        }
        if step in self.turns:
            out["traceId"] = self.turns[step]
        return out

    def utterance_cleared(self, step: int) -> bool:
        """第 step 步那一轮玩家和人物的原话都清空了（B-4：作废的一轮当场清空）。"""
        self._run(self._flush())
        turn_id = self.turns.get(step)
        if turn_id is None:
            raise ValueError(f"第 {step} 步不是对话")
        return self._run(self._cleared(turn_id))

    async def _cleared(self, turn_id: str) -> bool:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                texts = (await c.execute(select(utterances.c.text).where(utterances.c.turn_id == turn_id))).scalars()
                return all(t is None for t in texts)
        finally:
            await engine.dispose()

    async def _events(self) -> list[Json]:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                return await store.event_log(c, self.pid, self.book.version)
        finally:
            await engine.dispose()

    # —— 记忆和删除（B-13） ——

    def memory_book(self) -> Json:
        """模拟玩家只读正式記憶帳投影，不读检查用的 memories() 内部字段。"""
        self._run(self._flush())
        return self._run(self._memory_book())

    async def _memory_book(self) -> Json:
        from zoujin_backend.gateway import memory_book

        engine = self._engine()
        try:
            async with engine.connect() as c:
                return await memory_book.view(c, self.book, self.pid, self.role)
        finally:
            await engine.dispose()

    def delete_memory_id(self, memory_id: str) -> Json:
        """玩家按記憶帳给的 ID 删除；和正式 REST 共用删除事务，不能跨局删除。"""
        self._run(self._flush())
        self.steps += 1
        return self._run(self._delete_memory_id(memory_id))

    async def _delete_memory_id(self, memory_id: str) -> Json:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                d = await memory_delete.delete_memory(c, self.library, self.ids, self.schemas, self.pid, memory_id)
                evs = await store.event_log(c, self.pid, self.book.version, after_seq=(d.seq or 1) - 1)
        finally:
            await engine.dispose()
        self.last_reply.pop(d.character, None)
        return {
            "events": evs if d.seq is not None else [],
            "clockMinutes": 0,
            "deleted": d.memory_id,
            "promiseVoided": d.promise_voided,
        }

    def delete_memory(self, character: str, from_step: int) -> Json:
        """删这个人物来源于第 from_step 步提交的事件的那条记忆（和 REST 同一个函数；一个人物一轮最多一条，所以唯一）。
        没有这样的记忆 → ValueError（评测报错，不静默成功）。"""
        self._run(self._flush())
        self.steps += 1
        turn_id = self.turns.get(from_step)
        if turn_id is None:
            raise ValueError(f"第 {from_step} 步没有提交的一轮")
        return self._run(self._delete_memory(character, turn_id))

    async def _delete_memory(self, character: str, turn_id: str) -> Json:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                ids = set(
                    (
                        await c.scalars(
                            select(events_t.c.event_id).where(
                                events_t.c.playthrough_id == self.pid, events_t.c.turn_id == turn_id
                            )
                        )
                    ).all()
                )
                target = next(
                    (r["memory_id"] for r in await memory.alive(c, self.pid, character) if ids & set(r["from_events"])),
                    None,
                )
                if target is None:  # 不静默成功（数据评审）：评测报错
                    raise ValueError(f"{character} 没有来源于这一步的记忆")
                d = await memory_delete.delete_memory(c, self.library, self.ids, self.schemas, self.pid, target)
                evs = await store.event_log(c, self.pid, self.book.version, after_seq=(d.seq or 1) - 1)
        finally:
            await engine.dispose()
        return {
            "events": evs if d.seq is not None else [],
            "clockMinutes": 0,
            "deleted": d.memory_id,
            "promiseVoided": d.promise_voided,
        }

    def delete_playthrough(self) -> Json:
        """L2：这一局全删（和 REST 同一个函数）。之后 `db_absent` 查的就是这一局。"""
        self._run(self._flush())
        self.steps += 1
        self._run(self._delete_playthrough())
        return {"events": [], "clockMinutes": 0}

    async def _delete_playthrough(self) -> None:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                await memory_delete.delete_playthrough(c, self.pid)
        finally:
            await engine.dispose()
        self.deleted = self.pid

    def new_playthrough(self) -> Json:
        """同一个账号、同一个起点再开一局；这一局放弃（`abandoned`）。之后的步骤和查询都对新的一局。"""
        self._run(self._flush())
        self.steps += 1
        self._run(self._new_playthrough())
        return {"events": [], "clockMinutes": 0}

    async def _new_playthrough(self) -> None:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                await c.execute(
                    update(playthroughs).where(playthroughs.c.playthrough_id == self.pid).values(status="abandoned")
                )
        finally:
            await engine.dispose()
        self.safety = SafetyState()
        self.monitor = Monitor(self.library)
        self.monitor.attach(self.book)
        self.draft = None
        if self.persona is not None:
            await self._open()
        else:
            await self._setup()

    def memories(self, character: str) -> list[Json]:
        """契约第 4 节的 MemoryItem，删了的也在（带 deletedAt，text 是空的）。"""
        self._run(self._flush())
        return self._run(self._memories(character))

    async def _memories(self, character: str) -> list[Json]:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                rows = (
                    await c.execute(
                        select(memory_items)
                        .where(memory_items.c.playthrough_id == self.pid, memory_items.c.character == character)
                        .order_by(memory_items.c.t, memory_items.c.created_at)
                    )
                ).mappings()
                return [memory.item_json(dict(r)) for r in rows]
        finally:
            await engine.dispose()

    def trust(self, character: str) -> int:
        self._run(self._flush())
        return self._run(self._trust(character))

    async def _trust(self, character: str) -> int:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                return await memory.trust_of(c, self.book, self.pid, self.role, character)
        finally:
            await engine.dispose()

    def db_absent(self, tables: Sequence[str]) -> Mapping[str, int]:
        """每张表里还剩这一局（删了的那一局，没删过就是现在这一局）几行。data-design 5.3 里还没建的表
        （`NOT_BUILT`，局势说明不存库）答 0；名单外不认识的表名不答（评测报「后端没回这张表」，数据评审）。"""
        return self._run(self._db_absent(tables))

    async def _db_absent(self, tables: Sequence[str]) -> Mapping[str, int]:
        pid = self.deleted or self.pid
        engine = self._engine()
        out: dict[str, int] = {}
        try:
            async with engine.connect() as c:
                for name in tables:
                    if name in NOT_BUILT:
                        out[name] = 0
                    if name not in PER_PLAYTHROUGH:
                        continue
                    t = metadata.tables[name]
                    n = await c.scalar(select(func.count()).select_from(t).where(t.c.playthrough_id == pid))
                    out[name] = int(n or 0)
        finally:
            await engine.dispose()
        return out

    # —— 还没做的 ——

    def _no(self, name: str) -> NoReturn:
        raise EvalNotImplemented(name)

    def silence(self, seconds: int) -> Json:
        self._no("silence")

    def ending(self) -> Json:
        """B-9：存的 Ending（数据契约第 5 节的完整形状，含 `signature`）；还没进结局（或结局任务还没做完）返回 None。
        结局任务和别的任务一样，在触发它的那一步里同步跑完。"""
        self._run(self._flush())
        return self._run(self._ending())

    async def _ending(self) -> Json:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                body = await c.scalar(select(endings.c.body).where(endings.c.playthrough_id == self.pid))
        finally:
            await engine.dispose()
        return copy.deepcopy(body) if body is not None else None


def play_setup(w: Writer, scenarios: Mapping[str, Json], setup: Mapping[str, Json]) -> None:
    """起点：用 W-1 的 `opening()` 推演（和评测运行器同一套），结果写成这一局的初始事件（B-0 第 9 条）。

    `place`、情景的节拍改动、情景的事件、到点的节拍和期限、只推进时钟的事件都由 `opening()` 给，这里只补成完整的
    事件（eventId、summary、check）再按 seq 应用；之后在起点时刻追加 `events`（评测布置，api-contract 第 7 节）。
    """
    if "scenario" in setup:
        sc_id, until = str(setup["scenario"]), None
    else:
        sc_id, until = parse_checkpoint(str(setup["checkpoint"]))
    opened, _ = opening(w.book.world, w.state["role"], scenarios[sc_id], until, place=setup.get("place"))
    for d in opened:
        w.add(w.from_draft(d) if d["source"] == "schedule" else _setup_event(w, d))
    for e in setup.get("events", []):
        w.add(
            w.full(
                t=w.state["t"],
                dt=0,
                actor="system",
                type="action",
                place=w.player_place,
                summary=e.get("note") or "評価の設定",
                effects=e["effects"],
                check=SETUP_PASSED,
            )
        )


def setup_act_end(book: Book, w: Writer, setup: Mapping[str, Json]) -> Json | None:
    """检查点停在这一幕的收幕节拍上（例 `sc.canon@beat.07`）：setup 之后就是幕末待选（B-3 第 5 条），幕末的去处
    记在局上。只认收幕节拍本身：停在更后面的节拍上的老用例（`opening()` 不换幕）照旧可以对话。"""
    if "checkpoint" not in setup:
        return None
    _, until = parse_checkpoint(str(setup["checkpoint"]))
    act = acts.current_act(book, w.state)
    if not act.get("exits") or until is None or until[0] != "beat" or until[1] not in act["end"]["onBeats"]:
        return None
    if not act_closed(book, w.state):
        return None
    return acts.act_end(book, w.state, 0, w.events)


def _setup_event(w: Writer, d: Opened) -> Json:
    """开局地点、情景、只推进时钟的事件：summary 用 `opening()` 给的 note。"""
    e = d["event"]
    return w.full(
        t=e["t"],
        dt=e["dt"],
        actor=e["actor"],
        type=e["type"],
        origin=e.get("origin"),
        place=e["place"],
        summary=d.get("note") or "評価の設定",
        effects=e["effects"],
        check=SETUP_PASSED,
    )
