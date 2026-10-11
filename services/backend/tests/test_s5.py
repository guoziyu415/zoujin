"""zoujin-s5（B-5 验收第 7 组）：用造出来的账本和测试库跑，数字和手算的一样；不算 reply 和 use: "eval"；老行没有
ms 时写「没有数据」；账本和 playthrough_metrics 对不上时标出来。"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from zoujin_backend import eval_api, s5

from .conftest import OLD, PLAYER_LINE, Env

Json = Any

T0 = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)


def at(seconds: float) -> str:
    return (T0 + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def row(pid: str | None, kind: str, cost: float, t: float, **kw: Any) -> Json:
    out: Json = {"at": at(t), "provider": "claude", "kind": kind, "costUsd": cost, "use": "product", "item": "s5"}
    if pid:
        out["playthroughId"] = pid
    return out | kw


def talks(*starts: float) -> list[Json]:
    return [{"created_at": T0 + timedelta(seconds=x), "kind": "talk", "status": "done"} for x in starts]


STEPS = [{"kind": "say", "elapsedMs": 900}, {"kind": "say", "elapsedMs": 1100}, {"kind": "act", "elapsedMs": 300}]
RUNS = [
    {"playthroughId": "pt_a", "case": "S5-01", "persona": "persona.canon-follower", "seed": 1, "steps": STEPS},
    {"playthroughId": "pt_b", "case": "S5-02", "persona": "persona.idle", "seed": 2, "steps": []},
]
ROWS = [
    row("pt_a", "triage", 0.001, 1, ms=400, status="ok", usage={"inputTokens": 1000}),
    row("pt_a", "extract", 0.02, 2, ms=3000, status="ok", usage={"inputTokens": 1500, "cacheReadTokens": 17000}),
    row("pt_a", "check", 0.04, 3, ms=9000, status="ok", usage={"inputTokens": 2000, "cacheReadTokens": 17000}),
    row("pt_a", "reply", 0.5, 3, provider="google"),  # 替 Live 当人物：不算
    row("pt_a", "triage", 0.001, 11, ms=500, status="ok"),
    row("pt_a", "extract", 0.03, 12, ms=16000, status="ok"),  # 超过 15 秒的时限
    row("pt_a", "extract", 0.025, 13, ms=15001, status="timeout"),
    row("pt_a", "check", 0.05, 14, ms=8000, status="ok"),
    row("pt_a", "ending", 0.12, 30, ms=20000, status="ok"),  # 一局一次，不按轮
    row("pt_a", "player", 0.3, 5, use="eval"),  # AI 玩家：单列
    row("pt_b", "triage", 0.001, 101),  # 老行：没有 ms、status
    row("pt_b", "narrate", 0.01, 102),
    row(None, "judge", 1.0, 200, use="eval"),  # 不在这几局里
]
METRICS = {
    "pt_a": {
        "cost_triage_usd": 0.002,
        "cost_extract_usd": 0.075,
        "cost_check_usd": 0.09,
        "turns": 2,
        "actions": 1,
        "ending_template": False,
        "ending_calls": 2,
    },
    "pt_b": {
        "cost_triage_usd": 0.001,
        "cost_narrate_usd": 0.02,
        "turns": 1,
        "ending_template": True,
    },  # 叙事 0.01 vs 0.02：对不上
}
TALKS = {"pt_a": talks(0, 10), "pt_b": talks(100)}


def test_hand_computed_report() -> None:
    r = s5.report(ROWS, RUNS, METRICS, TALKS, {})
    a, b = r["playthroughs"]
    assert a["costByKind"] == {"check": 0.09, "ending": 0.12, "extract": 0.075, "triage": 0.002}
    assert a["narratorUsd"] == pytest.approx(0.287) and a["turns"] == 2
    assert a["liveUsd"] == pytest.approx(s5.LIVE.turn(0) + s5.LIVE.turn(1), abs=1e-6)
    assert a["evalUsd"] == pytest.approx(0.3)  # 单列，不算进单局
    assert a["metricsMismatch"] == {} and b["metricsMismatch"] == {"narrate": {"ledger": 0.01, "metrics": 0.02}}
    assert a["counts"] == {"turns": 2, "actions": 1, "ending_template": 0, "ending_calls": 2}  # B-9 的布尔记 1 / 0
    assert b["counts"]["ending_template"] == 1 and r["endingsTemplated"] == 1
    # 每轮：pt_a 第 1 轮 0.061、第 2 轮 0.106（ending 不算），pt_b 第 1 轮 0.011
    t = r["perTurn"]
    assert t["points"] == 3 and t["mean"] == pytest.approx((0.061 + 0.106 + 0.011) / 3)
    assert t["rising"] and t["slope"] == pytest.approx(0.07)  # 点 (1, .061) (2, .106) (1, .011) 的最小二乘
    # 换算：叙事者按趋势外推、种类按实测的比例分；世界推进单列；切片里有结局就用实测的（一局 0.12）
    forty = r["scaled"]["40"]
    narr = s5.narrator_cost(t, 40)
    assert sum(forty["narrator"].values()) == pytest.approx(narr, rel=1e-4)
    assert forty["world"] == pytest.approx(0.31 / 12 * (7 + 40 / 8), rel=1e-4)
    assert forty["ending"] == pytest.approx(0.12) and forty["live"] == pytest.approx(s5.LIVE.cost(40), rel=1e-4)
    assert sum(forty["share"].values()) == pytest.approx(1.0 - 0.12 / forty["totalUsd"], abs=1e-3)
    # Q-B8「减少世界推进」：世界推进减半时的合计（PM #117）
    assert forty["worldCutUsd"] == pytest.approx(forty["totalUsd"] - forty["world"] / 2, abs=1e-5)
    stress = r["scaled"]["stress"]
    sixty = r["scaled"]["60"]
    # 实测 3 轮里检查 2 次；压力档每轮 2 次：检查那一份乘 2 ÷ (2/3) = 3，别的和 60 轮一样
    assert stress["narrator"]["check"] == pytest.approx(sixty["narrator"]["check"] * 3, rel=1e-4)
    assert stress["narrator"]["extract"] == sixty["narrator"]["extract"] and stress["totalUsd"] > sixty["totalUsd"]
    assert r["cacheRead"]["claude"] == pytest.approx(34000 / 38500, abs=1e-4) and r["cacheRead"]["google"] == "没有数据"
    assert r["eval"]["usd"] == pytest.approx(1.3)
    lat = r["latency"]
    assert lat["extract"]["calls"] == 3 and lat["extract"]["ms"]["max"] == 16000
    assert lat["extract"]["overDeadline"] == pytest.approx(2 / 3, abs=1e-4)  # 一次超时、一次超过 15 秒
    assert lat["extract"]["timeouts"] == 1 and "reply" not in lat
    assert lat["narrate"]["ms"] == "没有数据" and lat["narrate"]["overDeadline"] == "没有数据"  # 老行没有 ms
    assert r["deadlineAdvice"]["check"] == 11  # p99 9000 × 1.2 = 10.8 → 11 秒
    assert r["steps"]["say"] == {"n": 2, "p50": 900.0, "p95": 1100.0, "p99": 1100.0, "max": 1100.0}
    assert r["endingMs"] == "没有数据"


def test_live_formula_and_crossing() -> None:
    live = s5.LIVE
    first = 0.00086 + 0.0000788 * 9 + 9 * 25 * 12e-6 + 18 * 6 * 4.5e-6
    assert live.turn(0) == pytest.approx(first)
    assert live.turn(1) - live.turn(0) == pytest.approx(0.0000788 * 18)
    assert live.cost(9) == pytest.approx(live.cost(8) + live.turn(0))  # 第 9 轮是新会话
    flat = {"mean": 0.05, "slope": 0.0, "intercept": 0.05}
    n = s5.crossing(flat, 0.0, 300)
    assert n is not None
    usd = s5.narrator_cost(flat, n) + sum(e.cost(n) for e in s5.MISSING.values()) + live.cost(n)
    before = s5.narrator_cost(flat, n - 1) + sum(e.cost(n - 1) for e in s5.MISSING.values()) + live.cost(n - 1)
    assert usd * 150 >= 300 > before * 150
    assert s5.crossing({"mean": 0.0, "slope": 0.0, "intercept": 0.0}, 0.0, 10_000) is None
    r = s5.report(ROWS, RUNS, METRICS, TALKS, {})
    assert list(r["crossing"]) == ["240", "300", "350"]  # 350：Q-B8「上限提到 350 円」（PM #117）
    assert r["crossing"]["240"] <= r["crossing"]["300"] <= r["crossing"]["350"]
    text = s5.markdown(r)
    assert "上限提到 350 円时" in text and "世界推进 ×0.5 时合计" in text and "是上限" in text


def test_flat_turns_use_the_mean() -> None:
    t = s5.trend([[0.05, 0.04, 0.03], [0.05]])  # 不升（缓存越来越热）：按平均，不往下外推
    assert not t["rising"] and t["slope"] == 0 and t["intercept"] == pytest.approx(0.0425)


@pytest.mark.db
def test_cli_on_the_test_database(env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATABASE_URL", env.url)
    s = eval_api.setup({"role": "role.traveler", "persona": "persona.canon-follower", "seed": 1}, mode="text")
    s.say(OLD, PLAYER_LINE)
    s.say(OLD, "宿はどこですか。")
    ledger = tmp_path / "ledger.jsonl"
    now = datetime.now(UTC) + timedelta(hours=1)  # 两轮都在这之前：都算进第 2 轮
    lines = [row(s.pid, "extract", 0.02, 0, ms=2000, status="ok"), row(s.pid, "reply", 0.4, 0)]
    for x in lines:
        x["at"] = now.isoformat().replace("+00:00", "Z")
    ledger.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    runs = tmp_path / "runner.json"
    runs.write_text(
        json.dumps({"cases": [{"id": "S5-01", "results": [{"playthroughId": s.pid, "persona": "p", "seed": 1}]}]}),
        encoding="utf-8",
    )
    out = tmp_path / "out"
    assert s5.main(["--ledger", str(ledger), "--runs", str(runs), "--out", str(out)]) == 0
    r = json.loads((out / "report.json").read_text(encoding="utf-8"))
    (p,) = r["playthroughs"]
    assert p["turns"] == 2 and p["costByKind"] == {"extract": 0.02}  # reply 不算
    assert p["metricsMismatch"] == {"extract": {"ledger": 0.02, "metrics": 0.0}}  # 假模型不花钱：对不上就标出来
    md = (out / "report.md").read_text(encoding="utf-8")
    assert s.pid in md and "没有数据" in md
    for text in (md, json.dumps(r, ensure_ascii=False)):
        assert PLAYER_LINE not in text and "宿" not in text  # 只有数字
    assert s5.main(["--ledger", str(tmp_path / "none.jsonl"), "--runs", str(runs), "--out", str(out)]) == 2
