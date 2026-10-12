"""200 局固定分母、逐局留证、有限预算和续跑不会重复付费。"""

import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from zoujin_evals import batch
from zoujin_evals.cases import load_cases


def test_plan_preserves_original_ten_personas_and_twenty_seeds() -> None:
    cases = batch.plan("simulations", 20)
    assert len(cases) == len({c["id"] for c in cases}) == 200
    assert set(Counter(c["setup"]["persona"] for c in cases).values()) == {20}
    assert set(Counter(c["setup"]["seed"] for c in cases).values()) == {10}
    assert all(c["runs"] == 1 and "melos-helper" not in c["setup"]["persona"] for c in cases)
    assert len(batch.plan("simulations", 2)) == 20
    assert len(batch.plan("four-act", 2)) == 980
    with pytest.raises(ValueError, match="1–20"):
        batch.plan("simulations", 21)


def test_late_checkpoints_explicitly_set_act_and_simulations_do_not() -> None:
    cases = load_cases(batch.REPO / "evals/seeds")
    late = next(c for c in cases if c["id"] == "E2-009")
    assert any(
        e.get("var") == "var.act.current" and e["value"] == "act.4"
        for item in late["setup"]["events"]
        for e in item["effects"]
    )
    for act in range(2, 5):
        for case in load_cases(batch.REPO / f"evals/acts/act{act}"):
            if "persona" in case["setup"]:
                assert "events" not in case["setup"]
            else:
                assert case["setup"]["events"][0]["effects"] == [
                    {"op": "set", "var": "var.act.current", "value": f"act.{act}"}
                ]


def test_incomplete_simulation_and_provider_failure_cannot_look_successful() -> None:
    case = batch.plan("simulations", 1)[0]
    run: dict[str, Any] = {"status": "pass", "sim": {"status": "active", "stopped": "max-steps"}}
    issues = batch.strict_result(case, {"results": [run]}, [])
    assert "incomplete-ending" in issues and "no-real-player-call" in issues
    run["sim"] = {"status": "ended", "ending": {"signature": "one"}, "player": {"bad": 1}}
    issues = batch.strict_result(case, {"results": [run]}, [{"kind": "player", "costUsd": 0.01, "status": "timeout"}])
    assert "player-fallback-or-replay" in issues and "provider-degradation" in issues


def test_completed_units_resume_without_relaunching(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZJ_EVAL_LIVE", "1")
    monkeypatch.setenv("ZJ_PLAYER_MODEL", "not-called")
    monkeypatch.setenv("ZJ_LEDGER", str(tmp_path / "unused.jsonl"))
    monkeypatch.setattr(batch, "source_hash", lambda: "test-code")
    monkeypatch.setattr(batch, "runtime_config", lambda: {"test": True})
    calls = []

    def run(argv: list[str], **kwargs: Any) -> Any:
        path = Path(argv[-1])
        calls.append(path)
        job = json.loads(path.read_text())
        result = {k: job["case"][k] for k in ("id", "suite", "title", "mode", "runs")}
        result["results"] = [{"run": 1, "status": "pass", "checks": [], "traceIds": []}]
        batch.save(
            path.parent / "result.json",
            {"status": "completed", "result": result, "costUsd": {"google": 0.1, "claude": 0.1}, "issues": []},
        )
        return type("Completed", (), {"returncode": 0})()

    monkeypatch.setattr(subprocess, "run", run)
    args = ["--seeds", "1", "--out", str(tmp_path), "--confirm"]
    assert batch.main(args) == 0
    assert len(calls) == 10
    assert batch.main(args) == 0
    assert len(calls) == 10
    monkeypatch.setattr(batch, "source_hash", lambda: "different-code")
    with pytest.raises(SystemExit, match="旧批次不能"):
        batch.main(args)


def test_interrupted_unit_is_not_automatically_replayed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZJ_EVAL_LIVE", "1")
    monkeypatch.setenv("ZJ_PLAYER_MODEL", "not-called")
    monkeypatch.setenv("ZJ_LEDGER", str(tmp_path / "unused.jsonl"))
    monkeypatch.setattr(batch, "runtime_config", lambda: {"test": True})
    batch.save(tmp_path / "units/E7-001-seed-01/started.json", {"pid": -1})
    with pytest.raises(SystemExit, match="禁止自动重复付费"):
        batch.main(["--seeds", "1", "--out", str(tmp_path), "--confirm"])
