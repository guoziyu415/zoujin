"""幕末和幕切换（B-3 第 4 条；api-contract 3.11，契约 2.8、2.8.1）。

- 收幕以后推的 `act_ended`（断线时 `pending.actEnd`）：去处按身份和 `requires` 过滤，带副题、时刻、同行的人、
  过场二选一；
  「この幕であなたが動かしたこと」；还能说几次打算。
- 幕切换的四步（2.8.1）：过场二选一的事件 → 玩家的 act-transition → 玩家不在场地结算到目标时刻 → 系统的
  act-transition。选给定去处和成行的打算共用，在提交的事务里、锁着这一局时调用（`Writer`）。
- 「その頃」（2.8.1 第 5 步）：从第 3 步结算的事件里取，最多 3 件。

这里只用世界模型和事件，不碰玩家的原话。打算的转述（`label`）在调用前已经过滤（`narrator/plans.py`）。
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from zoujin_backend.narrator.rules import Checked
from zoujin_backend.narrator.writer import Writer
from zoujin_backend.projection import as_you, committed
from zoujin_backend.world import Book
from zoujin_worldsim import SimState, arrival_delta, flat, world_state

log = logging.getLogger("zoujin.narrator")

Json = Any

PLAN_TRIES = 2  # 同一次幕末最多说 2 次打算（api-contract 3.11 Freeform）
RECAP_LINES = 4
RECAP_ITEMS = 3
CHECKER_EXIT = "world-exit"  # 世界模型写死的去处效果：数据的校验工具静态查过，不过模型检查
PASSED_EXIT = {"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER_EXIT}


# —— 时刻和副题 ——


def schedule(book: Book, state: SimState) -> dict[str, int]:
    """还没结果的节拍在本局的排定时刻（W-1 world_state 的 schedule）。"""
    sched: dict[str, int] = world_state(book.world, state, "")["schedule"]
    return sched


def target_t(book: Book, state: SimState, t: int, align_to: str | None) -> int:
    """去处的目标时刻：`t` 加上 alignTo 节拍本局被推迟或提前的分钟（排定或发生的时刻减原作时刻），不早于此刻。"""
    if align_to and align_to in book.beats:
        canon = int(book.beats[align_to]["window"]["canonical"])
        at = state["times"].get(align_to)
        if at is None:
            at = schedule(book, state).get(align_to, canon)
        t += int(at) - canon
    return max(t, int(state["t"]))


def where(book: Book, place: str, t: int) -> str:
    """副题的前半「{地点}・{日子}の{时段}」（api-contract 3.11 ActOption.where）：clock.labels 的叫法，不套 format。"""
    labels = book.labels
    day, minute = divmod(t, 1440)
    band = [b for m, b in labels.bands if m <= minute][-1]
    return f"{book.places[place]['name']}・{labels.days[min(day, len(labels.days) - 1)]}の{band}"


def companions(book: Book, effects: Iterable[Mapping[str, Any]], arrival: Mapping[str, Any] | None) -> list[str]:
    """同行的人：效果里 `set var.player.companionOf` 的人物，加上落地先开口的人，去重。"""
    out = [
        str(e["value"])
        for e in effects
        if e.get("op") == "set" and e.get("var") == "var.player.companionOf" and e.get("value") in book.characters
    ]
    if arrival and arrival.get("opener"):
        out.append(str(arrival["opener"]))
    return list(dict.fromkeys(out))


# —— 去处 ——


def current_act(book: Book, state: SimState) -> Json:
    return book.acts[book.act_of(state["vars"])]


def open_exits(book: Book, state: SimState) -> list[Json]:
    """这一幕的去处里，这个身份能选、`requires` 按此刻的状态成立的（api-contract 3.11）。"""
    values = flat(state)
    out = []
    for ex in current_act(book, state).get("exits", []):
        if ex.get("roles") and state["role"] not in ex["roles"]:
            continue
        if ex.get("requires") and not book.sim.holds(ex["requires"], values):
            continue
        out.append(ex)
    return out


def en_route(book: Book, state: SimState, ex: Mapping[str, Any], t: int) -> Json | None:
    """过场二选一（契约 1.4）：节拍还没结果、本局排定时刻在此刻和目标时刻之间才给。melosMinutes 按此刻用 W-1 的
    arrival_delta 算，最后一项（照原作）为 null；算不了（和已登记的改动合不了）时用世界模型写的分钟。"""
    er = ex.get("enRoute")
    if not er or er["beat"] in state["beats"]:
        return None
    at = schedule(book, state).get(er["beat"])
    if at is None or not state["t"] <= at <= t:
        return None
    choices = []
    last = len(er["choices"]) - 1
    for i, c in enumerate(er["choices"]):
        minutes: int | None = None
        if i < last:
            try:
                minutes = int(arrival_delta(book.world, state, c.get("effects", []), state["t"])["minutes"])
            except ValueError:
                minutes = int(c.get("melosMinutes", 0))
        choices.append({"index": i, "label": c["label"], "melosMinutes": minutes, "afterLine": c.get("after")})
    return {"line": er["line"], "choices": choices}


def option(book: Book, state: SimState, ex: Mapping[str, Any]) -> Json:
    """一个去处（ActOption）。"""
    t = target_t(book, state, int(ex["t"]), ex.get("alignTo"))
    out: Json = {
        "optionId": ex["id"],
        "label": ex["label"],
        "sceneId": book.scene_of(ex["place"], ex["toAct"]),
        "toActId": ex["toAct"],
        "tLabel": book.label(t),
        "where": where(book, ex["place"], t),
    }
    if ex.get("sub"):
        out["sub"] = ex["sub"]
    out["with"] = companions(book, ex.get("effects", []), ex.get("arrival"))
    out["because"] = None
    er = en_route(book, state, ex, t)
    if er is not None:
        out["enRoute"] = er
    return out


def recap_lines(book: Book, role_id: str, act_events: Iterable[Mapping[str, Any]]) -> list[str]:
    """「この幕であなたが動かしたこと」：这一幕里玩家做的（或人物为玩家做的）、已提交、改了东西的事件的摘要，
    按 seq 取最后 4 条；一条都没有时为空（前端显示 actEnd.summary.empty）。玩家写成「あなた」、句末补「。」。"""
    lines = [
        as_you(book, role_id, str(e["summary"]), period=True)
        for e in act_events
        if committed(e)
        and e["effects"]
        and (e["actor"] == "player" or e.get("beneficiary") == "player")
        and e["type"] != "act-transition"
    ]
    return lines[-RECAP_LINES:]


def act_end(book: Book, state: SimState, tries: int, act_events: Iterable[Mapping[str, Any]]) -> Json:
    """ActEnd（act_ended 和 pending.actEnd 同形，不带 type）。"""
    exits = open_exits(book, state)
    if not exits:  # 世界模型总有一个不带条件的去处；万一都不成立，照全部给，不让幕末页空着
        log.warning("%s 的去处都不成立，照全部给", book.act_of(state["vars"]))
        exits = list(current_act(book, state).get("exits", []))
    left = max(0, PLAN_TRIES - tries)
    return {
        "actId": book.act_of(state["vars"]),
        "recapLines": recap_lines(book, state["role"], act_events),
        "options": [option(book, state, ex) for ex in exits],
        "freeform": {"allowed": left > 0, "triesLeft": left},
    }


def exit_of(book: Book, state: SimState, exit_id: str) -> Json | None:
    return next((ex for ex in current_act(book, state).get("exits", []) if ex["id"] == exit_id), None)


# —— 幕切换（2.8.1） ——


@dataclass
class Landing:
    """跳到哪里：下一幕、地点、原定时刻（目标时刻在第 1 步以后按 alignTo 算）、位置点、落地。"""

    to_act: str
    place: str
    t: int
    align_to: str | None = None
    spot: str | None = None
    arrival: Json | None = None

    @classmethod
    def of_exit(cls, ex: Mapping[str, Any]) -> Landing:
        return cls(ex["toAct"], ex["place"], int(ex["t"]), ex.get("alignTo"), ex.get("spot"), ex.get("arrival"))

    @classmethod
    def of_plan(cls, plan: Mapping[str, Any]) -> Landing:
        return cls(plan["toAct"], plan["place"], int(plan["t"]), None, plan.get("spot"), plan.get("arrival"))


@dataclass
class Moved:
    """幕切换写了什么：第 3 步结算的事件（「その頃」从这里取）、目标时刻、落地后要推的。"""

    from_act: str
    to_act: str
    t: int
    skipped: list[Json] = field(default_factory=list)
    arrival: Json | None = None
    world: list[Json] = field(default_factory=list)  # B-16：第 3 步里世界推进写的事件（也在 skipped 里）


def catch_up(w: Writer) -> None:
    """幕已经收了、时钟走在收幕那一刻之后时（对话、动作的分钟跨过了收幕节拍），中间到点的节拍先结了，之后的事件
    才能写在此刻（W-1 apply 要先 settle）。这段是玩家说着话过去的，人在场：落在他所在地点的节拍照给 learn、固定演出
    （数据 #158）；不在场只管第 3 步（契约 2.8.1）。"""
    w.settle(w.state["t"], guard=False)


