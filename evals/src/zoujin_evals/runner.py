"""跑用例：每例按 runs 重复 setup → 逐步执行 → 检查（E-0 卡第 1 条）。

- setup 照用例原样交给后端，运行器自己不推演、不补字段。
- setup 或某一步后端没做（EvalNotImplemented）：每次都一样，只试第一次，整例记「跳过：后端未实现（名字）」。
- 某个查询没做：只有用到它的检查跳过，其余照常判。
- 回放里查不到（ReplayMissing）：这一次记「回放缺失或过期」，不当作通过，也不退回假模型。
- 后端抛了别的异常：这一次算不过，原因写异常，运行器不崩。
- 每次有时限（data-design 7.3：文字 10 分钟，语音和模拟局 30 分钟起步），超时重跑一次，仍超时记「超时」。
"""

from __future__ import annotations

import signal
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from types import FrameType
from typing import Any, Protocol

from .api import EvalApi, EvalNotImplemented, EvalSession, Event, Json, StepResult, not_implemented, replay_missing
from .checks import CHECKS, RunContext, WorldIndex, step_kind
from .results import CaseResult, CheckResult, RunResult, Skip, SkipCheck, run_status

TIMEOUT_TEXT_S = 600.0
TIMEOUT_LONG_S = 1800.0  # 语音、模拟局


class Judge(Protocol):
    """LLM 评审（E-0 卡第 4 条）：按用例的 expect.judge（rubric、pass）给一次运行打分。"""

    def __call__(self, case: Mapping[str, Json], ctx: RunContext) -> CheckResult: ...


def skip_judge(case: Mapping[str, Json], ctx: RunContext) -> CheckResult:
    """现在没有真模型：判分全部记「跳过：要真模型」。"""
    return {"index": 0, "type": "judge", "status": "skip", "skip": {"code": "needs-live-model"}}


@dataclass
class Options:
    deterministic_only: bool = False  # 不跑判分（真模型时省钱；假模型和回放本来也判不了）
    judge: Judge = skip_judge
    timeout_s: float | None = None  # 每次的时限；None = 按用例的 mode 和起点取默认值，0 = 不限
    progress: Callable[[str], None] = field(default=lambda _: None)


class RunTimeout(BaseException):
    """一次运行超过时限。继承 BaseException：检查里的 except Exception 拦不住它。"""


class _WholeCase(Exception):
    def __init__(self, skip: Skip) -> None:
        super().__init__(skip)
        self.skip = skip


def validate(cases: Sequence[Mapping[str, Json]]) -> list[str]:
    """遇到不认识的检查类型和步骤就报错，不悄悄跳过（E-0 卡第 2 条）。"""
    errors = []
    for c in cases:
        for d in c.get("expect", {}).get("deterministic", []):
            if d.get("type") not in CHECKS:
                errors.append(f"{c.get('id')}：不认识的检查 {d.get('type')}")
        for s in c.get("steps", []):
            try:
                step_kind(s)
            except ValueError as e:
                errors.append(f"{c.get('id')}：{e}")
    return errors


def run_cases(
    api: EvalApi | None, cases: Sequence[Mapping[str, Json]], world: WorldIndex, opts: Options
) -> list[CaseResult]:
    errors = validate(cases)
    if errors:
        raise ValueError("用例里有运行器不认识的东西：\n" + "\n".join(errors))
    return [run_case(api, c, world, opts) for c in cases]


def run_case(api: EvalApi | None, case: Mapping[str, Json], world: WorldIndex, opts: Options) -> CaseResult:
    runs = case.get("runs", 5)
    out: CaseResult = {
        "id": case["id"],
        "suite": case["suite"],
        "title": case["title"],
        "mode": case.get("mode", "text"),
        "runs": runs,
    }
    if api is None:
        out["skip"] = {"code": "not-implemented", "name": "eval_api"}
        opts.progress(f"{case['id']} 跳过：没有后端的评测入口")
        return out
    results: list[RunResult] = []
    for i in range(1, runs + 1):
        try:
            results.append(_run_with_retry(api, case, world, opts, i))
        except _WholeCase as e:
            out["skip"] = e.skip
            opts.progress(f"{case['id']} 跳过：后端未实现（{e.skip.get('name')}）")
            return out
        opts.progress(f"{case['id']} 第 {i}/{runs} 次：{results[-1]['status']}")
    out["results"] = results
    return out


def _timeout(case: Mapping[str, Json], opts: Options) -> float:
    if opts.timeout_s is not None:
        return opts.timeout_s
    long = case.get("mode") == "voice" or "persona" in case.get("setup", {})
    return TIMEOUT_LONG_S if long else TIMEOUT_TEXT_S


def _run_with_retry(api: EvalApi, case: Mapping[str, Json], world: WorldIndex, opts: Options, i: int) -> RunResult:
    for _ in range(2):
        try:
            with time_limit(_timeout(case, opts)):
                return run_once(api, case, world, opts, i)
        except RunTimeout:
            opts.progress(f"{case['id']} 第 {i} 次超时")
    return {"run": i, "status": "skip", "checks": [], "skip": {"code": "timeout"}, "traceIds": []}


