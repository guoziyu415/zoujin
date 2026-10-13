"""Running cases: each case repeats setup → step-by-step execution → checks, `runs` times (E-0 card item 1).

- setup is handed to the backend exactly as in the case; the runner itself does not simulate or fill in fields.
- The backend has not implemented setup or some step (EvalNotImplemented): it is the same every time, so only the first
  run is tried, and the whole case records "skipped: backend not implemented (name)".
- A query is not implemented: only the checks that use it are skipped; the rest are judged as usual.
- Not found in the replay (ReplayMissing): this run records "replay missing or stale", is not treated as a pass, and
  does not fall back to the fake model.
- The backend raised some other exception: this run counts as failed, the exception is written as the reason, and the
  runner does not crash.
- Each run has a time limit (data-design 7.3: 10 minutes for text, at least 30 minutes for voice and simulated games);
  on a timeout it is rerun once, and if it times out again it records "timeout".

ケースの実行：各ケースは runs 回、setup → ステップを順に実行 → チェック を繰り返す（E-0 カード第 1 条）。

- setup はケースのままバックエンドに渡し、ランナー自身はシミュレーションもフィールドの補完もしない。
- バックエンドが setup またはあるステップを未実装（EvalNotImplemented）：毎回同じなので最初の 1 回だけ試し、ケース全体を
  「スキップ：バックエンド未実装（名前）」と記録する。
- あるクエリが未実装：それを使うチェックだけをスキップし、残りは通常どおり判定する。
- リプレイに見つからない（ReplayMissing）：この回は「リプレイが無いか期限切れ」と記録し、合格扱いにせず、偽モデルにも
  戻らない。
- バックエンドがそれ以外の例外を投げた：この回は不合格とし、理由に例外を書く。ランナーはクラッシュしない。
- 各回には時間制限がある（data-design 7.3：テキストは 10 分、音声とシミュレーション局は 30 分から）。タイムアウトしたら
  1 回再実行し、それでもタイムアウトなら「タイムアウト」と記録する。
"""

from __future__ import annotations

import signal
import threading
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from types import FrameType
from typing import Any, Literal, Protocol

from zoujin_llm import Stop

from .api import EvalApi, EvalNotImplemented, EvalSession, Event, Json, StepResult, not_implemented, replay_missing
from .checks import CHECKS, RunContext, WorldIndex, step_kind
from .player import MAX_STEPS, Persona, Played, Player, load_personas, play, sim_stats
from .results import CaseResult, CheckResult, RunResult, Skip, SkipCheck, run_status

TIMEOUT_TEXT_S = 600.0
TIMEOUT_LONG_S = 1800.0  # voice, simulated games / 音声、シミュレーション局


class Judge(Protocol):
    """LLM judge (E-0 card item 4): scores one run by the case's expect.judge (rubric, pass).

    LLM 審査（E-0 カード第 4 条）：ケースの expect.judge（rubric、pass）に従って 1 回の実行を採点する。
    """

    def __call__(self, case: Mapping[str, Json], ctx: RunContext) -> CheckResult: ...


def skip_judge(case: Mapping[str, Json], ctx: RunContext) -> CheckResult:
    """There is no real model for now: all judging records "skipped: needs a real model".

    現在は実モデルがない：採点はすべて「スキップ：実モデルが必要」と記録する。
    """
    return {"index": 0, "type": "judge", "status": "skip", "skip": {"code": "needs-live-model"}}


@dataclass
class Options:
    # do not run judging (saves money with a real model; the fake model and replays cannot judge anyway)
    # 採点を実行しない（実モデルでは費用の節約。偽モデルとリプレイはもともと採点できない）
    deterministic_only: bool = False
    judge: Judge = skip_judge
    # time limit per run; None = default by the case's mode and starting point, 0 = no limit
    # 各回の時間制限。None = ケースの mode と開始点に応じたデフォルト、0 = 無制限
    timeout_s: float | None = None
    progress: Callable[[str], None] = field(default=lambda _: None)
    # The AI player of simulated games: one made per case (player.py). None = simulated games record "needs a real
    # model".
    # シミュレーション局の AI プレイヤー：ケースごとに 1 つ作る（player.py）。None = シミュレーション局は「実モデルが
    # 必要」と記録する
    player: Callable[[Mapping[str, Json]], Player] | None = None
    personas: Mapping[str, Persona] = field(default_factory=load_personas)
    max_steps: int = MAX_STEPS
    # Finite batches can set 0: a timed-out half game is kept as evidence, and no paid game is restarted automatically.
    # 有限バッチでは 0 にできる：タイムアウトした途中の局は証拠として残し、有料の局を自動で再開しない。
    timeout_retries: int = 1


