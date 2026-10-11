"""live 模式只有开关和退出（E-0 卡验收最后一条）：没开关退出、少上限退出、不带 --confirm 打印预计花费和命令。

花费按两本账分：google（人物的文字回答）、claude（叙事者、评审员和 AI 玩家）。
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


def g(env: dict[str, str], **kw: Any) -> tuple[int, str]:
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
    assert "| 套件 | 用例 | 次数 | Google | Claude |" in msg
    assert "| E7 | 11 | 11 | $5.50 | $1.10 |" in msg  # 11 局模拟局 × Google $0.5、Claude $0.1
    cmd = "uv run zoujin-eval --mode live --max-item-usd 1 --max-google-usd 30 --max-claude-usd 10 --confirm"
    assert f"{LIVE_SWITCH}=1 {cmd}" in msg
    assert "上限" in msg and "合计超过" not in msg and "超过上限" not in msg
    code, msg = g(ON, caps={"google": 30.0, "claude": 1.0}, max_item_usd=0.1)
    assert "Claude 合计超过上限" in msg and "Google 合计超过上限" not in msg and "超过单项上限" in msg


def test_confirm_still_exits() -> None:
    code, msg = g(ON, confirm=True)
    assert code == 2 and "M2" in msg


def test_case_cost() -> None:
    by_id = {c["id"]: c for c in CASES}
    # E2-009：5 次 ×（1 步 × Google 0.03 + 判分 Claude 0.015）
    e2 = by_id["E2-009"]
    assert case_cost(e2, PRICES, deterministic_only=False) == pytest.approx({"google": 0.15, "claude": 0.075})
    assert case_cost(e2, PRICES, deterministic_only=True) == pytest.approx({"google": 0.15, "claude": 0})
    # E5-006：只有 advance，不调模型
    assert case_cost(by_id["E5-006"], PRICES, deterministic_only=False) == {"google": 0, "claude": 0}
    assert case_cost(by_id["E7-001"], PRICES, deterministic_only=False) == pytest.approx({"google": 0.5, "claude": 0.1})


def test_unknown_provider_in_prices() -> None:
    with pytest.raises(ValueError, match="openai"):
        Prices.from_json({"turn": {"openai": 0.03}, "judge": {}, "simulatedPlaythrough": {}})
