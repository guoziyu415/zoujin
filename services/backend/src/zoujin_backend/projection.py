"""世界状态 → 前端看到的东西：快照（api-contract 2.3）、玩家可见的事件（2.4）、commit 的 patch（3.4）。

快照和 commit 用同一个投影：patch = 提交前后两个快照的差。

B-0 的投影只做骨架能给的：场景里的人物（位置点按布局分配，activity 一律 idle，此刻不在场的是 absent、不能搭话（B-2，
S-077 ⑩）；还没有关系的省略关系）、地点能不能进、
场景出口、期限和梅洛斯的预计到达。情境动作、可调查物、关系、记忆、待处理的东西是 M2 各卡的。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from zoujin_worldsim import OCCURRED, SimState, flat, world_state

from zoujin_backend.narrator.rules import absent, index
from zoujin_backend.world import Book

Json = Any

PROMISE_BEAT = "beat.05"  # 「約束」：之后才显示期限和预计到达（S-049 ④、防剧透）
DEADLINE_TAIL = "遅れれば、身代わりが死ぬ"  # 期限那一行的后半（api-contract 2.3 的例子）；UX 定了文案再换
VOICE = {"enabled": True, "degraded": False, "minutesLeftToday": 60}  # 预算是 M2 的卡
PENDING = {"reveal": None, "confirm": None, "actEnd": None, "safetyPause": False, "approach": None}
CLOSED = "いまは入れない"
COMMITTED = ("passed", "rewritten", "downgraded")


# —— 事件 ——


def committed(ev: Mapping[str, Any]) -> bool:
    return bool(ev["check"]["status"] in COMMITTED)


def _beat_label(book: Book, beat: str, change: str, variant: str | None = None) -> str:
    b = book.beats[beat]
    if change in ("happened", "altered"):
        if variant:
            for v in b.get("variants", []):
                if v["id"] == variant and v.get("summary"):
                    return str(v["summary"])
        return str(b["title"])
    return f"「{b['title']}」" + {"prevented": "は起きなかった", "delayed": "が遅れる", "hastened": "が早まる"}[change]


def visible_effects(book: Book, effects: Sequence[Mapping[str, Any]]) -> list[Json]:
    """2.4 的 visibleEffects：可见变量（只给标签）和节拍走向。"""
    svars = {v["id"]: v for v in book.world["stateVars"]}
    out: list[Json] = []
    for e in effects:
        if e.get("op") == "set":
            v = svars.get(e.get("var", ""))
            labels = (v or {}).get("valueLabels") or {}
            key = str(e["value"]).lower() if isinstance(e.get("value"), bool) else str(e.get("value"))
            if v and v.get("visibleToPlayer") and key in labels:
                out.append({"kind": "var", "var": e["var"], "label": labels[key]})
        elif e.get("op") == "beat" and e.get("beat") in book.beats:
            out.append(
                {
                    "kind": "beat",
                    "beat": e["beat"],
                    "change": e["to"],
                    "label": _beat_label(book, e["beat"], e["to"], e.get("variant")),
                }
            )
    return out


def promise_change(effects: Sequence[Mapping[str, Any]]) -> Json | None:
    for e in effects:
        if e.get("op") == "promise" and e.get("promiseId"):
            return {"promiseId": e["promiseId"], "change": e["change"]}
    return None


def is_visible(book: Book, ev: Mapping[str, Any], player_place: str) -> bool:
    """第 0 节：改的是可见变量或节拍走向（或约定），并且玩家在场或是玩家做的。被否决的不推。"""
    if not committed(ev):
        return False
    if not visible_effects(book, ev["effects"]) and promise_change(ev["effects"]) is None:
        return False
    return bool(ev["actor"] == "player" or ev["place"] == player_place)


def visible_event(book: Book, ev: Mapping[str, Any]) -> Json:
    out: Json = {
        "eventId": ev["eventId"],
        "seq": ev["seq"],
        "t": ev["t"],
        "dt": ev["dt"],
        "tLabel": book.label(ev["t"]),
        "type": ev["type"],
        "actor": ev["actor"],
        "forPlayer": ev.get("beneficiary") == "player",
        "place": ev["place"],
        "summary": ev["summary"],
        "causes": list(ev["causes"]),
        "visibleEffects": visible_effects(book, ev["effects"]),
        "promise": promise_change(ev["effects"]),
        "keyMoment": ev["keyMoment"],
        "supersedes": ev.get("supersedes"),
    }
    if ev.get("turnId"):
        out["turnId"] = ev["turnId"]
    return out


# —— 快照 ——


def _holds(conds: Sequence[Mapping[str, Any]], values: Mapping[str, Any]) -> bool:
    ops = {
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        "<": lambda a, b: a < b,
    }
    return all(ops[c["op"]](values.get(c["var"]), c["value"]) for c in conds)


def place_open(book: Book, role_id: str, place: str, state: SimState) -> bool:
    role = book.roles[role_id]
    if place in role.get("access", []):
        return True
    vals = flat(state)
    return any(c["place"] == place and _holds(c["when"], vals) for c in role.get("conditionalAccess", []))


def snapshot(book: Book, pid: str, role_id: str, status: str, state: SimState, last_seq: int) -> Json:
    """2.3 的快照。state 是 last_seq 时的 SimState。"""
    vars_ = state["vars"]
    act = book.act_of(vars_)
    player_place: str = vars_["var.player.location"]
    scene_id = book.scene_of(player_place, act)
    scene = book.scenes.get(scene_id)
    scene_places = list(scene.places) if scene else [player_place]
    deadline_t: int = book.world["clock"]["deadline"]["t"]
    promised = state["beats"].get(PROMISE_BEAT) in OCCURRED

    present = [(c, state["locations"][c]) for c in book.characters if state["locations"].get(c) in scene_places]
    player_spot = scene.player_spot(player_place) if scene else player_place.removeprefix("place.")
    spots = (
        scene.character_spots(present, {player_spot}) if scene else {c: p.removeprefix("place.") for c, p in present}
    )
    ix = index(book.world)
    away = {c for c, _ in present if absent(ix, state, c)}
    characters = [
        {
            "id": c,
            "place": p,
            "spot": spots[c],
            "activity": "absent" if c in away else "idle",
            "talkable": c not in away and bool(book.characters[c].get("talkable")),
        }
        for c, p in present
    ]
    places = []
    for p in scene_places:
        entry: Json = {"id": p, "enabled": place_open(book, role_id, p, state)}
        if not entry["enabled"]:
            entry["reason"] = CLOSED
        places.append(entry)
    interactables = []
    for ex in scene.exits if scene else ():
        interactables.append(
            {
                "id": ex["spot"],
                "kind": "go",
                "spot": ex["spot"],
                "label": book.places[ex["place"]]["name"],
                "enabled": place_open(book, role_id, ex["place"], state),
                "estimatedMinutes": _travel(book, player_place, ex["place"]),
            }
        )

    forecast = None
    if promised:
        watch: str = book.world["clock"]["deadline"]["watchBeat"]
        eta = state["times"].get(watch)
        if eta is None:
            eta = world_state(book.world, state, pid)["schedule"].get(watch)
        if eta is not None:
            forecast = {"melosEtaT": eta, "beforeDeadline": eta <= deadline_t}
    deadline: Json = {"shown": promised}
    if promised:
        deadline["line"] = f"期限　{book.world['clock']['deadline']['label']}／{DEADLINE_TAIL}"

    return {
        "playthroughId": pid,
        "lastSeq": last_seq,
        "status": status,
        "actId": act,
        "sceneId": scene_id,
        "clock": {"t": state["t"], "tLabel": book.label(state["t"]), "deadlineT": deadline_t},
        "deadline": deadline,
        "forecast": forecast,
        "player": {
            "roleId": role_id,
            "place": player_place,
            "spot": player_spot,
        },
        "places": places,
        "characters": characters,
        "interactables": interactables,
        "actions": [],
        "pending": dict(PENDING),
        "voice": dict(VOICE),
    }


def _travel(book: Book, a: str, b: str) -> int:
    for adj in book.places.get(a, {}).get("adjacent", []):
        if adj["place"] == b:
            return int(adj.get("travelMinutes", 0))
    return 0


# —— patch ——


def _by_id(xs: Sequence[Json], key: str) -> dict[str, Json]:
    return {x[key]: x for x in xs}


def _add_remove(before: Sequence[Json], after: Sequence[Json], key: str) -> Json | None:
    a, b = _by_id(before, key), _by_id(after, key)
    add = [x for k, x in b.items() if a.get(k) != x]
    remove = [k for k in a if k not in b]
    out: Json = {}
    if add:
        out["add"] = add
    if remove:
        out["remove"] = remove
    return out or None


def patch(before: Json, after: Json) -> Json:
    """commit.patch：快照字段的增量，按 id 合并（3.4）。clock 每次都带。"""
    out: Json = {"clock": {"t": after["clock"]["t"], "tLabel": after["clock"]["tLabel"]}}
    for k in ("deadline", "forecast"):
        if before[k] != after[k]:
            out[k] = after[k]
    a, b = _by_id(before["characters"], "id"), _by_id(after["characters"], "id")
    chars: list[Json] = []
    for cid, now in b.items():
        was = a.get(cid)
        if was is None:
            chars.append(now)
        elif was != now:
            chars.append({"id": cid, **{k: v for k, v in now.items() if was.get(k) != v}})
    for cid in a:
        if cid not in b:
            chars.append({"id": cid, "place": after["_locations"][cid]})
    if chars:
        out["characters"] = chars
    pa, pb = _by_id(before["places"], "id"), _by_id(after["places"], "id")
    places = [x for k, x in pb.items() if pa.get(k) != x]
    if places:
        out["places"] = places
    player = {k: v for k, v in after["player"].items() if k != "roleId" and before["player"].get(k) != v}
    if player:
        out["player"] = player
    for k, key in (("actions", "actionId"), ("interactables", "id")):
        d = _add_remove(before[k], after[k], key)
        if d:
            out[k] = d
    return out


def with_locations(snap: Json, state: SimState) -> Json:
    """patch 要知道离场的人物去了哪里；快照里不给不在场的人，所以另外挂在 `_locations` 上（不发出去）。"""
    return {**snap, "_locations": dict(state["locations"])}
