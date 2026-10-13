"""A few ways of judging text: whether it is Japanese, replacing proper nouns with a placeholder, the longest common
substring, and the human-readable text in an ending.

テキストを判定するいくつかの方法：日本語かどうか、固有名詞のプレースホルダーへの置き換え、最長共通部分文字列、結末の中の
人が読むテキスト。
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from typing import Any

# "japanese": kana and kanji are at least 80% of letters / 「japanese」：かなと漢字が文字の 80% 以上
JAPANESE_MIN = 0.8
# S-046: a longest common substring of ≥ 8 characters counts as a verbatim quote
# S-046：最長共通部分文字列が 8 文字以上なら逐語引用とみなす
VERBATIM_MAX = 8
# Placeholder for proper nouns: one private-use character, which never forms a long run with real text
# 固有名詞のプレースホルダー：私用領域の 1 文字。実際の文字と長い連続を作ることはない
PLACEHOLDER = ""

_JAPANESE_RANGES = (
    (0x3040, 0x309F),  # hiragana / ひらがな
    (0x30A0, 0x30FF),  # katakana (including the long-vowel mark ー) / カタカナ（長音符ーを含む）
    (0x31F0, 0x31FF),  # katakana phonetic extensions / カタカナ拡張
    (0xFF66, 0xFF9F),  # half-width katakana / 半角カタカナ
    (0x3400, 0x4DBF),  # CJK extension A / 漢字拡張 A
    (0x4E00, 0x9FFF),  # CJK unified ideographs / 漢字
    (0xF900, 0xFAFF),  # CJK compatibility ideographs / 互換漢字
    (0x3005, 0x3007),  # 々 〆 〇
)


def is_japanese_char(c: str) -> bool:
    o = ord(c)
    return any(lo <= o <= hi for lo, hi in _JAPANESE_RANGES)


def japanese_ratio(text: str) -> float | None:
    """What share of letters (Unicode category L) are kana and kanji. Punctuation, digits, whitespace and symbols do
    not count. None when there are no letters.

    文字（Unicode の L カテゴリ）のうちかなと漢字が占める割合。句読点、数字、空白、記号は数えない。文字がなければ None。
    """
    letters = [c for c in text if unicodedata.category(c).startswith("L")]
    if not letters:
        return None
    return sum(map(is_japanese_char, letters)) / len(letters)


_KATAKANA_RUN = re.compile(r"[ァ-ヺー]{3,}")


def proper_nouns(world: Mapping[str, Any]) -> list[str]:
    """Contract section 5 "proper nouns in the world model (character names, place names, quotations)": the names of
    characters, places and items, katakana runs of 3+ characters within names (「ディオニス」 in 「王ディオニス」,
    「シラクス」 in 「シラクスの広場と大路」), and the original text quoted in the world model. Longest first.

    契約第 5 節「世界モデル中の固有名詞（人物名、地名、引用文）」：人物、場所、物品の名前、名前の中の 3 文字以上の
    カタカナ（「王ディオニス」の「ディオニス」、「シラクスの広場と大路」の「シラクス」）、そして世界モデルが引用する
    原文。長いものが先。
    """
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
    """Replace proper nouns with the placeholder (longest first).

    固有名詞をプレースホルダーに置き換える（長いものから）。
    """
    for n in nouns:
        text = text.replace(n, PLACEHOLDER)
    return text


def longest_common_substring(a: str, b: str) -> str:
    """The longest common substring of a and b (on a tie, the one that appears first in a).

    a と b の最長共通部分文字列（同じ長さなら a で先に現れるもの）。
    """
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
    """Which part of lines text quotes verbatim (S-046): replace proper nouns on both sides first, then return the
    longest common substring if it is ≥ 8 characters, otherwise None.

    text が lines のどの部分を逐語引用しているか（S-046）：まず両方の固有名詞を置き換え、最長共通部分文字列が 8 文字以上
    ならそれを返し、そうでなければ None。
    """
    t = mask(text, nouns)
    for line in lines:
        common = longest_common_substring(t, mask(line, nouns))
        if len(common) >= VERBATIM_MAX:
            return common
    return None


# Fields in an ending that are not human-readable text: IDs, citations, state values, file references
# 結末の中で人が読むテキストではないフィールド：ID、引用、状態値、ファイル参照
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
    """All the human-readable text in an ending (contract section 5 "every text field"), in order of appearance.

    結末の中の人が読むテキストすべて（契約第 5 節「各テキストフィールド」）、出現順。
    """
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
