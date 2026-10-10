"""评测入口（api-contract 第 7 节、B-0 第 9 条的最小版）：给数据工程的运行器在 Python 包内调，不开 HTTP，生产环境没有。

    from zoujin_backend import eval_api
    s = eval_api.setup({"role": "role.traveler", "checkpoint": "sc.canon@beat.03"}, mode="text")
    s.say("char.old-man", "…")
    s.state()

- `setup` 每次读 `DATABASE_URL` 和 `ZJ_MODEL`（fake / replay）。一局是测试库里真的一局：一个新账号、一局、
  起点的事件和 world_state，之后的步骤走和网关同一个叙事者（`Narrator.run`）。
- 做了的：setup 的 `role`、`place`、`budgetTier`（只记下）、`scenario`、`checkpoint`、`events`；步骤 `say`、
  `advance`；`check`（不提交）；查询 `state()`、`events()`。
- 没做的步骤和查询、带 `persona` 的 setup、带 `memory` 的布置事件抛 `EvalNotImplemented("<名字>")`；
  回放里查不到抛 `ReplayMissing`。运行器按类名认。
- 每次调用在自己的事件循环里跑（`asyncio.run`）、用不进连接池的连接，运行器的超时（SIGALRM）中途打断时，
  丢下的那一局只是留在测试库里。
"""

from __future__ import annotations

import asyncio
import copy
import json
from collections.abc import Coroutine, Mapping, Sequence
from functools import cache
from pathlib import Path
from typing import Any, NoReturn

from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from zoujin_worldsim import OCCURRED, SimState, initial_state, role_of, world_state

from zoujin_backend.config import Settings
from zoujin_backend.db import store
from zoujin_backend.db.events import recorded_at, to_row
from zoujin_backend.db.tables import events as events_t
from zoujin_backend.db.tables import playthrough_metrics, playthroughs, users
from zoujin_backend.db.tables import world_state as world_state_t
from zoujin_backend.ids import IdGen
from zoujin_backend.models.text import ReplayMissing, TextModel, text_model
from zoujin_backend.narrator.core import Narrator, Result
from zoujin_backend.narrator.rules import check_candidates
from zoujin_backend.narrator.writer import Writer
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.world import Book, Library

__all__ = ["EvalNotImplemented", "ReplayMissing", "Session", "setup"]

Json = Any

