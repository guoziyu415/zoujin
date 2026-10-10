"""看文字的几个判法：是不是日语、专有名词换占位符、最长公共子串、结局里给人看的文字。"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from typing import Any

JAPANESE_MIN = 0.8  # 「japanese」：假名和汉字占字母类字符 80% 以上
VERBATIM_MAX = 8  # S-046：最长公共子串 ≥ 8 字算逐字引用
PLACEHOLDER = ""  # 专有名词的占位符：一个私用区的字，不会和真文字连成长串

_JAPANESE_RANGES = (
    (0x3040, 0x309F),  # 平假名
    (0x30A0, 0x30FF),  # 片假名（含长音符ー）
    (0x31F0, 0x31FF),  # 片假名音标扩展
    (0xFF66, 0xFF9F),  # 半角片假名
    (0x3400, 0x4DBF),  # 汉字扩展 A
    (0x4E00, 0x9FFF),  # 汉字
    (0xF900, 0xFAFF),  # 兼容汉字
    (0x3005, 0x3007),  # 々 〆 〇
)


def is_japanese_char(c: str) -> bool:
    o = ord(c)
    return any(lo <= o <= hi for lo, hi in _JAPANESE_RANGES)


def japanese_ratio(text: str) -> float | None:
    """字母类字符（Unicode 的 L 类）里假名和汉字占多少。标点、数字、空白、符号不算。没有字母类字符时 None。"""
    letters = [c for c in text if unicodedata.category(c).startswith("L")]
    if not letters:
        return None
    return sum(map(is_japanese_char, letters)) / len(letters)


_KATAKANA_RUN = re.compile(r"[ァ-ヺー]{3,}")


def proper_nouns(world: Mapping[str, Any]) -> list[str]:
    """契约第 5 节「世界模型里的专有名词（人物名、地名、引文）」：人物、地点、物品的名字，名字里 3 字以上的片假名
    （「王ディオニス」里的「ディオニス」、「シラクスの広場と大路」里的「シラクス」），和世界模型里引用的原文。长的在前。"""
    names: set[str] = set()
    for key in ("characters", "places", "items"):
        for x in world.get(key, []):
            if x.get("name"):
                names.add(x["name"])
                names.update(_KATAKANA_RUN.findall(x["name"]))
    names.update(q for q in _quotes(world) if q)
    return sorted(names, key=lambda s: (-len(s), s))


def _quotes(o: Any) -> Iterator[str]:
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "quote" and isinstance(v, str):
                yield v
            else:
                yield from _quotes(v)
    elif isinstance(o, list):
        for v in o:
            yield from _quotes(v)


def mask(text: str, nouns: Iterable[str]) -> str:
    """把专有名词换成占位符（长的先换）。"""
    for n in nouns:
        text = text.replace(n, PLACEHOLDER)
    return text


def longest_common_substring(a: str, b: str) -> str:
    """a 和 b 最长的公共子串（一样长的取在 a 里最先出现的）。"""
    best, end = 0, 0
    prev = [0] * (len(b) + 1)
    for i, ca in enumerate(a, 1):
        cur = [0] * (len(b) + 1)
        for j, cb in enumerate(b, 1):
            if ca == cb:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best, end = cur[j], i
        prev = cur
    return a[end - best : end]


def verbatim(text: str, lines: Iterable[str], nouns: list[str]) -> str | None:
    """text 逐字引用了 lines 里的哪一段（S-046）：两边都先换掉专有名词，最长公共子串 ≥ 8 字就返回它，否则 None。"""
    t = mask(text, nouns)
    for line in lines:
        common = longest_common_substring(t, mask(line, nouns))
        if len(common) >= VERBATIM_MAX:
            return common
    return None


# 结局里不是给人看的文字的字段：ID、引用、状态值、文件引用
_NOT_TEXT = {
    "schemaVersion",
    "endingId",
    "playthroughId",
    "worldModelVersion",
    "trigger",
    "decidedAt",
    "outcome",
    "id",
    "beat",
    "to",
    "var",
    "value",
    "character",
    "place",
    "present",
    "causedBy",
    "cites",
    "memoryIds",
    "changedBeats",
    "finalVars",
    "claims",
    "signature",
    "share",
    "fallbackImageUrl",
}


def ending_texts(ending: Any) -> list[str]:
    """结局里全部给人看的文字（契约第 5 节「每个文字字段」），按出现的先后。"""
    out: list[str] = []

    def walk(o: Any) -> None:
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k not in _NOT_TEXT:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(ending)
    return out
