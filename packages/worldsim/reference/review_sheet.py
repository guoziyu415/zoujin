#!/usr/bin/env python3
"""Generates the manual review sheet from world.json (step 5 of the pipeline for adding a book).

Usage: python3 -I review_sheet.py --world world.json --out REVIEW.md
One row per entry: content, source quotes (paragraph numbers), the inferred marker; the last column is left for the
reviewer to fill in OK / fix / delete. Standard library only.

world.json から人手の校閲表を生成する（本を 1 冊追加するパイプラインの第 5 段階）。

使い方：python3 -I review_sheet.py --world world.json --out REVIEW.md
1 件 1 行：内容、原文の引用（段落番号）、推定マーク。最後の列はレビュアーが OK / 修正 / 削除 を記入するために空けておく。
標準ライブラリのみ。
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
    return "、".join(f"{c['var'].removeprefix('var.')} {c['op']} {c['value']}" + ("〔inferred / 推定〕" if c.get("inferred") else "") for c in cs) or "—"


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
            out.append(f"{e['beat']} {e['to']}" + (f" {e['minutes']} min / 分" if "minutes" in e else ""))
        elif e["op"] == "promise":
            out.append(f"promise made / 約束成立「{e.get('text', '')}」")
        elif e["op"] == "hold":                       # contracts 1.3
            to = {None: "taken away / 取られる", "player": "given to you / あなたに渡す"}.get(e["to"], f"→ {str(e['to']).removeprefix('char.')}")
            out.append(f"{e['item']} {to}")
        else:
            out.append(json.dumps(e, ensure_ascii=False))
    return "、".join(out) or "—"


def lines(qs):
    return "<br>".join(f"「{c['quote']}」({c['para']}){when(c)}" for c in qs) or "—"


def when(x):
    """When lines, traits and motives take effect (contracts 2.1, 1.1) and their conditions (1.4).

    セリフ、性格、動機の有効時期（contracts 2.1、1.1）と条件（1.4）。
    """
    return "".join(f"〔{k} {x[k]}〕" for k in ("since", "until") if k in x) + (f"〔condition / 条件 {cond(x['when'])}〕" if x.get("when") else "")


def design_lines(ds):
    """1.4: sample lines written for the game that are not in the source text.

    1.4：原文にはない、ゲームのために書いたセリフの例。
    """
    return "<br>".join(f"「{d['text']}」{when(d)}〔inferred / 推定〕" + (f"（{d['note']}）" if d.get("note") else "")
                       + (f" based on / 根拠 {quotes(d['cite'])}" if d.get("cite") else "") for d in ds)


def span(n):
    """How times are written on buttons (ux-design 4.3): half-width digits; 60 minutes or more is written 「1時間」
    「1時間半」.

    ボタンの時間の書き方（ux-design 4.3）：半角数字。60 分以上は「1時間」「1時間半」と書く。
    """
    h, m = divmod(abs(n), 60)
    if not h:
        return f"{m}分"
    return f"{h}時間" + ("" if not m else "半" if m == 30 else f"{m}分")


def button(label, melos_minutes=None, minutes=None):
    """Act 4 shows the effect on Melos (0 = 「変わらない」); acts 1〜3 show the time the player spends (「ほど」).

    第四幕はメロスへの影響を書き（0 =「変わらない」）、第一〜三幕はプレイヤーが使う時間を書く（「ほど」）。
    """
    if isinstance(melos_minutes, int):
        if not melos_minutes:
            return f"{label}（変わらない）"
        return f"{label}（{span(melos_minutes)}{'遅れる' if melos_minutes > 0 else '早まる'}）"
    return f"{label}（{span(minutes)}ほど）" if minutes else label


def cue_text(w):
    """1.5: the line said the first time the floor is reached (clock.deadline.earliestArrivalCue).

    1.5：初めて下限に達したときに言う一文（clock.deadline.earliestArrivalCue）。
    """
    c = w["clock"]["deadline"].get("earliestArrivalCue")
    if not c:
        return ""
    sp = c['speaker'].removeprefix('char.')
    return (f" Said only once, the first time the floor is reached: when {sp} is present they say 「{c['line']}」;"
            f" when absent, the narrator says 「{c['narration']}」. / 初めて下限に達したときに 1 回だけ言う："
            f"{sp} が在場なら「{c['line']}」、不在ならナレーターが「{c['narration']}」と語る。")


def en_route(x):
    """1.4: the either-or in an interlude (UX proofreading 3.2); 1.5: the minutes on the buttons and the line after
    choosing (ux-design 4.5).

    1.4：幕間の二択（UX 校正 3.2）。1.5：ボタンの分数と選んだ後の一文（ux-design 4.5）。
    """
    er = x.get("enRoute")
    if not er:
        return ""
    ch = " / ".join(f"〔{button(c['label'], c.get('melosMinutes'))}〕{eff(c['effects']) if c['effects'] else '（原作どおり）'}"
                    + (f", after choosing / 選択後：「{c['after']}」" if c.get("after") else "") for c in er["choices"])
    return f"<br>　Interlude / 幕間：「{er['line']}」{ch}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    w = json.loads(Path(a.world).read_text(encoding="utf-8"))
    chars = {c["id"]: c["name"] for c in w["characters"]}
    L = [f"# Review sheet / 校閲表: {w['book']['title']} ({w['worldModelVersion']})", "",
         "Generated from `world.json` by `packages/worldsim/reference/review_sheet.py`; **do not edit by hand**: change"
         " `world.src.json` and regenerate.",
         "`packages/worldsim/reference/review_sheet.py` が `world.json` から生成する。**手で編集しない**こと。"
         "`world.src.json` を変えてから再生成する。", "",
         "The number after a quote is the paragraph number in the normalized source text. The reviewer fills in OK / fix /"
         " delete in the last column. 〔inferred / 推定〕 = not in the source text, inferred by a person.",
         "引用の後の数字は正規化した原文の段落番号。レビュアーは最後の列に OK / 修正 / 削除 を記入する。"
         "〔inferred / 推定〕 = 原文に書かれておらず、人が推定したもの。", ""]

    L += ["## 1. Anchors (PM confirms: the player cannot change these) / アンカー（PM が確認：プレイヤーはこれらを変えられない）", "",
          "| ID | Content / 内容 | Source / 原文 | Review / 校閲 |", "|---|---|---|---|"]
    beats = {b["id"]: b for b in w["beats"]}
    facts = {f["id"]: f for f in w["facts"]}
    for an in w["anchors"]:
        x = beats.get(an) or facts.get(an)
        text = x.get("title", "") + ("：" if "title" in x else "") + x.get("summary", x.get("statement", ""))
        L.append(f"| {an} | {text} | {quotes(x['cite'])} | |")

    L += ["", "## 2. Beats / ビート", "",
          "| ID | Time (original / earliest〜latest) / 時刻（原作 / 最早〜最遅） | Place / 場所 | Characters / 登場人物"
          " | Kind / 種類 | Preconditions / 前提 | Outcomes / 結果 | Source / 原文 | Review / 校閲 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for b in sorted(w["beats"], key=lambda b: (b["window"]["canonical"], b["order"])):
        wd = b["window"]
        who = "、".join(chars.get(p, p) for p in b["participants"]) or "—"
        L.append(f"| {b['id']} {b['title']} | {fmt_t(wd['canonical'])}（{fmt_t(wd['earliest'])}〜{fmt_t(wd['latest'])}） | "
                 f"{b['place'].removeprefix('place.')} | {who} | {b['kind']} | {cond(b['preconditions'])} | {eff(b['outcomes'])} | {quotes(b['cite'])} | |")
        for v in b.get("variants", []):                # 1.4: when due, play it differently per state / 状態で演じ方を変える
            L.append(f"| ↳ variant / バリアント {v['id']}〔inferred / 推定〕 | — | — | — | — | {cond(v['when'])} | {v['summary']} {eff(v['outcomes']) if v['outcomes'] else ''} | "
                     f"{quotes(v.get('cite', []))} | |")

    L += ["", "## 3. Facts / 事実", "",
          "| ID | Statement / 内容 | True from / 成立時期 | Visibility / 公開 | Source / 原文 | Review / 校閲 |",
          "|---|---|---|---|---|---|"]
    for f in w["facts"]:
        L.append(f"| {f['id']} | {f['statement']} | {f['trueFrom']} | {f['visibility']} | {quotes(f['cite'])} | |")

    L += ["", "## 4. Characters / 登場人物", ""]
    for c in w["characters"]:
        L += [f"### {c['name']}（{c['id']}）{' · talkable / 会話可' if c['talkable'] else ''}", "", c["summary"], "",
              "| Item / 項目 | Content / 内容 | Source / 原文 | Review / 校閲 |", "|---|---|---|---|"]
        for t in c["traits"]:
            L.append(f"| Trait / 性格 | {t['text']}{when(t)} | {quotes(t['cite'])} | |")
        for g in c["goals"]:
            L.append(f"| Motive / 動機 | {g['text']}{when(g)} | {quotes(g['cite'])} | |")
        sp = c["speech"]
        L.append(f"| Speech / 話し方 | First person / 一人称「{sp.get('firstPerson', '—')}」; {sp['register']}; "
                 f"doing at the opening / 開始時の行動: {c.get('initialActivity', 'idle')} | "
                 f"{lines(sp['sampleLines'])} | |")
        if sp.get("designLines"):
            L.append(f"| Designed lines / 設計セリフ | {design_lines(sp['designLines'])} | — | |")
        L.append(f"| Knows / 知っている | {'、'.join(k['fact'].removeprefix('fact.') + '@' + k['since'] + ('〔inferred / 推定〕' if k.get('inferred') else '') for k in c['knows']) or '—'} | — | |")
        for x in c.get("mutualAid", []):
            kind = "They can do for you / あなたのためにできる" if x["direction"] == "forYou" else "You can do for them / あなたがその人のためにできる"
            op = (f"〔opening mutual help / オープニングの助け合い：{x['opening']}〕" if x.get("opening") else "") + ("〔big thing: a key moment when fulfilled / 大きなこと：果たすとキーモーメント〕" if x.get("major") else "")
            op += f"〔gives you / あなたに渡す：{x['gives']}〕" if x.get("gives") else ""
            op += f"〔effects / 効果：{eff(x['effects'])}〕" if x.get("effects") else ""
            cond_ = f"（condition / 条件：{cond(x['when'])}）" if x.get("when") else ""
            L.append(f"| {kind} | {x['text']}{cond_}{op}{'〔inferred / 推定〕' if x.get('inferred') else ''} | {quotes(x.get('cite', []))} | |")
        for x in c.get("promiseTemplates", []):
            who = "player / プレイヤー" if x["by"] == "player" else chars.get(x["by"], x["by"])
            note = f"（{x['note']}）" if x.get("note") else ""
            L.append(f"| Promise / 約束 | {who}：「{x['text']}」{note}{'〔inferred / 推定〕' if x.get('inferred') else ''} | {quotes(x.get('cite', []))} | |")
        for x in c.get("plans", []):
            L.append(f"| Plan / プラン {x['act']} | {x['text']}{'〔inferred / 推定〕' if x.get('inferred') else ''} | {quotes(x.get('cite', []))} | |")
        L.append("")

    L += ["## 5. Causal edges / 因果エッジ", "",
          "| ID | Relation / 関係 | Note / 説明 | Inferred / 推定 | Source / 原文 | Review / 校閲 |", "|---|---|---|---|---|---|"]
    for e in w["causal"]:
        m = f"（{e['minutes']} min / 分）" if "minutes" in e else ""
        o = "（order only / 順序のみ）" if e.get("timeLink") == "order" else ""
        L.append(f"| {e['id']} | {e['from']} —{e['type']}{m}{o}→ {e['to']} | {e['note']} | {'〔inferred / 推定〕' if e['inferred'] else ''} | {quotes(e.get('cite', []))} | |")

    L += ["", "## 6. Design layer (all 〔inferred / 推定〕, confirmed by UX / PM) / 設計層（すべて推定、UX / PM が確認）", "",
          "### Places and scenes / 場所とシーン", "",
          "| Place / 場所 | Scene / シーン | Adjacent (minutes) / 隣接（分） | Note / 説明 | Review / 校閲 |", "|---|---|---|---|---|"]
    for p in w["places"]:
        adj = "、".join(f"{x['place'].removeprefix('place.')} {x['travelMinutes']}" for x in p["adjacent"])
        L.append(f"| {p['id']} {p['name']} | {p.get('sceneRef') or '(no scene / シーンなし)'} | {adj} | {p.get('note', '')} | |")
    L += ["", "### Roles / ロール", "",
          "| ID | Name / 名前 | Release / 版 | Start / 開始 | Knows / 知り合い | Access / 入れる | Conditional access / 条件付きで入れる"
          " | Note / 説明 | Review / 校閲 |", "|---|---|---|---|---|---|---|---|---|"]
    for r in w["roles"]:
        ca = "<br>".join(f"{x['place'].removeprefix('place.')}：{cond(x['when'])}" for x in r.get("conditionalAccess", [])) or "—"
        L.append(f"| {r['id']} | {r['name']} | release / 第 {r['release']} 版 | {r['startAct']} · {r['startPlace'].removeprefix('place.')} · {fmt_t(r['startT'])} | "
                 f"{'、'.join(chars.get(x, x) for x in r['knownCharacters']) or '—'} | {'、'.join(x.removeprefix('place.') for x in r['access'])} | {ca} | {r.get('note', '')} | |")
    L += ["", "### Acts / 幕", "",
          "| Act / 幕 | Time / 時刻 | Scenes / シーン | End of act / 幕を閉じる | End-of-act exits / 幕末の行き先 | Review / 校閲 |",
          "|---|---|---|---|---|---|"]
    for act in w["acts"]:
        exits = "<br>".join(f"{x['label']} → {x['toAct']} · {x['place'].removeprefix('place.')} · {fmt_t(x['t'])}" + en_route(x)
                            for x in act["exits"]) or "(to the ending / エンディングへ)"
        L.append(f"| {act['id']} {act['title']} | {fmt_t(act['start']['t'])}〜（latest / 最遅 {fmt_t(act['end']['atLatest'])}） | "
                 f"{'、'.join(s.removeprefix('scene.') for s in act['scenes'])} | {'、'.join(act['end']['onBeats'])} | {exits} | |")
    L += ["", "### Situational actions (contracts 2.10; every act 4 place can both slow him and speed him up, S-036 ②)"
          " / 状況アクション（第四幕の各場所では彼を遅らせることも速めることもできる）", "",
          "For act 4 actions \"on Melos\", the button shows the effect on Melos (`melosMinutes`, 1.4, UX 4.3); others show"
          " the time the player spends. These are the values on the original path; in the game the button shows this run's"
          " actual value (S-066), and once the 17:30 floor is reached, \"speed him up\" shows 「（変わらない）」."
          " / 第四幕の「メロスに対する」アクションは、ボタンにメロスへの影響を書く（`melosMinutes`、1.4、UX 4.3）。ほかは"
          "プレイヤーが使う時間を書く。ここにあるのは原作の経路での値で、ゲームではボタンにこのプレイの実際の値を書き（S-066）、"
          "17:30 の下限に達した後の「速める」は「（変わらない）」と書く。"
          + cue_text(w), "",
          "| ID | Act · place / 幕 · 場所 | Who can use / 使える人 | Action / アクション | Button / ボタン | On Melos / メロスに"
          " | Condition / 条件 | Mutual help fulfilled / 果たす助け合い | Effects / 効果 | Note / 説明 | Source / 原文 | Review / 校閲 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    aids = {x["id"]: x["text"] for c in w["characters"] for x in c.get("mutualAid", [])}
    for af in w.get("affordances", []):
        who = "、".join(r.removeprefix("role.") for r in af.get("roles", [])) or "all / 全員"
        mel = {"delay": "slow him / 遅らせる", "hasten": "speed him up / 速める"}.get(af.get("melos"), "—")
        item = f"（hands over / 渡す {af['item']}）" if af.get("item") else ""
        mm = af.get("melosMinutes")
        btn = button(af["label"], mm, af["minutes"])
        L.append(f"| {af['id']} | {af.get('act', 'every act / 各幕')} · {af['place'].removeprefix('place.')} | {who} | {af['kind']}{item} | "
                 f"{btn} | {mel} | {cond(af.get('when', []))} | {aids.get(af.get('aid'), '—')} | "
                 f"{eff(af['effects'])} | {af.get('note', '')} | {quotes(af.get('cite', []))} | |")
    L += ["", "### Items (1.3: portable = one physical object, in one person's hands at any one time)"
          " / アイテム（1.3：持ち歩ける = 実物 1 つで、同時には 1 人の手にしかない）", "",
          "| ID | Name / 名前 | How to get it / 入手方法 | Note / 説明 | Source / 原文 | Review / 校閲 |", "|---|---|---|---|---|---|"]
    owners = {}
    for r in w["roles"]:
        for i in r.get("items", []):
            owners.setdefault(i, []).append(f"role {r['id'].removeprefix('role.')} starts with it / ロール {r['id'].removeprefix('role.')} が最初から持つ")
    for c in w["characters"]:
        for i in c.get("items", []):
            owners.setdefault(i, []).append(f"{chars.get(c['id'], c['id'])} starts with it / が最初から持つ")
        for x in c.get("mutualAid", []):
            if x.get("gives"):
                owners.setdefault(x["gives"], []).append(f"{chars.get(c['id'], c['id'])} gives it to you when fulfilling {x['id']} / {x['id']} を果たすときにあなたに渡す")
    for it in w.get("items", []):
        how = ([f"at hand at / 手に入る場所: {'、'.join(x.removeprefix('place.') for x in it['at'])}"] if it.get("at") else []) + owners.get(it["id"], [])
        L.append(f"| {it['id']} | {it['name']} | {'<br>'.join(how) or '—'} | {it.get('note', '')} | {quotes(it.get('cite', []))} | |")
    L += ["", "### Characters' states on beats (the frontend's activity) / ビート上の登場人物の状態（フロントエンドの activity）", "",
          "| Beat / ビート | Doing afterwards / その後の行動 |", "|---|---|"]
    for b in w["beats"]:
        if b.get("activities"):
            L.append(f"| {b['id']} {b['title']} | {'、'.join(chars.get(x['character'], x['character']) + '：' + x['activity'] for x in b['activities'])} |")
    lab = w["clock"].get("labels", {})
    L += ["", "### Clock labels (S-037, UX 4.2) / 時刻ラベル", "",
          f"Format / 書式「{lab.get('format', '')}」; days / 日：{'／'.join(lab.get('days', []))}", "",
          "| From / 開始 | Band / 時間帯 |", "|---|---|"]
    L += [f"| {b[0] // 60:02d}:{b[0] % 60:02d} | {b[1]} |" for b in lab.get("bands", [])]
    L += ["", "### World endings / 世界の結末", "",
          "| Order / 順序 | ID | Label / 表示 | Condition / 条件 | Review / 校閲 |", "|---|---|---|---|---|"]
    for en in w["endings"]["world"]:
        L.append(f"| {en['order']} | {en['id']} | {en['label']} | {cond(en['when'])} | |")
    L += ["", "### State variables / 状態変数", "",
          "| ID | Type / 型 | Default / 初期値 | Key moment / キーモーメント | Player-visible wording / プレイヤーに見える表現"
          " | Description / 説明 |", "|---|---|---|---|---|---|"]
    for v in w["stateVars"]:
        vals = f"{v['type']}" + (f"（{' / '.join(map(str, v['values']))}）" if v.get("values") else "")
        labels = "、".join(f"{k}:{t}" for k, t in v.get("valueLabels", {}).items()) or "—"
        # 1.6 (C-16): the conditions for changing to a given value, written after the description
        # 1.6（C-16）：ある値に変えるために満たすべき条件。説明の後に書く
        req = "".join(f"<br>Setting {r['value']} requires / {r['value']} にするには {cond(r['when'])}：{r['note']}" for r in v.get("valueRequires", []))
        L.append(f"| {v['id']} | {vals} | {v['default']} | {'yes / はい' if v.get('keyMoment') else ''} | {labels} | {v['description']}{req} |")
    L += ["", "### Global rules / 全体ルール", ""] + [f"- {g['id']}：{g['text']}" + (f"（{quotes(g['cite'])}）" if g.get("cite") else "") for g in w["globalRules"]]
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {a.out}: {len(L)} lines")


if __name__ == "__main__":
    main()
