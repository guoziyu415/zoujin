"""After-the-fact monitoring of character output (B-12, backend-design 2.11). Characters' words go out live and
can't be stopped; they can only be checked afterwards and corrected next time.

- **Spoiler detection** (deterministic, no model call): whether the `spoilerTerms` of a fact this character must not
  say at this moment appear in the line. "Must not say" = `zoujin_worldsim.knows(world, state, character, fact)` is
  False (knows is also False for facts not yet true, contract 1.4). A hit records only the fact ID.
- **Model Armor `sanitizeModelResponse`** (second layer, run in parallel in the gateway, not awaited): RAI HIGH counts
  as one "harmful output"; only the count is recorded.
- On a hit: Trace records a `monitor.hit` Span (turn, character ID, fact ID or RAI category, whether rebuilt; never the
  words said or the term); the character's next situation description gets a corrective hint; 2 hits in a row in the
  same session → rebuild the character's session (`should_rebuild`).
- **Question ratio**: per character, finals ending in a question / all finals (`is_question`, on this connection,
  counted only after `QUESTION_MIN` lines); above 30% add `NOTE_QUESTIONS`, below 20% remove it.
- The hints (`notes`) are a few Japanese sentences, handed to `LiveModel.open(notes=…)` when a session opens (switching
  characters, rebuilding); in the evals' text mode they go into `situation`. How real Live puts them into the
  situation description is up to the Live proxy card.

登場人物の出力の事後モニタリング（B-12、backend-design 2.11）。登場人物の言葉はリアルタイムで出ていくので
止められず、あとで確認して次回に訂正するしかない。

- **ネタバレ検出**（決定的、モデルは呼ばない）：この時点でこの登場人物が言ってはならない事実の `spoilerTerms` が
  その発言にあるかどうか。「言ってはならない」= `zoujin_worldsim.knows(world, state, 登場人物, 事実)` が False
  （まだ成り立っていない事実も knows は False、契約 1.4）。ヒットしたら事実 ID だけを記録する。
- **Model Armor `sanitizeModelResponse`**（第 2 層、ゲートウェイ内で並行に実行し、待たない）：RAI HIGH を
  「有害な出力」1 回と数え、回数だけを記録する。
- ヒットしたとき：Trace に `monitor.hit` Span を記録する（ターン、登場人物 ID、事実 ID または RAI の分類、
  作り直したかどうか。発言そのものや語は記録しない）。その登場人物の次の状況説明に訂正のヒントを 1 文加える。
  同じセッションで 2 文続けてヒットしたら → その登場人物のセッションを作り直す（`should_rebuild`）。
- **質問の割合**：登場人物ごとに、問いで終わる確定文 / 確定文の総数（`is_question`。この接続上で、
  `QUESTION_MIN` 文に達してから数える）。30% を超えたら `NOTE_QUESTIONS` を加え、20% 未満になったら外す。
- ヒント（`notes`）は日本語の数文で、セッションを開くとき（登場人物の切り替え、作り直し）に
  `LiveModel.open(notes=…)` に渡す。評価の文字モードでは `situation` に入れる。本物の Live がそれを状況説明に
  どう入れるかは Live プロキシのカードで扱う。
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from zoujin_worldsim import SimState
from zoujin_worldsim import spoilers as shared_spoilers

from zoujin_backend.world import Book, Library

Json = Any

QUESTION_RATIO = 0.30  # 2.11 item 3 (S-023) / 2.11 第 3 項（S-023）
QUESTION_CLEAR = 0.20
QUESTION_MIN = 6  # below this many lines no ratio is computed / これ未満の文数では割合を数えない
# Rebuild after this many spoiler lines in a row in one session (2.11 item 2).
# 同じセッションでネタバレがこの文数続いたら作り直す（2.11 第 2 項）。
REBUILD_AFTER = 2
MAX_SPOILER_NOTES = 3

# The Japanese of the hints (wording given by UX in the #112 review; changing the text doesn't affect the contract).
# Spoilers: never named (data review #112: writing out the term would tell the character what hasn't happened yet).
# The term lives only in Trace as the fact ID and counts.
# The Japanese is the data side's first draft; UX decides.
# ヒントの日本語（UX が #112 のレビューで示した書き方。文言を変えても契約には影響しない）。
# ネタバレ：名指ししない（データのレビュー #112：その語を書くと、まだ起きていないことを登場人物に教えることになる）。
# 語は Trace の事実 ID と回数にしか残らない。
# 日本語はデータ側の初稿で、UX が決める。
NOTE_SPOILER = (
    "さっき、まだ知らないはずのことを口にした。"
    "話すのは、自分の目で見たこと、人から聞いたこと、自分の思いだけにする。"
    "その話を振られたら、よく分からないと答える。"
)
NOTE_QUESTIONS = "問いかけは控えめにする。相手の言葉に応えて、自分の思いや知っていることを話す。"
# After an ambiguous line (S-069 ①): covers only what the player said, without avoiding the main plot of the
# execution; carried until the end of the act, by every character in the playthrough.
# どちらとも取れる発言のあと（S-069 ①）：プレイヤーのその言葉だけを扱い、処刑という本筋は避けない。幕が終わるまで、
# このプレイのすべての登場人物に付ける。
NOTE_CALM = (
    "相手のさっきの言葉を、死や絶望の話へ広げない。"
    "さりげなく気づかう一言はかまわないが、問いただしたり、励ましすぎたりしない。"
)

_SENTENCE_END = re.compile(r"(?<=[。．！!？?])")
_CLOSE = re.compile(r"[」』）)\s]+$")
_NOT_QUESTION = (
    "そうか",
    "ものか",
    "ではないか",
    "じゃないか",
    "ではありませんか",
    "じゃありませんか",
)  # agreement, rhetorical questions (data review #112) / 相槌、反語（データのレビュー #112）
_PUNCT = re.compile(r"[\W_]+", re.UNICODE)


def last_sentence(text: str) -> str:
    parts = [p for p in _SENTENCE_END.split(_CLOSE.sub("", text.strip())) if p.strip()]
    return _CLOSE.sub("", parts[-1].strip()) if parts else ""


def is_question(text: str | None) -> bool:
    """Turning the conversation back to the player (S-023): the last sentence of a character's final ends with
    「？」 or 「?」, or, after stripping full stops, exclamation marks and ellipses, ends with 「か」「かい」「かね」
    「かしら」 (「のか」「だろうか」「ですか」 etc. all end with 「か」; 「そうか」「ものか」「ではないか」
    「じゃないか」「ではありませんか」「じゃありませんか」 are excluded). 「〜の。」 and 「かな」 don't count
    (statements, talking to oneself). Definition in data-design 9.1.

    話をプレイヤーに投げ返す（S-023）：登場人物の確定文の最後の文が「？」「?」で終わる、または句点・感嘆符・
    三点リーダーを除いたあと「か」「かい」「かね」「かしら」で終わる（「のか」「だろうか」「ですか」などはみな「か」で
    終わる。「そうか」「ものか」「ではないか」「じゃないか」「ではありませんか」「じゃありませんか」は除く）。
    「〜の。」「かな」は数えない（叙述、独り言）。定義は data-design 9.1。
    """
    if not text:
        return False
    last = last_sentence(text)
    if last.endswith(("？", "?")):
        return True
    body = last.rstrip("。．.！!…‥")
    if not body.endswith(("か", "かい", "かね", "かしら")):
        return False
    return not body.endswith(_NOT_QUESTION)


def question_key(text: str) -> str:
    """Comparison key for repeated questions: hash of the last sentence after NFKC with punctuation and whitespace
    removed (only the hash is kept in memory, never the text).

    繰り返しの質問を比べるキー：最後の文を NFKC にして句読点と空白を除いたもののハッシュ（メモリにはハッシュだけを
    残し、文は残さない）。
    """
    norm = _PUNCT.sub("", unicodedata.normalize("NFKC", last_sentence(text)))
    return hashlib.sha256(norm.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Spoiler:
    fact: str
    term: str


def spoilers(world: Json, state: SimState, who: str, text: str | None, said: str | None = None) -> list[Spoiler]:
    """Facts said in this line that `who` must not know at this moment (`spoilers` from the shared rules library;
    terms the player said in the same turn don't count; the first term of each fact is taken).

    この発言で口にされた、`who` がいま知っているはずのない事実（共通ルールライブラリの `spoilers`。同じターンで
    プレイヤーが言った語は数えない。各事実の最初の語を取る）。
    """
    if not text:
        return []
    return [Spoiler(f, terms[0]) for f, terms in shared_spoilers(world, state, who, text, said or "").items()]


@dataclass
class _Char:
    said: int = 0
    asked: int = 0
    asking_note: bool = False
    streak: int = 0  # hits in a row in this session / このセッションで続けてヒットした文数
    spoiler_terms: list[str] = field(default_factory=list)
    asked_keys: set[str] = field(default_factory=set)


@dataclass
class Observed:
    spoilers: list[Spoiler]
    rebuild: bool
    question_note_added: bool
    question: bool = False
    repeated: bool = False

    def counts(self) -> dict[str, float]:
        """The items added to `playthrough_metrics` (column names per data review #112).

        `playthrough_metrics` に加える項目（列名はデータのレビュー #112 に従う）。
        """
        out: dict[str, float] = {"output_lines": 1}
        for col, on in (
            ("output_spoilers", bool(self.spoilers)),
            ("output_questions", self.question),
            ("output_questions_repeated", self.repeated),
            ("output_question_notes", self.question_note_added),
        ):
            if on:
                out[col] = 1
        return out


class Monitor:
    """Output monitoring for each character on one connection (or in one eval playthrough).

    1 本の接続上（または評価の 1 プレイ内）の、登場人物ごとの出力モニタリング。
    """

    def __init__(self, library: Library | None = None) -> None:
        self.library = library
        self.book: Book | None = None
        self.chars: dict[str, _Char] = {}
        self.calming = False  # after an ambiguous line, until the act ends / どちらとも取れる発言のあと、幕の終わりまで

    def attach(self, book: Book) -> None:
        self.book = book

    def _c(self, who: str) -> _Char:
        return self.chars.setdefault(who, _Char())

    def observe(
        self,
        who: str,
        text: str | None,
        state: SimState | None,
        world: Mapping[str, Any] | None = None,
        *,
        said: str | None = None,
    ) -> Observed:
        """One final from a character (with `source: "live"`); said = the player's final for this turn. Without world,
        the world model of the playthrough passed to attach is used.

        登場人物の確定文 1 つ（`source: "live"` のもの）。said = このターンのプレイヤーの確定文。world がなければ attach
        したプレイの世界モデルを使う。
        """
        c = self._c(who)
        w = world if world is not None else (self.book.world if self.book is not None else None)
        hits = spoilers(w, state, who, text, said) if w is not None and state is not None else []
        if hits:
            c.streak += 1
            for h in hits:
                if h.term not in c.spoiler_terms:
                    c.spoiler_terms.append(h.term)
            del c.spoiler_terms[:-MAX_SPOILER_NOTES]
        else:
            c.streak = 0
        c.said += 1
        question = is_question(text)
        repeated = False
        if question and text:
            key = question_key(text)
            repeated = key in c.asked_keys
            c.asked_keys.add(key)
        c.asked += 1 if question else 0
        added = False
        if c.said >= QUESTION_MIN:
            ratio = c.asked / c.said
            if not c.asking_note and ratio > QUESTION_RATIO:
                c.asking_note = added = True
            elif c.asking_note and ratio < QUESTION_CLEAR:
                c.asking_note = False
        return Observed(hits, c.streak >= REBUILD_AFTER, added, question, repeated)

    def rebuilt(self, who: str) -> None:
        """The session was rebuilt: consecutive hits count from zero; the corrective hint is already in the new session.

        セッションを作り直した：連続ヒットは数え直し、訂正のヒントはもう新しいセッションに入っている。
        """
        self._c(who).streak = 0

    def terms(self, who: str) -> list[str]:
        """Spoiler terms this character let slip (the latest few).

        この登場人物がうっかり口にしたネタバレの語（直近のいくつか）。
        """
        c = self.chars.get(who)
        return list(c.spoiler_terms) if c is not None else []

    def calm(self) -> None:
        """After an ambiguous line: every character's situation description avoids pushing that line toward death or
        despair (S-069 ①), until the act ends (`act_ended`).

        どちらとも取れる発言のあと：すべての登場人物の状況説明で、その言葉を死や絶望へ押しやらない（S-069 ①）。幕が
        終わるまで（`act_ended`）。
        """
        self.calming = True

    def act_ended(self) -> None:
        self.calming = False

    def notes(self, who: str) -> list[str]:
        c = self.chars.get(who)
        out = [NOTE_SPOILER] if c is not None and c.spoiler_terms else []
        if c is not None and c.asking_note:
            out.append(NOTE_QUESTIONS)
        if self.calming:
            out.append(NOTE_CALM)
        return out
