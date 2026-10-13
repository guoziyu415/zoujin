"""B-10: `zoujin-live reconcile` (S-090 reconciliation) with a synthetic ledger.

B-10：合成した台帳で `zoujin-live reconcile`（S-090 の照合）を確認する。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from zoujin_backend import live_cli


def line(
    pid: str,
    turn: int,
    before_ms: int,
    usd: float,
    first_ms: int = 900,
    item: str = "b10",
    out_usd: float = 0.002,
    estimated: bool = False,
) -> dict[str, object]:
    usage = {
        "sessionTurn": turn,
        "sessionAudioMsBefore": before_ms,
        "firstAudioMs": first_ms,
        "replyAudioMs": 3000,
        "inputMicroUsd": round(usd * 1_000_000),
        "outputMicroUsd": round(out_usd * 1_000_000),
        "usageEstimated": int(estimated),
    }
    return {
        "at": f"2026-10-12T00:00:{turn:02d}Z",
        "kind": f"live.turn/{pid}",
        "item": item,
        "costUsd": usd + out_usd,
        "usage": usage,
    }


def test_reconcile_compares_input_only_and_fits(tmp_path: Path) -> None:
    lines = [
        line("pt_a", 1, 0, 0.001),
        line("pt_a", 2, 10_000, 0.0017),
        line("pt_a", 1, 0, 0.0009, first_ms=-1),  # A new session after a rebuild / 再構築後の新しいセッション
        line("pt_b", 1, 0, 0.00086, first_ms=1100),
        # No usage arrived: counted only, not compared / 使用量が届かない：数えるだけで比べない
        line("pt_b", 2, 5_000, 0.0, out_usd=0.01, estimated=True),
        line("pt_b", 1, 0, 9.0, item="other"),  # Other items don't count / 別の項目は数えない
        {"kind": "live.fallback/pt_a", "item": "b10", "costUsd": 0.0003, "usage": {}},
    ]
    r = live_cli.reconcile(lines, "b10")
    t = r["total"]
    assert (t["turns"], t["estimatedTurns"]) == (5, 1)
    assert t["inputUsd"] == pytest.approx(round(0.001 + 0.0017 + 0.0009 + 0.00086, 4))
    assert t["formulaInputUsd"] == pytest.approx(round(0.00086 * 4 + 0.0000788 * 10, 4))
    # Output is listed separately; the estimated turn doesn't count / 出力は別に並べ、見積もりのターンは数えない
    assert t["outputUsd"] == pytest.approx(0.008)
    assert t["fallbackUsd"] == 0.0003
    fit = r["fit"]
    assert fit["n"] == 4 and fit["slopeUsdPerS"] == pytest.approx((0.0017 - 0.00092) / 10, rel=1e-3)
    a = r["games"][0]
    assert (a["turns"], a["sessions"], a["estimatedTurns"]) == (3, 2, 0)
    assert r["games"][1]["estimatedTurns"] == 1
    assert r["releaseToFirstAudioMs"]["n"] == 4
    assert {b["sessionTurns"] for b in r["bySessionTurn"]} == {"1–2"}
    md = live_cli.markdown(r)
    assert "| 1 | 3 | 0 | 2 |" in md and "Fit (n=4)" in md


def test_reconcile_command_writes_files(tmp_path: Path) -> None:
    import json

    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps(line("pt_a", 1, 0, 0.001)) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        live_cli.main(["reconcile", "--ledger", str(ledger), "--out", str(tmp_path / "out")])
    assert e.value.code == 0
    assert (tmp_path / "out" / "reconcile.md").read_text(encoding="utf-8").startswith("# S-090")
