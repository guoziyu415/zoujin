"""一口气推演：参考实现 reference/worldsim.py 的 Sim 原样移植（W-1），加类型标注，行为不改。

只改了一处：开局状态不再写死成广场，按身份读（Role.startPlace、Role.items，另按契约 3.1 把 var.act.current
设成 Role.startAct；没有条件用到它，推演结果不变），所以 run()、arrival_delta() 要传 role。
规则的来由见参考实现的文件头和 docs/data/contracts.md 2.4.1、2.5.1、2.6（1.6 的取值条件）。
"""

from __future__ import annotations

import copy
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

type World = Mapping[str, Any]
type State = dict[str, Any]
type Effect = Mapping[str, Any]
type Condition = Mapping[str, Any]
type Scenario = Mapping[str, Any]
type Override = dict[str, Any]

OCCURRED = ("happened", "altered")  # contracts 2.5（1.4 写清）：requires 的「发生了」包括 altered
OPS: dict[str, Callable[[Any, Any], bool]] = {
    "==": lambda x, y: x == y,
    "!=": lambda x, y: x != y,
    ">=": lambda x, y: x >= y,
    "<=": lambda x, y: x <= y,
    "in": lambda x, y: x in y,
}
BIG = 10**9
SIGN = {"delayed": 1, "hastened": -1}  # 推迟的分钟为正，提前为负


def change_conflict(old: Override | None, new: Mapping[str, Any]) -> str | None:
    """contracts 第 3 节（1.6 写清）：本局对一个还没结果的节拍只有一种改动。old 是已登记的改动（没有是 None），
    new 是新的 {to, minutes?, outcomes?, note?}。能合返回 None，不能合返回原因（自检报 bad-state）。"""
    if old is None or (new["to"] == "prevented" and old["to"] != "prevented"):
        return None
    if old["to"] == "prevented":
        return "已经登记了 prevented，不能再改"
    if old["to"] in SIGN and new["to"] in SIGN:
        return None
    return f"已经登记了 {old['to']}，不能再登记 {new['to']}（altered 不和推迟、提前混用，也只登记一次）"


def merge_change(over: dict[str, Override], e: Effect) -> None:
    """把一条 {op: beat} 改动合进 over（节拍 ID → 改动，就地改）：
    - delayed、hastened 按带符号的分钟相加，净值 0 就去掉这条改动；
    - prevented 顶掉之前的推迟、提前、改写；
    - 其他组合（已登记 prevented 之后再改；altered 和推迟、提前混用；第二次 altered）抛 ValueError。"""
    bid = e["beat"]
    new: Override = {k: copy.deepcopy(v) for k, v in e.items() if k not in ("op", "beat")}
    old = over.get(bid)
    why = change_conflict(old, new)
    if why:
        raise ValueError(f"{bid}：{why}")
    if new["to"] in SIGN:
        net = SIGN[new["to"]] * new["minutes"] + (SIGN[old["to"]] * old["minutes"] if old else 0)
        if net == 0:
            over.pop(bid, None)
            return
        new = {**new, "to": "delayed" if net > 0 else "hastened", "minutes": abs(net)}
    over[bid] = new


def role_of(world: World, role_id: str) -> Mapping[str, Any]:
    for r in world["roles"]:
        if r["id"] == role_id:
            return r  # type: ignore[no-any-return]
    raise KeyError(f"身份不存在：{role_id}")