BOOK = "hashire-merosu"
CHECKER = "eval-setup"
SETUP_PASSED: Json = {"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER}


class EvalNotImplemented(Exception):
    """B-0 没做的步骤或查询（运行器按类名认，记「跳过：后端未实现」）。"""


@cache
def _library(worlds: Path, scenes: Path) -> Library:
    return Library(worlds, scenes)


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
    return asyncio.run(coro)


def setup(setup: Mapping[str, Json], *, mode: str = "text") -> Session:
    """开一局。setup 是用例的 setup 原样，mode 是 text / voice（B-0 两种都走文字的叙事者流程）。"""
    if "persona" in setup:
        raise EvalNotImplemented("persona")
    if any("memory" in e for e in setup.get("events", [])):
        raise EvalNotImplemented("memory")
    settings = Settings.from_env()
    library = _library(settings.worlds, settings.scenes)
    book = library.book(setup.get("book", BOOK))
    if book is None:
        raise ValueError(f"没有这本书：{setup.get('book', BOOK)}")
    if setup["role"] not in book.roles:
        raise ValueError(f"没有这个身份：{setup['role']}")
    s = Session(settings, library, book, setup, mode)
    _run(s._setup())
    return s


class Session:
    def __init__(self, settings: Settings, library: Library, book: Book, setup: Mapping[str, Json], mode: str) -> None:
        self.settings = settings
        self.library = library
        self.book = book
        self.setup_doc = copy.deepcopy(dict(setup))
        self.mode = mode
        self.role: str = setup["role"]
        self.budget_tier: str = setup.get("budgetTier", "normal")  # 只记下（预算是 M2 的卡）
        self.ids = IdGen()
        self.text: TextModel = text_model(settings.model, fake_rules=settings.fake_text, replays=settings.replays)
        self.schemas = _schemas(settings.schemas)
        self.pid = ""
        self.steps = 0

    # —— 连接和叙事者：每次调用新建（各自的事件循环） ——

    def _engine(self) -> AsyncEngine:
        return create_async_engine(self.settings.database_url, poolclass=NullPool)

    def _narrator(self, engine: AsyncEngine) -> Narrator:
        return Narrator(engine=engine, library=self.library, text=self.text, schemas=self.schemas, ids=self.ids)

    # —— 起点 ——

    async def _setup(self) -> None:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                user_id = self.ids.new("usr")
                await c.execute(insert(users).values(user_id=user_id))
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
                w = Writer(
                    self.book,
                    self.pid,
                    initial_state(self.book.world, self.role),
                    key_base=f"{self.pid}/setup",
                    turn_id=None,
                    ids=self.ids,
                    now=recorded_at(),
                )
                Start(w, _scenarios(self._world_dir())).play(self.setup_doc)
                for ev in w.events:
                    self.schemas.event(ev)
                if w.events:
                    await c.execute(insert(events_t), [to_row(e) for e in w.events])
                await c.execute(
                    insert(world_state_t).values(playthrough_id=self.pid, as_of_seq=w.state["seq"], state=w.state)
                )
                await c.execute(
                    update(playthroughs)
                    .where(playthroughs.c.playthrough_id == self.pid)
                    .values(last_seq=w.state["seq"])
                )
        finally:
            await engine.dispose()

    def _world_dir(self) -> Path:
        for p in self.settings.worlds.glob("*/*/world.json"):
            if json.loads(p.read_text(encoding="utf-8"))["worldModelVersion"] == self.book.version:
                return p.parent
        raise FileNotFoundError(self.book.version)

    # —— 步骤 ——

    def say(self, to: str, text: str) -> Json:
        """文字代替语音：人物的回答（文本模型 reply），原话和这一轮写进去，走叙事者。"""
        self.steps += 1
        return _run(self._say(to, text))

    async def _say(self, to: str, text: str) -> Json:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                st = await store.sim_state(c, self.pid)
                assert st is not None
                request = {
                    "role": self.role,
                    "place": st["vars"]["var.player.location"],
                    "t": st["t"],
                    "character": to,
                    "player": text,
                }
                answer = await self.text.call("reply", request)
                reply = answer.output.get("text")
                turn_id = await store.enqueue(c, self.ids, self.pid, kind="talk", input_mode="text", character=to)
                await store.add_utterance(c, self.ids, self.pid, turn_id, speaker="player", text=text, t=st["t"])
                await store.add_utterance(
                    c, self.ids, self.pid, turn_id, speaker=to, text=reply, t=st["t"], source="live"
                )
            done = await self._narrator(engine).run(self.pid)
        finally:
            await engine.dispose()
        result = self._only(done, turn_id)
        return {
            "reply": reply,
            "characterTextMissing": reply is None,
            "events": self._step_events(result),
            "clockMinutes": result.minutes,
            "traceId": turn_id,
        }

    def advance(self, minutes: int) -> Json:
        self.steps += 1
        return _run(self._advance(minutes))

    async def _advance(self, minutes: int) -> Json:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                turn_id = await store.enqueue(c, self.ids, self.pid, kind="advance", minutes=minutes)
            done = await self._narrator(engine).run(self.pid)
        finally:
            await engine.dispose()
        result = self._only(done, turn_id)
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
        """S-2：候选事件交给第 3 步（W-1 的 check_effects），不提交。B-0 没有第 4 步，模型检查记 skipped。"""
        st = _run(self._state())
        (checked,) = check_candidates(self.book.world, st, [dict(candidate)], self.ids)
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
        return world_state(self.book.world, _run(self._state()), self.pid)

    def events(self) -> list[Json]:
        """这一局的全部事件（含评测布置的、被否决的），按 seq。"""
        return _run(self._events())

    async def _events(self) -> list[Json]:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                return await store.event_log(c, self.pid, self.book.version)
        finally:
            await engine.dispose()

    # —— B-0 没做的 ——

    def _no(self, name: str) -> NoReturn:
        raise EvalNotImplemented(name)

    def act(self, kind: str, target: str | None, params: Mapping[str, Json]) -> Json:
        self._no("act")

    def delete_memory(self, character: str, from_step: int) -> Json:
        self._no("delete_memory")

    def retract(self, step: int) -> Json:
        self._no("retract")

    def delete_playthrough(self) -> Json:
        self._no("delete_playthrough")

    def new_playthrough(self) -> Json:
        self._no("new_playthrough")

    def silence(self, seconds: int) -> Json:
        self._no("silence")

    def propose(self, text: str) -> Json:
        self._no("propose")

    def choose(self, exit: str, en_route: int | None = None) -> Json:
        self._no("choose")

    def memories(self, character: str) -> list[Json]:
        self._no("memories")

    def trust(self, character: str) -> int:
        self._no("trust")

    def utterance_cleared(self, step: int) -> bool:
        self._no("utterance_cleared")

    def db_absent(self, tables: Sequence[str]) -> Mapping[str, int]:
        self._no("db_absent")

    def ending(self) -> Json:
        self._no("ending")


class Start:
    """起点：用 W-1 推演，结果写成这一局的初始事件（B-0 第 9 条）。

    - `place`：时钟 0 一个评测布置事件，改玩家所在地；
    - 情景的节拍改动：时钟 0 一个事件；情景的事件按 t 排，每个之前先结算到它的 t；
    - `scenario`：推演到底；`checkpoint`：`<情景>@<节拍>` 停在那个节拍的系统事件刚写完，`<情景>@t=<分钟>`
      结算到那一刻再写一个只推进时钟的事件（含那一刻的期限规则）；
    - `events`：起点时刻的评测布置，只给了 effects 的补成完整事件（api-contract 第 7 节）。
    """

    def __init__(self, w: Writer, scenarios: Mapping[str, Json]) -> None:
        self.w = w
        self.scenarios = scenarios

    def play(self, setup: Mapping[str, Json]) -> None:
        w = self.w
        if "place" in setup:
            self._setup_event(0, [{"op": "set", "var": "var.player.location", "value": setup["place"]}], "開始地点")
        if "scenario" in setup:
            self._scenario(self.scenarios[setup["scenario"]], None)
        else:
            sc_id, _, at = str(setup["checkpoint"]).partition("@")
            until = ("t", int(at[2:])) if at.startswith("t=") else ("beat", at)
            self._scenario(self.scenarios[sc_id], until)
        for e in setup.get("events", []):
            self._setup_event(w.state["t"], e["effects"], e.get("note") or "評価の設定")

    def _setup_event(self, t: int, effects: Sequence[Json], summary: str) -> None:
        w = self.w
        w.add(
            w.full(
                t=t,
                dt=0,
                actor="system",
                type="action",
                place=w.player_place,
                summary=summary,
                effects=effects,
                check=SETUP_PASSED,
            )
        )

    def _scenario(self, sc: Mapping[str, Json], until: tuple[str, Any] | None) -> None:
        w = self.w
        if sc.get("beats"):
            effects = [{"op": "beat", "beat": b, **o} for b, o in sc["beats"].items()]
            w.add(
                w.full(
                    t=0,
                    dt=0,
                    actor="system",
                    type="action",
                    origin="action",
                    place=w.player_place,
                    summary=f"情景 {sc['id']}",
                    effects=effects,
                    check=SETUP_PASSED,
                )
            )
        start = int(role_of(w.book.world, w.state["role"])["startT"])
        if self._until(start, until):
            return
        for e in sorted(sc.get("events", []), key=lambda e: e["t"]):
            if self._until(e["t"], until):
                return
            w.add(
                w.full(
                    t=e["t"],
                    dt=0,
                    actor="system",
                    type="action",
                    origin="action",
                    place=w.player_place,
                    summary=e.get("note") or f"情景 {sc['id']}",
                    effects=e["effects"],
                    check=SETUP_PASSED,
                )
            )
        if until is None:
            w.settle(None)
        else:
            self._until(None, until)

    def _until(self, t2: int | None, until: tuple[str, Any] | None) -> bool:
        """结算到 t2，碰到检查点就停；返回停没停。"""
        w = self.w
        if until is None:
            w.settle(t2)
            return False
        kind, x = until
        if kind == "t":
            if t2 is None or t2 >= x:
                self._move_clock(int(x))
                return True
            w.settle(t2)
            return False
        written = w.settle(t2, stop_after=x)
        return any(
            any(f.get("op") == "beat" and f.get("beat") == x and f.get("to") in OCCURRED for f in e["effects"])
            for e in written
        )

    def _move_clock(self, t2: int) -> None:
        w = self.w
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
                    check=SETUP_PASSED,
                )
            )
