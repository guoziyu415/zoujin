"""live 模式只有开关和退出（E-0 卡验收最后一条）：没开关退出、少上限退出、不带 --confirm 打印预计花费和命令。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from zoujin_evals.cases import load_cases
from zoujin_evals.live import LIVE_SWITCH, Prices, case_cost, gate

CASES = load_cases(Path(__file__).resolve().parents[1] / "seeds")
PRICES = Prices(turn_usd=0.03, judge_usd=0.015, simulated_playthrough_usd=0.6)
ON = {LIVE_SWITCH: "1"}


def g(env: dict[str, str], **kw: Any) -> tuple[int, str]:
    args: dict[str, Any] = {
        "max_item_usd": 1.0,
        "max_total_usd": 30.0,
        "confirm": False,
        "cases": CASES,
        "prices": PRICES,
        "deterministic_only": False,
        "argv": ["--mode", "live", "--max-item-usd", "1", "--max-total-usd", "30"],
        **kw,
    }
    return gate(env, **args)


def test_needs_the_mac_switch() -> None:
    code, msg = g({})
    assert code == 2 and LIVE_SWITCH in msg
    assert g({LIVE_SWITCH: "yes"})[0] == 2


def test_needs_both_caps() -> None:
    code, msg = g(ON, max_item_usd=None)
    assert code == 2 and "--max-item-usd" in msg and "--max-total-usd" not in msg
    code, msg = g(ON, max_item_usd=None, max_total_usd=None)
    assert code == 2 and "--max-item-usd --max-total-usd" in msg


def test_without_confirm_prints_estimate_and_command() -> None:
    code, msg = g(ON)
    assert code == 0
    assert "| E7 | 11 | 11 | $6.60 |" in msg  # 11 局模拟局 × $0.6
    assert f"{LIVE_SWITCH}=1 uv run zoujin-eval --mode live --max-item-usd 1 --max-total-usd 30 --confirm" in msg
    code, msg = g(ON, max_total_usd=5.0, max_item_usd=0.1)
    assert "合计超过总上限" in msg and "超过单项上限" in msg


def test_confirm_still_exits() -> None:
    code, msg = g(ON, confirm=True)
    assert code == 2 and "M2" in msg


def test_case_cost() -> None:
    by_id = {c["id"]: c for c in CASES}
    # E2-009：5 次 ×（1 步 × 0.03 + 判分 0.015）
    assert abs(case_cost(by_id["E2-009"], PRICES, deterministic_only=False) - 5 * 0.045) < 1e-9
    assert abs(case_cost(by_id["E2-009"], PRICES, deterministic_only=True) - 5 * 0.03) < 1e-9
    # E5-006：只有 advance，不调模型
    assert case_cost(by_id["E5-006"], PRICES, deterministic_only=False) == 0
    assert case_cost(by_id["E7-001"], PRICES, deterministic_only=False) == 0.6
