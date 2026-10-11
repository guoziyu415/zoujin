"""逐事件推演：叙事者用的增量接口（W-1，后端提的）。

一局的状态 SimState 只由事件推出：initial_state() 给开局前的状态，之后每个事件（玩家的、叙事者的、
settle() 写出的系统事件）都用 apply() 应用。settle() 自己也是先算出系统事件的草稿，再一个个 apply()，
所以「拿事件日志从 initial_state() 重放」和「逐事件算」得到同一个状态（契约 3.1，评测 E7）。

规则和一口气推演（sim.Sim.run）一样，见 docs/data/contracts.md 2.4.1、2.5.1 和参考实现的文件头：

- 同一时刻先节拍（按 order），再期限，最后事件。所以调用方要先 settle 到事件的 t，再 apply 这个事件；
  下一次 settle 的 t2 不早于这个事件的 t。
- 节拍到了排定时间：前提成立就发生（有变体按变体演，玩家登记了 altered 按登记的演）；前提不成立的
  到 window.latest 为止每一步之后再查，成立了就在那一刻发生，过了 latest 写 prevented（时間切れ）。
- 有 delays / hastens 出边的节拍到点前提不成立就当场 prevented，它的分钟按 2.5.1 退还给下游；
  排定时间超过 latest 的（late）当场 prevented，不退还。
- 期限：时钟到 clock.deadline.t 时，按那一刻的状态判 onDeadline，成立的规则写成一个系统事件。
  没有规则成立也写一个 effects 为空的系统事件：状态只由事件推出，靠它记下「期限已经结算过」。

- 本局对一个还没结果的节拍只有一种改动（契约第 3 节，1.6 写清）：推迟、提前按带符号的分钟相加，净值 0 就去掉；
  prevented 顶掉之前的改动；别的组合 check_effects() 报 bad-state，apply() 抛 ValueError（sim.merge_change）。
- origin = "schedule" 只用于到点的节拍（type beat，一条 beat 结果）和期限（type action，每局一条，不早于期限）。
- （1.7）relocate 写了 spot 就记在 spots 里；没写 spot 时换到别的地点才去掉，同一个地点里不动（节拍先把参与人物移到
  节拍地点，已经站在那里的人保持原来的位置点）。位置点不进任何判定，给后端摆人用（契约 3.1）。

一口气推演没有、这里才有的两处，24 次推演都不受影响：
① 玩家在 t 时登记的改动让某个还没结果的节拍的排定时间提前到 t 之前，这个节拍在 t 判
  （一口气推演是从头就知道全部改动）；
② 下游已经在等前提时，上游被阻止让它的排定时间推后，它回到「还没到点」，到新的排定时间再判。
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, NotRequired, TypedDict

from .sim import BIG, OCCURRED, Effect, Override, Sim, World, change_conflict, merge_change, role_of

SCHEDULE = "schedule"  # Event.origin：到点的节拍和期限
SPOT = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*")  # 1.7：位置点名（data common.schema.json 的 SpotId）


class SimState(TypedDict):
    """一局到某个事件为止的状态，能直接存成 JSON。只由 initial_state() 和 apply() 产生。"""

    worldModelVersion: str
    role: str
    t: int  # 时钟 = max(之前的时钟, 每个事件的 t + dt)
    cursor: int | None  # 最后一个事件的 t；还没有事件时是 None
    seq: int  # 应用过几个事件（WorldState.asOfSeq）
    vars: dict[str, Any]  # 所有 stateVar
    holdings: dict[str, str | None]  # portable 物品（和开局有人拿着的物品）→ 现在谁拿着
    locations: dict[str, str]  # 人物 → 地点
    spots: NotRequired[dict[str, str]]  # （1.7）人物 → 指定的位置点；1.7 之前存下的状态没有这一项
    knowledge: dict[str, list[str]]  # 人物 → 运行时学到的事实（按学到的先后，不重复）
    runFacts: dict[str, dict[str, Any]]  # factId → RunFact（madeBy 没有事件 ID 时是 None）
    promises: dict[str, dict[str, Any]]  # promiseId → StoryPromise（同上）
    beats: dict[str, str]  # 有结果的节拍：happened / altered / prevented
    times: dict[str, int]  # 发生（happened / altered）的时刻
    variants: dict[str, str]  # 按变体演的节拍 → 变体 ID
    overrides: dict[str, Override]  # 本局对节拍的改动，按登记的先后（参考实现的 sc.beats）
    deadline: bool  # 期限结算过了


class Draft(TypedDict):
    """settle() 写出的系统事件草稿。event 是契约 Event 的子集，B-0 补上 eventId、seq、summary 等再写库。"""

    event: dict[str, Any]
    beat: str | None  # 哪个节拍（B-0 用它取 summary）；期限是 None
    variant: str | None  # 按哪个变体演的
    reason: str | None  # prevented 的原因，一句日语，B-0 写进 check.reason
    reasonCode: str | None  # late / overridden / requires / precondition / expired


type Emit = Callable[[Draft], None]
type Bad = Callable[[int, str, str], None]


class Problem(TypedDict):
    """check_effects() 报的一个问题。"""

    index: int  # 第几个 effect
    code: str
    message: str
    note: NotRequired[str]  # valueRequires 的 note（日语），叙事者的 reason 用它


REASONS = {
    "late": "時間切れ（予定の時刻が刻限を過ぎた）",
    "overridden": "この局の出来事で起きなくなった",
    "requires": "前の出来事が起きなかった",
    "precondition": "その時点で前提が成り立たなかった",
    "expired": "前提が成り立たないまま時間切れになった",
    "expired-requires": "前の出来事が起きないまま時間切れになった",
}


class _Sim(Sim):
    """settle() 里排程要算很多次，改动列表没变时结果也不变，按内容缓存。返回的 dict / set 调用方不能改。"""

    def __init__(self, world: World) -> None:
        super().__init__(world)
        self._cache: dict[tuple[str, bool], tuple[dict[str, int], set[str]]] = {}

    def schedule(self, over: Mapping[str, Override], _floor: bool = True) -> tuple[dict[str, int], set[str]]:
        key = (json.dumps(over, sort_keys=True, ensure_ascii=False), _floor)
        if key not in self._cache:
            self._cache[key] = super().schedule(over, _floor)
        return self._cache[key]


def initial_state(world: World, role_id: str) -> SimState:
    """这个身份开局前的状态：时钟 0，变量初值（var.player.location = startPlace，var.act.current = startAct），
    人物在 initialPlace，物品在 Character.items、Role.items 的人手上。调用方接着 settle 到身份的 startT。"""
    role = role_of(world, role_id)
    vars_ = {v["id"]: v["default"] for v in world["stateVars"]}
    vars_["var.player.location"] = role["startPlace"]
    if "startAct" in role and "var.act.current" in vars_:
        vars_["var.act.current"] = role["startAct"]
    holdings: dict[str, str | None] = {it["id"]: None for it in world.get("items", []) if it.get("portable")}
    for c in world["characters"]:
        for it in c.get("items", []):
            holdings[it] = c["id"]
    for it in role.get("items") or []:
        holdings[it] = "player"
    return {
        "worldModelVersion": world["worldModelVersion"],
        "role": role_id,
        "t": 0,
        "cursor": None,
        "seq": 0,
        "vars": vars_,
        "holdings": holdings,
        "locations": {c["id"]: c["initialPlace"] for c in world["characters"]},
        "spots": {},
        "knowledge": {},
        "runFacts": {},
        "promises": {},
        "beats": {},
        "times": {},
        "variants": {},
        "overrides": {},
        "deadline": False,
    }


def flat(state: SimState) -> dict[str, Any]:
    """条件求值用的视图：变量加上物品的持有者（参考实现把两者放在同一个 dict 里）。"""
    return {**state["holdings"], **state["vars"]}


def apply(world: World, state: SimState, event: Mapping[str, Any]) -> SimState:
    """应用一个事件，返回新的状态（不改传进来的）。用到 event 的 t、dt、origin、type、effects，有的话还有 eventId、seq。

    origin = "schedule" 的系统事件里，beat 效果是节拍的结果；其他事件里是本局的改动（delayed / hastened /
    prevented / altered，按 sim.merge_change 合），to = "happened" 契约没定义，抛 ValueError。
    别的不合法的地方也抛 ValueError，叙事者应该先用 check_effects() 挡掉：
    - 不是 schedule 的事件之前还有没结算的节拍或期限（没先 settle 到它的 t；同一时刻的上一个事件之后也要再 settle，
      它可能让在等前提的节拍成立）。重放事件日志时这条能抓到漏写的系统事件；
    - 带 seq 的事件，seq 不是上一个 + 1；
    - schedule 事件不是到点的节拍或期限，或期限写了第二次、早于期限。"""
    _same_world(world, state)
    if event.get("origin") != SCHEDULE and (state["cursor"] is None or event["t"] >= state["cursor"]):
        due = settle(world, state, event["t"])[0]
        if due:
            what = "、".join(d["beat"] or "期限" for d in due)
            raise ValueError(f"t={event['t']} 之前还有没结算的 {what}：先 settle 到 {event['t']} 再 apply")
    return _apply(_Sim(world), state, event)


def _apply(sim: Sim, state: SimState, event: Mapping[str, Any]) -> SimState:
    t, dt = event["t"], event.get("dt", 0)
    if state["cursor"] is not None and t < state["cursor"]:
        raise ValueError(f"事件的 t 倒退：{t} < {state['cursor']}")
    if "seq" in event and event["seq"] != state["seq"] + 1:
        raise ValueError(f"seq 不连续：{event['seq']}，上一个是 {state['seq']}")
    system = event.get("origin") == SCHEDULE
    if system:
        _check_schedule_event(sim, state, event)
    s = copy.deepcopy(state)
    eid = event.get("eventId")
    for e in event["effects"]:
        _apply_effect(sim, s, e, t, system, eid)
    if system and event.get("type") == "action":  # 期限
        s["deadline"] = True
    s["t"] = max(s["t"], t + dt)
    s["cursor"] = t
    s["seq"] += 1
    return s


def _check_schedule_event(sim: Sim, state: SimState, event: Mapping[str, Any]) -> None:
    """契约第 3 节（1.6 写清）：origin = "schedule" 只用于到点的节拍和期限，别的系统事件不用它。"""
    ty = event.get("type")
    if ty == "beat":
        n = sum(1 for e in event["effects"] if e["op"] == "beat")
        if n != 1:
            raise ValueError(f"到点的节拍事件要有且只有一条 beat 效果，这里 {n} 条")
    elif ty == "action":
        dl = sim.world["clock"]["deadline"]["t"]
        if state["deadline"]:
            raise ValueError("期限已经结算过：每局只有一条期限事件")
        if event["t"] < dl:
            raise ValueError(f"期限事件的 t={event['t']} 早于期限 {dl}")
    else:
        raise ValueError(f"origin = schedule 只用于到点的节拍（type beat）和期限（type action），不能是 {ty!r}")


def _apply_effect(sim: Sim, s: SimState, e: Effect, t: int, system: bool, eid: str | None) -> None:
    op = e["op"]
    if op == "set":
        s["vars"][e["var"]] = e["value"]
    elif op == "inc":
        v = sim.svars[e["var"]]
        s["vars"][e["var"]] = max(v.get("min", -BIG), min(v.get("max", BIG), s["vars"][e["var"]] + e["by"]))
    elif op == "relocate":  # 1.7：写了 spot 就站那里；没写时换了地点才去掉，同一个地点里不动（契约 3.1）
        c, spots = e["character"], s.setdefault("spots", {})
        if "spot" in e:
            spots[c] = e["spot"]
        elif s["locations"].get(c) != e["place"]:
            spots.pop(c, None)
        s["locations"][c] = e["place"]
    elif op == "hold":
        s["holdings"][e["item"]] = e["to"]
    elif op == "learn":
        known = s["knowledge"].setdefault(e["character"], [])
        if e["fact"] not in known:
            known.append(e["fact"])
    elif op == "improv":
        if e["factId"] in s["runFacts"]:
            raise ValueError(f"即兴设定重复：{e['factId']}")
        s["runFacts"][e["factId"]] = {
            "factId": e["factId"],
            "character": e["character"],
            "statement": e["statement"],
            "madeBy": eid,
        }
    elif op == "promise":
        _apply_promise(s, e, eid)
    elif op == "beat":
        if system:
            _apply_beat_result(sim, s, e, t, eid)
        else:
            _apply_beat_change(s, e)
    else:
        raise ValueError(f"未知的效果 {op}")


def _apply_promise(s: SimState, e: Effect, eid: str | None) -> None:
    pid = e.get("promiseId")
    if not pid:
        raise ValueError("提交的 promise 效果要带 promiseId")
    if e["change"] == "made":
        if pid in s["promises"]:
            raise ValueError(f"约定重复：{pid}")
        made: dict[str, Any] = {"promiseId": pid, "from": e["from"], "to": e["to"], "text": e["text"]}
        for k in ("due", "template"):
            if k in e:
                made[k] = copy.deepcopy(e[k])
        made["status"], made["madeBy"] = "open", eid
        s["promises"][pid] = made
        return
    p = s["promises"].get(pid)
    if p is None or p["status"] != "open":
        raise ValueError(f"只有 open 的约定能变成 {e['change']}：{pid}")
    p["status"], p["resolvedBy"] = e["change"], eid


def _apply_beat_result(sim: Sim, s: SimState, e: Effect, t: int, eid: str | None) -> None:
    bid, to = e["beat"], e["to"]
    if bid in s["beats"]:
        raise ValueError(f"{bid} 已经有结果（{s['beats'][bid]}）")
    if to in OCCURRED:
        s["beats"][bid], s["times"][bid] = to, t
        if to == "altered":
            if e.get("note") in {v["id"] for v in sim.beats[bid].get("variants", [])}:
                s["variants"][bid] = e["note"]
            for x in e.get("outcomes", []):
                _apply_effect(sim, s, x, t, True, eid)
    elif to == "prevented":
        # 2.5.1：有 delays / hastens 出边的节拍到点前提不成立而被阻止，它的分钟退还给下游（参考实现 run() 的 auto）
        late = sim.schedule(s["overrides"])[1]
        if bid in sim.timed and bid not in late and bid not in s["overrides"] and sim.requires_met(bid, s["beats"]):
            s["overrides"][bid] = {"to": "prevented"}
        s["beats"][bid] = "prevented"
    else:
        raise ValueError(f"系统事件里的 beat 只能是 happened / altered / prevented：{to}")


def _apply_beat_change(s: SimState, e: Effect) -> None:
    bid = e["beat"]
    if e["to"] == "happened":
        raise ValueError(f"非系统事件里的 {{op: beat, to: happened}} 契约没定义：{bid}")
    if bid in s["beats"]:
        raise ValueError(f"{bid} 已经有结果（{s['beats'][bid]}），不能再改")
    merge_change(s["overrides"], e)


def settle(
    world: World, state: SimState, t2: int | None, *, player_present: bool = True
) -> tuple[list[Draft], SimState]:
    """时钟走到 t2：按先后结算排定时间 ≤ t2 的节拍和期限。t2 = None 时结算到所有节拍都有结果、期限也结算过。

    player_present=False：这一段玩家一律算不在场，节拍落在 `var.player.location` 也不给玩家写 learn（契约 2.1 ②）。
    幕切换的第 3 步用（2.8.1）：这时玩家的地点还没换，人已经不在了。

    返回 (系统事件的草稿，结算后的状态)。结算后的状态 = 把草稿依次 apply 到传进来的状态。不改传进来的状态。"""
    _same_world(world, state)
    sim = _Sim(world)
    s = state
    drafts: list[Draft] = []
    end = BIG * 2 if t2 is None else t2

    def emit(d: Draft) -> None:
        nonlocal s
        s = _apply(sim, s, d["event"])
        drafts.append(d)

    def current() -> SimState:
        return s

    now = s["cursor"] if s["cursor"] is not None else -BIG
    # 排定时间已过、还没结果的节拍在等前提（上一次 settle 判过；判一次就有结果的那几种不会在等）
    seen = {b for b, tb in _schedule(sim, s).items() if tb <= now} - _special(sim, s)
    if s["cursor"] is not None:
        _recheck(sim, now, seen, emit, current, player_present)

    while True:
        sched = _schedule(sim, s)
        # 排定时间被推后的回到「还没到点」；判一次就有结果的那几种（_special）不会在等
        seen &= {b for b, tb in sched.items() if tb <= now}
        seen -= _special(sim, s)
        items: list[tuple[int, int, int, str, str | None]] = []
        for b, tb in sched.items():
            order = sim.beats[b]["order"]
            if b not in seen:
                if max(tb, now) <= end:
                    items.append((max(tb, now), 0, order, "beat", b))
            elif b not in sim.timed:
                latest = sim.beats[b]["window"]["latest"]
                if latest < end:
                    items.append((max(latest, now), 3, order, "expire", b))
        dl = world["clock"]["deadline"]["t"]
        if not s["deadline"] and dl <= end:
            items.append((max(dl, now), 1, 0, "deadline", None))
        if not items:
            break
        tt, _, _, kind, bid = min(items)
        now = tt
        if kind == "deadline" or bid is None:
            emit(_deadline_draft(sim, world, s, tt))
        elif kind == "beat":
            seen.add(bid)
            _first_check(sim, s, bid, tt, emit, player_present)
        else:
            code = "expired" if sim.requires_met(bid, s["beats"]) else "expired-requires"
            emit(_prevented(sim, bid, tt, code))
        _recheck(sim, tt, seen, emit, current, player_present)
    return drafts, s


def _schedule(sim: Sim, s: SimState) -> dict[str, int]:
    """还没结果的节拍的本局排定时间（2.5.1）。"""
    shift = sim.schedule(s["overrides"])[0]
    return {b: x["window"]["canonical"] + shift.get(b, 0) for b, x in sim.beats.items() if b not in s["beats"]}


def _special(sim: Sim, s: SimState) -> set[str]:
    """判一次就一定有结果的节拍：有 delays / hastens 出边的、排定时间超过 latest 的、玩家登记了 prevented 的。"""
    late = sim.schedule(s["overrides"])[1]
    return {
        b
        for b in sim.beats
        if b not in s["beats"] and (b in sim.timed or b in late or s["overrides"].get(b, {}).get("to") == "prevented")
    }


def _first_check(sim: Sim, s: SimState, b: str, t: int, emit: Emit, player_present: bool) -> None:
    """节拍到了排定时间（参考实现的 _step1）。"""
    x = sim.beats[b]
    late = sim.schedule(s["overrides"])[1]
    if b in late:
        emit(_prevented(sim, b, t, "late"))
    elif s["overrides"].get(b, {}).get("to") == "prevented":
        emit(_prevented(sim, b, t, "overridden"))
    elif b not in sim.timed and t > x["window"]["latest"]:
        emit(_prevented(sim, b, t, "expired" if sim.requires_met(b, s["beats"]) else "expired-requires"))
    elif not sim.requires_met(b, s["beats"]):
        if b in sim.timed:  # 参考实现记 blocked、不再查，结局里等于 prevented
            emit(_prevented(sim, b, t, "requires"))
    elif not sim.holds(x["preconditions"], flat(s)):
        if b in sim.timed:
            emit(_prevented(sim, b, t, "precondition"))
    else:
        emit(_occur_draft(sim, s, b, t, player_present))


def _recheck(
    sim: Sim, t: int, seen: set[str], emit: Emit, current: Callable[[], SimState], player_present: bool
) -> None:
    """每一步之后按 order 再查在等前提的节拍，成立的在此刻 t 发生；查到不再变化（参考实现的 _recheck）。"""
    changed = True
    while changed:
        changed = False
        s = current()
        sched, special = _schedule(sim, s), _special(sim, s)
        waiting = sorted(
            (
                b
                for b in seen
                if b in sched and sched[b] <= t and b not in special and t <= sim.beats[b]["window"]["latest"]
            ),
            key=lambda b: sim.beats[b]["order"],
        )
        for b in waiting:
            s = current()
            if (
                b not in s["beats"]
                and sim.requires_met(b, s["beats"])
                and sim.holds(sim.beats[b]["preconditions"], flat(s))
            ):
                emit(_occur_draft(sim, s, b, t, player_present))
                changed = True


def _occur_draft(sim: Sim, s: SimState, b: str, t: int, player_present: bool) -> Draft:
    """节拍发生：先把参与人物移到节拍地点，再写结果（参考实现的 _occur）。"""
    x = sim.beats[b]
    effects: list[dict[str, Any]] = [{"op": "relocate", "character": p, "place": x["place"]} for p in x["participants"]]
    o = s["overrides"].get(b, {})
    variant = None
    if o.get("to") == "altered":  # 玩家的事件事先改了这个节拍
        effects.append({"op": "beat", "beat": b, "to": "altered", "outcomes": copy.deepcopy(o["outcomes"])})
    else:
        v = sim.variant_of(x, flat(s))
        if v is not None:  # 1.4：到点时按本局状态换一种演法
            variant = v["id"]
            effects.append(
                {"op": "beat", "beat": b, "to": "altered", "outcomes": copy.deepcopy(v["outcomes"]), "note": v["id"]}
            )
        else:
            effects.append({"op": "beat", "beat": b, "to": "happened"})
            effects += copy.deepcopy(list(x["outcomes"]))
    # 玩家在场：public 事实玩家也知道了（契约 2.1、2.3，1.7）
    if player_present and s["vars"].get("var.player.location") == x["place"]:
        known = s["knowledge"].get("player", [])
        effects += [
            {"op": "learn", "character": "player", "fact": f["id"]}
            for f in sim.world["facts"]
            if f["trueFrom"] == b and f["visibility"] == "public" and f["id"] not in known
        ]
    return {
        "event": _system_event("beat", t, x["place"], effects),
        "beat": b,
        "variant": variant,
        "reason": None,
        "reasonCode": None,
    }


def _prevented(sim: Sim, b: str, t: int, code: str) -> Draft:
    x = sim.beats[b]
    return {
        "event": _system_event("beat", t, x["place"], [{"op": "beat", "beat": b, "to": "prevented"}]),
        "beat": b,
        "variant": None,
        "reason": REASONS[code],
        "reasonCode": code.removesuffix("-requires"),
    }


def _deadline_draft(sim: Sim, world: World, s: SimState, t: int) -> Draft:
    """期限：onDeadline 里 if 成立的规则，全部按期限那一刻的状态判；一条都不成立也写（effects 为空）。"""
    dl = world["clock"]["deadline"]
    pre = flat(s)
    effects = [
        copy.deepcopy(e) for r in world["clock"].get("onDeadline", []) if sim.holds(r["if"], pre) for e in r["then"]
    ]
    wb = dl.get("watchBeat")
    place = str(sim.beats[wb]["place"] if wb in sim.beats else s["vars"]["var.player.location"])
    return {
        "event": _system_event("action", t, place, effects),
        "beat": None,
        "variant": None,
        "reason": None,
        "reasonCode": None,
    }


def _system_event(type_: str, t: int, place: str, effects: list[dict[str, Any]]) -> dict[str, Any]:
    return {"actor": "system", "type": type_, "origin": SCHEDULE, "t": t, "dt": 0, "place": place, "effects": effects}


def world_state(world: World, state: SimState, playthrough_id: str) -> dict[str, Any]:
    """转成契约 3.1 的 WorldState。没有事件 ID 的约定或即兴设定（提交前的试算）不能转，抛 ValueError。"""
    _same_world(world, state)
    for kind, xs in (("promises", state["promises"]), ("runFacts", state["runFacts"])):
        for k, x in xs.items():
            if x.get("madeBy") is None or ("resolvedBy" in x and x["resolvedBy"] is None):
                raise ValueError(f"{kind} 里的 {k} 没有事件 ID（试算的状态不能转成 WorldState）")
    sim = _Sim(world)
    sched = _schedule(sim, state)
    beats: dict[str, str] = {}
    for b in sim.beats:
        if b in state["beats"]:
            beats[b] = state["beats"][b]
        else:
            to = state["overrides"].get(b, {}).get("to")
            beats[b] = to if to in ("delayed", "hastened") else "pending"
    return {
        "playthroughId": playthrough_id,
        "asOfSeq": state["seq"],
        "t": state["t"],
        "vars": copy.deepcopy(state["vars"]),
        "beats": beats,
        "schedule": sched,
        "knowledge": copy.deepcopy(state["knowledge"]),
        "locations": dict(state["locations"]),
        "spots": dict(state.get("spots", {})),
        "promises": copy.deepcopy(state["promises"]),
        "runFacts": copy.deepcopy(state["runFacts"]),
        "holdings": dict(state["holdings"]),
    }


def classify(world: World, state: SimState) -> str | None:
    """2.9：按现在的状态落到哪一类世界结局。"""
    return Sim(world).classify(flat(state))


def signature(world: World, state: SimState) -> dict[str, Any]:
    """2.9.1 结局署名：`endings.signature.vars` 的最终值，`beats` 是否照原著发生（happened，altered 不算）。
    结局的 `world.signature`、数据的多样性统计、关键时刻的第三条都用这一份。世界模型没写署名时是空的。"""
    sig = world.get("endings", {}).get("signature") or {}
    out: dict[str, Any] = {v: copy.deepcopy(state["vars"].get(v)) for v in sig.get("vars", [])}
    out |= {b: state["beats"].get(b) == "happened" for b in sig.get("beats", [])}
    return out


def predict(world: World, state: SimState) -> str | None:
    """预测（backend-design 2.5）：玩家不再做任何事，在状态的副本上结算到底再分类。"""
    return classify(world, settle(world, state, None)[1])


def arrival_delta(world: World, state: SimState, effects: Sequence[Effect], t: int) -> dict[str, Any]:
    """S-066 ①，契约 2.10：在 t 提交 effects，梅洛斯到刑场（watchBeat）会晚（+）或早（−）几分钟，做了以后还赶不赶得上。
    和 Sim.arrival_delta 同一个算法：分钟数在去掉 window.latest 的世界里，做和不做各结算到底再比排定时间。
    state 要先 settle 到 t。effects 和已登记的改动合不了（check_effects 的 bad-state）时抛 ValueError。"""
    wb = world["clock"]["deadline"].get("watchBeat")
    loose = {**world, "beats": [{**b, "window": {**b["window"], "latest": BIG}} for b in world["beats"]]}
    event = {"t": t, "dt": 0, "origin": "action", "effects": list(effects)}
    after = apply(world, state, event)
    lsim = _Sim(loose)
    a = lsim.schedule(settle(loose, state, None)[1]["overrides"])[0]
    b = lsim.schedule(settle(loose, after, None)[1]["overrides"])[0]
    real = settle(world, after, None)[1]
    return {"minutes": b.get(wb, 0) - a.get(wb, 0), "inTime": real["beats"].get(wb) in OCCURRED}


def check_effects(world: World, state: SimState, effects: Iterable[Effect], origin: str | None) -> list[Problem]:
    """效果本身合不合法：引用的 ID 存在、取值符合类型、op 用得对。origin 不是 "schedule" 时（叙事者的候选事件、
    导演事件都不是）{op: beat, to: happened} 和改已经有结果的节拍也报，并按 StateVar.valueRequires（契约 1.6，C-16）
    判。按 origin 区分，不按 actor：导演事件的 actor 也是 system。只查形状和引用；R1〜R7 是叙事者的。"""
    effects = list(effects)
    sim = Sim(world)
    chars = set(sim.chars)
    places = {p["id"] for p in world["places"]}
    facts = {f["id"] for f in world["facts"]}
    items = {it["id"]: it for it in world.get("items", [])}
    templates = {x["id"] for c in world["characters"] for x in c.get("promiseTemplates", [])}
    run_facts = set(state["runFacts"])
    promises = {k: p["status"] for k, p in state["promises"].items()}
    over = copy.deepcopy(state["overrides"])  # 同一批里前面的改动也算（merge_change）
    system = origin == SCHEDULE
    out: list[Problem] = []

    def bad(i: int, code: str, msg: str) -> None:
        out.append({"index": i, "code": code, "message": msg})

    def who(x: Any) -> bool:
        return x == "player" or x in chars

    for i, e in enumerate(effects):
        op = e.get("op")
        if op == "set":
            msg = _check_value(sim, places, e.get("var"), e.get("value"))
            if msg:
                bad(i, "bad-value", msg)
        elif op == "inc":
            v = sim.svars.get(e.get("var", ""))
            if v is None or v["type"] not in ("int", "minutes"):
                bad(i, "bad-op", f"inc 只能用于 int、minutes 变量：{e.get('var')}")
            elif not isinstance(e.get("by"), int) or isinstance(e.get("by"), bool):
                bad(i, "bad-value", f"inc 的 by 要是整数：{e.get('by')!r}")
        elif op == "relocate":
            if e.get("character") not in chars or e.get("place") not in places:
                bad(i, "unknown-id", f"relocate 引用不存在：{e.get('character')} → {e.get('place')}")
            if "spot" in e and not (isinstance(e["spot"], str) and SPOT.fullmatch(e["spot"])):
                bad(i, "bad-value", f"relocate 的 spot 要是布局里的位置点名（小写 slug）：{e['spot']!r}")
        elif op == "hold":
            it = items.get(e.get("item", ""))
            if not it or not it.get("portable"):
                bad(i, "bad-op", f"hold 只能用于 portable 的物品：{e.get('item')}")
            for k in ("to", "from"):
                if k in e and e[k] is not None and not who(e[k]):
                    bad(i, "unknown-id", f"hold.{k} 要是 player、人物 ID 或 null：{e[k]!r}")
            if "to" not in e:
                bad(i, "bad-op", "hold 要写 to（null = 被拿走、用掉）")
        elif op == "learn":
            if not who(e.get("character")):  # 1.7：玩家也能学（契约 2.1）
                bad(i, "unknown-id", f"learn 的人物不存在：{e.get('character')}")
            if e.get("fact") not in facts and e.get("fact") not in run_facts:
                bad(i, "unknown-id", f"learn 的事实不存在：{e.get('fact')}")
        elif op == "improv":
            if e.get("character") not in chars:
                bad(i, "unknown-id", f"improv 的人物不存在：{e.get('character')}")
            if e.get("factId") in run_facts:
                bad(i, "duplicate-id", f"即兴设定重复：{e.get('factId')}")
            run_facts.add(e.get("factId", ""))
        elif op == "promise":
            _check_promise(i, e, who, sim, templates, promises, bad)
        elif op == "beat":
            _check_beat(i, e, sim, state, over, system, bad)
        else:
            bad(i, "bad-op", f"未知的效果 {op}")
    if not system and not out:  # 形状都对了再按 valueRequires 判，规则照 Sim.value_requires（按每个 effect 之前的状态）
        cur = flat(state)
        for i, e in enumerate(effects):
            for x in sim.value_requires([e], cur, origin):
                msg = f"{x['var']} = {x['value']!r} 要 {x['when']}"
                out.append({"index": i, "code": "value-requires", "message": msg, "note": x["note"]})
            sim.apply([e], cur)
    return out


def _check_value(sim: Sim, places: set[str], var: Any, value: Any) -> str | None:
    v = sim.svars.get(var)
    if v is None:
        return f"未定义的状态变量 {var}"
    ty = v["type"]
    if ty == "enum" and value not in v["values"]:
        return f"{var} 的取值 {value!r} 不在枚举 {v['values']}"
    if ty == "bool" and not isinstance(value, bool):
        return f"{var} 要 bool，得到 {value!r}"
    if ty in ("int", "minutes"):
        if not isinstance(value, int) or isinstance(value, bool):
            return f"{var} 要整数，得到 {value!r}"
        if not v.get("min", -BIG) <= value <= v.get("max", BIG):
            return f"{var} 的取值 {value} 超出 {v.get('min')}〜{v.get('max')}"
    if ty == "place" and value not in places:
        return f"{var} 要地点 ID，得到 {value!r}"
    return None


def _check_promise(
    i: int, e: Effect, who: Callable[[Any], bool], sim: Sim, templates: set[str], promises: dict[str, str], bad: Bad
) -> None:
    change, pid = e.get("change"), e.get("promiseId")
    if change == "made":
        for k in ("from", "to"):
            if not who(e.get(k)):
                bad(i, "unknown-id", f"promise.{k} 要是 player 或人物 ID：{e.get(k)!r}")
        if not e.get("text"):
            bad(i, "bad-value", "promise made 要有 text")
        if e.get("template") and e["template"] not in templates:
            bad(i, "unknown-id", f"promise.template 不存在：{e['template']}")
        if e.get("due", {}).get("beat") and e["due"]["beat"] not in sim.beats:
            bad(i, "unknown-id", f"promise.due.beat 不存在：{e['due']['beat']}")
        if pid and pid in promises:
            bad(i, "duplicate-id", f"约定重复：{pid}")
        if pid:
            promises[pid] = "open"
    elif change in ("kept", "broken", "voided"):
        if not pid or promises.get(pid) != "open":
            bad(i, "bad-state", f"只有 open 的约定能变成 {change}：{pid}")
        else:
            promises[pid] = change
    else:
        bad(i, "bad-value", f"promise.change 不认识：{change!r}")


def _check_beat(
    i: int, e: Effect, sim: Sim, state: SimState, over: dict[str, Override], system: bool, bad: Bad
) -> None:
    bid, to = e.get("beat"), e.get("to")
    if bid not in sim.beats:
        bad(i, "unknown-id", f"节拍不存在：{bid}")
        return
    if to not in ("happened", "prevented", "delayed", "hastened", "altered"):
        bad(i, "bad-value", f"beat.to 不认识：{to!r}")
        return
    ok = True
    if to in ("delayed", "hastened"):
        m = e.get("minutes")
        if not isinstance(m, int) or isinstance(m, bool) or m < 0:
            bad(i, "bad-value", f"{to} 要写 minutes（≥ 0 的整数）：{m!r}")
            ok = False
    if to == "altered" and not system and not isinstance(e.get("outcomes"), list):
        bad(i, "bad-value", "altered 要写 outcomes（改变后的结果）")
        ok = False
    if bid in state["beats"]:
        bad(i, "beat-has-result", f"{bid} 已经有结果（{state['beats'][bid]}）")
    elif not system and to == "happened":
        bad(i, "beat-happened", f"候选事件不能让 {bid} 直接发生（节拍到点由系统结算）")
    elif system and to in ("delayed", "hastened"):
        bad(i, "bad-value", f"系统事件里的 beat 只能是 happened / altered / prevented：{to}")
    elif not system and ok:
        why = change_conflict(over.get(bid), e)
        if why:
            bad(i, "bad-state", f"{bid}：{why}")
        else:
            merge_change(over, e)


def _same_world(world: World, state: SimState) -> None:
    if world["worldModelVersion"] != state["worldModelVersion"]:
        raise ValueError(f"状态是 {state['worldModelVersion']} 的，世界模型是 {world['worldModelVersion']}")
