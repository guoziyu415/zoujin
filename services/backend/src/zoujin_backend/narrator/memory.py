"""人物对玩家的记忆（B-13，契约第 4 节、backend-design 2.10）。

- **只从已提交的事件写**：叙事者一次提交的事件里，玩家做的、为玩家做的、和玩家的约定，给事件里的对方和在场的人物写。
  哪种事件写成哪种 `kind`、`trustDelta`、`salience` 是下面的对照表（确定性的，不让模型给数）；
  `via` 按他当时在不在场、事件里有没有写明他听说了确定（`witnessed` / `told`；`rumor` 切片里不出）。
- **一句话由模型写**（提示 `memory`，Claude Haiku，关思考，5 秒，不重发）：输入只有事件的 `summary`、`visibleEffects`、
  人物的人设摘要和 `via`，不给原话。三道过滤（个人信息规则、Model Armor、长度和引号里的命令句）任一不过就不写这条，
  事件照留。模型超时、出错也不写，只计数。
- **关系不存**：`trust` = 起始值（身份认识这个人物 +10）+ 没删的记忆的 `trustDelta` 之和，夹在 -100〜100，
  五档按契约的表。

记忆的文字只进 `memory_items` 和推给这一局的 `commit`，不进日志和 Trace（Span 只有 ID、次数、状态）。
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import jsonschema
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection
from zoujin_backend.db import store
from zoujin_backend.db.events import recorded_at
from zoujin_backend.db.tables import memory_items
from zoujin_backend.models.armor import DEADLINE_S as ARMOR_DEADLINE_S
from zoujin_backend.models.armor import Armor, ArmorFailed, cost_usd
from zoujin_backend.models.prompts import PROMPTS
from zoujin_backend.models.text import BadOutput, ModelCallFailed, RateLimited, Stop, TextModel, model_and_version, spec
from zoujin_backend.narrator.rules import has_pii
from zoujin_backend.projection import committed, visible_effects
from zoujin_backend.trace import Tracer
from zoujin_backend.world import Book
from zoujin_worldsim import SimState, apply, lived, sees

Json = Any

SCHEMA_VERSION = "1.12"  # 写入时的数据契约版本（同 narrator/writer.py）
MAX_TEXT = 30  # 一句记忆的长度上限（NFKC 以后的字数；UX 评审 30，比数据的 40 严，取 30；超了当过滤没过）
MAX_KEEPS = 30  # 「不会撤销的后果」一句的上限（UX 评审）
MAX_PER_COMMIT = 3  # 一次提交最多写几条（按 salience 取前几条）
BRIEF_LIMIT = 8  # 局势说明里带几条（节约档 4 条，E6-007）
BRIEF_LIMIT_SAVING = 4
KNOWN_TRUST = 10  # 身份认识的人物，起始信任
TRUST_MIN, TRUST_MAX = -100, 100

# 契约第 4 节的五档：(trust 的上限（含）, level, label)；最后一档没有上限
LEVELS: tuple[tuple[int | None, int, str], ...] = (
    (-40, 1, "敵意を抱いている"),
    (-10, 2, "警戒している"),
    (9, 3, "様子を見ている"),
    (39, 4, "気を許している"),
    (None, 5, "信じている"),
)

# 事件 → 记忆的对照表（数据定，#153 评审）：(kind, trustDelta, salience)。每个人物、每一轮取最靠前的一行
PROMISE_MADE = ("promise", 5, 0.8)  # 和他立了约定（谁许下的都算）
PROMISE_KEPT = ("help", 10, 0.8)  # 玩家兑现了和他的约定
PROMISE_BROKEN = ("harm", -15, 0.9)  # 玩家违背了和他的约定
HELPED = ("help", 10, 0.7)  # actor = player、beneficiary = 他
HARMED = ("harm", -10, 0.7)  # actor = player，他的信任类变量降了、他被带走（beneficiary 不是他）
HELPED_YOU = ("shared-moment", 3, 0.5)  # actor = 他、beneficiary = player
BEAT = ("shared-moment", 2, 0.6)  # 节拍发生、玩家看得到、他亲历（`zoujin_worldsim.lived`）
CLAIM = ("claim", 0, 0.5)  # 玩家说自己的事（learn 效果写明他学到了，或 improv 成了他的即兴设定）
IMPRESSION = ("impression", 0, 0.3)  # 其余 actor = player 的事件（说话、动作）
ROWS = (PROMISE_MADE, PROMISE_KEPT, PROMISE_BROKEN, HELPED, HARMED, HELPED_YOU, BEAT, CLAIM, IMPRESSION)
KEY_MOMENT_BONUS = 0.2  # keyMoment 的 salience 加分（上限 1）
WEIGHT_STEP = 0.1  # 模型给的 weight 1〜3：salience 再加 0.1 × (weight - 1)，上限 1
DELTA_MIN, DELTA_MAX = -20, 20  # 契约的 trustDelta 范围

# 引号里的命令句（「〜しろ」之类）：记忆里不该有人对谁下命令
_COMMAND = re.compile(r"[「『][^」』]{0,40}(?:しろ|せよ|なさい|てくれ|ください|やれ|ろ|け)[」』]")
# 不写记忆的系统事件（节拍照写）
SKIP_TYPES = frozenset({"forget", "act-transition", "ending", "correction"})


@dataclass(frozen=True)
class Seed:
    """要写的一条记忆（文字还没有）：一个人物一轮最多一条，这一轮和他有关的事件合在一起（`events`）。"""

    character: str
    kind: str
    events: tuple[Json, ...]
    trust_delta: int
    salience: float  # 对照表的值加 keyMoment；模型的 weight 在写的时候再加
    via: str
    promise_id: str | None = None
    t: int = 0

    @property
    def event(self) -> Json:
        return self.events[0]


@dataclass
class Written:
    """写记忆这一步的结果：存进 `memory_items` 的行、计数、花费。"""

    rows: list[Json] = field(default_factory=list)
    filtered: int = 0
    failed: int = 0
    armor_errors: int = 0
    cost_usd: float = 0.0
    armor_usd: float = 0.0


def relation(trust: int) -> tuple[str, int]:
    """trust → (label, level)，契约第 4 节的表。"""
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
    """约定里玩家以外的那一方（和玩家无关的约定是 None）。"""
    if p.get("from") == "player":
        return str(p.get("to"))
    if p.get("to") == "player":
        return str(p.get("from"))
    return None


def _trust_var(character: str, var: str) -> bool:
    """`var.<他>.trust` 这类变量（人物 ID 的最后一段）。"""
    short = character.rsplit(".", 1)[-1]
    return var.endswith(".trust") and short in var.split(".")


def _lived(book: Book, after: SimState, ev: Json) -> set[str]:
    """这条节拍事件里亲历了节拍的人物（`zoujin_worldsim.lived`，#154）。after = 这条事件之后的状态。"""
    beats = [e["beat"] for e in ev["effects"] if e.get("op") == "beat"]
    return {c for c in book.characters if any(lived(book.world, after, c, x) for x in beats)}


