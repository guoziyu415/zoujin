"""命令行：CI 用的 --mode fake --deterministic-only 和预期快照逐字段相同（E-0 卡第 6 条）。

B-0 或假模型改了输出，快照要在同一个 PR 里更新（要测试库，见 services/backend/README.md）：
    DATABASE_URL=… uv run zoujin-eval --mode fake --deterministic-only --quiet --out evals/tests/snapshots/fake
评审时看 report.json 的差异。trace ID 和不过的原因里的事件 ID 每次不一样，比的时候去掉。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
from zoujin_evals.cli import main

REPO = Path(__file__).resolve().parents[2]
SNAPSHOT = Path(__file__).resolve().parent / "snapshots" / "fake"
ARGS = ["--world", str(REPO / "worlds/hashire-merosu/1.0.0-draft/world.json"), "--cases", str(REPO / "evals/seeds")]


EVENT_ID = re.compile(r"ev_[0-9A-HJKMNP-TV-Z]{26}")  # 不过的原因里列出的事件 ID（B-13 起 E6 真跑到这里）每次不一样


def ids_masked(s: str) -> str:
    return EVENT_ID.sub("ev_…", s)


def without_traces(x: Any) -> Any:
    if isinstance(x, str):
        return ids_masked(x)
    if isinstance(x, dict):
        return {k: without_traces(v) for k, v in x.items() if k != "traceIds"}
    if isinstance(x, list):
        return [without_traces(v) for v in x]
    return x


@pytest.mark.db  # 后端的评测入口每局写测试库（B-0）；没有 DATABASE_URL 时跳过
def test_fake_deterministic_matches_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    assert main(["--mode", "fake", "--deterministic-only", "--quiet", "--out", str(tmp_path), *ARGS]) == 0
    got = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    want = json.loads((SNAPSHOT / "report.json").read_text(encoding="utf-8"))
    assert without_traces(got) == without_traces(want)
    got_md, want_md = ((d / "report.md").read_text(encoding="utf-8") for d in (tmp_path, SNAPSHOT))
    assert ids_masked(got_md) == ids_masked(want_md)
    assert got["meta"]["cases"] == 100 and len(got["cases"]) == 100


def test_filters(tmp_path: Path) -> None:
    assert main(["--suite", "E5", "--case", "E5-002", "--quiet", "--out", str(tmp_path), *ARGS]) == 0
    got = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in got["cases"]] == ["E5-002"]


def test_slice_runs_the_slice_cases_on_the_slice_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO)
    monkeypatch.delenv("ZJ_WORLD", raising=False)
    assert main(["--slice", "--deterministic-only", "--quiet", "--out", str(tmp_path)]) == 0
    got = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    ids = [json.loads(line)["id"] for f in sorted((REPO / "evals/slice").glob("E*.jsonl")) for line in f.open()]
    assert "1.0.0-slice" in got["meta"]["worldModelVersion"]
    assert sorted(c["id"] for c in got["cases"]) == sorted(ids)
    assert os.environ["ZJ_WORLD"] == str(REPO / "worlds/hashire-merosu/1.0.0-slice/world.json")  # 绝对路径


LIVE = ["--mode", "live", "--max-item-usd", "1", "--max-google-usd", "30", "--max-claude-usd", "10"]


def test_live_exits(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("ZJ_EVAL_LIVE", raising=False)
    assert main([*LIVE, *ARGS]) == 2
    assert "ZJ_EVAL_LIVE" in capsys.readouterr().err
    monkeypatch.setenv("ZJ_EVAL_LIVE", "1")
    assert main(["--mode", "live", "--max-item-usd", "1", "--max-google-usd", "30", *ARGS]) == 2
    assert main([*LIVE, *ARGS]) == 0
    out = capsys.readouterr().out
    assert "--confirm" in out and "Claude" in out


def test_live_failed_result_has_nonzero_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from zoujin_evals import cli

    monkeypatch.setenv("ZJ_EVAL_LIVE", "1")
    monkeypatch.setenv("ZJ_LEDGER", str(tmp_path / "unused.jsonl"))
    monkeypatch.setattr(cli, "players", lambda args: None)
    monkeypatch.setattr(
        cli,
        "run_cases",
        lambda *args: [
            {
                "id": "E2-009",
                "suite": "E2",
                "title": "failure",
                "mode": "text",
                "runs": 1,
                "results": [
                    {"run": 1, "status": "fail", "checks": [], "traceIds": [], "error": "offline test failure"}
                ],
            }
        ],
    )
    assert (
        main(
            [
                *LIVE,
                *ARGS,
                "--case",
                "E2-009",
                "--confirm",
                "--deterministic-only",
                "--item",
                "unit-test",
                "--out",
                str(tmp_path),
            ]
        )
        == 1
    )
    result = json.loads((tmp_path / "report.json").read_text())
    assert result["meta"]["expectedJudgeRuns"] == {"E2-009": 5}