def en_route_event(w: Writer, ex: Mapping[str, Any], checked: Checked | None, turn_id: str) -> None:
    """第 1 步：过场二选一选了不是最后一个的那项，玩家的 action 事件（origin act，exitId），过了第 3、4 步的结果。"""
    if checked is None:
        return
    cand = checked.candidate
    w.add(
        w.full(
            t=w.state["t"],
            dt=0,
            actor="player",
            type="action",
            origin="act",
            place=w.player_place,
            summary=cand["summary"],
            effects=checked.effects if checked.passed else [],
            check=checked.check,
            turn_id=turn_id,
            exitId=ex["id"],
        )
    )


def player_transition(
    w: Writer,
    *,
    turn_id: str,
    summary: str,
    effects: Sequence[Mapping[str, Any]],
    check: Mapping[str, Any],
    exit_id: str | None = None,
    plan: Mapping[str, Any] | None = None,
) -> Json:
    """第 2 步：玩家的 act-transition，此刻、dt 0，origin act。给定去处带 exitId，打算带 plan。"""
    extra: dict[str, Any] = {}
    if exit_id is not None:
        extra["exitId"] = exit_id
    if plan is not None:
        extra["plan"] = dict(plan)
    return w.add(
        w.full(
            t=w.state["t"],
            dt=0,
            actor="player",
            type="act-transition",
            origin="act",
            place=w.player_place,
            summary=summary,
            effects=effects,
            check=check,
            turn_id=turn_id,
            **extra,
        )
    )


