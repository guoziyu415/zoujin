"""切片的简化结局（B-9；backend-design 2.9 的切片版，api-contract 2.8、3.13，契约第 5 节）。

- **什么时候进**（`due`）：只在最后一幕（没有 exits 的那一幕）。期限盯的节拍（`clock.deadline.watchBeat`）有了结果，
  或期限结算过了，就进。在触发的那次提交里（`enter`）：把这一幕结算到收幕（收幕节拍上的固定演出不看玩家在哪，算进结局
  演出）→ `classify` → 演出站位 `staging` → 局改成 `ended` → 插一条 `kind: "ending"` 的任务 → 推送最前面是
  `ending_started`。
- **站位、受影响排序、署名、模板、校验**：都是确定性的，全在这里，不交给模型。
- **生成**（`run_ending`）：Claude 写尾声、你的结局、人物的结局（提示 `ending`，结构化输出），每句引用这一局的事件；
  事件 ID 在请求里写成 `e<seq>`（同样的局面请求一样，回放的键才对得上），收到以后换回真 ID。最多调两次（超时、出错、
  不过 Schema、不过校验都算一次；第二次带上不过的规则名和字段），之后用模板（S-065，ux-design 11.4）。
- **保存**：同一个事务里存结局、清空这一局的原话和打算文字（S-035）、补 `playthrough_metrics`、任务改成 done 并推
  `ending_ready`、NOTIFY。
- 日志和 Trace 只有 ID、规则名、次数、耗时、花费，没有结局的文字和原话（data-design 第 8 节）。
"""

from __future__ import annotations

import asyncio
import copy
import logging
import re
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import jsonschema
from sqlalchemy import func, insert, select, update
from zoujin_backend.db import store
from zoujin_backend.db.events import recorded_at
from zoujin_backend.db.store import Run
from zoujin_backend.db.tables import endings, playthrough_metrics, playthroughs, turns, utterances
from zoujin_backend.models.prompts import PROMPTS
from zoujin_backend.models.text import BadOutput, ModelCallFailed, RateLimited, TextResult, model_and_version, spec
from zoujin_backend.narrator.pipeline import Spend
from zoujin_backend.narrator.rules import PII, VERBATIM, lcs_len
from zoujin_backend.narrator.writer import SCHEMA_VERSION, Writer, has_exits
from zoujin_backend.projection import committed, player_spot
from zoujin_backend.world import Book
from zoujin_worldsim import OCCURRED, SimState, classify, flat, signature

if TYPE_CHECKING:
    from zoujin_backend.narrator.core import Narrator, Result, Task

log = logging.getLogger("zoujin.narrator")

Json = Any

KIND = "ending"
MAX_CALLS = 2  # 一次调用 + 重写（或超时重发）一次，之后用模板（backend-design 第 138 行）
ETA_SECONDS = 30  # 202 的 etaSeconds = 30 减去已经过的秒数，最少 5（api-contract 2.8）
ETA_MIN = 5

# 演出里的几个人（『走れメロス』的切片；状态表按他们分，见卡「做」第 2 条）
MELOS = "char.melos"
KING = "char.king"
FRIEND = "char.selinuntius"  # 不是人质时也列（S-053 默认在场）
CROWD_SPOTS = frozenset({"stake-front"})  # 群众前排的位置点（「身を寄せる」落在这里，S-077 ⑤）

# S-067：处刑只间接交代。这一局有人被处刑时，结局的文字里不能有这些写法（ux-design 11.2，v1.0.4）；按子串查。
# 「磔」本身不禁。提示和校验共用这一处
FORBIDDEN = (
    "処刑",
    "死",
    "殺",
    "最期",
    "亡くな",
    "命を落と",
    "息絶え",
    "絶命",
    "事切れ",
    "帰らぬ人",
    "磔にされ",
    "磔になっ",
)
# 字数（ux-design 11.3）
TITLE_MAX = 14
SUBTITLE_MAX = 26
CARD_LINE_MAX = 40
CARD_CONTRAST_MAX = 48
EPILOGUE = (3, 5)
SIDE = (0, 2)  # didForYou、youDid
YOURS = (1, 3)
CARD_LINES = 3

ALIAS = re.compile(r"e([1-9][0-9]*)")
PLACEHOLDER = ""  # 专有名词的占位符（和评测 text.py 一样：私用区的一个字）
_KATAKANA_RUN = re.compile(r"[ァ-ヺー]{3,}")


# —— 进结局 ——


