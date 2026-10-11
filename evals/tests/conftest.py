"""评测运行器测试共用的东西：世界模型、两种后端的替身。

- ScriptedSession：结果全部预先写好，给单条检查的过 / 不过用；
- SimApi：只用 W-1 推演的后端替身。做 scenario、checkpoint（含 place、events）、say（固定回答、只走时钟）、
  advance 和 state() / events()，推演到底的局还有 ending() 的世界结局。B-0 没好之前，拿它确认「只靠推演就能判的
  检查」在真实的事件日志上判得对（E-0 卡验收第 2 条）。其余步骤和查询抛 EvalNotImplemented，和 B-0 最小版一样。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from zoujin_evals import RunContext, StepResult, WorldIndex
from zoujin_evals.api import EvalNotImplemented, EvalSession, Event
from zoujin_worldsim import SimState, apply, classify, initial_state, opening, parse_checkpoint, settle, world_state

REPO = Path(__file__).resolve().parents[2]
WORLD_DIR = REPO / "worlds" / "hashire-merosu" / "1.0.0-draft"
SEEDS = REPO / "evals" / "seeds"
SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"

WORLD: dict[str, Any] = json.loads((WORLD_DIR / "world.json").read_text(encoding="utf-8"))
SCENARIOS: dict[str, dict[str, Any]] = {
    "sc.canon": {"id": "sc.canon"},
    **{s["id"]: s for s in json.loads((WORLD_DIR / "scenarios.json").read_text(encoding="utf-8"))},
}
WORLD_IX = WorldIndex(WORLD)


@pytest.fixture(scope="session")
def world_ix() -> WorldIndex:
    return WORLD_IX


# ---------- 预先写好结果的会话 ----------


@dataclass
class ScriptedSession:
    state_: dict[str, Any] = field(default_factory=dict)
    events_: list[Event] = field(default_factory=list)
    memories_: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    trust_: dict[str, int] = field(default_factory=dict)
    cleared: set[int] = field(default_factory=set)
    db: dict[str, int] = field(default_factory=dict)
    ending_: dict[str, Any] | None = None
    no_ending: bool = False  # 后端实现了 ending()，但这一局没进结局（回 None）

    def state(self) -> dict[str, Any]:
        return self.state_

    def events(self) -> list[Event]:
        return self.events_

    def memories(self, character: str) -> list[dict[str, Any]]:
        return self.memories_.get(character, [])

    def trust(self, character: str) -> int:
        return self.trust_[character]

    def utterance_cleared(self, step: int) -> bool:
        return step in self.cleared

    def db_absent(self, tables: Sequence[str]) -> Mapping[str, int]:
        return {t: self.db.get(t, 0) for t in tables}

    def ending(self) -> dict[str, Any] | None:
        if self.no_ending:
            return None
        if self.ending_ is None:
            raise EvalNotImplemented("ending")
        return self.ending_


type MakeCtx = Callable[..., RunContext]


@pytest.fixture
def make_ctx() -> MakeCtx:
    """make_ctx(steps=[…], results=[…], setup={…}, setup_events=[…], played=[…], **ScriptedSession 的字段)
    → RunContext。played 是模拟局里 AI 玩家走的步骤。"""

    def make(
        steps: Sequence[Mapping[str, Any]] = (),
        results: Sequence[StepResult] = (),
        setup: Mapping[str, Any] | None = None,
        setup_events: list[Event] | None = None,
        played: Sequence[Mapping[str, Any]] | None = None,
        **session: Any,
    ) -> RunContext:
        case = {
            "id": "T-001",
            "suite": "T",
            "setup": setup or {"role": "role.traveler", "checkpoint": "sc.canon@beat.03"},
            "steps": list(steps),
        }
        s: EvalSession = ScriptedSession(**session)  # type: ignore[assignment]
        return RunContext(
            world=WORLD_IX,
            case=case,
            session=s,
            results=list(results),
            setup_events=setup_events,
            played=None if played is None else list(played),
        )

    return make


def ev(
    eid: str | None = None,
    *,
    status: str = "passed",
    effects: Sequence[Mapping[str, Any]] = (),
    **kw: Any,
) -> Event:
    """测试里写事件的简写。"""
    rules = kw.pop("failedRules", [])
    e: Event = {"type": "say", "actor": "char.melos", "origin": "turn", "effects": list(effects), **kw}
    e["check"] = {"status": status, "failedRules": rules}
    if eid is not None:
        e["eventId"] = eid
    return e


@pytest.fixture(scope="session")
def make_event() -> Callable[..., Event]:
    return ev


# ---------- 只用 W-1 推演的后端替身 ----------


class SimSession:
    """一局：事件日志 + W-1 的状态。每个事件按卡的协议先 settle 到它的 t 再 apply。"""

    def __init__(self, role: str) -> None:
        self.role = role
        self.s: SimState = initial_state(WORLD, role)
        self.log: list[Event] = []
        self.done = False  # 推演到底了（scenario）：ending() 有世界结局
        self.steps = 0

    # ----- 写事件 -----
    def _write(self, e: Mapping[str, Any]) -> Event:
        full: Event = {
            "eventId": f"ev_{len(self.log) + 1:04d}",
            "seq": len(self.log) + 1,
            "actor": "system",
            "type": "action",
            "dt": 0,
            "place": self.s["vars"]["var.player.location"],
            "causes": [],
            "effects": [],
            "check": {"status": "passed", "failedRules": [], "checker": "sim"},
            **e,
        }
        self.s = apply(WORLD, self.s, full)
        self.log.append(full)
        return full

    def settle_to(self, t2: int | None) -> list[Event]:
        drafts, _ = settle(WORLD, self.s, t2)
        return [self._write(d["event"]) for d in drafts]

    def move_clock(self, t2: int) -> list[Event]:
        """时钟走到 t2：结算到 t2，再写一个只推进时钟的事件（契约：时钟只由事件推出）。"""
        evs = self.settle_to(t2)
        if self.s["t"] < t2:
            evs.append(self._write({"t": t2, "effects": []}))
        return evs

    # ----- 步骤 -----
    def say(self, to: str, text: str) -> StepResult:
        self.steps += 1
        act4 = max(WORLD["acts"], key=lambda a: a["order"])["start"]["t"]
        minutes = WORLD["pacing"]["talkTurnMinutesAct4" if self.s["t"] >= act4 else "talkTurnMinutes"]
        t = self.s["t"]
        evs = self.settle_to(t)
        evs.append(self._write({"t": t, "dt": minutes, "actor": "player", "type": "say", "origin": "turn"}))
        evs += self.settle_to(self.s["t"])
        return {"reply": "……そうか。", "events": evs, "clockMinutes": minutes, "traceId": f"tr_{self.steps}"}

    def advance(self, minutes: int) -> StepResult:
        self.steps += 1
        evs = self.move_clock(self.s["t"] + minutes)
        return {"events": evs, "clockMinutes": minutes, "traceId": f"tr_{self.steps}"}

    # ----- 查询 -----
    def state(self) -> dict[str, Any]:
        return world_state(WORLD, self.s, "pt_sim")

    def events(self) -> list[Event]:
        return list(self.log)

    def ending(self) -> dict[str, Any]:
        if not self.done:
            raise EvalNotImplemented("ending")
        return {"world": {"outcome": classify(WORLD, self.s)}}


class SimApi:
    """setup(setup, mode=…) → SimSession。"""

    def __init__(self) -> None:
        self.sessions: list[SimSession] = []

    def setup(self, setup: Mapping[str, Any], *, mode: str = "text") -> EvalSession:
        if "persona" in setup:
            raise EvalNotImplemented("persona")
        sc_id, until = (setup["scenario"], None) if "scenario" in setup else parse_checkpoint(setup["checkpoint"])
        opened, _ = opening(WORLD, setup["role"], SCENARIOS[sc_id], until, place=setup.get("place"))
        sess = SimSession(setup["role"])  # 起点之前的事件和 B-0 一样由 worldsim 的 opening() 写出
        for o in opened:
            sess._write(o["event"])
        sess.done = until is None
        for e in setup.get("events", []):  # 评测布置：t = 起点时刻
            check = {"status": "passed", "failedRules": [], "checker": "eval-setup"}
            sess._write({"t": sess.s["t"], "effects": e["effects"], "check": check})
        self.sessions.append(sess)
        return sess  # type: ignore[return-value]


@pytest.fixture
def sim_api() -> SimApi:
    return SimApi()
