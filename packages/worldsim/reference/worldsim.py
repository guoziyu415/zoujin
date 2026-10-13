"""World simulation: the reference implementation of contracts 2.4.1 (beats are the world's default timetable) and
2.5.1 (time propagation).

1.4: beat variants (when due, play it a different way depending on state, recorded as altered); "happened" for
requires includes altered;
arrival floor clock.deadline.earliestArrival (S-066): helping him go faster beyond the floor is void, slowing him down
counts in full; arrival_delta gives a button's actual minutes and whether he still makes it after doing it.

2026-10-10 (aligning with the contract for W-1's incremental interface; the 24 simulations and all generated files
unchanged): at the same time, beats first, then the deadline, events last; a beat whose scheduled time has come but
whose preconditions fail is rechecked after every step until window.latest (contracts 2.4.1 item 3); previously it was
checked only once.

1.6 (C-16): StateVar.valueRequires, the conditions that must hold when a variable is changed to a given value
(value_requires()). The simulation still applies the events and records violations in the result's violations;
build_world uses it to check scenarios, and the S-2 reference judgement uses it to report R2.

2026-10-10 (clarified in 1.6, backend review of W-1): how several changes to the same beat merge (merge_change()).
Previously minutes in the same direction were added and a change of direction replaced the whole entry, so slowing by
30 and then helping by 10 became helping by 10. The 24 simulations and all generated files are unchanged (in the
scenarios each beat has only one change).

build_world.py (rerouting scenarios) and check_evals.py (eval checkpoints) share this one copy, so the two sides do not
diverge in their rules. Standard library only.

世界シミュレーション：contracts 2.4.1（ビートは世界の既定の時刻表）と 2.5.1（時間の伝播）の参照実装。

1.4：ビートの variants（期限が来たら状態に応じて別の演じ方をし、altered と記録する）。requires の「起きた」は
altered を含む。
到着下限 clock.deadline.earliestArrival（S-066）：下限を越えて彼を速める分は無効、遅らせる分は全額計上する。
arrival_delta はボタンの実際の分数と、実行後もまだ間に合うかを返す。

2026-10-10（W-1 の増分インターフェースのために契約に合わせた。24 回のシミュレーションとすべての生成物は不変）：
同時刻ではビート、期限、イベントの順。予定時刻が来ても前提条件が成り立たないビートは、window.latest まで各
ステップの後に再確認する（contracts 2.4.1 第 3 項）。以前は 1 回しか確認しなかった。

1.6（C-16）：StateVar.valueRequires、変数をある値に変えるときに満たすべき条件（value_requires()）。シミュレーションは
それでもイベントを適用し、違反は結果の violations に記録する。build_world はこれでシナリオを確認し、S-2 の参照判定は
これで R2 を報告する。

2026-10-10（1.6 で明記、W-1 のバックエンドレビュー）：同じビートへの複数の変更をどう統合するか（merge_change()）。
以前は同じ方向の分数を足し、方向が変わると丸ごと置き換えていたので、30 分遅らせてから 10 分速めると 10 分速める
だけになった。24 回のシミュレーションとすべての生成物は不変（シナリオでは各ビートの変更は 1 件だけ）。

build_world.py（分岐シナリオ）と check_evals.py（評価のチェックポイント）がこの 1 つを共用し、両者のルールが
食い違わないようにする。標準ライブラリのみ。
"""
from collections import defaultdict

# contracts 2.5 (clarified in 1.4): "happened" for requires includes altered
# contracts 2.5（1.4 で明記）：requires の「起きた」は altered を含む
OCCURRED = ("happened", "altered")
OPS = {"==": lambda x, y: x == y, "!=": lambda x, y: x != y, ">=": lambda x, y: x >= y,
       "<=": lambda x, y: x <= y, "in": lambda x, y: x in y}
SIGN = {"delayed": 1, "hastened": -1}             # Delays are positive minutes, hastening negative / 遅延は正、前倒しは負の分


def change_conflict(old, new):
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


def merge_change(over, e):
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
    new = {k: v for k, v in e.items() if k not in ("op", "beat")}
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


