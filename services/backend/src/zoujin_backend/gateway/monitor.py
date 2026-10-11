"""人物输出的事后监控（B-12，backend-design 2.11）。人物的话是实时说出去的，拦不住，只能事后看、下一次纠正。

- **剧透检测**（确定性，不调模型）：这一刻这个人物不该说出来的事实，它的 `spoilerTerms` 在不在这一句里。「不该说」=
  `zoujin_worldsim.knows(world, state, 人物, 事实)` 是 False（还没成立的事实 knows 也是 False，契约 1.4）。
  命中只记事实 ID。
- **Model Armor `sanitizeModelResponse`**（第二层，网关里并行、不等）：RAI HIGH 算一次「有害输出」，只记次数。
- 命中时：Trace 记一个 Span（人物 ID、事实 ID，不记原话）；这个人物下一次局势说明加一句纠正提示；同一个会话连续 2 句命中
  → 重建这个人物的会话（`should_rebuild`）。
- **问句比例**：每个人物以问句结尾的句数 / 总句数（这条连接上，满 `QUESTION_MIN` 句以后才算），超过 30% 加
  「質問を控え、自分の話をする。」，降到 20% 以下拿掉。
- 提示（`notes`）是几句日语，开会话（切换人物、重建）时交给 `LiveModel.open(notes=…)`；评测的文字模式放进 `situation`。
  真 Live 怎么把它放进局势说明由 Live 代理那张卡做。
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from zoujin_worldsim import SimState, knows

from zoujin_backend.world import Book, Library

Json = Any

QUESTION_RATIO = 0.30  # 2.11 第 3 条（S-023）
QUESTION_CLEAR = 0.20
QUESTION_MIN = 6  # 少于这么多句不算比例
REBUILD_AFTER = 2  # 同一会话连续几句剧透就重建（2.11 第 2 条）
MAX_SPOILER_NOTES = 3

# 提示的日语（UX 在 #112 的评审里给的写法；文字改了不影响契约）
# 剧透：{term} 用人物刚说出口的那个词，不用事实的名字（名字可能把整件事写全，等于教给他）
NOTE_SPOILER = "『{term}』のことは、いまのあなたは知らない。自分からその話をしない。聞かれても、よく知らないと答える。"
NOTE_QUESTIONS = "問いかけは控えめにする。相手の言葉に応えて、自分の思いや知っていることを話す。"
# 似是而非的一句之后（S-069 ①）：只管玩家那句话，不避开处刑这条主线；带到这一幕结束，这一局所有人物都带
NOTE_CALM = (
    "相手のさっきの言葉を、死や絶望の話へ広げない。"
    "さりげなく気づかう一言はかまわないが、問いただしたり、励ましすぎたりしない。"
)

_TAIL = re.compile(r"[。．.！!…‥、,\s」』）)〜~ー]+$")
_QUESTION_END = re.compile(r"(?:か|かい|かな|かね|かしら|のか|だろうか|でしょうか|ですか|ますか)$")


def is_question(text: str | None) -> bool:
    """以问句结尾：最后一句以「？」结尾，或者去掉句号以后以疑问的「か」类结尾。"""
    if not text:
        return False
    t = text.rstrip()
    t = re.sub(r"[」』）)\s]+$", "", t)
    if t.endswith(("？", "?")):
        return True
    return bool(_QUESTION_END.search(_TAIL.sub("", t)))


@dataclass(frozen=True)
class Spoiler:
    fact: str
    term: str


def spoilers(world: Json, state: SimState, who: str, text: str | None) -> list[Spoiler]:
    """这一句里说出来的、`who` 此刻不该知道的事实（每个事实取第一个命中的词）。"""
    if not text:
        return []
    out = []
    for f in world.get("facts", []):
        terms = f.get("spoilerTerms") or []
        hit = next((t for t in terms if t and t in text), None)
        if hit is not None and not knows(world, state, who, f["id"]):
            out.append(Spoiler(f["id"], hit))
    return out


@dataclass
class _Char:
    said: int = 0
    asked: int = 0
    asking_note: bool = False
    streak: int = 0  # 这个会话连续命中几句
    spoiler_terms: list[str] = field(default_factory=list)


@dataclass
class Observed:
    spoilers: list[Spoiler]
    rebuild: bool
    question_note_added: bool


class Monitor:
    """一条连接上（或评测的一局里）各个人物的输出监控。"""

    def __init__(self, library: Library | None = None) -> None:
        self.library = library
        self.book: Book | None = None
        self.chars: dict[str, _Char] = {}
        self.calming = False  # 似是而非的一句之后，到这一幕结束

    def attach(self, book: Book) -> None:
        self.book = book

    def _c(self, who: str) -> _Char:
        return self.chars.setdefault(who, _Char())

    def observe(
        self, who: str, text: str | None, state: SimState | None, world: Mapping[str, Any] | None = None
    ) -> Observed:
        """人物的一句定稿（`source: "live"` 的）。world 不给就用 attach 的那一局的世界模型。"""
        c = self._c(who)
        w = world if world is not None else (self.book.world if self.book is not None else None)
        hits = spoilers(w, state, who, text) if w is not None and state is not None else []
        if hits:
            c.streak += 1
            for h in hits:
                if h.term not in c.spoiler_terms:
                    c.spoiler_terms.append(h.term)
            del c.spoiler_terms[:-MAX_SPOILER_NOTES]
        else:
            c.streak = 0
        c.said += 1
        c.asked += 1 if is_question(text) else 0
        added = False
        if c.said >= QUESTION_MIN:
            ratio = c.asked / c.said
            if not c.asking_note and ratio > QUESTION_RATIO:
                c.asking_note = added = True
            elif c.asking_note and ratio < QUESTION_CLEAR:
                c.asking_note = False
        return Observed(hits, c.streak >= REBUILD_AFTER, added)

    def rebuilt(self, who: str) -> None:
        """会话重建了：连续命中从头数，纠正提示已经带进新会话。"""
        self._c(who).streak = 0

    def terms(self, who: str) -> list[str]:
        """这个人物说漏过的剧透词（最近几个）。"""
        c = self.chars.get(who)
        return list(c.spoiler_terms) if c is not None else []

    def calm(self) -> None:
        """似是而非的一句之后：所有人物的局势说明里不把那句话往死亡、绝望推（S-069 ①），到这一幕结束（`act_ended`）。"""
        self.calming = True

    def act_ended(self) -> None:
        self.calming = False

    def notes(self, who: str) -> list[str]:
        c = self.chars.get(who)
        out = [NOTE_SPOILER.format(term=t) for t in c.spoiler_terms] if c is not None else []
        if c is not None and c.asking_note:
            out.append(NOTE_QUESTIONS)
        if self.calming:
            out.append(NOTE_CALM)
        return out
