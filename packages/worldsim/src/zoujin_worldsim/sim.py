"""Whole-run simulation: the Sim of the reference implementation reference/worldsim.py ported verbatim (W-1), with
type annotations added and behaviour unchanged.

Only one thing changed: the opening state is no longer hard-coded to the square but read from the role
(Role.startPlace, Role.items, and per contract 3.1 var.act.current is set to Role.startAct; no condition uses it, so
simulation results are unchanged), so run() and arrival_delta() take role.
For where the rules come from, see the reference implementation's file header and docs/data/contracts.md 2.4.1, 2.5.1,
2.6 (value conditions in 1.6).

一括シミュレーション：参照実装 reference/worldsim.py の Sim をそのまま移植（W-1）し、型注釈を加えた。挙動は
変えていない。

変えたのは 1 か所だけ：オープニングの状態を広場に固定せず、ロールから読む（Role.startPlace、Role.items。さらに
契約 3.1 に従い var.act.current を Role.startAct にする。これを使う条件はなく、シミュレーション結果は変わらない）。
そのため run()、arrival_delta() には role を渡す。
ルールの由来は参照実装のファイル冒頭と docs/data/contracts.md 2.4.1、2.5.1、2.6（1.6 の値の条件）を参照。
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

# contracts 2.5 (clarified in 1.4): "happened" for requires includes altered
# contracts 2.5（1.4 で明記）：requires の「起きた」は altered を含む
OCCURRED = ("happened", "altered")
OPS: dict[str, Callable[[Any, Any], bool]] = {
    "==": lambda x, y: x == y,
    "!=": lambda x, y: x != y,
    ">=": lambda x, y: x >= y,
    "<=": lambda x, y: x <= y,
    "in": lambda x, y: x in y,
}
BIG = 10**9
SIGN = {"delayed": 1, "hastened": -1}  # Delays are positive minutes, hastening negative / 遅延は正、前倒しは負の分


def change_conflict(old: Override | None, new: Mapping[str, Any]) -> str | None:
    """contracts section 3 (clarified in 1.6): in one run, a beat without a result yet has only one kind of change.
    old is the registered change (None if none), new is the new {to, minutes?, outcomes?, note?}. Returns None if they
    can be merged, otherwise the reason (the self-check reports bad-state).

    contracts 第 3 節（1.6 で明記）：1 回のプレイで、まだ結果の出ていないビートへの変更は 1 種類だけ。old は登録済みの
    変更（なければ None）、new は新しい {to, minutes?, outcomes?, note?}。統合できれば None、できなければ理由を返す
    （セルフチェックは bad-state を報告する）。
    """
    if old is None or (new["to"] == "prevented" and old["to"] != "prevented"):
        return None
    if old["to"] == "prevented":
        return "prevented is already registered; it cannot be changed / すでに prevented が登録済みで、変更できない"
    if old["to"] in SIGN and new["to"] in SIGN:
        return None
    return (
        f"{old['to']} is already registered; cannot register {new['to']} as well (altered is not mixed with delays or"
        f" hastening, and is registered only once) / すでに {old['to']} が登録済みで、{new['to']} は登録できない"
        "（altered は遅延・前倒しと混ぜず、登録も 1 回だけ）"
    )


def merge_change(over: dict[str, Override], e: Effect) -> None:
    """Merges one {op: beat} change into over (beat ID → change, modified in place):
    - delayed and hastened add up as signed minutes; if the net is 0, the change is removed;
    - prevented replaces any earlier delay, hastening or rewrite;
    - any other combination (changing after prevented is registered; mixing altered with delays or hastening; a second
      altered) raises ValueError.

    {op: beat} の変更 1 件を over（ビート ID → 変更、その場で更新）に統合する：
    - delayed と hastened は符号付きの分数として足し合わせ、正味 0 ならその変更を取り除く；
    - prevented はそれまでの遅延、前倒し、書き換えを上書きする；
    - それ以外の組み合わせ（prevented 登録後の変更、altered と遅延・前倒しの混用、2 回目の altered）は ValueError を
      送出する。
    """
    bid = e["beat"]
    new: Override = {k: copy.deepcopy(v) for k, v in e.items() if k not in ("op", "beat")}
    old = over.get(bid)
    why = change_conflict(old, new)
    if why:
        raise ValueError(f"{bid}: {why}")
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
    raise KeyError(f"Role does not exist / ロールが存在しない: {role_id}")


class Sim:
    def __init__(self, world: World) -> None:
        self.world = world
        self.svars: dict[str, Mapping[str, Any]] = {v["id"]: v for v in world["stateVars"]}
        self.beats: dict[str, Mapping[str, Any]] = {b["id"]: b for b in world["beats"]}
        self.chars: dict[str, Mapping[str, Any]] = {c["id"]: c for c in world["characters"]}
        self.endings = sorted(world.get("endings", {}).get("world", []), key=lambda x: x["order"])
        # to -> [(from, type, minutes)]: only edges that pass on a time offset
        # to -> [(from, type, minutes)]：時間のずれを伝えるエッジだけ
        self.parents: defaultdict[str, list[tuple[str, str, int]]] = defaultdict(list)
        # to -> [(from, type)]: edges with timeLink = "order", which only require not being earlier than from
        # (contracts 2.5.1, 1.1)
        # to -> [(from, type)]：timeLink = "order" のエッジ。from より早くないことだけを求める（contracts 2.5.1、1.1）
        self.after: defaultdict[str, list[tuple[str, str]]] = defaultdict(list)
        # Beats with outgoing delays / hastens edges: whether they happen decides later times
        # delays / hastens の出エッジを持つビート：起きるかどうかで後の時刻が決まる
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
            # contracts 1.3: an item changes hands; the holder is recorded in state[item ID]
            # contracts 1.3：アイテムの持ち主が替わる。持ち主は state[アイテム ID] に記録
            elif e["op"] == "hold":
                state[e["item"]] = e["to"]

    def value_requires(
        self, effs: Iterable[Effect], state: Mapping[str, Any], origin: str | None = None
    ) -> list[dict[str, Any]]:
        """contracts 2.6 (1.6, C-16) StateVar.valueRequires: when an event changes a variable to some value, that
        value's when must hold.
        ① Only origin == "schedule" (due beats and deadlines) is not checked; director events also have actor system
        and are still checked, so skipping by actor is wrong; ② checked only when the value really changes; ③ checked
        against the state before this effect, with earlier effects in the same event already applied; ④ when and beat
        preconditions use the same holds(); ⑤ once set, a condition that stops holding later is not pursued.
        Does not change state. Returns the violated entries [{var, value, when, note}].

        contracts 2.6（1.6、C-16）StateVar.valueRequires：イベントが変数をある値に変えるとき、その値の when が
        成り立たなければならない。
        ① origin == "schedule"（期限に達したビートと期限）だけは判定しない。ディレクターイベントの actor も system
        だが、それでも判定する（actor でスキップしてはいけない）；② 値が実際に変わったときだけ判定する；③ この
        effect の前の状態で判定し、同じイベント内の前の effect はすでに反映済み；④ when とビートの前提条件は同じ
        holds() を使う；⑤ 設定後に条件が成り立たなくなっても追及しない。
        state は変えない。違反した項目 [{var, value, when, note}] を返す。
        """
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
        """2.5.1: schedule times first (independent of state). Returns (shift, late). For the arrival-floor algorithm,
        see the reference implementation.

        2.5.1：先に時刻を決める（状態とは無関係）。(shift, late) を返す。到着下限のアルゴリズムは参照実装を参照。
        """
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
        """Applies effects and checks preconditions in time order; the return value is the same as the reference
        implementation's run() (outcome, status, times, state, where, t, stopped, late, shift, variant, violations,
        auto, over, plus rest when stopped midway).
        role: role ID; the starting place, carried items and starting act are read from it (the reference
        implementation takes start_place, player_items).
        place: used when an eval case's setup.place gives a different starting place; omitted = the role's
        startPlace.

        contracts 2.5.1: a beat with outgoing delays / hastens edges has its preconditions checked at its scheduled
        time; if they fail it is recorded as prevented on the spot, and its minutes are still refunded. So the whole
        run is simulated first and such beats are added to over until nothing changes (auto).

        時刻順に効果を適用して前提条件を確認する。戻り値は参照実装の run() と同じ（outcome、status、times、state、
        where、t、stopped、late、shift、variant、violations、auto、over。途中で止まった場合は rest も）。
        role：ロール ID。開始地点、所持品、開始の幕をここから読む（参照実装では start_place、player_items を渡す）。
        place：評価ケースの setup.place が別の開始地点を与えるときに使う。省略 = ロールの startPlace。

        contracts 2.5.1：delays / hastens の出エッジを持つビートは予定時刻の時点で前提条件を判定し、成り立たなければ
        その場で prevented と記録し、その分数はそのまま戻す。そのため先にプレイ全体をシミュレーションし、こうした
        ビートを over に加えて、変化がなくなるまで繰り返す（auto）。
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
        # Initial values set by the role (var.player.location, var.act.current)
        # ロールが決める初期値（var.player.location、var.act.current）
        state.update(start)
        for c, x in self.chars.items():  # contracts 1.3: initial WorldState.holdings / WorldState.holdings の初期値
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
        # At the same time: beats first, then the deadline, events last (2026-10-10, W-1 incremental interface)
        # 同時刻ではビート、期限、イベントの順（2026-10-10、W-1 の増分インターフェース）
        queue += [(ev["t"], 2, 0, "event", ev) for ev in sc.get("events", [])]
        queue.append((self.world["clock"]["deadline"]["t"], 1, 0, "deadline", None))
        queue.sort(key=lambda q: q[:3])
        # contracts 1.4: beat ID → variant ID used in this run / ビート ID → このプレイで使うバリアント ID
        variant: dict[str, str] = {}
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
            # 1.6: events violating valueRequires [(t, violated entry)] / valueRequires に違反したイベント
            "violations": [],
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
        """Continues from where run(until=…) stopped: apply extra_effects first, then simulate to until_t (None = to
        the end and classify the ending).
        Scheduled times stay as run() computed them (extra_effects no longer change the timetable).

        run(until=…) の停止点から続ける：先に extra_effects を適用し、until_t までシミュレーションする（None = 最後
        まで進めて結末を分類する）。
        予定時刻は run() が計算したものをそのまま使う（extra_effects は時刻表を変えない）。
        """
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
        """S-066 ①: given that this run so far is scenario sc, if effects are also submitted at time t, how many
        minutes later (+) or earlier (−) Melos reaches the execution ground (watchBeat).
        Returns {"minutes": minutes (including the arrival floor), "inTime": whether he still makes it after doing
        it}. Minutes are computed on a copy with window.latest removed.
        Beat changes in effects are merged into sc's existing changes with merge_change(); if they cannot be merged
        (the self-check's bad-state), raises ValueError.

        S-066 ①：このプレイがここまでシナリオ sc だったとして、時刻 t にさらに effects を提出すると、メロスが刑場
        （watchBeat）に何分遅れる（+）か早まる（−）か。
        {"minutes": 分数（到着下限込み）, "inTime": 実行後もまだ間に合うか} を返す。分数は window.latest を外した
        コピーで計算する。
        effects 内のビート変更は merge_change() で sc の既存の変更に統合する。統合できなければ（セルフチェックの
        bad-state）ValueError を送出する。
        """
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
        """contracts 2.4.1 item 3: when the scheduled time arrives but the preconditions fail (or the preceding
        requires beat has not happened yet), recheck on every clock advance until window.latest. Except beats with
        outgoing delays / hastens edges: those are prevented on the spot (run()'s auto).

        contracts 2.4.1 第 3 項：予定時刻になっても前提条件が成り立たない（または requires の前のビートがまだ起きて
        いない）場合、window.latest まで時刻が進むたびに再確認する。delays / hastens の出エッジを持つビートは例外で、
        その場で prevented になる（run() の auto）。
        """
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
        """After every step, recheck the beats still waiting in scheduled order; those that now hold happen at this
        time t. Repeat until nothing changes.

        各ステップの後、まだ待っているビートを予定順に再確認し、成り立ったものはこの時刻 t に起きる。変化が
        なくなるまで繰り返す。
        """
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
        if o.get("to") == "altered":  # A player's event changed this beat in advance / プレイヤーのイベントが事前に変更
            status[bid] = "altered"
            self.apply(o["outcomes"], state, where)
            return
        v = self.variant_of(x, state)
        # contracts 1.4: when due, play it a different way depending on this run's state
        # contracts 1.4：期限が来たら、このプレイの状態に応じて別の演じ方にする
        if v is not None:
            status[bid] = "altered"
            if variant is not None:
                variant[bid] = v["id"]
            self.apply(v["outcomes"], state, where)
            return
        status[bid] = "happened"
        self.apply(x["outcomes"], state, where)

    def variant_of(self, x: Mapping[str, Any], state: Mapping[str, Any]) -> Mapping[str, Any] | None:
        return next((v for v in x.get("variants", []) if self.holds(v["when"], state)), None)