def due(book: Book, state: SimState) -> str | None:
    """这一次提交以后进不进结局：进就返回 trigger（`story-closed` / `deadline`），不进返回 None。
    只在最后一幕判；期限盯的节拍有了结果，或期限结算过了。"""
    return None if has_exits(book, state) else closed(book, state)


def closed(book: Book, state: SimState) -> str | None:
    """不看在哪一幕：期限盯的节拍有了结果，或期限结算过了。评测 setup 在 `curtain_fell` 之后用它取 trigger（情景模式
    一口气推到收幕时，玩家没跟着换幕）。"""
    watch = book.world["clock"]["deadline"].get("watchBeat")
    if watch in state["beats"]:
        return "story-closed" if state["beats"][watch] in OCCURRED else "deadline"
    if state["deadline"]:
        return "deadline"
    return None


def curtain_fell(book: Book, state: SimState) -> bool:
    """最后一幕（没有 exits 的那一幕）的 `end` 满足了：`onBeats` 有一个有了结果，或到了 `atLatest`。评测 setup 用：
    情景一口气推到底才算，检查点停在 beat.24 以后、还没换幕的老用例不算（照旧可以对话，数据评审 #124）。"""
    last = next(a for a in book.world["acts"] if not a.get("exits"))
    end = last["end"]
    return any(b in state["beats"] for b in end.get("onBeats", [])) or state["t"] >= end["atLatest"]


def outcome_of(book: Book, state: SimState) -> tuple[str, bool]:
    """世界结局的分类；5 类都不成立时取最后一类（世界模型的错，Trace 记 `ending-unclassified`）。"""
    got = classify(book.world, state)
    if got is not None:
        return got, False
    return str(book.world["endings"]["world"][-1]["id"]), True


def label_of(book: Book, outcome: str) -> str:
    return str(next(x["label"] for x in book.world["endings"]["world"] if x["id"] == outcome))


def staging(book: Book, state: SimState, run: Run | None) -> Json:
    """演出站位（api-contract 3.13）：按结算到收幕以后的状态，每人一个「从哪到哪」的状态（卡「做」第 2 条的表）。"""
    watch = book.world["clock"]["deadline"]["watchBeat"]
    place = str(book.beats[watch]["place"])
    vars_ = state["vars"]
    hostage = str(vars_.get("var.hostage.who", "none"))
    where = dict(state["locations"])
    where["player"] = str(vars_["var.player.location"])

    def scene_ref(p: str | None) -> str | None:
        got = book.places.get(p or "", {}).get("sceneRef")
        return None if got is None else str(got)

    order: list[str] = []
    if hostage != "none":
        order.append(hostage)
    for c in (FRIEND, MELOS, KING):
        if c in book.characters and c not in order:
            order.append(c)
    order += [
        c
        for c, p in state["locations"].items()
        if p == place and c not in order and c in book.characters and not book.characters[c].get("group")
    ]
    order.append("player")

    def state_of(c: str) -> str:
        if c == FRIEND and c != hostage:
            return "absent" if scene_ref(where.get(c)) != scene_ref(place) else "in-crowd"
        if where.get(c) != place:
            return "absent"
        if c == hostage:
            return "freed" if vars_.get("var.hostage.fate") == "released" else "on-cross"
        if c == MELOS:
            return "arriving" if vars_.get("var.melos.custody") == "returned" else "collapsed"
        if c == KING:
            return "approaching" if vars_.get("var.king.disposition") == "reformed" else "present"
        if c == "player":
            return "in-crowd" if player_spot(book, state, run) in CROWD_SPOTS else "present"
        return "in-crowd"

    return {"place": place, "characters": [{"id": c, "state": state_of(c)} for c in dict.fromkeys(order)]}


def enter(w: Writer, book: Book, trigger: str) -> Json:
    """触发的那次提交里（锁着这一局）：结算到收幕，分类，算站位。返回 `ending_started` 消息和任务的 request。
    局的状态、任务行、推送顺序由调用方（`Narrator._commit`）写。"""
    guard, w.guard = w.guard, True  # 最后一幕：借收幕的拦法结算到 end.onBeats 有了结果（或 atLatest），之后不再结算
    try:
        w.settle(None, anywhere=True)
    finally:
        w.guard = guard
    outcome, unclassified = outcome_of(book, w.state)
    stage = staging(book, w.state, w.run)
    return {
        "message": {"type": "ending_started", "trigger": trigger, "staging": stage},
        "request": {"trigger": trigger, "staging": stage, "outcome": outcome, "unclassified": unclassified},
    }


# —— 这一局的事件 ——


