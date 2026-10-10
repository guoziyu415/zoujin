"""live 模式（E-0 卡第 3 条）：本卡只有开关和退出，真模型的客户端 M2 再接。

1. 没有 Mac 上的开关（环境变量 ZJ_EVAL_LIVE=1，只在 zg 的 Mac 上设）就退出，打印原因。
2. 上限必须显式传入，没有默认值：--max-item-usd（单项）和两本账各一个总上限 --max-google-usd、--max-claude-usd。
   少一个就退出。两本账（PM 2026-10-10，Claude 额度）：产品路径的 Gemini 记 google，评审员和 AI 玩家记 claude。
3. 不带 --confirm：打印预计花费和完整命令后退出。由协调拿给 zg 看，zg 同意后才带 --confirm 再跑。
4. 带 --confirm：退出，打印「真模型的客户端还没有，M2 接上」。
"""

from __future__ import annotations

import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .checks import step_kind

LIVE_SWITCH = "ZJ_EVAL_LIVE"
MODEL_STEPS = {"to", "act", "propose", "silence", "choose"}  # 要调模型的步骤；删除、advance 只动数据库和规则
PROVIDERS = ("google", "claude")  # 两本账
CAP_FLAGS = {"google": "--max-google-usd", "claude": "--max-claude-usd"}
NAMES = {"google": "Google", "claude": "Claude"}

type Cost = dict[str, float]  # 供应商 → 美元


def _cost(d: Mapping[str, Any]) -> Cost:
    unknown = sorted(set(d) - set(PROVIDERS))
    if unknown:
        raise ValueError(f"live-cost.json 里有不认识的供应商：{unknown}")
    return {p: float(d.get(p, 0)) for p in PROVIDERS}


@dataclass(frozen=True)
class Prices:
    turn: Cost  # 一步：人物回答 + 叙事者提取、检查、记忆（产品路径）
    judge: Cost  # 判分一次（评审员）
    simulated_playthrough: Cost  # 一局模拟局：产品路径 + AI 玩家 + 结局

    @classmethod
    def from_json(cls, d: Mapping[str, Any]) -> Prices:
        return cls(_cost(d["turn"]), _cost(d["judge"]), _cost(d["simulatedPlaythrough"]))


def case_cost(case: Mapping[str, Any], prices: Prices, *, deterministic_only: bool) -> Cost:
    """一例的预计花费，按供应商分 = runs ×（要调模型的步数 × 一步 + 判分一次）；模拟局按一局算。"""
    runs = case.get("runs", 5)
    if "persona" in case["setup"]:
        per_run = dict(prices.simulated_playthrough)
    else:
        n = sum(step_kind(s) in MODEL_STEPS for s in case.get("steps", []))
        per_run = {p: n * prices.turn[p] for p in PROVIDERS}
    if "judge" in case.get("expect", {}) and not deterministic_only:
        per_run = {p: per_run[p] + prices.judge[p] for p in PROVIDERS}
    return {p: float(runs * per_run[p]) for p in PROVIDERS}


def gate(
    env: Mapping[str, str],
    *,
    max_item_usd: float | None,
    caps: Mapping[str, float | None],
    confirm: bool,
    cases: Sequence[Mapping[str, Any]],
    prices: Prices,
    deterministic_only: bool,
    argv: Sequence[str],
) -> tuple[int, str]:
    """返回（退出码，要打印的话）。live 现在总是退出：0 = 打印了预计花费，2 = 不能跑。caps：供应商 → 总上限。"""
    if env.get(LIVE_SWITCH) != "1":
        return 2, f"live 要调真模型，只在 zg 的 Mac 上跑：没有设 {LIVE_SWITCH}=1，退出。"
    given = {"--max-item-usd": max_item_usd, **{CAP_FLAGS[p]: caps.get(p) for p in PROVIDERS}}
    missing = [n for n, v in given.items() if v is None]
    if missing:
        why = "没有默认值（开发期的模型花费上限 zg 还没定）"
        return 2, f"live 要显式给单项上限和两本账的总上限，{why}。少了 {' '.join(missing)}，退出。"
    assert max_item_usd is not None
    total_caps = {p: float(caps[p] or 0) for p in PROVIDERS}
    if confirm:
        return 2, "真模型的客户端还没有，M2 接上。没有调用任何模型，退出。"
    return 0, estimate_text(cases, prices, deterministic_only, max_item_usd, total_caps, argv)


def estimate_text(
    cases: Sequence[Mapping[str, Any]],
    prices: Prices,
    deterministic_only: bool,
    max_item_usd: float,
    caps: Mapping[str, float],
    argv: Sequence[str],
) -> str:
    costs = [(c, case_cost(c, prices, deterministic_only=deterministic_only)) for c in cases]
    total = {p: sum(x[p] for _, x in costs) for p in PROVIDERS}
    lines = [
        "预计花费（推算，单价见 evals/config/live-cost.json）：",
        "",
        "| 套件 | 用例 | 次数 | " + " | ".join(NAMES[p] for p in PROVIDERS) + " |",
        "|---|---:|---:|" + "---:|" * len(PROVIDERS),
    ]
    for suite in sorted({c["suite"] for c, _ in costs}):
        xs = [(c, x) for c, x in costs if c["suite"] == suite]
        runs = sum(c.get("runs", 5) for c, _ in xs)
        money = " | ".join(f"${sum(x[p] for _, x in xs):.2f}" for p in PROVIDERS)
        lines.append(f"| {suite} | {len(xs)} | {runs} | {money} |")
    sums = "，".join(f"{NAMES[p]} 约 ${total[p]:.2f}（上限 ${caps[p]:.2f}）" for p in PROVIDERS)
    lines += ["", f"合计：{sums}；单项上限 ${max_item_usd:.2f}（两本账合起来算）。"]
    over = [c["id"] for c, x in costs if sum(x.values()) > max_item_usd]
    if over:
        lines.append(f"超过单项上限、会在中途停下的用例：{'、'.join(over)}。")
    for p in PROVIDERS:
        if total[p] > caps[p]:
            lines.append(f"{NAMES[p]} 合计超过上限：这本账跑到上限就停，后面的用例不跑。")
    cmd = ["uv", "run", "zoujin-eval", *argv]
    if "--confirm" not in cmd:
        cmd.append("--confirm")
    lines += ["", "zg 同意后在 Mac 上跑：", "", f"    {LIVE_SWITCH}=1 {shlex.join(cmd)}"]
    return "\n".join(lines)
