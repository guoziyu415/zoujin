"""S-2 叙事者自检准确率的标注集：格式自检 + 确定性规则的参考判法（不调模型）。

标注集两份，写法相同：
- evals/s2/s2_dev.jsonl（公开，10 条）：给后端搭 S-2 运行器、看格式，由 gen_s2_dev.py 生成；
- evals/holdout/s2/s2_holdout.jsonl（测量集，50 条）：叙事者自检的提示定稿前后端不看（S-069 的教训），由同目录的 gen_s2_holdout.py 生成。

一条 = 一个检查点 + 这一轮（玩家原话和人物回答，或玩家的动作）+ 叙事者提取出的一个候选事件 + 人工标注。
被测的是叙事者的第 3、4 步（backend-design 2.4：确定性 R1〜R4、R7，模型 R5、R6）：给它候选事件，它判过或不过、报哪几条规则。

这里的 `judge()` 是数据写的**最简确定性判法**，只用来核对标注自洽：
- 标成 stage = "rules" 的违规，判法必须报出 label.failedRules 的第一条（主规则），报出的规则都在 failedRules ∪ acceptAlso 里；
- 合规的、和 stage = "model" 的违规（只有读懂意思才判得出），判法一条都不许报，
  否则说明标注写错了，或这条其实规则就能判。
它不是后端的实现；后端按 contracts 第 3 节的规则表实现，判法的写法见 evals/s2/README.md「确定性规则的最简判法」。

用法：python3 -I evals/s2_check.py <标注集.jsonl>（默认的世界模型和情景见 --world、--scenarios）
只用标准库。
"""
import argparse
import heapq
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent
from zoujin_worldsim import OCCURRED, Sim  # 共享规则（W-1 的包）
sys.path.insert(0, str(DATA / "packages" / "worldsim" / "reference"))
from check_evals import Checker  # noqa: E402  效果的格式检查沿用评测用例自检

WORLD = DATA / "worlds" / "hashire-merosu" / "1.0.0-draft" / "world.json"
SCENARIOS = DATA / "worlds" / "hashire-merosu" / "1.0.0-draft" / "scenarios.json"

RULES = ["R1-anchor", "R2-precondition", "R3-time", "R4-knowledge", "R5-persona", "R6-safety", "R7-capability"]
DET_RULES = {"R1-anchor", "R2-precondition", "R3-time", "R4-knowledge", "R7-capability"}
EVENT_TYPES = {"say", "action", "move", "learn"}           # 叙事者从一轮里提取的候选事件只有这几种
ORIGINS = {"turn", "action"}
ITEM_KEYS = {"id", "title", "setup", "turn", "candidate", "label", "tags"}
CAND_KEYS = {"actor", "type", "origin", "t", "dt", "place", "summary", "causes", "effects", "beneficiary", "confirmed"}
LABEL_KEYS = {"verdict", "failedRules", "acceptAlso", "stage", "rationale", "fix", "refs"}
TURN_KEYS = {"player", "to", "reply", "act"}
TAGS = {"anchor-text", "improv", "claim", "tricky-valid", "pair", "no-effects", "verbatim-quote", "pii",
        "violence", "affordance", "aid", "travel", "past", "romance", "faith", "threshold"}
TERMINAL = {"var.hostage.fate": "executed", "var.player.custody": "executed", "var.melos.custody": "executed"}
JA = re.compile(r"[぀-ヿ一-鿿]")
PII = re.compile(r"\d{2,4}-\d{2,4}-\d{3,4}|@[\w.-]+\.\w+|〒")
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
RF_ID = re.compile(r"^rf_[0-9A-HJKMNP-TV-Z]{26}$")      # contracts 第 0 节：运行时 ID = 前缀 + ULID（C-2 的 RunFactId）


def fake_ulid(key):
    """测试数据用的、合法形状的 ULID（26 位 Crockford base32），由 key 确定地算出，重跑生成器不变。"""
    import hashlib
    n = int.from_bytes(hashlib.sha256(key.encode()).digest()[:15], "big")
    return "01J" + "".join(CROCKFORD[(n >> (5 * i)) & 31] for i in range(23))


