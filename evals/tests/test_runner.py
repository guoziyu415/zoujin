"""Running cases: whole-case skips, query skips, missing replays, backend errors, timeouts, judging, and running the
100 cases on the simulation-only stand-in.

ケースの実行：ケースまるごとのスキップ、クエリのスキップ、リプレイの欠落、バックエンドのエラー、タイムアウト、採点、
そしてシミュレーションだけの代役で 100 例を実行すること。
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from zoujin_evals import CaseResult, Options, WorldIndex, run_case, run_cases
from zoujin_evals.api import EvalNotImplemented, EvalSession, StepResult
from zoujin_evals.cases import load_cases
from zoujin_evals.runner import RunTimeout, time_limit, validate

CASES = load_cases(Path(__file__).resolve().parents[1] / "seeds")
BY_ID = {c["id"]: c for c in CASES}
FAST = Options(deterministic_only=True, timeout_s=0)


class ReplayMissing(Exception):
    """An exception with the same name as B-0's: the runner recognises it by class name.

    B-0 と同名の例外：ランナーはクラス名で認識する。
    """


class Session:
    def __init__(self, behaviour: str) -> None:
        self.behaviour = behaviour
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def say(self, to: str, text: str) -> StepResult:
        match self.behaviour:
            case "replay":
                raise ReplayMissing("prompt v2")
            case "crash":
                raise KeyError("turn")
            case "slow":
                time.sleep(0.5)
        return {"reply": "……そうか。", "events": [], "clockMinutes": 10, "traceId": "tr_1"}

    def state(self) -> dict[str, Any]:
        raise EvalNotImplemented("state")

    def events(self) -> list[dict[str, Any]]:
        return []


class Api:
    def __init__(self, behaviour: str = "ok", setup_raises: str | None = None) -> None:
        self.behaviour, self.setup_raises, self.calls = behaviour, setup_raises, 0

    def setup(self, setup: Mapping[str, Any], *, mode: str = "text") -> EvalSession:
        self.calls += 1
        if self.setup_raises:
            raise EvalNotImplemented(self.setup_raises)
        return Session(self.behaviour)  # type: ignore[return-value]


def one(case_id: str, api: Any, world_ix: WorldIndex, opts: Options = FAST) -> CaseResult:
    return run_case(api, BY_ID[case_id], world_ix, opts)


def test_no_backend_skips_every_case(world_ix: WorldIndex) -> None:
    got = run_cases(None, CASES, world_ix, FAST)
    assert len(got) == 100
    assert all(c.get("skip") == {"code": "not-implemented", "name": "eval_api"} for c in got)


@pytest.mark.parametrize("behaviour", ["ok", "crash", "replay", "slow"])
def test_sessions_close_even_after_failure_or_timeout(behaviour: str, world_ix: WorldIndex) -> None:
    sessions: list[Session] = []

    class ClosingApi(Api):
        def setup(self, setup: Mapping[str, Any], *, mode: str = "text") -> EvalSession:
            session = Session(behaviour)
            sessions.append(session)
            return session  # type: ignore[return-value]

    case = {**BY_ID["E2-009"], "runs": 1}
    run_case(ClosingApi(), case, world_ix, Options(deterministic_only=True, timeout_s=0.05, timeout_retries=0))
    assert len(sessions) == 1 and sessions[0].closed


def test_setup_not_implemented_skips_whole_case_once(world_ix: WorldIndex) -> None:
    api = Api(setup_raises="persona")
    got = one("E7-001", api, world_ix)
    assert got["skip"] == {"code": "not-implemented", "name": "persona"}
    assert "results" not in got and api.calls == 1


def test_simulated_run_needs_the_ai_player(world_ix: WorldIndex) -> None:
    """Once the backend accepts a persona setup, the AI player lives in the runner and needs a real model: each run
    records "needs a real model", which is not a whole-case skip.

    バックエンドが persona の setup を受け付けると、AI プレイヤーはランナー内にあり実モデルが必要：各回は「実モデルが
    必要」と記録し、ケースまるごとのスキップにはしない。
    """
    got = one("E7-001", Api(), world_ix)
    assert "skip" not in got
    assert [r["skip"] for r in got["results"]] == [{"code": "needs-live-model"}] * got["runs"]


def test_step_not_implemented_skips_whole_case(world_ix: WorldIndex) -> None:
    # step 2 is deleteMemory, and the session has no delete_memory
    # ステップ 2 は deleteMemory で、セッションに delete_memory がない
    got = one("E6-005", Api(), world_ix)
    assert got["skip"] == {"code": "not-implemented", "name": "delete_memory"}


def test_query_not_implemented_skips_only_that_check(world_ix: WorldIndex) -> None:
    # not_mention_fact looks only at the reply / not_mention_fact は返答だけを見る
    got = one("E2-009", Api(), world_ix)
    assert [r["status"] for r in got["results"]] == ["pass"] * 5
    # var needs state(); no_event looks only at this step's events
    # var は state() が必要、no_event はこのステップのイベントだけを見る
    got = one("E4-001", Api(), world_ix)
    checks = got["results"][0]["checks"]
    assert [c["status"] for c in checks] == ["skip", "pass"]
    assert checks[0]["skip"] == {"code": "not-implemented", "name": "state"}
    assert got["results"][0]["status"] == "skip"
    assert got["results"][0]["traceIds"] == ["tr_1"]


def test_replay_missing_and_backend_errors_are_per_run(world_ix: WorldIndex) -> None:
    got = one("E2-009", Api("replay"), world_ix)
    assert len(got["results"]) == 5
    assert all(r["status"] == "skip" and r["skip"] == {"code": "replay-missing"} for r in got["results"])
    got = one("E2-009", Api("crash"), world_ix)
    assert all(r["status"] == "fail" and r["error"] == "KeyError: 'turn'" for r in got["results"])


def test_timeout_retries_once(world_ix: WorldIndex) -> None:
    api = Api("slow")
    case = {**BY_ID["E2-009"], "runs": 1}
    got = run_case(api, case, world_ix, Options(deterministic_only=True, timeout_s=0.1))
    assert got["results"] == [{"run": 1, "status": "skip", "checks": [], "skip": {"code": "timeout"}, "traceIds": []}]
    assert api.calls == 2


def test_time_limit() -> None:
    with pytest.raises(RunTimeout), time_limit(0.05):
        time.sleep(1)
    with time_limit(0):
        pass


def test_judge_recorded_unless_deterministic_only(world_ix: WorldIndex) -> None:
    got = one("E2-009", Api(), world_ix, Options(timeout_s=0))
    r = got["results"][0]
    assert r["judge"] == {"index": 0, "type": "judge", "status": "skip", "skip": {"code": "needs-live-model"}}
    assert (
        r["status"] == "skip"
    )  # judging skipped, so this run is not a pass / 採点がスキップされ、この回は合格にならない
    assert "judge" not in one("E2-009", Api(), world_ix)["results"][0]


def test_judge_only_case_is_skipped_when_deterministic_only(world_ix: WorldIndex) -> None:
    case = BY_ID["E2-009"]
    judge_only = {**case, "expect": {"judge": case["expect"]["judge"]}}
    got = run_case(Api(), judge_only, world_ix, FAST)
    assert got["results"][0]["status"] == "skip"
    assert got["results"][0]["skip"] == {"code": "needs-live-model"}


def test_unknown_check_or_step_is_an_error(world_ix: WorldIndex) -> None:
    bad = {**BY_ID["E2-009"], "expect": {"deterministic": [{"type": "vibes"}]}}
    assert validate([bad]) == ["E2-009: unknown check vibes / 不明なチェック vibes"]
    with pytest.raises(ValueError, match="vibes"):
        run_cases(Api(), [bad], world_ix, FAST)
    assert validate([{**BY_ID["E2-009"], "steps": [{"dance": True}]}]) == [
        "E2-009: Unknown step ['dance'] / 不明なステップ ['dance']"
    ]


def test_all_seeds_on_the_sim_only_backend(world_ix: WorldIndex, sim_api: Any) -> None:
    """Run the 100 cases on the stand-in that only simulates with W-1 (the same steps as B-0's minimal version):
    - 30 cases skipped entirely: 12 simulated games (the 11 cases of E7 and E5-001), 18 cases with steps B-0 has not
      implemented (E-0 card item 1);
    - the checks that simulation alone can judge all pass: the 12 scenario cases of E5 and the beat, var, outcome of
      E5-006;
    - nothing crashes, and no deterministic check fails because of a runner error.

    W-1 のシミュレーションだけを使う代役（B-0 の最小版と同じステップ）で 100 例を実行する：
    - ケースまるごとのスキップは 30 例：シミュレーション局 12（E7 の 11 例と E5-001）、B-0 が未実装のステップを含む
      18 例（E-0 カード第 1 条）。
    - シミュレーションだけで判定できるチェックはすべて合格：E5 の 12 個の scenario ケースと E5-006 の beat、var、
      outcome。
    - クラッシュせず、ランナーのエラーで不合格になった決定的チェックがない。
    """
    got = run_cases(sim_api, CASES, world_ix, FAST)
    skipped = Counter(c["skip"].get("name") for c in got if "skip" in c)
    assert skipped == {
        "persona": 12,
        "act": 8,
        "delete_memory": 5,
        "propose": 2,
        "silence": 1,
        "new_playthrough": 1,
        "delete_playthrough": 1,
    }
    sim_cases = [c for c in CASES if "scenario" in c["setup"]] + [BY_ID["E5-006"]]
    assert len(sim_cases) == 13
    for c in sim_cases:
        res = next(r for r in got if r["id"] == c["id"])
        for run in res["results"]:
            assert run["status"] == "pass", (c["id"], run)
    for res in got:
        for run in res.get("results", []):
            assert "error" not in run
            for ck in run["checks"]:
                assert not ck.get("reason", "").startswith("Error while checking"), (res["id"], ck)
