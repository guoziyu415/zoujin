"""个人信息的规则（B-12，backend-design 5.5）：Model Armor 的 SDP 只认出日语个人信息 6 条里的 1 条（S-4），所以以我们
自己的规则为主、SDP 只作补充。叙事者第 3 步 R6 的规则部分（`narrator/rules.py`）、存下的原话、
B-13 的记忆过滤都用这一套。

认的五种（全角数字、各种横线都认）：
- 电话：`0` 开头，`0\\d{1,4}-?\\d{1,4}-?\\d{3,4}`，合计 10〜11 位数字；
- 邮箱；
- 住所：〒（带不带邮编都算）、「郵便番号」+ 7 位、「都道府県 + 市区町村 + 番地」、`N丁目`、`N番地`；
- 卡号：13〜19 位数字（中间可以有空格、横线），过 Luhn；
- マイナンバー：12 位数字，过校验位（総務省令の検査用数字）。

`find` 只返回种类和位置（不返回命中的字），`mask` 把命中的部分换成「〔個人情報〕」。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MASK = "〔個人情報〕"

_D = "[0-9０-９]"
_H = "[-‐‑‒–—―ー－−]"  # 各种横线（含长音符：语音转写有时把横线写成「ー」）
_SEP = r"[-‐‑‒–—―－−\s　]"  # 卡号中间的分隔
_NOT_BEFORE = rf"(?<![0-9０-９])(?<![0-9０-９]{_SEP})"  # 前后不能再接数字（隔一个分隔也不行）
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
    """全角数字换成半角，只留数字。"""
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
    """マイナンバーの検査用数字：前 11 位从右数第 n 位 Pn，权 Qn = n+1（1〜6）、n-5（7〜11）；
    余数 = ΣPn×Qn mod 11，≤ 1 时检查位是 0，否则是 11 - 余数。"""
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
    """命中的个人信息（按位置排，重叠的只留先出现、更长的那个）。"""
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
    """命中的部分换成「〔個人情報〕」。None 原样返回。"""
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