def jump(
    w: Writer,
    landing: Landing,
    t: int,
    turn_id: str,
    world: Sequence[Any] = (),
    log_: Sequence[Mapping[str, Any]] = (),
) -> Moved:
    """第 3、4 步：玩家不在场地结算到目标时刻（不 learn 节拍的 public 事实，不演固定演出），再写系统的
    act-transition（换幕、换地点）。world：世界推进过了检查的候选（B-16，`advance.Item`），和到点的节拍按时刻合并，
    写之前再判一次；log_ 是这一局到这次提交之前的事件（causes 只留里面有的）。"""
    from zoujin_backend.narrator import advance

    from_act = w.book.act_of(w.state["vars"])
    before = len(w.events)
    written = advance.write(w, world, until=t, away=True, log_=[*log_, *w.events]) if world else []
    w.settle(t, guard=False, present=False)
    skipped = list(w.events[before:])
    w.add(
        w.full(
            t=t,
            dt=0,
            actor="system",
            type="act-transition",
            origin="act",
            place=landing.place,
            summary=f"{w.book.acts[landing.to_act]['title']}へ",
            effects=[
                {"op": "set", "var": "var.act.current", "value": landing.to_act},
                {"op": "set", "var": "var.player.location", "value": landing.place},
            ],
            check=PASSED_EXIT,
            turn_id=turn_id,
        )
    )
    run = w.run
    run.player_spot = landing.spot
    run.act_end = None
    run.plan_tries = 0
    run.plan_alternative = None
    arrival = dict(landing.arrival) if landing.arrival else None
    run.arrival = {"actId": landing.to_act, **arrival} if arrival and arrival.get("opener") else None
    return Moved(from_act, landing.to_act, t, skipped, arrival, written)


# —— 「その頃」 ——


def _who(e: Mapping[str, Any]) -> set[str]:
    """一个事件里出现的人物：行为者和效果的对象。"""
    out = {str(e["actor"])}
    for x in e.get("effects", []):
        for k in ("character", "to", "from"):
            v = x.get(k)
            if isinstance(v, str):
                out.add(v)
    return out


def seen_characters(
    book: Book, start_place: str, log: Iterable[Mapping[str, Any]], talked: Collection[str]
) -> set[str]:
    """玩家见过的人物（近似，WorldState 不记谁见过谁）：和玩家说过话的，加上在玩家在场时提交的事件里当过行为者或对象的。
    log 是这一局按 seq 的全部事件，玩家的地点从开局的地点起，按事件里的 `set var.player.location` 跟着走。"""
    seen = set(talked)
    loc = start_place
    for e in log:
        if committed(e) and (e["actor"] == "player" or e["place"] == loc):
            seen |= _who(e)
        for x in e.get("effects", []):
            if x.get("op") == "set" and x.get("var") == "var.player.location":
                loc = str(x["value"])
    return {c for c in seen if c in book.characters}


def recap(
    book: Book,
    role_id: str,
    skipped: Iterable[Mapping[str, Any]],
    seen: Collection[str],
    player_promises: Collection[str],
) -> list[Json]:
    """「その頃」（契约 2.8.1 第 5 步）：和玩家有关的约定兑现或违背 → keyMoment → 玩家见过的人物自己做的事
    （origin plan）和导演事件（origin director）。不写 voided 的约定和 forget；line 用 summary（玩家写成「あなた」、
    句末补「。」）。最多 3 件。"""
    promised: list[Json] = []
    key: list[Json] = []
    others: list[Json] = []
    for e in skipped:
        if not committed(e) or e["type"] == "forget":
            continue
        change = next(
            (
                x
                for x in e.get("effects", [])
                if x.get("op") == "promise"
                and x.get("change") in ("kept", "broken")
                and x.get("promiseId") in player_promises
            ),
            None,
        )
        item = {"eventId": e["eventId"], "line": as_you(book, role_id, str(e["summary"]), period=True)}
        if change is not None:
            promised.append({**item, "promise": change["change"]})
        elif e.get("keyMoment"):
            key.append(item)
        elif e.get("origin") == "director" or (e.get("origin") == "plan" and e["actor"] in seen):
            others.append(item)
    return (promised + key + others)[:RECAP_ITEMS]


def player_promises(state: SimState) -> set[str]:
    return {p for p, x in state["promises"].items() if "player" in (x.get("from"), x.get("to"))}