class RunTimeout(BaseException):
    """One run went over its time limit. Inherits BaseException so that `except Exception` in checks cannot catch it.

    1 回の実行が時間制限を超えた。BaseException を継承するので、チェック内の except Exception では捕まえられない。
    """


class _WholeCase(Exception):
    def __init__(self, skip: Skip) -> None:
        super().__init__(skip)
        self.skip = skip


def validate(cases: Sequence[Mapping[str, Json]]) -> list[str]:
    """Report unknown check types and steps as errors instead of skipping them silently (E-0 card item 2).

    不明なチェックの種類とステップはエラーにし、黙ってスキップしない（E-0 カード第 2 条）。
    """
    errors = []
    for c in cases:
        for d in c.get("expect", {}).get("deterministic", []):
            if d.get("type") not in CHECKS:
                errors.append(f"{c.get('id')}: unknown check {d.get('type')} / 不明なチェック {d.get('type')}")
        for s in c.get("steps", []):
            try:
                step_kind(s)
            except ValueError as e:
                errors.append(f"{c.get('id')}: {e}")
    return errors


def run_cases(
    api: EvalApi | None, cases: Sequence[Mapping[str, Json]], world: WorldIndex, opts: Options
) -> list[CaseResult]:
    errors = validate(cases)
    if errors:
        raise ValueError(
            "The cases contain things the runner does not know / ケースにランナーの知らないものがある:\n"
            + "\n".join(errors)
        )
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
    if any("deleteMemory" in s or "deletePlaythrough" in s for s in case.get("steps", [])):
        out["deletes"] = True
    if api is None:
        out["skip"] = {"code": "not-implemented", "name": "eval_api"}
        opts.progress(f"{case['id']} skipped: no backend eval entry point / スキップ：バックエンドの評価エントリがない")
        return out
    results: list[RunResult] = []
    for i in range(1, runs + 1):
        try:
            results.append(_run_with_retry(api, case, world, opts, i))
        except _WholeCase as e:
            out["skip"] = e.skip
            name = e.skip.get("name")
            opts.progress(
                f"{case['id']} skipped: backend not implemented ({name}) / スキップ：バックエンド未実装（{name}）"
            )
            return out
        opts.progress(f"{case['id']} run {i}/{runs} / {i}/{runs} 回目: {results[-1]['status']}")
    out["results"] = results
    return out


def _timeout(case: Mapping[str, Json], opts: Options) -> float:
    if opts.timeout_s is not None:
        return opts.timeout_s
    long = case.get("mode") == "voice" or "persona" in case.get("setup", {})
    return TIMEOUT_LONG_S if long else TIMEOUT_TEXT_S


def _run_with_retry(api: EvalApi, case: Mapping[str, Json], world: WorldIndex, opts: Options, i: int) -> RunResult:
    for _ in range(opts.timeout_retries + 1):
        try:
            with time_limit(_timeout(case, opts)):
                return run_once(api, case, world, opts, i)
        except RunTimeout:
            opts.progress(f"{case['id']} run {i} timed out / {i} 回目がタイムアウト")
    return {"run": i, "status": "skip", "checks": [], "skip": {"code": "timeout"}, "traceIds": []}


def run_once(api: EvalApi, case: Mapping[str, Json], world: WorldIndex, opts: Options, i: int) -> RunResult:
    sessions: list[EvalSession] = []

    class ClosingApi:
        def setup(self, setup: Mapping[str, Json], *, mode: Literal["text", "voice"] = "text") -> EvalSession:
            session = api.setup(setup, mode=mode)
            sessions.append(session)
            return session

    try:
        return _run_once(ClosingApi(), case, world, opts, i)
    finally:
        for session in sessions:
            close = getattr(session, "close", None)
            if close is not None:
                close()


