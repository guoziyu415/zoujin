"""S-2 runner script (B-2 acceptance check group 6's replays, group 7): the fake model on the public 10 items,
resuming, the real-model switch, replays.

The fake model's check passes everything, so the only fails are those stopped in step 3: the 4 items labelled `rules`
are judged correctly, the 2 labelled `model` (s2d-02's R1, s2d-05's R5) are missed, and the 4 compliant ones are judged
correctly. The numbers below are worked out by hand from this.

S-2 の実行スクリプト（B-2 受け入れ確認 第 6 組のリプレイ、第 7 組）：偽モデルで公開の 10 件、続きからの実行、
本物のモデルのスイッチ、リプレイ。

偽モデルのチェックはすべて合格なので、不合格になるのは第 3 段階で止めたものだけ：`rules` とラベルした 4 件は正しく
判定し、`model` とラベルした 2 件（s2d-02 の R1、s2d-05 の R5）は見逃し、適合の 4 件は正しく判定する。
下の数字はこれをもとに手で計算した。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from zoujin_backend import eval_api, s2
from zoujin_backend.config import REPO
from zoujin_backend.models.prompts import PROMPTS

from .conftest import Env

Json = Any

DEV = REPO / "evals" / "s2" / "s2_dev.jsonl"
KEY = "sk-ant-test-marker-0000"  # Fake; checked that it is never printed / 偽物。表示されないことを確認する


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
    assert rep["meta"]["checkPromptFinal"] is True
    md = (tmp_path / "out" / "report.md").read_text(encoding="utf-8")
    assert "| Agreement (worst run) / 一致率（最も低い回） | 80.0% |" in md and "s2d-02 run 1" in md
    assert f"`{s2.CHECK_FINAL}` (final / 確定版)" in md
    for item in (json.loads(x) for x in DEV.read_text(encoding="utf-8").splitlines()):
        # Original words and summaries are not copied / 発話の原文と要約は写さない
        assert item["turn"]["player"] not in md and item["candidate"]["summary"] not in md


@pytest.mark.db
def test_resume_skips_what_is_done(env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    out = tmp_path / "out"
    assert run(monkeypatch, env, out, runs=1) == 0
    # Results exist: without --resume it does not run / 結果があるので --resume なしでは実行しない
    assert run(monkeypatch, env, out, runs=1) == s2.EXIT_CONFIG
    lines = (out / s2.RESULTS).read_text(encoding="utf-8").splitlines()
    # As if it broke off at item 8 / 8 件目で途切れたかのように
    (out / s2.RESULTS).write_text("\n".join(lines[:7]) + "\n", encoding="utf-8")
    called: list[str] = []
    real = s2.check_one

    def counting(item: Json, *a: Any) -> Json:
        called.append(item["id"])
        return real(item, *a)

    monkeypatch.setattr(s2, "check_one", counting)
    assert run(monkeypatch, env, out, "--resume", runs=1) == 0
    assert called == ["s2d-08", "s2d-09", "s2d-10"]
    assert report(out)["complete"] and len((out / s2.RESULTS).read_text(encoding="utf-8").splitlines()) == 10
    # The number of runs changed: resuming is refused / 回数が変わったので続きからは実行させない
    assert run(monkeypatch, env, out, "--resume", runs=2) == s2.EXIT_CONFIG


@pytest.mark.db
def test_budget_stop_still_writes_the_report(env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ZJ_MODEL", raising=False)
    real = s2.check_one
    n: list[int] = []

    def broke(item: Json, *a: Any) -> Json:
        n.append(1)
        if len(n) > 4:
            raise eval_api.BudgetStop("Cap reached / 上限に達した")
        return real(item, *a)

    monkeypatch.setattr(s2, "check_one", broke)
    assert run(monkeypatch, env, tmp_path / "out", runs=1) == s2.EXIT_STOP
    rep = report(tmp_path / "out")
    assert not rep["complete"] and rep["stopped"] == "BudgetStop" and rep["runs"][0]["done"] == 4


@pytest.mark.db
def test_replays_recorded_from_the_fake_give_the_same_report(
    env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Real-model replays only exist after the first run on the Mac; until then test this path with replays recorded
    from the fake model (ZJ_RECORD_REPLAYS → ZJ_REPLAYS).

    本物のモデルのリプレイは Mac で最初の実行が終わるまでない。それまでは偽モデルで録ったリプレイでこの経路をテストする
    （ZJ_RECORD_REPLAYS → ZJ_REPLAYS）。
    """
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
    # Missing replay: stop / リプレイがない：止まる
    assert run(monkeypatch, env, tmp_path / "missing", runs=1) == s2.EXIT_CONFIG


