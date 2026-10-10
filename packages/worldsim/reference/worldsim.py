"""世界推演：contracts 2.4.1（节拍是世界的默认时间表）和 2.5.1（时间传播）的参考实现。

1.4：节拍的 variants（到点时按状态换一种演法，记为 altered）；requires 的「发生了」包括 altered；
到达下限 clock.deadline.earliestArrival（S-066）：帮他快超过下限的部分作废，拖慢照算全额；arrival_delta 给按钮的实际分钟数和做了以后还赶不赶得上。

2026-10-10（为 W-1 的增量接口对齐契约，24 次推演和全部生成物不变）：同一时刻先节拍、再期限、最后事件；
排定时间到了而前提不成立的节拍，到 window.latest 为止每一步之后再查（contracts 2.4.1 第 3 条），以前只查一次。

1.6（C-16）：StateVar.valueRequires，变量改成某个值时要满足的条件（value_requires()）。推演照样应用事件，
违反的记进结果的 violations，build_world 拿它查情景，S-2 的参考判法拿它报 R2。

2026-10-10（1.6 写清，后端评审 W-1）：同一个节拍的几次改动怎么合（merge_change()）。以前同方向分钟相加、换方向整条替换，
先拖慢 30 再帮快 10 变成帮快 10。24 次推演和全部生成物不变（情景里每个节拍只有一条改动）。

build_world.py（改道情景）和 check_evals.py（评测检查点）共用这一份，免得两边规则不一致。只用标准库。
"""
from collections import defaultdict

OCCURRED = ("happened", "altered")               # contracts 2.5（1.4 写清）：requires 的「发生了」包括 altered
OPS = {"==": lambda x, y: x == y, "!=": lambda x, y: x != y, ">=": lambda x, y: x >= y,
       "<=": lambda x, y: x <= y, "in": lambda x, y: x in y}
SIGN = {"delayed": 1, "hastened": -1}             # 推迟的分钟为正，提前为负


def change_conflict(old, new):
    """contracts 第 3 节（1.6 写清）：本局对一个还没结果的节拍只有一种改动。old 是已登记的改动（没有是 None），
    new 是新的 {to, minutes?, outcomes?, note?}。能合返回 None，不能合返回原因（自检报 bad-state）。"""
    if old is None or (new["to"] == "prevented" and old["to"] != "prevented"):
        return None
    if old["to"] == "prevented":
        return "已经登记了 prevented，不能再改"
    if old["to"] in SIGN and new["to"] in SIGN:
        return None
    return f"已经登记了 {old['to']}，不能再登记 {new['to']}（altered 不和推迟、提前混用，也只登记一次）"


def merge_change(over, e):
    """把一条 {op: beat} 改动合进 over（节拍 ID → 改动，就地改）：
    - delayed、hastened 按带符号的分钟相加，净值 0 就去掉这条改动；
    - prevented 顶掉之前的推迟、提前、改写；
    - 其他组合（已登记 prevented 之后再改；altered 和推迟、提前混用；第二次 altered）抛 ValueError。"""
    bid = e["beat"]
    new = {k: v for k, v in e.items() if k not in ("op", "beat")}
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


