"""看文字的判法：日语比例、专有名词占位、最长公共子串。"""

from __future__ import annotations

from zoujin_evals import WorldIndex
from zoujin_evals.text import (
    PLACEHOLDER,
    ending_texts,
    japanese_ratio,
    longest_common_substring,
    mask,
    proper_nouns,
    verbatim,
)


def test_japanese_ratio_counts_letters_only() -> None:
    assert japanese_ratio("「メロスは激怒した。」") == 1.0
    assert japanese_ratio("１２３！？…") is None  # 没有字母类字符
    r = japanese_ratio("OK、わかった")  # 2 个拉丁字母 + 4 个假名
    assert r is not None and abs(r - 4 / 6) < 1e-9
    assert japanese_ratio("々〆ーｱ") == 1.0


def test_proper_nouns_include_names_katakana_and_quotes(world_ix: WorldIndex) -> None:
    nouns = proper_nouns(world_ix.raw)
    for n in ("セリヌンティウス", "王ディオニス", "ディオニス", "シラクス", "メロス"):
        assert n in nouns
    assert any(len(n) > 15 for n in nouns)  # 原文的引文
    assert nouns == sorted(nouns, key=lambda s: (-len(s), s))  # 长的先换


def test_mask_and_verbatim(world_ix: WorldIndex) -> None:
    nouns = world_ix.nouns
    assert mask("王ディオニスとメロス", nouns) == f"{PLACEHOLDER}と{PLACEHOLDER}"
    # 光是名字就有 8 个字，不换掉会误判
    assert len(longest_common_substring("セリヌンティウスは待った", "セリヌンティウスを信じる")) == 8
    assert verbatim("セリヌンティウスは待った", ["セリヌンティウスを信じる"], nouns) is None
    assert verbatim("あなたは必ず戻ると約束した", ["わたしは必ず戻ると約束します"], nouns) == "は必ず戻ると約束し"
    assert verbatim("短い", ["短い"], nouns) is None


def test_longest_common_substring() -> None:
    assert longest_common_substring("abcdef", "zcdez") == "cde"
    assert longest_common_substring("", "abc") == ""
    assert longest_common_substring("abab", "ab") == "ab"


def test_ending_texts_skip_ids() -> None:
    end = {
        "endingId": "end_1",
        "world": {"outcome": "too-late", "summary": "間に合わなかった。", "changedBeats": [{"beat": "beat.24"}]},
        "player": {"epilogue": [{"sentence": "雨が降った。", "cites": ["ev_1"]}], "fate": {"id": "f", "label": "人質"}},
        "characters": [{"character": "char.melos", "original": "抱き合った。"}],
        "card": {"title": "称号", "characterLines": [{"character": "char.melos", "line": "走った。"}]},
    }
    assert ending_texts(end) == ["間に合わなかった。", "雨が降った。", "人質", "抱き合った。", "称号", "走った。"]
