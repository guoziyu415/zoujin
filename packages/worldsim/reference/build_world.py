#!/usr/bin/env python3
"""世界模型构建与校验（新增一本书流水线的第 2 步「自动校验」原型）。

用法：
  python3 -I build_world.py --src world.src.json --text melos_plain.txt --out world.json --report report.md \
      [--scenarios scenarios.json]

做的事：
1. 出处定位：每个 {"q": 引文, "p": 段落号(可省)} 必须是规范化原文某一段的精确子串。
   省略 p 时自动定位；找不到或在多段出现（且没给 p）都算错误。
   输出时展开成 contracts.md 的 Cite：{source, para, quote}。
2. 引用完整性：所有 ID 唯一；knows / since / place / participants / var / anchors / causal / roles 的引用都存在；
   状态变量的取值符合类型和枚举；（1.6，C-16）valueRequires 的 value 在这个变量的取值里，when 引用的变量存在、取值合法；节拍以外的效果模板把变量设成受限的值时给警告。
3. 时间：节拍 earliest <= canonical <= latest；按 order 排列时 canonical 不倒退；期限 = Day 3 日没。
4. 知情范围：角色「从 X 起知道 F」时，F 必须在 X 之前（或同时）已经成立。
5. 因果图无环；from 的 canonical 不晚于 to。
6. 设计层：场景（sceneRef）、幕（acts，开始/收幕/幕末去处）、身份（release、startAct、conditionalAccess）、世界结局（endings）、
   时刻标签（clock.labels）、人物的互助 / 约定 / 打算（S-029、S-030、S-048）、情境动作和物品（affordances / items，
   contracts 2.10；第四幕让他慢和帮他快并排，S-036 ②）、节拍上的人物状态（activities）、台词和动机的生效时间（since / until / when）、
   （1.4）设计台词、互助的效果、节拍的变体、过场二选一（enRoute）都成立。
7. 情景模拟（--scenarios）：按 contracts 2.5 的时间传播规则推演原著路径和若干改道情景，
   检查原著路径每个节拍都发生、每个情景落到预期的世界结局（和预期的节拍状态、变体）、每类底线世界结局都能走到；
   （1.4）第四幕按钮上的 melosMinutes 和共享规则算出的梅洛斯到达时间差一致；（1.5）过场选项的 melosMinutes 也一样。
8. 覆盖率：被引用的段落占全文段落的比例，列出未被引用的段落。
只用标准库。
"""
import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from worldsim import Sim  # noqa: E402  共用的推演规则（contracts 2.4.1 / 2.5.1）

CONTRACT_VERSION = "1.6"  # contracts.md 的版本
errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def load_text(path):
    raw = Path(path).read_bytes()
    paras = raw.decode("utf-8").rstrip("\n").split("\n")
    return paras, hashlib.sha256(raw).hexdigest()


def make_cite_resolver(paras, source_id, used):
    def resolve(c, where):
        q, p = c.get("q"), c.get("p")
        if not q:
            err(f"{where}: 引文为空")
            return None
        if p is not None:
            if not (1 <= p <= len(paras)) or q not in paras[p - 1]:
                err(f"{where}: 引文不在第 {p} 段：「{q}」")
                return None
        else:
            hits = [i + 1 for i, para in enumerate(paras) if q in para]
            if not hits:
                err(f"{where}: 原文中找不到引文：「{q}」")
                return None
            if len(hits) > 1:
                err(f"{where}: 引文出现在多段 {hits}，请加 p：「{q}」")
                return None
            p = hits[0]
        if len(q) > 80:
            warn(f"{where}: 引文超过 80 字（{len(q)} 字）")
        used[p].append(where)
        out = {"source": source_id, "para": p, "quote": q}
        for k in ("since", "until", "when"):  # sampleLines 的生效时间（contracts 2.1，1.1；when 是 1.4）
            if k in c:
                out[k] = c[k]
        return out
    return resolve


def expand_cites(obj, resolve, path="$"):
    """把对象树里所有 cite / sampleLines 的 {q,p} 展开成 Cite。"""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            here = f"{path}.{k}"
            if k in ("cite", "sampleLines") and isinstance(v, list):
                out[k] = [r for i, c in enumerate(v) if (r := resolve(c, f"{here}[{i}]")) is not None]
            else:
                out[k] = expand_cites(v, resolve, here)
        return out
    if isinstance(obj, list):
        return [expand_cites(v, resolve, f"{path}[{i}]") for i, v in enumerate(obj)]
    return obj


