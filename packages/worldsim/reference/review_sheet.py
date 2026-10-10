#!/usr/bin/env python3
"""从 world.json 生成人工校对表（新增一本书流水线第 5 步）。

用法：python3 -I review_sheet.py --world world.json --out REVIEW.md
每条一行：内容、原文引文（段落号）、推断标记，最后一列留给校对人填 OK / 改 / 删。只用标准库。
"""
import argparse
import json
from pathlib import Path


def fmt_t(t):
    d, m = divmod(t, 1440)
    return f"D{d} {m // 60:02d}:{m % 60:02d}"


def quotes(cites):
    return "<br>".join(f"「{c['quote']}」({c['para']})" for c in cites) or "—"


def cond(cs):
    return "、".join(f"{c['var'].removeprefix('var.')} {c['op']} {c['value']}" + ("〔推断〕" if c.get("inferred") else "") for c in cs) or "—"


def eff(es):
    out = []
    for e in es:
        if e["op"] == "set":
            out.append(f"{e['var'].removeprefix('var.')} = {e['value']}")
        elif e["op"] == "inc":
            out.append(f"{e['var'].removeprefix('var.')} {e['by']:+d}")
        elif e["op"] == "relocate":
            out.append(f"{e['character'].removeprefix('char.')} → {e['place'].removeprefix('place.')}")
        elif e["op"] == "beat":
            out.append(f"{e['beat']} {e['to']}" + (f" {e['minutes']} 分" if "minutes" in e else ""))
        elif e["op"] == "promise":
            out.append(f"约定成立「{e.get('text', '')}」")
        elif e["op"] == "hold":                       # contracts 1.3
            to = {None: "被拿走", "player": "交给你"}.get(e["to"], f"→ {str(e['to']).removeprefix('char.')}")
            out.append(f"{e['item']} {to}")
        else:
            out.append(json.dumps(e, ensure_ascii=False))
    return "、".join(out) or "—"


def lines(qs):
    return "<br>".join(f"「{c['quote']}」({c['para']}){when(c)}" for c in qs) or "—"


def when(x):
    """台词、性格、动机的生效时间（contracts 2.1，1.1）和条件（1.4）。"""
    return "".join(f"〔{k} {x[k]}〕" for k in ("since", "until") if k in x) + (f"〔条件 {cond(x['when'])}〕" if x.get("when") else "")


def design_lines(ds):
    """1.4：原文没有、为游戏写的示例台词。"""
    return "<br>".join(f"「{d['text']}」{when(d)}〔推断〕" + (f"（{d['note']}）" if d.get("note") else "")
                       + (f" 依据 {quotes(d['cite'])}" if d.get("cite") else "") for d in ds)


def span(n):
    """按钮上的时间写法（ux-design 4.3）：半角数字；60 分以上写「1時間」「1時間半」。"""
    h, m = divmod(abs(n), 60)
    if not h:
        return f"{m}分"
    return f"{h}時間" + ("" if not m else "半" if m == 30 else f"{m}分")


def button(label, melos_minutes=None, minutes=None):
    """第四幕写对梅洛斯的影响（0 =「変わらない」），第一〜三幕写玩家花的时间（「ほど」）。"""
    if isinstance(melos_minutes, int):
        if not melos_minutes:
            return f"{label}（変わらない）"
        return f"{label}（{span(melos_minutes)}{'遅れる' if melos_minutes > 0 else '早まる'}）"
    return f"{label}（{span(minutes)}ほど）" if minutes else label


def cue_text(w):
    """1.5：第一次到达下限时说的一句（clock.deadline.earliestArrivalCue）。"""
    c = w["clock"]["deadline"].get("earliestArrivalCue")
    if not c:
        return ""
    return f"第一次到下限时只说一次：{c['speaker'].removeprefix('char.')}在场时说「{c['line']}」，不在场时叙事说「{c['narration']}」。"


