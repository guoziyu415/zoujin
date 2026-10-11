"""世界状态 → 前端看到的东西：快照（api-contract 2.3）、玩家可见的事件（2.4）、commit 的 patch（3.4）。

快照和 commit 用同一个投影：patch = 提交前后两个快照的差。

B-0 的投影只做骨架能给的：场景里的人物（位置点按契约 3.1：relocate 指定的站那里，`group` 的不占，其余按布局
分配；activity 是世界模型给的那部分，W-1 的 `activity()`；此刻不在场的是 absent、不能搭话（B-2，S-077 ⑩）；
还没有关系的省略关系）、地点能不能进、场景出口、期限和梅洛斯的预计到达。

B-3 加了：情境动作（世界模型的 affordances 里此刻成立的）、可调查物（objects）、出口一律能点（拦不拦由判定说，
S-077 ③）、玩家的位置点（局上记的，`Run.player_spot`）、期限一行按玩家知不知道约定（S-077 ⑫）、
`pending.actEnd` 和 `pending.arrival`。关系、记忆、别的待处理的东西是 M2 各卡的。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from zoujin_worldsim import SimState, activity, arrival_delta, flat, knows, world_state

from zoujin_backend.db.store import Run
from zoujin_backend.world import Book

Json = Any

PROMISE_FACT = "fact.promise"  # 玩家知道约定以后才显示期限和预计到达（S-077 ⑫，api-contract 2.3）
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


YOU = "あなた"
ENDS = ("。", "！", "？", "!", "?")


def as_you(book: Book, role_id: str, text: str, *, period: bool = False) -> str:
    """下发给前端的事件句里，玩家一律是「あなた」：把这一局的身份名换掉（存的 summary 照旧用身份名，模型、检查、
    评测读那一份）。名字里含身份名的人物（例「一団の旅人」）不换。period：句末没有「。」就补上（recapLines、
    「その頃」；commit 的 summary 不补，前端放在括号里）。"""
    name = str(book.roles[role_id]["name"])
    keep = sorted(
        {str(c["name"]) for c in book.characters.values() if name in str(c["name"]) and c["name"] != name},
        key=len,
        reverse=True,
    )
    for i, k in enumerate(keep):
        text = text.replace(k, f"\x00{i}\x00")
    text = text.replace(name, YOU)
    for i, k in enumerate(keep):
        text = text.replace(f"\x00{i}\x00", k)
    if period and text and not text.endswith(ENDS):
        text += "。"
    return text


def visible_event(book: Book, ev: Mapping[str, Any], role_id: str) -> Json:
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
        "summary": as_you(book, role_id, str(ev["summary"])),
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


def action_id(affordance: str) -> str:
    """快照里情境动作的 ID：`act_` 加上 Affordance ID 去掉 `aff.` 的部分（B-3），前端原样回传。"""
    return "act_" + affordance.removeprefix("aff.")


def item_ready(book: Book, state: SimState, item: str | None) -> bool:
    """情境动作要用的物品此刻拿得到（叙事者 R7 的同一个判法）：不能带走的在这个地点，能带走的在玩家手上。"""
    it = next((x for x in book.world.get("items", []) if x["id"] == item), None)
    if it is None:
        return True
    if it.get("portable"):
        return bool(state["holdings"].get(it["id"]) == "player")
    return state["vars"]["var.player.location"] in it.get("at", [])


def open_affordances(book: Book, state: SimState) -> list[Json]:
    """此刻成立的情境动作（B-3 第 1 条）：玩家所在地点、这一幕、这个身份、when 成立、对象人物在这里而且不是
    absent、要用的物品拿得到。"""
    vars_ = state["vars"]
    place, act, values = vars_["var.player.location"], book.act_of(vars_), flat(state)
    out = []
    for a in book.world.get("affordances", []):
        if a["place"] != place or a.get("act", act) != act:
            continue
        if a.get("roles") and state["role"] not in a["roles"]:
            continue
        if a.get("when") and not book.sim.holds(a["when"], values):
            continue
        who = a.get("target")
        if who is not None and (state["locations"].get(who) != place or activity(book.world, state, who) == "absent"):
            continue
        if not item_ready(book, state, a.get("item")):
            continue
        out.append(a)
    return out


def affordance_minutes(book: Book, a: Json) -> int:
    return int(a.get("minutes", book.world["pacing"]["situationalMinMinutes"]))


def situational(book: Book, state: SimState, a: Json) -> Json:
    """快照的 SituationalAction。带 melos 的按本局此刻算梅洛斯会晚几分钟、还赶不赶得上（W-1 arrival_delta）。"""
    out: Json = {"actionId": action_id(a["id"]), "kind": a["kind"]}
    if a.get("target"):
        out["target"] = a["target"]
    out |= {
        "label": a["label"],
        "estimatedMinutes": affordance_minutes(book, a),
        "melos": a.get("melos"),
        "melosMinutes": None,
        "melosInTime": None,
        "enabled": True,
    }
    if a.get("melos"):
        effects = [e for e in a.get("effects", []) if e.get("op") not in ("promise", "improv")]
        try:
            d = arrival_delta(book.world, state, effects, state["t"])
            out["melosMinutes"], out["melosInTime"] = int(d["minutes"]), bool(d["inTime"])
        except ValueError:  # 和已登记的改动合不了：照世界模型写的分钟，赶不赶得上按现在的预计
            out["melosMinutes"] = int(a.get("melosMinutes", 0))
            out["melosInTime"] = True
    return out


def player_spot(book: Book, state: SimState, run: Run | None) -> str:
    """玩家站的位置点：局上记的（属于玩家现在的地点时），不然是这个地点的起点（契约 3.1，B-3 第 1 条）。"""
    place: str = state["vars"]["var.player.location"]
    scene = book.scenes.get(book.scene_of(place, book.act_of(state["vars"])))
    if scene is None:
        return place.removeprefix("place.")
    if run is not None and run.player_spot and scene.spots.get(run.player_spot) == place:
        return run.player_spot
    return scene.player_spot(place)


def pending(run: Run | None) -> Json:
    out: Json = dict(PENDING)
    if run is not None:
        out["actEnd"] = run.act_end
        if run.arrival and run.arrival.get("opener"):
            out["arrival"] = {k: run.arrival[k] for k in ("line", "opener")}
    return out


def snapshot(
    book: Book, pid: str, role_id: str, status: str, state: SimState, last_seq: int, run: Run | None = None
) -> Json:
    """2.3 的快照。state 是 last_seq 时的 SimState；run 是局上记的位置点和待处理的（没给 = 起点、没有待处理的）。"""
    vars_ = state["vars"]
    act = book.act_of(vars_)
    player_place: str = vars_["var.player.location"]
    scene_id = book.scene_of(player_place, act)
    scene = book.scenes.get(scene_id)
    scene_places = list(scene.places) if scene else [player_place]
    deadline_t: int = book.world["clock"]["deadline"]["t"]
    promised = knows(book.world, state, "player", PROMISE_FACT)

    present = [(c, state["locations"][c]) for c in book.characters if state["locations"].get(c) in scene_places]
    doing = {c: activity(book.world, state, c) for c, _ in present}  # W-1：节拍给的 activity，absent = 不在场
    away = {c for c, a in doing.items() if a == "absent"}
    me = player_spot(book, state, run)
    # 契约 3.1 的站位规则：group 的人物不占位置点；relocate 写了 spot 的站那里（布局里这个地点得有这个点）；
    # 其余的人按布局顺序站空着的点，玩家和指定的点算占着
    group = {c for c, _ in present if book.characters[c].get("group")}
    named = state.get("spots", {})
    fixed = {
        c: named[c] for c, p in present if c not in group and c in named and scene and scene.spots.get(named[c]) == p
    }
    rest = [x for x in present if x[0] not in group and x[0] not in fixed]
    # 看得见的人先排位置点，不在场的排在最后：前端不画他们，别让他们挤掉看得见的人的点
    order = [x for x in rest if x[0] not in away] + [x for x in rest if x[0] in away]
    if scene:
        spots = {**scene.character_spots(order, {me, *fixed.values()}), **fixed}
    else:
        spots = {c: p.removeprefix("place.") for c, p in order}
    characters = []
    for c, p in present:
        who: Json = {"id": c, "place": p}
        if c in group:
            who["group"] = True
        else:
            who["spot"] = spots[c]
        who["activity"] = doing[c]
        who["talkable"] = c not in away and bool(book.characters[c].get("talkable"))
        characters.append(who)
    places = []
    for p in scene_places:
        entry: Json = {"id": p, "enabled": place_open(book, role_id, p, state)}
        if not entry["enabled"]:
            entry["reason"] = CLOSED
        places.append(entry)
    interactables = []
    for obj in book.world.get("objects", []):  # 調べる（契约 2.12）：这个场景里的、布局里有位置点的
        if obj["place"] in scene_places and obj.get("spot"):
            interactables.append(
                {
                    "id": obj["id"],
                    "kind": "examine",
                    "spot": obj["spot"],
                    "label": obj["label"],
                    "enabled": place_open(book, role_id, obj["place"], state),
                    "estimatedMinutes": 0,
                }
            )
    for ex in scene.exits if scene else ():  # 出口一律能点，拦不拦由判定说（S-077 ③）
        interactables.append(
            {
                "id": ex["spot"],
                "kind": "go",
                "spot": ex["spot"],
                "label": book.places[ex["place"]]["name"],
                "enabled": True,
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
            "spot": me,
        },
        "places": places,
        "characters": characters,
        "interactables": interactables,
        "actions": [situational(book, state, a) for a in open_affordances(book, state)],
        "pending": pending(run),
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
