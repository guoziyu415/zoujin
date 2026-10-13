"""Timeline (api-contract 2.5) and 「なぜこうなった？」 (2.6): computed fresh from this game's event log every time,
never stored separately.

Same scope as 2.4: the events the player can see (`projection.is_visible`; presence is judged by the state before the
event, and step 3 of an act transition doesn't count), plus things the player themself got done that had effects (2.4
doesn't push events that only change invisible variables, e.g. 「渡した」, but the map should show the player's moves;
events that only spend time don't count). If the player saw the event that moved a beat, they know that beat; if they
didn't, knowing the fact the beat established (`knows`, by hearsay) also counts. Beats the player doesn't know get only
a time (ux-design 9.1). 「なぜ」 only follows things that happened (rejected ones don't enter, data review item 7);
events the player can't see are left out of the chain, but their causes are still traced back.

時間線（api-contract 2.5）と「なぜこうなった？」（2.6）：毎回このゲームのイベントログからその場で計算し、
別に保存しない。

2.4 と同じ範囲：プレイヤーに見えるイベント（`projection.is_visible`。その場にいたかはそのイベントの直前の状態で判断し、
幕切り替えの第 3 ステップのものは数えない）に、プレイヤー自身がやり遂げた効果のあることを加える
（2.4 は見えない変数だけを変えたもの、たとえば「渡した」をプッシュしないが、地図にはプレイヤーの行動が要る。
時間を使っただけのものは数えない）。ビートを動かしたイベントをプレイヤーが見ていれば、そのビートを知っている。
見ていなくても、そのビートが成立させた事実を知っていれば（`knows`、伝聞）知っているとみなす。
知らないビートは時刻だけを出す（ux-design 9.1）。「なぜ」は起きたことだけをたどり（却下されたものは入らない、
データレビュー第 7 項）、プレイヤーに見えないイベントはチェーンに載せないが、その原因は同じように遡って探す。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from zoujin_worldsim import SimState, apply, initial_state, knows, same_scene, spoilers

from zoujin_backend.projection import Away, _beat_label, as_you, committed, is_visible
from zoujin_backend.world import Book

Json = Any

MAX_CHAIN = 12  # 2.6: at most 12 steps, the middle collapsed beyond that / 最大 12 ステップ、超えたら中間を折りたたむ
# 2.5: the contract's WorldState.beats `happened` is called canon on the timeline; the rest keep their names.
# 2.5：契約の WorldState.beats の happened は時間線では canon と呼ぶ。それ以外は同じ名前。
STATUS = {"happened": "canon"}
SLOW = ("delayed", "prevented")  # forecast: the step that made a beat late or gone / ビートを遅らせた・消したステップ


@dataclass
class Replay:
    """Replay the event log from the start: the final state, every event, the events the player can see, the beats they
    saw, the characters they met.

    イベントログを最初から再生した結果：最後の状態、各イベント、プレイヤーに見えるイベント、見たビート、会った登場人物。
    """

    state: SimState
    events: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    visible: list[Mapping[str, Any]] = field(default_factory=list)
    seen_beats: set[str] = field(default_factory=set)
    met: set[str] = field(default_factory=set)
    # Event ID → the characters in that scene at the time (including the actor).
    # イベント ID → そのときその場面にいた登場人物（行為者を含む）。
    witnesses: dict[str, list[str]] = field(default_factory=dict)


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
        # Everything the player got done goes on the map / プレイヤー自身がやり遂げたことはすべて地図に載せる
        mine = ev["actor"] == "player" and committed(ev) and bool(ev["effects"])
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
    """2.5: leave out quotes that contain spoiler words for facts the player doesn't know yet.

    2.5：プレイヤーがまだ知らない事実のネタバレ語を含む原文の引用は出さない。
    """
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
    """The 「なぜ」 target is not an event the player can see or a beat they know (or a key moment, which the slice
    doesn't have yet).

    「なぜ」の対象が、プレイヤーに見えるイベントでも知っているビートでもない
    （あるいは重要な瞬間だが、スライスにはまだない）。
    """


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
    """`start` and all its causes found by following `causes` back (the ones that happened), in ascending seq order.

    start と、`causes` を遡ってたどれるすべての原因（起きたもの）を seq の昇順で返す。
    """
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