def kept(log_: Iterable[Mapping[str, Any]]) -> list[Json]:
    """结局看的事件：已提交的（被否决的不算），不含 forget。"""
    return [dict(e) for e in log_ if committed(e) and e["type"] != "forget"]


def by_player(e: Mapping[str, Any]) -> bool:
    """「玩家的事件」：actor 是玩家，或来自玩家的一轮、动作（和评测 checks.py 的 `_by_player` 同一个判法）。"""
    return e.get("actor") == "player" or e.get("origin") in ("turn", "action")


def involves(e: Mapping[str, Any], c: str, state: SimState) -> bool:
    """事件和这个人物有关：他是 actor、beneficiary，或是效果的对象（learn、relocate、improv 的 character，约定的
    对方，物品换手的 from / to）。"""
    if e.get("actor") == c or e.get("beneficiary") == c:
        return True
    for x in e.get("effects", []):
        op = x.get("op")
        if op in ("learn", "relocate", "improv") and x.get("character") == c:
            return True
        if op == "hold" and c in (x.get("from"), x.get("to")):
            return True
        if op == "promise":
            p = state["promises"].get(str(x.get("promiseId")), {})
            if c in (x.get("from"), x.get("to"), p.get("from"), p.get("to")):
                return True
    return False


def changed_beats(book: Book, state: SimState, events: Sequence[Mapping[str, Any]]) -> list[Json]:
    """和原著不同的节拍（结果不是 happened 的），各自指回事件：改它的事件在前，再加写下结果的系统事件。"""
    out: list[Json] = []
    for b in book.world["beats"]:
        to = state["beats"].get(b["id"])
        if to is None or to == "happened":
            continue
        caused = [
            e["eventId"]
            for e in events
            if e.get("origin") != "schedule"
            and any(x.get("op") == "beat" and x.get("beat") == b["id"] for x in e["effects"])
        ]
        caused += [
            e["eventId"]
            for e in events
            if e.get("origin") == "schedule"
            and any(x.get("op") == "beat" and x.get("beat") == b["id"] for x in e["effects"])
        ]
        out.append({"beat": b["id"], "to": to, "causedBy": list(dict.fromkeys(caused))})
    return out


def listed(book: Book) -> list[str]:
    """结局页列哪些人物：`endings.characters`，没写就是 talkable 的人物。"""
    got = book.world["endings"].get("characters")
    if got:
        return [str(c) for c in got]
    return [c for c, x in book.characters.items() if x.get("talkable")]


def rank(
    book: Book, state: SimState, events: Sequence[Mapping[str, Any]], changed: Sequence[Mapping[str, Any]]
) -> dict[str, Json]:
    """受影响的排序（切片的简化版）：玩家的事件里和他有关的条数，加上 changedBeats 里他是参与者的节拍数。
    0 分 `unchanged`、`rank: null`；其余按分数从高到低给 1、2…，同分按 `endings.characters` 的顺序。"""
    mine = [e for e in events if by_player(e)]
    names = listed(book)
    score: dict[str, int] = {}
    for c in names:
        n = sum(1 for e in mine if involves(e, c, state))
        n += sum(1 for x in changed if c in book.beats[x["beat"]].get("participants", []))
        score[c] = n
    ordered = sorted((c for c in names if score[c] > 0), key=lambda c: (-score[c], names.index(c)))
    out = {c: {"character": c, "rank": None, "unchanged": True, "score": 0} for c in names}
    for i, c in enumerate(ordered, 1):
        out[c] = {"character": c, "rank": i, "unchanged": False, "score": score[c]}
    return out


def original(book: Book, c: str) -> str:
    oe = book.characters[c].get("originalEnding") or {}
    return str(oe.get("text") or book.characters[c]["name"])


def executed(state: SimState) -> bool:
    v = state["vars"]
    return v.get("var.hostage.fate") == "executed" or v.get("var.player.custody") == "executed"


def fate_id(state: SimState, place: str) -> str:
    custody = state["vars"].get("var.player.custody")
    if custody in ("hostage", "executed"):
        return str(custody)
    return "witness" if state["vars"]["var.player.location"] == place else "elsewhere"


def last_scene(book: Book, state: SimState, stage: Mapping[str, Any]) -> Json:
    place = str(stage["place"])
    present = [x["id"] for x in stage["characters"] if x["id"] != "player" and x["state"] != "absent"]
    return {
        "place": place,
        "description": f"{book.places[place]['name']}、{book.label(state['t'])}",
        "present": present,
    }


