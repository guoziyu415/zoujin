"""tLabel: built from the world model's `clock.labels` (api-contract section 0, "story time").

When the day names carry plot (`clock.labels.daysKnownBy`; for 『走れメロス』 it is `fact.promise`), the character
situation notes given to the model give characters who don't know that fact only the time band (`band`, S-086); the UI
and tLabel still use the full wording. When something a character lived through happened is phrased the way UX decided
(`ago`, S-092: 今朝, 昨夜, おととい...), also without day names.

tLabel：世界モデルの `clock.labels` から生成する（api-contract 第 0 節「物語の時間」）。

日名が筋を含むとき（`clock.labels.daysKnownBy`、『走れメロス』では `fact.promise`）、
モデルに渡す登場人物の状況説明では、その事実を知らない登場人物には時間帯（`band`、S-086）だけを渡す。
画面と tLabel は従来どおり完全な言い方を使う。登場人物が自分で経験したことがいつだったかは、
UX が決めた言い方（`ago`、S-092：今朝、昨夜、おととい……）で表し、これも日名は使わない。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# S-092 (UX 10-11): a character's day starts at 夜明け (when the band starting at midnight ends); late night before
# dawn still counts as the previous day. Which clock band counts as 朝, 昼, 夕方 or 夜 is a mapping the data side
# maintains; these are the band names world.json has now.
# S-092（UX 10-11）：登場人物の一日は夜明け（零時から始まる区間が終わるとき）から数え、夜明け前の深夜は前の日に数える。
# 時計のどの区間を朝・昼・夕方・夜とするかはデータ側が管理する対応で、ここにあるのは world.json の現在の時間帯名。
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
        """world: the path to the world model's world.json, or an already loaded world model.

        world：世界モデル world.json のパス、または読み込み済みの世界モデル。
        """
        raw = json.loads(world.read_text(encoding="utf-8")) if isinstance(world, Path) else world
        labels: dict[str, Any] = raw["clock"]["labels"]
        self.days: list[str] = labels["days"]
        self.bands: list[tuple[int, str]] = [(int(m), str(b)) for m, b in labels["bands"]]
        self.format: str = labels["format"]
        self.days_known_by: str | None = labels.get("daysKnownBy")
        missing = [b for _, b in self.bands if b not in PART_OF_DAY]
        if missing:
            raise ValueError(
                f"Band names missing from PART_OF_DAY: {missing} (S-092; the table is maintained by the data side)"
                f" / PART_OF_DAY にない時間帯名：{missing}（S-092、表はデータ側が管理）"
            )

    def band(self, t: int) -> str:
        return [b for m, b in self.bands if m <= t % 1440][-1]

    def ago(self, then: int, now: int) -> str | None:
        """When `then` is, seen from `now`: 今朝, 今日の昼, 今日の夕方, 今夜, 昨日, 昨夜, おととい, 三日前;
        None if earlier.

        `now` から見て `then` がいつか：今朝、今日の昼、今日の夕方、今夜、昨日、昨夜、おととい、三日前。
        それより前は None。
        """
        dawn = self.bands[1][0] if self.bands[0][0] == 0 and len(self.bands) > 1 else 0
        n = (now - dawn) // 1440 - (then - dawn) // 1440
        part = PART_OF_DAY[self.band(then)]
        if n == 0:
            return TODAY[part]
        if n == 1:
            return "昨夜" if part == "夜" else "昨日"
        return {2: "おととい", 3: "三日前"}.get(n)

    def label(self, t: int) -> str:
        day = t // 1440
        return self.format.format(day=self.days[min(day, len(self.days) - 1)], band=self.band(t))
