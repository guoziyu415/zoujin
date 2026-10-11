"""B-10：`zoujin-live reconcile`（S-090 的对账）用一份合成的账本。"""

from __future__ import annotations

from pathlib import Path

import pytest
from zoujin_backend import live_cli


def line(pid: str, turn: int, before_ms: int, usd: float, first_ms: int = 900, item: str = "b10") -> dict[str, object]:
    usage = {"sessionTurn": turn, "sessionAudioMsBefore": before_ms, "firstAudioMs": first_ms, "replyAudioMs": 3000}
    return {
        "at": f"2026-10-12T00:00:{turn:02d}Z",
        "kind": f"live.turn/{pid}",
        "item": item,
        "costUsd": usd,
        "usage": usage,
    }


def test_reconcile_groups_and_formula(tmp_path: Path) -> None:
    lines = [
        line("pt_a", 1, 0, 0.001),
        line("pt_a", 2, 10_000, 0.0017),
        line("pt_a", 1, 0, 0.0009, first_ms=-1),  # 重建后的新会话
        line("pt_b", 1, 0, 0.00086, first_ms=1100),
        line("pt_b", 1, 0, 9.0, item="other"),  # 别的项不算
        {"kind": "live.fallback/pt_a", "item": "b10", "costUsd": 0.0003, "usage": {}},
    ]
    r = live_cli.reconcile(lines, "b10")
    assert r["total"]["turns"] == 4
    assert r["total"]["formulaUsd"] == pytest.approx(round(0.00086 * 4 + 0.0000788 * 10, 4))
    assert r["total"]["fallbackUsd"] == 0.0003
    a = r["games"][0]
    assert (a["turns"], a["sessions"]) == (3, 2)
    assert r["releaseToFirstAudioMs"]["n"] == 3 and r["releaseToFirstAudioMs"]["median"] == 900
    assert {b["sessionTurns"] for b in r["bySessionTurn"]} == {"1–2"}
    md = live_cli.markdown(r)
    assert "| 1 | 3 | 2 |" in md


def test_reconcile_command_writes_files(tmp_path: Path) -> None:
    import json

    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps(line("pt_a", 1, 0, 0.001)) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        live_cli.main(["reconcile", "--ledger", str(ledger), "--out", str(tmp_path / "out")])
    assert e.value.code == 0
    assert (tmp_path / "out" / "reconcile.md").read_text(encoding="utf-8").startswith("# S-090")