def en_route(x):
    """1.4：过场里的二选一（UX 校对 3.2）；1.5：按钮上的分钟数和选后的一句（ux-design 4.5）。"""
    er = x.get("enRoute")
    if not er:
        return ""
    ch = " / ".join(f"〔{button(c['label'], c.get('melosMinutes'))}〕{eff(c['effects']) if c['effects'] else '（原作どおり）'}"
                    + (f"，选后：「{c['after']}」" if c.get("after") else "") for c in er["choices"])
    return f"<br>　过场：「{er['line']}」{ch}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    w = json.loads(Path(a.world).read_text(encoding="utf-8"))
    chars = {c["id"]: c["name"] for c in w["characters"]}
    L = [f"# 校对表：{w['book']['title']}（{w['worldModelVersion']}）", "",
         "由 `spikes/pipeline/review_sheet.py` 从 `world.json` 生成，**不要手改**；改 `world.src.json` 后重新生成。",
         "引文后的数字是规范化原文的段落号。校对人在最后一列填 OK / 改 / 删。〔推断〕= 原文没写、由人推断。", ""]

    L += ["## 1. 锚点（PM 确认：这些不能被玩家改变）", "", "| ID | 内容 | 原文 | 校对 |", "|---|---|---|---|"]
    beats = {b["id"]: b for b in w["beats"]}
    facts = {f["id"]: f for f in w["facts"]}
    for an in w["anchors"]:
        x = beats.get(an) or facts.get(an)
        text = x.get("title", "") + ("：" if "title" in x else "") + x.get("summary", x.get("statement", ""))
        L.append(f"| {an} | {text} | {quotes(x['cite'])} | |")

    L += ["", "## 2. 节拍", "", "| ID | 时间（原著 / 最早〜最晚） | 地点 | 人物 | 类型 | 前提 | 结果 | 原文 | 校对 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for b in sorted(w["beats"], key=lambda b: (b["window"]["canonical"], b["order"])):
        wd = b["window"]
        who = "、".join(chars.get(p, p) for p in b["participants"]) or "—"
        L.append(f"| {b['id']} {b['title']} | {fmt_t(wd['canonical'])}（{fmt_t(wd['earliest'])}〜{fmt_t(wd['latest'])}） | "
                 f"{b['place'].removeprefix('place.')} | {who} | {b['kind']} | {cond(b['preconditions'])} | {eff(b['outcomes'])} | {quotes(b['cite'])} | |")
        for v in b.get("variants", []):                # 1.4：到点时按状态换一种演法
            L.append(f"| ↳ 变体 {v['id']}〔推断〕 | — | — | — | — | {cond(v['when'])} | {v['summary']} {eff(v['outcomes']) if v['outcomes'] else ''} | "
                     f"{quotes(v.get('cite', []))} | |")

    L += ["", "## 3. 事实", "", "| ID | 陈述 | 何时成立 | 公开 | 原文 | 校对 |", "|---|---|---|---|---|---|"]
    for f in w["facts"]:
        L.append(f"| {f['id']} | {f['statement']} | {f['trueFrom']} | {f['visibility']} | {quotes(f['cite'])} | |")

    L += ["", "## 4. 人物", ""]
    for c in w["characters"]:
        L += [f"### {c['name']}（{c['id']}）{'· 可对话' if c['talkable'] else ''}", "", c["summary"], "",
              "| 项 | 内容 | 原文 | 校对 |", "|---|---|---|---|"]
        for t in c["traits"]:
            L.append(f"| 性格 | {t['text']}{when(t)} | {quotes(t['cite'])} | |")
        for g in c["goals"]:
            L.append(f"| 动机 | {g['text']}{when(g)} | {quotes(g['cite'])} | |")
        sp = c["speech"]
        L.append(f"| 说话 | 一人称「{sp.get('firstPerson', '—')}」；{sp['register']}；开局在做：{c.get('initialActivity', 'idle')} | "
                 f"{lines(sp['sampleLines'])} | |")
        if sp.get("designLines"):
            L.append(f"| 设计台词 | {design_lines(sp['designLines'])} | — | |")
        L.append(f"| 知道 | {'、'.join(k['fact'].removeprefix('fact.') + '@' + k['since'] for k in c['knows']) or '—'} | — | |")
        for x in c.get("mutualAid", []):
            kind = "他能为你" if x["direction"] == "forYou" else "你能为他"
            op = (f"〔开局互助：{x['opening']}〕" if x.get("opening") else "") + ("〔大事：兑现时算关键时刻〕" if x.get("major") else "")
            op += f"〔交给你：{x['gives']}〕" if x.get("gives") else ""
            op += f"〔效果：{eff(x['effects'])}〕" if x.get("effects") else ""
            cond_ = f"（条件：{cond(x['when'])}）" if x.get("when") else ""
            L.append(f"| {kind} | {x['text']}{cond_}{op}{'〔推断〕' if x.get('inferred') else ''} | {quotes(x.get('cite', []))} | |")
        for x in c.get("promiseTemplates", []):
            who = "玩家" if x["by"] == "player" else chars.get(x["by"], x["by"])
            note = f"（{x['note']}）" if x.get("note") else ""
            L.append(f"| 约定 | {who}：「{x['text']}」{note}{'〔推断〕' if x.get('inferred') else ''} | {quotes(x.get('cite', []))} | |")
        for x in c.get("plans", []):
            L.append(f"| 打算 {x['act']} | {x['text']}{'〔推断〕' if x.get('inferred') else ''} | {quotes(x.get('cite', []))} | |")
        L.append("")

    L += ["## 5. 因果边", "", "| ID | 关系 | 说明 | 推断 | 原文 | 校对 |", "|---|---|---|---|---|---|"]
    for e in w["causal"]:
        m = f"（{e['minutes']} 分）" if "minutes" in e else ""
        o = "（只管先后）" if e.get("timeLink") == "order" else ""
        L.append(f"| {e['id']} | {e['from']} —{e['type']}{m}{o}→ {e['to']} | {e['note']} | {'〔推断〕' if e['inferred'] else ''} | {quotes(e.get('cite', []))} | |")

    L += ["", "## 6. 设计层（全部〔推断〕，UX / PM 确认）", "", "### 地点与场景", "",
          "| 地点 | 场景 | 相邻（分钟） | 说明 | 校对 |", "|---|---|---|---|---|"]
    for p in w["places"]:
        adj = "、".join(f"{x['place'].removeprefix('place.')} {x['travelMinutes']}" for x in p["adjacent"])
        L.append(f"| {p['id']} {p['name']} | {p.get('sceneRef') or '（无场景）'} | {adj} | {p.get('note', '')} | |")
    L += ["", "### 身份", "", "| ID | 名字 | 版本 | 起点 | 认识 | 能进 | 有条件能进 | 说明 | 校对 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in w["roles"]:
        ca = "<br>".join(f"{x['place'].removeprefix('place.')}：{cond(x['when'])}" for x in r.get("conditionalAccess", [])) or "—"
        L.append(f"| {r['id']} | {r['name']} | 第 {r['release']} 版 | {r['startAct']} · {r['startPlace'].removeprefix('place.')} · {fmt_t(r['startT'])} | "
                 f"{'、'.join(chars.get(x, x) for x in r['knownCharacters']) or '—'} | {'、'.join(x.removeprefix('place.') for x in r['access'])} | {ca} | {r.get('note', '')} | |")
    L += ["", "### 幕", "", "| 幕 | 时间 | 场景 | 收幕 | 幕末去处 | 校对 |", "|---|---|---|---|---|---|"]
    for act in w["acts"]:
        exits = "<br>".join(f"{x['label']} → {x['toAct']} · {x['place'].removeprefix('place.')} · {fmt_t(x['t'])}" + en_route(x)
                            for x in act["exits"]) or "（进入结局）"
        L.append(f"| {act['id']} {act['title']} | {fmt_t(act['start']['t'])}〜（最迟 {fmt_t(act['end']['atLatest'])}） | "
                 f"{'、'.join(s.removeprefix('scene.') for s in act['scenes'])} | {'、'.join(act['end']['onBeats'])} | {exits} | |")
    L += ["", "### 情境动作（contracts 2.10；第四幕每处既能让他慢，也能帮他快，S-036 ②）", "",
          "第四幕带「对梅洛斯」的动作，按钮写对梅洛斯的影响（`melosMinutes`，1.4，UX 4.3）；其他写玩家花的时间。"
          "这里是原著路径上的值；游戏里按钮写本局实际值（S-066），到了 17:30 的下限后「帮他快」写「（変わらない）」。"
          + cue_text(w), "",
          "| ID | 幕 · 地点 | 谁能用 | 动作 | 按钮 | 对梅洛斯 | 条件 | 兑现的互助 | 效果 | 说明 | 原文 | 校对 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    aids = {x["id"]: x["text"] for c in w["characters"] for x in c.get("mutualAid", [])}
    for af in w.get("affordances", []):
        who = "、".join(r.removeprefix("role.") for r in af.get("roles", [])) or "全部"
        mel = {"delay": "让他慢", "hasten": "帮他快"}.get(af.get("melos"), "—")
        item = f"（交出 {af['item']}）" if af.get("item") else ""
        mm = af.get("melosMinutes")
        btn = button(af["label"], mm, af["minutes"])
        L.append(f"| {af['id']} | {af.get('act', '各幕')} · {af['place'].removeprefix('place.')} | {who} | {af['kind']}{item} | "
                 f"{btn} | {mel} | {cond(af.get('when', []))} | {aids.get(af.get('aid'), '—')} | "
                 f"{eff(af['effects'])} | {af.get('note', '')} | {quotes(af.get('cite', []))} | |")
    L += ["", "### 物品（1.3：能带在身上的 = 一件实物，同一时刻只在一个人手里）", "",
          "| ID | 名字 | 怎么拿得到 | 说明 | 原文 | 校对 |", "|---|---|---|---|---|---|"]
    owners = {}
    for r in w["roles"]:
        for i in r.get("items", []):
            owners.setdefault(i, []).append(f"身份 {r['id'].removeprefix('role.')} 开局带着")
    for c in w["characters"]:
        for i in c.get("items", []):
            owners.setdefault(i, []).append(f"{chars.get(c['id'], c['id'])} 开局带着")
        for x in c.get("mutualAid", []):
            if x.get("gives"):
                owners.setdefault(x["gives"], []).append(f"{chars.get(c['id'], c['id'])} 兑现互助 {x['id']} 时交给你")
    for it in w.get("items", []):
        how = ([f"在 {'、'.join(x.removeprefix('place.') for x in it['at'])} 随手可得"] if it.get("at") else []) + owners.get(it["id"], [])
        L.append(f"| {it['id']} | {it['name']} | {'<br>'.join(how) or '—'} | {it.get('note', '')} | {quotes(it.get('cite', []))} | |")
    L += ["", "### 节拍上的人物状态（前端的 activity）", "", "| 节拍 | 之后在做什么 |", "|---|---|"]
    for b in w["beats"]:
        if b.get("activities"):
            L.append(f"| {b['id']} {b['title']} | {'、'.join(chars.get(x['character'], x['character']) + '：' + x['activity'] for x in b['activities'])} |")
    lab = w["clock"].get("labels", {})
    L += ["", "### 时刻标签（S-037、UX 4.2）", "", f"格式「{lab.get('format', '')}」；日子：{'／'.join(lab.get('days', []))}", "",
          "| 从 | 时段 |", "|---|---|"]
    L += [f"| {b[0] // 60:02d}:{b[0] % 60:02d} | {b[1]} |" for b in lab.get("bands", [])]
    L += ["", "### 世界结局", "", "| 顺序 | ID | 显示 | 条件 | 校对 |", "|---|---|---|---|---|"]
    for en in w["endings"]["world"]:
        L.append(f"| {en['order']} | {en['id']} | {en['label']} | {cond(en['when'])} | |")
    L += ["", "### 状态变量", "", "| ID | 类型 | 初值 | 关键时刻 | 玩家可见的说法 | 说明 |", "|---|---|---|---|---|---|"]
    for v in w["stateVars"]:
        vals = f"{v['type']}" + (f"（{' / '.join(map(str, v['values']))}）" if v.get("values") else "")
        labels = "、".join(f"{k}:{t}" for k, t in v.get("valueLabels", {}).items()) or "—"
        L.append(f"| {v['id']} | {vals} | {v['default']} | {'是' if v.get('keyMoment') else ''} | {labels} | {v['description']} |")
    L += ["", "### 全局规则", ""] + [f"- {g['id']}：{g['text']}" + (f"（{quotes(g['cite'])}）" if g.get("cite") else "") for g in w["globalRules"]]
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {a.out}: {len(L)} lines")


if __name__ == "__main__":
    main()
