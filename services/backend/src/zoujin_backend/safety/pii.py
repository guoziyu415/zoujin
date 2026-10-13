"""個人情報の規則（B-12、backend-design 5.5）：Model Armor の SDP は日本語の個人情報 6 件のうち 1 件しか検出できなかった
（S-4）ので、自前の規則を主とし、SDP は補助にとどめる。ナレーターの第 3 ステップ R6 の規則部分（`narrator/rules.py`）、
保存する元の発言、B-13 の記憶のフィルターはすべてこれを使う。

認める 5 種類（全角数字、各種の横線も認める）：
- 電話：`0` で始まり、`0\\d{1,4}-?\\d{1,4}-?\\d{3,4}`、合計 10〜11 桁の数字。
- メールアドレス。
- 住所：〒（郵便番号の有無を問わない）、「郵便番号」+ 7 桁、「都道府県 + 市区町村 + 番地」、`N丁目`、`N番地`。
- カード番号：13〜19 桁の数字（間に空白や横線があってよい）で、Luhn を通るもの。
- マイナンバー：12 桁の数字で、検査用数字を通るもの（総務省令の検査用数字）。

`find` は種類と位置だけを返し（一致した文字は返さない）、`mask` は一致した部分を「〔個人情報〕」に置き換える。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MASK = "〔個人情報〕"

_D = "[0-9０-９]"
# 各種の横線（長音符を含む：音声の書き起こしでは横線が「ー」になることがある）
_H = "[-‐‑‒–—―ー－−]"
_SEP = r"[-‐‑‒–—―－−\s　]"  # カード番号の途中の区切り
# 前後に数字が続いてはならない（区切りを 1 つ挟んでも不可）
_NOT_BEFORE = rf"(?<![0-9０-９])(?<![0-9０-９]{_SEP})"
_NOT_AFTER = rf"(?!{_SEP}?[0-9０-９])"

PREFECTURES = (
    "北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 "
    "石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 "
    "岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県"
).split()

PATTERNS: dict[str, re.Pattern[str]] = {
    "phone": re.compile(rf"(?<![0-9０-９]){'[0０]'}{_D}{{1,4}}{_H}?{_D}{{1,4}}{_H}?{_D}{{3,4}}(?![0-9０-９])"),
    "email": re.compile(r"[\w.+-]+[@＠][\w-]+(?:[.．][\w-]+)+"),
    "address": re.compile(
        rf"〒\s*(?:{_D}{{3}}{_H}?{_D}{{4}})?"
        rf"|郵便番号\s*[:：は]?\s*{_D}{{3}}{_H}?{_D}{{4}}"
        rf"|(?:{'|'.join(PREFECTURES)})\S{{0,8}}?[市区町村郡]\S{{0,12}}?{_D}{{1,4}}(?:丁目|番地?|{_H}{_D})"
        rf"(?:[丁目番地号の]|{_H}|{_D})*"
        rf"|{_D}{{1,4}}丁目(?:{_D}+[番号の]?)*|{_D}{{1,5}}番地"
    ),
    "card": re.compile(rf"{_NOT_BEFORE}{_D}(?:{_SEP}?{_D}){{12,18}}{_NOT_AFTER}"),
    "mynumber": re.compile(rf"{_NOT_BEFORE}{_D}{{4}}{_SEP}?{_D}{{4}}{_SEP}?{_D}{{4}}{_NOT_AFTER}"),
}
KINDS = tuple(PATTERNS)


@dataclass(frozen=True)
class Hit:
    kind: str  # phone / email / address / card / mynumber
    start: int
    end: int


def digits(s: str) -> str:
    """全角数字を半角に替え、数字だけを残す。"""
    return "".join(str(int(c)) for c in s if c.isdigit())


def luhn(number: str) -> bool:
    total = 0
    for i, c in enumerate(reversed(number)):
        d = int(c)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def mynumber_ok(number: str) -> bool:
    """マイナンバーの検査用数字：先頭 11 桁の右から n 桁目を Pn、重み Qn = n+1（1〜6）、n-5（7〜11）とし、
    余り = ΣPn×Qn mod 11 が ≤ 1 なら検査用数字は 0、それ以外は 11 - 余り。"""
    if len(number) != 12:
        return False
    body, check = number[:11], int(number[11])
    r = sum(int(p) * (n + 1 if n <= 6 else n - 5) for n, p in enumerate(reversed(body), start=1)) % 11
    return check == (0 if r <= 1 else 11 - r)


def _valid(kind: str, raw: str) -> bool:
    if kind == "card":
        n = digits(raw)
        return 13 <= len(n) <= 19 and luhn(n)
    if kind == "mynumber":
        return mynumber_ok(digits(raw))
    if kind == "phone":
        return 10 <= len(digits(raw)) <= 11
    return True


def find(text: str | None) -> list[Hit]:
    """一致した個人情報（位置順に並べ、重なるものは先に現れた長いほうだけを残す）。"""
    if not text:
        return []
    hits: list[Hit] = []
    for kind, pat in PATTERNS.items():
        for m in pat.finditer(text):
            if _valid(kind, m.group()):
                hits.append(Hit(kind, m.start(), m.end()))
    hits.sort(key=lambda h: (h.start, -(h.end - h.start)))
    out: list[Hit] = []
    for h in hits:
        if out and h.start < out[-1].end:
            continue
        out.append(h)
    return out


def kinds(text: str | None) -> set[str]:
    return {h.kind for h in find(text)}


def mask(text: str | None) -> str | None:
    """一致した部分を「〔個人情報〕」に置き換える。None はそのまま返す。"""
    if text is None:
        return None
    hits = find(text)
    if not hits:
        return text
    parts: list[str] = []
    at = 0
    for h in hits:
        parts.append(text[at : h.start])
        parts.append(MASK)
        at = h.end
    parts.append(text[at:])
    return "".join(parts)
