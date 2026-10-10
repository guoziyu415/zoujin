"""tLabel：按世界模型的 `clock.labels` 生成（api-contract 第 0 节「故事时间」）。"""

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

    def label(self, t: int) -> str:
        day, minute = divmod(t, 1440)
        band = [b for m, b in self.bands if m <= minute][-1]
        return self.format.format(day=self.days[min(day, len(self.days) - 1)], band=band)
