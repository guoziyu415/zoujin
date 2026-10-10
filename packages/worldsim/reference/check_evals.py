#!/usr/bin/env python3
"""评测用例自检（格式见 data/evals/README.md）。

用法：
  python3 -I check_evals.py --world world.json --scenarios scenarios.json --cases evals/seeds --personas personas.json

不调用任何模型，只检查用例本身写得对不对：
1. 格式：每行一个 JSON；id 唯一、和文件名的套件一致；字段、步骤、检查类型和参数都认识。
2. 引用：身份、人物、地点、事实、节拍、状态变量、世界结局、情景、画像都存在；取值符合类型。
3. 起点：按情景推演到检查点（和 build_world.py 共用 worldsim.py）。检查点的节拍在该情景里确实发生；
   身份那时已经开局；玩家所在的地方是身份能进的（或由 setup.events 安排）；说话对象那时就在玩家身边。
4. 防剧透用例的前提：被问的角色在检查点确实还不知道那个事实；玩家的问题里没有直接说出剧透词。
5. 只靠时间规则就能算出结果的用例（只有 setup.scenario，或检查点 + setup.events + advance），
   现在就推演一遍，确认期望的结局、节拍、状态变量成立。
只用标准库。
"""
import argparse
import json
import re
import sys
from pathlib import Path

from zoujin_worldsim import Sim  # 和 build_world.py 共用的推演规则（W-1 的包）

CHECK_STATUS = {"passed", "rewritten", "downgraded", "rejected"}
RULES = {"R1-anchor", "R2-precondition", "R3-time", "R4-knowledge", "R5-persona", "R6-safety", "R7-capability"}
EVENT_TYPES = {"say", "action", "move", "beat", "learn", "act-transition", "correction", "ending", "forget"}
EVENT_ORIGINS = {"turn", "action", "schedule", "plan", "director", "act", "memory"}      # contracts 3（1.1）
PROMISE_STATUS = {"open", "kept", "broken", "voided"}
BEAT_STATUS = {"pending", "happened", "prevented", "delayed", "hastened", "altered"}
MEMORY_KINDS = {"promise", "help", "harm", "shared-moment", "claim", "impression"}
# 动作清单：UX v1.0 18.2（target 的种类），外加 api-contract 的 move（在地点之间走）
ACT_KINDS = {"examine": "any", "give": "char", "follow": "char", "block": "char", "help": "char", "wait": "none",
             "go": "place", "shortcut": "place?", "run-together": "char", "hasten": "any?", "move": "place"}
TABLES = {"playthroughs", "events", "utterances", "memory_items", "world_state", "endings",
          "playthrough_metrics", "turns", "briefs"}
