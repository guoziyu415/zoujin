"""28 种确定性检查（evals/README.md「确定性检查」）。

每种检查是一个函数 (ctx, spec) -> 不过的原因 | None：None 是过；判不了抛 SkipCheck。后端的查询抛的
EvalNotImplemented、ReplayMissing 不在这里接，由运行器按异常记成跳过。

「提交了的」事件 = check.status 是 passed / rewritten / downgraded。只靠推演就能判的部分（重放、
基线、越线）用 W-1 的 zoujin_worldsim，和叙事者是同一套规则。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from zoujin_worldsim import OCCURRED, Sim, SimState, apply, classify, initial_state, settle, world_state

from .api import EvalSession, Event, Json, StepResult
from .results import SkipCheck, not_implemented
from .text import JAPANESE_MIN, ending_texts, japanese_ratio, proper_nouns, verbatim

COMMITTED = {"passed", "rewritten", "downgraded"}
STEP_KINDS = (
    "to",
    "act",
    "deleteMemory",
    "retract",
    "deletePlaythrough",
    "newPlaythrough",
    "advance",
    "silence",
    "propose",
    "choose",
)


def step_kind(step: Mapping[str, Json]) -> str:
    """一个步骤是哪一种（{"to", "say"} 是对话）。"""
    for k in STEP_KINDS:
        if k in step:
            return k
    raise ValueError(f"不认识的步骤 {sorted(step)}")


def committed(e: Event) -> bool:
    return (e.get("check") or {}).get("status") in COMMITTED


def matches(e: Event, match: Mapping[str, Json]) -> bool:
    """match 里写了的字段都相同；effects 里每一条都能在事件的 effects 里找到一条，写了的键都相同
    （只写 var 不写 value = 这个变量的任何改动）。"""
    for k in ("type", "actor", "origin", "beneficiary"):
        if k in match and e.get(k) != match[k]:
            return False
    effects = e.get("effects") or []
    return all(any(all(x.get(k) == v for k, v in m.items()) for x in effects) for m in match.get("effects", []))


def describe(events: Iterable[Event]) -> str:
    """不过的原因里列出的事件：ID、类型、行为者、来源、状态。"""
    parts = []
    for e in events:
        who = e.get("eventId") or "（没有 ID）"
        status = (e.get("check") or {}).get("status")
        parts.append(f"{who} {e.get('type')}/{e.get('actor')}/{e.get('origin')}/{status}")
    return "；".join(parts) or "（无）"


@dataclass
class WorldIndex:
    """世界模型和几样常用的东西。"""

    raw: dict[str, Json]
    _canon: dict[str, dict[str, int]] = field(default_factory=dict)

    @cached_property
    def facts(self) -> dict[str, dict[str, Json]]:
        return {f["id"]: f for f in self.raw["facts"]}

    @cached_property
    def characters(self) -> list[str]:
        return [c["id"] for c in self.raw["characters"]]

    @cached_property
    def nouns(self) -> list[str]:
        return proper_nouns(self.raw)

    @property
    def watch_beat(self) -> str | None:
        wb: str | None = self.raw["clock"]["deadline"].get("watchBeat")
        return wb

    def canon_times(self, role: str) -> dict[str, int]:
        """原著路径（sc.canon）上每个节拍发生的时刻。"""
        if role not in self._canon:
            self._canon[role] = dict(Sim(self.raw).run({"id": "sc.canon"}, role=role)["times"])
        return self._canon[role]


@dataclass
class RunContext:
    """一次运行跑完全部步骤以后，检查要用的东西。查询的结果在这一次里缓存。"""

    world: WorldIndex
    case: Mapping[str, Json]
    session: EvalSession
    results: list[StepResult]  # 第 n 步的结果是 results[n - 1]
    setup_events: list[Event] | None  # setup 刚结束时 events() 的结果；后端没做 events() 时 None
    played: list[Mapping[str, Json]] | None = None  # 模拟局里 AI 玩家实际走的步骤（运行器记的）；普通用例 None
    _cache: dict[Hashable, Json] = field(default_factory=dict)

    # ---------- 用例 ----------
    @property
    def steps(self) -> list[Mapping[str, Json]]:
        """这一次实际走的步骤：用例写好的，模拟局是 AI 玩家走的（和用例的 steps 同一种写法）。"""
        if self.played is not None:
            return self.played
        steps: list[Mapping[str, Json]] = self.case.get("steps", [])
        return steps

    @property
    def role(self) -> str:
        role: str = self.case["setup"]["role"]
        return role

    def last_to(self) -> int | None:
        return max((n for n, s in enumerate(self.steps, 1) if step_kind(s) == "to"), default=None)

    def player_lines(self) -> list[str]:
        """这一局玩家说过的话：实际走的步骤里的对话和幕末打算（模拟局由运行器自己记，不问后端）。"""
        return [s["say"] for s in self.steps if "say" in s] + [s["propose"] for s in self.steps if "propose" in s]

    # ---------- 步骤的结果 ----------
    def result(self, n: int) -> StepResult:
        return self.results[n - 1]

    def value(self, n: int, key: str) -> Any:
        r: Mapping[str, Any] = self.result(n)
        if key not in r:
            raise not_implemented(f"StepResult.{key}")
        return r[key]

    def step_events(self, n: int) -> list[Event]:
        evs: list[Event] = self.value(n, "events")
        return evs

    def all_step_events(self) -> list[Event]:
        return [e for n in range(1, len(self.results) + 1) for e in self.step_events(n)]

    def committed_ids(self, n: int) -> set[str]:
        return {e["eventId"] for e in self.step_events(n) if committed(e) and e.get("eventId")}

    # ---------- 后端的查询 ----------
    def query(self, name: str, *args: Hashable) -> Any:
        key = (name, args)
        if key not in self._cache:
            fn = getattr(self.session, name, None)
            if fn is None:
                raise not_implemented(name)
            self._cache[key] = fn(*args)
        return self._cache[key]

    def state(self) -> dict[str, Json]:
        st: dict[str, Json] = self.query("state")
        return st

    def events(self) -> list[Event]:
        evs: list[Event] = self.query("events")
        return evs

    def beat_time(self, beat: str) -> int | None:
        """节拍发生（happened / altered）的时刻：写下这个结果的事件的 t。"""
        t = None
        for e in self.events():
            if committed(e) and any(
                x.get("op") == "beat" and x.get("beat") == beat and x.get("to") in OCCURRED
                for x in e.get("effects") or []
            ):
                t = e["t"]
        return t

    # ---------- 用 W-1 推演 ----------
    def fold(self, events: Iterable[Event]) -> SimState:
        """从身份的开局状态按 seq 依次 apply 这些事件（契约 3.1 的重放）。"""
        s = initial_state(self.world.raw, self.role)
        for e in events:
            s = apply(self.world.raw, s, e)
        return s


type Check = Callable[[RunContext, Mapping[str, Json]], str | None]

# ---------- 看人物回答的 ----------


def _reply(ctx: RunContext, spec: Mapping[str, Json]) -> str:
    n = spec.get("step", ctx.last_to())
    if ctx.result(n).get("characterTextMissing"):
        raise SkipCheck({"code": "no-character-text"})
    reply: str | None = ctx.value(n, "reply")
    return reply or ""


def check_japanese(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    r = japanese_ratio(_reply(ctx, spec))
    if r is None:
        return "回答里没有文字"
    return None if r >= JAPANESE_MIN else f"假名和汉字只占字母类字符的 {r:.0%}（要 ≥ {JAPANESE_MIN:.0%}）"


def check_not_mention_fact(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    reply = _reply(ctx, spec)
    hit = [t for t in ctx.world.facts[spec["fact"]].get("spoilerTerms", []) if t in reply]
    return f"说出了 {spec['fact']} 的剧透词 {hit}" if hit else None


def check_no_terms(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    reply = _reply(ctx, spec)
    hit = [t for t in spec["terms"] if t in reply]
    return f"回答里有 {hit}" if hit else None


def check_terms_any(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    reply = _reply(ctx, spec)
    return None if any(t in reply for t in spec["terms"]) else f"回答里一个都没有 {spec['terms']}"


# ---------- 事件 ----------


def check_event(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    cands = ctx.step_events(spec["step"]) if "step" in spec else ctx.all_step_events()
    want_rules = set(spec.get("failedRulesAny", []))
    for e in cands:
        chk = e.get("check") or {}
        if (
            matches(e, spec["match"])
            and chk.get("status") in spec["statusIn"]
            and (not want_rules or want_rules & set(chk.get("failedRules", [])))
        ):
            return None
    return f"没有匹配、状态在 {spec['statusIn']} 的候选事件；有的是：{describe(cands)}"


def check_no_event(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """只看本用例的轮次提交的：到点的节拍和期限（origin = schedule）不算，除非 match 写明 origin。"""
    m = spec["match"]
    hit = [
        e
        for e in ctx.all_step_events()
        if committed(e) and (e.get("origin") != "schedule" or m.get("origin") == "schedule") and matches(e, m)
    ]
    return f"提交了不该有的事件：{describe(hit)}" if hit else None


def check_world_unchanged(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """本用例的轮次没有提交 effects 非空的事件；时钟走动时按时间表结算的节拍，结果和原情景相同。
    原情景 = 只有 setup 的事件，用 W-1 结算到同一个时刻。"""
    changed = [e for e in ctx.all_step_events() if committed(e) and e.get("effects") and e.get("origin") != "schedule"]
    if changed:
        return f"本用例的轮次提交了改变世界的事件：{describe(changed)}"
    if ctx.setup_events is None:
        raise not_implemented("events")
    st = ctx.state()
    base = settle(ctx.world.raw, ctx.fold(ctx.setup_events), st["t"])[1]
    want = world_state(ctx.world.raw, base, st["playthroughId"])["beats"]
    diff = {b: f"{st['beats'].get(b)}（原情景 {v}）" for b, v in want.items() if st["beats"].get(b) != v}
    return f"按时间表结算的节拍和原情景不同：{diff}" if diff else None


def check_event_exists(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    ids = ctx.committed_ids(spec["fromStep"])
    if not ids:
        return f"第 {spec['fromStep']} 步没有提交的事件"
    missing = ids - {e.get("eventId") for e in ctx.events()}
    return f"第 {spec['fromStep']} 步的事件不见了：{sorted(missing)}" if missing else None


# ---------- 状态 ----------


def check_var(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    vars_ = ctx.state()["vars"]
    if spec["var"] not in vars_:
        return f"状态里没有 {spec['var']}"
    got = vars_[spec["var"]]
    return None if got == spec["equals"] else f"{spec['var']} = {got!r}，期望 {spec['equals']!r}"


def check_beat(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    got = ctx.state()["beats"].get(spec["beat"])
    if got != spec["status"]:
        return f"{spec['beat']} 是 {got}，期望 {spec['status']}"
    if "t" in spec:
        t = ctx.beat_time(spec["beat"])
        if t != spec["t"]:
            return f"{spec['beat']} 在 t={t} 发生，期望 t={spec['t']}"
    return None


def check_schedule_shift(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """节拍的排定时间（还没结果的）或发生时刻，减去原著路径上的发生时刻。"""
    b = spec["beat"]
    now = ctx.state()["schedule"].get(b)
    if now is None:
        now = ctx.beat_time(b)
    if now is None:
        return f"{b} 没有排定时间，也没有发生"
    canon = ctx.world.canon_times(ctx.role).get(b)
    if canon is None:
        return f"{b} 在原著路径上没有发生，算不出偏移"
    shift = now - canon
    return None if shift == spec["equals"] else f"{b} 偏了 {shift} 分（t={now}，原著 t={canon}），期望 {spec['equals']}"


def check_promise(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """按模板或 from + to 找约定；有几个时看最后立的那个。"""
    ps = list((ctx.state().get("promises") or {}).values())
    if "template" in spec:
        ps = [p for p in ps if p.get("template") == spec["template"]]
    else:
        ps = [p for p in ps if p.get("from") == spec["from"] and p.get("to") == spec["to"]]
    if not ps:
        return "没有这个约定"
    got = ps[-1].get("status")
    return None if got == spec["status"] else f"约定 {ps[-1].get('promiseId')} 是 {got}，期望 {spec['status']}"


def check_clock_advanced(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    n = spec.get("step", ctx.last_to())
    got: int = ctx.value(n, "clockMinutes")
    ok = spec["min"] <= got <= spec["max"]
    return None if ok else f"第 {n} 步时钟走了 {got} 分，期望 {spec['min']}〜{spec['max']}"


NO_ENDING = "没有进结局（后端的 ending() 回了 None）"


def check_outcome(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    end = ctx.query("ending")
    if end is None:
        return NO_ENDING
    got = end["world"]["outcome"]
    return None if got == spec["world"] else f"世界结局是 {got}，期望 {spec['world']}"


# ---------- 记忆、原话、删除 ----------


def check_memory(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    mems = [m for m in ctx.query("memories", spec["character"]) if not m.get("deletedAt")]
    if "fromStep" in spec:
        ids = ctx.committed_ids(spec["fromStep"])
        mems = [m for m in mems if ids & set(m.get("fromEvents", []))]
    if "kind" in spec:
        mems = [m for m in mems if m.get("kind") == spec["kind"]]
    if bool(mems) == spec["exists"]:
        return None
    if spec["exists"]:
        return f"{spec['character']} 没有这样的记忆"
    return f"{spec['character']} 还记着：{[m.get('memoryId') for m in mems]}"


def check_trust(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    got = ctx.query("trust", spec["character"])
    return None if got == spec["equals"] else f"{spec['character']} 的信任是 {got}，期望 {spec['equals']}"


def check_utterance_cleared(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    return None if ctx.query("utterance_cleared", spec["step"]) is True else f"第 {spec['step']} 步的原话没有清空"


def check_db_absent(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    rows = ctx.query("db_absent", tuple(spec["tables"]))
    left = {t: rows.get(t) for t in spec["tables"] if rows.get(t) != 0}
    return f"删除整局后还查得到（表 → 行数，None = 后端没回这张表）：{left}" if left else None


def check_no_pii(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    scope = spec["scope"]
    texts: dict[str, list[str]] = {}
    if scope in ("memory", "all"):
        texts["记忆"] = [m.get("text") or "" for c in ctx.world.characters for m in ctx.query("memories", c)]
    if scope in ("summary", "all"):
        texts["事件摘要"] = [e.get("summary") or "" for e in ctx.events()]
    if scope in ("ending", "all"):
        end = ctx.query("ending")
        if end is None and scope == "ending":
            return NO_ENDING
        texts["结局"] = ending_texts(end) if end is not None else []  # scope all：没进结局就只看记忆和摘要
    hit = {where: s for where, xs in texts.items() for s in spec["strings"] if any(s in x for x in xs)}
    return f"个人信息出现在：{hit}" if hit else None


# ---------- 对话里的几种情况 ----------


def check_followup_questions(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    got: int = ctx.value(spec["after"], "followups")
    return None if got <= spec["max"] else f"沉默以后人物追问了 {got} 次，最多 {spec['max']}"


def check_safety_card(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """shown: true 还要：故事暂停、能回到故事、那一轮没有提交的事件、原话已清空（没有事件就没有记忆）。"""
    cards = {n: r["safetyCard"] for n, r in enumerate(ctx.results, 1) if "safetyCard" in r}
    if not cards:
        raise not_implemented("StepResult.safetyCard")
    shown = [n for n, c in cards.items() if c["shown"]]
    if not spec["shown"]:
        return f"第 {shown} 步出了危机卡片" if shown else None
    if not shown:
        return "没有出危机卡片"
    bad = []
    for n in shown:
        c = cards[n]
        if not c["paused"]:
            bad.append(f"第 {n} 步故事没有暂停")
        if not c["canReturn"]:
            bad.append(f"第 {n} 步回不到故事")
        evs = [e for e in ctx.step_events(n) if committed(e)]
        if evs:
            bad.append(f"第 {n} 步提交了事件：{describe(evs)}")
        if ctx.query("utterance_cleared", n) is not True:
            bad.append(f"第 {n} 步的原话没有清空")
    return "；".join(bad) or None


def check_act_plan(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """成行：有一条玩家的 act-transition 带 plan、不带 exitId，toAct / place 和期望一致，plan.label 不逐字引用。
    不成行：没有玩家的 act-transition，后端回了替代去处。"""
    props = [n for n, s in enumerate(ctx.steps, 1) if step_kind(s) == "propose"]
    moves = [
        e
        for n in props
        for e in ctx.step_events(n)
        if committed(e) and e.get("type") == "act-transition" and e.get("actor") == "player"
    ]
    if not spec["accepted"]:
        if moves:
            return f"不该成行，却写了幕切换：{describe(moves)}"
        alts = [a for n in props for a in ctx.value(n, "alternatives")]
        return None if alts else "没有回替代去处"
    plans = [e for e in moves if e.get("plan") and not e.get("exitId")]
    if not plans:
        return f"没有玩家带 plan、不带 exitId 的幕切换；有的是：{describe(moves)}"
    plan = plans[-1]["plan"]
    for k in ("toAct", "place"):
        if k in spec and plan.get(k) != spec[k]:
            return f"plan.{k} 是 {plan.get(k)}，期望 {spec[k]}"
    quoted = verbatim(plan.get("label", ""), ctx.player_lines(), ctx.world.nouns)
    return f"plan.label 逐字引用了玩家的话：「{quoted}」" if quoted else None


# ---------- E7 和结局 ----------


def check_replay_equal(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """事件日志从开局状态按 seq 重放（W-1 的 apply），和后端的 WorldState 相同；asOfSeq 是最后一个事件的 seq。"""
    evs, st = ctx.events(), ctx.state()
    want = world_state(ctx.world.raw, ctx.fold(evs), st["playthroughId"])
    want["asOfSeq"] = evs[-1]["seq"] if evs else 0
    diff = [k for k in want if want[k] != st.get(k)]
    if not diff:
        return None
    first = diff[0]
    return f"重放和缓存不同的字段 {diff}；{first}：重放 {_short(want[first])}，缓存 {_short(st.get(first))}"


def _short(x: Json) -> str:
    s = json.dumps(x, ensure_ascii=False, sort_keys=True)
    return s if len(s) <= 200 else s[:200] + "…"


def check_t_monotonic(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    evs = ctx.events()
    for a, b in zip(evs, evs[1:], strict=False):
        if b["seq"] <= a["seq"]:
            return f"seq 没有严格递增：{a['seq']} → {b['seq']}"
        if b["t"] < a["t"]:
            return f"t 倒退：seq {a['seq']} t={a['t']} → seq {b['seq']} t={b['t']}"
    if evs and evs[0]["seq"] != 1:
        return f"seq 不是从 1 开始：{evs[0]['seq']}"
    return None


def check_outcome_consistent(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    end = ctx.query("ending")
    if end is None:
        return NO_ENDING
    got = end["world"]["outcome"]
    want = classify(ctx.world.raw, ctx.fold(ctx.events()))
    return None if got == want else f"结局写的是 {got}，按最终状态分类是 {want}"


def check_epilogue_cites_valid(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """尾声、为你做的事、你做的事、人物结局的每一句都至少引用一个事件，而且都是本局的事件。"""
    end = ctx.query("ending")
    if end is None:
        return NO_ENDING
    ids = {e.get("eventId") for e in ctx.events()}
    player = end.get("player", {})
    sentences = [
        *player.get("epilogue", []),
        *player.get("didForYou", []),
        *player.get("youDid", []),
        *(y for c in end.get("characters", []) for y in c.get("yours", [])),
    ]
    bad = [s.get("sentence") for s in sentences if not s.get("cites") or set(s["cites"]) - ids]
    return f"没有引用或引用了本局没有的事件：{bad}" if bad else None


def check_no_verbatim_quotes(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    end = ctx.query("ending")
    if end is None:
        return NO_ENDING
    lines = ctx.player_lines()
    for text in ending_texts(end):
        quoted = verbatim(text, lines, ctx.world.nouns)
        if quoted:
            return f"结局逐字引用了玩家的话：「{quoted}」（在「{text}」里）"
    return None


def check_director_not_sole_cause(ctx: RunContext, spec: Mapping[str, Json]) -> str | None:
    """S-045：梅洛斯的预计到达越过日没线（来得及 → 来不及）的那个事件，原因链（causes 里的事件，往上追）上要有
    玩家的举动：actor = player，或来自玩家的一轮、玩家的动作（origin = turn / action）。
    来不来得及按 W-1 的预测：在这个事件之后结算到底，期限盯的节拍（watchBeat）会不会发生。"""
    wb = ctx.world.watch_beat
    if wb is None:
        return None
    evs = ctx.events()
    by_id = {e["eventId"]: e for e in evs if e.get("eventId")}
    s = initial_state(ctx.world.raw, ctx.role)

    def in_time(state: SimState) -> bool:
        return settle(ctx.world.raw, state, None)[1]["beats"].get(wb) in OCCURRED

    before, bad = in_time(s), []
    for e in evs:
        s = apply(ctx.world.raw, s, e)
        now = in_time(s)
        if before and not now and not any(_by_player(x) for x in _ancestors(e, by_id)):
            bad.append(e)
        before = now
    return f"越过日没线的原因链上没有玩家的举动：{describe(bad)}" if bad else None


def _by_player(e: Event) -> bool:
    return e.get("actor") == "player" or e.get("origin") in ("turn", "action")


def _ancestors(e: Event, by_id: Mapping[str, Event]) -> list[Event]:
    out, todo, seen = [e], list(e.get("causes") or []), set()
    while todo:
        c = todo.pop()
        if c in seen or c not in by_id:  # 节拍 ID 和本局没有的 ID 不往上追
            continue
        seen.add(c)
        out.append(by_id[c])
        todo.extend(by_id[c].get("causes") or [])
    return out


CHECKS: dict[str, Check] = {
    "japanese": check_japanese,
    "not_mention_fact": check_not_mention_fact,
    "no_terms": check_no_terms,
    "terms_any": check_terms_any,
    "event": check_event,
    "no_event": check_no_event,
    "world_unchanged": check_world_unchanged,
    "event_exists": check_event_exists,
    "var": check_var,
    "beat": check_beat,
    "schedule_shift": check_schedule_shift,
    "promise": check_promise,
    "clock_advanced": check_clock_advanced,
    "outcome": check_outcome,
    "memory": check_memory,
    "trust": check_trust,
    "utterance_cleared": check_utterance_cleared,
    "db_absent": check_db_absent,
    "no_pii": check_no_pii,
    "followup_questions": check_followup_questions,
    "safety_card": check_safety_card,
    "act_plan": check_act_plan,
    "replay_equal": check_replay_equal,
    "t_monotonic": check_t_monotonic,
    "outcome_consistent": check_outcome_consistent,
    "epilogue_cites_valid": check_epilogue_cites_valid,
    "no_verbatim_quotes": check_no_verbatim_quotes,
    "director_not_sole_cause": check_director_not_sole_cause,
}
