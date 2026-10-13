"""The live mode gate (last acceptance item of the E-0 card; real runs since B-5): exit without the switch, exit when a
cap is missing, and without --confirm print the estimated cost and the command.

Costs are split across the two ledgers: google (the characters' text replies), claude (narrator, judge and AI player).

live モードのゲート（E-0 カードの受け入れ確認の最後の項目。B-5 から実際に実行）：スイッチがなければ終了、上限が欠けて
いれば終了、--confirm なしなら見積もり費用とコマンドを表示する。

費用は 2 つの台帳に分ける：google（人物のテキスト返答）、claude（ナレーター、審査員、AI プレイヤー）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from zoujin_evals.cases import load_cases
from zoujin_evals.live import LIVE_SWITCH, Prices, case_cost, gate

CASES = load_cases(Path(__file__).resolve().parents[1] / "seeds")
PRICES = Prices.from_json(
    {"turn": {"google": 0.03}, "judge": {"claude": 0.015}, "simulatedPlaythrough": {"google": 0.5, "claude": 0.1}}
)
ON = {LIVE_SWITCH: "1"}


def g(env: dict[str, str], **kw: Any) -> tuple[int | None, str]:
    args: dict[str, Any] = {
        "max_item_usd": 1.0,
        "caps": {"google": 30.0, "claude": 10.0},
        "confirm": False,
        "cases": CASES,
        "prices": PRICES,
        "deterministic_only": False,
        "argv": ["--mode", "live", "--max-item-usd", "1", "--max-google-usd", "30", "--max-claude-usd", "10"],
        **kw,
    }
    return gate(env, **args)


def test_needs_the_mac_switch() -> None:
    code, msg = g({})
    assert code == 2 and LIVE_SWITCH in msg
    assert g({LIVE_SWITCH: "yes"})[0] == 2


def test_needs_every_cap() -> None:
    code, msg = g(ON, max_item_usd=None)
    assert code == 2 and "--max-item-usd" in msg and "--max-google-usd" not in msg
    code, msg = g(ON, caps={"google": 30.0, "claude": None})
    assert code == 2 and "--max-claude-usd" in msg and "--max-item-usd" not in msg
    code, msg = g(ON, max_item_usd=None, caps={})
    assert code == 2 and "--max-item-usd --max-google-usd --max-claude-usd" in msg


def test_without_confirm_prints_estimate_and_command() -> None:
    code, msg = g(ON)
    assert code == 0
    assert "| Suite / スイート | Cases / ケース | Runs / 回数 | Google | Claude |" in msg
    # 11 simulated games × Google $0.5, Claude $0.1 / シミュレーション局 11 局 × Google $0.5、Claude $0.1
    assert "| E7 | 11 | 11 | $5.50 | $1.10 |" in msg
    cmd = "uv run zoujin-eval --mode live --max-item-usd 1 --max-google-usd 30 --max-claude-usd 10 --confirm"
    assert f"{LIVE_SWITCH}=1 {cmd}" in msg
    assert "cap" in msg and "total is over" not in msg and "over its cap" not in msg
    code, msg = g(ON, caps={"google": 30.0, "claude": 1.0}, max_item_usd=0.1)
    assert "Claude total is over its cap" in msg and "Google total is over its cap" not in msg
    assert "over the per-item cap" in msg


def test_confirm_needs_the_rest() -> None:
    """Checked only with --confirm: judging not wired in (needs --deterministic-only), --item, the ledger, the AI
    player's model (details in test_player).

    --confirm があるときだけ確認する：採点が未接続（--deterministic-only が必要）、--item、台帳、AI プレイヤーのモデル
    （詳細は test_player）。
    """
    code, msg = g(ON, confirm=True)
    assert code == 2 and "--deterministic-only" in msg
    code, msg = g({**ON, "ZJ_LEDGER": "/x"}, confirm=True, deterministic_only=True, item="s5", player_model="m")
    assert code is None


def test_case_cost() -> None:
    by_id = {c["id"]: c for c in CASES}
    # E2-009: 5 runs × (1 step × Google 0.03 + judging Claude 0.015)
    # E2-009：5 回 ×（1 ステップ × Google 0.03 + 採点 Claude 0.015）
    e2 = by_id["E2-009"]
    assert case_cost(e2, PRICES, deterministic_only=False) == pytest.approx({"google": 0.15, "claude": 0.075})
    assert case_cost(e2, PRICES, deterministic_only=True) == pytest.approx({"google": 0.15, "claude": 0})
    # E5-006: only advance, no model call / E5-006：advance だけで、モデルを呼ばない
    assert case_cost(by_id["E5-006"], PRICES, deterministic_only=False) == {"google": 0, "claude": 0}
    assert case_cost(by_id["E7-001"], PRICES, deterministic_only=False) == pytest.approx({"google": 0.5, "claude": 0.1})


def test_unknown_provider_in_prices() -> None:
    with pytest.raises(ValueError, match="openai"):
        Prices.from_json({"turn": {"openai": 0.03}, "judge": {}, "simulatedPlaythrough": {}})
