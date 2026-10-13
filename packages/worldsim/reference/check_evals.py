#!/usr/bin/env python3
"""Self-check of eval cases (format in data/evals/README.md).

Usage:
  python3 -I check_evals.py --world world.json --scenarios scenarios.json --cases evals/seeds --personas personas.json

Calls no model; only checks that the cases themselves are written correctly:
1. Format: one JSON per line; ids are unique and match the suite of the file name; fields, steps, check types and
   parameters are all known.
2. References: roles, characters, places, facts, beats, state variables, world endings, scenarios and personas all
   exist; values match their types.
3. Starting point: simulate the scenario to the checkpoint (sharing worldsim.py with build_world.py). The checkpoint's
   beat really happens in that scenario; the role has started by then; the player's location is one the role can
   enter (or is arranged by setup.events); the character being talked to is next to the player at that moment.
4. Preconditions of anti-spoiler cases: the character asked really does not know the fact yet at the checkpoint; the
   player's question does not state the spoiler terms outright.
5. Cases whose results can be computed from the time rules alone (only setup.scenario, or checkpoint + setup.events +
   advance) are simulated right away to confirm that the expected ending, beats and state variables hold.
Standard library only.

評価ケースのセルフチェック（形式は data/evals/README.md）。

使い方：
  python3 -I check_evals.py --world world.json --scenarios scenarios.json --cases evals/seeds --personas personas.json

モデルは一切呼ばず、ケース自体が正しく書かれているかだけを確認する：
1. 形式：1 行に JSON 1 つ。id は一意で、ファイル名のスイートと一致する。フィールド、ステップ、チェックの種類と
   パラメータがすべて既知のもの。
2. 参照：ロール、登場人物、場所、事実、ビート、状態変数、世界の結末、シナリオ、ペルソナがすべて存在し、値が型に合う。
3. 起点：シナリオをチェックポイントまでシミュレーションする（build_world.py と worldsim.py を共用）。チェックポイントの
   ビートがそのシナリオで実際に起きる。その時点でロールがすでに開始している。プレイヤーのいる場所はロールが入れる
   場所（または setup.events で配置）。話しかける相手はその時点でプレイヤーのそばにいる。
4. ネタバレ防止ケースの前提：問われる登場人物はチェックポイントで本当にまだその事実を知らない。プレイヤーの問いに
   ネタバレ語をそのまま含めない。
5. 時間ルールだけで結果を計算できるケース（setup.scenario だけ、またはチェックポイント + setup.events + advance）は
   その場でシミュレーションし、期待する結末、ビート、状態変数が成り立つことを確認する。
標準ライブラリのみ。
"""
import argparse
import json
import re
import sys
from pathlib import Path

from zoujin_worldsim import Sim  # Simulation rules shared with build_world.py (W-1 package) / build_world.py と共有

CHECK_STATUS = {"passed", "rewritten", "downgraded", "rejected"}
RULES = {"R1-anchor", "R2-precondition", "R3-time", "R4-knowledge", "R5-persona", "R6-safety", "R7-capability"}
EVENT_TYPES = {"say", "action", "move", "beat", "learn", "act-transition", "correction", "ending", "forget"}
EVENT_ORIGINS = {"turn", "action", "schedule", "plan", "director", "act", "memory"}      # contracts 3 (1.1)
PROMISE_STATUS = {"open", "kept", "broken", "voided"}
BEAT_STATUS = {"pending", "happened", "prevented", "delayed", "hastened", "altered"}
MEMORY_KINDS = {"promise", "help", "harm", "shared-moment", "claim", "impression"}
# Action list: UX v1.0 18.2 (target kinds), plus api-contract's move (walking between places)
# アクション一覧：UX v1.0 18.2（target の種類）、加えて api-contract の move（場所間の移動）
ACT_KINDS = {"examine": "any", "give": "char", "follow": "char", "block": "char", "help": "char", "wait": "none",
             "go": "place", "shortcut": "place?", "run-together": "char", "hasten": "any?", "move": "place"}
TABLES = {"playthroughs", "events", "utterances", "memory_items", "world_state", "endings",
          "playthrough_metrics", "turns", "briefs"}
REPLY_CHECKS = {"not_mention_fact", "no_terms", "terms_any", "japanese"}       # Check a step's reply / ある段の返答を確認
E7_CHECKS = {"replay_equal", "t_monotonic", "outcome_consistent", "epilogue_cites_valid"}
SIM_CHECKS = {"outcome", "beat", "var"}                                         # Computable by simulation / シミュレーションで計算可能
ENDING_CHECKS = {"no_verbatim_quotes", "director_not_sole_cause"}               # S-046、S-045
CHECK_TYPES = REPLY_CHECKS | E7_CHECKS | SIM_CHECKS | ENDING_CHECKS | {
    "world_unchanged", "event", "no_event", "clock_advanced", "memory", "trust", "utterance_cleared",
    "event_exists", "db_absent", "no_pii", "followup_questions", "schedule_shift", "safety_card", "promise",
    "act_plan"}                                                                  # contracts 1.2: plan said at end of act / 幕末に話すプラン