class Sim:
    def __init__(self, world: World) -> None:
        self.world = world
        self.svars: dict[str, Mapping[str, Any]] = {v["id"]: v for v in world["stateVars"]}
        self.beats: dict[str, Mapping[str, Any]] = {b["id"]: b for b in world["beats"]}
        self.chars: dict[str, Mapping[str, Any]] = {c["id"]: c for c in world["characters"]}
        self.endings = sorted(world.get("endings", {}).get("world", []), key=lambda x: x["order"])
        # to -> [(from, type, minutes)]：只含传递时间偏移的边
        self.parents: defaultdict[str, list[tuple[str, str, int]]] = defaultdict(list)
        # to -> [(from, type)]：timeLink = "order" 的边，只要求不早于 from（contracts 2.5.1，1.1）
        self.after: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
        # 有 delays / hastens 出边的节拍：它发不发生决定后面的时间
        self.timed: set[str] = set()
        for e in world["causal"]:
            if e["from"] in self.beats and e["to"] in self.beats:
                if e.get("timeLink") == "order":
                    self.after[e["to"]].append((e["from"], e["type"]))
                else:
                    self.parents[e["to"]].append((e["from"], e["type"], e.get("minutes", 0)))
                if e["type"] in ("delays", "hastens"):
                    self.timed.add(e["from"])
        self._loose: Sim | None = None

    def holds(self, conds: Iterable[Condition], state: Mapping[str, Any]) -> bool:
        return all(OPS[c["op"]](state.get(c["var"]), c["value"]) for c in conds)

    def apply(self, effs: Iterable[Effect], state: State, where: dict[str, Any] | None = None) -> None:
        for e in effs:
            if e["op"] == "set":
                state[e["var"]] = e["value"]
            elif e["op"] == "inc":
                v = self.svars[e["var"]]
                state[e["var"]] = max(v.get("min", -BIG), min(v.get("max", BIG), state[e["var"]] + e["by"]))
            elif e["op"] == "relocate" and where is not None:
                where[e["character"]] = e["place"]
            elif e["op"] == "hold":  # contracts 1.3：物品换手，持有者记在 state[物品 ID]
                state[e["item"]] = e["to"]

    def value_requires(
        self, effs: Iterable[Effect], state: Mapping[str, Any], origin: str | None = None
    ) -> list[dict[str, Any]]:
        """contracts 2.6（1.6，C-16）StateVar.valueRequires：事件把变量改成某个值时，这个值的 when 要成立。
        ① 只有 origin == "schedule"（到点的节拍和期限）不判；导演事件的 actor 也是 system，照样判，不能按 actor 跳过；
        ② 值真的变了才判；③ 按这个 effect 之前的状态判，同一事件里前面的 effect 已经生效；
        ④ when 和节拍前提用同一个 holds()；⑤ 设好以后条件不再成立不追究。
        不改 state。返回违反的条目 [{var, value, when, note}]。"""
        if origin == "schedule":
            return []
        out: list[dict[str, Any]] = []
        cur = dict(state)
        for e in effs:
            nxt = dict(cur)
            self.apply([e], nxt)
            var = e.get("var") if e["op"] in ("set", "inc") else None
            if var is not None and nxt.get(var) != cur.get(var):
                for r in self.svars.get(var, {}).get("valueRequires", []):
                    if r["value"] == nxt[var] and not self.holds(r["when"], cur):
                        out.append({"var": var, "value": nxt[var], "when": r["when"], "note": r["note"]})
            cur = nxt
        return out

    def schedule(self, over: Mapping[str, Override], _floor: bool = True) -> tuple[dict[str, int], set[str]]:
        """2.5.1：先排时间（与状态无关）。返回 (shift, late)。到达下限的算法见参考实现。"""
        shift: dict[str, int] = {}
        late: set[str] = set()
        dl = self.world["clock"]["deadline"]
        wb, floor = dl.get("watchBeat"), dl.get("earliestArrival")
        use_floor = _floor and wb in self.beats and floor is not None
        for b in sorted(self.world["beats"], key=lambda b: (b["window"]["canonical"], b["order"])):
            bid, w = b["id"], b["window"]
            ps = self.parents[bid]
            if any(f in late for f, ty, _ in ps if ty in ("enables", "requires")) or any(
                f in late for f, _ in self.after[bid]
            ):
                late.add(bid)
                continue
            sh = max([shift.get(f, 0) for f, ty, _ in ps if ty in ("enables", "requires")], default=0)
            for f, ty, m in ps:
                if ty == "delays" and over.get(f, {}).get("to") == "prevented":
                    sh -= m
                if ty == "hastens" and over.get(f, {}).get("to") == "prevented":
                    sh += m
            o = over.get(bid, {})
            if o.get("to") == "delayed":
                sh += o["minutes"]
            if o.get("to") == "hastened":
                sh -= o["minutes"]
            t = max(
                [w["earliest"], w["canonical"] + sh]
                + [self.beats[f]["window"]["canonical"] + shift.get(f, 0) for f, _ in self.after[bid]]
            )
            if use_floor and bid == wb and over:
                keys = sorted(over, key=lambda x: self.beats[x]["order"] if x in self.beats else 0)
                prev = a = 0
                for k in range(1, len(keys) + 1):
                    s_k = self.schedule({x: over[x] for x in keys[:k]}, _floor=False)[0].get(wb, 0)
                    a, prev = max(floor - w["canonical"], a + s_k - prev), s_k
                t = w["canonical"] + a + (t - w["canonical"] - prev)
            shift[bid] = t - w["canonical"]
            if t > w["latest"]:
                late.add(bid)
        return shift, late

    def run(
        self, sc: Scenario, until: tuple[str, Any] | None = None, *, role: str, place: str | None = None
    ) -> dict[str, Any]:
        """按时间顺序应用效果、检查前提，返回值和参考实现 run() 一样（outcome、status、times、state、where、t、
        stopped、late、shift、variant、violations、auto、over，停在中途时另有 rest）。
        role：身份 ID，开局地点、随身物品和开始的幕从它读（参考实现是传 start_place、player_items）。
        place：评测用例的 setup.place 另给开局地点时用，不给 = 身份的 startPlace。

        contracts 2.5.1：有 delays / hastens 出边的节拍，在排定时间那一刻判前提，不成立就当场记为 prevented，
        它的分钟照样退还。所以先整局推演，把这类节拍补进 over，直到不再变化（auto）。
        """
        r = role_of(self.world, role)
        start = {"var.player.location": place or r["startPlace"]}
        if "startAct" in r and "var.act.current" in self.svars:
            start["var.act.current"] = r["startAct"]
        player_items = tuple(r.get("items") or ())
        over: dict[str, Override] = dict(sc.get("beats", {}))
        auto: set[str] = set()
        full: dict[str, Any] = {}
        for _ in range(len(self.timed) + 1):
            full = self._run(sc, over, None, start, player_items)
            new = {
                b
                for b, st in full["status"].items()
                if st == "precondition-failed" and b in self.timed and b not in over
            }
            if not new:
                break
            for b in new:
                over[b] = {"to": "prevented"}
            auto |= new
        res = full if until is None else self._run(sc, over, until, start, player_items)
        res["auto"], res["over"] = auto, over
        return res

    def _run(
        self,
        sc: Scenario,
        over: Mapping[str, Override],
        until: tuple[str, Any] | None,
        start: Mapping[str, Any],
        player_items: Sequence[str] = (),
    ) -> dict[str, Any]:
        shift, late = self.schedule(over)
        state: State = {v["id"]: v["default"] for v in self.world["stateVars"]}
        state.update(start)  # 身份决定的初值（var.player.location、var.act.current）
        for c, x in self.chars.items():  # contracts 1.3：WorldState.holdings 的初值
            for it in x.get("items", []):
                state[it] = c
        for it in player_items:
            state[it] = "player"
        where: dict[str, Any] = {c: x.get("initialPlace") for c, x in self.chars.items()}
        status: dict[str, str] = {}
        times: dict[str, int] = {}
        queue: list[tuple[int, int, int, str, Any]] = [
            (b["window"]["canonical"] + shift.get(b["id"], 0), 0, b["order"], "beat", b) for b in self.world["beats"]
        ]
        # 同一时刻：先节拍，再期限，最后事件（2026-10-10，W-1 增量接口）
        queue += [(ev["t"], 2, 0, "event", ev) for ev in sc.get("events", [])]
        queue.append((self.world["clock"]["deadline"]["t"], 1, 0, "deadline", None))
        queue.sort(key=lambda q: q[:3])
        variant: dict[str, str] = {}  # contracts 1.4：节拍 ID → 本局用的变体 ID
        res: dict[str, Any] = {
            "status": status,
            "times": times,
            "state": state,
            "where": where,
            "outcome": None,
            "t": None,
            "stopped": until is None,
            "late": late,
            "shift": shift,
            "variant": variant,
            "violations": [],  # 1.6：违反 valueRequires 的事件 [(t, 违反的条目)]
        }
        for i, (t, _, _, kind, x) in enumerate(queue):
            if until and until[0] == "t" and t > until[1]:
                res["t"], res["stopped"], res["rest"] = until[1], True, queue[i:]
                return res
            if kind == "event":
                res["violations"] += [(t, v) for v in self.value_requires(x["effects"], state)]
            self._step(kind, x, t, over, late, state, where, status, times, variant)
            if until and until[0] == "beat" and kind == "beat" and x["id"] == until[1]:
                res["t"], res["stopped"], res["rest"] = t, status[x["id"]] in OCCURRED, queue[i + 1 :]
                return res
        if until:
            res["t"] = until[1] if until[0] == "t" else None
            res["stopped"], res["rest"] = until[0] == "t", []
            return res
        res["outcome"] = self.classify(state)
        return res

    def resume(
        self,
        res: dict[str, Any],
        sc: Scenario,
        extra_effects: Sequence[Effect] = (),
        until_t: int | None = None,
    ) -> dict[str, Any]:
        """从 run(until=…) 的停止点继续：先应用 extra_effects，再推演到 until_t（None = 到底并分类结局）。
        排定时间沿用 run() 算好的（extra_effects 不再改时间表）。"""
        over = res["over"]
        state, where, status, times = res["state"], res["where"], res["status"], res["times"]
        res["violations"] += [(res["t"], v) for v in self.value_requires(extra_effects, state)]
        self.apply(extra_effects, state, where)
        if res["t"] is not None:
            self._recheck(res["t"], over, state, where, status, times, res["variant"])
        for t, _, _, kind, x in res["rest"]:
            if until_t is not None and t > until_t:
                res["t"] = until_t
                return res
            if kind == "event":
                res["violations"] += [(t, v) for v in self.value_requires(x["effects"], state)]
            self._step(kind, x, t, over, res["late"], state, where, status, times, res["variant"])
        res["t"] = until_t
        if until_t is None:
            res["outcome"] = self.classify(state)
        return res

    def arrival_delta(
        self, sc: Scenario, effects: Sequence[Effect], t: int, *, role: str, place: str | None = None
    ) -> dict[str, Any]:
        """S-066 ①：本局到此为止是情景 sc，在时刻 t 再提交 effects，梅洛斯到刑场（watchBeat）会晚（+）或早（−）几分钟。
        返回 {"minutes": 分钟数（含到达下限）, "inTime": 做了以后还赶不赶得上}。分钟数用去掉 window.latest 的副本算。
        effects 里的节拍改动按 merge_change() 合进 sc 已有的改动；合不了（自检的 bad-state）抛 ValueError。"""
        wb = self.world["clock"]["deadline"].get("watchBeat")
        beats: dict[str, Override] = {b: dict(o) for b, o in sc.get("beats", {}).items()}
        for e in effects:
            if e.get("op") == "beat":
                merge_change(beats, e)
        rest = [x for x in effects if x.get("op") != "beat"]
        after = {
            **sc,
            "beats": beats,
            "events": list(sc.get("events", [])) + ([{"t": t, "effects": rest}] if rest else []),
        }
        if self._loose is None:
            loose = {
                **self.world,
                "beats": [{**b, "window": {**b["window"], "latest": BIG}} for b in self.world["beats"]],
            }
            self._loose = Sim(loose)
        a, b = self._loose.run(sc, role=role, place=place), self._loose.run(after, role=role, place=place)
        real = self.run(after, role=role, place=place)
        return {
            "minutes": b["shift"].get(wb, 0) - a["shift"].get(wb, 0),
            "inTime": real["status"].get(wb) in OCCURRED,
        }

    def classify(self, state: Mapping[str, Any]) -> str | None:
        return next((en["id"] for en in self.endings if self.holds(en["when"], state)), None)

    def _step(
        self,
        kind: str,
        x: Any,
        t: int,
        over: Mapping[str, Override],
        late: set[str],
        state: State,
        where: dict[str, Any],
        status: dict[str, str],
        times: dict[str, int],
        variant: dict[str, str] | None = None,
    ) -> None:
        self._step1(kind, x, t, over, late, state, where, status, times, variant)
        self._recheck(t, over, state, where, status, times, variant)

    def _waiting(self, bid: str, status: Mapping[str, str], t: int) -> bool:
        """contracts 2.4.1 第 3 条：排定时间到了而前提不成立（或 requires 的前一节拍还没发生），到 window.latest 为止
        每次时钟前进都再查。有 delays / hastens 出边的节拍除外：当场 prevented（run() 的 auto）。"""
        return (
            status.get(bid) in ("precondition-failed", "blocked")
            and bid not in self.timed
            and t <= self.beats[bid]["window"]["latest"]
        )

    def _recheck(
        self,
        t: int,
        over: Mapping[str, Override],
        state: State,
        where: dict[str, Any],
        status: dict[str, str],
        times: dict[str, int],
        variant: dict[str, str] | None,
    ) -> None:
        """每一步之后，按排定顺序再查还在等的节拍；成立的在此刻 t 发生。查到不再变化。"""
        changed = True
        while changed:
            changed = False
            for bid in sorted((b for b in status if self._waiting(b, status, t)), key=lambda b: self.beats[b]["order"]):
                x = self.beats[bid]
                if self._ready(x, status, state):
                    self._occur(x, t, over.get(bid, {}), state, where, status, times, variant)
                    changed = True

    def requires_met(self, bid: str, status: Mapping[str, str]) -> bool:
        return not (
            any(status.get(f) not in OCCURRED for f, ty, _ in self.parents[bid] if ty == "requires")
            or any(status.get(f) not in OCCURRED for f, ty in self.after[bid] if ty == "requires")
        )

    def _ready(self, x: Mapping[str, Any], status: Mapping[str, str], state: Mapping[str, Any]) -> bool:
        if not self.requires_met(x["id"], status):
            return False
        return self.holds(x["preconditions"], state)

    def _step1(
        self,
        kind: str,
        x: Any,
        t: int,
        over: Mapping[str, Override],
        late: set[str],
        state: State,
        where: dict[str, Any],
        status: dict[str, str],
        times: dict[str, int],
        variant: dict[str, str] | None = None,
    ) -> None:
        if kind == "event":
            self.apply(x["effects"], state, where)
            return
        if kind == "deadline":
            pre = dict(state)
            for r in self.world["clock"].get("onDeadline", []):
                if self.holds(r["if"], pre):
                    self.apply(r["then"], state, where)
            return
        bid = x["id"]
        o = over.get(bid, {})
        if bid in late:
            status[bid] = "late"
        elif o.get("to") == "prevented":
            status[bid] = "prevented"
        elif not self.requires_met(bid, status):
            status[bid] = "blocked"
        elif not self.holds(x["preconditions"], state):
            status[bid] = "precondition-failed"
        else:
            self._occur(x, t, o, state, where, status, times, variant)

    def _occur(
        self,
        x: Mapping[str, Any],
        t: int,
        o: Mapping[str, Any],
        state: State,
        where: dict[str, Any],
        status: dict[str, str],
        times: dict[str, int],
        variant: dict[str, str] | None = None,
    ) -> None:
        bid = x["id"]
        times[bid] = t
        for p in x["participants"]:
            where[p] = x["place"]
        if o.get("to") == "altered":  # 玩家的事件事先改了这个节拍
            status[bid] = "altered"
            self.apply(o["outcomes"], state, where)
            return
        v = self.variant_of(x, state)
        if v is not None:  # contracts 1.4：到点时按本局状态换一种演法
            status[bid] = "altered"
            if variant is not None:
                variant[bid] = v["id"]
            self.apply(v["outcomes"], state, where)
            return
        status[bid] = "happened"
        self.apply(x["outcomes"], state, where)

    def variant_of(self, x: Mapping[str, Any], state: Mapping[str, Any]) -> Mapping[str, Any] | None:
        return next((v for v in x.get("variants", []) if self.holds(v["when"], state)), None)
