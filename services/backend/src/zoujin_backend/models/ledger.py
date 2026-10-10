"""Google 那本账（B-2 卡「账本」，dev-plan Z-8）：真客户端每次调用前查、调用后记。

- 一个 JSONL 文件，和 E-0 live 的 Google 账本是**同一个文件、同一种行格式**：Z-8 的第一段是后端调提示、S-2、
  第一遍切片评测和 S-5 合用的，所以总上限比的是文件里已有的累计花费加这一次，不只是这一次跑的。
- 一行：`at`（UTC，Z 结尾）、`provider`（"google"）、`kind`（提示类型）、`model`、`usage`、`costUsd`，
  有的话 `item`（记在哪一项下：S-2 的条目 ID、E-0 的用例 ID）。不写请求和回答的内容，也不写项目 ID。
- 调用前用预计花费（按输入长度和输出上限估，偏高）判上限，到了抛 `BudgetStop`，这次不发；调用后记实际的花费。
- 单项上限只在给了 `item` 时判：同一个 item 在账本里的花费加这一次。
- Claude 那本账在数据的运行器里（评审员、AI 玩家），后端不碰。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from zoujin_backend.config import PRICES, REGIONAL_MARKUP
from zoujin_backend.models.text import BudgetStop, now_z

PROVIDER = "google"


def cost_usd(model: str, usage: Mapping[str, int], *, regional: bool) -> float:
    """花费 = 用量 × 价目（config.PRICES）。思考 token 按输出计；缓存命中的输入按缓存价。"""
    p = PRICES[model]
    cached = usage.get("cachedTokens", 0)
    fresh = max(0, usage.get("inputTokens", 0) - cached)
    out = usage.get("outputTokens", 0) + usage.get("thoughtTokens", 0)
    usd = (fresh * p["input"] + cached * p["cachedInput"] + out * p["output"]) / 1_000_000
    return usd * (REGIONAL_MARKUP if regional else 1.0)


@dataclass
class Ledger:
    path: Path
    max_total_usd: float
    max_item_usd: float | None = None
    item: str | None = None

    def _lines(self) -> list[dict[str, object]]:
        if not self.path.is_file():
            return []
        return [json.loads(x) for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip()]

    def spent(self, item: str | None = None) -> float:
        """账本里 Google 这本账累计的花费；给了 item 只算这一项。每次重读文件（E-0 可能同时在记）。"""
        total = 0.0
        for line in self._lines():
            if line.get("provider", PROVIDER) != PROVIDER:
                continue
            if item is not None and line.get("item") != item:
                continue
            total += float(line.get("costUsd", 0.0))  # type: ignore[arg-type]
        return total

    def before(self, estimate_usd: float) -> None:
        """调用前：累计 + 这一次的预计超过上限就抛 BudgetStop（不发这次调用）。"""
        so_far = self.spent()
        if so_far + estimate_usd > self.max_total_usd:
            raise BudgetStop(
                f"Google 账本已花 ${so_far:.4f}，加上这次预计 ${estimate_usd:.4f} 超过总上限 ${self.max_total_usd:.2f}"
            )
        if self.item is not None and self.max_item_usd is not None:
            on_item = self.spent(self.item)
            if on_item + estimate_usd > self.max_item_usd:
                raise BudgetStop(
                    f"这一项已花 ${on_item:.4f}，加上这次预计 ${estimate_usd:.4f} 超过单项上限 ${self.max_item_usd:.2f}"
                )

    def add(self, *, kind: str, model: str, usage: Mapping[str, int], cost: float) -> None:
        line: dict[str, object] = {
            "at": now_z(),
            "provider": PROVIDER,
            "kind": kind,
            "model": model,
            "usage": dict(usage),
            "costUsd": round(cost, 8),
        }
        if self.item is not None:
            line["item"] = self.item
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