SETUP_KEYS = {"role", "checkpoint", "place", "events", "budgetTier", "scenario", "persona", "seed"}
STEP_KEYS = {"to", "act", "deleteMemory", "retract", "deletePlaythrough", "newPlaythrough", "advance", "silence",
             "propose", "choose"}


class Checker:
    def __init__(self, world, scenarios, personas):
        self.sim = Sim(world)
        self.scenarios = {"sc.canon": {"id": "sc.canon"}, **{s["id"]: s for s in scenarios}}
        self.personas = {p["id"]: p for p in personas}
        self.chars = {c["id"]: c for c in world["characters"]}
        self.places = {p["id"] for p in world["places"]}
        self.objects = {o["id"] for o in world.get("objects", [])}  # (1.7) examinables, targets of examine / 調べられる物
        self.items = {x["id"]: x for x in world.get("items", [])}
        self.pacing = world.get("pacing", {})
        self.scene_of = {p["id"]: p.get("sceneRef") for p in world["places"]}
        # When the last act starts (talking takes 15 minutes there) / 最後の幕の開始時刻（そこでは会話が 15 分）
        self.act4_t = max(world["acts"], key=lambda a: a["order"])["start"]["t"]
        self.templates = {x["id"] for c in world["characters"] for x in c.get("promiseTemplates", [])}
        self.facts = {f["id"]: f for f in world["facts"]}
        self.roles = {r["id"]: r for r in world["roles"]}
        self.acts = {a["id"]: a for a in world["acts"]}
        # End-of-act beat → act / 幕を閉じるビート → 幕
        self.act_end = {b: a for a in world["acts"] if a["exits"] for b in a["end"]["onBeats"]}
        self.endings = {e["id"] for e in self.sim.endings}
        self.errors, self.warnings = [], []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    # ---------- Values and effects / 値と効果 ----------
    def check_value(self, var, value, where):
        v = self.sim.svars.get(var)
        if not v:
            return self.err(f"{where}: state variable does not exist / 状態変数が存在しない: {var}")
        ty = v["type"]
        if ty == "bool" and not isinstance(value, bool):
            self.err(f"{where}: {var} is bool, got / {var} は bool だが次が与えられた: {value!r}")
        elif ty == "int" and (not isinstance(value, int) or isinstance(value, bool)):
            self.err(f"{where}: {var} is int, got / {var} は int だが次が与えられた: {value!r}")
        elif ty == "enum" and value not in v["values"]:
            self.err(f"{where}: {var} has no value {value!r} (options {v['values']}) / {var} に値 {value!r} はない（選択肢 {v['values']}）")
        elif ty == "place" and value not in self.places:
            self.err(f"{where}: {var}: place does not exist / 場所が存在しない: {value!r}")

    def check_effects(self, effs, where, partial=False):
        """partial=True: used in the match of event / no_event, where only the fields to match are written.

        partial=True：event / no_event の match で使い、照合したいフィールドだけを書く。
        """
        if not isinstance(effs, list):
            return self.err(f"{where}: effects must be a list / effects はリストでなければならない")
        for e in effs:
            op = e.get("op")
            if op == "set":
                if "var" not in e:
                    if not partial:
                        self.err(f"{where}: set is missing var / set に var がない")
                elif "value" in e:
                    self.check_value(e["var"], e["value"], where)
                elif e["var"] not in self.sim.svars:
                    self.err(f"{where}: state variable does not exist / 状態変数が存在しない: {e['var']}")
                elif not partial:
                    self.err(f"{where}: set is missing value / set に value がない")
            elif op == "inc":
                v = self.sim.svars.get(e.get("var"))
                if not v or v["type"] != "int":
                    self.err(f"{where}: inc's variable is not int / inc の変数が int ではない: {e.get('var')}")
            elif op == "relocate":
                if e.get("character") not in self.chars:
                    self.err(f"{where}: relocate's character does not exist / relocate の登場人物が存在しない: {e.get('character')}")
                if ("place" in e or not partial) and e.get("place") not in self.places:
                    self.err(f"{where}: relocate's place does not exist / relocate の場所が存在しない: {e.get('place')}")
            elif op == "beat":
                if e.get("beat") not in self.sim.beats:
                    self.err(f"{where}: beat does not exist / ビートが存在しない: {e.get('beat')}")
                if "to" in e and e["to"] not in BEAT_STATUS - {"pending"}:
                    self.err(f"{where}: unrecognized beat.to / 不明な beat.to: {e['to']}")
            elif op == "learn":
                if (e.get("character") != "player" and e.get("character") not in self.chars) or e.get("fact") not in self.facts:
                    self.err(f"{where}: learn's character or fact does not exist / learn の登場人物か事実が存在しない")
            elif op == "promise":
                if "change" in e and e["change"] not in ("made", "kept", "broken", "voided"):
                    self.err(f"{where}: unrecognized promise.change / 不明な promise.change: {e['change']}")
                if "template" in e and e["template"] not in self.templates:
                    self.err(f"{where}: promise template does not exist / 約束のテンプレートが存在しない: {e['template']}")
                for k in ("from", "to"):
                    if k in e and e[k] != "player" and e[k] not in self.chars:
                        self.err(f"{where}: promise.{k} must be player or a character ID / promise.{k} は player か登場人物 ID")
                if not partial and not (e.get("change") and e.get("from") and e.get("to") and e.get("text")):
                    self.err(f"{where}: promise needs change / from / to / text / promise には change / from / to / text が必要")
            elif op == "hold":                                  # contracts 1.3
                it = self.items.get(e.get("item"))
                if not it or not it.get("portable"):
                    self.err(f"{where}: hold only works on portable items / hold は portable なアイテム専用: {e.get('item')}")
                for k in ("to", "from"):
                    if k in e and e[k] is not None and e[k] != "player" and e[k] not in self.chars:
                        self.err(f"{where}: hold.{k} must be player, a character ID or null / hold.{k} は player、登場人物 ID、null のいずれか")
                if not partial and "to" not in e:
                    self.err(f"{where}: hold needs to / hold には to が必要")
            elif op == "improv":
                if e.get("character") not in self.chars:
                    self.err(f"{where}: improv's character does not exist / improv の登場人物が存在しない: {e.get('character')}")
            else:
                self.err(f"{where}: unknown effect op / 不明な effect op: {op!r}")

    def knows(self, ch, fact, res):
        """Whether the character already knows it at the checkpoint: knows has the entry, and since is pre or that beat
        has already happened in this scenario; (contracts 2.3, clarified in 1.4) if the fact's trueFrom beat has not
        happened in this run, the fact is not true and nobody counts as knowing it.

        チェックポイントの時点で登場人物がすでに知っているか：knows にその項目があり、since が pre か、そのビートが
        このシナリオですでに起きている。（contracts 2.3、1.4 で明記）事実の trueFrom のビートがこのプレイで起きて
        いなければ、その事実は成立せず、誰も知っていることにはならない。
        """
        def occurred(b):
            return b == "pre" or res["status"].get(b) in ("happened", "altered")
        f = self.facts.get(fact)
        return (f is None or occurred(f["trueFrom"])) and \
            any(k["fact"] == fact and occurred(k["since"]) for k in self.chars[ch]["knows"])

    def beat_status(self, bid, res, end_t):
        st = res["status"].get(bid)
        if st in ("happened", "altered"):                # 1.4: beat variants count as altered / バリアントは altered
            return st
        if st is None:
            return "pending"
        if end_t is None or st in ("late", "prevented", "blocked") or end_t >= self.sim.beats[bid]["window"]["latest"]:
            return "prevented"
        return "pending"

    # ---------- One case / ケース 1 件 ----------
    def case(self, c, where, suite):
        """Returns True = this case's results have been verified by simulation.

        True を返す = このケースの結果はシミュレーションで検証済み。
        """
        setup, steps, exp = c.get("setup", {}), c.get("steps", []), c.get("expect", {})
        det, judge = exp.get("deterministic", []), exp.get("judge")
        if not det and not judge:
            self.err(f"{where}: expect has no checks at all / expect にチェックが 1 つもない")
        for k in set(setup) - SETUP_KEYS:
            self.err(f"{where}: unknown setup field / setup の不明なフィールド: {k}")
        role = self.roles.get(setup.get("role"))
        if not role:
            self.err(f"{where}: role does not exist / ロールが存在しない: {setup.get('role')}")
            return False
        if role["release"] != 1:
            self.err(f"{where}: role {role['id']} is not in release 1 / ロール {role['id']} は第 1 版にない")
        starts = [k for k in ("checkpoint", "scenario", "persona") if k in setup]
        if len(starts) != 1:
            self.err(f"{where}: exactly one of checkpoint / scenario / persona is required (now {starts}) / checkpoint / scenario / persona はちょうど 1 つ必要（今は {starts}）")
            return False
        start = starts[0]
        if setup.get("budgetTier", "normal") not in ("normal", "saving"):
            self.err(f"{where}: budgetTier can only be normal / saving / budgetTier は normal / saving のみ")

        res, sc, place, companion, cp_beat, reach = None, None, None, None, None, None
        if start == "persona":
            p = self.personas.get(setup["persona"])
            if not p:
                self.err(f"{where}: persona does not exist / ペルソナが存在しない: {setup['persona']}")
            elif p["role"] != role["id"]:
                self.err(f"{where}: persona {p['id']} has role {p['role']} but setup.role is {role['id']} / ペルソナ {p['id']} のロールは {p['role']} だが、setup.role は {role['id']}")
            if not isinstance(setup.get("seed"), int):
                self.err(f"{where}: a simulated game needs an integer seed / シミュレーション局には整数の seed が必要")
            if steps:
                self.err(f"{where}: a simulated game has no steps (the persona plays by itself) / シミュレーション局には steps を書かない（ペルソナが自分でプレイする）")
        elif start == "scenario":
            sc = self.scenarios.get(setup["scenario"])
            if not sc:
                return self.err(f"{where}: scenario does not exist / シナリオが存在しない: {setup['scenario']}") or False
            if any(set(s) != {"advance"} for s in steps):
                self.err(f"{where}: a case that only simulates a scenario can only have advance steps / シナリオをシミュレーションするだけのケースは advance ステップしか持てない")
        else:
            m = re.fullmatch(r"(sc\.[\w-]+)@(?:(beat\.[\w-]+)|t=(\d+))", setup["checkpoint"])
            if not m:
                return self.err(f"{where}: bad checkpoint format / チェックポイントの形式が正しくない: {setup['checkpoint']!r}") or False
            sc = self.scenarios.get(m[1])
            if not sc:
                return self.err(f"{where}: scenario does not exist / シナリオが存在しない: {m[1]}") or False
            cp_beat = m[2]
            if m[2] and m[2] not in self.sim.beats:
                return self.err(f"{where}: beat does not exist / ビートが存在しない: {m[2]}") or False
            res = self.sim.run(sc, ("beat", m[2]) if m[2] else ("t", int(m[3])),
                               role=role["id"], place=setup.get("place"))
            if not res["stopped"]:
                return self.err(f"{where}: {m[2]} does not happen in {m[1]} ({res['status'].get(m[2])}), so it cannot be a checkpoint / {m[2]} は {m[1]} で起きないので、チェックポイントにできない") or False
            if res["t"] < role["startT"]:
                self.err(f"{where}: checkpoint t={res['t']} is earlier than role {role['id']} starts ({role['startT']}) / チェックポイント t={res['t']} がロール {role['id']} の開始（{role['startT']}）より早い")
            granted = set()
            for i, ev in enumerate(setup.get("events", []), 1):
                ew = f"{where} setup.events[{i}]"
                self.check_effects(ev.get("effects", []), ew)
                for e in ev.get("effects", []):
                    if e.get("op") == "set" and e.get("var") == "var.player.location":
                        granted.add(e.get("value"))
                mem = ev.get("memory")
                if mem is not None:
                    if mem.get("character") not in self.chars or mem.get("kind") not in MEMORY_KINDS or not mem.get("text"):
                        self.err(f"{ew}: memory needs an existing character, a valid kind and text / memory には存在する character、正しい kind、text が必要")
                self.sim.apply(ev.get("effects", []), res["state"], res["where"])
            place = res["state"]["var.player.location"]
            granted |= {ca["place"] for ca in role.get("conditionalAccess", []) if self.sim.holds(ca["when"], res["state"])}
            if "place" in setup and setup["place"] not in self.places:
                self.err(f"{where}: place does not exist / 場所が存在しない: {setup['place']}")
            if "place" in setup and granted and setup["place"] not in granted:
                self.err(f"{where}: setup.place disagrees with the place arranged by setup.events / setup.place が setup.events で配置した場所と一致しない")
            reach = set(role["access"]) | granted
            if place not in reach:
                self.err(f"{where}: {role['id']} cannot enter {place} (can enter {role['access']}, or meet conditionalAccess; setup.events can also arrange it) / {role['id']} は {place} に入れない（入れるのは {role['access']}、または conditionalAccess を満たす場合。setup.events で配置してもよい）")
            companion = res["state"]["var.player.companionOf"]

        # ---------- Steps / ステップ ----------
        kinds, says, moved, gives, held = {}, {}, False, {}, {}
        for i, s in enumerate(steps, 1):
            sw = f"{where} step / 第 {i} 段階"
            keys = set(s) & STEP_KEYS
            if len(keys) != 1 or (set(s) - STEP_KEYS - {"say"}):
                self.err(f"{sw}: a step needs exactly one kind / ステップはちょうど 1 種類が必要 ({sorted(STEP_KEYS)})")
                continue
            k = keys.pop()
            kinds[i] = k
            if k == "to":
                ch = s["to"]
                if ch not in self.chars or not self.chars[ch]["talkable"]:
                    self.err(f"{sw}: {ch} does not exist or cannot be talked to / {ch} は存在しないか会話できない")
                elif res and not moved and companion != ch and res["where"].get(ch) != place:
                    self.err(f"{sw}: at the checkpoint {ch} is at {res['where'].get(ch)} and the player at {place}, so they cannot talk / チェックポイントで {ch} は {res['where'].get(ch)}、プレイヤーは {place} にいて話せない")
                if not isinstance(s.get("say"), str) or not s["say"].strip():
                    self.err(f"{sw}: say must be a non-empty string / say は空でない文字列でなければならない")
                says[i] = (ch, s.get("say", ""))
            elif k == "act":
                act = s["act"]
                want = ACT_KINDS.get(act.get("kind"))
                tgt = act.get("target")
                ok_t = {"place": self.places, "char": set(self.chars), "any": self.places | set(self.chars) | self.objects}
                if not want:
                    self.err(f"{sw}: unknown action kind {act.get('kind')} (UX list: {sorted(ACT_KINDS)}) / 不明なアクションの kind {act.get('kind')}（UX の一覧：{sorted(ACT_KINDS)}）")
                elif want == "none" and tgt is not None:
                    self.err(f"{sw}: {act['kind']} takes no target / {act['kind']} は target を取らない")
                elif want != "none" and not (want.endswith("?") and tgt is None) and tgt not in ok_t[want.rstrip("?")]:
                    self.err(f"{sw}: wrong target for {act['kind']} / {act['kind']} の target が正しくない: {tgt}")
                if not isinstance(act.get("params", {}), dict):
                    self.err(f"{sw}: params must be an object / params はオブジェクトでなければならない")
                # contracts 2.10: obtainable = the player is at a place in Item.at, or (1.3) holds it
                # contracts 2.10：入手できる = Item.at の場所にいる、または（1.3）プレイヤーの手にある
                if act.get("kind") == "give":
                    iid = act.get("params", {}).get("item")
                    it = self.items.get(iid)
                    holder = held.get(iid, res["state"].get(iid) if res else None)
                    gives[i] = bool(it and (place in it.get("at", []) or holder == "player"))
                    if it and it.get("portable") and gives[i]:
                        held[iid] = tgt
            elif k == "deleteMemory":
                d = s["deleteMemory"]
                if d.get("character") not in self.chars:
                    self.err(f"{sw}: character does not exist / 登場人物が存在しない: {d.get('character')}")
                if kinds.get(d.get("fromStep")) not in ("to", "act"):
                    self.err(f"{sw}: fromStep must point to an earlier talk or action step / fromStep は前の会話かアクションのステップを指す")
            elif k == "retract":
                if kinds.get(s["retract"].get("step")) != "to":
                    self.err(f"{sw}: retract.step must point to an earlier talk step / retract.step は前の会話のステップを指す")
            elif k in ("deletePlaythrough", "newPlaythrough"):
                if s[k] is not True:
                    self.err(f"{sw}: write {k} as true / {k} は true と書く")
            elif k == "advance":
                moved = True
                if not isinstance(s["advance"], int) or s["advance"] <= 0:
                    self.err(f"{sw}: advance must be a positive integer (minutes) / advance は正の整数（分）")
            elif k == "silence":
                if not isinstance(s["silence"], int) or s["silence"] <= 0:
                    self.err(f"{sw}: silence must be a positive integer (seconds) / silence は正の整数（秒）")
            # contracts 2.8.1 step 2 (1.2): saying your own plan at the end of the act
            # contracts 2.8.1 第 2 段階（1.2）：幕末に自分のプランを話す
            elif k == "propose":
                if not isinstance(s["propose"], str) or not s["propose"].strip():
                    self.err(f"{sw}: propose must be a non-empty string / propose は空でない文字列でなければならない")
                if cp_beat not in self.act_end:
                    self.err(f"{sw}: propose is only for the end of an act (the checkpoint must be an end-of-act beat {sorted(self.act_end)}) / propose は幕末にだけ使う（チェックポイントは幕を閉じるビート {sorted(self.act_end)} でなければならない）")
            # contracts 2.8.1 step 2 (1.5): choosing a suggested exit at the end of the act
            # contracts 2.8.1 第 2 段階（1.5）：幕末に推奨された行き先を 1 つ選ぶ
            elif k == "choose":
                ended = self.act_end.get(cp_beat)
                ch = s["choose"] if isinstance(s["choose"], dict) else {}
                ex = {e["id"]: e for e in ended["exits"]} if ended else {}
                if not ended:
                    self.err(f"{sw}: choose is only for the end of an act (the checkpoint must be an end-of-act beat {sorted(self.act_end)}) / choose は幕末にだけ使う（チェックポイントは幕を閉じるビート {sorted(self.act_end)} でなければならない）")
                elif ch.get("exit") not in ex:
                    self.err(f"{sw}: {ended['id']} has no exit {ch.get('exit')} (has {sorted(ex)}) / {ended['id']} に行き先 {ch.get('exit')} はない（あるのは {sorted(ex)}）")
                else:
                    e = ex[ch["exit"]]
                    if "enRoute" in ch and ch["enRoute"] not in range(len(e.get("enRoute", {}).get("choices", []))):
                        self.err(f"{sw}: enRoute must be an index into the interlude either-or of {e['id']} / enRoute は {e['id']} の幕間の二択の番号でなければならない")
                    moved, place = True, e["place"]
        if list(kinds.values()).count("propose") > 2:
            self.err(f"{where}: at most 2 plans can be said at one end of act (S-031 ③) / 1 回の幕末で話せるプランは 2 回まで")
        if list(kinds.values()).count("choose") > 1:
            self.err(f"{where}: only one exit can be chosen at one end of act / 1 回の幕末で選べる行き先は 1 つだけ")
        last_to = max((i for i, k in kinds.items() if k == "to"), default=None)

        # ---------- Checks / チェック ----------
        types = set()
        for j, d in enumerate(det, 1):
            dw = f"{where} 检查 {j}"
            ty = d.get("type")
            types.add(ty)
            if ty not in CHECK_TYPES:
                self.err(f"{dw}：不认识的检查 {ty}")
                continue
            if ty in REPLY_CHECKS:
                st = d.get("step", last_to)
                if kinds.get(st) != "to":
                    self.err(f"{dw}：{ty} 的 step 要指向一个对话步骤")
                    continue
                ch, say = says[st]
            if ty == "not_mention_fact":
                f = self.facts.get(d.get("fact"))
                if not f:
                    self.err(f"{dw}：事实不存在 {d.get('fact')}")
                    continue
                if not f.get("spoilerTerms"):
                    self.err(f"{dw}：{f['id']} 没有 spoilerTerms，确定性检查判不了")
                if res and ch in self.chars and self.knows(ch, f["id"], res):
                    self.err(f"{dw}：{ch} 在检查点已经知道 {f['id']}，这不是剧透")
                hit = [t for t in f.get("spoilerTerms", []) if t in say]
                if hit:
                    self.err(f"{dw}：玩家的问题里已经说了剧透词 {hit}")
            elif ty in ("no_terms", "terms_any"):
                terms = d.get("terms")
                if not terms or not all(isinstance(t, str) and t for t in terms):
                    self.err(f"{dw}：terms 要是非空字符串列表")
                elif ty == "no_terms" and not d.get("forbidEcho") and [t for t in terms if t in say]:
                    self.warn(f"{dw}：玩家自己说了 {[t for t in terms if t in say]}，角色复述也会判失败；有意的话加 forbidEcho: true")
            elif ty in ("event", "no_event"):
                mt = d.get("match", {})
                for kk in set(mt) - {"type", "actor", "effects", "origin", "beneficiary"}:
                    self.err(f"{dw}：match 只能有 type / actor / effects / origin / beneficiary，多了 {kk}")
                if "origin" in mt and mt["origin"] not in EVENT_ORIGINS:
                    self.err(f"{dw}：origin 不认识 {mt['origin']}")
                if "beneficiary" in mt and mt["beneficiary"] != "player" and mt["beneficiary"] not in self.chars:
                    self.err(f"{dw}：beneficiary 要是 player 或人物 ID")
                if "type" in mt and mt["type"] not in EVENT_TYPES:
                    self.err(f"{dw}：事件 type 不认识 {mt['type']}")
                if "actor" in mt and mt["actor"] not in {"player", "system", "narrator"} | set(self.chars):
                    self.err(f"{dw}：actor 不认识 {mt['actor']}")
                self.check_effects(mt.get("effects", []), dw, partial=True)
                if ty == "event":
                    if not set(d.get("statusIn", [])) or set(d["statusIn"]) - CHECK_STATUS:
                        self.err(f"{dw}：statusIn 要是 {sorted(CHECK_STATUS)} 的非空子集")
                    if set(d.get("failedRulesAny", [])) - RULES:
                        self.err(f"{dw}：failedRulesAny 不认识 {set(d['failedRulesAny']) - RULES}")
                    if "step" in d and kinds.get(d["step"]) not in ("to", "act"):
                        self.err(f"{dw}：step 要指向对话或动作步骤")
                    if d.get("step") in gives:
                        r7 = set(d.get("statusIn", [])) == {"rejected"} and "R7-capability" in d.get("failedRulesAny", [])
                        if gives[d["step"]] and r7:
                            self.err(f"{dw}：这一步给的物品此刻拿得到（在 {place} 的 at，或在玩家手上），不该期待 R7 否决")
                        if not gives[d["step"]] and not set(d.get("statusIn", [])) & {"rejected", "downgraded"}:
                            self.err(f"{dw}：这一步给的东西不在 items 里、在 {place} 拿不到、也不在玩家手上，只能被否决")
            elif ty == "var":
                self.check_value(d.get("var"), d.get("equals"), dw)
            elif ty == "beat":
                if d.get("beat") not in self.sim.beats or d.get("status") not in BEAT_STATUS:
                    self.err(f"{dw}：节拍或状态不对 {d.get('beat')} {d.get('status')}")
            elif ty == "outcome":
                if d.get("world") not in self.endings:
                    self.err(f"{dw}：世界结局不存在 {d.get('world')}")
            elif ty == "clock_advanced":
                lo, hi = d.get("min"), d.get("max")
                if not (isinstance(lo, int) and isinstance(hi, int) and 0 <= lo <= hi):
                    self.err(f"{dw}：min / max 要是 0 ≤ min ≤ max 的整数")
                st = d.get("step", last_to)
                if st not in kinds:
                    self.err(f"{dw}：step 不存在")
                elif lo is not None and hi is not None:       # S-038、UX 4.3：耗时是几个固定值，不是 1〜120 的任意数
                    pc, k = self.pacing, kinds[st]
                    zero = {pc.get("failedTurnMinutes", 0), pc.get("sceneWalkMinutes", 0), pc.get("examineMinutes", 0)}
                    if k == "to":
                        talk = pc.get("talkTurnMinutesAct4") if res and res["t"] is not None and res["t"] >= self.act4_t \
                            else pc.get("talkTurnMinutes")
                        if (lo, hi) != (talk, talk):
                            self.err(f"{dw}：此刻说话一来一回是 {talk} 分（pacing），写 min = max = {talk}")
                    elif k == "retract":
                        if (lo, hi) != (0, 0):
                            self.err(f"{dw}：作废的一轮不花时间，写 0")
                    elif k == "act":
                        a = steps[st - 1]["act"]
                        same = a.get("kind") == "move" and self.scene_of.get(a.get("target")) == self.scene_of.get(place)
                        if a.get("kind") == "examine" or same:
                            if (lo, hi) != (0, 0) or 0 not in zero:
                                self.err(f"{dw}：调查和同一场景里走动不花时间，写 0")
                        elif a.get("kind") not in ("move", "go", "wait", "run-together") and \
                                not pc.get("situationalMinMinutes", 0) <= lo <= hi <= pc.get("situationalMaxMinutes", 10**9):
                            self.err(f"{dw}：情境动作的耗时要在 pacing 的 15〜120 分之间")
            elif ty == "memory":
                if d.get("character") not in self.chars or not isinstance(d.get("exists"), bool):
                    self.err(f"{dw}：memory 要有存在的 character 和 bool 的 exists")
                if "fromStep" in d and kinds.get(d["fromStep"]) not in ("to", "act"):
                    self.err(f"{dw}：fromStep 要指向对话或动作步骤")
                if "kind" in d and d["kind"] not in MEMORY_KINDS:
                    self.err(f"{dw}：记忆 kind 不认识 {d['kind']}")
            elif ty == "trust":
                if d.get("character") not in self.chars or not isinstance(d.get("equals"), int) or not -100 <= d["equals"] <= 100:
                    self.err(f"{dw}：trust 要有存在的 character 和 -100..100 的 equals")
            elif ty == "utterance_cleared":
                if kinds.get(d.get("step")) != "to":
                    self.err(f"{dw}：step 要指向对话步骤")
            elif ty == "event_exists":
                if kinds.get(d.get("fromStep")) not in ("to", "act"):
                    self.err(f"{dw}：fromStep 要指向对话或动作步骤")
            elif ty == "db_absent":
                if not d.get("tables") or set(d["tables"]) - TABLES:
                    self.err(f"{dw}：tables 要是 {sorted(TABLES)} 的非空子集")
                if "deletePlaythrough" not in kinds.values():
                    self.err(f"{dw}：db_absent 需要前面有 deletePlaythrough 步骤")
            elif ty == "no_pii":
                strs = d.get("strings") or []
                if not strs or d.get("scope") not in ("memory", "summary", "ending", "all"):
                    self.err(f"{dw}：no_pii 要有 strings 和 scope（memory / summary / ending / all）")
                said = " ".join(x for _, x in says.values())
                for s_ in strs:
                    if s_ not in said:
                        self.err(f"{dw}：{s_!r} 玩家没说过，这条检查测不到东西")
            elif ty == "followup_questions":
                if kinds.get(d.get("after")) != "silence" or not isinstance(d.get("max"), int) or d["max"] < 0:
                    self.err(f"{dw}：after 要指向 silence 步骤，max 是非负整数")
            elif ty == "schedule_shift":
                if d.get("beat") not in self.sim.beats or not isinstance(d.get("equals"), int):
                    self.err(f"{dw}：schedule_shift 要有存在的 beat 和整数 equals")
            elif ty == "promise":
                if d.get("status") not in PROMISE_STATUS:
                    self.err(f"{dw}：promise.status 要是 {sorted(PROMISE_STATUS)}")
                if "template" in d and d["template"] not in self.templates:
                    self.err(f"{dw}：约定模板不存在 {d['template']}")
                if "template" not in d and not ("from" in d and "to" in d):
                    self.err(f"{dw}：promise 要用 template，或 from + to 指明是哪一个约定")
            elif ty == "act_plan":
                if "propose" not in kinds.values():
                    self.err(f"{dw}：act_plan 要有前面的 propose 步骤")
                elif not isinstance(d.get("accepted"), bool):
                    self.err(f"{dw}：act_plan 要写 accepted: true / false")
                elif d["accepted"]:
                    ended = self.act_end.get(cp_beat)
                    # 下一幕 = 这一幕的去处去的那一幕（切片版第一幕直接跳到 act.4，S-077 ⑤）；
                    # （1.7，C-19）幕上有 plan 时成行就落在它写的下一幕和地点
                    plan = ended.get("plan") if ended else None
                    nxt = [plan["toAct"]] if plan else sorted({e["toAct"] for e in ended["exits"]}) if ended else []
                    if d.get("toAct") not in nxt:
                        self.err(f"{dw}：成行的打算 toAct 要是下一幕 {nxt}")
                    if plan and d.get("place") != plan["place"]:
                        self.err(f"{dw}：这一幕有 plan，成行的打算落在 {plan['place']}")
                    elif d.get("place") not in self.places:
                        self.err(f"{dw}：地点不存在 {d.get('place')}")
                    elif reach is not None and d["place"] not in reach:
                        self.err(f"{dw}：{role['id']} 进不了 {d['place']}，期待成行和 R7 矛盾")
                elif set(d) - {"type", "accepted"}:
                    self.err(f"{dw}：不成行时只写 accepted: false")
            elif ty == "safety_card":
                if not isinstance(d.get("shown"), bool):
                    self.err(f"{dw}：safety_card 要写 shown: true / false")
            elif ty in ENDING_CHECKS and start != "persona" and "advance" not in kinds.values():
                self.err(f"{dw}：{ty} 要走到结局（模拟局，或有 advance）")
            elif ty in E7_CHECKS and start != "persona":
                self.err(f"{dw}：{ty} 只用于模拟局（setup.persona）")
        if judge is not None:
            if not isinstance(judge.get("rubric"), str) or not judge["rubric"].strip():
                self.err(f"{where}：judge.rubric 要写评分细则")
            if not re.fullmatch(r">=[1-5]/5", str(judge.get("pass", ""))):
                self.err(f"{where}：judge.pass 写成 \">=N/5\"")

        # ---------- 套件约定 ----------
        if suite == "E1" and not (types & {"world_unchanged", "no_event"} and "no_terms" in types):
            self.warn(f"{where}：E1 一般要有 world_unchanged / no_event 和 no_terms")
        if suite == "E2" and not types & {"not_mention_fact", "no_terms"}:
            self.err(f"{where}：E2 要有 not_mention_fact 或 no_terms")
        if suite == "E7" and (start != "persona" or E7_CHECKS - types):
            self.err(f"{where}：E7 用模拟局，四项检查都要有")

        # ---------- 能用推演算出来的，现在就算 ----------
        sim_checks = [d for d in det if d.get("type") in SIM_CHECKS]
        if not sim_checks or any(k != "advance" for k in kinds.values()) or start == "persona":
            return False
        if start == "scenario":
            res, end_t = self.sim.run(sc, role=role["id"]), None
        else:
            if any(d["type"] == "outcome" for d in sim_checks):
                end_t = None
            else:
                end_t = res["t"] + sum(s["advance"] for s in steps)
            res = self.sim.resume(res, sc, until_t=end_t)
        ok = True
        for d in sim_checks:
            if d["type"] == "outcome" and res["outcome"] != d["world"]:
                ok = False
                self.err(f"{where}：推演出的世界结局是 {res['outcome']}，期望 {d['world']}")
            elif d["type"] == "var" and res["state"].get(d["var"]) != d["equals"]:
                ok = False
                self.err(f"{where}：推演出 {d['var']} = {res['state'].get(d['var'])!r}，期望 {d['equals']!r}")
            elif d["type"] == "beat":
                got = self.beat_status(d["beat"], res, end_t)
                if got != d["status"] or ("t" in d and res["times"].get(d["beat"]) != d["t"]):
                    ok = False
                    self.err(f"{where}：推演出 {d['beat']} {got} t={res['times'].get(d['beat'])}，期望 {d['status']} t={d.get('t')}")
        return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", required=True)
    ap.add_argument("--scenarios", required=True)
    ap.add_argument("--cases", required=True)
    ap.add_argument("--personas", nargs="+", default=[],
                    help="模拟局的画像，可以给几个文件（第一幕的 + evals/acts/actN 的）；不给 = 用例里不能有模拟局")
    a = ap.parse_args()
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    ck = Checker(load(a.world), load(a.scenarios), [p for f in a.personas for p in load(f)])
    ids = [p["id"] for f in a.personas for p in load(f)]
    for pid in sorted({i for i in ids if ids.count(i) > 1}):
        ck.err(f"画像 {pid} 在几个文件里重复")

    # 画像文件四幕共用：切片只有旅人，别的身份的画像切片用例用不到，只查用例里用到的（W-2）
    used = set(re.findall(r'"persona": "([^"]+)"', "".join(
        f.read_text(encoding="utf-8") for f in Path(a.cases).glob("E*.jsonl"))))
    for pid, p in ck.personas.items():
        r = ck.roles.get(p.get("role"))
        if pid in used and (not r or r["release"] != 1):
            ck.err(f"画像 {pid}：身份 {p.get('role')} 不存在或不在第一版")

    files = sorted(Path(a.cases).glob("E*.jsonl"))
    if not files:
        ck.err(f"{a.cases} 下没有 E*.jsonl")
    seen, rows = set(), []
    for f in files:
        suite, n, verified, modes = f.stem, 0, 0, {"text": 0, "voice": 0}
        for ln, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                c = json.loads(line)
            except json.JSONDecodeError as e:
                ck.err(f"{f.name}:{ln}：不是合法 JSON（{e}）")
                continue
            cid = c.get("id", "?")
            where = f"{f.name}:{ln} {cid}"
            n += 1
            if cid in seen:
                ck.err(f"{where}：id 重复")
            seen.add(cid)
            if not re.fullmatch(rf"{suite}-\d{{3}}", cid) or c.get("suite") != suite:
                ck.err(f"{where}：id / suite 应该是 {suite}-NNN / {suite}")
            if not c.get("title"):
                ck.err(f"{where}：缺 title")
            mode = c.get("mode", "text")
            if mode not in modes:
                ck.err(f"{where}：mode 只能是 text / voice")
            else:
                modes[mode] += 1
            runs = c.get("runs", 5)
            if not isinstance(runs, int) or runs < 1:
                ck.err(f"{where}：runs 要是正整数")
            verified += bool(ck.case(c, where, suite))
        rows.append((suite, n, modes["text"], modes["voice"], verified))

    print("| 套件 | 用例 | 文字 | 语音 | 已用推演验证结果 |")
    print("|---|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(map(str, r)) + " |")
    print(f"\n错误 {len(ck.errors)}，警告 {len(ck.warnings)}")
    for e in ck.errors:
        print("ERROR", e)
    for x in ck.warnings:
        print("WARN ", x)
    return 1 if ck.errors else 0


if __name__ == "__main__":
    sys.exit(main())