REPLY_CHECKS = {"not_mention_fact", "no_terms", "terms_any", "japanese"}       # 检查某一步角色的回答
E7_CHECKS = {"replay_equal", "t_monotonic", "outcome_consistent", "epilogue_cites_valid"}
SIM_CHECKS = {"outcome", "beat", "var"}                                         # 能用推演直接算出来的
ENDING_CHECKS = {"no_verbatim_quotes", "director_not_sole_cause"}               # S-046、S-045
CHECK_TYPES = REPLY_CHECKS | E7_CHECKS | SIM_CHECKS | ENDING_CHECKS | {
    "world_unchanged", "event", "no_event", "clock_advanced", "memory", "trust", "utterance_cleared",
    "event_exists", "db_absent", "no_pii", "followup_questions", "schedule_shift", "safety_card", "promise",
    "act_plan"}                                                                  # contracts 1.2：幕末说出的打算
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
        self.items = {x["id"]: x for x in world.get("items", [])}
        self.pacing = world.get("pacing", {})
        self.scene_of = {p["id"]: p.get("sceneRef") for p in world["places"]}
        self.act4_t = max(world["acts"], key=lambda a: a["order"])["start"]["t"]        # 最后一幕从几点起（说话 15 分）
        self.templates = {x["id"] for c in world["characters"] for x in c.get("promiseTemplates", [])}
        self.facts = {f["id"]: f for f in world["facts"]}
        self.roles = {r["id"]: r for r in world["roles"]}
        self.acts = {a["id"]: a for a in world["acts"]}
        self.act_end = {b: a for a in world["acts"] if a["exits"] for b in a["end"]["onBeats"]}  # 收幕节拍 → 幕
        self.endings = {e["id"] for e in self.sim.endings}
        self.errors, self.warnings = [], []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    # ---------- 取值和效果 ----------
    def check_value(self, var, value, where):
        v = self.sim.svars.get(var)
        if not v:
            return self.err(f"{where}：状态变量不存在 {var}")
        ty = v["type"]
        if ty == "bool" and not isinstance(value, bool):
            self.err(f"{where}：{var} 是 bool，给了 {value!r}")
        elif ty == "int" and (not isinstance(value, int) or isinstance(value, bool)):
            self.err(f"{where}：{var} 是 int，给了 {value!r}")
        elif ty == "enum" and value not in v["values"]:
            self.err(f"{where}：{var} 没有取值 {value!r}（可选 {v['values']}）")
        elif ty == "place" and value not in self.places:
            self.err(f"{where}：{var} 的地点不存在 {value!r}")

    def check_effects(self, effs, where, partial=False):
        """partial=True：用在 event / no_event 的 match 里，只写想匹配的字段。"""
        if not isinstance(effs, list):
            return self.err(f"{where}：effects 要是列表")
        for e in effs:
            op = e.get("op")
            if op == "set":
                if "var" not in e:
                    if not partial:
                        self.err(f"{where}：set 缺 var")
                elif "value" in e:
                    self.check_value(e["var"], e["value"], where)
                elif e["var"] not in self.sim.svars:
                    self.err(f"{where}：状态变量不存在 {e['var']}")
                elif not partial:
                    self.err(f"{where}：set 缺 value")
            elif op == "inc":
                v = self.sim.svars.get(e.get("var"))
                if not v or v["type"] != "int":
                    self.err(f"{where}：inc 的变量不是 int：{e.get('var')}")
            elif op == "relocate":
                if e.get("character") not in self.chars:
                    self.err(f"{where}：relocate 的人物不存在 {e.get('character')}")
                if ("place" in e or not partial) and e.get("place") not in self.places:
                    self.err(f"{where}：relocate 的地点不存在 {e.get('place')}")
            elif op == "beat":
                if e.get("beat") not in self.sim.beats:
                    self.err(f"{where}：节拍不存在 {e.get('beat')}")
                if "to" in e and e["to"] not in BEAT_STATUS - {"pending"}:
                    self.err(f"{where}：beat.to 不认识 {e['to']}")
            elif op == "learn":
                if (e.get("character") != "player" and e.get("character") not in self.chars) or e.get("fact") not in self.facts:
                    self.err(f"{where}：learn 的人物或事实不存在")
            elif op == "promise":
                if "change" in e and e["change"] not in ("made", "kept", "broken", "voided"):
                    self.err(f"{where}：promise.change 不认识 {e['change']}")
                if "template" in e and e["template"] not in self.templates:
                    self.err(f"{where}：约定模板不存在 {e['template']}")
                for k in ("from", "to"):
                    if k in e and e[k] != "player" and e[k] not in self.chars:
                        self.err(f"{where}：promise.{k} 要是 player 或人物 ID")
                if not partial and not (e.get("change") and e.get("from") and e.get("to") and e.get("text")):
                    self.err(f"{where}：promise 要有 change / from / to / text")
            elif op == "hold":                                  # contracts 1.3
                it = self.items.get(e.get("item"))
                if not it or not it.get("portable"):
                    self.err(f"{where}：hold 只能用于 portable 的物品 {e.get('item')}")
                for k in ("to", "from"):
                    if k in e and e[k] is not None and e[k] != "player" and e[k] not in self.chars:
                        self.err(f"{where}：hold.{k} 要是 player、人物 ID 或 null")
                if not partial and "to" not in e:
                    self.err(f"{where}：hold 要写 to")
            elif op == "improv":
                if e.get("character") not in self.chars:
                    self.err(f"{where}：improv 的人物不存在 {e.get('character')}")
            else:
                self.err(f"{where}：不认识的 effect op {op!r}")

    def knows(self, ch, fact, res):
        """检查点时角色是否已经知道：knows 里有这条，且 since 是 pre 或那个节拍在本情景里已经发生；
        （contracts 2.3，1.4 写清）事实的 trueFrom 节拍本局没发生，这条事实就不成立，谁都不算知道。"""
        def occurred(b):
            return b == "pre" or res["status"].get(b) in ("happened", "altered")
        f = self.facts.get(fact)
        return (f is None or occurred(f["trueFrom"])) and \
            any(k["fact"] == fact and occurred(k["since"]) for k in self.chars[ch]["knows"])

    def beat_status(self, bid, res, end_t):
        st = res["status"].get(bid)
        if st in ("happened", "altered"):                # 1.4：节拍的变体按 altered 记
            return st
        if st is None:
            return "pending"
        if end_t is None or st in ("late", "prevented", "blocked") or end_t >= self.sim.beats[bid]["window"]["latest"]:
            return "prevented"
        return "pending"

    # ---------- 一个用例 ----------
    def case(self, c, where, suite):
        """返回 True = 这个用例的结果已经用推演验证过。"""
        setup, steps, exp = c.get("setup", {}), c.get("steps", []), c.get("expect", {})
        det, judge = exp.get("deterministic", []), exp.get("judge")
        if not det and not judge:
            self.err(f"{where}：expect 里没有任何检查")
        for k in set(setup) - SETUP_KEYS:
            self.err(f"{where}：setup 不认识的字段 {k}")
        role = self.roles.get(setup.get("role"))
        if not role:
            self.err(f"{where}：身份不存在 {setup.get('role')}")
            return False
        if role["release"] != 1:
            self.err(f"{where}：身份 {role['id']} 不在第一版")
        starts = [k for k in ("checkpoint", "scenario", "persona") if k in setup]
        if len(starts) != 1:
            self.err(f"{where}：checkpoint / scenario / persona 必须且只能有一个（现在 {starts}）")
            return False
        start = starts[0]
        if setup.get("budgetTier", "normal") not in ("normal", "saving"):
            self.err(f"{where}：budgetTier 只能是 normal / saving")

        res, sc, place, companion, cp_beat, reach = None, None, None, None, None, None
        if start == "persona":
            p = self.personas.get(setup["persona"])
            if not p:
                self.err(f"{where}：画像不存在 {setup['persona']}")
            elif p["role"] != role["id"]:
                self.err(f"{where}：画像 {p['id']} 的身份是 {p['role']}，setup.role 却是 {role['id']}")
            if not isinstance(setup.get("seed"), int):
                self.err(f"{where}：模拟局要给整数 seed")
            if steps:
                self.err(f"{where}：模拟局不写 steps（由画像自己玩）")
        elif start == "scenario":
            sc = self.scenarios.get(setup["scenario"])
            if not sc:
                return self.err(f"{where}：情景不存在 {setup['scenario']}") or False
            if any(set(s) != {"advance"} for s in steps):
                self.err(f"{where}：只推演情景的用例只能有 advance 步骤")
        else:
            m = re.fullmatch(r"(sc\.[\w-]+)@(?:(beat\.[\w-]+)|t=(\d+))", setup["checkpoint"])
            if not m:
                return self.err(f"{where}：检查点格式不对 {setup['checkpoint']!r}") or False
            sc = self.scenarios.get(m[1])
            if not sc:
                return self.err(f"{where}：情景不存在 {m[1]}") or False
            cp_beat = m[2]
            if m[2] and m[2] not in self.sim.beats:
                return self.err(f"{where}：节拍不存在 {m[2]}") or False
            res = self.sim.run(sc, ("beat", m[2]) if m[2] else ("t", int(m[3])),
                               role=role["id"], place=setup.get("place"))
            if not res["stopped"]:
                return self.err(f"{where}：{m[2]} 在 {m[1]} 里没有发生（{res['status'].get(m[2])}），不能当检查点") or False
            if res["t"] < role["startT"]:
                self.err(f"{where}：检查点 t={res['t']} 早于身份 {role['id']} 开局（{role['startT']}）")
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
                        self.err(f"{ew}：memory 要有存在的 character、合法的 kind 和 text")
                self.sim.apply(ev.get("effects", []), res["state"], res["where"])
            place = res["state"]["var.player.location"]
            granted |= {ca["place"] for ca in role.get("conditionalAccess", []) if self.sim.holds(ca["when"], res["state"])}
            if "place" in setup and setup["place"] not in self.places:
                self.err(f"{where}：地点不存在 {setup['place']}")
            if "place" in setup and granted and setup["place"] not in granted:
                self.err(f"{where}：setup.place 和 setup.events 安排的地点不一致")
            reach = set(role["access"]) | granted
            if place not in reach:
                self.err(f"{where}：{role['id']} 不能进 {place}（能进 {role['access']}，或满足 conditionalAccess；也可以用 setup.events 安排）")
            companion = res["state"]["var.player.companionOf"]

        # ---------- 步骤 ----------
        kinds, says, moved, gives, held = {}, {}, False, {}, {}
        for i, s in enumerate(steps, 1):
            sw = f"{where} 第 {i} 步"
            keys = set(s) & STEP_KEYS
            if len(keys) != 1 or (set(s) - STEP_KEYS - {"say"}):
                self.err(f"{sw}：步骤要且只要一种（{sorted(STEP_KEYS)}）")
                continue
            k = keys.pop()
            kinds[i] = k
            if k == "to":
                ch = s["to"]
                if ch not in self.chars or not self.chars[ch]["talkable"]:
                    self.err(f"{sw}：{ch} 不存在或不能对话")
                elif res and not moved and companion != ch and res["where"].get(ch) != place:
                    self.err(f"{sw}：检查点时 {ch} 在 {res['where'].get(ch)}，玩家在 {place}，说不上话")
                if not isinstance(s.get("say"), str) or not s["say"].strip():
                    self.err(f"{sw}：say 要是非空字符串")
                says[i] = (ch, s.get("say", ""))
            elif k == "act":
                act = s["act"]
                want = ACT_KINDS.get(act.get("kind"))
                tgt = act.get("target")
                ok_t = {"place": self.places, "char": set(self.chars), "any": self.places | set(self.chars)}
                if not want:
                    self.err(f"{sw}：动作 kind 不认识 {act.get('kind')}（UX 清单：{sorted(ACT_KINDS)}）")
                elif want == "none" and tgt is not None:
                    self.err(f"{sw}：{act['kind']} 不带 target")
                elif want != "none" and not (want.endswith("?") and tgt is None) and tgt not in ok_t[want.rstrip("?")]:
                    self.err(f"{sw}：{act['kind']} 的 target 不对 {tgt}")
                if not isinstance(act.get("params", {}), dict):
                    self.err(f"{sw}：params 要是对象")
                if act.get("kind") == "give":           # contracts 2.10：拿得到 = 人在 Item.at 的地点，或（1.3）在玩家手上
                    iid = act.get("params", {}).get("item")
                    it = self.items.get(iid)
                    holder = held.get(iid, res["state"].get(iid) if res else None)
                    gives[i] = bool(it and (place in it.get("at", []) or holder == "player"))
                    if it and it.get("portable") and gives[i]:
                        held[iid] = tgt
            elif k == "deleteMemory":
                d = s["deleteMemory"]
                if d.get("character") not in self.chars:
                    self.err(f"{sw}：人物不存在 {d.get('character')}")
                if kinds.get(d.get("fromStep")) not in ("to", "act"):
                    self.err(f"{sw}：fromStep 要指向前面的对话或动作步骤")
            elif k == "retract":
                if kinds.get(s["retract"].get("step")) != "to":
                    self.err(f"{sw}：retract.step 要指向前面的对话步骤")
            elif k in ("deletePlaythrough", "newPlaythrough"):
                if s[k] is not True:
                    self.err(f"{sw}：{k} 写 true")
            elif k == "advance":
                moved = True
                if not isinstance(s["advance"], int) or s["advance"] <= 0:
                    self.err(f"{sw}：advance 要是正整数（分钟）")
            elif k == "silence":
                if not isinstance(s["silence"], int) or s["silence"] <= 0:
                    self.err(f"{sw}：silence 要是正整数（秒）")
            elif k == "propose":                       # contracts 2.8.1 第 2 步（1.2）：幕末说出自己的打算
                if not isinstance(s["propose"], str) or not s["propose"].strip():
                    self.err(f"{sw}：propose 要是非空字符串")
                if cp_beat not in self.act_end:
                    self.err(f"{sw}：propose 只能用在幕末（检查点要是某一幕的收幕节拍 {sorted(self.act_end)}）")
            elif k == "choose":                        # contracts 2.8.1 第 2 步（1.5）：幕末选一个推荐去处
                ended = self.act_end.get(cp_beat)
                ch = s["choose"] if isinstance(s["choose"], dict) else {}
                ex = {e["id"]: e for e in ended["exits"]} if ended else {}
                if not ended:
                    self.err(f"{sw}：choose 只能用在幕末（检查点要是某一幕的收幕节拍 {sorted(self.act_end)}）")
                elif ch.get("exit") not in ex:
                    self.err(f"{sw}：{ended['id']} 没有去处 {ch.get('exit')}（有 {sorted(ex)}）")
                else:
                    e = ex[ch["exit"]]
                    if "enRoute" in ch and ch["enRoute"] not in range(len(e.get("enRoute", {}).get("choices", []))):
                        self.err(f"{sw}：enRoute 要是 {e['id']} 过场二选一的序号")
                    moved, place = True, e["place"]
        if list(kinds.values()).count("propose") > 2:
            self.err(f"{where}：同一次幕末最多说 2 次打算（S-031 ③）")
        if list(kinds.values()).count("choose") > 1:
            self.err(f"{where}：一次幕末只选一个去处")
        last_to = max((i for i, k in kinds.items() if k == "to"), default=None)

        # ---------- 检查 ----------
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
    ap.add_argument("--personas", help="模拟局的画像；不给 = 用例里不能有模拟局（切片用例就不给）")
    a = ap.parse_args()
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731
    ck = Checker(load(a.world), load(a.scenarios), load(a.personas) if a.personas else [])

    for pid, p in ck.personas.items():
        r = ck.roles.get(p.get("role"))
        if not r or r["release"] != 1:
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