def live_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://nobody@127.0.0.1:1/none")
    monkeypatch.setenv("ZJ_MODEL", "real")
    monkeypatch.setenv("ZJ_LEDGER", str(tmp_path / "ledger.jsonl"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.setenv("ZJ_CLAUDE_HAIKU", "test-haiku-5-5-marker")
    monkeypatch.setenv("ZJ_CLAUDE_SONNET", "test-sonnet-5-5-marker")


def never(*a: Any, **k: Any) -> None:
    raise AssertionError("Must not start a playthrough or call / プレイの開始や呼び出しをしてはならない")


@pytest.mark.parametrize(
    ("live", "args"),
    [
        (None, ["--max-item-usd", "0.5", "--max-claude-usd", "30", "--confirm"]),  # No ZJ_EVAL_LIVE / 未設定
        ("1", ["--max-claude-usd", "30", "--confirm"]),  # One cap missing / 上限が 1 つない
        ("1", ["--max-item-usd", "0.5", "--max-claude-usd", "30"]),  # No --confirm / --confirm なし
        # The key was not read into the environment / キーを環境に読み込んでいない
        ("no-key", ["--max-item-usd", "0.5", "--max-claude-usd", "30", "--confirm"]),
    ],
)
def test_live_gate_only_prints(
    live: str | None,
    args: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    live_env(monkeypatch, tmp_path)
    if live is None:
        monkeypatch.delenv("ZJ_EVAL_LIVE", raising=False)
    elif live == "no-key":
        monkeypatch.setenv("ZJ_EVAL_LIVE", "1")
        monkeypatch.delenv("ANTHROPIC_API_KEY")
    else:
        monkeypatch.setenv("ZJ_EVAL_LIVE", live)
    monkeypatch.setattr(eval_api, "setup", never)
    assert s2.main([str(DEV), "--out", str(tmp_path / "out"), *args]) == 0
    printed = capsys.readouterr().out
    assert "Estimated cost" in printed and "Printing only, no calls" in printed and "zoujin-s2" in printed
    # Only variable names are printed, never the key or model IDs / 変数名だけを表示し、キーとモデル ID は表示しない
    assert KEY not in printed and "marker" not in printed
    assert "sonnet-5.5" in printed  # Tier name plus version is fine / ティア名とバージョンはよい
    assert not (tmp_path / "out").exists() and not (tmp_path / "ledger.jsonl").exists()


def test_check_prompt_is_the_final_one() -> None:
    # If the check text or Schema changes after it is final, the S-2 results no longer represent the new prompt: data
    # must produce a new measurement set before s2.CHECK_FINAL is changed (card B-2)
    # 確定後に check のテキストか Schema を変えると、S-2 の結果は新しいプロンプトを表さなくなる：
    # データ担当が新しい測定セットを作ってから s2.CHECK_FINAL を変える（B-2 カード）
    assert PROMPTS["check"].version == s2.CHECK_FINAL


def test_live_runs_other_sets_only_with_the_final_check_prompt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    live_env(monkeypatch, tmp_path)
    monkeypatch.setenv("ZJ_EVAL_LIVE", "1")
    monkeypatch.setattr(eval_api, "setup", never)
    # Pretend the prompt changed after it was final / 確定後にプロンプトが変わったことにする
    monkeypatch.setattr(s2, "CHECK_FINAL", "p000000000000")
    other = tmp_path / "s2_other.jsonl"
    other.write_bytes(DEV.read_bytes())
    caps = ["--max-item-usd", "0.5", "--max-claude-usd", "30"]
    assert s2.main([str(other), "--out", str(tmp_path / "out"), *caps, "--confirm"]) == s2.EXIT_CONFIG
    got = capsys.readouterr()
    assert "is not the final p000000000000" in got.err and "Estimated cost" not in got.out
    # The public 10 items can still be used to tune the prompt / 公開の 10 件ではこれまでどおりプロンプトを調整できる
    assert s2.main([str(DEV), "--out", str(tmp_path / "out"), *caps]) == 0
    assert "Estimated cost" in capsys.readouterr().out
    assert not (tmp_path / "out").exists() and not (tmp_path / "ledger.jsonl").exists()
