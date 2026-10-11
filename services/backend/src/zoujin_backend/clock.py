"""tLabel：按世界模型的 `clock.labels` 生成（api-contract 第 0 节「故事时间」）。

日名带着情节时（`clock.labels.daysKnownBy`，『走れメロス』是 `fact.promise`），给模型的人物局势说明里，不知道这条事实
的人物只给时段（`band`，S-086）；界面和 tLabel 照旧用完整的说法。人物亲历的事是什么时候，按 UX 定的
说法（`ago`，S-092：今朝、昨夜、おととい……），也不用日名。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# S-092（UX 10-11）：人物的一天从夜明け算起（零点开始的那一段结束时），天亮前的深夜还算前一天。时钟的哪一段算朝、昼、
# 夕方、夜，是数据维护的对应；这里是 world.json 现在的时段名。
PART_OF_DAY = {
    "薄明": "朝",
    "朝": "朝",
    "午前": "昼",
    "真昼": "昼",
    "午後": "昼",
    "夕方": "夕方",
    "日没前": "夕方",
    "日没": "夕方",
    "夜": "夜",
    "深夜": "夜",
}
TODAY = {"朝": "今朝", "昼": "今日の昼", "夕方": "今日の夕方", "夜": "今夜"}


class Labels:
    def __init__(self, world: Path | dict[str, Any]) -> None:
        """world：世界模型 world.json 的路径，或读好的世界模型。"""
        raw = json.loads(world.read_text(encoding="utf-8")) if isinstance(world, Path) else world
        labels: dict[str, Any] = raw["clock"]["labels"]
        self.days: list[str] = labels["days"]
        self.bands: list[tuple[int, str]] = [(int(m), str(b)) for m, b in labels["bands"]]
        self.format: str = labels["format"]
        self.days_known_by: str | None = labels.get("daysKnownBy")

    def band(self, t: int) -> str:
        return [b for m, b in self.bands if m <= t % 1440][-1]

    def ago(self, then: int, now: int) -> str | None:
        """从 `now` 看 `then` 是什么时候：今朝、今日の昼、今日の夕方、今夜、昨日、昨夜、おととい、三日前；再早 None。"""
        dawn = self.bands[1][0] if self.bands[0][0] == 0 and len(self.bands) > 1 else 0
        n = (now - dawn) // 1440 - (then - dawn) // 1440
        part = PART_OF_DAY.get(self.band(then))
        if n == 0:
            return TODAY.get(part or "", "今日")
        if n == 1:
            return "昨夜" if part == "夜" else "昨日"
        return {2: "おととい", 3: "三日前"}.get(n)

    def label(self, t: int) -> str:
        day = t // 1440
        return self.format.format(day=self.days[min(day, len(self.days) - 1)], band=self.band(t))
