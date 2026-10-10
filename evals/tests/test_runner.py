"""跑用例：整例跳过、查询跳过、回放缺失、后端报错、超时、判分，以及用只推演的替身跑 100 例。"""

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
    """和 B-0 同名的异常：运行器按类名认。"""


class Session:
    def __init__(self, behaviour: str) -> None:
        self.behaviour = behaviour

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


def test_setup_not_implemented_skips_whole_case_once(world_ix: WorldIndex) -> None:
    api = Api(setup_raises="persona")
    got = one("E7-001", api, world_ix)
    assert got["skip"] == {"code": "not-implemented", "name": "persona"}
    assert "results" not in got and api.calls == 1


def test_step_not_implemented_skips_whole_case(world_ix: WorldIndex) -> None:
    got = one("E6-005", Api(), world_ix)  # 第 2 步 deleteMemory，会话上没有 delete_memory
    assert got["skip"] == {"code": "not-implemented", "name": "delete_memory"}


def test_query_not_implemented_skips_only_that_check(world_ix: WorldIndex) -> None:
    got = one("E2-009", Api(), world_ix)  # not_mention_fact 只看回答
    assert [r["status"] for r in got["results"]] == ["pass"] * 5
    got = one("E4-001", Api(), world_ix)  # var 要 state()，no_event 只看这一步的事件
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
    assert r["status"] == "skip"  # 判分跳过，这一次不算过
    assert "judge" not in one("E2-009", Api(), world_ix)["results"][0]


def test_judge_only_case_is_skipped_when_deterministic_only(world_ix: WorldIndex) -> None:
    case = BY_ID["E2-009"]
    judge_only = {**case, "expect": {"judge": case["expect"]["judge"]}}
    got = run_case(Api(), judge_only, world_ix, FAST)
    assert got["results"][0]["status"] == "skip"
    assert got["results"][0]["skip"] == {"code": "needs-live-model"}


def test_unknown_check_or_step_is_an_error(world_ix: WorldIndex) -> None:
    bad = {**BY_ID["E2-009"], "expect": {"deterministic": [{"type": "vibes"}]}}
    assert validate([bad]) == ["E2-009：不认识的检查 vibes"]
    with pytest.raises(ValueError, match="vibes"):
        run_cases(Api(), [bad], world_ix, FAST)
    assert validate([{**BY_ID["E2-009"], "steps": [{"dance": True}]}]) == ["E2-009：不认识的步骤 ['dance']"]


def test_all_seeds_on_the_sim_only_backend(world_ix: WorldIndex, sim_api: Any) -> None:
    """只用 W-1 推演的替身（和 B-0 最小版做的步骤一样）跑 100 例：
    - 整例跳过 30 例：模拟局 12（E7 的 11 例和 E5-001）、带 B-0 没做的步骤的 18 例（E-0 卡第 1 条）；
    - 只靠推演就能判的检查全过：E5 的 12 个 scenario 用例和 E5-006 的 beat、var、outcome；
    - 不崩，确定性检查没有因为运行器出错的。"""
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
                assert not ck.get("reason", "").startswith("检查时出错"), (res["id"], ck)