def _event_rows(
    book: Book, state: SimState, after: SimState, ev: Json, addressee: str | None
) -> dict[str, tuple[int, str, str | None]]:
    """一条事件给谁哪一行：人物 → (行号, via, promiseId)。state / after 是这条事件之前 / 之后的状态。"""
    if not committed(ev) or ev["type"] in SKIP_TYPES:
        return {}
    player_place = state["vars"]["var.player.location"]
    if ev["actor"] != "player" and not sees(book.world, player_place, ev):  # 玩家看不到的事不写
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
        return None  # 切片不写 rumor

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
        if ev["type"] == "say":  # 玩家说自己的事：写明他学到了（learn），或成了他的即兴设定（improv）
            for c in told | {e["character"] for e in ev["effects"] if e.get("op") == "improv"}:
                put(c, CLAIM)
        # 印象：说话只给说话的对象（这一轮的人物），动作给在场的人
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
    """一次提交（一轮）要写的记忆：每个人物最多一条，这一轮和他有关的事件合在一起，kind 取对照表最靠前的一行；
    按 salience 取前 `MAX_PER_COMMIT` 个人物（同分按第一次出现的顺序）。addressee：这一轮玩家对谁说。"""
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
    """模型给的 weight（1〜3）加到 salience 上，夹在这一行的值到 1 之间。"""
    return round(max(s.salience, min(1.0, s.salience + WEIGHT_STEP * (max(1, min(3, weight)) - 1))), 3)


# setup 直接种的记忆（评测入口）：按 kind 取对照表里第一行同一种的数
BY_KIND = {
    "promise": PROMISE_MADE,
    "help": HELPED,
    "harm": PROMISE_BROKEN,
    "shared-moment": HELPED_YOU,
    "claim": CLAIM,
    "impression": IMPRESSION,
}


def seeded(ids: Any, pid: str, ev: Json, character: str, kind: str, text: str) -> Json:
    """评测 setup 种的一条记忆（来源是布置的那条事件，`via` = witnessed）。"""
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
    """去掉整句外面的「」『』和句末的「。」（前端会加引号，UX 评审）。"""
    t = text.strip()
    while len(t) >= 2 and t[0] in "「『" and t[-1] in "」』":
        t = t[1:-1].strip()
    return t.rstrip("。．.").strip()


def length(text: str) -> int:
    """长度按 NFKC 以后的字数（含标点，数据评审）。"""
    return len(unicodedata.normalize("NFKC", text))