def deciders(book: Book, state: SimState, outcome: str, events: Sequence[Mapping[str, Any]]) -> list[str]:
    """把分类用到的变量设成现值的事件（各取最后一次设的那条）：模板的句子引用它们。一条都没有（变量还是初值）时取
    最后一个事件。"""
    rule = next(x for x in book.world["endings"]["world"] if x["id"] == outcome)
    out: list[str] = []
    for cond in rule.get("when", []):
        var = cond["var"]
        now = state["vars"].get(var)
        hit = next(
            (
                e["eventId"]
                for e in reversed(events)
                if any(x.get("op") == "set" and x.get("var") == var and x.get("value") == now for x in e["effects"])
            ),
            None,
        )
        if hit is not None and hit not in out:
            out.append(hit)
    if not out and events:
        out.append(events[-1]["eventId"])
    return out


# —— 模板（S-065；ux-design 11.4，契约 2.9.2）——


def template_of(book: Book, state: SimState, outcome: str) -> Json:
    values = flat(state)
    for t in book.world["endings"].get("templates", []):
        if t["outcome"] == outcome and (not t.get("when") or book.sim.holds(t["when"], values)):
            return t
    raise ValueError(f"世界模型没有 {outcome} 的结局模板")


@dataclass
class Ctx:
    """一局的结局要用的：分类、站位、事件、排序，和要拼进结局的代码算的部分。"""

    book: Book
    state: SimState
    pid: str
    role: str  # 开局身份名
    trigger: str
    outcome: str
    stage: Json
    events: list[Json]
    changed: list[Json]
    ranks: dict[str, Json]
    said: list[str] = field(default_factory=list)  # 玩家的原话（校验用，不进请求）

    @property
    def label(self) -> str:
        return label_of(self.book, self.outcome)

    @property
    def ids(self) -> set[str]:
        return {e["eventId"] for e in self.events}

    @property
    def place(self) -> str:
        return str(self.stage["place"])

    @property
    def fate(self) -> str:
        return fate_id(self.state, self.place)


def make_ctx(
    book: Book,
    state: SimState,
    pid: str,
    role_id: str,
    request: Mapping[str, Any],
    log_: Sequence[Json],
    said: list[str],
) -> Ctx:
    events = kept(log_)
    changed = changed_beats(book, state, events)
    return Ctx(
        book=book,
        state=state,
        pid=pid,
        role=str(book.roles[role_id]["name"]),
        trigger=str(request["trigger"]),
        outcome=str(request["outcome"]),
        stage=copy.deepcopy(request["staging"]),
        events=events,
        changed=changed,
        ranks=rank(book, state, events, changed),
        said=said,
    )


def from_template(ctx: Ctx) -> Json:
    """模板的结局（不带 endingId、decidedAt 等外层字段，`assemble` 补）。"""
    book, state = ctx.book, ctx.state
    t = template_of(book, state, ctx.outcome)
    cites = deciders(book, state, ctx.outcome, ctx.events)
    fates = book.world["endings"].get("fates", {})
    fate = t.get("fate") or fates.get(ctx.fate) or fates.get("elsewhere", "日没を迎えた。")
    title = str(t["title"]).replace("{role}", ctx.role)
    written = [x["character"] for x in t["lines"]]
    characters = []
    for c in listed(book):
        if c in written:
            line = next(x["line"] for x in t["lines"] if x["character"] == c)
            characters.append(
                {
                    "character": c,
                    "rank": written.index(c) + 1,
                    "unchanged": False,
                    "original": original(book, c),
                    "yours": [{"sentence": line, "cites": cites}],
                }
            )
        else:
            characters.append({"character": c, "rank": None, "unchanged": True, "original": original(book, c)})
    return {
        "world": world_part(ctx),
        "player": {
            "fate": {"id": ctx.fate, "label": fate, "causedBy": cites},
            "relationships": [],
            "title": {"text": title, "causedBy": cites},
            "epilogue": [{"sentence": t["subtitle"], "cites": cites}],
            "lastScene": last_scene(book, state, ctx.stage),
            "didForYou": [],
            "youDid": [],
        },
        "characters": characters,
        "card": {
            "title": title,
            "subtitle": t["subtitle"],
            "contrast": t["contrast"],
            "characterLines": [{"character": x["character"], "line": x["line"]} for x in t["lines"]][:CARD_LINES],
        },
    }


def world_part(ctx: Ctx) -> Json:
    return {
        "outcome": ctx.outcome,
        "title": ctx.label,
        "summary": ctx.label,
        "changedBeats": copy.deepcopy(ctx.changed),
        "finalVars": copy.deepcopy(ctx.state["vars"]),
        "signature": signature(ctx.book.world, ctx.state),
    }