class Sim:
    def __init__(self, world):
        self.world = world
        self.svars = {v["id"]: v for v in world["stateVars"]}
        self.beats = {b["id"]: b for b in world["beats"]}
        self.chars = {c["id"]: c for c in world["characters"]}
        self.endings = sorted(world.get("endings", {}).get("world", []), key=lambda x: x["order"])
        # to -> [(from, type, minutes)]: only edges that pass on a time offset
        # to -> [(from, type, minutes)]：時間のずれを伝えるエッジだけ
        self.parents = defaultdict(list)
        # to -> [(from, type)]: edges with timeLink = "order", which only require not being earlier than from
        # (contracts 2.5.1, 1.1)
        # to -> [(from, type)]：timeLink = "order" のエッジ。from より早くないことだけを求める（contracts 2.5.1、1.1）
        self.after = defaultdict(list)
        # Beats with outgoing delays / hastens edges: whether they happen decides later times
        # delays / hastens の出エッジを持つビート：起きるかどうかで後の時刻が決まる
        self.timed = set()
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
            # contracts 1.3: an item changes hands; the holder is recorded in state[item ID]
            # contracts 1.3：アイテムの持ち主が替わる。持ち主は state[アイテム ID] に記録
            elif e["op"] == "hold":
                state[e["item"]] = e["to"]

    def value_requires(self, effs, state, origin=None):
        """contracts 2.6 (1.6, C-16) StateVar.valueRequires: when an event changes a variable to some value, that
        value's when must hold.
        ① Only origin == "schedule" (due beats and deadlines) is not checked; a beat's outcomes are governed by the
        beat's preconditions. Director events also have actor system but origin director, and are still checked (do
        not skip by actor); ② checked only when the value really changes; setting it to its current value is not
        checked; ③ checked against the state before this effect, with earlier effects in the same event already
        applied (raising trust first and then setting wavering passes; the reverse does not); ④ when and beat
        preconditions use the same holds(); ⑤ once set, a condition that stops holding later is not pursued.
        Does not change state. Returns the violated entries [{var, value, when, note}]; the narrator's step 3 reports
        R2, with the variable, value and note in reason.

        contracts 2.6（1.6、C-16）StateVar.valueRequires：イベントが変数をある値に変えるとき、その値の when が
        成り立たなければならない。
        ① origin == "schedule"（期限に達したビートと期限）だけは判定せず、ビートの結果はビートの前提条件が管理する。
        ディレクターイベントの actor も system だが origin は director で、それでも判定する（actor でスキップしない）；
        ② 値が実際に変わったときだけ判定し、今の値に設定するのは判定しない；③ この effect の前の状態で判定し、同じ
        イベント内の前の effect はすでに反映済み（先に信頼を上げてから wavering にすれば通り、逆は通らない）；
        ④ when とビートの前提条件は同じ holds() を使う；⑤ 設定後に条件が成り立たなくなっても追及しない。
        state は変えない。違反した項目 [{var, value, when, note}] を返し、ナレーターの第 3 段階が R2 を報告する。
        reason には変数、value、note を入れる。
        """
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
        """2.5.1: schedule times first (independent of state). Returns (shift, late).

        (1.5, S-066) clock.deadline.earliestArrival: the time Melos reaches watchBeat is never earlier than the floor
        at any step. Add the changes (over) one by one in beat order (= the order the player made them), and after each
        one see how much watchBeat's offset changed (delta), accumulating a = max(floor − canonical, a + delta). So:
        helping him go faster once at the floor = 0 (void); slowing him counts in full (S-066 ②); after slowing him
        moves him off the floor, helping him go faster works again, at most back to the floor (ux-design 4.3).

        2.5.1：先に時刻を決める（状態とは無関係）。(shift, late) を返す。

        （1.5、S-066）clock.deadline.earliestArrival：メロスが watchBeat に着く時刻は、どのステップでも下限より早く
        ならない。変更（over）をビート順（= プレイヤーが行った順）に 1 件ずつ加え、加えるたびに watchBeat のずれが
        どれだけ変わったか（delta）を見て、a = max(下限 − canonical, a + delta) を累積する。したがって：下限に達して
        からさらに速めても 0（無効）；遅らせる分は全額計上（S-066 ②）；遅らせて下限から離れた後なら、速めるのは
        また効き、最大で下限まで戻る（ux-design 4.3）。
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
        """Applies effects and checks preconditions in time order.

        until: None = simulate to the end and classify the world ending; ("beat", id) = stop right after that beat is
        processed; ("t", n) = stop at time n (including the deadline at time n).
        When stopped midway, resume() can add effects (eval setup.events) and continue the simulation.
        Returns a dict: outcome (only when simulated to the end), status, times, state, where (characters' locations),
        t, stopped, auto.
        player_items: items the role starts with (Role.items, contracts 1.3); state[item ID] = who holds it now.

        contracts 2.5.1: a beat with outgoing delays / hastens edges has its preconditions checked at its scheduled
        time; if they fail it is recorded as prevented on the spot (without waiting for window.latest), and its
        minutes are still refunded. So the whole run is simulated first and such beats are added to over until
        nothing changes (auto).

        時刻順に効果を適用して前提条件を確認する。

        until：None = 最後までシミュレーションして世界の結末を分類する；("beat", id) = そのビートの処理直後で止まる；
        ("t", n) = 時刻 n で止まる（時刻 n の期限を含む）。
        途中で止まったら resume() で効果（評価の setup.events）を追加してシミュレーションを続けられる。
        dict を返す：outcome（最後までシミュレーションしたときだけ）、status、times、state、where（登場人物の
        所在地）、t、stopped、auto。
        player_items：ロールが最初に持っているアイテム（Role.items、contracts 1.3）。state[アイテム ID] = 今誰が
        持っているか。

        contracts 2.5.1：delays / hastens の出エッジを持つビートは予定時刻の時点で前提条件を判定し、成り立たなければ
        その場で prevented と記録し（window.latest まで待たない）、その分数はそのまま戻す。そのため先にプレイ全体を
        シミュレーションし、こうしたビートを over に加えて、変化がなくなるまで繰り返す（auto）。
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
        for c, x in self.chars.items():                # contracts 1.3: initial WorldState.holdings / 初期値
            for it in x.get("items", []):
                state[it] = c
        for it in player_items:
            state[it] = "player"
        where = {c: x.get("initialPlace") for c, x in self.chars.items()}
        status, times = {}, {}
        queue = [(b["window"]["canonical"] + shift.get(b["id"], 0), 0, b["order"], "beat", b) for b in self.world["beats"]]
        # At the same time: beats first, then the deadline, events last. This matches the narrator's event-by-event
        # commits: when the clock reaches t, the due (≤ t) beats and deadline are settled first, and what the player
        # does at t comes after them; run(until=("t", n)) plus resume() uses the same order (2026-10-10, W-1
        # incremental interface).
        # 同時刻ではビート、期限、イベントの順。ナレーターのイベントごとのコミットと一致させる：時刻が t に達したら
        # 期限に達した（≤ t）ビートと期限を先に精算し、プレイヤーが t に行ったことはその後に並ぶ。
        # run(until=("t", n)) と resume() も同じ順序（2026-10-10、W-1 の増分インターフェース）。
        queue += [(ev["t"], 2, 0, "event", ev) for ev in sc.get("events", [])]
        queue.append((self.world["clock"]["deadline"]["t"], 1, 0, "deadline", None))
        queue.sort(key=lambda q: q[:3])
        variant = {}                                   # contracts 1.4: beat ID → variant ID / ビート ID → バリアント ID
        res = {"status": status, "times": times, "state": state, "where": where, "outcome": None,
               "t": None, "stopped": until is None, "late": late, "shift": shift, "variant": variant,
               "violations": []}                 # 1.6: events violating valueRequires [(t, entry)] / valueRequires 違反
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

    def arrival_delta(self, sc, effects, t, start_place="place.syracuse-square", player_items=()):
        """S-066 ①: given that this run so far is scenario sc (beats = existing delays/hastening/preventions,
        events = effects already submitted), if effects are also submitted at time t, how many minutes later (+) or
        earlier (−) Melos reaches the execution ground (watchBeat).
        Returns {"minutes": minutes (including the arrival floor; "helping him go faster" is 0 once at the floor),
        "inTime": whether he still makes it after doing it}.
        Minutes are computed on a copy with window.latest removed, so there is a number even when "delaying him makes
        him too late".
        Beat changes in effects are merged into sc's existing changes with merge_change(); if they cannot be merged
        (the self-check's bad-state), raises ValueError.

        S-066 ①：このプレイがここまでシナリオ sc（beats = 既存の遅延/前倒し/阻止、events = 提出済みの効果）だった
        として、時刻 t にさらに effects を提出すると、メロスが刑場（watchBeat）に何分遅れる（+）か早まる（−）か。
        {"minutes": 分数（到着下限込み。下限に達していれば「速める」は 0）, "inTime": 実行後もまだ間に合うか} を
        返す。
        分数は window.latest を外したコピーで計算するので、「遅らせたら間に合わない」場合も数値が出る。
        effects 内のビート変更は merge_change() で sc の既存の変更に統合する。統合できなければ（セルフチェックの
        bad-state）ValueError を送出する。
        """
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
        """contracts 2.4.1 item 3: when the scheduled time arrives but the preconditions fail (or the preceding
        requires beat has not happened yet), it is not a result yet; recheck on every clock advance until
        window.latest. Except beats with outgoing delays / hastens edges: those are prevented on the spot (run()'s
        auto).

        contracts 2.4.1 第 3 項：予定時刻になっても前提条件が成り立たない（または requires の前のビートがまだ起きて
        いない）場合は結果とみなさず、window.latest まで時刻が進むたびに再確認する。delays / hastens の出エッジを
        持つビートは例外で、その場で prevented になる（run() の auto）。
        """
        return (status.get(bid) in ("precondition-failed", "blocked") and bid not in self.timed
                and t <= self.beats[bid]["window"]["latest"])

    def _recheck(self, t, over, state, where, status, times, variant):
        """After every step, recheck the beats still waiting in scheduled order; those that now hold happen at this
        time t. One happening may make another hold, so repeat until nothing changes.

        各ステップの後、まだ待っているビートを予定順に再確認し、成り立ったものはこの時刻 t に起きる。1 つが起きると
        別のものが成り立つことがあるので、変化がなくなるまで繰り返す。
        """
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
        if o.get("to") == "altered":                   # A player's event changed this beat in advance / 事前に変更済み
            status[bid] = "altered"
            self.apply(o["outcomes"], state, where)
            return
        v = next((v for v in x.get("variants", []) if self.holds(v["when"], state)), None)
        if v is not None:                              # contracts 1.4: play it differently per state / 状態で演じ方を変える
            status[bid] = "altered"
            if variant is not None:
                variant[bid] = v["id"]
            self.apply(v["outcomes"], state, where)
            return
        status[bid] = "happened"
        self.apply(x["outcomes"], state, where)