def _run_once(api: EvalApi, case: Mapping[str, Json], world: WorldIndex, opts: Options, i: int) -> RunResult:
    results: list[StepResult] = []
    played: Played | None = None
    try:
        session = api.setup(case["setup"], mode=case.get("mode", "text"))
        setup_events = _setup_events(session)
        if "persona" in case["setup"]:
            # Simulated game: the AI player walks step by step in the runner according to the persona (the backend
            # uses persona and seed only to set the role, the starting point and the fake model's seed).
            # シミュレーション局：AI プレイヤーはランナー内でペルソナに従って一歩ずつ進む（バックエンドは persona、
            # seed でロール、開始点、偽モデルのシードを決めるだけ）
            if opts.player is None:
                return {"run": i, "status": "skip", "checks": [], "skip": {"code": "needs-live-model"}, "traceIds": []}
            persona = opts.personas[case["setup"]["persona"]]
            played = play(session, persona, opts.player(case), progress=opts.progress, max_steps=opts.max_steps)
            results = played.results
        else:
            for step in case.get("steps", []):
                results.append(call_step(session, step))
    except Stop:
        # ledger at its cap, rate limit: stop the whole run (live) / 台帳が上限、レート制限：実行全体を止める（live）
        raise
    except Exception as e:
        name = not_implemented(e)
        if name is not None:
            raise _WholeCase({"code": "not-implemented", "name": name}) from e
        traces = [r["traceId"] for r in results if "traceId" in r]
        if replay_missing(e):
            return {"run": i, "status": "skip", "checks": [], "skip": {"code": "replay-missing"}, "traceIds": traces}
        return {"run": i, "status": "fail", "checks": [], "error": f"{type(e).__name__}: {e}", "traceIds": traces}

    ctx = RunContext(
        world=world,
        case=case,
        session=session,
        results=results,
        setup_events=setup_events,
        played=played.steps if played is not None else None,
    )
    expect = case.get("expect", {})
    checks = [run_check(ctx, n, spec) for n, spec in enumerate(expect.get("deterministic", []), 1)]
    out: RunResult = {"run": i, "status": "pass", "checks": checks, "traceIds": []}
    judge = None
    if "judge" in expect and not opts.deterministic_only:
        out["judge"] = judge = opts.judge(case, ctx)
    out["status"] = run_status(checks, judge)
    # a judge-only case run with deterministic checks only / 採点だけのケースを決定的チェックだけで実行した
    if not checks and judge is None:
        out["skip"] = {"code": "needs-live-model"}
    out["traceIds"] = [r["traceId"] for r in results if "traceId" in r]
    if played is not None:
        out["playthroughId"] = played.playthrough_id
        out["sim"] = sim_stats(played, _query(ctx, "events"), _query(ctx, "ending"))
        diagnostics = getattr(session, "diagnostics", None)
        if diagnostics is not None:
            out["sim"]["backend"] = diagnostics()
    return out


def _query(ctx: RunContext, name: str) -> Any:
    """A query for statistics: None when the backend has not implemented it or the replay is missing; it does not
    affect this run's verdict.

    統計用のクエリ：バックエンド未実装やリプレイ欠落のときは None。この回の判定には影響しない。
    """
    try:
        return ctx.query(name)
    except Exception as e:
        if not_implemented(e) is not None or replay_missing(e):
            return None
        raise


def _setup_events(session: EvalSession) -> list[Event] | None:
    """This game's events right after setup: world_unchanged uses them to compute the baseline scenario. None when
    the backend has not implemented events().

    setup 直後のこの局のイベント：world_unchanged はこれで元のシナリオを計算する。バックエンドが events() を未実装なら
    None。
    """
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
    "deleteMemoryId": ("delete_memory_id", lambda s: (s["deleteMemoryId"],)),
    "confirm": ("confirm", lambda s: (s["confirm"],)),
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
    result: StepResult = (
        fn(*args(step), action_id=step["act"]["actionId"])
        if method == "act" and "actionId" in step["act"]
        else fn(*args(step))
    )
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
            out["status"], out["reason"] = "fail", f"Error while checking / チェック中のエラー: {type(e).__name__}: {e}"
        return out
    if reason is not None:
        out["status"], out["reason"] = "fail", reason
    return out


@contextmanager
def time_limit(seconds: float) -> Iterator[None]:
    """Raise RunTimeout at the time limit. Works only in the main thread on systems with SIGALRM (Mac, Linux);
    seconds = 0 means no limit.

    時間制限で RunTimeout を投げる。メインスレッドかつ SIGALRM のあるシステム（Mac、Linux）でのみ有効。seconds = 0 は
    無制限。
    """
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
