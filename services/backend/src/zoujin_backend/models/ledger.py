"""账本（B-2 卡「账本」，dev-plan Z-8）：真客户端每次调用前查、调用后记。B-8 起账本类在共用包 `zoujin_llm.ledger`
（叙事者和数据的评审员同一个类），这里留 Google 那本的写法和单价。

- 一个 JSONL 文件，两本账、E-0 live、评审员都记在同一个文件、同一种行（`zoujin_llm.ledger` 的说明）：Z-8 的上限是
  后端调提示、S-2、评测和 S-5 合用的，总上限比的是文件里已有的累计加这一次，不只是这一次跑的。
- 调用前用预计花费（按输入长度和输出上限估，偏高）判上限，到了抛 `BudgetStop`，这次不发；调用后记实际的花费。
- 总上限只算自己那家的行；单项上限只在给了 `item` 时判：同一个 item 两本账合起来（数据 #49）。
- 每行带 `use`：叙事者各步、预录句、Live 是 "product"，在评测里跑也是（S-5 的单局成本只加 product）。
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from zoujin_llm import Ledger as _Ledger

from zoujin_backend.config import PRICES, REGIONAL_MARKUP

PROVIDER = "google"


def cost_usd(model: str, usage: Mapping[str, int], *, regional: bool) -> float:
    """花费 = 用量 × 价目（config.PRICES）。思考 token 按输出计；缓存命中的输入按缓存价。"""
    p = PRICES[model]
    cached = usage.get("cachedTokens", 0)
    fresh = max(0, usage.get("inputTokens", 0) - cached)
    out = usage.get("outputTokens", 0) + usage.get("thoughtTokens", 0)
    usd = (fresh * p["input"] + cached * p["cachedInput"] + out * p["output"]) / 1_000_000
    return usd * (REGIONAL_MARKUP if regional else 1.0)


class Ledger(_Ledger):
    """Google 那本账（共用的账本类，provider 写 google）。构造的参数和 B-2 时一样，B-6 的预录句也用它。"""

    def __init__(
        self,
        path: Path,
        max_total_usd: float,
        max_item_usd: float | None = None,
        item: str | None = None,
        use: str = "product",
    ) -> None:
        super().__init__(path, PROVIDER, max_total_usd, max_item_usd, item, use)

    def spent(self, item: str | None = None) -> float:
        """没给 item：Google 这本账的累计（总上限）。给了 item：这一项两本账合起来的花费（单项上限）。"""
        return self.spent_total() if item is None else self.spent_on(item)