def lcs_len(a, b):
    """最长公共子串长度（no_verbatim_quotes 同样的比法：原话 8 字以上照抄算引用）。"""
    best, prev = 0, [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            if x == y:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


class S2:
    def __init__(self, world, scenarios):
        self.w = world
        self.sim = Sim(world)
        self.ck = Checker(world, scenarios, [])
        self.scen = {"sc.canon": {"id": "sc.canon"}, **{s["id"]: s for s in scenarios}}
        self.roles = {r["id"]: r for r in world["roles"]}
        self.chars = {c["id"]: c for c in world["characters"]}
        self.facts = {f["id"]: f for f in world["facts"]}
        self.items = {x["id"]: x for x in world.get("items", [])}
        self.affs = {a["id"]: a for a in world["affordances"]}
        self.places = {p["id"]: p for p in world["places"]}
        self.anchor_beats = {b["id"] for b in world["beats"] if b["kind"] == "anchor"} | \
            {a for a in world["anchors"] if a.startswith("beat.")}
        self.ids = set(self.chars) | set(self.facts) | set(self.items) | set(self.affs) | set(self.places) | \
            set(self.sim.beats) | set(self.sim.svars) | set(self.roles) | set(self.scen) | \
            {a["id"] for c in world["characters"] for a in c.get("mutualAid", [])} | \
            {p["id"] for c in world["characters"] for p in c.get("promiseTemplates", [])} | \
            {g["id"] for g in world["globalRules"]} | \
            {v["id"] for b in world["beats"] for v in b.get("variants", [])}

    # ---------- 检查点 ----------
    def state_at(self, setup):
        """按情景推演到检查点，再应用 setup.events。返回 (res, learned, granted, err)。"""
        role = self.roles.get(setup.get("role"))
        if not role or role.get("release") != 1:
            return None, None, None, f"身份不存在或不在第一版：{setup.get('role')}"
        m = re.fullmatch(r"(sc\.[\w-]+)@(?:(beat\.[\w-]+)|t=(\d+))", setup.get("checkpoint", ""))
        if not m or m[1] not in self.scen or (m[2] and m[2] not in self.sim.beats):
            return None, None, None, f"检查点不对：{setup.get('checkpoint')}"
        res = self.sim.run(self.scen[m[1]], ("beat", m[2]) if m[2] else ("t", int(m[3])),
                           role=role["id"], place=setup.get("place"))
        if not res["stopped"]:
            return None, None, None, f"{m[2]} 在 {m[1]} 里没有发生"
        if res["t"] < role["startT"]:
            return None, None, None, f"检查点 t={res['t']} 早于身份开局 {role['startT']}"
        learned, granted = {}, set()
        for ev in setup.get("events", []):
            for e in ev.get("effects", []):
                if e.get("op") == "learn":
                    learned.setdefault(e["character"], set()).add(e["fact"])
                if e.get("op") == "set" and e.get("var") == "var.player.location":
                    granted.add(e["value"])
            self.sim.apply(ev.get("effects", []), res["state"], res["where"])
        return res, learned, granted, None

    def reach(self, role, state, granted):
        ok = set(role["access"]) | granted
        return ok | {ca["place"] for ca in role.get("conditionalAccess", []) if self.sim.holds(ca["when"], state)}

    def occurred(self, b, res):
        return b == "pre" or res["status"].get(b) in OCCURRED

    def fact_true(self, f, res):
        return self.occurred(self.facts[f]["trueFrom"], res)

    def knows(self, actor, fact, res, learned, role):
        if not self.fact_true(fact, res):
            return False
        if actor == "player":
            return fact in role.get("initialKnowledge", [])
        if fact in learned.get(actor, set()):
            return True
        return any(k["fact"] == fact and self.occurred(k["since"], res) for k in self.chars[actor]["knows"])

    def dist(self, a, b):
        if a == b:
            return 0
        best, q = {a: 0}, [(0, a)]
        while q:
            d, p = heapq.heappop(q)
            if p == b:
                return d
            if d > best.get(p, 10 ** 9):
                continue
            for e in self.places[p]["adjacent"]:
                nd = d + e["travelMinutes"]
                if nd < best.get(e["place"], 10 ** 9):
                    best[e["place"]] = nd
                    heapq.heappush(q, (nd, e["place"]))
        return 10 ** 9

    def anchor_locked(self, res):
        """已发生的锚点节拍写下、之后没有别的节拍改过的变量 → 值（推翻它 = R1）。"""
        locked = {}
        for bid in sorted(res["times"], key=lambda b: (res["times"][b], self.sim.beats[b]["order"])):
            if res["status"].get(bid) not in OCCURRED:
                continue
            for e in self.sim.beats[bid]["outcomes"]:
                if e["op"] != "set":
                    continue
                if bid in self.anchor_beats:
                    locked[e["var"]] = e["value"]
                else:
                    locked.pop(e["var"], None)
        return {v: x for v, x in locked.items() if res["state"].get(v) == x}

    # ---------- 最简确定性判法 ----------
    def judge(self, item):
        """返回 (报出的规则集合, 理由列表, 错误列表)。错误 = 这条标注本身写坏了（不是规则判定）。"""
        setup, turn, c = item["setup"], item.get("turn", {}), item["candidate"]
        role = self.roles.get(setup.get("role"))
        res, learned, granted, e0 = self.state_at(setup)
        if e0:
            return set(), [], [e0]
        state, where, clock = res["state"], res["where"], res["t"]
        ppl = state["var.player.location"]
        errs, hits, why = [], set(), []

        def hit(rule, msg):
            hits.add(rule)
            why.append(f"{rule}：{msg}")

        if ppl not in self.reach(role, state, granted):
            errs.append(f"玩家在 {ppl}，{role['id']} 此刻进不去（用 setup.events 安排）")
        to = turn.get("to")
        if to and to not in self.chars:
            errs.append(f"turn.to 不存在 {to}")
        elif to and state["var.player.companionOf"] != to and where.get(to) != ppl:
            errs.append(f"{to} 在 {where.get(to)}，玩家在 {ppl}，说不上话")
        if c["place"] not in self.places:
            errs.append(f"candidate.place 不存在 {c['place']}")
        actor = c["actor"]
        if actor != "player" and actor not in self.chars:
            errs.append(f"actor 不存在 {actor}")
        if errs:
            return hits, why, errs

        # R3：时间只往前走
        if c["t"] < clock:
            hit("R3-time", f"t={c['t']} 早于此刻的时钟 {clock}（时间不能倒退，rule.time-moves-forward）")

        sim_state = dict(state)
        for e in c["effects"]:
            op = e["op"]
            if op == "beat":
                b, st = e["beat"], res["status"].get(e["beat"])
                if b in self.anchor_beats and e["to"] != "happened":
                    hit("R1-anchor", f"{b} 是锚点，不能 {e['to']}")
                if st is not None:
                    hit("R2-precondition", f"{b} 已经有结果（{st}），不能再 {e['to']}")
                elif e["to"] in OCCURRED:
                    if e["to"] == "happened":            # W-1 的 check_effects 同样报（后端 2026-10-10）
                        hit("R2-precondition", f"{b}：只有到点的系统事件写 happened，候选事件要早用 hastened（契约 2.4.1）")
                    bb = self.sim.beats[b]
                    if not self.sim.holds(bb["preconditions"], sim_state):
                        hit("R2-precondition", f"{b} 的前提不成立 {bb['preconditions']}")
                    if any(res["status"].get(f) not in OCCURRED for f, ty, _ in self.sim.parents[b] if ty == "requires"):
                        hit("R2-precondition", f"{b} 要求的前一个节拍还没发生")
            elif op == "set":
                v = e["var"]
                locked = self.anchor_locked(res)
                if v in locked and e["value"] != locked[v]:
                    hit("R1-anchor", f"{v} = {locked[v]!r} 是锚点节拍的结果，不能改成 {e['value']!r}")
                if v in TERMINAL and sim_state.get(v) == TERMINAL[v] and e["value"] != TERMINAL[v]:
                    hit("R2-precondition", f"{v} 已经是 {TERMINAL[v]}，死者不复活（rule.no-resurrection）")
                if v == "var.player.location":
                    if e["value"] not in self.reach(role, sim_state, set()):
                        hit("R7-capability", f"{role['id']} 进不了 {e['value']}（access 和此刻成立的 conditionalAccess）")
                    d = self.dist(ppl, e["value"])
                    if d > c["dt"]:
                        hit("R3-time", f"玩家从 {ppl} 到 {e['value']} 至少 {d} 分，事件只给 {c['dt']} 分")
            elif op == "relocate":
                ch, frm = e["character"], where.get(e["character"])
                if any(state.get(v) == TERMINAL[v] for v in TERMINAL if v == "var.hostage.fate") and \
                        state.get("var.hostage.who") == ch:
                    hit("R2-precondition", f"{ch} 已经被处刑，死者不复活")
                d = self.dist(frm, e["place"]) if frm else 0
                if d > c["dt"]:
                    hit("R3-time", f"{ch} 从 {frm} 到 {e['place']} 至少 {d} 分，事件只给 {c['dt']} 分")
            elif op == "learn":
                f = e["fact"]
                if not self.fact_true(f, res):
                    hit("R4-knowledge", f"{f} 此刻还不成立（trueFrom {self.facts[f]['trueFrom']} 没发生）")
                elif not self.knows(actor, f, res, learned, role):
                    hit("R4-knowledge", f"{actor} 此刻不知道 {f}")
            elif op == "improv":
                ch = e["character"]
                for fid, f in self.facts.items():
                    terms = [x for x in f.get("spoilerTerms") or [] if x in e["statement"]]
                    if terms and not self.knows(ch, fid, res, learned, role):
                        hit("R4-knowledge", f"即兴设定里有 {fid} 的剧透词 {terms}，{ch} 此刻不知道它")
            elif op == "hold" and actor == "player":
                if sim_state.get(e["item"]) != "player":
                    hit("R7-capability", f"{e['item']} 不在玩家手上（现在在 {sim_state.get(e['item'])}）")
                tgt = e.get("to")
                if tgt not in (None, "player") and where.get(tgt) != ppl and state["var.player.companionOf"] != tgt:
                    hit("R7-capability", f"{tgt} 在 {where.get(tgt)}，玩家在 {ppl}，交不到他手上")
            # 契约 1.6（C-16）StateVar.valueRequires：王的心（信任 40 / 70）、过桥渡河（桥还在）等，只读世界模型
            for x in self.sim.value_requires([e], sim_state):
                now = {cnd["var"]: sim_state.get(cnd["var"]) for cnd in x["when"]}
                hit("R2-precondition", f"{x['var']} = {x['value']!r} 要 {x['when']}，此刻 {now}（{x['note']}）")
            self.sim.apply([e], sim_state, None)

        act = turn.get("act")
        if act and act.get("affordance"):
            a = self.affs.get(act["affordance"])
            if not a:
                errs.append(f"动作不存在 {act['affordance']}")
            else:
                if a["place"] != ppl:
                    hit("R7-capability", f"{a['id']} 只能在 {a['place']} 做，玩家在 {ppl}")
                if a.get("roles") and role["id"] not in a["roles"]:
                    hit("R7-capability", f"{a['id']} 只有 {a['roles']} 能做")
                if a.get("when") and not self.sim.holds(a["when"], state):
                    hit("R7-capability", f"{a['id']} 的条件此刻不成立 {a['when']}")
                it = self.items.get(a.get("item"))
                if it and not it.get("portable") and ppl not in it.get("at", []):
                    hit("R7-capability", f"{a['id']} 要 {it['id']}，这里没有")
        return hits, why, errs

    # ---------- 格式 ----------
    def check_item(self, item, where):
        errs = []
        for k in set(item) - ITEM_KEYS:
            errs.append(f"{where}：不认识的字段 {k}")
        c, lb, turn = item.get("candidate", {}), item.get("label", {}), item.get("turn", {})
        for k in set(c) - CAND_KEYS:
            errs.append(f"{where}：candidate 不认识的字段 {k}")
        for k in set(lb) - LABEL_KEYS:
            errs.append(f"{where}：label 不认识的字段 {k}")
        for k in set(turn) - TURN_KEYS:
            errs.append(f"{where}：turn 不认识的字段 {k}")
        if not (turn.get("player") or turn.get("act")):
            errs.append(f"{where}：turn 要有玩家原话或动作")
        if c.get("type") not in EVENT_TYPES or c.get("origin") not in ORIGINS:
            errs.append(f"{where}：type / origin 不对 {c.get('type')} / {c.get('origin')}")
        if not isinstance(c.get("dt"), int) or c["dt"] < 0:
            errs.append(f"{where}：dt 要是非负整数")
        if not JA.search(c.get("summary", "")):
            errs.append(f"{where}：summary 要是日语")
        for x in c.get("causes", []):
            if x not in self.sim.beats:
                errs.append(f"{where}：causes 里的节拍不存在 {x}")
        if c.get("beneficiary") not in (None, "player") and c["beneficiary"] not in self.chars:
            errs.append(f"{where}：beneficiary 不对")
        n0 = len(self.ck.errors)
        self.ck.check_effects(c.get("effects", []), where)
        errs += self.ck.errors[n0:]
        del self.ck.errors[n0:]
        for e in c.get("effects", []):
            if e.get("op") == "improv" and not (RF_ID.match(str(e.get("factId", ""))) and JA.search(e.get("statement", ""))):
                errs.append(f"{where}：improv 要有「rf_ + ULID」的 factId（用 fake_ulid）和日语 statement")
        v, fr, aa = lb.get("verdict"), lb.get("failedRules", []), lb.get("acceptAlso", [])
        if v not in ("pass", "fail"):
            errs.append(f"{where}：verdict 只能是 pass / fail")
        if any(r not in RULES for r in fr + aa):
            errs.append(f"{where}：规则名不对 {fr + aa}")
        if v == "pass" and (fr or aa or lb.get("stage") or lb.get("fix")):
            errs.append(f"{where}：合规的不写 failedRules / acceptAlso / stage / fix")
        if v == "fail":
            if not fr:
                errs.append(f"{where}：违规的要写 failedRules")
            if lb.get("stage") not in ("rules", "model"):
                errs.append(f"{where}：违规的 stage 只能是 rules / model")
            elif lb["stage"] == "rules" and fr and fr[0] not in DET_RULES:
                errs.append(f"{where}：主规则 {fr[0]} 不是确定性规则，stage 不能是 rules")
            if not lb.get("fix"):
                errs.append(f"{where}：违规的要写 fix（怎样改写、降级或拒绝才对）")
            if set(fr) & set(aa):
                errs.append(f"{where}：acceptAlso 不和 failedRules 重复")
        if not lb.get("rationale") or not lb.get("refs"):
            errs.append(f"{where}：要写 rationale 和 refs")
        for r in lb.get("refs", []):
            if r not in self.ids:
                errs.append(f"{where}：refs 里的 ID 不存在 {r}")
        for t in item.get("tags", []):
            if t not in TAGS:
                errs.append(f"{where}：不认识的 tag {t}")
        # 摘要只写故事里的行为：不照抄玩家原话、不含个人信息（违反就是 R6），除非这条就是测它的
        tags = set(item.get("tags", []))
        said = turn.get("player", "")
        if said and "verbatim-quote" not in tags and lcs_len(said, c.get("summary", "")) >= 8:
            errs.append(f"{where}：summary 照抄了玩家原话 8 字以上（不是测 R6 的条目就改写）")
        texts = [turn.get("player", ""), turn.get("reply", ""), c.get("summary", "")] + \
            [e.get("statement", "") + e.get("text", "") for e in c.get("effects", [])]
        if "pii" not in tags and any(PII.search(x) for x in texts):
            errs.append(f"{where}：有像电话、邮箱、邮编的字串（只许出现在 pii 条目）")
        if errs:
            return errs
        hits, why, jerr = self.judge(item)
        if jerr:
            return [f"{where}：{x}" for x in jerr]
        if v == "fail" and lb["stage"] == "rules":
            if fr[0] not in hits:
                errs.append(f"{where}：标成 rules 的违规，判法没报出主规则 {fr[0]}（报了 {sorted(hits)}）")
            extra = hits - set(fr) - set(aa)
            if extra:
                errs.append(f"{where}：判法多报了 {sorted(extra)}：{why}")
        elif hits:
            errs.append(f"{where}：{'合规的' if v == 'pass' else '标成 model 的'}条目被确定性判法报了 {why}")
        return errs


def load(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def fill_t(items, world_path=WORLD, scen_path=SCENARIOS):
    """candidate.t 省略 = 检查点的时钟。生成器调用。"""
    s2 = S2(json.loads(Path(world_path).read_text(encoding="utf-8")), json.loads(Path(scen_path).read_text(encoding="utf-8")))
    for it in items:
        if "t" not in it["candidate"]:
            res, _, _, err = s2.state_at(it["setup"])
            if err:
                raise SystemExit(f"{it['id']}：{err}")
            it["candidate"] = {"t": res["t"], **it["candidate"]}
    return items


def check_all(items, world_path=WORLD, scen_path=SCENARIOS):
    world = json.loads(Path(world_path).read_text(encoding="utf-8"))
    scen = json.loads(Path(scen_path).read_text(encoding="utf-8"))
    s2 = S2(world, scen)
    errs, seen = [], set()
    for it in items:
        if it.get("id") in seen:
            errs.append(f"id 重复 {it.get('id')}")
        seen.add(it.get("id"))
        errs += s2.check_item(it, it.get("id", "?"))
    return s2, errs


def scope_gap(items):
    """backend-design v1.0.9 2.4：第 4 步（模型检查）跑过了第 3 步、effects 不为空的全部候选事件；
    R6 的规则部分（电话、邮箱、地址的模式，和原话连续 8 字相同）在第 3 步对每条摘要都跑。
    标成 model 的违规里，effects 为空、又不是这两种 R6 的 → 按这个范围到不了任何检查。"""
    def r6_rules(it):
        return it["label"]["failedRules"][0] == "R6-safety" and {"pii", "verbatim-quote"} & set(it.get("tags", []))
    return [it["id"] for it in items if it["label"]["verdict"] == "fail" and it["label"]["stage"] == "model"
            and not it["candidate"]["effects"] and not r6_rules(it)]


def summary(items):
    from collections import Counter
    fails = [i for i in items if i["label"]["verdict"] == "fail"]
    by = Counter(i["label"]["failedRules"][0] for i in fails)
    st = Counter(i["label"]["stage"] for i in fails)
    return (f"{len(items)} 条：违规 {len(fails)}（" + "、".join(f"{r.split('-')[0]} {by[r]}" for r in RULES if by[r]) +
            f"；规则判得出 {st['rules']}、要读懂意思 {st['model']}），合规 {len(items) - len(fails)}；"
            f"按第 4 步的范围（backend-design v1.0.9）会漏看的违规 {len(scope_gap(items))} 条")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--world", default=str(WORLD))
    ap.add_argument("--scenarios", default=str(SCENARIOS))
    a = ap.parse_args()
    items = load(a.path)
    _, errs = check_all(items, a.world, a.scenarios)
    for e in errs:
        print("错误：" + e)
    print(summary(items) + f"；错误 {len(errs)}")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
