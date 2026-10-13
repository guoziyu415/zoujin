"""Characters' memories of the player (B-13, contract section 4, backend-design 2.10).

- **Written only from committed events**: from the events of one narrator commit, things the player did, things done
  for the player, and promises with the player are written for the other party in the event and the characters
  present. Which kind of event becomes which `kind`, `trustDelta` and `salience` is the lookup table below
  (deterministic; the model doesn't give numbers); `via` depends on whether the character was present at the time and
  whether the event states that they heard about it (`witnessed` / `told`; `rumor` doesn't occur in the slice).
- **The sentence is written by the model** (prompt `memory`, Claude Haiku, thinking off, 5 seconds, no resend): the
  input is only the events' `summary` and `visibleEffects`, the character's persona summary and `via`, never the
  player's words. If any of the three filters (personal-information rules, Model Armor, length and commands inside
  quotes) fails, that memory isn't written; the event stays. A model timeout or error also writes nothing; it is only
  counted.
- **Relationships aren't stored**: `trust` = the starting value (+10 if the role knows this character) + the sum of
  `trustDelta` of the undeleted memories, clamped to -100-100, with five levels per the contract's table.

Memory text only goes into `memory_items` and the `commit` pushed to this game, never into logs or Trace (Spans only
have IDs, counts and statuses).

登場人物のプレイヤーについての記憶（B-13、契約第 4 節、backend-design 2.10）。

- **コミット済みのイベントからだけ書く**：ナレーターの 1 回のコミットのイベントのうち、プレイヤーがしたこと、
  プレイヤーのためにされたこと、プレイヤーとの約束を、イベントの相手とその場にいる登場人物について書く。
  どのイベントをどの `kind`、`trustDelta`、`salience` にするかは下の対応表で決める（決定的で、
  数値はモデルに出させない）。
  `via` はその人物がそのときその場にいたか、イベントにその人物が聞いたと明記されているかで決める
  （`witnessed` / `told`。`rumor` はスライスでは出ない）。
- **一文はモデルが書く**（プロンプト `memory`、Claude Haiku、思考オフ、5 秒、再送なし）：入力はイベントの `summary`、
  `visibleEffects`、登場人物の人物設定の要約、`via` だけで、発話は渡さない。3 つのフィルター（個人情報の規則、
  Model Armor、長さと括弧内の命令文）のどれかを通らなければその記憶は書かず、イベントはそのまま残す。
  モデルのタイムアウトやエラーのときも書かず、数えるだけ。
- **関係は保存しない**：`trust` = 初期値（役柄がこの登場人物を知っていれば +10）+ 削除されていない記憶の `trustDelta`
  の合計で、-100〜100 に収め、5 段階は契約の表に従う。

記憶の文章は `memory_items` とこのゲームに送る `commit` にだけ入れ、ログや Trace には入れない（Span は ID、回数、
状態だけ）。
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import jsonschema
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection
from zoujin_backend.db import store
from zoujin_backend.db.events import recorded_at
from zoujin_backend.db.tables import memory_items
from zoujin_backend.models.armor import DEADLINE_S as ARMOR_DEADLINE_S
from zoujin_backend.models.armor import Armor, ArmorFailed, cost_usd
from zoujin_backend.models.prompts import PROMPTS
from zoujin_backend.models.text import BadOutput, ModelCallFailed, RateLimited, Stop, TextModel, model_and_version, spec
from zoujin_backend.narrator.roles import act_at
from zoujin_backend.narrator.rules import has_pii
from zoujin_backend.projection import committed, visible_effects
from zoujin_backend.trace import Tracer
from zoujin_backend.world import Book
from zoujin_worldsim import SimState, apply, lived, sees

Json = Any

# The data contract version written into rows (as in narrator/writer.py).
# 書き込むときのデータ契約バージョン（narrator/writer.py と同じ）。
SCHEMA_VERSION = "1.12"
# Max length of a memory line (characters after NFKC; UX review said 30, stricter than the data side's 40, so 30;
# longer counts as failing the filter).
# 記憶の一文の長さの上限（NFKC 後の文字数。UX レビューは 30 で、データ側の 40 より厳しいので 30 を採る。
# 超えたらフィルターを通らなかったとみなす）。
MAX_TEXT = 30
# Max length of the "consequences that won't be undone" line (UX review).
# 「取り消されない結果」の一文の上限（UX レビュー）。
MAX_KEEPS = 30
# Max memories written per commit (the top ones by salience) / 1 回のコミットで書く最大件数（salience の上位から）
MAX_PER_COMMIT = 3
# How many go into the situation notes (4 in saving mode, E6-007) / 状況説明に入れる件数（節約モードでは 4 件、E6-007）
BRIEF_LIMIT = 8
BRIEF_LIMIT_SAVING = 4
KNOWN_TRUST = 10  # starting trust for characters the role knows / 役柄が知っている登場人物の初期の信頼
TRUST_MIN, TRUST_MAX = -100, 100

# The five levels of contract section 4: (upper bound of trust (inclusive), level, label); the last has no bound.
# 契約第 4 節の 5 段階：（trust の上限（含む）, level, label）。最後の段階には上限がない。
LEVELS: tuple[tuple[int | None, int, str], ...] = (
    (-40, 1, "敵意を抱いている"),
    (-10, 2, "警戒している"),
    (9, 3, "様子を見ている"),
    (39, 4, "気を許している"),
    (None, 5, "信じている"),
)

# Event → memory lookup table (set by the data side, review #153): (kind, trustDelta, salience). For each character
# and turn, the topmost matching row wins.
# イベント → 記憶の対応表（データ側が決めた、レビュー #153）：(kind, trustDelta, salience)。登場人物ごと、ターンごとに
# 最も上の行を採る。
PROMISE_MADE = ("promise", 5, 0.8)  # made a promise with them (whoever made it) / その人物と約束した（誰がしても）
PROMISE_KEPT = ("help", 10, 0.8)  # the player kept a promise with them / プレイヤーがその人物との約束を守った
PROMISE_BROKEN = ("harm", -15, 0.9)  # the player broke a promise with them / プレイヤーがその人物との約束を破った
HELPED = ("help", 10, 0.7)  # actor = player, beneficiary = them / actor = player、beneficiary = その人物
# actor = player, and their trust-type variable went down or they were taken away (beneficiary isn't them).
# actor = player で、その人物の信頼系の変数が下がった、またはその人物が連れて行かれた（beneficiary はその人物でない）。
HARMED = ("harm", -10, 0.7)
HELPED_YOU = ("shared-moment", 3, 0.5)  # actor = them, beneficiary = player / actor = その人物、beneficiary = player
# A beat happened, the player can see it, and they lived through it (`zoujin_worldsim.lived`).
# ビートが起き、プレイヤーに見え、その人物が自分で経験した（`zoujin_worldsim.lived`）。
BEAT = ("shared-moment", 2, 0.6)
# The player talks about themself (a learn effect states they learned it, or an improv became their improvised fact).
# プレイヤーが自分のことを話す（learn の効果でその人物が知ったと明記、または improv がその人物の即興設定になった）。
CLAIM = ("claim", 0, 0.5)
# Other events with actor = player (talk, actions) / ほかの actor = player のイベント（発話、アクション）
IMPRESSION = ("impression", 0, 0.3)
ROWS = (PROMISE_MADE, PROMISE_KEPT, PROMISE_BROKEN, HELPED, HARMED, HELPED_YOU, BEAT, CLAIM, IMPRESSION)
KEY_MOMENT_BONUS = 0.2  # salience bonus for keyMoment (max 1) / keyMoment の salience 加点（上限 1）
# Model weight 1-3: salience gets another 0.1 × (weight - 1), max 1.
# モデルが出す weight 1〜3：salience にさらに 0.1 × (weight - 1) を足す。上限 1。
WEIGHT_STEP = 0.1
DELTA_MIN, DELTA_MAX = -20, 20  # the contract's trustDelta range / 契約の trustDelta の範囲

# Commands inside quotes (「〜しろ」 and the like): memories shouldn't have anyone ordering anyone around.
# 括弧内の命令文（「〜しろ」など）：記憶の中で誰かが誰かに命令していてはいけない。
_COMMAND = re.compile(r"[「『][^」』]{0,40}(?:しろ|せよ|なさい|てくれ|ください|やれ|ろ|け)[」』]")
# System events that don't produce memories (beats still do).
# 記憶を書かないシステムイベント（ビートは書く）。
SKIP_TYPES = frozenset({"forget", "act-transition", "ending", "correction"})


@dataclass(frozen=True)
class Seed:
    """A memory to write (no text yet): at most one per character per turn, combining this turn's events involving
    them (`events`).

    書く記憶 1 件（文章はまだない）：登場人物ごとに 1 ターン最大 1 件で、このターンのその人物に関わるイベントをまとめる
    （`events`）。
    """

    character: str
    kind: str
    events: tuple[Json, ...]
    trust_delta: int
    # The table value plus keyMoment; the model's weight is added when writing.
    # 対応表の値に keyMoment を足したもの。モデルの weight は書くときに足す。
    salience: float
    via: str
    promise_id: str | None = None
    t: int = 0

    @property
    def event(self) -> Json:
        return self.events[0]


@dataclass
class Written:
    """The result of writing memories: rows stored in `memory_items`, counts, and cost.

    記憶を書くステップの結果：`memory_items` に保存する行、件数、費用。
    """

    rows: list[Json] = field(default_factory=list)
    filtered: int = 0
    failed: int = 0
    armor_errors: int = 0
    cost_usd: float = 0.0
    armor_usd: float = 0.0


def relation(trust: int) -> tuple[str, int]:
    """trust → (label, level), per the table in contract section 4.

    trust → (label, level)。契約第 4 節の表に従う。
    """
    for top, level, label in LEVELS:
        if top is None or trust <= top:
            return label, level
    raise AssertionError("unreachable")


def clamp(trust: int) -> int:
    return max(TRUST_MIN, min(TRUST_MAX, trust))


def initial_trust(book: Book, role_id: str, character: str) -> int:
    return KNOWN_TRUST if character in book.roles[role_id].get("knownCharacters", []) else 0


def talkable(book: Book, character: str) -> bool:
    c = book.characters.get(character)
    return c is not None and bool(c.get("talkable")) and not c.get("group")


def _present(state: SimState, place: str) -> set[str]:
    return {c for c, p in state["locations"].items() if p == place}


def _party(p: Mapping[str, Any]) -> str | None:
    """The party to a promise other than the player (None for promises not involving the player).

    約束のプレイヤー以外の当事者（プレイヤーに関係ない約束なら None）。
    """
    if p.get("from") == "player":
        return str(p.get("to"))
    if p.get("to") == "player":
        return str(p.get("from"))
    return None


def _trust_var(character: str, var: str) -> bool:
    """Variables like `var.<them>.trust` (using the last segment of the character ID).

    `var.<その人物>.trust` のような変数（登場人物 ID の最後の部分を使う）。
    """
    short = character.rsplit(".", 1)[-1]
    return var.endswith(".trust") and short in var.split(".")


def _lived(book: Book, after: SimState, ev: Json) -> set[str]:
    """The characters who lived through the beat in this beat event (`zoujin_worldsim.lived`, #154). after = the state
    after this event.

    このビートのイベントでビートを自分で経験した登場人物（`zoujin_worldsim.lived`、#154）。
    after = このイベントの後の状態。
    """
    beats = [e["beat"] for e in ev["effects"] if e.get("op") == "beat"]
    return {c for c in book.characters if any(lived(book.world, after, c, x) for x in beats)}


def _event_rows(
    book: Book, state: SimState, after: SimState, ev: Json, addressee: str | None
) -> dict[str, tuple[int, str, str | None]]:
    """Which row an event gives to whom: character → (row index, via, promiseId). state / after are the states before
    / after this event.

    1 つのイベントで誰にどの行を与えるか：登場人物 → (行番号, via, promiseId)。
    state / after はこのイベントの前 / 後の状態。
    """
    if not committed(ev) or ev["type"] in SKIP_TYPES:
        return {}
    player_place = state["vars"]["var.player.location"]
    # What the player can't see isn't written / プレイヤーに見えないことは書かない
    if ev["actor"] != "player" and not sees(book.world, player_place, ev):
        return {}
    present = _present(state, ev["place"])
    beat = ev.get("origin") == "schedule" and any(e.get("op") == "beat" for e in ev["effects"])
    lived_ = _lived(book, after, ev) if beat else set()
    told = {e["character"] for e in ev["effects"] if e.get("op") == "learn"}

    def via(c: str) -> str | None:
        if c == ev["actor"] or c in present or c in lived_:
            return "witnessed"
        if c in told:
            return "told"
        return None  # the slice writes no rumor / スライスでは rumor を書かない

    out: dict[str, tuple[int, str, str | None]] = {}

    def put(c: str | None, row: tuple[str, int, float], promise_id: str | None = None) -> None:
        if c is None or c == "player" or not talkable(book, c):
            return
        v = via(c)
        if v is None:
            return
        i = ROWS.index(row)
        if c not in out or i < out[c][0]:
            out[c] = (i, v, promise_id)

    for e in ev["effects"]:
        if e.get("op") != "promise" or not e.get("promiseId"):
            continue
        if e["change"] == "made":
            put(_party(e), PROMISE_MADE, e["promiseId"])
            continue
        p = (state.get("promises") or {}).get(e["promiseId"])
        if p is None or p.get("from") != "player":
            continue
        if e["change"] == "kept":
            put(_party(p), PROMISE_KEPT)
        elif e["change"] == "broken":
            put(_party(p), PROMISE_BROKEN)
    b = ev.get("beneficiary")
    if ev["actor"] == "player":
        put(b, HELPED)
        for e in ev["effects"]:
            if e.get("op") == "inc" and e.get("by", 0) < 0:
                for c in present | told:
                    if _trust_var(c, str(e.get("var", ""))):
                        put(c, HARMED)
            elif e.get("op") == "relocate" and e.get("character") != b:
                put(e.get("character"), HARMED)
        # The player talks about themself: stated that they learned it (learn), or it became their improvised fact
        # (improv).
        # プレイヤーが自分のことを話す：その人物が知ったと明記（learn）、またはその人物の即興設定になった（improv）。
        if ev["type"] == "say":
            for c in told | {e["character"] for e in ev["effects"] if e.get("op") == "improv"}:
                put(c, CLAIM)
        # Impression: talk only gives one to the person addressed (this turn's character); actions give one to
        # everyone present.
        # 印象：発話は話しかけた相手（このターンの登場人物）だけに、アクションはその場にいる人に与える。
        hearers = {addressee} if ev["type"] == "say" and addressee else present
        for c in sorted(hearers):
            put(c, IMPRESSION)
    elif b == "player":
        put(ev["actor"], HELPED_YOU)
    if beat:
        for c in sorted(lived_):
            put(c, BEAT)
    return out


def seeds(book: Book, before: SimState, events: Sequence[Json], addressee: str | None = None) -> list[Seed]:
    """The memories to write for one commit (one turn): at most one per character, combining this turn's events
    involving them, with kind from the topmost table row; the top `MAX_PER_COMMIT` characters by salience (ties in
    order of first appearance). addressee: who the player talked to this turn.

    1 回のコミット（1 ターン）で書く記憶：登場人物ごとに最大 1 件。このターンのその人物に関わるイベントをまとめ、kind は
    対応表の最も上の行を採る。salience の上位 `MAX_PER_COMMIT` 人を採る（同点なら最初に出た順）。
    addressee：このターンでプレイヤーが話しかけた相手。
    """
    state = before
    best: dict[str, tuple[int, str, str | None, Json]] = {}
    evs: dict[str, list[Json]] = {}
    for ev in events:
        after = apply(book.world, state, ev)
        for c, (i, v, pr) in _event_rows(book, state, after, ev, addressee).items():
            evs.setdefault(c, []).append(ev)
            if c not in best or i < best[c][0]:
                best[c] = (i, v, pr, ev)
        state = after
    out: list[Seed] = []
    for c, (i, v, pr, ev) in best.items():
        kind, delta, salience = ROWS[i]
        mine = evs[c]
        if any(e.get("keyMoment") for e in mine):
            salience = min(1.0, salience + KEY_MOMENT_BONUS)
        lead = [ev, *(e for e in mine if e is not ev)]
        out.append(
            Seed(
                c,
                kind,
                tuple(lead),
                max(DELTA_MIN, min(DELTA_MAX, delta)),
                round(salience, 3),
                v,
                pr,
                int(ev["t"]),
            )
        )
    ranked = sorted(enumerate(out), key=lambda x: (-x[1].salience, x[0]))
    return [s for _, s in ranked[:MAX_PER_COMMIT]]


def weighted(s: Seed, weight: int) -> float:
    """Add the model's weight (1-3) to salience, clamped between this row's value and 1.

    モデルが出した weight（1〜3）を salience に足し、この行の値から 1 の間に収める。
    """
    return round(max(s.salience, min(1.0, s.salience + WEIGHT_STEP * (max(1, min(3, weight)) - 1))), 3)


# Memories planted directly by setup (eval entry point): take the numbers of the first table row of the same kind.
# setup が直接植える記憶（評価の入口）：kind ごとに対応表で同じ種類の最初の行の数値を使う。
BY_KIND = {
    "promise": PROMISE_MADE,
    "help": HELPED,
    "harm": PROMISE_BROKEN,
    "shared-moment": HELPED_YOU,
    "claim": CLAIM,
    "impression": IMPRESSION,
}


def seeded(ids: Any, pid: str, ev: Json, character: str, kind: str, text: str) -> Json:
    """A memory planted by eval setup (its source is the staged event, `via` = witnessed).

    評価の setup が植える記憶 1 件（出どころは用意したイベント、`via` = witnessed）。
    """
    _, delta, salience = BY_KIND[kind]
    return {
        "memory_id": ids.new("mem"),
        "playthrough_id": pid,
        "schema_version": SCHEMA_VERSION,
        "character": character,
        "kind": kind,
        "text": text,
        "from_events": [ev["eventId"]],
        "t": ev["t"],
        "trust_delta": delta,
        "salience": salience,
        "via": "witnessed",
        "promise_id": None,
    }


def command_like(text: str) -> bool:
    return _COMMAND.search(text) is not None


def tidy(text: str) -> str:
    """Strip 「」『』 around the whole sentence and the final 「。」 (the frontend adds quotes; UX review).

    文全体を囲む「」『』と文末の「。」を取り除く（フロントエンドが括弧を付ける。UX レビュー）。
    """
    t = text.strip()
    while len(t) >= 2 and t[0] in "「『" and t[-1] in "」』":
        t = t[1:-1].strip()
    return t.rstrip("。．.").strip()


def length(text: str) -> int:
    """Length in characters after NFKC (punctuation included; data review).

    長さは NFKC 後の文字数（句読点を含む。データレビュー）。
    """
    return len(unicodedata.normalize("NFKC", text))


def rule_ok(text: str, role_name: str | None = None) -> bool:
    """The first and third filters: personal-information rules (the same as R6), length (too long isn't truncated),
    commands inside quotes, and the role name (UX review: memories refer to the player as 「あなた」 or 「あの人」;
    contract 1.8's role-name replacement only covers summary).

    1 段目と 3 段目のフィルター：個人情報の規則（R6 と同じ）、長さ（超えても切り詰めない）、括弧内の命令文、役柄名
    （UX レビュー：記憶でプレイヤーに触れるときは「あなた」「あの人」を使う。
    契約 1.8 の役柄名の置き換えは summary だけが対象）。
    """
    t = text.strip()
    return (
        bool(t)
        and length(t) <= MAX_TEXT
        and not has_pii(t)
        and not command_like(t)
        and not (role_name and role_name in t)
    )


# Not allowed in the "consequences that won't be undone" line: pronouns (use names), remembering and forgetting (UX
# review). 「彼方」 and 「彼岸」 don't count as pronouns (UX second look).
# 「取り消されない結果」の一文に入れてはいけないもの：代名詞（名前を使う）、覚える・忘れる（UX レビュー）。
# 「彼方」「彼岸」は代名詞に数えない（UX の再確認）。
_KEEPS_BANNED = re.compile(r"彼(?![方岸])|覚え|忘れ")


def keeps_ok(text: str) -> bool:
    t = text.strip()
    return bool(t) and length(t) <= MAX_KEEPS and not has_pii(t) and not command_like(t) and not _KEEPS_BANNED.search(t)


def persona(book: Book, character: str) -> Json:
    c = book.characters[character]
    out: Json = {"id": character, "name": c["name"], "summary": c.get("summary", "")}
    first = (c.get("speech") or {}).get("firstPerson")
    if first:
        out["firstPerson"] = first
    return out


def request(book: Book, role_id: str, s: Seed) -> Json:
    """The request for the `memory` prompt: summary and visibleEffects of this turn's events involving them, the
    character's persona summary, and via. Never the player's words. `role` only tells the model who the player is;
    the prompt asks for it not to be written into the sentence (the filter blocks it too).

    プロンプト `memory` へのリクエスト：このターンのその人物に関わるイベントの summary と visibleEffects、登場人物の
    人物設定の要約、via。発話は渡さない。`role` はプレイヤーが誰かをモデルに知らせるだけで、プロンプトで文に書かないよう
    求めている（フィルターも止める）。
    """
    return {
        "character": persona(book, s.character),
        "role": book.roles[role_id]["name"],
        "kind": s.kind,
        "via": s.via,
        "events": [{"summary": e["summary"], "visibleEffects": visible_effects(book, e["effects"])} for e in s.events],
    }


@dataclass
class Memorizer:
    """The model call and filters for writing memories. Shared by the narrator and the eval entry point.

    記憶を書くためのモデル呼び出しとフィルター。ナレーターと評価の入口で共用する。
    """

    text: TextModel
    armor: Armor | None
    ids: Any
    tracer: Tracer = field(default_factory=Tracer)
    deadline: float | None = None  # None = the deadline in config.TEXT["memory"] / config.TEXT["memory"] の時間制限
    armor_deadline: float = ARMOR_DEADLINE_S
    # True (evals): stop the whole run when the ledger hits its limit or on a 429.
    # True（評価）：台帳が上限に達したときや 429 で全体を止める。
    raise_stops: bool = False

    async def write(self, book: Book, pid: str, role_id: str, todo: Sequence[Seed], **span: object) -> Written:
        out = Written()
        got = await asyncio.gather(*(self._one(book, role_id, s, out, **span) for s in todo))
        for s, one in zip(todo, got, strict=True):
            if one is None:
                continue
            text, weight = one
            out.rows.append(
                {
                    "memory_id": self.ids.new("mem"),
                    "playthrough_id": pid,
                    "schema_version": SCHEMA_VERSION,
                    "character": s.character,
                    "kind": s.kind,
                    "text": text,
                    "from_events": [e["eventId"] for e in s.events],
                    "t": s.t,
                    "trust_delta": s.trust_delta,
                    "salience": weighted(s, weight),
                    "via": s.via,
                    "promise_id": s.promise_id,
                }
            )
        return out

    async def _one(self, book: Book, role_id: str, s: Seed, out: Written, **span: object) -> tuple[str, int] | None:
        kind = "memory"
        model, version = model_and_version(kind)
        req = request(book, role_id, s)
        deadline = self.deadline if self.deadline is not None else spec(kind).deadline
        with self.tracer.span(
            "narrator.memory",
            provider=spec(kind).provider,
            model=model,
            prompt_version=version,
            character=s.character,
            event_id=s.event["eventId"],
            **span,
        ) as sp:
            try:
                r = await asyncio.wait_for(self.text.call(kind, req), deadline)
                out.cost_usd += r.cost_usd
                jsonschema.validate(r.output, PROMPTS[kind].schema)
            except TimeoutError:
                out.cost_usd += self.text.cancelled_cost(kind, req)
                out.failed += 1
                sp.set(status="timeout")
                return None
            except BadOutput as e:
                out.cost_usd += e.cost_usd
                out.failed += 1
                sp.set(status="invalid")
                return None
            except jsonschema.ValidationError:
                out.failed += 1
                sp.set(status="invalid")
                return None
            except (ModelCallFailed, RateLimited, Stop) as e:
                if self.raise_stops and not isinstance(e, ModelCallFailed):
                    raise
                out.failed += 1
                sp.set(status="error")
                return None
            text = tidy(str(r.output["text"]))
            ok = rule_ok(text, book.roles[role_id]["name"]) and await self._armor_ok(text, out)
            sp.set(status="ok" if ok else "filtered", cost_usd=round(r.cost_usd, 6))
            if not ok:
                out.filtered += 1
                return None
            return text, int(r.output.get("weight", 1))

    async def _armor_ok(self, text: str, out: Written) -> bool:
        """The second filter (`sanitizeModelResponse`): if any of injection, RAI HIGH, SDP or a malicious URL matches,
        don't write it. No answer within 1 second, or an error, counts as no match (`armor_errors` records one).

        2 段目のフィルター（`sanitizeModelResponse`）：インジェクション、RAI HIGH、SDP、悪意のあるリンクのどれかに
        当たれば書かない。1 秒以内に返事がない、またはエラーなら当たらなかったとみなす（`armor_errors` に 1 回記録）。
        """
        if self.armor is None:
            return True
        out.armor_usd += cost_usd(self.armor, text)
        try:
            ar = await asyncio.wait_for(self.armor.screen_response(text), self.armor_deadline)
        except (TimeoutError, ArmorFailed):
            out.armor_errors += 1
            return True
        return not (ar.injection or ar.harmful or ar.pii or ar.uri)


# —— Storing / 保存 ——


async def save(c: AsyncConnection, book: Book, pid: str, rows: Sequence[Json]) -> list[tuple[Json, str]]:
    """Store the memories written this turn: (row, "added" / "updated").

    At most one undeleted impression (`impression`) per character per act (set by the data side, a UX requirement
    before R1): if the character already has an impression this act, update it with the new sentence (`updated`, so
    the 記憶帳 doesn't grow another card), appending the source events, taking the larger salience, not adding
    trustDelta again (small talk mustn't keep raising the relationship), and clearing the consequences line (keeps)
    to be recomputed. Other kinds are added anew every time as before.

    このターンで書いた記憶を保存する：(行, "added" / "updated")。

    印象（`impression`）は登場人物ごと、幕ごとに削除されていないものを最大 1 件だけ残す（データ側が決めた、UX の R1 前の
    要件）：この幕ですでに印象が 1 件あれば、新しい一文でその件を更新し（`updated`、記憶帳のカードを増やさない）、
    出どころのイベントをつなげ、salience は大きいほうを採り、trustDelta は足さない（雑談で関係が上がり続けないように）。
    結果の一文（keeps）は消して計算し直す。ほかの種類は従来どおり毎回新しく加える。
    """
    out: list[tuple[Json, str]] = []
    for r in rows:
        old = await _impression_this_act(c, book, pid, r) if r["kind"] == "impression" else None
        if old is None:
            await c.execute(insert(memory_items).values(**r))
            out.append((r, "added"))
            continue
        merged = {
            **old,
            "text": r["text"],
            "from_events": [*old["from_events"], *r["from_events"]],
            "t": r["t"],
            "salience": max(float(old["salience"]), float(r["salience"])),
            "keeps": None,
            "keeps_done": False,
        }
        await c.execute(
            update(memory_items)
            .where(memory_items.c.memory_id == old["memory_id"])
            .values({k: merged[k] for k in ("text", "from_events", "t", "salience", "keeps", "keeps_done")})
        )
        out.append((merged, "updated"))
    return out


async def _impression_this_act(c: AsyncConnection, book: Book, pid: str, r: Json) -> Json | None:
    act = act_at(book, int(r["t"]))
    for m in reversed(await alive(c, pid, r["character"])):
        if m["kind"] == "impression" and act_at(book, int(m["t"])) == act:
            return m
    return None


# —— Reading / 読み込み ——


async def alive(c: AsyncConnection, pid: str, who: str | None = None) -> list[Json]:
    """This game's undeleted memories (ordered by t, then creation order).

    このゲームの削除されていない記憶（t の順、次に作成順）。
    """
    q = select(memory_items).where(memory_items.c.playthrough_id == pid, memory_items.c.deleted_at.is_(None))
    if who is not None:
        q = q.where(memory_items.c.character == who)
    rows = (await c.execute(q.order_by(memory_items.c.t, memory_items.c.created_at))).mappings().all()
    return [dict(r) for r in rows]


async def trust_of(c: AsyncConnection, book: Book, pid: str, role_id: str, who: str) -> int:
    total = await c.scalar(
        select(func.coalesce(func.sum(memory_items.c.trust_delta), 0)).where(
            memory_items.c.playthrough_id == pid,
            memory_items.c.character == who,
            memory_items.c.deleted_at.is_(None),
        )
    )
    return clamp(initial_trust(book, role_id, who) + int(total or 0))


async def relation_of(c: AsyncConnection, book: Book, pid: str, role_id: str, who: str) -> tuple[str, int]:
    return relation(await trust_of(c, book, pid, role_id, who))


async def memories_for_brief(c: AsyncConnection, pid: str, who: str, limit: int = BRIEF_LIMIT) -> list[str]:
    """What goes into the situation notes: this character's undeleted memories, the top limit by salience (newer first
    on ties), as text sorted by time.

    状況説明に入れるもの：この登場人物の削除されていない記憶を salience の上位 limit 件（同点なら新しいものが先）取り、
    時刻順に並べた文章。
    """
    rows = (
        await c.execute(
            select(memory_items.c.text, memory_items.c.t)
            .where(
                memory_items.c.playthrough_id == pid,
                memory_items.c.character == who,
                memory_items.c.deleted_at.is_(None),
            )
            .order_by(memory_items.c.salience.desc(), memory_items.c.t.desc(), memory_items.c.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [str(text) for text, _ in sorted(rows, key=lambda r: r[1]) if text]


async def forgotten_facts(c: AsyncConnection, book: Book, pid: str, who: str) -> frozenset[str]:
    """Facts (`learn`) and improvised facts (`improv`) the character learned in the source events of deleted memories,
    minus those other committed events also taught them (left out of the situation notes, `gateway/brief.py`).

    削除された記憶の出どころのイベントでその人物が知った事実（`learn`）と即興設定（`improv`）から、ほかのコミット済み
    イベントでも教わったものを除いたもの（状況説明には入れない、`gateway/brief.py`）。
    """
    gone = (
        await c.scalars(
            select(memory_items.c.from_events).where(
                memory_items.c.playthrough_id == pid,
                memory_items.c.character == who,
                memory_items.c.deleted_at.is_not(None),
            )
        )
    ).all()
    dropped = {str(e) for evs in gone for e in evs}
    if not dropped:
        return frozenset()
    learned: dict[str, set[str]] = {}  # fact → events that taught them / 事実 → それを教えたイベント
    for ev in await store.event_log(c, pid, book.version):
        if not committed(ev):
            continue
        for e in ev["effects"]:
            if e.get("op") == "learn" and e.get("character") == who:
                learned.setdefault(str(e["fact"]), set()).add(str(ev["eventId"]))
            # Improvised fact: what the player told them (rf_ ID) / 即興設定：プレイヤーがその人物に話したこと（rf_ ID）
            elif e.get("op") == "improv" and e.get("character") == who:
                learned.setdefault(str(e["factId"]), set()).add(str(ev["eventId"]))
    return frozenset(f for f, by in learned.items() if by and by <= dropped)


def item_json(row: Mapping[str, Any]) -> Json:
    """A `memory_items` row → the contract's MemoryItem (the eval entry point's `memories()`).

    `memory_items` の 1 行 → 契約の MemoryItem（評価の入口の `memories()`）。
    """
    out: Json = {
        "schemaVersion": row["schema_version"],
        "memoryId": row["memory_id"],
        "playthroughId": row["playthrough_id"],
        "character": row["character"],
        "kind": row["kind"],
        "text": row["text"] or "",
        "fromEvents": list(row["from_events"]),
        "t": row["t"],
        "trustDelta": row["trust_delta"],
        "salience": float(row["salience"]),
        "createdAt": recorded_at(row["created_at"]),
    }
    if row["via"]:
        out["via"] = row["via"]
    if row["promise_id"]:
        out["promiseId"] = row["promise_id"]
    if row["deleted_at"] is not None:
        out["deletedAt"] = recorded_at(row["deleted_at"])
    return out


# —— The 記憶帳 (memory book) / 記憶帳 ——


async def keeps(
    text: TextModel,
    tracer: Tracer,
    book: Book,
    row: Mapping[str, Any],
    evs: Sequence[Json],
    promise: Mapping[str, Any] | None,
    **span: object,
) -> tuple[str | None, bool, float]:
    """The "consequences that won't be undone" line in the deletion confirmation (prompt `keeps`, reading only the
    source events' summaries and results). Returns (the line or None, whether it may be cached, the cost): model error,
    timeout, invalid output, or failing the filter → None, not cached (computed again next time); the model says there
    is none → None, cached.

    削除の確認に出す「取り消されない結果」の一文（プロンプト `keeps`。出どころのイベントの要約と結果だけを読む）。
    （一文または None, キャッシュしてよいか, 費用）を返す：モデルのエラー、タイムアウト、不合格の出力、フィルターを
    通らない → None でキャッシュしない（次回また計算する）。モデルがないと言った → None でキャッシュする。
    """
    kind = "keeps"
    model, version = model_and_version(kind)
    req: Json = {
        "character": book.characters[row["character"]]["name"],
        "events": [{"summary": e["summary"], "visibleEffects": visible_effects(book, e["effects"])} for e in evs],
        "promise": {"text": promise["text"], "status": promise["status"]} if promise else None,
        # When the promise will be voided, the line doesn't mention it (the next line is
        # 「この約束も、なかったことになります」, UX review).
        # 約束が無効になるときは、文にその約束を書かない（次の行が「この約束も、なかったことになります」、
        # UX レビュー）。
        "voidsPromise": bool(promise and promise["status"] == "open"),
    }
    with tracer.span("gateway.keeps", provider=spec(kind).provider, model=model, prompt_version=version, **span) as sp:
        try:
            r = await asyncio.wait_for(text.call(kind, req), spec(kind).deadline)
            jsonschema.validate(r.output, PROMPTS[kind].schema)
        except TimeoutError:
            sp.set(status="timeout")
            return None, False, text.cancelled_cost(kind, req)
        except BadOutput as e:
            sp.set(status="invalid")
            return None, False, e.cost_usd
        except jsonschema.ValidationError:
            sp.set(status="invalid")
            return None, False, r.cost_usd
        except (ModelCallFailed, RateLimited, Stop):
            sp.set(status="error")
            return None, False, 0.0
        sp.set(status="ok", cost_usd=round(r.cost_usd, 6))
        got = r.output["keeps"]
        if got is None:
            return None, True, r.cost_usd
        got = tidy(str(got))
        if not keeps_ok(got):
            sp.set(status="filtered")
            return None, False, r.cost_usd
        return got, True, r.cost_usd
