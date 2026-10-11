"""世界推进：不在场人物的打算、约定的结算、导演事件（B-16；backend-design 2.6，契约 3.2、2.8.1 第 3 步）。

三个时机，一次调用（提示 `world`）同时处理打算、约定和导演：
- 幕切换（`act`）：选定去处或打算成行以后、跳幕之前，时间段是此刻到目标时刻。事件和到点的节拍按时间合并（2.8.1 第 3 步，
  玩家不在场），「その頃」从里面取。模型在提交的事务之外调，事务里按时刻结算、重判第 3 步和导演规则，不过的丢掉。
- 关键时刻之后（`key`）：一次提交里有 `keyMoment` 的事件，提交的同一个事务里排一个 `world` 任务；此刻发生（dt 0）。
- 每幕中段（`mid`）：这一幕每 8 个判完的对话轮次排一个；没有还没推进的打算、导演也没名额时不调模型。

检查：候选按时刻顺序过第 3 步（R1〜R4、R7，`Turn.act.kind = "world"`：行为者不在玩家身边也算碰得到，对象和他同一个地点
才算），过了的合在一起做一次第 4 步（R5、R6），再过导演规则。不过的直接丢掉，不改写、不写 rejected 事件（2.6 第 3 步）。

导演规则（确定性）：
- D1、D2：世界推进（导演和人物的打算一样）不能让梅洛斯晚到日没以后：提交后预测（玩家不再做什么）到不了、而且比提交前
  更晚 → 丢。比设计稿的 D2 严：导演让他晚一点可以，但玩家什么都不做也还来得及，补救的机会总在。
- D3：在玩家面前的导演事件只在 `key`、`mid` 里，没有排着的玩家轮次时才投；行为者是环境（`system`），或人物从别处走来
  （效果里把他 relocate 到玩家的地点）。
- D4：在玩家面前每幕最多 1 件；不在场的每幕最多 3 件（「その頃」最多交代 3 件）。
- D5：`causes` 里至少一个玩家或人物的事件。

人物的打算在玩家看得到的地方不写（当面的事走对话）。玩家写成「あなた」只在下发时换（和别的事件一样）。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from zoujin_backend.db import store
from zoujin_backend.db.tables import turns
from zoujin_backend.narrator.pipeline import CallFailed, Spend, TurnInput, _Try, normalize, result
from zoujin_backend.narrator.rules import absent, fill_ids, index, judge, trial
from zoujin_backend.narrator.view import state_view
from zoujin_backend.narrator.writer import Writer
from zoujin_backend.projection import as_you, committed
from zoujin_backend.world import Book
from zoujin_worldsim import SimState, activity, same_scene, sees, world_state

if TYPE_CHECKING:
    from zoujin_backend.narrator.core import Narrator, Planned, Result, Task

log = logging.getLogger("zoujin.narrator")

Json = Any

KIND = "world"  # 任务和提示的种类
MID_EVERY = 8  # 每幕中段：每 8 个判完的对话轮次
PRESENT_PER_ACT = 1  # D4：在玩家面前每幕最多 1 件
ABSENT_PER_ACT = 3  # D4：不在场的导演事件每幕最多 3 件
RECENT = 12  # 给模型的这一幕玩家看得到的事件，最近的几条
SUMMARY_MAX = 80
WORLD_ACT = {"kind": "world"}  # 第 3 步的 Turn.act：世界推进


@dataclass(frozen=True)
class Window:
    """这次推进的时间段和原因（act / key / mid）。key、mid 的 start == end（此刻）。"""

    reason: str
    start: int
    end: int
    to_act: str | None = None  # act：跳到哪一幕（给模型看下一幕的打算）


@dataclass
class Item:
    """过了检查的一个候选（提交时按当时的状态再判一次第 3 步和导演规则）。"""

    cand: Json
    effects: list[Json]
    check: Json
    present: bool = False  # 在玩家面前（D3、D4）


@dataclass
class Prepared:
    items: list[Item] = field(default_factory=list)
    called: bool = False


# —— 这一幕 ——


def act_start(log_: Sequence[Mapping[str, Any]]) -> int:
    """这一幕从哪个 seq 之后算：最后一个系统的 act-transition（开局时 0）。"""
    return max((int(e["seq"]) for e in log_ if e["type"] == "act-transition" and e["actor"] == "system"), default=0)


def visible_log(book: Book, role_id: str, log_: Sequence[Mapping[str, Any]]) -> set[str]:
    """玩家看得到的事件 ID（和时间线同一个口径：2.4 的可见，加上玩家自己做成的、带效果的）。"""
    from zoujin_backend.timeline import replay

    return {ev["eventId"] for ev in replay(book, role_id, log_).visible}


def used(log_: Sequence[Mapping[str, Any]], shown: set[str]) -> tuple[int, int]:
    """这一幕已经用掉的导演名额：(在玩家面前的, 不在场的)。"""
    start = act_start(log_)
    mine = [e for e in log_ if int(e["seq"]) > start and e.get("origin") == "director" and committed(e)]
    present = sum(1 for e in mine if e["eventId"] in shown)
    return present, len(mine) - present


def quota(window: Window, log_: Sequence[Mapping[str, Any]], shown: set[str], *, busy: bool) -> Json:
    p, a = used(log_, shown)
    present = window.reason != "act" and not busy and p < PRESENT_PER_ACT
    return {"present": present, "absent": max(0, ABSENT_PER_ACT - a)}


def plans_for(book: Book, who: str, acts_: Iterable[str]) -> list[str]:
    wanted = set(acts_)
    return [str(p["text"]) for p in book.characters[who].get("plans", []) if p.get("act") in wanted]


def actors(book: Book, state: SimState, window: Window) -> list[Json]:
    """给模型的人物：有目标或打算的，此刻在哪里、在做什么、和玩家是不是同一个场景、这一幕（和下一幕）的打算。"""
    acts_ = [book.act_of(state["vars"]), *([window.to_act] if window.to_act else [])]
    player = state["vars"]["var.player.location"]
    out = []
    for c in sorted(book.characters):
        ch = book.characters[c]
        plans = plans_for(book, c, acts_)
        if not plans and not ch.get("goals"):
            continue
        place = state["locations"].get(c)
        out.append(
            {
                "id": c,
                "name": ch["name"],
                "place": place,
                "activity": activity(book.world, state, c),
                "withPlayer": place is not None and same_scene(book.world, place, player),
                "goals": [str(g["text"]) for g in ch.get("goals", [])],
                "plans": plans,
            }
        )
    return out


def has_work(book: Book, state: SimState, window: Window, q: Mapping[str, Any]) -> bool:
    """mid 和 key：有不在玩家身边、不是不在场、这一幕有打算的人物，或导演还有名额，才值得调模型。"""
    if q["present"] or q["absent"] > 0:
        return True
    ix = index(book.world)
    player = state["vars"]["var.player.location"]
    for c in book.characters:
        place = state["locations"].get(c)
        if place is None or absent(ix, state, c) or same_scene(book.world, place, player):
            continue
        if plans_for(book, c, [book.act_of(state["vars"])]):
            return True
    return False


def request(
    book: Book, state: SimState, log_: Sequence[Mapping[str, Any]], shown: set[str], window: Window, q: Json
) -> Json:
    start = act_start(log_)
    role = state["role"]
    recent = [
        {"eventId": e["eventId"], "t": e["t"], "actor": e["actor"], "summary": as_you(book, role, str(e["summary"]))}
        for e in log_
        if int(e["seq"]) > start and e["eventId"] in shown
    ][-RECENT:]
    view = state_view(book, state)
    promises = [p for p in view.doc["promises"] if p.get("status") == "open"]
    return {
        "worldModelVersion": book.version,
        "state": view.doc,
        "reason": window.reason,
        "window": {
            "from": window.start,
            "to": window.end,
            "fromLabel": book.label(window.start),
            "toLabel": book.label(window.end),
        },
        "player": {"place": state["vars"]["var.player.location"]},
        "characters": actors(book, state, window),
        "promises": promises,
        "recent": recent,
        "director": q,
    }


# —— 候选和检查 ——


def candidate(raw: Mapping[str, Any], book: Book, state: SimState, ids: set[str], window: Window) -> Json | None:
    """模型的一件 → 候选；时刻不在时间段里、行为者或地点不认识、摘要太长的丢掉。causes 只留这一局的事件和节拍。"""
    t = int(raw.get("t", window.start))
    actor = str(raw.get("actor") or "")
    origin = raw.get("origin")
    if not window.start <= t <= window.end or origin not in ("plan", "director"):
        return None
    if actor not in book.characters and not (actor == "system" and origin == "director"):
        return None
    if raw.get("place") not in book.places:
        return None
    summary = str(raw.get("summary") or "").strip()
    if not summary or len(summary) > SUMMARY_MAX or not raw.get("effects"):
        return None  # 什么都不改的只是叙述，不写
    view = state_view(book, state)
    c = normalize({**raw, "summary": summary}, view, book)
    c.pop("needsConfirm", None)
    c["origin"] = origin
    c["place"] = raw["place"]
    c["t"] = t
    c["causes"] = list(dict.fromkeys(x for x in raw.get("causes") or [] if x in ids or x in book.beats))
    return c


def arrival(book: Book, state: SimState) -> int | None:
    """梅洛斯到刑场的预测时刻（`clock.deadline.watchBeat`）：发生了用发生的时刻，没结果用排定的；不会发生是 None。"""
    watch = book.world["clock"]["deadline"].get("watchBeat")
    if watch is None:
        return None
    at = state["times"].get(watch)
    if at is None:
        at = world_state(book.world, state, "")["schedule"].get(watch)
    return None if at is None else int(at)


def too_late(book: Book, before: SimState, after: SimState) -> bool:
    """D1、D2：提交后到不了日没、而且比提交前更晚（不会发生算最晚）。没有期限的世界模型不判。"""
    if book.world["clock"]["deadline"].get("watchBeat") is None:
        return False
    deadline = int(book.world["clock"]["deadline"]["t"])
    a, b = arrival(book, before), arrival(book, after)
    late = b is None or b > deadline
    later = (b is None and a is not None) or (a is not None and b is not None and b > a)
    return late and later


def in_sight(book: Book, cand: Mapping[str, Any], effects: Sequence[Mapping[str, Any]], player: str) -> bool:
    """玩家看不看得到（契约 1.12 的 `sees()`，和推 commit 同一个判法）。"""
    return sees(book.world, player, {**cand, "effects": list(effects)})


def entered(cand: Mapping[str, Any], effects: Sequence[Mapping[str, Any]], player: str) -> bool:
    """D3：在玩家面前的导演事件从环境或走来的人物进来。"""
    if cand["actor"] == "system":
        return True
    return any(
        e.get("op") == "relocate" and e.get("character") == cand["actor"] and e.get("place") == player for e in effects
    )


def fairness(
    book: Book,
    state: SimState,
    cand: Mapping[str, Any],
    effects: Sequence[Json],
    log_by_id: Mapping[str, Mapping[str, Any]],
    q: Mapping[str, Any],
    taken: dict[str, int],
    *,
    away: bool = False,
) -> tuple[str | None, bool]:
    """导演规则和「打算不在玩家面前」。返回 (不过的规则码, 在不在玩家面前)。taken：这次推进已经用掉的名额。
    幕切换（`away`）的玩家一律不在场。"""
    player = state["vars"]["var.player.location"]
    shown = not away and in_sight(book, cand, effects, player)
    try:
        after = trial(book.world, state, dict(cand), list(effects))
    except ValueError:
        return "apply", shown
    if too_late(book, state, after):
        return "D1", shown
    if cand["origin"] == "plan":
        return ("plan-in-sight" if shown else None), shown
    causes = [log_by_id[c] for c in cand.get("causes", []) if c in log_by_id]
    if not any(c["actor"] == "player" or c["actor"] in book.characters for c in causes):
        return "D5", shown
    if shown:
        if not q["present"] or taken["present"] >= 1 or not entered(cand, effects, player):
            return "D3", shown
    elif taken["absent"] >= int(q["absent"]):
        return "D4", shown
    return None, shown


async def prepare(
    n: Narrator,
    book: Book,
    state: SimState,
    log_: Sequence[Mapping[str, Any]],
    window: Window,
    spend: Spend,
    span: Mapping[str, Any],
    *,
    busy: bool = False,
) -> Prepared:
    """事务外：调模型、过第 3 步、导演规则，过了的合在一起做一次第 4 步。模型出错、超时返回空（世界推进不挡玩家）。"""
    if not n.world_advance:
        return Prepared()
    shown = visible_log(book, state["role"], log_)
    q = quota(window, log_, shown, busy=busy)
    if window.reason != "act" and not has_work(book, state, window, q):
        return Prepared()
    req = request(book, state, log_, shown, window, q)
    try:
        r = await n.pipeline.call(KIND, req, spend, span={**span, "reason": window.reason})
    except CallFailed:
        log.info("世界推进（%s）两次都没成，这次不推", window.reason)
        return Prepared(called=True)
    by_id = {e["eventId"]: e for e in log_ if committed(e)}
    turn = TurnInput(character=None, player=None, act=WORLD_ACT)
    raws = sorted(r.output["events"], key=lambda x: int(x.get("t", window.start)))
    now = state
    taken = {"present": 0, "absent": 0}
    tries: list[tuple[_Try, bool]] = []
    for raw in raws:
        c = candidate(raw, book, state, set(by_id), window)
        if c is None:
            continue
        c["dt"] = window.end - c["t"]  # R3：走动在这段时间里走完；写进去时 dt 0（时钟由结算走）
        effects = fill_ids(c.get("effects", []), n.ids)
        hits = n.pipeline.step3(book, now, c, effects, turn)
        if hits:
            log.info("世界推进的候选没过第 3 步：%s", [h.code for h in hits])
            continue
        code, shown_ = fairness(book, now, c, effects, by_id, q, taken, away=window.reason == "act")
        if code is not None:
            log.info("世界推进的候选没过 %s", code)
            continue
        if c["origin"] == "director":
            taken["present" if shown_ else "absent"] += 1
        tries.append((_Try(c, effects, []), shown_))
        now = trial(book.world, now, c, effects)
    if not tries:
        return Prepared(called=True)
    rows = await n.pipeline.model_check(book, state, [t for t, _ in tries], turn, spend, span)
    items = []
    for (t, shown_), row in zip(tries, rows, strict=True):
        t.model = row
        if not t.ok:
            log.info("世界推进的候选没过第 4 步：%s", [f for f, _ in t.fails])
            continue
        items.append(Item(t.cand, t.effects, result("passed", 1, [], True), present=shown_))
    return Prepared(items, called=True)


# —— 写入（提交的事务里） ——


def write(
    w: Writer,
    items: Sequence[Item],
    *,
    until: int | None = None,
    away: bool = False,
    log_: Sequence[Mapping[str, Any]] = (),
) -> list[Json]:
    """按时刻写过了检查的候选。away（幕切换）：先玩家不在场地结算到这一件的时刻。写之前按当时的状态再判一次第 3 步和
    D1，不过的丢掉。返回写了的事件。"""
    book = w.book
    turn = TurnInput(character=None, player=None, act=WORLD_ACT).rules
    by_id = {e["eventId"]: e for e in log_}
    out: list[Json] = []
    for it in sorted(items, key=lambda x: int(x.cand["t"])):
        t = int(it.cand["t"])
        if until is not None and t > until:
            continue
        if away and t > w.state["t"]:
            w.settle(t, guard=False, present=False)
        t = max(t, int(w.state["t"]))
        cand = {**it.cand, "t": t, "dt": (until - t) if until is not None else 0}
        causes = [c for c in cand.get("causes", []) if c in by_id or c in book.beats]
        hits = judge(book.world, w.state, cand, it.effects, turn)
        if hits:
            log.info("世界推进的事件写之前没过第 3 步：%s", [h.code for h in hits])
            continue
        try:
            after = trial(book.world, w.state, cand, it.effects)
        except ValueError:
            continue
        if too_late(book, w.state, after):
            continue
        if not away and it.present != in_sight(book, cand, it.effects, w.player_place):
            continue  # 在不在玩家面前和判的时候不一样了（人走了）：名额是按判的时候算的，丢掉
        extra = {"beneficiary": cand["beneficiary"]} if cand.get("beneficiary") else {}
        out.append(
            w.add(
                w.full(
                    t=t,
                    dt=0,
                    actor=cand["actor"],
                    type=cand["type"],
                    origin=cand["origin"],
                    place=cand["place"],
                    summary=cand["summary"],
                    effects=it.effects,
                    check=it.check,
                    causes=causes,
                    **extra,
                )
            )
        )
    return out


def counts(events: Iterable[Mapping[str, Any]]) -> tuple[int, int]:
    """(人物打算的事件数, 导演事件数)。"""
    evs = list(events)
    return sum(1 for e in evs if e.get("origin") == "plan"), sum(1 for e in evs if e.get("origin") == "director")


# —— 任务 ——


async def busy(n: Narrator, pid: str, turn_id: str) -> bool:
    """有排着的玩家轮次（D3：不插在玩家说话的那一轮里）。"""
    async with n.engine.connect() as c:
        got = await c.scalar(
            select(func.count())
            .select_from(turns)
            .where(
                turns.c.playthrough_id == pid,
                turns.c.turn_id != turn_id,
                turns.c.status.in_(("pending", "leased")),
                turns.c.kind.in_(("talk", "action", "plan", "choose", "confirm")),
            )
        )
    return bool(got)


async def run_world(n: Narrator, task: Task) -> Result:
    """`world` 任务（key、mid）：此刻发生。这一幕已经收了、局已经进了结局：什么都不写。"""
    from zoujin_backend.narrator.core import MAX_STALE, Planned, Stale

    reason = str((task.request or {}).get("reason") or "mid")
    for _ in range(MAX_STALE):
        pt, state = await n.read(task.pid)
        book = n.library.version(pt["world_model_version"])
        if pt["act_end"] is not None or pt["status"] != "active":
            return await n._commit(task, pt["last_seq"], lambda w, b: Planned())
        async with n.engine.connect() as c:
            log_ = await store.event_log(c, task.pid, book.version)
        window = Window(reason, int(state["t"]), int(state["t"]))
        span = {"playthrough_id": task.pid, "turn_id": task.turn_id, "world_model_version": book.version}
        prepared = await prepare(
            n, book, state, log_, window, task.spend, span, busy=await busy(n, task.pid, task.turn_id)
        )

        def go(w: Writer, b: Book, items: list[Item] = prepared.items, log_: list[Json] = log_) -> Planned:
            written = write(w, items, log_=log_)
            plans, directed = counts(written)
            # 在玩家面前的导演事件：摘要作为 commit.narration 的一行地の文（api-contract 3.4），玩家写成「あなた」
            lines = [
                as_you(b, w.state["role"], str(e["summary"]), period=True)
                for e in written
                if in_sight(b, e, e["effects"], w.player_place)
            ]
            info = {"reason": reason, "events": len(written)}
            extra = {"narration": lines} if lines else {}
            return Planned(info=info, extra=extra, world_events=plans, director_events=directed)

        try:
            return await n._commit(task, pt["last_seq"], go, spend=task.spend)
        except Stale:
            log.info("lastSeq 变了，%s 重来", task.turn_id)
    raise RuntimeError(f"{task.turn_id}：lastSeq 一直在变")


__all__ = ["KIND", "MID_EVERY", "Item", "Prepared", "Window", "prepare", "run_world", "write"]