class Sim:
    def __init__(self, world):
        self.world = world
        self.svars = {v["id"]: v for v in world["stateVars"]}
        self.beats = {b["id"]: b for b in world["beats"]}
        self.chars = {c["id"]: c for c in world["characters"]}
        self.endings = sorted(world.get("endings", {}).get("world", []), key=lambda x: x["order"])
        self.parents = defaultdict(list)          # to -> [(from, type, minutes)]；只含传递时间偏移的边
        self.after = defaultdict(list)            # to -> [(from, type)]：timeLink = "order" 的边，只要求不早于 from（contracts 2.5.1，1.1）
        self.timed = set()                        # 有 delays / hastens 出边的节拍：它发不发生决定后面的时间
        for e in world["causal"]:
            if e["from"] in self.beats and e["to"] in self.beats:
                if e.get("timeLink") == "order":
                    self.after[e["to"]].append((e["from"], e["type"]))
                else:
                    self.parents[e["to"]].append((e["from"], e["type"], e.get("minutes", 0)))
                if e["type"] in ("delays", "hastens"):
                    self.timed.add(e["from"])

    def holds(self, conds, state):
        return all(OPS[c["op"]](state.get(c["var"]), c["value"]) for c in conds)

    def apply(self, effs, state, where=None):
        for e in effs:
            if e["op"] == "set":
                state[e["var"]] = e["value"]
            elif e["op"] == "inc":
                v = self.svars[e["var"]]
                state[e["var"]] = max(v.get("min", -10**9), min(v.get("max", 10**9), state[e["var"]] + e["by"]))
            elif e["op"] == "relocate" and where is not None:
                where[e["character"]] = e["place"]
            elif e["op"] == "hold":                    # contracts 1.3：物品换手，持有者记在 state[物品 ID]
                state[e["item"]] = e["to"]

    def value_requires(self, effs, state, origin=None):
        """contracts 2.6（1.6，C-16）StateVar.valueRequires：事件把变量改成某个值时，这个值的 when 要成立。
        ① 只有 origin == "schedule"（到点的节拍和期限）不判，节拍的结果由节拍前提管；导演事件的 actor 也是 system，
        origin 是 director，照样判（不能按 actor 跳过）；② 值真的变了才判，设成现在的值不判；
        ③ 按这个 effect 之前的状态判，同一事件里前面的 effect 已经生效（先升信任再设 wavering 能过，反过来不过）；
        ④ when 和节拍前提用同一个 holds()；⑤ 设好以后条件不再成立不追究。
        不改 state。返回违反的条目 [{var, value, when, note}]，叙事者第 3 步报 R2，reason 带变量、value 和 note。"""
        if origin == "schedule":
            return []
        out, cur = [], dict(state)
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

    def schedule(self, over, _floor=True):
        """2.5.1：先排时间（与状态无关）。返回 (shift, late)。

        （1.5，S-066）clock.deadline.earliestArrival：梅洛斯到 watchBeat 的时刻每一步都不早于下限。
        把改动（over）按节拍顺序（= 玩家做的先后）一个个加上去，每加一个就看 watchBeat 的偏移变了多少（delta），
        累计 a = max(下限 − canonical, a + delta)。所以：到了下限再帮他快 = 0（作废）；拖慢照算全额（S-066 ②）；
        拖慢之后离开了下限，再帮他快又有用，最多回到下限（ux-design 4.3）。
        """
        shift, late = {}, set()
        dl = self.world["clock"]["deadline"]
        wb, floor = dl.get("watchBeat"), dl.get("earliestArrival")
        use_floor = _floor and wb in self.beats and floor is not None
        for b in sorted(self.world["beats"], key=lambda b: (b["window"]["canonical"], b["order"])):
            bid, w = b["id"], b["window"]
            ps = self.parents[bid]
            if any(f in late for f, ty, _ in ps if ty in ("enables", "requires")) or any(f in late for f, _ in self.after[bid]):
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
            t = max([w["earliest"], w["canonical"] + sh] +
                    [self.beats[f]["window"]["canonical"] + shift.get(f, 0) for f, _ in self.after[bid]])
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

    def run(self, sc, until=None, start_place="place.syracuse-square", player_items=()):
        """按时间顺序应用效果、检查前提。

        until：None = 推演到底并分类世界结局；("beat", id) = 停在该节拍刚处理完；("t", n) = 停在时刻 n（含 n 时刻的期限）。
        停在中途时可以用 resume() 追加效果（评测 setup.events）后接着推演。
        返回 dict：outcome（只有推演到底才有）、status、times、state、where（人物所在地）、t、stopped、auto。
        player_items：身份开局带的物品（Role.items，contracts 1.3）；state[物品 ID] = 现在谁拿着。

        contracts 2.5.1：有 delays / hastens 出边的节拍，在排定时间那一刻判前提，不成立就当场记为 prevented
        （不等到 window.latest），它的分钟照样退还。所以先整局推演，把这类节拍补进 over，直到不再变化（auto）。
        """
        over = dict(sc.get("beats", {}))
        auto = set()
        for _ in range(len(self.timed) + 1):
            full = self._run(sc, over, None, start_place, player_items)
            new = {b for b, st in full["status"].items() if st == "precondition-failed" and b in self.timed and b not in over}
            if not new:
                break
            for b in new:
                over[b] = {"to": "prevented"}
            auto |= new
        res = full if until is None else self._run(sc, over, until, start_place, player_items)
        res["auto"], res["over"] = auto, over
        return res

    def _run(self, sc, over, until, start_place, player_items=()):
        shift, late = self.schedule(over)
        state = {v["id"]: v["default"] for v in self.world["stateVars"]}
        state["var.player.location"] = start_place
        for c, x in self.chars.items():                # contracts 1.3：WorldState.holdings 的初值
            for it in x.get("items", []):
                state[it] = c
        for it in player_items:
            state[it] = "player"
        where = {c: x.get("initialPlace") for c, x in self.chars.items()}
        status, times = {}, {}
        queue = [(b["window"]["canonical"] + shift.get(b["id"], 0), 0, b["order"], "beat", b) for b in self.world["beats"]]
        # 同一时刻：先节拍，再期限，最后事件。和叙事者逐事件提交一致：时钟走到 t 时先结算到点（≤ t）的节拍和期限，
        # 玩家在 t 做的事排在它们之后；run(until=("t", n)) 加 resume() 也是这个顺序（2026-10-10，W-1 增量接口）。
        queue += [(ev["t"], 2, 0, "event", ev) for ev in sc.get("events", [])]
        queue.append((self.world["clock"]["deadline"]["t"], 1, 0, "deadline", None))
        queue.sort(key=lambda q: q[:3])
        variant = {}                                   # contracts 1.4：节拍 ID → 本局用的变体 ID
        res = {"status": status, "times": times, "state": state, "where": where, "outcome": None,
               "t": None, "stopped": until is None, "late": late, "shift": shift, "variant": variant,
               "violations": []}                 # 1.6：违反 valueRequires 的事件 [(t, 违反的条目)]
        for i, (t, _, _, kind, x) in enumerate(queue):
            if until and until[0] == "t" and t > until[1]:
                res["t"], res["stopped"], res["rest"] = until[1], True, queue[i:]
                return res
            if kind == "event":
                res["violations"] += [(t, v) for v in self.value_requires(x["effects"], state)]
            self._step(kind, x, t, over, late, state, where, status, times, variant)
            if until and until[0] == "beat" and kind == "beat" and x["id"] == until[1]:
                res["t"], res["stopped"], res["rest"] = t, status[x["id"]] in OCCURRED, queue[i + 1:]
                return res
        if until:
            res["t"] = until[1] if until[0] == "t" else None
            res["stopped"], res["rest"] = until[0] == "t", []
            return res
        res["outcome"] = self.classify(state)
        return res

    def resume(self, res, sc, extra_effects=(), until_t=None):
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

    def arrival_delta(self, sc, effects, t, start_place="place.syracuse-square", player_items=()):
        """S-066 ①：本局到此为止是情景 sc（beats = 已有的推迟/提前/阻止，events = 已提交的效果），
        在时刻 t 再提交 effects，梅洛斯到刑场（watchBeat）会晚（+）或早（−）几分钟。
        返回 {"minutes": 分钟数（含到达下限，已到下限时「帮他快」是 0）, "inTime": 做了以后还赶不赶得上}。
        分钟数用去掉 window.latest 的副本算，所以「拖了就来不及」时也有数。
        effects 里的节拍改动按 merge_change() 合进 sc 已有的改动；合不了（自检的 bad-state）抛 ValueError。"""
        wb = self.world["clock"]["deadline"].get("watchBeat")
        beats = {b: dict(o) for b, o in sc.get("beats", {}).items()}
        for e in effects:
            if e.get("op") == "beat":
                merge_change(beats, e)
        rest = [x for x in effects if x.get("op") != "beat"]
        after = {**sc, "beats": beats, "events": list(sc.get("events", [])) + ([{"t": t, "effects": rest}] if rest else [])}
        if not hasattr(self, "_loose"):
            loose = {**self.world, "beats": [{**b, "window": {**b["window"], "latest": 10 ** 9}} for b in self.world["beats"]]}
            self._loose = Sim(loose)
        kw = dict(start_place=start_place, player_items=player_items)
        a, b = self._loose.run(sc, **kw), self._loose.run(after, **kw)
        real = self.run(after, **kw)
        return {"minutes": b["shift"].get(wb, 0) - a["shift"].get(wb, 0),
                "inTime": real["status"].get(wb) in OCCURRED}

    def classify(self, state):
        return next((en["id"] for en in self.endings if self.holds(en["when"], state)), None)

    def _step(self, kind, x, t, over, late, state, where, status, times, variant=None):
        self._step1(kind, x, t, over, late, state, where, status, times, variant)
        self._recheck(t, over, state, where, status, times, variant)

    def _waiting(self, bid, status, t):
        """contracts 2.4.1 第 3 条：排定时间到了而前提不成立（或 requires 的前一节拍还没发生），不算结果，
        到 window.latest 为止每次时钟前进都再查。有 delays / hastens 出边的节拍除外：当场 prevented（run() 的 auto）。"""
        return (status.get(bid) in ("precondition-failed", "blocked") and bid not in self.timed
                and t <= self.beats[bid]["window"]["latest"])

    def _recheck(self, t, over, state, where, status, times, variant):
        """每一步之后，按排定顺序再查还在等的节拍；成立的在此刻 t 发生。一个发生了可能让别的成立，所以查到不再变化。"""
        changed = True
        while changed:
            changed = False
            for bid in sorted((b for b in status if self._waiting(b, status, t)), key=lambda b: self.beats[b]["order"]):
                x = self.beats[bid]
                if self._ready(x, status, state):
                    self._occur(x, t, over.get(bid, {}), state, where, status, times, variant)
                    changed = True

    def _ready(self, x, status, state):
        bid = x["id"]
        if any(status.get(f) not in OCCURRED for f, ty, _ in self.parents[bid] if ty == "requires") or \
                any(status.get(f) not in OCCURRED for f, ty in self.after[bid] if ty == "requires"):
            return False
        return self.holds(x["preconditions"], state)

    def _step1(self, kind, x, t, over, late, state, where, status, times, variant=None):
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
        elif any(status.get(f) not in OCCURRED for f, ty, _ in self.parents[bid] if ty == "requires") or \
                any(status.get(f) not in OCCURRED for f, ty in self.after[bid] if ty == "requires"):
            status[bid] = "blocked"
        elif not self.holds(x["preconditions"], state):
            status[bid] = "precondition-failed"
        else:
            self._occur(x, t, o, state, where, status, times, variant)

    def _occur(self, x, t, o, state, where, status, times, variant=None):
        bid = x["id"]
        times[bid] = t
        for p in x["participants"]:
            where[p] = x["place"]
        if o.get("to") == "altered":                   # 玩家的事件事先改了这个节拍
            status[bid] = "altered"
            self.apply(o["outcomes"], state, where)
            return
        v = next((v for v in x.get("variants", []) if self.holds(v["when"], state)), None)
        if v is not None:                              # contracts 1.4：到点时按本局状态换一种演法
            status[bid] = "altered"
            if variant is not None:
                variant[bid] = v["id"]
            self.apply(v["outcomes"], state, where)
            return
        status[bid] = "happened"
        self.apply(x["outcomes"], state, where)