def run_once(api: EvalApi, case: Mapping[str, Json], world: WorldIndex, opts: Options, i: int) -> RunResult:
    results: list[StepResult] = []
    try:
        session = api.setup(case["setup"], mode=case.get("mode", "text"))
        if "persona" in case["setup"]:
            # 模拟局：AI 玩家在运行器里按画像逐步走（后端只按 persona、seed 定身份、起点和假模型的种子）。
            # AI 玩家要真模型，M2 接上；现在这一次记「要真模型」
            return {"run": i, "status": "skip", "checks": [], "skip": {"code": "needs-live-model"}, "traceIds": []}
        setup_events = _setup_events(session)
        for step in case.get("steps", []):
            results.append(call_step(session, step))
    except Exception as e:
        name = not_implemented(e)
        if name is not None:
            raise _WholeCase({"code": "not-implemented", "name": name}) from e
        traces = [r["traceId"] for r in results if "traceId" in r]
        if replay_missing(e):
            return {"run": i, "status": "skip", "checks": [], "skip": {"code": "replay-missing"}, "traceIds": traces}
        return {"run": i, "status": "fail", "checks": [], "error": f"{type(e).__name__}: {e}", "traceIds": traces}

    ctx = RunContext(world=world, case=case, session=session, results=results, setup_events=setup_events)
    expect = case.get("expect", {})
    checks = [run_check(ctx, n, spec) for n, spec in enumerate(expect.get("deterministic", []), 1)]
    out: RunResult = {"run": i, "status": "pass", "checks": checks, "traceIds": []}
    judge = None
    if "judge" in expect and not opts.deterministic_only:
        out["judge"] = judge = opts.judge(case, ctx)
    out["status"] = run_status(checks, judge)
    if not checks and judge is None:  # 只有判分的用例只跑确定性检查
        out["skip"] = {"code": "needs-live-model"}
    out["traceIds"] = [r["traceId"] for r in results if "traceId" in r]
    return out


def _setup_events(session: EvalSession) -> list[Event] | None:
    """setup 刚结束时这一局的事件：world_unchanged 拿它算原情景。后端没做 events() 时 None。"""
    fn = getattr(session, "events", None)
    if fn is None:
        return None
    try:
        evs: list[Event] = fn()
    except Exception as e:
        if not_implemented(e) is not None:
            return None
        raise
    return evs


_STEP_CALLS: dict[str, tuple[str, Callable[[Any], tuple[Any, ...]]]] = {
    "to": ("say", lambda s: (s["to"], s["say"])),
    "act": ("act", lambda s: (s["act"]["kind"], s["act"].get("target"), s["act"].get("params", {}))),
    "deleteMemory": ("delete_memory", lambda s: (s["deleteMemory"]["character"], s["deleteMemory"]["fromStep"])),
    "retract": ("retract", lambda s: (s["retract"]["step"],)),
    "deletePlaythrough": ("delete_playthrough", lambda s: ()),
    "newPlaythrough": ("new_playthrough", lambda s: ()),
    "advance": ("advance", lambda s: (s["advance"],)),
    "silence": ("silence", lambda s: (s["silence"],)),
    "propose": ("propose", lambda s: (s["propose"],)),
    "choose": ("choose", lambda s: (s["choose"]["exit"], s["choose"].get("enRoute"))),
}


def call_step(session: EvalSession, step: Mapping[str, Json]) -> StepResult:
    method, args = _STEP_CALLS[step_kind(step)]
    fn = getattr(session, method, None)
    if fn is None:
        raise EvalNotImplemented(method)
    result: StepResult = fn(*args(step))
    return result


def run_check(ctx: RunContext, index: int, spec: Mapping[str, Json]) -> CheckResult:
    out: CheckResult = {"index": index, "type": spec["type"], "status": "pass"}
    try:
        reason = CHECKS[spec["type"]](ctx, spec)
    except SkipCheck as e:
        out["status"], out["skip"] = "skip", e.skip
        return out
    except Exception as e:
        name = not_implemented(e)
        if name is not None:
            out["status"], out["skip"] = "skip", {"code": "not-implemented", "name": name}
        elif replay_missing(e):
            out["status"], out["skip"] = "skip", {"code": "replay-missing"}
        else:
            out["status"], out["reason"] = "fail", f"检查时出错：{type(e).__name__}: {e}"
        return out
    if reason is not None:
        out["status"], out["reason"] = "fail", reason
    return out


@contextmanager
def time_limit(seconds: float) -> Iterator[None]:
    """到时限抛 RunTimeout。只在主线程、有 SIGALRM 的系统上生效（Mac、Linux）；seconds = 0 不限。"""
    if not seconds or threading.current_thread() is not threading.main_thread() or not hasattr(signal, "setitimer"):
        yield
        return

    def handler(signum: int, frame: FrameType | None) -> None:
        raise RunTimeout

    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)