def label(obj, default):
    return obj.get("id", default) if isinstance(obj, dict) else default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--scenarios")
    a = ap.parse_args()

    src = json.loads(Path(a.src).read_text(encoding="utf-8"))
    paras, sha = load_text(a.text)
    s = src["book"]["source"]
    source_id = f"{s['provider']}:{s['fileId']}@sha256:{sha[:12]}"
    used = defaultdict(list)
    resolve = make_cite_resolver(paras, source_id, used)

    # 用可读的路径名（实体 ID）替代数组下标，报告更好读
    def named(obj, path):
        if isinstance(obj, list):
            return [named(v, f"{path}/{label(v, i)}") for i, v in enumerate(obj)]
        if isinstance(obj, dict):
            return {k: (named(v, f"{path}.{k}") if k not in ("cite", "sampleLines") else v) for k, v in obj.items()}
        return obj

    world = expand_cites(src, resolve, "$")
    world.pop("_authoring", None)
    world["book"]["source"]["textSha256"] = sha

    # ---------- ID 与引用 ----------
    if world.get("schemaVersion") != CONTRACT_VERSION:
        err(f"schemaVersion 要是契约版本 {CONTRACT_VERSION}，现在 {world.get('schemaVersion')}")
    ids = {}
    for kind in ("characters", "places", "facts", "beats", "stateVars", "roles", "causal", "globalRules", "scenes", "acts", "affordances", "items"):
        for x in world.get(kind, []):
            if x["id"] in ids:
                err(f"ID 重复：{x['id']}")
            ids[x["id"]] = kind
    for c in world["characters"]:
        for x in c.get("mutualAid", []) + c.get("promiseTemplates", []):
            if x["id"] in ids:
                err(f"ID 重复：{x['id']}")
            ids[x["id"]] = "characters"
    chars = {c["id"] for c in world["characters"]}
    tmpl_ids = {x["id"] for c in world["characters"] for x in c.get("promiseTemplates", [])}
    item_map = {x["id"]: x for x in world.get("items", [])}
    places = {p["id"] for p in world["places"]}
    facts = {f["id"]: f for f in world["facts"]}
    beats = {b["id"]: b for b in world["beats"]}
    svars = {v["id"]: v for v in world["stateVars"]}
    scenes = {x["id"]: x for x in world.get("scenes", [])}
    acts = {x["id"]: x for x in world.get("acts", [])}

    def beat_t(bid):
        return -1 if bid == "pre" else beats[bid]["window"]["canonical"]

    def check_value(var, value, where):
        v = svars.get(var)
        if v is None:
            err(f"{where}: 未定义的状态变量 {var}")
            return
        if isinstance(value, list):          # op "in"
            for x in value:
                check_value(var, x, where)
            return
        t = v["type"]
        if t == "enum" and value not in v["values"]:
            err(f"{where}: {var} 的取值 {value!r} 不在枚举 {v['values']}")
        if t == "bool" and not isinstance(value, bool):
            err(f"{where}: {var} 需要 bool，得到 {value!r}")
        if t == "int" and not isinstance(value, (int, float)):
            err(f"{where}: {var} 需要数值，得到 {value!r}")
        if t == "place" and value not in places and value != "role.startPlace":
            err(f"{where}: {var} 需要地点 ID，得到 {value!r}")

    def check_effects(effs, where):
        for e in effs:
            op = e.get("op")
            if op == "set":
                check_value(e["var"], e["value"], where)
            elif op == "inc":
                if e["var"] not in svars or svars[e["var"]]["type"] != "int":
                    err(f"{where}: inc 只能用于 int 变量：{e['var']}")
            elif op == "relocate":
                if e["character"] not in chars or e["place"] not in places:
                    err(f"{where}: relocate 引用不存在：{e}")
            elif op == "learn":
                if e["character"] not in chars or e["fact"] not in facts:
                    err(f"{where}: learn 引用不存在：{e}")
            elif op == "beat":
                if e["beat"] not in beats:
                    err(f"{where}: beat 引用不存在：{e}")
                if e.get("to") == "altered":
                    check_effects(e.get("outcomes", []), where)
            elif op == "hold":                   # 1.3：随身物品换手
                it = item_map.get(e.get("item"))
                if not it or not it.get("portable"):
                    err(f"{where}: hold 只能用于 portable 的物品：{e.get('item')}")
                for k in ("to", "from"):
                    if k in e and e[k] is not None and e[k] != "player" and e[k] not in chars:
                        err(f"{where}: hold.{k} 要是 player、人物 ID 或 null")
                if "to" not in e:
                    err(f"{where}: hold 要写 to（null = 被拿走、用掉）")
            elif op == "promise":                # 1.1；世界模型里只出现在情境动作的效果模板，promiseId 提交时分配
                if e.get("change") != "made" or not e.get("text"):
                    err(f"{where}: 效果模板里的 promise 只能是 change=made，且要有 text")
                for k in ("from", "to"):
                    if e.get(k) != "player" and e.get(k) not in chars:
                        err(f"{where}: promise.{k} 要是 player 或人物 ID")
                if e.get("template") and e["template"] not in tmpl_ids:
                    err(f"{where}: promise.template 不存在 {e['template']}")
            else:
                err(f"{where}: 未知 op {op}")

    for v in world["stateVars"]:
        if v["type"] != "place":
            check_value(v["id"], v["default"], f"{v['id']}.default")
        for key in v.get("valueLabels", {}):
            val = {"true": True, "false": False}.get(key, key) if v["type"] == "bool" else key
            check_value(v["id"], val, f"{v['id']}.valueLabels")
        if v.get("valueLabels") and not v.get("visibleToPlayer"):
            warn(f"{v['id']}: 有 valueLabels 但没有标 visibleToPlayer")
        for r in v.get("valueRequires", []):     # 1.6，C-16
            check_value(v["id"], r["value"], f"{v['id']}.valueRequires")
            if not r.get("when"):
                err(f"{v['id']}.valueRequires: {r['value']!r} 的 when 是空的")
            for cnd in r.get("when", []):
                check_value(cnd["var"], cnd["value"], f"{v['id']}.valueRequires[{r['value']!r}].when")
            if not r.get("note"):
                err(f"{v['id']}.valueRequires: {r['value']!r} 要写 note（叙事者的 reason 用它）")

    # 1.6：除了到点的节拍（origin = schedule），互助、幕末去处、情境动作这些效果模板运行时都按 valueRequires 判，
    # 模板把变量设成受限的值，when 不成立时叙事者会按 R2 否决。现在没有这种模板，以后加世界模型时早点看到
    limited = {(v["id"], r["value"]): r["when"] for v in world["stateVars"] for r in v.get("valueRequires", [])}

    def limited_templates(x, owner):
        if isinstance(x, dict):
            owner = x.get("id", owner)
            for k, y in x.items():
                for e in y if k in ("effects", "outcomes") and isinstance(y, list) else []:
                    if isinstance(e, dict) and e.get("op") == "set" and (e.get("var"), e.get("value")) in limited:
                        when = limited[(e["var"], e["value"])]
                        warn(f"{owner}: 把 {e['var']} 设成 {e['value']!r}，运行时要 {when} 成立，不成立叙事者按 R2 否决")
                limited_templates(y, owner)
        elif isinstance(x, list):
            for y in x:
                limited_templates(y, owner)

    for k, x in world.items():
        if k != "beats":                         # 节拍到点发生（origin = schedule），结果由节拍前提管
            limited_templates(x, k)

    for c in world["characters"]:
        if c["initialPlace"] not in places:
            err(f"{c['id']}: initialPlace 不存在 {c['initialPlace']}")
        if not c.get("cite"):
            err(f"{c['id']}: 缺少出处")
        for k in c["knows"]:
            if k["fact"] not in facts:
                err(f"{c['id']}: knows 引用不存在的事实 {k['fact']}")
                continue
            if k["since"] != "pre" and k["since"] not in beats:
                err(f"{c['id']}: knows.since 引用不存在的节拍 {k['since']}")
                continue
            tf = facts[k["fact"]]["trueFrom"]
            if beat_t(k["since"]) < beat_t(tf):
                err(f"{c['id']}: 从 {k['since']} 起就知道 {k['fact']}，但该事实到 {tf} 才成立（剧透）")

    for f in world["facts"]:
        if any(not isinstance(x, str) or not x for x in f.get("spoilerTerms", [])):
            err(f"{f['id']}: spoilerTerms 要是非空字符串")
        if f["trueFrom"] != "pre" and f["trueFrom"] not in beats:
            err(f"{f['id']}: trueFrom 引用不存在的节拍 {f['trueFrom']}")
        if not f.get("cite"):
            err(f"{f['id']}: 缺少出处")

    for p in world["places"]:
        for adj in p.get("adjacent", []):
            if adj["place"] not in places:
                err(f"{p['id']}: adjacent 引用不存在 {adj['place']}")
        if not p.get("cite"):
            err(f"{p['id']}: 缺少出处")
        if p.get("sceneRef") is not None and p["sceneRef"] not in scenes:
            err(f"{p['id']}: sceneRef 不存在 {p['sceneRef']}")
    for sc in scenes.values():
        if not any(p.get("sceneRef") == sc["id"] for p in world["places"]):
            err(f"{sc['id']}: 没有任何地点指向这个场景")

    # ---------- 节拍与时间 ----------
    ordered = sorted(world["beats"], key=lambda b: b["order"])
    prev = None
    for b in ordered:
        w = b["window"]
        if not (w["earliest"] <= w["canonical"] <= w["latest"]):
            err(f"{b['id']}: 时间窗不成立 {w}")
        if b["place"] not in places:
            err(f"{b['id']}: 地点不存在 {b['place']}")
        for ch in b["participants"]:
            if ch not in chars:
                err(f"{b['id']}: 参与者不存在 {ch}")
        for cnd in b["preconditions"]:
            check_value(cnd["var"], cnd["value"], f"{b['id']}.preconditions")
        check_effects(b["outcomes"], f"{b['id']}.outcomes")
        for v in b.get("variants", []):                   # 1.4：到点时按状态换一种演法
            wv = f"{b['id']}.variants/{v.get('id')}"
            if not v.get("id") or v["id"] in ids:
                err(f"{wv}: 变体要有唯一的 id")
            ids[v.get("id")] = "beats"
            if not v.get("when") or not v.get("summary") or v.get("inferred") is not True:
                err(f"{wv}: 变体要有 when、summary，且 inferred: true")
            for cnd in v.get("when", []):
                check_value(cnd["var"], cnd["value"], wv)
            check_effects(v.get("outcomes", []), wv)
        if b.get("variants") and b["kind"] == "anchor":
            err(f"{b['id']}: 锚点节拍不能有变体（R1）")
        if not b.get("cite"):
            err(f"{b['id']}: 缺少出处")
        world_event = b["kind"] == "anchor" and not b["participants"]  # 天气等世界事件，原著可以晚些才写到
        if prev and not world_event and w["canonical"] < prev["window"]["canonical"]:
            warn(f"{b['id']}（order {b['order']}）的 canonical 时间早于 {prev['id']}，原著顺序与时间不一致")
        if not world_event:
            prev = b

    clk = world["clock"]
    expect_deadline = 3 * 1440 + clk["sunsetMinuteOfDay"]
    if clk["deadline"]["t"] != expect_deadline:
        err(f"期限 {clk['deadline']['t']} 不等于 Day 3 日没 {expect_deadline}")
    for r in clk.get("onDeadline", []):
        for cnd in r["if"]:
            check_value(cnd["var"], cnd["value"], "clock.onDeadline.if")
        check_effects(r["then"], "clock.onDeadline.then")

    # ---------- 因果 ----------
    graph = defaultdict(list)
    for e in world["causal"]:
        for end in (e["from"], e["to"]):
            if end not in beats and end not in svars:
                err(f"{e['id']}: 引用不存在 {end}")
        if e["from"] in beats and e["to"] in beats:
            graph[e["from"]].append(e["to"])
            if beat_t(e["from"]) > beat_t(e["to"]):
                warn(f"{e['id']}: from 的时间晚于 to")
        if not e.get("inferred") and not e.get("cite"):
            warn(f"{e['id']}: 标为非推断但没有出处")
        if e["type"] in ("delays", "hastens") and not isinstance(e.get("minutes"), int):
            err(f"{e['id']}: {e['type']} 边需要整数 minutes")
    seen, stack = set(), set()

    def dfs(n):
        if n in stack:
            err(f"因果图有环，经过 {n}")
            return
        if n in seen:
            return
        seen.add(n); stack.add(n)
        for m in graph[n]:
            dfs(m)
        stack.discard(n)
    for n in list(graph):
        dfs(n)

    for e in world["causal"]:
        if "timeLink" in e and (e["timeLink"] not in ("shift", "order") or e["type"] not in ("enables", "requires")):
            err(f"{e['id']}: timeLink 只能是 shift / order，且只用于 enables / requires（contracts 2.5.1，1.1）")

    # ---------- 角色、锚点 ----------
    for r in world["roles"]:
        if r["startPlace"] not in places:
            err(f"{r['id']}: startPlace 不存在")
        for x in r["knownCharacters"]:
            if x not in chars:
                err(f"{r['id']}: knownCharacters 不存在 {x}")
        for x in r["access"]:
            if x not in places:
                err(f"{r['id']}: access 不存在 {x}")
        for ca in r.get("conditionalAccess", []):
            if ca["place"] not in places:
                err(f"{r['id']}: conditionalAccess 地点不存在 {ca['place']}")
            if not ca.get("when"):
                err(f"{r['id']}: conditionalAccess 要写 when")
            for cnd in ca.get("when", []):
                check_value(cnd["var"], cnd["value"], f"{r['id']}.conditionalAccess")
        for x in r["initialKnowledge"]:
            if x not in facts:
                err(f"{r['id']}: initialKnowledge 不存在 {x}")
            elif facts[x]["trueFrom"] != "pre" and beat_t(facts[x]["trueFrom"]) > r["startT"]:
                err(f"{r['id']}: 开局就知道 {x}，但该事实开局时还没成立")
    for r in world["roles"]:
        if r.get("release") not in (1, 2, 3):
            err(f"{r['id']}: release 应为 1/2/3")
        act = acts.get(r.get("startAct"))
        if act is None:
            err(f"{r['id']}: startAct 不存在 {r.get('startAct')}")
        else:
            if not (act["start"]["t"] <= r["startT"] <= act["end"]["atLatest"]):
                err(f"{r['id']}: startT {r['startT']} 不在 {act['id']} 的时间内")
            sref = next((p.get("sceneRef") for p in world["places"] if p["id"] == r["startPlace"]), None)
            if sref not in act["scenes"]:
                err(f"{r['id']}: 起点场景 {sref} 不在 {act['id']} 的场景里")

    # ---------- 幕（S-004） ----------
    enroute_minutes = []   # 1.5：(位置, 选项, 选的时刻) —— 情景模拟时核对 melosMinutes
    for i, act in enumerate(sorted(acts.values(), key=lambda x: x["order"])):
        where = act["id"]
        if act["order"] != i + 1:
            err(f"{where}: order 应连续，从 1 开始")
        if act["start"]["t"] > act["end"]["atLatest"]:
            err(f"{where}: 开始时间晚于最迟收幕时间")
        for b in act["end"]["onBeats"]:
            if b not in beats:
                err(f"{where}: 收幕节拍不存在 {b}")
            elif not (act["start"]["t"] <= beats[b]["window"]["canonical"] <= act["end"]["atLatest"]):
                err(f"{where}: 收幕节拍 {b} 的原著时间不在本幕内")
        for sc in act["scenes"]:
            if sc not in scenes:
                err(f"{where}: 场景不存在 {sc}")
        if not act["exits"] and act["order"] != len(acts):
            err(f"{where}: 不是最后一幕却没有幕末去处")
        for ex in act["exits"]:
            w2 = f"{where}/{ex['id']}"
            to = acts.get(ex["toAct"])
            if to is None or to["order"] <= act["order"]:
                err(f"{w2}: toAct 无效 {ex['toAct']}")
                continue
            if ex["place"] not in places:
                err(f"{w2}: 地点不存在 {ex['place']}")
            else:
                sref = next(p.get("sceneRef") for p in world["places"] if p["id"] == ex["place"])
                if sref not in to["scenes"]:
                    err(f"{w2}: 去处的场景 {sref} 不在 {to['id']} 的场景里")
            if not (to["start"]["t"] <= ex["t"] <= to["end"]["atLatest"]):
                err(f"{w2}: 跳到的时间 {ex['t']} 不在 {to['id']} 内")
            if ex.get("alignTo") and ex["alignTo"] not in beats:
                err(f"{w2}: alignTo 节拍不存在 {ex['alignTo']}")
            for r in ex.get("roles", []):
                if r not in {x["id"] for x in world["roles"]}:
                    err(f"{w2}: 身份不存在 {r}")
            for cnd in ex.get("requires", []):
                check_value(cnd["var"], cnd["value"], f"{w2}.requires")
            check_effects(ex.get("effects", []), f"{w2}.effects")
            er = ex.get("enRoute")                        # 1.4：过场二选一（UX 校对 3.2）
            if er:
                eb = beats.get(er.get("beat"))
                chs = er.get("choices", [])
                ends = [beats[b]["window"]["canonical"] for b in act["end"]["onBeats"] if b in beats]
                if eb is None:
                    err(f"{w2}.enRoute: 节拍不存在 {er.get('beat')}")
                elif eb["kind"] == "anchor":
                    err(f"{w2}.enRoute: 锚点节拍不能改 {eb['id']}")
                else:
                    if not (min(ends, default=act["start"]["t"]) <= eb["window"]["canonical"] <= ex["t"]):
                        err(f"{w2}.enRoute: {eb['id']} 不在跳过的这段路上（收幕 {ends} 到 {ex['t']} 之间）")
                if not er.get("line") or len(chs) != 2 or any(not x.get("label") for x in chs):
                    err(f"{w2}.enRoute: 要有 line 和正好两个带 label 的选项")
                elif chs[-1].get("effects") or chs[-1].get("melosMinutes") or chs[-1].get("after"):
                    err(f"{w2}.enRoute: 最后一个选项是「照原作」，effects 要为空，也不写 melosMinutes、after")
                for x in chs:
                    check_effects(x.get("effects", []), f"{w2}.enRoute")
                    moves = any(e.get("op") == "beat" for e in x.get("effects", []))   # 1.5：按钮上写对梅洛斯的影响
                    if moves and not isinstance(x.get("melosMinutes"), int):
                        err(f"{w2}.enRoute「{x.get('label')}」: 改节拍的选项要写整数 melosMinutes（contracts 2.8，1.5）")
                    elif moves:
                        enroute_minutes.append((f"{w2}.enRoute「{x['label']}」", x, max(ends, default=act["start"]["t"])))
                    if "after" in x and not (isinstance(x["after"], str) and x["after"]):
                        err(f"{w2}.enRoute「{x.get('label')}」: after 要是一句日语")
    used_scenes = {sc for act in acts.values() for sc in act["scenes"]}
    for sc in scenes:
        if sc not in used_scenes:
            warn(f"{sc}: 没有任何一幕用到这个场景")

    # ---------- 人物的互助、约定、打算（S-029、S-030、S-048） ----------
    role_ids = {x["id"] for x in world["roles"]}
    for c in world["characters"]:
        w2 = c["id"]
        aids = c.get("mutualAid", [])
        for x in aids:
            if x.get("direction") not in ("forYou", "fromYou") or not x.get("text"):
                err(f"{w2}/{x['id']}: direction 要是 forYou / fromYou，text 不能空")
            if x.get("opening") and x["opening"] not in role_ids:
                err(f"{w2}/{x['id']}: opening 的身份不存在 {x['opening']}")
            if "major" in x and (x["major"] is not True or x["direction"] != "forYou"):
                err(f"{w2}/{x['id']}: major 只能写 true，而且只用于 forYou（S-041 的「为你做的一件大事」）")
            for cnd in x.get("when", []):
                check_value(cnd["var"], cnd["value"], f"{w2}/{x['id']}.when")
            check_effects(x.get("effects", []), f"{w2}/{x['id']}.effects")     # 1.4
            if not x.get("inferred") and not x.get("cite"):
                err(f"{w2}/{x['id']}: 不是推断就要有出处")
        for x in c.get("promiseTemplates", []):
            if x.get("by") != "player" and x.get("by") not in chars:
                err(f"{w2}/{x['id']}: by 要是 player 或人物 ID")
        for x in c.get("plans", []):
            if x.get("act") not in acts or not x.get("text"):
                err(f"{w2}: plans 的幕不存在或 text 为空 {x.get('act')}")
            if not x.get("inferred") and not x.get("cite"):
                err(f"{w2}: plans[{x.get('act')}] 不是推断就要有出处")
        if c["talkable"]:
            dirs = {x.get("direction") for x in aids}
            if dirs != {"forYou", "fromYou"}:
                err(f"{w2}: 能对话的人物至少要有一种「他能为你做的」和一种「你能为他做的」（S-029），现在 {sorted(d for d in dirs if d)}")
            if not c.get("plans"):
                err(f"{w2}: 能对话的人物要有打算（S-030）")
    for r in world["roles"]:
        if r.get("release") != 1:
            continue
        dirs = {x["direction"] for c in world["characters"] for x in c.get("mutualAid", []) if x.get("opening") == r["id"]}
        if dirs != {"forYou", "fromYou"}:
            err(f"{r['id']}: 第一版身份要有一对开局互助（S-048），现在 {sorted(dirs)}")

    # ---------- 时刻标签（S-037、UX 4.2） ----------
    lab = clk.get("labels", {})
    if len(lab.get("days", [])) != 4:
        err("clock.labels.days 要有 4 个（約束の日〜三日目）")
    bands = lab.get("bands", [])
    if not bands or bands[0][0] != 0 or any(a[0] >= b[0] for a, b in zip(bands, bands[1:])) or bands[-1][0] >= 1440:
        err("clock.labels.bands 要从 0 开始、严格递增、小于 1440")
    if "{day}" not in lab.get("format", "") or "{band}" not in lab.get("format", ""):
        err("clock.labels.format 要含 {day} 和 {band}")

    # ---------- 情境动作和物品（contracts 2.10；S-036 ②、S-038、UX 5.1） ----------
    UX_ACTIONS = {"examine", "give", "follow", "block", "help", "wait", "go", "shortcut", "run-together", "hasten"}
    pace = world.get("pacing", {})
    lo, hi = pace.get("situationalMinMinutes", 0), pace.get("situationalMaxMinutes", 10**9)
    aid_dir = {x["id"]: x["direction"] for c in world["characters"] for x in c.get("mutualAid", [])}
    items = item_map
    role_items = {r["id"]: r.get("items", []) for r in world["roles"]}
    char_items = {c["id"]: c.get("items", []) for c in world["characters"]}
    gives = {x["gives"]: x["id"] for c in world["characters"] for x in c.get("mutualAid", []) if x.get("gives")}
    for c in world["characters"]:
        for x in c.get("mutualAid", []):
            if x.get("gives") and (x["direction"] != "forYou" or not items.get(x["gives"], {}).get("portable")):
                err(f"{x['id']}: gives 只用于 forYou，且要是 portable 的物品 {x['gives']}")
    for owner, lst in list(role_items.items()) + list(char_items.items()):
        for i in lst:
            if not items.get(i, {}).get("portable"):
                err(f"{owner}: items 里的 {i} 不存在或不是 portable")
    for it in items.values():
        if not it.get("name"):
            err(f"{it['id']}: 缺 name")
        if it.get("portable"):                 # 1.3：一件实物，开局最多在一个人物手里
            holders = [c for c, lst in char_items.items() if it["id"] in lst]
            in_roles = [r for r, lst in role_items.items() if it["id"] in lst]
            if len(holders) > 1 or (holders and in_roles):
                err(f"{it['id']}: 开局只能在一个人手里（人物 {holders}，身份 {in_roles}）")
            if not holders and not in_roles and it["id"] not in gives:
                warn(f"{it['id']}: 没有人开局拿着，也没有互助会交给玩家")
            if it.get("at"):
                warn(f"{it['id']}: portable 的物品一般不写 at")
        elif not it.get("at"):
            err(f"{it['id']}: 不能带在身上的物品要写 at（在哪里随手可得）")
        for pl in it.get("at", []):
            if pl not in places:
                err(f"{it['id']}: at 的地点不存在 {pl}")
    by_place = defaultdict(set)
    for af in world.get("affordances", []):
        w2 = af["id"]
        act = acts.get(af.get("act")) if af.get("act") else None
        if af.get("act") and act is None:
            err(f"{w2}: 幕不存在 {af.get('act')}")
        if af.get("place") not in places:
            err(f"{w2}: 地点不存在 {af.get('place')}")
        else:
            sref = next(p.get("sceneRef") for p in world["places"] if p["id"] == af["place"])
            if sref is None:
                err(f"{w2}: 地点 {af['place']} 没有场景，不能放动作")
            elif act is not None and sref not in act["scenes"]:
                err(f"{w2}: 地点的场景 {sref} 不在 {act['id']} 里")
        if af.get("kind") not in UX_ACTIONS:
            err(f"{w2}: kind 不在 UX 的动作清单里 {af.get('kind')}")
        if not af.get("label") or any(ch in af["label"] for ch in "（(0123456789"):
            err(f"{w2}: label 要是动词短语，不写耗时（前端用 minutes 拼）：{af.get('label')!r}")
        for r in af.get("roles", []):
            if r not in role_ids:
                err(f"{w2}: 身份不存在 {r}")
        if af.get("target") and af["target"] not in chars:
            err(f"{w2}: target 不是人物 {af['target']}")
        if af.get("kind") == "give" and af.get("item") not in items:
            err(f"{w2}: give 要有存在的 item，现在 {af.get('item')}")
        if af.get("item") in items and af.get("kind") == "give" and af["place"] not in items[af["item"]]["at"] \
                and not (af.get("roles") and all(af["item"] in role_items[r] for r in af["roles"])):
            err(f"{w2}: 在 {af['place']} 拿不到 {af['item']}（不在 at 的地点，身份开局也不带）")
        if af.get("aid") and aid_dir.get(af["aid"]) != "fromYou":
            err(f"{w2}: aid 要是 fromYou 的互助 {af.get('aid')}")
        m = af.get("minutes")
        if not isinstance(m, int) or m < 0:
            err(f"{w2}: minutes 要是非负整数")
        elif af.get("kind") not in ("examine", "wait", "go", "run-together") and not lo <= m <= hi:
            err(f"{w2}: 情境动作耗时 {m} 不在 pacing 的 {lo}〜{hi} 分之间（S-038）")
        for cnd in af.get("when", []):
            check_value(cnd["var"], cnd["value"], f"{w2}.when")
        effs = af.get("effects", [])
        check_effects(effs, w2)
        tos = set()
        for e in effs:
            if e.get("op") == "beat":
                if e.get("to") in ("delayed", "hastened") and not isinstance(e.get("minutes"), int):
                    err(f"{w2}: {e['to']} 要写整数 minutes")
                tos.add(e.get("to"))
        mel = af.get("melos")
        if mel == "delay":
            if "delayed" not in tos:
                err(f"{w2}: melos=delay 的效果里要有 delayed 的节拍")
            by_place[af["place"]].add("slower")
        elif mel == "hasten":
            if not tos & {"hastened", "prevented"}:
                err(f"{w2}: melos=hasten 的效果里要有 hastened 或 prevented 的节拍")
            by_place[af["place"]].add("faster")
        elif mel is not None:
            err(f"{w2}: melos 只能是 delay / hasten")
        if mel and (af.get("act") != "act.4" or af.get("target") != "char.melos"):
            err(f"{w2}: melos 只用于第四幕、对象是梅洛斯的动作")
        if mel and not isinstance(af.get("melosMinutes"), int):
            err(f"{w2}: 有 melos 的动作要写整数 melosMinutes（按钮上写对梅洛斯的影响，contracts 2.10，1.4）")
        elif mel and (af["melosMinutes"] > 0) != (mel == "delay"):
            err(f"{w2}: melosMinutes 的正负号和 melos={mel} 不一致")
    for pl, kinds in by_place.items():
        if kinds != {"slower", "faster"}:
            err(f"{pl}: 第四幕每处要同时有让他慢和帮他快的动作（S-036 ②），现在只有 {sorted(kinds)}")

    # ---------- 节拍上的人物状态、台词和动机的生效时间（contracts 2.1、2.4，1.1） ----------
    ACTIVITIES = {"idle", "walk", "run", "talk", "work", "sleep", "absent"}
    for b in world["beats"]:
        for x in b.get("activities", []):
            if x.get("character") not in chars or x.get("activity") not in ACTIVITIES:
                err(f"{b['id']}.activities: 人物或状态不对 {x}")
    for c in world["characters"]:
        if c.get("initialActivity", "idle") not in ACTIVITIES:
            err(f"{c['id']}: initialActivity 不在 {sorted(ACTIVITIES)}")
        rows = [("traits", x) for x in c["traits"]] + [("goals", x) for x in c["goals"]] + \
               [("sampleLines", x) for x in c["speech"]["sampleLines"]] + \
               [("designLines", x) for x in c["speech"].get("designLines", [])]
        for part, x in rows:
            for k in ("since", "until"):
                if k in x and x[k] not in beats:
                    err(f"{c['id']}.{part}: {k} 的节拍不存在 {x[k]}")
            for cnd in x.get("when", []):                 # 1.4
                check_value(cnd["var"], cnd["value"], f"{c['id']}.{part}.when")
            if part == "designLines" and (not x.get("text") or x.get("inferred") is not True):
                err(f"{c['id']}.designLines: 要有 text，且 inferred: true（原文的台词放 sampleLines）")
            if "since" in x and "until" in x and beat_t(x["since"]) >= beat_t(x["until"]):
                err(f"{c['id']}.{part}: since 要早于 until")

    # ---------- 世界结局（S-007、S-034）和结局署名（S-031 ⑤） ----------
    ending_defs = sorted(world.get("endings", {}).get("world", []), key=lambda x: x["order"])
    for en in ending_defs:
        for cnd in en["when"]:
            check_value(cnd["var"], cnd["value"], f"endings.{en['id']}")
    sig = world.get("endings", {}).get("signature", {})
    for v in sig.get("vars", []):
        if v not in svars:
            err(f"endings.signature: 状态变量不存在 {v}")
    for b in sig.get("beats", []):
        if b not in beats:
            err(f"endings.signature: 节拍不存在 {b}")
    wb = clk["deadline"].get("watchBeat")
    if wb is not None and wb not in beats:
        err(f"clock.deadline.watchBeat 节拍不存在 {wb}")
    ea = clk["deadline"].get("earliestArrival")          # 1.4，S-066
    if ea is not None and (wb not in beats or not isinstance(ea, int)
                           or not beats[wb]["window"]["earliest"] <= ea <= clk["deadline"]["t"]):
        err(f"clock.deadline.earliestArrival {ea!r} 要是整数、有 watchBeat，且在 watchBeat 的 earliest 和期限之间")
    cue = clk["deadline"].get("earliestArrivalCue")      # 1.5，S-066 ①：第一次到下限时说的一句
    if cue is not None:
        if ea is None:
            err("clock.deadline.earliestArrivalCue 要和 earliestArrival 一起写")
        if cue.get("speaker") not in chars:
            err(f"clock.deadline.earliestArrivalCue: 人物不存在 {cue.get('speaker')}")
        if not all(isinstance(cue.get(k), str) and cue.get(k) for k in ("line", "narration")) or cue.get("inferred") is not True:
            err("clock.deadline.earliestArrivalCue 要有 line（人物在场时说）、narration（不在场时叙事说）和 inferred: true")
    for k, v in world.get("pacing", {}).items():
        if not isinstance(v, (int, float)) or v < 0:
            err(f"pacing.{k} 要是非负数")

    for an in world["anchors"]:
        if an not in beats and an not in facts:
            err(f"锚点引用不存在：{an}")
        if an in beats and beats[an]["kind"] != "anchor":
            err(f"{an} 在 anchors 里但 kind 不是 anchor")
    for b in world["beats"]:
        if b["kind"] == "anchor" and b["id"] not in world["anchors"]:
            err(f"{b['id']} 的 kind 是 anchor 但不在 anchors 列表")

    # ---------- 情景模拟（原著路径 + 改道情景） ----------
    sim = Sim(world)

    def simulate(sc):
        r = sim.run(sc)
        return r["outcome"], r["status"], r["times"], r["state"], r["variant"], r["violations"]

    # 1.4：第四幕按钮上的 melosMinutes = 只做这一个动作时，梅洛斯到刑场（watchBeat）在原著路径上早晚几分钟。
    # 晚到超过期限也照算分钟数（按钮写「六十分遅れる」），所以用去掉 window.latest 的副本推演。
    if wb in beats:
        loose = json.loads(json.dumps(world))
        for b in loose["beats"]:
            b["window"]["latest"] = 10 ** 9
        lsim = Sim(loose)
        for af in world.get("affordances", []):
            if not af.get("melos") or not isinstance(af.get("melosMinutes"), int):
                continue
            over = {e["beat"]: {k: v for k, v in e.items() if k not in ("op", "beat")} for e in af["effects"] if e.get("op") == "beat"}
            got = lsim.run({"beats": over})["shift"].get(wb, 0)
            if got != af["melosMinutes"]:
                err(f"{af['id']}: melosMinutes 写的是 {af['melosMinutes']:+d}，按共享规则在原著路径上是 {got:+d}")
        # 1.5：过场选项在收幕时选，非节拍的效果（如体力）也算进去，用共享规则 arrival_delta（和服务端一样：做和不做各排一次程）
        for where_, x, t_ in enroute_minutes:
            got = sim.arrival_delta({}, x["effects"], t_)["minutes"]
            if got != x["melosMinutes"]:
                err(f"{where_}: melosMinutes 写的是 {x['melosMinutes']:+d}，按共享规则在原著路径上是 {got:+d}")

    scenarios = [{"id": "sc.canon", "note": "原著どおり（プレイヤーは何もしない）", "expect": "canon-reunion"}]
    if a.scenarios:
        scenarios += json.loads(Path(a.scenarios).read_text(encoding="utf-8"))
    sim_rows, reached, sigs = [], set(), set()
    canon_status = canon_times = None
    for sc in scenarios:
        for bid, o in sc.get("beats", {}).items():
            if bid not in beats:
                err(f"{sc['id']}: 节拍不存在 {bid}")
            check_effects([{"op": "beat", "beat": bid, **o}], sc["id"])
        for ev in sc.get("events", []):
            check_effects(ev["effects"], sc["id"])
        outcome, status, times, state, variant, violations = simulate(sc)
        for t_, x in violations:                 # 1.6：情景里的事件也守 valueRequires
            err(f"{sc['id']}：t={t_} 把 {x['var']} 改成 {x['value']!r}，条件 {x['when']} 不成立（{x['note']}）")
        if sc["id"] == "sc.canon":
            canon_status, canon_times = status, times
            for bid, st in status.items():
                if st != "happened":
                    err(f"原著路径：{bid} 没有发生（{st}）")
        if outcome:
            reached.add(outcome)
        if sc.get("gap"):
            warn(f"{sc['id']}：{sc['note']} → 落不进任何一类世界结局（{outcome or '无'}），需要 PM/UX 决定")
        elif outcome != sc.get("expect"):
            err(f"{sc['id']}：预期结局 {sc.get('expect')}，实际 {outcome}")
        for var, val in sc.get("expectVars", {}).items():
            if state.get(var) != val:
                err(f"{sc['id']}：预期 {var} = {val!r}，实际 {state.get(var)!r}")
        for bid, want in sc.get("expectBeats", {}).items():     # 1.4：happened / altered / not-happened
            st = status.get(bid)
            got = st if st in ("happened", "altered") else "not-happened"
            if got != want:
                err(f"{sc['id']}：预期 {bid} {want}，实际 {st}")
        for bid, want in sc.get("expectTimes", {}).items():      # 1.4：预期的发生时刻
            if times.get(bid) != want:
                err(f"{sc['id']}：预期 {bid} 在 {want} 发生，实际 {times.get(bid)}")
        for bid, want in sc.get("expectVariant", {}).items():
            if variant.get(bid) != want:
                err(f"{sc['id']}：预期 {bid} 按变体 {want} 演，实际 {variant.get(bid)}")
        sigs.add(json.dumps([state.get(v) for v in sig.get("vars", [])] + [status.get(b) == "happened" for b in sig.get("beats", [])]))
        b24 = times.get("beat.24")
        sim_rows.append((sc["id"], sc["note"], outcome or "（无）", status.get("beat.24"), b24,
                         state["var.hostage.fate"], state["var.king.disposition"],
                         f"{status.get('beat.s2', '—')} / {variant.get('beat.25', status.get('beat.25', '—'))}"))
    for en in ending_defs:
        if en["id"] not in reached:
            err(f"世界结局 {en['id']} 没有任何情景能走到")

    # ---------- 输出 ----------
    Path(a.out).write_text(json.dumps(world, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    cited = sorted(used)
    uncited = [i for i in range(1, len(paras) + 1) if i not in used]
    n_cites = sum(len(v) for v in used.values())
    rep = ["# 世界模型校验报告", "",
           f"- 源文件：`{a.src}`",
           f"- 原文：`{a.text}`（{len(paras)} 段，sha256 `{sha}`）",
           f"- 出处 ID：`{source_id}`",
           f"- 人物 {len(world['characters'])}、地点 {len(world['places'])}、事实 {len(world['facts'])}、节拍 {len(world['beats'])}、"
           f"因果边 {len(world['causal'])}、状态变量 {len(world['stateVars'])}、身份 {len(world['roles'])}、锚点 {len(world['anchors'])}",
           f"- 出处条数：{n_cites}；被引用段落 {len(cited)}/{len(paras)}（{len(cited) * 100 // len(paras)}%）",
           f"- **错误 {len(errors)}，警告 {len(warnings)}**", ""]
    rep += ["## 错误", ""] + ([f"- {e}" for e in errors] or ["（无）"]) + [""]
    rep += ["## 警告", ""] + ([f"- {w}" for w in warnings] or ["（无）"]) + [""]
    def fmt(t):
        if t is None:
            return "—"
        d, m = divmod(t, 1440)
        return f"Day {d} {m // 60:02d}:{m % 60:02d}"
    n_aid = sum(len(c.get("mutualAid", [])) for c in world["characters"])
    rep += [f"- 场景 {len(scenes)}、幕 {len(acts)}、世界结局 {len(ending_defs)}（情景能走到 {len(reached)}）、"
            f"能对话的角色 {sum(c['talkable'] for c in world['characters'])}、第一版身份 {sum(r['release'] == 1 for r in world['roles'])}、"
            f"互助 {n_aid}、情境动作 {len(world.get('affordances', []))}（第四幕 {sum(af.get('act') == 'act.4' for af in world.get('affordances', []))}）、"
            f"物品 {len(world.get('items', []))}（能带在身上的 {sum(bool(x.get('portable')) for x in world.get('items', []))}）", ""]
    rep += [f"情景 {len(sim_rows)} 个，世界结局署名（endings.signature）不同的 {len(sigs)} 种。", ""]
    rep += ["## 情景模拟（世界结局能否走到）", "", "最后一列：beat.s2（セリヌンティウスがちらと疑う）/ beat.25（殴り合い）用的演法。", "",
            "| 情景 | 说明 | 世界结局 | beat.24 | 到达 | 身代わり | 王 | 疑い / 殴り合い |", "|---|---|---|---|---|---|---|---|"]
    for row in sim_rows:
        rep.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {fmt(row[4])} | {row[5]} | {row[6]} | {row[7]} |")
    rep += ["", "## 原著路径时间线", "", "| 节拍 | 故事时间 | 状态 |", "|---|---|---|"]
    for b in sorted(world["beats"], key=lambda b: (canon_times.get(b["id"], 10**9), b["order"])):
        rep.append(f"| {b['id']} {b['title']} | {fmt(canon_times.get(b['id']))} | {canon_status.get(b['id'])} |")
    rep += ["", "## 未被引用的段落", ""]
    rep += [f"- 第 {i} 段：{paras[i - 1][:40]}…" for i in uncited] or ["（无）"]
    Path(a.report).write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep[:12]))
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