def rule_ok(text: str, role_name: str | None = None) -> bool:
    """第一、三道过滤：个人信息规则（和 R6 同一套）、长度（超了不截断）、引号里的命令句、身份名（UX 评审：
    记忆里提到玩家用「あなた」「あの人」，契约 1.8 的身份名替换只管 summary）。"""
    t = text.strip()
    return (
        bool(t)
        and length(t) <= MAX_TEXT
        and not has_pii(t)
        and not command_like(t)
        and not (role_name and role_name in t)
    )


# 「不会撤销的后果」一句里不能有的：代词（用名字）、记得和忘记（UX 评审）
_KEEPS_BANNED = re.compile(r"彼(?![方岸])|覚え|忘れ")  # 「彼方」「彼岸」不算代词（UX 复看）


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
    """提示 `memory` 的请求：这一轮和他有关的事件的 summary、visibleEffects，人物的人设摘要，via。不给原话。
    `role` 只让模型知道玩家是谁，提示里要求不写进句子（过滤也挡）。"""
    return {
        "character": persona(book, s.character),
        "role": book.roles[role_id]["name"],
        "kind": s.kind,
        "via": s.via,
        "events": [{"summary": e["summary"], "visibleEffects": visible_effects(book, e["effects"])} for e in s.events],
    }


@dataclass
class Memorizer:
    """写记忆的模型调用和过滤。叙事者和评测入口共用。"""

    text: TextModel
    armor: Armor | None
    ids: Any
    tracer: Tracer = field(default_factory=Tracer)
    deadline: float | None = None  # None = config.TEXT["memory"] 的时限
    armor_deadline: float = ARMOR_DEADLINE_S
    raise_stops: bool = False  # True（评测）：账本到上限、429 整次停下

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
        """第二道过滤（`sanitizeModelResponse`）：注入、RAI HIGH、SDP、恶意链接任一命中就不写。
        1 秒没回、出错当没命中（`armor_errors` 记一次）。"""
        if self.armor is None:
            return True
        out.armor_usd += cost_usd(self.armor, text)
        try:
            ar = await asyncio.wait_for(self.armor.screen_response(text), self.armor_deadline)
        except (TimeoutError, ArmorFailed):
            out.armor_errors += 1
            return True
        return not (ar.injection or ar.harmful or ar.pii or ar.uri)


# —— 读 ——


async def alive(c: AsyncConnection, pid: str, who: str | None = None) -> list[Json]:
    """这一局没删的记忆（按 t、建立的先后）。"""
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
    """局势说明里带的：这个人物没删的记忆，按 salience 取前 limit 条（同分新的在前），按时间排好的文字。"""
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
    """删了的记忆的来源事件里他学到的事实（`learn`）和即兴设定（`improv`），减去别的提交事件也教过他的
    （局势说明不带，`gateway/brief.py`）。"""
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
    learned: dict[str, set[str]] = {}  # 事实 → 教过他的事件
    for ev in await store.event_log(c, pid, book.version):
        if not committed(ev):
            continue
        for e in ev["effects"]:
            if e.get("op") == "learn" and e.get("character") == who:
                learned.setdefault(str(e["fact"]), set()).add(str(ev["eventId"]))
            elif e.get("op") == "improv" and e.get("character") == who:  # 即兴设定：玩家告诉他的（rf_ ID）
                learned.setdefault(str(e["factId"]), set()).add(str(ev["eventId"]))
    return frozenset(f for f, by in learned.items() if by and by <= dropped)


def item_json(row: Mapping[str, Any]) -> Json:
    """`memory_items` 的一行 → 契约的 MemoryItem（评测入口的 `memories()`）。"""
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


# —— 記憶帳 ——


async def keeps(
    text: TextModel,
    tracer: Tracer,
    book: Book,
    row: Mapping[str, Any],
    evs: Sequence[Json],
    promise: Mapping[str, Any] | None,
    **span: object,
) -> tuple[str | None, bool, float]:
    """删除确认里「不会撤销的后果」一句（提示 `keeps`，只读来源事件的摘要和结果）。
    返回（一句或 None、能不能缓存、花费）：模型出错、超时、输出不合格、过不了过滤 → None，不缓存（下次再算）；
    模型说没有 → None，缓存。"""
    kind = "keeps"
    model, version = model_and_version(kind)
    req: Json = {
        "character": book.characters[row["character"]]["name"],
        "events": [{"summary": e["summary"], "visibleEffects": visible_effects(book, e["effects"])} for e in evs],
        "promise": {"text": promise["text"], "status": promise["status"]} if promise else None,
        # 约定会作废时，句子里不写这个约定（下一行就是「この約束も、なかったことになります」，UX 评审）
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
