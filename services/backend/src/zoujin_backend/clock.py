"""tLabel：按世界模型的 `clock.labels` 生成（api-contract 第 0 节「故事时间」）。

日名带着情节时（`clock.labels.daysKnownBy`，『走れメロス』是 `fact.promise`），给模型的人物局势说明里，不知道这条事实
的人物只给时段（`band`，S-086）；界面和 tLabel 照旧用完整的说法。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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

    def label(self, t: int) -> str:
        day = t // 1440
        return self.format.format(day=self.days[min(day, len(self.days) - 1)], band=self.band(t))
