"""S-2 的运行脚本（B-2 验收第 6 组的回放、第 7 组）：假模型跑公开的 10 条、接着跑、真模型的开关、回放。

假模型的检查全过，所以判不过的只有第 3 步拦住的：标成 `rules` 的 4 条判对，标成 `model` 的 2 条（s2d-02 的 R1、s2d-05 的
R5）漏判，合规的 4 条判对。下面的数按这个手算。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from zoujin_backend import eval_api, s2
from zoujin_backend.config import REPO

from .conftest import Env

Json = Any

DEV = REPO / "evals" / "s2" / "s2_dev.jsonl"


def run(monkeypatch: pytest.MonkeyPatch, env: Env, out: Path, *extra: str, runs: int = 3) -> int:
    monkeypatch.setenv("DATABASE_URL", env.url)
    return s2.main([str(DEV), "--out", str(out), "--runs", str(runs), *extra])


def report(out: Path) -> Json:
    return json.loads((out / "report.json").read_text(encoding="utf-8"))


@pytest.mark.db
def test_fake_model_on_the_public_ten(env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    watch = tmp_path / "watch.txt"
    watch.write_text("s2d-02\ns2d-07\n", encoding="utf-8")
    assert run(monkeypatch, env, tmp_path / "out", "--watch", str(watch)) == 0
    rep = report(tmp_path / "out")
    s = rep["summary"]
    assert rep["complete"] and s["items"] == 10 and s["violations"] == 6
    assert s["worstAgreement"] == pytest.approx(0.8) and s["majorityAgree"] == 8
    assert s["anchorMisses"] == [{"id": "s2d-02", "run": r} for r in (1, 2, 3)]
    assert s["gates"] == {"agreement": False, "anchorMisses": False} and s["unstable"] == []
    assert s["watched"] == {"watch": {"items": 2, "agreeMajority": 1}, "others": {"items": 8, "agreeMajority": 7}}
    for r in rep["runs"]:
        assert (r["agree"], r["falseRejects"], r["missed"]) == (8, [], ["s2d-02", "s2d-05"])
        assert r["missedByStage"] == {"model": 2} and (r["rulesAgree"], r["bothFail"]) == (4, 4)
    by_id = {x["id"]: x for x in rep["items"]}
    assert [x["failedRules"] for x in by_id["s2d-06"]["runs"]] == [["R7-capability"]] * 3
    assert all(x["traceId"].startswith("trc_") for x in by_id["s2d-01"]["runs"])
    assert rep["meta"]["checkPromptVersion"].startswith("p") and rep["meta"]["dataset"] == "s2_dev.jsonl"
    md = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert "| 一致率（最差的一次） | 80.0% |" in md and "s2d-02 第 1 次" in md
    for item in (json.loads(x) for x in DEV.read_text(encoding="utf-8").splitlines()):
        assert item["turn"]["player"] not in md and item["candidate"]["summary"] not in md  # 不抄原话和摘要


@pytest.mark.db
def test_resume_skips_what_is_done(env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    out = tmp_path / "out"
    assert run(monkeypatch, env, out, runs=1) == 0
    assert run(monkeypatch, env, out, runs=1) == s2.EXIT_CONFIG  # 已有结果，不加 --resume 不跑
    lines = (out / s2.RESULTS).read_text(encoding="utf-8").splitlines()
    (out / s2.RESULTS).write_text("\n".join(lines[:7]) + "\n", encoding="utf-8")  # 像是第 8 条时断了
    called: list[str] = []
    real = s2.check_one

    def counting(item: Json, *a: Any) -> Json:
        called.append(item["id"])
        return real(item, *a)

    monkeypatch.setattr(s2, "check_one", counting)
    assert run(monkeypatch, env, out, "--resume", runs=1) == 0
    assert called == ["s2d-08", "s2d-09", "s2d-10"]
    assert report(out)["complete"] and len((out / s2.RESULTS).read_text(encoding="utf-8").splitlines()) == 10
    assert run(monkeypatch, env, out, "--resume", runs=2) == s2.EXIT_CONFIG  # 次数变了不让接着跑


@pytest.mark.db
def test_budget_stop_still_writes_the_report(env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    real = s2.check_one
    n: list[int] = []

    def broke(item: Json, *a: Any) -> Json:
        n.append(1)
        if len(n) > 4:
            raise eval_api.BudgetStop("到上限了")
        return real(item, *a)

    monkeypatch.setattr(s2, "check_one", broke)
    assert run(monkeypatch, env, tmp_path / "out", runs=1) == s2.EXIT_STOP
    rep = report(tmp_path / "out")
    assert not rep["complete"] and rep["stopped"] == "BudgetStop" and rep["runs"][0]["done"] == 4


@pytest.mark.db
def test_replays_recorded_from_the_fake_give_the_same_report(
    env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """真模型的回放要等 Mac 第一次跑完才有；先用假模型录的回放测这条路（ZJ_RECORD_REPLAYS → ZJ_REPLAYS）。"""
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    monkeypatch.setenv("ZJ_RECORD_REPLAYS", str(tmp_path / "rec"))
    assert run(monkeypatch, env, tmp_path / "fake", runs=1) == 0
    monkeypatch.delenv("ZJ_RECORD_REPLAYS")
    monkeypatch.setenv("ZJ_MODEL", "replay")
    monkeypatch.setenv("ZJ_REPLAYS", str(tmp_path / "rec"))
    assert run(monkeypatch, env, tmp_path / "replay", runs=1) == 0

    def verdicts(out: Path) -> list[Json]:
        return [(x["id"], x["runs"][0]["status"], x["runs"][0]["failedRules"]) for x in report(out)["items"]]

    assert verdicts(tmp_path / "fake") == verdicts(tmp_path / "replay")
    monkeypatch.setenv("ZJ_REPLAYS", str(tmp_path / "empty"))
    (tmp_path / "empty").mkdir()
    assert run(monkeypatch, env, tmp_path / "missing", runs=1) == s2.EXIT_CONFIG  # 回放缺失：停下


@pytest.mark.parametrize(
    ("live", "args"),
    [
        (None, ["--max-item-usd", "0.5", "--max-google-usd", "30", "--confirm"]),  # 没设 ZJ_EVAL_LIVE
        ("1", ["--max-google-usd", "30", "--confirm"]),  # 少一个上限
        ("1", ["--max-item-usd", "0.5", "--max-google-usd", "30"]),  # 不带 --confirm
    ],
)
def test_live_gate_only_prints(
    live: str | None,
    args: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://nobody@127.0.0.1:1/none")
    monkeypatch.setenv("ZJ_MODEL", "real")
    monkeypatch.setenv("ZJ_LEDGER", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setenv("ZJ_VERTEX_PROJECT", "proj-marker-0000")
    monkeypatch.setenv("ZJ_VERTEX_LOCATION", "global")
    if live is None:
        monkeypatch.delenv("ZJ_EVAL_LIVE", raising=False)
    else:
        monkeypatch.setenv("ZJ_EVAL_LIVE", live)

    def never(*a: Any, **k: Any) -> None:
        raise AssertionError("不该起局、调用")

    monkeypatch.setattr(eval_api, "setup", never)
    assert s2.main([str(DEV), "--out", str(tmp_path / "out"), *args]) == 0
    printed = capsys.readouterr().out
    assert "预计花费" in printed and "只打印，不调用" in printed and "zoujin-s2" in printed
    assert "proj-marker-0000" not in printed  # 只打印变量名
    assert not (tmp_path / "out").exists() and not (tmp_path / "ledger.jsonl").exists()
