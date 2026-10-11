"""時間線（api-contract 2.5）和「なぜこうなった？」（2.6）：每次从这一局的事件日志现算，不另存。

和 2.4 同一个口径：玩家看得到的事件（`projection.is_visible`，在不在场按这一条之前的状态算，幕切换第 3 步的不算），
再加上玩家自己做成的、带效果的事（2.4 不推只改了不可见变量的，比如「渡した」，地图上要有玩家的举动；只花时间的不算）；
节拍走向的事件是玩家看到的，这个节拍他就知道；没看到的，知道这个节拍成立的事实（`knows`，听说）也算知道。
不知道的节拍只给时刻（ux-design 9.1）。「なぜ」只走发生了的事（被否决的不进，数据评审第 7 条），玩家看不到的事件
不上链，但它的前因照样往回找。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from zoujin_worldsim import SimState, apply, initial_state, knows, same_scene, spoilers

from zoujin_backend.projection import Away, _beat_label, as_you, committed, is_visible
from zoujin_backend.world import Book

Json = Any

MAX_CHAIN = 12  # 2.6：最长 12 步，超过时中间折叠
STATUS = {"happened": "canon"}  # 2.5：契约 WorldState.beats 的 happened 在时间线上叫 canon，其余同名
SLOW = ("delayed", "prevented")  # forecast：让节拍晚了、没了的那一步


@dataclass
class Replay:
    """把事件日志从头放一遍：最后的状态、每条事件、玩家看得到的事件、看到的节拍、见过的人物。"""

    state: SimState
    events: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    visible: list[Mapping[str, Any]] = field(default_factory=list)
    seen_beats: set[str] = field(default_factory=set)
    met: set[str] = field(default_factory=set)
    witnesses: dict[str, list[str]] = field(default_factory=dict)  # 事件 ID → 当时在那个场景的人物（含行为者）


def replay(book: Book, role_id: str, log: Sequence[Mapping[str, Any]]) -> Replay:
    world = book.world
    r = Replay(state=initial_state(world, role_id))
    away = Away()
    for ev in log:
        skipped = away(ev)
        r.events[ev["eventId"]] = ev
        where = r.state["vars"]["var.player.location"]
        if committed(ev):
            here = [
                c for c, p in r.state["locations"].items() if c in book.characters and same_scene(world, p, ev["place"])
            ]
            if ev["actor"] in book.characters and ev["actor"] not in here:
                here.append(ev["actor"])
            r.witnesses[ev["eventId"]] = here
        mine = ev["actor"] == "player" and committed(ev) and bool(ev["effects"])  # 玩家自己做成的事都上地图
        if not skipped and (mine or is_visible(book, ev, where)):
            r.visible.append(ev)
            r.seen_beats.update(e["beat"] for e in ev["effects"] if e.get("op") == "beat")
            r.met.update(
                c
                for c in r.witnesses.get(ev["eventId"], [])
                if same_scene(world, r.state["locations"].get(c, ev["place"]), where)
            )
        r.state = apply(world, r.state, ev)
    return r


def _beat_known(book: Book, r: Replay, beat: str) -> bool:
    if r.state["beats"].get(beat, "pending") == "pending":
        return False
    if beat in r.seen_beats:
        return True
    return any(f["trueFrom"] == beat and knows(book.world, r.state, "player", f["id"]) for f in book.world["facts"])


def cites(book: Book, state: SimState, beat: str) -> list[Json]:
    """2.5：原句带玩家此刻不知道的事实的剧透词的那条不出。"""
    return [c for c in book.beats[beat].get("cite", []) if not spoilers(book.world, state, "player", c["quote"])]


def _caused_by_player(r: Replay, ev: Mapping[str, Any]) -> bool:
    todo, done = [ev], set()
    while todo:
        x = todo.pop()
        if x["actor"] == "player":
            return True
        for c in x.get("causes", []):
            if c not in done and c in r.events:
                done.add(c)
                todo.append(r.events[c])
    return False


def timeline(book: Book, role_id: str, log: Sequence[Mapping[str, Any]], last_seq: int) -> Json:
    r = replay(book, role_id, log)
    items: list[tuple[tuple[int, int, int], Json]] = []
    for ev in r.visible:
        by_player = _caused_by_player(r, ev)
        style = (
            "player"
            if ev["actor"] == "player"
            else "system"
            if ev["actor"] == "system"
            else "caused"
            if by_player
            else "character"
        )
        item = {
            "kind": "event",
            "eventId": ev["eventId"],
            "t": ev["t"],
            "tLabel": book.label(ev["t"]),
            "summary": as_you(book, role_id, str(ev["summary"])),
            "place": ev["place"],
            "style": style,
            "causedByPlayer": by_player,
            "forPlayer": ev.get("beneficiary") == "player",
            "knownBy": [c for c in r.witnesses.get(ev["eventId"], []) if c in r.met],
        }
        items.append(((ev["t"], 0, ev["seq"]), item))
    for b in book.world["beats"]:
        t = r.state["times"].get(b["id"])
        if t is None:
            continue
        item = {"kind": "beat", "beatId": b["id"], "t": int(t), "tLabel": book.label(int(t)), "known": False}
        if _beat_known(book, r, b["id"]):
            item.update(known=True, title=b["title"], place=b["place"])
            item["status"] = STATUS.get(r.state["beats"][b["id"]], r.state["beats"][b["id"]])
            if c := cites(book, r.state, b["id"]):
                item["cite"] = c
        items.append(((int(t), 1, int(b["order"])), item))
    days: dict[int, list[Json]] = {}
    for _, item in sorted(items, key=lambda x: x[0]):
        days.setdefault(item["t"] // 1440, []).append(item)
    names = book.labels.days
    return {
        "days": [{"day": d, "label": names[min(d, len(names) - 1)], "items": xs} for d, xs in sorted(days.items())],
        "lastSeq": last_seq,
    }


class NotFound(Exception):
    """「なぜ」的目标不是玩家看得到的事件、知道的节拍（或关键时刻，切片还没有）。"""


def why(book: Book, role_id: str, log: Sequence[Mapping[str, Any]], target: str) -> Json:
    r = replay(book, role_id, log)
    shown = {ev["eventId"] for ev in r.visible}
    beat_step: Json | None = None
    if target == "forecast":
        last = next((ev for ev in reversed(r.visible) if any(e.get("to") in SLOW for e in _beats(ev))), None)
        if last is None:
            return {"target": target, "chain": [], "collapsed": 0}
        start = last
    elif target in r.events and target in shown:
        start = r.events[target]
    elif target in book.beats and _beat_known(book, r, target):
        start = next(
            (ev for ev in reversed(log) if committed(ev) and any(e["beat"] == target for e in _beats(ev))), None
        )
        if start is None:
            raise NotFound(target)
        change = next(e for e in _beats(start) if e["beat"] == target)
        beat_step = {
            "beatId": target,
            "tLabel": book.label(int(r.state["times"].get(target, start["t"]))),
            "summary": _beat_label(book, target, change["to"], change.get("variant")),
            "change": change["to"],
        }
        if c := cites(book, r.state, target):
            beat_step["cite"] = c
    else:
        raise NotFound(target)
    chain = [_event_step(book, role_id, ev) for ev in _ancestors(r, start) if ev["eventId"] in shown]
    if beat_step is not None:
        chain.append(beat_step)
    collapsed = max(0, len(chain) - MAX_CHAIN)
    if collapsed:
        chain = chain[: MAX_CHAIN // 2] + chain[-(MAX_CHAIN - MAX_CHAIN // 2) :]
    return {"target": target, "chain": chain, "collapsed": collapsed}


def _beats(ev: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [e for e in ev["effects"] if e.get("op") == "beat"]


def _ancestors(r: Replay, start: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """start 和它沿 `causes` 往回的全部前因（发生了的），按 seq 正序。"""
    todo, got = [start], {start["eventId"]: start}
    while todo:
        x = todo.pop()
        for c in x.get("causes", []):
            ev = r.events.get(c)
            if ev is not None and c not in got and committed(ev):
                got[c] = ev
                todo.append(ev)
    return sorted(got.values(), key=lambda ev: int(ev["seq"]))


def _event_step(book: Book, role_id: str, ev: Mapping[str, Any]) -> Json:
    step = {
        "eventId": ev["eventId"],
        "seq": ev["seq"],
        "tLabel": book.label(ev["t"]),
        "summary": as_you(book, role_id, str(ev["summary"])),
        "actor": ev["actor"],
    }
    if ev.get("beneficiary") == "player":
        step["forPlayer"] = True
    return step