# —— 请求 ——


def alias_map(events: Sequence[Mapping[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    """事件 ID ↔ 请求里的别名 `e<seq>`。"""
    to_alias = {e["eventId"]: f"e{e['seq']}" for e in events}
    return to_alias, {v: k for k, v in to_alias.items()}


def request_of(ctx: Ctx, problems: Sequence[Mapping[str, str]] = ()) -> Json:
    """送给模型的 request（回放按它算键）：分类、署名变量的最终值、changedBeats、人物、这一局的事件、身份名。
    不给原话（S-046），不给记忆。重写时带上一次不过的规则名和字段（不带文字）。"""
    book = ctx.book
    to_alias, _ = alias_map(ctx.events)
    sig_vars = book.world["endings"].get("signature", {}).get("vars", [])
    req: Json = {
        "worldModelVersion": book.version,
        "outcome": {"id": ctx.outcome, "label": ctx.label},
        "finalVars": {v: ctx.state["vars"].get(v) for v in sig_vars},
        "changedBeats": [
            {
                "beat": x["beat"],
                "to": x["to"],
                "summary": book.beats[x["beat"]]["summary"],
                "causedBy": [to_alias[i] for i in x["causedBy"] if i in to_alias],
            }
            for x in ctx.changed
        ],
        "characters": [
            {
                "character": c,
                "name": book.characters[c]["name"],
                "rank": r["rank"],
                "unchanged": r["unchanged"],
                "originalEnding": original(book, c),
            }
            for c, r in ctx.ranks.items()
        ],
        "events": [
            {
                "eventId": to_alias[e["eventId"]],
                "t": e["t"],
                "actor": e["actor"],
                "type": e["type"],
                "summary": e["summary"],
                **({"beneficiary": e["beneficiary"]} if e.get("beneficiary") else {}),
                **beat_result(e),
            }
            for e in ctx.events
        ],
        "role": ctx.role,
        "place": {"id": ctx.place, "name": book.places[ctx.place]["name"], "fate": ctx.fate},
        "executed": executed(ctx.state),
    }
    if executed(ctx.state):
        req["forbidden"] = list(FORBIDDEN)
    if problems:
        req["problems"] = [dict(p) for p in problems]
    return req


def beat_result(e: Mapping[str, Any]) -> Json:
    """节拍的系统事件带上节拍和结果：没照原作发生的（prevented 等），summary 还是原作那一句，模型要靠这个分清。"""
    for x in e.get("effects", []):
        if x.get("op") == "beat":
            return {"beat": {"id": x["beat"], "to": x.get("to", "happened")}}
    return {}


# —— 校验（确定性，卡「做」第 5 条）——


def proper_nouns(world: Mapping[str, Any]) -> list[str]:
    """世界模型里的专有名词（人物、地点、物品的名字，名字里 3 字以上的片假名，引用的原文），长的在前。
    和评测 `zoujin_evals.text.proper_nouns` 同一个取法。"""
    names: set[str] = set()
    for key in ("characters", "places", "items"):
        for x in world.get(key, []):
            if x.get("name"):
                names.add(x["name"])
                names.update(_KATAKANA_RUN.findall(x["name"]))
    names.update(q for q in _quotes(world) if q)
    return sorted(names, key=lambda s: (-len(s), s))


def _quotes(o: Any) -> Iterable[str]:
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
    for n in nouns:
        text = text.replace(n, PLACEHOLDER)
    return text


@dataclass(frozen=True)
class Problem:
    rule: str
    field: str

    def doc(self) -> dict[str, str]:
        return {"rule": self.rule, "field": self.field}


def _sentences(out: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    """模型输出里带 cites 的每一句：（字段，{sentence 或 text, cites}）。"""
    you = out["you"]
    rows: list[tuple[str, Mapping[str, Any]]] = [(f"epilogue[{i}]", x) for i, x in enumerate(out["epilogue"])]
    rows += [("you.title", you["title"]), ("you.fate", you["fate"])]
    rows += [(f"you.didForYou[{i}]", x) for i, x in enumerate(you["didForYou"])]
    rows += [(f"you.youDid[{i}]", x) for i, x in enumerate(you["youDid"])]
    for c in out["characters"]:
        rows += [(f"characters.{c['character']}[{i}]", x) for i, x in enumerate(c["yours"])]
    return rows


def texts_of(out: Mapping[str, Any]) -> list[tuple[str, str]]:
    """模型输出里给人看的每一段文字（字段，文字）。"""
    rows = [(f, str(x.get("sentence", x.get("text", "")))) for f, x in _sentences(out)]
    rows += [
        ("contrast.original", out["contrast"]["original"]),
        ("contrast.yours", out["contrast"]["yours"]),
        ("subtitle", out["subtitle"]),
        ("cardContrast", out["cardContrast"]),
    ]
    return rows


def validate(ctx: Ctx, out: Mapping[str, Any]) -> list[Problem]:
    """模型输出（cites 已换回真 ID）过不过确定性校验：引用、条数、字数、contrast.beat、不逐字引用原话、个人信息、
    S-067 的写法。返回不过的规则名和字段（不带文字）。"""
    bad: list[Problem] = []
    ids = ctx.ids
    for f, x in _sentences(out):
        cites = list(x.get("cites", []))
        if not cites:
            bad.append(Problem("cite-empty", f))
        elif any(c not in ids for c in cites):
            bad.append(Problem("cite-unknown", f))
    if not EPILOGUE[0] <= len(out["epilogue"]) <= EPILOGUE[1]:
        bad.append(Problem("count", "epilogue"))
    for k in ("didForYou", "youDid"):
        if not SIDE[0] <= len(out["you"][k]) <= SIDE[1]:
            bad.append(Problem("count", f"you.{k}"))
    want = {c for c, r in ctx.ranks.items() if not r["unchanged"]}
    got = [c["character"] for c in out["characters"]]
    if set(got) != want or len(got) != len(set(got)):
        bad.append(Problem("characters", "characters"))
    for c in out["characters"]:
        if not YOURS[0] <= len(c["yours"]) <= YOURS[1]:
            bad.append(Problem("count", f"characters.{c['character']}"))
    if len(out["you"]["title"]["text"]) > TITLE_MAX:
        bad.append(Problem("length", "you.title"))
    if len(out["subtitle"]) > SUBTITLE_MAX:
        bad.append(Problem("length", "subtitle"))
    if len(out["cardContrast"]) > CARD_CONTRAST_MAX:
        bad.append(Problem("length", "cardContrast"))
    for c in card_lines(ctx, out):
        if len(c["line"]) > CARD_LINE_MAX:
            bad.append(Problem("length", f"characters.{c['character']}[0]"))
    beat = out["contrast"].get("beat")
    if beat is not None and beat not in {x["beat"] for x in ctx.changed}:
        bad.append(Problem("contrast-beat", "contrast.beat"))
    nouns = proper_nouns(ctx.book.world)
    said = [mask(s, nouns) for s in ctx.said if s]
    forbid = executed(ctx.state)
    for f, text in texts_of(out):
        if any(lcs_len(mask(text, nouns), s) >= VERBATIM for s in said):
            bad.append(Problem("verbatim", f))
        if PII.search(text):
            bad.append(Problem("pii", f))
        if forbid and any(w in text for w in FORBIDDEN):
            bad.append(Problem("s067", f))
    return bad


def card_lines(ctx: Ctx, out: Mapping[str, Any]) -> list[Json]:
    """卡上的人物：rank 最前的 1〜3 人各自的第一句；都 unchanged 时放梅洛斯的 originalEnding（契约 1.6）。"""
    yours = {c["character"]: c["yours"] for c in out["characters"] if c["yours"]}
    top = sorted((r for r in ctx.ranks.values() if not r["unchanged"]), key=lambda r: r["rank"])[:CARD_LINES]
    lines = [
        {"character": r["character"], "line": yours[r["character"]][0]["sentence"]}
        for r in top
        if r["character"] in yours
    ]
    if not lines:
        lines = [{"character": MELOS, "line": original(ctx.book, MELOS)}]
    return lines


def unalias(out: Json, back: Mapping[str, str]) -> Json:
    """模型输出里的别名 `e<seq>` 换回真 ID；认不出的原样留着（校验报 cite-unknown）。contrast.beat 照原样。"""
    o = copy.deepcopy(out)

    def fix(x: Json) -> None:
        if isinstance(x, dict):
            if isinstance(x.get("cites"), list):
                x["cites"] = [back.get(c, c) for c in x["cites"]]
            for v in x.values():
                fix(v)
        elif isinstance(x, list):
            for v in x:
                fix(v)

    fix(o)
    return o


def from_model(ctx: Ctx, out: Mapping[str, Any]) -> Json:
    """过了校验的模型输出 → 结局（代码算的部分照补）。"""
    book = ctx.book
    you = out["you"]
    yours = {c["character"]: c["yours"] for c in out["characters"]}
    contrast = {"original": out["contrast"]["original"], "yours": out["contrast"]["yours"]}
    if out["contrast"].get("beat") is not None:
        contrast["beat"] = out["contrast"]["beat"]
    characters = []
    for c, r in ctx.ranks.items():
        row: Json = {"character": c, "rank": r["rank"], "unchanged": r["unchanged"], "original": original(book, c)}
        if not r["unchanged"]:
            row["yours"] = copy.deepcopy(yours[c])
        characters.append(row)
    return {
        "world": {**world_part(ctx), "contrast": contrast},
        "player": {
            "fate": {"id": ctx.fate, "label": you["fate"]["text"], "causedBy": list(you["fate"]["cites"])},
            "relationships": [],
            "title": {"text": you["title"]["text"], "causedBy": list(you["title"]["cites"])},
            "epilogue": copy.deepcopy(out["epilogue"]),
            "lastScene": last_scene(book, ctx.state, ctx.stage),
            "didForYou": copy.deepcopy(you["didForYou"]),
            "youDid": copy.deepcopy(you["youDid"]),
        },
        "characters": characters,
        "card": {
            "title": you["title"]["text"],
            "subtitle": out["subtitle"],
            "contrast": out["cardContrast"],
            "characterLines": card_lines(ctx, out),
        },
    }


def assemble(ctx: Ctx, body: Mapping[str, Any], ending_id: str, t: int) -> Json:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "endingId": ending_id,
        "playthroughId": ctx.pid,
        "worldModelVersion": ctx.book.version,
        "trigger": ctx.trigger,
        "t": t,
        "decidedAt": recorded_at(),
        **copy.deepcopy(dict(body)),
    }


# —— API 的投影（api-contract 2.8）——


def view(ending: Mapping[str, Any]) -> Json:
    """存的 Ending → EndingView。signature、finalVars、changedBeats、各处的 causedBy 不给。"""
    w, p = ending["world"], ending["player"]
    world: Json = {
        "outcomeId": (w.get("variant") or {}).get("id", w["outcome"]),
        "baseline": "variant" not in w,
        "title": (w.get("variant") or {}).get("title", w["title"]),
        "epilogue": copy.deepcopy(p["epilogue"]),
    }
    if w.get("contrast"):
        world["contrast"] = copy.deepcopy(w["contrast"])
    return {
        "endingId": ending["endingId"],
        "world": world,
        "you": {
            "title": p["title"]["text"],
            "fate": p["fate"]["label"],
            "didForYou": copy.deepcopy(p.get("didForYou", [])),
            "youDid": copy.deepcopy(p.get("youDid", [])),
        },
        "characters": copy.deepcopy(ending.get("characters", [])),
        "card": {**copy.deepcopy(ending["card"]), "fallbackImageUrl": f"/endings/{w['outcome']}.webp"},
    }


def eta(started: float, now: float) -> int:
    return max(ETA_MIN, ETA_SECONDS - int(now - started))


# —— 生成（kind: "ending" 的任务）——


@dataclass
class Generated:
    body: Json
    template: bool
    calls: int
    problems: list[Problem]


async def generate(n: Narrator, ctx: Ctx, spend: Spend, span: Mapping[str, Any]) -> Generated:
    """调模型写结局：最多两次（超时、出错、不过 Schema、不过校验都算一次；第二次带不过的规则名），之后用模板。"""
    _, back = alias_map(ctx.events)
    model, version = model_and_version(KIND)
    problems: list[Problem] = []
    calls = 0
    for attempt in range(1, MAX_CALLS + 1):
        calls = attempt
        request = request_of(ctx, [p.doc() for p in problems])
        with n.tracer.span(
            f"narrator.{KIND}",
            provider=spec(KIND).provider,
            model=model,
            prompt_version=version,
            attempt=attempt,
            **span,
        ) as sp:
            got: TextResult | None = None
            try:
                r = got = await asyncio.wait_for(n.text.call(KIND, request), n.deadlines[KIND])
                spend.add(r)
                try:
                    jsonschema.validate(r.output, PROMPTS[KIND].schema)
                except jsonschema.ValidationError:
                    raise BadOutput(f"{KIND} 的输出不过 Schema") from None
            except TimeoutError:
                cost = n.text.cancelled_cost(KIND, request)
                spend.charge(KIND, cost)
                sp.set(status="timeout", cost_usd=round(cost, 6))
                problems = []
                continue
            except BadOutput as e:
                if got is None:
                    spend.charge(KIND, e.cost_usd)
                sp.set(status="invalid", cost_usd=round(e.cost_usd if got is None else got.cost_usd, 6))
                problems = []
                continue
            except ModelCallFailed:
                sp.set(status="error")
                problems = []
                continue
            except RateLimited:
                if n.on_rate_limit == "stop":
                    raise
                sp.set(status="rate_limited")
                problems = []
                continue
            out = unalias(r.output, back)
            problems = validate(ctx, out)
            sp.set(
                status="ok" if not problems else "rejected",
                failed_rules=sorted({p.rule for p in problems}),
                tokens_in=r.usage.get("inputTokens", 0),
                tokens_out=r.usage.get("outputTokens", 0),
                tokens_cached=r.usage.get("cachedTokens", r.usage.get("cacheReadTokens", 0)),
                cost_usd=round(r.cost_usd, 6),
            )
            if not problems:
                return Generated(from_model(ctx, out), False, calls, [])
    log.info("结局 %s 走模板（调了 %d 次）", ctx.pid, calls)
    return Generated(from_template(ctx), True, calls, problems)


async def run_ending(n: Narrator, task: Task) -> Result:
    """`kind: "ending"` 的任务：在事务外调模型，再用一个事务存结局、清空原话、推 `ending_ready`。"""
    from zoujin_backend.narrator.core import Gone, Result, cost_values

    started = time.monotonic()
    pt, state = await n.read(task.pid)
    book = n.library.version(pt["world_model_version"])
    async with n.engine.connect() as c:
        log_ = await store.event_log(c, task.pid, book.version)
        said = [
            str(t)
            for t in (
                await c.scalars(
                    select(utterances.c.text).where(
                        utterances.c.playthrough_id == task.pid,
                        utterances.c.speaker == "player",
                        utterances.c.text.is_not(None),
                    )
                )
            ).all()
        ]
    request = dict(task.request or {})
    ctx = make_ctx(book, state, task.pid, pt["role_id"], request, log_, said)
    spend = task.spend
    span = {"playthrough_id": task.pid, "turn_id": task.turn_id, "world_model_version": book.version}
    if request.get("unclassified"):  # 世界模型的错：5 类都不成立
        with n.tracer.span("narrator.ending.unclassified", failed_rules=["ending-unclassified"], **span):
            pass
    got = await generate(n, ctx, spend, span)
    ending_id = n.ids.new("end")
    doc = assemble(ctx, got.body, ending_id, int(state["t"]))
    n.schemas.ending(doc)  # 不合数据契约就抛 SchemaError，任务按失败重来
    ms = int((time.monotonic() - started) * 1000)
    push = [{"type": "ending_ready", "endingId": ending_id}]
    async with n.engine.begin() as c:
        live = await c.scalar(
            select(playthroughs.c.status).where(playthroughs.c.playthrough_id == task.pid).with_for_update()
        )
        if live is None:
            raise Gone(task.pid)
        status = await c.scalar(select(turns.c.status).where(turns.c.turn_id == task.turn_id).with_for_update())
        if status != "leased":
            raise Gone(task.turn_id)
        await c.execute(
            insert(endings).values(ending_id=ending_id, playthrough_id=task.pid, body=doc, decided_at=func.now())
        )
        await c.execute(
            update(utterances)
            .where(utterances.c.playthrough_id == task.pid, utterances.c.text.is_not(None))
            .values(text=None)
        )
        await store.clear_plan_texts(c, task.pid, None)
        m = playthrough_metrics.c
        await c.execute(
            update(playthrough_metrics)
            .where(m.playthrough_id == task.pid)
            .values(
                ending_outcome=ctx.outcome,
                ending_template=got.template,
                ending_calls=got.calls,
                ending_ms=ms,
                **cost_values(spend),
            )
        )
        spend.usd.clear()
        await c.execute(
            update(turns)
            .where(turns.c.turn_id == task.turn_id)
            .values(
                status="done",
                outcome="committed",
                minutes=0,
                lease_until=None,
                settled_at=func.now(),
                result={"push": push, "pieces": [], "seq": pt["last_seq"], "endingId": ending_id},
            )
        )
        await n._notify(c, task, seq=int(pt["last_seq"]), outcome="committed")
    with n.tracer.span(
        "narrator.ending.done",
        trigger=ctx.trigger,
        outcome=ctx.outcome,
        template=got.template,
        calls=got.calls,
        failed_rules=sorted({p.rule for p in got.problems}),
        **span,
    ) as sp:
        sp.attrs["duration_ms"] = ms
    log.info("结局 %s：%s，模板 %s，调了 %d 次，%d ms", task.pid, ctx.outcome, got.template, got.calls, ms)
    return Result(task, [], state, "committed", 0, [], push, {"endingId": ending_id, "template": got.template})
