#!/usr/bin/env python3
"""World model build and validation (prototype of step 2, "automatic validation", of the pipeline for adding a book).

Usage:
  python3 -I build_world.py --src world.src.json --text melos_plain.txt --out world.json --report report.md \
      [--scenarios scenarios.json]

What it does:
1. Locating citations: every {"q": quote, "p": paragraph number (optional)} must be an exact substring of one
   paragraph of the normalized source text. Without p it is located automatically; not found, or found in several
   paragraphs (with no p given), is an error. On output it is expanded into contracts.md's Cite: {source, para, quote}.
2. Reference integrity: all IDs are unique; references in knows / since / place / participants / var / anchors / causal
   / roles all exist; state variable values match their types and enums; (1.6, C-16) a valueRequires value is among
   the variable's values, and the variables referenced in when exist with valid values; a warning when an effect
   template outside beats sets a variable to a restricted value.
3. Time: beat earliest <= canonical <= latest; canonical never goes backwards in order; deadline = sunset on Day 3.
4. Scope of knowledge: when a character "knows F from X", F must already be true before (or at) X.
5. The causal graph has no cycles; from's canonical is not later than to's.
6. Design layer: scenes (sceneRef), acts (start / end of act / exits at the end of act), roles (release, startAct,
   conditionalAccess), world endings (endings), clock labels (clock.labels), (1.10) role summaries, every character's
   reading, the ruby list (ruby), (1.11) originalEnding of characters on the ending page and ending templates
   (endings.templates: length, fallback, S-067's wording), characters' mutual help / promises / plans (S-029, S-030,
   S-048), situational actions and items (affordances / items, contracts 2.10; in act 4 slowing him and speeding him
   up sit side by side, S-036 ②), characters' states on beats (activities), when lines and motives take effect (since
   / until / when), (1.4) designed lines, the effects of mutual help, beat variants, and interlude either-or choices
   (enRoute) all hold up; (1.7) spots (relocate and exit spots) are in the layout of the scene the place belongs to and
   belong to that place (assets/scenes/<scene>/scene.json), exit landings' arrival, group characters cannot be talked
   to; where a plan lands (Act.plan, C-19) is checked like exits, and so is where the player stands after a
   situational action (playerSpot); the beats, characters, facts, places and other set pieces referenced by set pieces
   (setPieces, 2.11) all exist, and at one moment there is no entry that can never get its turn; examinables (objects,
   2.12) have a place with a scene and spots in the layout.
7. Scenario simulation (--scenarios): simulates the original story's path and several rerouting scenarios with the
   time propagation rules of contracts 2.5, checking that every beat happens on the original path, that each scenario
   lands on the expected world ending (and the expected beat statuses and variants), and that every class of baseline
   world ending is reachable; (1.4) the melosMinutes on act 4 buttons agree with Melos's arrival time difference
   computed by the shared rules; (1.5) the same for the melosMinutes of interlude options.
8. Coverage: the share of the text's paragraphs that are cited, with the uncited paragraphs listed.
Standard library only.

世界モデルの構築と検証（本を 1 冊追加するパイプラインの第 2 段階「自動検証」のプロトタイプ）。

使い方：
  python3 -I build_world.py --src world.src.json --text melos_plain.txt --out world.json --report report.md \
      [--scenarios scenarios.json]

やること：
1. 出典の特定：各 {"q": 引用, "p": 段落番号（省略可）} は、正規化した原文のある段落の正確な部分文字列でなければ
   ならない。p を省略すると自動で特定する。見つからない、または複数の段落に現れる（p がない）場合はエラー。
   出力時に contracts.md の Cite：{source, para, quote} に展開する。
2. 参照の整合性：すべての ID が一意。knows / since / place / participants / var / anchors / causal / roles の参照が
   すべて存在する。状態変数の値が型と列挙に合う。（1.6、C-16）valueRequires の value がその変数の値の範囲内にあり、
   when が参照する変数が存在し値が妥当。ビート以外の効果テンプレートが変数を制限付きの値に設定するときは警告。
3. 時間：ビートの earliest <= canonical <= latest。order 順に並べたとき canonical が逆行しない。期限 = Day 3 の日没。
4. 知識の範囲：登場人物が「X から F を知っている」なら、F は X より前（または同時）に成立していなければならない。
5. 因果グラフに循環がない。from の canonical が to より遅くない。
6. 設計層：シーン（sceneRef）、幕（acts。開始 / 幕を閉じる / 幕末の行き先）、ロール（release、startAct、
   conditionalAccess）、世界の結末（endings）、時刻ラベル（clock.labels）、（1.10）ロールの summary、各登場人物の
   reading、ルビの語表（ruby）、（1.11）結末ページの登場人物の originalEnding と結末テンプレート（endings.templates。
   文字数、フォールバック、S-067 の言葉づかい）、登場人物の助け合い / 約束 / プラン（S-029、S-030、S-048）、状況
   アクションとアイテム（affordances / items、contracts 2.10。第四幕では彼を遅らせるものと速めるものを並べる、
   S-036 ②）、ビート上の登場人物の状態（activities）、セリフと動機の有効時期（since / until / when）、（1.4）設計
   セリフ、助け合いの効果、ビートのバリアント、幕間の二択（enRoute）がすべて成り立つ。（1.7）立ち位置（relocate と
   行き先の spot）がその場所の属するシーンのレイアウトにあり、その場所に属する（assets/scenes/<シーン>/scene.json）。
   行き先に着いたときの arrival。群れの登場人物（group）とは会話できない。プランが成立したときの着地点（Act.plan、
   C-19）は行き先と同様に確認し、状況アクションの後にプレイヤーが立つ位置（playerSpot）も確認する。固定演出
   （setPieces、2.11）が参照するビート、登場人物、事実、場所、ほかの固定演出がすべて存在し、同じタイミングに永遠に
   順番が回ってこない項目がない。調べられる物（objects、2.12）の場所にシーンがあり、立ち位置がレイアウトにある。
7. シナリオのシミュレーション（--scenarios）：contracts 2.5 の時間伝播ルールで原作の経路といくつかの分岐シナリオを
   シミュレーションし、原作の経路ですべてのビートが起き、各シナリオが期待した世界の結末（と期待したビートの状態、
   バリアント）に落ち、各種の最低限の世界の結末にすべて到達できることを確認する。（1.4）第四幕のボタンの
   melosMinutes が共有ルールで計算したメロスの到着時刻の差と一致する。（1.5）幕間の選択肢の melosMinutes も同様。
8. カバー率：引用された段落が全段落に占める割合と、引用されていない段落の一覧。
標準ライブラリのみ。
"""
import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from zoujin_worldsim import Sim  # Shared simulation rules (W-1 package) / 共有のシミュレーションルール（W-1 のパッケージ）

CONTRACT_VERSION = "1.15"  # Version of contracts.md / contracts.md のバージョン
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
            err(f"{where}: empty quote / 引用が空")
            return None
        if p is not None:
            if not (1 <= p <= len(paras)) or q not in paras[p - 1]:
                err(f"{where}: quote not in paragraph {p} / 引用が第 {p} 段落にない: 「{q}」")
                return None
        else:
            hits = [i + 1 for i, para in enumerate(paras) if q in para]
            if not hits:
                err(f"{where}: quote not found in the source text / 原文に引用が見つからない: 「{q}」")
                return None
            if len(hits) > 1:
                err(f"{where}: quote appears in several paragraphs {hits}; add p / 引用が複数の段落 {hits} にある。p を付ける: 「{q}」")
                return None
            p = hits[0]
        if len(q) > 80:
            warn(f"{where}: quote longer than 80 characters ({len(q)}) / 引用が 80 字を超える（{len(q)} 字）")
        used[p].append(where)
        out = {"source": source_id, "para": p, "quote": q}
        # When sampleLines take effect (contracts 2.1, 1.1; when is 1.4) / sampleLines の有効時期（when は 1.4）
        for k in ("since", "until", "when"):
            if k in c:
                out[k] = c[k]
        return out
    return resolve


def expand_cites(obj, resolve, path="$"):
    """Expands every {q,p} in cite / sampleLines in the object tree into a Cite.

    オブジェクトツリー内のすべての cite / sampleLines の {q,p} を Cite に展開する。
    """
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
    ap.add_argument(
        "--scenes-dir",
        help="Directory of scene layouts (default: the repo's assets/scenes) / シーンレイアウトのディレクトリ（既定：リポジトリの assets/scenes）",
    )
    a = ap.parse_args()

    src = json.loads(Path(a.src).read_text(encoding="utf-8"))
    paras, sha = load_text(a.text)
    s = src["book"]["source"]
    source_id = f"{s['provider']}:{s['fileId']}@sha256:{sha[:12]}"
    used = defaultdict(list)
    resolve = make_cite_resolver(paras, source_id, used)

    # Use readable path names (entity IDs) instead of array indices so the report is easier to read
    # 配列の添字の代わりに読みやすいパス名（エンティティ ID）を使い、レポートを読みやすくする
    def named(obj, path):
        if isinstance(obj, list):
            return [named(v, f"{path}/{label(v, i)}") for i, v in enumerate(obj)]
        if isinstance(obj, dict):
            return {k: (named(v, f"{path}.{k}") if k not in ("cite", "sampleLines") else v) for k, v in obj.items()}
        return obj

    world = expand_cites(src, resolve, "$")
    world.pop("_authoring", None)
    world["book"]["source"]["textSha256"] = sha

    # ---------- IDs and references / ID と参照 ----------
    if world.get("schemaVersion") != CONTRACT_VERSION:
        err(f"schemaVersion must be the contract version {CONTRACT_VERSION} / schemaVersion は契約バージョン {CONTRACT_VERSION} でなければならない: {world.get('schemaVersion')}")
    ids = {}
    for kind in ("characters", "places", "facts", "beats", "stateVars", "roles", "causal", "globalRules", "scenes", "acts", "affordances", "items",
                 "setPieces", "objects"):
        for x in world.get(kind, []):
            if x["id"] in ids:
                err(f"Duplicate ID / ID の重複: {x['id']}")
            ids[x["id"]] = kind
    for c in world["characters"]:
        for x in c.get("mutualAid", []) + c.get("promiseTemplates", []):
            if x["id"] in ids:
                err(f"Duplicate ID / ID の重複: {x['id']}")
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
            err(f"{where}: undefined state variable / 未定義の状態変数: {var}")
            return
        if isinstance(value, list):          # op "in"
            for x in value:
                check_value(var, x, where)
            return
        t = v["type"]
        if t == "enum" and value not in v["values"]:
            err(f"{where}: {var}: value {value!r} not in the enum / 値が列挙にない: {v['values']}")
        if t == "bool" and not isinstance(value, bool):
            err(f"{where}: {var} needs a bool, got / bool が必要だが次を受け取った: {value!r}")
        if t == "int" and not isinstance(value, (int, float)):
            err(f"{where}: {var} needs a number, got / 数値が必要だが次を受け取った: {value!r}")
        if t == "place" and value not in places and value != "role.startPlace":
            err(f"{where}: {var} needs a place ID, got / 場所 ID が必要だが次を受け取った: {value!r}")

    def check_effects(effs, where):
        for e in effs:
            op = e.get("op")
            if op == "set":
                check_value(e["var"], e["value"], where)
            elif op == "inc":
                if e["var"] not in svars or svars[e["var"]]["type"] != "int":
                    err(f"{where}: inc only works on int variables / inc は int の変数専用: {e['var']}")
            elif op == "relocate":
                if e["character"] not in chars or e["place"] not in places:
                    err(f"{where}: relocate references something that does not exist / relocate の参照先が存在しない: {e}")
            elif op == "learn":
                if (e["character"] != "player" and e["character"] not in chars) or e["fact"] not in facts:
                    # 1.7: the player can learn too (contract 2.1) / 1.7：プレイヤーも知ることができる（契約 2.1）
                    err(f"{where}: learn references something that does not exist / learn の参照先が存在しない: {e}")
            elif op == "beat":
                if e["beat"] not in beats:
                    err(f"{where}: beat references something that does not exist / beat の参照先が存在しない: {e}")
                if e.get("to") == "altered":
                    check_effects(e.get("outcomes", []), where)
            elif op == "hold":                   # 1.3: a carried item changes hands / 所持品の持ち主が替わる
                it = item_map.get(e.get("item"))
                if not it or not it.get("portable"):
                    err(f"{where}: hold only works on portable items / hold は portable なアイテム専用: {e.get('item')}")
                for k in ("to", "from"):
                    if k in e and e[k] is not None and e[k] != "player" and e[k] not in chars:
                        err(f"{where}: hold.{k} must be player, a character ID or null / hold.{k} は player、登場人物 ID、null のいずれか")
                if "to" not in e:
                    err(f"{where}: hold needs to (null = taken away, used up) / hold には to が必要（null = 取られた、使い切った）")
            # 1.1: in the world model it appears only in effect templates of situational actions; promiseId is assigned
            # at submission / 1.1：世界モデルでは状況アクションの効果テンプレートにだけ現れ、promiseId は提出時に割り当てる
            elif op == "promise":
                if e.get("change") != "made" or not e.get("text"):
                    err(f"{where}: promise in an effect template can only be change=made and needs text / 効果テンプレートの promise は change=made のみで、text が必要")
                for k in ("from", "to"):
                    if e.get(k) != "player" and e.get(k) not in chars:
                        err(f"{where}: promise.{k} must be player or a character ID / promise.{k} は player か登場人物 ID")
                if e.get("template") and e["template"] not in tmpl_ids:
                    err(f"{where}: promise.template does not exist / promise.template が存在しない: {e['template']}")
            else:
                err(f"{where}: unknown op / 未知の op: {op}")

    for v in world["stateVars"]:
        if v["type"] != "place":
            check_value(v["id"], v["default"], f"{v['id']}.default")
        for key in v.get("valueLabels", {}):
            val = {"true": True, "false": False}.get(key, key) if v["type"] == "bool" else key
            check_value(v["id"], val, f"{v['id']}.valueLabels")
        if v.get("valueLabels") and not v.get("visibleToPlayer"):
            warn(f"{v['id']}: has valueLabels but is not marked visibleToPlayer / valueLabels があるのに visibleToPlayer が付いていない")
        for r in v.get("valueRequires", []):     # 1.6, C-16
            check_value(v["id"], r["value"], f"{v['id']}.valueRequires")
            if not r.get("when"):
                err(f"{v['id']}.valueRequires: when of {r['value']!r} is empty / {r['value']!r} の when が空")
            for cnd in r.get("when", []):
                check_value(cnd["var"], cnd["value"], f"{v['id']}.valueRequires[{r['value']!r}].when")
            if not r.get("note"):
                err(f"{v['id']}.valueRequires: {r['value']!r} needs a note (used for the narrator's reason) / {r['value']!r} には note が必要（ナレーターの reason に使う）")

    # 1.6: apart from due beats (origin = schedule), effect templates such as mutual help, end-of-act exits and
    # situational actions are all judged by valueRequires at runtime; if a template sets a variable to a restricted
    # value and when does not hold, the narrator rejects it under R2. No such template exists now; this is to see it
    # early when world models are added later
    # 1.6：期限に達したビート（origin = schedule）を除き、助け合い、幕末の行き先、状況アクションといった効果テンプレートは
    # 実行時にすべて valueRequires で判定する。テンプレートが変数を制限付きの値に設定し、when が成り立たなければ
    # ナレーターは R2 で却下する。今そういうテンプレートはないが、今後世界モデルを追加するときに早めに気づけるように
    limited = {(v["id"], r["value"]): r["when"] for v in world["stateVars"] for r in v.get("valueRequires", [])}

    def limited_templates(x, owner):
        if isinstance(x, dict):
            owner = x.get("id", owner)
            for k, y in x.items():
                for e in y if k in ("effects", "outcomes") and isinstance(y, list) else []:
                    if isinstance(e, dict) and e.get("op") == "set" and (e.get("var"), e.get("value")) in limited:
                        when = limited[(e["var"], e["value"])]
                        warn(f"{owner}: sets {e['var']} to {e['value']!r}; at runtime {when} must hold, otherwise the narrator rejects it under R2 / {e['var']} を {e['value']!r} に設定する。実行時に {when} が成り立たなければナレーターが R2 で却下する")
                limited_templates(y, owner)
        elif isinstance(x, list):
            for y in x:
                limited_templates(y, owner)

    for k, x in world.items():
        # Beats happen when due (origin = schedule); their outcomes are governed by the beat's preconditions
        # ビートは期限に起きる（origin = schedule）。結果はビートの前提条件が管理する
        if k != "beats":
            limited_templates(x, k)

    for c in world["characters"]:
        if c["initialPlace"] not in places:
            err(f"{c['id']}: initialPlace does not exist / initialPlace が存在しない: {c['initialPlace']}")
        if not c.get("cite"):
            err(f"{c['id']}: missing citation / 出典がない")
        for k in c["knows"]:
            if k["fact"] not in facts:
                err(f"{c['id']}: knows references a fact that does not exist / knows が存在しない事実を参照: {k['fact']}")
                continue
            if k["since"] != "pre" and k["since"] not in beats:
                err(f"{c['id']}: knows.since references a beat that does not exist / knows.since が存在しないビートを参照: {k['since']}")
                continue
            tf = facts[k["fact"]]["trueFrom"]
            if beat_t(k["since"]) < beat_t(tf):
                err(f"{c['id']}: knows {k['fact']} from {k['since']}, but the fact only becomes true at {tf} (spoiler) / {k['since']} から {k['fact']} を知っているが、その事実は {tf} で初めて成立する（ネタバレ）")

    for f in world["facts"]:
        if any(not isinstance(x, str) or not x for x in f.get("spoilerTerms", [])):
            err(f"{f['id']}: spoilerTerms must be non-empty strings / spoilerTerms は空でない文字列でなければならない")
        if f["trueFrom"] != "pre" and f["trueFrom"] not in beats:
            err(f"{f['id']}: trueFrom references a beat that does not exist / trueFrom が存在しないビートを参照: {f['trueFrom']}")
        if not f.get("cite"):
            err(f"{f['id']}: missing citation / 出典がない")

    for p in world["places"]:
        for adj in p.get("adjacent", []):
            if adj["place"] not in places:
                err(f"{p['id']}: adjacent references something that does not exist / adjacent の参照先が存在しない: {adj['place']}")
        if not p.get("cite"):
            err(f"{p['id']}: missing citation / 出典がない")
        if p.get("sceneRef") is not None and p["sceneRef"] not in scenes:
            err(f"{p['id']}: sceneRef does not exist / sceneRef が存在しない: {p['sceneRef']}")
    for sc in scenes.values():
        if not any(p.get("sceneRef") == sc["id"] for p in world["places"]):
            err(f"{sc['id']}: no place points to this scene / このシーンを指す場所がない")

    # ---------- Beats and time / ビートと時間 ----------
    ordered = sorted(world["beats"], key=lambda b: b["order"])
    prev = None
    for b in ordered:
        w = b["window"]
        if not (w["earliest"] <= w["canonical"] <= w["latest"]):
            err(f"{b['id']}: invalid time window / 時間枠が成り立たない: {w}")
        if b["place"] not in places:
            err(f"{b['id']}: place does not exist / 場所が存在しない: {b['place']}")
        for ch in b["participants"]:
            if ch not in chars:
                err(f"{b['id']}: participant does not exist / 参加者が存在しない: {ch}")
        for cnd in b["preconditions"]:
            check_value(cnd["var"], cnd["value"], f"{b['id']}.preconditions")
        check_effects(b["outcomes"], f"{b['id']}.outcomes")
        for v in b.get("variants", []):                   # 1.4: when due, play it differently per state / 状態で演じ方を変える
            wv = f"{b['id']}.variants/{v.get('id')}"
            if not v.get("id") or v["id"] in ids:
                err(f"{wv}: a variant needs a unique id / バリアントには一意の id が必要")
            ids[v.get("id")] = "beats"
            if not v.get("when") or not v.get("summary") or v.get("inferred") is not True:
                err(f"{wv}: a variant needs when, summary and inferred: true / バリアントには when、summary、inferred: true が必要")
            for cnd in v.get("when", []):
                check_value(cnd["var"], cnd["value"], wv)
            check_effects(v.get("outcomes", []), wv)
        if b.get("variants") and b["kind"] == "anchor":
            err(f"{b['id']}: an anchor beat cannot have variants (R1) / アンカーのビートはバリアントを持てない（R1）")
        if not b.get("cite"):
            err(f"{b['id']}: missing citation / 出典がない")
        # World events such as weather; the original story may mention them later
        # 天候などの世界のイベント。原作ではもっと後で書かれることがある
        world_event = b["kind"] == "anchor" and not b["participants"]
        if prev and not world_event and w["canonical"] < prev["window"]["canonical"]:
            warn(f"{b['id']} (order {b['order']}): canonical time earlier than {prev['id']}; the story order and the times disagree / canonical の時刻が {prev['id']} より早く、原作の順序と時刻が一致しない")
        if not world_event:
            prev = b

    clk = world["clock"]
    expect_deadline = 3 * 1440 + clk["sunsetMinuteOfDay"]
    if clk["deadline"]["t"] != expect_deadline:
        err(f"Deadline {clk['deadline']['t']} is not sunset on Day 3 {expect_deadline} / 期限 {clk['deadline']['t']} が Day 3 の日没 {expect_deadline} と一致しない")
    for r in clk.get("onDeadline", []):
        for cnd in r["if"]:
            check_value(cnd["var"], cnd["value"], "clock.onDeadline.if")
        check_effects(r["then"], "clock.onDeadline.then")

    # ---------- Causality / 因果 ----------
    graph = defaultdict(list)
    for e in world["causal"]:
        for end in (e["from"], e["to"]):
            if end not in beats and end not in svars:
                err(f"{e['id']}: reference does not exist / 参照先が存在しない: {end}")
        if e["from"] in beats and e["to"] in beats:
            graph[e["from"]].append(e["to"])
            if beat_t(e["from"]) > beat_t(e["to"]):
                warn(f"{e['id']}: from is later than to / from の時刻が to より遅い")
        if not e.get("inferred") and not e.get("cite"):
            warn(f"{e['id']}: marked as not inferred but has no citation / 推定ではないとされているのに出典がない")
        if e["type"] in ("delays", "hastens") and not isinstance(e.get("minutes"), int):
            err(f"{e['id']}: a {e['type']} edge needs integer minutes / {e['type']} のエッジには整数の minutes が必要")
    seen, stack = set(), set()

    def dfs(n):
        if n in stack:
            err(f"The causal graph has a cycle through / 因果グラフに循環がある: {n}")
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
            err(f"{e['id']}: timeLink can only be shift / order, and only on enables / requires (contracts 2.5.1, 1.1) / timeLink は shift / order のみで、enables / requires にだけ使う")

    # ---------- Roles, anchors / ロール、アンカー ----------
    for r in world["roles"]:
        if r["startPlace"] not in places:
            err(f"{r['id']}: startPlace does not exist / startPlace が存在しない")
        for x in r["knownCharacters"]:
            if x not in chars:
                err(f"{r['id']}: knownCharacters does not exist / knownCharacters が存在しない: {x}")
        for x in r["access"]:
            if x not in places:
                err(f"{r['id']}: access does not exist / access が存在しない: {x}")
        for ca in r.get("conditionalAccess", []):
            if ca["place"] not in places:
                err(f"{r['id']}: conditionalAccess place does not exist / conditionalAccess の場所が存在しない: {ca['place']}")
            if not ca.get("when"):
                err(f"{r['id']}: conditionalAccess needs when / conditionalAccess には when が必要")
            for cnd in ca.get("when", []):
                check_value(cnd["var"], cnd["value"], f"{r['id']}.conditionalAccess")
        for x in r["initialKnowledge"]:
            if x not in facts:
                err(f"{r['id']}: initialKnowledge does not exist / initialKnowledge が存在しない: {x}")
            elif facts[x]["trueFrom"] != "pre" and beat_t(facts[x]["trueFrom"]) > r["startT"]:
                err(f"{r['id']}: knows {x} from the opening, but the fact is not yet true at the opening / オープニングから {x} を知っているが、その事実はオープニング時点でまだ成立していない")
    for r in world["roles"]:
        if r.get("release") not in (1, 2, 3):
            err(f"{r['id']}: release must be 1/2/3 / release は 1/2/3 のいずれか")
        act = acts.get(r.get("startAct"))
        if act is None:
            err(f"{r['id']}: startAct does not exist / startAct が存在しない: {r.get('startAct')}")
        else:
            if not (act["start"]["t"] <= r["startT"] <= act["end"]["atLatest"]):
                err(f"{r['id']}: startT {r['startT']} is outside the time of {act['id']} / startT {r['startT']} が {act['id']} の時間外")
            sref = next((p.get("sceneRef") for p in world["places"] if p["id"] == r["startPlace"]), None)
            if sref not in act["scenes"]:
                err(f"{r['id']}: starting scene {sref} is not among {act['id']}'s scenes / 開始シーン {sref} が {act['id']} のシーンにない")

    # ---------- Acts (S-004) / 幕（S-004） ----------
    # 1.5: (location, option, time chosen), used to check melosMinutes in the scenario simulation
    # 1.5：（位置, 選択肢, 選んだ時刻）。シナリオのシミュレーションで melosMinutes を照合する
    enroute_minutes = []
    for i, act in enumerate(sorted(acts.values(), key=lambda x: x["order"])):
        where = act["id"]
        if act["order"] != i + 1:
            err(f"{where}: order must be consecutive, starting at 1 / order は 1 から連続でなければならない")
        if act["start"]["t"] > act["end"]["atLatest"]:
            err(f"{where}: start time is later than the latest end of act / 開始時刻が幕を閉じる最遅時刻より遅い")
        for b in act["end"]["onBeats"]:
            if b not in beats:
                err(f"{where}: end-of-act beat does not exist / 幕を閉じるビートが存在しない: {b}")
            elif not (act["start"]["t"] <= beats[b]["window"]["canonical"] <= act["end"]["atLatest"]):
                err(f"{where}: the original time of end-of-act beat {b} is outside this act / 幕を閉じるビート {b} の原作の時刻がこの幕の外")
        for sc in act["scenes"]:
            if sc not in scenes:
                err(f"{where}: scene does not exist / シーンが存在しない: {sc}")
        if not act["exits"] and act["order"] != len(acts):
            err(f"{where}: not the last act but has no end-of-act exits / 最後の幕ではないのに幕末の行き先がない")
        landings = [(f"{where}/{ex['id']}", ex) for ex in act["exits"]]
        # 1.7 (C-19): where a plan lands when it works out; check the next act, place and time like exits
        # 1.7（C-19）：プランが成立したときの着地点。行き先と同様に次の幕、場所、時刻を確認する
        if act.get("plan"):
            landings.append((f"{where}.plan", act["plan"]))
        for w2, ex in landings:
            to = acts.get(ex["toAct"])
            if to is None or to["order"] <= act["order"]:
                err(f"{w2}: invalid toAct / toAct が無効: {ex['toAct']}")
                continue
            if ex["place"] not in places:
                err(f"{w2}: place does not exist / 場所が存在しない: {ex['place']}")
            else:
                sref = next(p.get("sceneRef") for p in world["places"] if p["id"] == ex["place"])
                if sref not in to["scenes"]:
                    err(f"{w2}: the exit's scene {sref} is not among {to['id']}'s scenes / 行き先のシーン {sref} が {to['id']} のシーンにない")
            if not (to["start"]["t"] <= ex["t"] <= to["end"]["atLatest"]):
                err(f"{w2}: jump time {ex['t']} is outside {to['id']} / 飛び先の時刻 {ex['t']} が {to['id']} の外")
            if "id" not in ex:                         # Act.plan has only a landing and fixed effects / 着地点と固定の効果だけ
                check_effects(ex.get("effects", []), f"{w2}.effects")
                continue
            if ex.get("alignTo") and ex["alignTo"] not in beats:
                err(f"{w2}: alignTo beat does not exist / alignTo のビートが存在しない: {ex['alignTo']}")
            for r in ex.get("roles", []):
                if r not in {x["id"] for x in world["roles"]}:
                    err(f"{w2}: role does not exist / ロールが存在しない: {r}")
            for cnd in ex.get("requires", []):
                check_value(cnd["var"], cnd["value"], f"{w2}.requires")
            check_effects(ex.get("effects", []), f"{w2}.effects")
            er = ex.get("enRoute")                        # 1.4: interlude either-or (UX proofreading 3.2) / 幕間の二択
            if er:
                eb = beats.get(er.get("beat"))
                chs = er.get("choices", [])
                ends = [beats[b]["window"]["canonical"] for b in act["end"]["onBeats"] if b in beats]
                if eb is None:
                    err(f"{w2}.enRoute: beat does not exist / ビートが存在しない: {er.get('beat')}")
                elif eb["kind"] == "anchor":
                    err(f"{w2}.enRoute: an anchor beat cannot be changed / アンカーのビートは変えられない: {eb['id']}")
                else:
                    if not (min(ends, default=act["start"]["t"]) <= eb["window"]["canonical"] <= ex["t"]):
                        err(f"{w2}.enRoute: {eb['id']} is not on the skipped stretch (between end of act {ends} and {ex['t']}) / {eb['id']} が飛ばす区間（幕を閉じる {ends} から {ex['t']} の間）にない")
                if not er.get("line") or len(chs) != 2 or any(not x.get("label") for x in chs):
                    err(f"{w2}.enRoute: needs line and exactly two options with label / line と、label 付きの選択肢がちょうど 2 つ必要")
                elif chs[-1].get("effects") or chs[-1].get("melosMinutes") or chs[-1].get("after"):
                    err(f"{w2}.enRoute: the last option is \"as in the original\"; its effects must be empty, with no melosMinutes or after / 最後の選択肢は「原作どおり」で、effects は空、melosMinutes と after も書かない")
                for x in chs:
                    check_effects(x.get("effects", []), f"{w2}.enRoute")
                    # 1.5: the button states its effect on Melos / ボタンにメロスへの影響を書く
                    moves = any(e.get("op") == "beat" for e in x.get("effects", []))
                    if moves and not isinstance(x.get("melosMinutes"), int):
                        err(f"{w2}.enRoute「{x.get('label')}」: an option that changes beats needs integer melosMinutes (contracts 2.8, 1.5) / ビートを変える選択肢には整数の melosMinutes が必要")
                    elif moves:
                        enroute_minutes.append((f"{w2}.enRoute「{x['label']}」", x, max(ends, default=act["start"]["t"])))
                    if "after" in x and not (isinstance(x["after"], str) and x["after"]):
                        err(f"{w2}.enRoute「{x.get('label')}」: after must be one Japanese sentence / after は日本語の一文でなければならない")
    # ---------- (1.7, C-18) Spots / 立ち位置 ----------
    scenes_dir = Path(a.scenes_dir) if a.scenes_dir else Path(a.src).resolve().parents[3] / "assets" / "scenes"
    # Scene ID → {spot: place} (scene.json generated by the frontend) / シーン ID → {立ち位置: 場所}（フロントエンドが生成）
    layouts = {}
    for sc in scenes:
        f = scenes_dir / sc.removeprefix("scene.") / "scene.json"
        if f.exists():
            layouts[sc] = {k: v["place"] for k, v in json.loads(f.read_text(encoding="utf-8"))["spots"].items()}
    scene_of = {p["id"]: p.get("sceneRef") for p in world["places"]}

    def check_spot(place, spot, where):
        lay = layouts.get(scene_of.get(place))
        if lay is None:
            err(f"{where}: the scene of {place} has no layout yet ({scenes_dir}), so spot {spot} cannot be used / {place} のシーンにまだレイアウトがなく（{scenes_dir}）、立ち位置 {spot} を書けない")
        elif spot not in lay:
            err(f"{where}: spot {spot} is not in the layout of {scene_of[place]} / 立ち位置 {spot} が {scene_of[place]} のレイアウトにない")
        elif lay[spot] != place:
            err(f"{where}: spot {spot} belongs to {lay[spot]}, not {place} / 立ち位置 {spot} は {place} ではなく {lay[spot]} に属する")

    def walk_spots(x, where):
        if isinstance(x, dict):
            where = x.get("id", where)
            if x.get("op") == "relocate" and "spot" in x:
                check_spot(x["place"], x["spot"], where)
            for y in x.values():
                walk_spots(y, where)
        elif isinstance(x, list):
            for y in x:
                walk_spots(y, where)

    walk_spots(world, "$")
    for act in acts.values():
        landings = [(f"{act['id']}/{ex['id']}", ex) for ex in act["exits"]]
        if act.get("plan"):
            landings.append((f"{act['id']}.plan", act["plan"]))
        for w2, ex in landings:
            if "spot" in ex:
                check_spot(ex["place"], ex["spot"], w2)
            arr = ex.get("arrival")
            if arr is not None:
                if not arr.get("line"):
                    err(f"{w2}.arrival: needs line (one line of narration on landing) / line（着地時のナレーション 1 行）が必要")
                if "opener" in arr and arr["opener"] not in chars:
                    err(f"{w2}.arrival: opener is not a character / opener が登場人物ではない: {arr['opener']}")
    for a_ in world.get("affordances", []):           # 1.7: where the player stands afterwards / 実行後の立ち位置
        if "playerSpot" in a_:
            check_spot(a_["place"], a_["playerSpot"], f"{a_['id']}.playerSpot")
    for c in world["characters"]:
        if c.get("group") and c.get("talkable"):
            err(f"{c['id']}: a group (a crowd) cannot be talked to / group（群れ）とは会話できない")

    used_scenes = {sc for act in acts.values() for sc in act["scenes"]}
    for sc in scenes:
        if sc not in used_scenes:
            warn(f"{sc}: no act uses this scene / このシーンを使う幕がない")

    # ---------- Characters' mutual help, promises, plans (S-029, S-030, S-048) / 登場人物の助け合い、約束、プラン ----------
    role_ids = {x["id"] for x in world["roles"]}
    for c in world["characters"]:
        w2 = c["id"]
        aids = c.get("mutualAid", [])
        for x in aids:
            if x.get("direction") not in ("forYou", "fromYou") or not x.get("text"):
                err(f"{w2}/{x['id']}: direction must be forYou / fromYou and text must not be empty / direction は forYou / fromYou で、text は空にできない")
            if x.get("opening") and x["opening"] not in role_ids:
                err(f"{w2}/{x['id']}: opening role does not exist / opening のロールが存在しない: {x['opening']}")
            if "major" in x and (x["major"] is not True or x["direction"] != "forYou"):
                err(f"{w2}/{x['id']}: major can only be true and only for forYou (S-041 \"one big thing done for you\") / major は true のみで、forYou にだけ使う（S-041 の「あなたのための大きなこと」）")
            for cnd in x.get("when", []):
                check_value(cnd["var"], cnd["value"], f"{w2}/{x['id']}.when")
            check_effects(x.get("effects", []), f"{w2}/{x['id']}.effects")     # 1.4
            if not x.get("inferred") and not x.get("cite"):
                err(f"{w2}/{x['id']}: needs a citation unless inferred / 推定でなければ出典が必要")
        for x in c.get("promiseTemplates", []):
            if x.get("by") != "player" and x.get("by") not in chars:
                err(f"{w2}/{x['id']}: by must be player or a character ID / by は player か登場人物 ID")
        for x in c.get("plans", []):
            if x.get("act") not in acts or not x.get("text"):
                err(f"{w2}: a plan's act does not exist or its text is empty / plans の幕が存在しないか text が空: {x.get('act')}")
            if not x.get("inferred") and not x.get("cite"):
                err(f"{w2}: plans[{x.get('act')}] needs a citation unless inferred / 推定でなければ出典が必要")
        if c["talkable"]:
            dirs = {x.get("direction") for x in aids}
            if dirs != {"forYou", "fromYou"}:
                err(f"{w2}: a talkable character needs at least one \"what they can do for you\" and one \"what you can do for them\" (S-029) / 会話できる登場人物には「あなたのためにできること」と「あなたがその人のためにできること」が少なくとも 1 つずつ必要: {sorted(d for d in dirs if d)}")
            if not c.get("plans"):
                err(f"{w2}: a talkable character needs plans (S-030) / 会話できる登場人物にはプランが必要（S-030）")
    for r in world["roles"]:
        if r.get("release") != 1:
            continue
        dirs = {x["direction"] for c in world["characters"] for x in c.get("mutualAid", []) if x.get("opening") == r["id"]}
        if dirs != {"forYou", "fromYou"}:
            err(f"{r['id']}: a release-1 role needs a pair of opening mutual help (S-048) / 第 1 版のロールにはオープニングの助け合いが 1 組必要: {sorted(dirs)}")

    # ---------- Clock labels (S-037, UX 4.2) / 時刻ラベル ----------
    lab = clk.get("labels", {})
    if len(lab.get("days", [])) != 4:
        err("clock.labels.days needs 4 entries (約束の日〜三日目) / clock.labels.days は 4 つ必要（約束の日〜三日目）")
    bands = lab.get("bands", [])
    if not bands or bands[0][0] != 0 or any(a[0] >= b[0] for a, b in zip(bands, bands[1:])) or bands[-1][0] >= 1440:
        err("clock.labels.bands must start at 0, strictly increase and stay below 1440 / clock.labels.bands は 0 から始まり、狭義単調増加で、1440 未満")
    if "{day}" not in lab.get("format", "") or "{band}" not in lab.get("format", ""):
        err("clock.labels.format must contain {day} and {band} / clock.labels.format には {day} と {band} が必要")
    if "daysKnownBy" in lab and lab["daysKnownBy"] not in facts:
        err(f"clock.labels.daysKnownBy is not a fact in the world model / clock.labels.daysKnownBy が世界モデルの事実ではない: {lab['daysKnownBy']}")

    # ---------- Names shown to the player: the role's one line, character readings, the ruby list (1.10, B-7 manifest)
    # プレイヤーに見せる名前：ロールの一文、登場人物の読み、ルビの語表（1.10、B-7 の manifest） ----------
    kanji = re.compile(r"[\u3400-\u9fff々〆ヶ]")
    for r in world["roles"]:
        if not r.get("summary"):
            err(f"{r['id']}: needs summary (the line shown to the player on the role page and in the manifest) / summary（ロールページと manifest でプレイヤーに見せる一文）が必要")
    for c in world["characters"]:
        if not c.get("reading"):
            err(f"{c['id']}: needs reading (every character in the manifest has a reading) / reading が必要（manifest の各登場人物は読みを持つ）")
        elif kanji.search(c["reading"]):
            err(f"{c['id']}: reading must not contain kanji / reading に漢字を含めない: {c['reading']}")
    body = "\n".join(paras) + json.dumps({k: v for k, v in world.items() if k != "ruby"}, ensure_ascii=False)
    seen = set()
    for x in world.get("ruby", []):
        word, rd = x["word"], x["reading"]
        if word in seen:
            err(f"ruby: duplicate word / 語の重複: {word}")
        seen.add(word)
        if not kanji.search(word):
            err(f"ruby: {word} has no kanji and needs no ruby / {word} に漢字がなく、ルビは不要")
        if not re.fullmatch(r"[ぁ-ゖー]+", rd):
            err(f"ruby: the reading of {word} must be all hiragana / {word} の読みはすべてひらがなでなければならない: {rd}")
        if word not in body:
            err(f"ruby: {word} appears in neither the source text nor the world model (a typo?) / {word} が原文にも世界モデルにも現れない（書き間違い？）")

    # ---------- Endings: characters' 「原作では」, templates (1.11, B-9; ux-design 11.2〜11.4, S-065, S-067)
    # 結末：登場人物の「原作では」、テンプレート ----------
    # S-067: the execution is only told indirectly. These expressions could appear in any ending (templates, 「原作では」)
    # and are never used (UX added the last few in the #97 review)
    # S-067：処刑は間接的にしか伝えない。これらの表現はどの結末にも現れうる（テンプレート、「原作では」）ので一切使わない
    # （UX が #97 のレビューで後半のいくつかを追加）
    death_words = ("処刑", "死", "殺", "最期", "亡くな", "命を落と", "息絶え", "絶命", "事切れ", "帰らぬ人", "磔にされ", "磔になっ")

    def no_death_words(text, where):
        hit = [x for x in death_words if x in text]
        if hit:
            err(f"{where}: ending text must not state death directly (S-067) / 結末の文章で死を直接書かない: {'、'.join(hit)}")

    cmap_e = {c["id"]: c for c in world["characters"]}
    ends = world.get("endings", {})
    listed = ends.get("characters", [c["id"] for c in world["characters"] if c["talkable"]])
    if len(set(listed)) != len(listed):
        err("endings.characters has duplicate characters / endings.characters に登場人物の重複がある")
    for cid in listed:
        c = cmap_e.get(cid)
        if c is None:
            err(f"endings.characters: not a character / 登場人物ではない: {cid}")
        elif not c.get("originalEnding"):
            err(f"{cid}: a character listed on the ending page needs originalEnding (the 「原作では」 line) / 結末ページに載せる登場人物には originalEnding（「原作では」の一文）が必要")
    for c in world["characters"]:
        oe = c.get("originalEnding")
        if not oe:
            continue
        if len(oe["text"]) > 40 or not oe["text"].endswith("。"):
            err(f"{c['id']}.originalEnding: one sentence, ≤ 40 characters, ending in 「。」 (now {len(oe['text'])}) / 一文、40 字以内、「。」で終わる（今は {len(oe['text'])} 字）")
        if not oe.get("cite"):
            err(f"{c['id']}.originalEnding: needs a citation / 出典が必要")
        no_death_words(oe["text"], f"{c['id']}.originalEnding")
    outcomes = [e["id"] for e in ends.get("world", [])]
    templates = ends.get("templates", [])
    if templates:
        by_outcome = defaultdict(list)
        for i, tp in enumerate(templates):
            w2 = f"endings.templates[{i}]（{tp['outcome']}）"
            if tp["outcome"] not in outcomes:
                err(f"{w2}: outcome is not a baseline class of world ending / outcome が世界の結末の基本分類ではない")
            by_outcome[tp["outcome"]].append(tp)
            for cnd in tp.get("when", []):
                check_value(cnd["var"], cnd["value"], f"{w2}.when")
            if len(tp["subtitle"]) > 26:
                err(f"{w2}: subtitle ≤ 26 characters (now {len(tp['subtitle'])}) / subtitle は 26 字以内（今は {len(tp['subtitle'])}）")
            if tp["title"].count("{role}") != 1 or len(tp["title"].replace("{role}", "")) > 9:
                err(f"{w2}: title needs one {{role}} and ≤ 9 characters without it / title には {{role}} が 1 つ必要で、それを除いて 9 字以内")
            if len(tp["contrast"]) > 48:
                err(f"{w2}: contrast ≤ 48 characters (now {len(tp['contrast'])}) / contrast は 48 字以内（今は {len(tp['contrast'])}）")
            for ln in tp["lines"]:
                if ln["character"] not in cmap_e:
                    err(f"{w2}: character in lines does not exist / lines の登場人物が存在しない: {ln['character']}")
                if len(ln["line"]) > 40:
                    err(f"{w2}: the line of {ln['character']} ≤ 40 characters (now {len(ln['line'])}) / {ln['character']} の一文は 40 字以内（今は {len(ln['line'])}）")
            if "fate" not in tp and not ends.get("fates"):
                err(f"{w2}: without fate, endings.fates is required / fate がなければ endings.fates が必要")
            # The player is the hostage; fate.id is not witness / elsewhere
            # プレイヤーが人質なので、fate.id は witness / elsewhere ではない
            if "fate" not in tp and tp["outcome"] == "player-substituted":
                err(f"{w2}: a player-substituted template needs fate (endings.fates has only witness, elsewhere) / player-substituted のテンプレートには fate が必要（endings.fates は witness、elsewhere のみ）")
            for k in ("subtitle", "title", "fate", "contrast"):
                if k in tp:
                    no_death_words(tp[k], f"{w2}.{k}")
            for ln in tp["lines"]:
                no_death_words(ln["line"], f"{w2}.lines")
        for oc in outcomes:
            tps = by_outcome.get(oc, [])
            if not tps:
                err(f"endings.templates: world ending {oc} has no template / 世界の結末 {oc} にテンプレートがない")
            elif "when" in tps[-1] or any("when" not in x for x in tps[:-1]):
                err(f"endings.templates: {oc}: only the last one has no when (the fallback); all before it need one / 最後の 1 件だけ when なし（フォールバック）で、それより前はすべて when が必要")
    for k, v in ends.get("fates", {}).items():
        no_death_words(v, f"endings.fates.{k}")

    # ---------- Situational actions and items (contracts 2.10; S-036 ②, S-038, UX 5.1) / 状況アクションとアイテム ----------
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
                err(f"{x['id']}: gives is only for forYou and must be a portable item / gives は forYou 専用で、portable なアイテムでなければならない: {x['gives']}")
    for owner, lst in list(role_items.items()) + list(char_items.items()):
        for i in lst:
            if not items.get(i, {}).get("portable"):
                err(f"{owner}: {i} in items does not exist or is not portable / items の {i} が存在しないか portable ではない")
    for it in items.values():
        if not it.get("name"):
            err(f"{it['id']}: missing name / name がない")
        # 1.3: one physical object, in at most one character's hands at the opening
        # 1.3：実物 1 つで、オープニングでは多くとも 1 人の登場人物の手にある
        if it.get("portable"):
            holders = [c for c, lst in char_items.items() if it["id"] in lst]
            in_roles = [r for r, lst in role_items.items() if it["id"] in lst]
            if len(holders) > 1 or (holders and in_roles):
                err(f"{it['id']}: can be in only one person's hands at the opening (characters {holders}, roles {in_roles}) / オープニングでは 1 人の手にしかあってはならない（登場人物 {holders}、ロール {in_roles}）")
            if not holders and not in_roles and it["id"] not in gives:
                warn(f"{it['id']}: nobody holds it at the opening and no mutual help gives it to the player / オープニングで誰も持っておらず、プレイヤーに渡す助け合いもない")
            if it.get("at"):
                warn(f"{it['id']}: portable items normally do not have at / portable なアイテムには通常 at を書かない")
        elif not it.get("at"):
            err(f"{it['id']}: an item that cannot be carried needs at (where it is at hand) / 持ち歩けないアイテムには at（どこで手に入るか）が必要")
        for pl in it.get("at", []):
            if pl not in places:
                err(f"{it['id']}: at place does not exist / at の場所が存在しない: {pl}")
    by_place = defaultdict(set)
    for af in world.get("affordances", []):
        w2 = af["id"]
        act = acts.get(af.get("act")) if af.get("act") else None
        if af.get("act") and act is None:
            err(f"{w2}: act does not exist / 幕が存在しない: {af.get('act')}")
        if af.get("place") not in places:
            err(f"{w2}: place does not exist / 場所が存在しない: {af.get('place')}")
        else:
            sref = next(p.get("sceneRef") for p in world["places"] if p["id"] == af["place"])
            if sref is None:
                err(f"{w2}: place {af['place']} has no scene, so no action can go there / 場所 {af['place']} にシーンがなく、アクションを置けない")
            elif act is not None and sref not in act["scenes"]:
                err(f"{w2}: the place's scene {sref} is not in {act['id']} / 場所のシーン {sref} が {act['id']} にない")
        if af.get("kind") not in UX_ACTIONS:
            err(f"{w2}: kind is not in UX's action list / kind が UX のアクション一覧にない: {af.get('kind')}")
        if not af.get("label") or any(ch in af["label"] for ch in "（(0123456789"):
            err(f"{w2}: label must be a verb phrase without the duration (the frontend adds minutes) / label は動詞句で、所要時間は書かない（フロントエンドが minutes で組み立てる）: {af.get('label')!r}")
        pl = af.get("pastLabel")  # 1.8: event sentence / イベント文「{ロール名}は、{pastLabel}」
        if not pl or "。" in pl or pl[-1] not in "ただ" or len(pl) > 30 or pl == af.get("label"):
            err(f"{w2}: pastLabel must be a sentence for after it is done (past tense ending in 「〜た」, with an object, no 「。」, at most 30 characters) / pastLabel は実行後の一文（過去形「〜た」で終わり、対象を含み、「。」なし、30 字以内）: {pl!r}")
        for r in af.get("roles", []):
            if r not in role_ids:
                err(f"{w2}: role does not exist / ロールが存在しない: {r}")
        if af.get("target") and af["target"] not in chars:
            err(f"{w2}: target is not a character / target が登場人物ではない: {af['target']}")
        if af.get("kind") == "give" and af.get("item") not in items:
            err(f"{w2}: give needs an existing item / give には存在する item が必要: {af.get('item')}")
        if af.get("item") in items and af.get("kind") == "give" and af["place"] not in items[af["item"]]["at"] \
                and not (af.get("roles") and all(af["item"] in role_items[r] for r in af["roles"])):
            err(f"{w2}: {af['item']} cannot be had at {af['place']} (not an at place, and the role does not start with it) / {af['place']} では {af['item']} が手に入らない（at の場所ではなく、ロールも最初から持っていない）")
        if af.get("aid") and aid_dir.get(af["aid"]) != "fromYou":
            err(f"{w2}: aid must be a fromYou mutual help / aid は fromYou の助け合いでなければならない: {af.get('aid')}")
        m = af.get("minutes")
        if not isinstance(m, int) or m < 0:
            err(f"{w2}: minutes must be a non-negative integer / minutes は 0 以上の整数でなければならない")
        elif af.get("kind") not in ("examine", "wait", "go", "run-together") and not lo <= m <= hi:
            err(f"{w2}: situational action takes {m}, outside pacing's {lo}〜{hi} minutes (S-038) / 状況アクションの所要時間 {m} が pacing の {lo}〜{hi} 分の範囲外")
        for cnd in af.get("when", []):
            check_value(cnd["var"], cnd["value"], f"{w2}.when")
        effs = af.get("effects", [])
        check_effects(effs, w2)
        tos = set()
        for e in effs:
            if e.get("op") == "beat":
                if e.get("to") in ("delayed", "hastened") and not isinstance(e.get("minutes"), int):
                    err(f"{w2}: {e['to']} needs integer minutes / {e['to']} には整数の minutes が必要")
                tos.add(e.get("to"))
        mel = af.get("melos")
        if mel == "delay":
            if "delayed" not in tos:
                err(f"{w2}: melos=delay effects need a delayed beat / melos=delay の効果には delayed のビートが必要")
            by_place[af["place"]].add("slower")
        elif mel == "hasten":
            if not tos & {"hastened", "prevented"}:
                err(f"{w2}: melos=hasten effects need a hastened or prevented beat / melos=hasten の効果には hastened か prevented のビートが必要")
            by_place[af["place"]].add("faster")
        elif mel is not None:
            err(f"{w2}: melos can only be delay / hasten / melos は delay / hasten のみ")
        if mel and (af.get("act") != "act.4" or af.get("target") != "char.melos"):
            err(f"{w2}: melos is only for act 4 actions targeting Melos / melos は第四幕でメロスを対象とするアクション専用")
        if mel and not isinstance(af.get("melosMinutes"), int):
            err(f"{w2}: an action with melos needs integer melosMinutes (the button states its effect on Melos, contracts 2.10, 1.4) / melos のあるアクションには整数の melosMinutes が必要（ボタンにメロスへの影響を書く）")
        elif mel and (af["melosMinutes"] > 0) != (mel == "delay"):
            err(f"{w2}: the sign of melosMinutes disagrees with melos={mel} / melosMinutes の符号が melos={mel} と一致しない")
    for pl, kinds in by_place.items():
        if kinds != {"slower", "faster"}:
            err(f"{pl}: every act 4 place needs both actions that slow him and actions that speed him up (S-036 ②); only / 第四幕の各場所には彼を遅らせるアクションと速めるアクションの両方が必要。今あるのは: {sorted(kinds)}")

    # ---------- (1.8) Role names only refer to the player (contracts 2.7): when sending, the server replaces role names
    # with 「あなた」 / ロール名はプレイヤーを指すためだけに使う：送信時にサーバーがロール名を「あなた」に置き換える ----------
    role_names = {r["id"]: (r["name"], r.get("release")) for r in world["roles"]}
    for rid, (nm, _) in role_names.items():
        for rid2, (nm2, _) in role_names.items():
            if rid != rid2 and nm in nm2:
                err(f"{rid}: role name 「{nm}」 is contained in {rid2}'s 「{nm2}」, so they cannot be told apart when replaced with 「あなた」 / ロール名「{nm}」が {rid2} の「{nm2}」に含まれ、「あなた」に置き換えるときに区別できない")

    # Places that describe the player: the role itself, state variable descriptions, mutual help text (IDs in the path
    # contain no 「/」) / プレイヤーを書く箇所：ロール自身、状態変数の説明、助け合いの text（パス内の ID は「/」を含まない）
    def about_player(path):
        return (path.startswith("$.roles")
                or re.fullmatch(r"\$\.stateVars/[^/]+\.description", path) is not None
                or re.fullmatch(r"\$\.characters/[^/]+\.mutualAid/[^/]+\.text", path) is not None)

    # Release-2 roles: record name clashes first and sum them up as one warning
    # 第 2 版のロール：名前の衝突をまず記録し、1 件の警告にまとめる
    later = defaultdict(list)

    def walk_names(x, path):
        if isinstance(x, dict):
            for k, v in x.items():
                if k not in ("cite", "note", "quote", "book", "_authoring"):
                    walk_names(v, f"{path}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk_names(v, f"{path}/{label(v, i)}")
        elif isinstance(x, str) and not about_player(path):
            for rid, (nm, rel) in role_names.items():
                if nm in x:
                    if rel == 1:
                        err(f"{path}: contains the release-1 role name 「{nm}」 ({rid}). Role names only refer to the player"
                            f" and are replaced with 「あなた」 when sent (contracts 2.7) / 第 1 版のロール名「{nm}」（{rid}）"
                            f"がある。ロール名はプレイヤーを指すためだけに使い、送信時に「あなた」に置き換える: {x[:40]}")
                    else:
                        later[rid].append(path)

    walk_names(world, "$")
    for rid, paths in later.items():
        warn(f"{rid}: the release-2 role name 「{role_names[rid][0]}」 also refers to something else in the world model"
             f" ({len(paths)} places, e.g. {paths[0]}); rename this role before opening release 2 (contracts 2.7)"
             f" / 第 2 版のロール名「{role_names[rid][0]}」が世界モデル内で別のものも指している（{len(paths)} か所、"
             f"例 {paths[0]}）。第 2 版を公開する前にこのロールの名前を変える")

    # Names are shown to the player as is (event sentences, manifest), without the bracketed notes used while writing the
    # world model (1.8 addendum: 「警吏（巡邏・刑吏）」→「城の警吏」)
    # 名前はそのままプレイヤーに見せる（イベント文、manifest）。世界モデルを書くときの括弧書きの注記は付けない
    # （1.8 補注：「警吏（巡邏・刑吏）」→「城の警吏」）
    for sec in ("characters", "places", "roles", "items", "objects"):
        for x in world.get(sec, []):
            if re.search(r"[（）()［］\[\]【】「」『』]", x.get("name", "")):
                err(f"{x['id']}: name 「{x['name']}」 has brackets. Names go into event sentences and the manifest as is; put notes in note (contracts 2.7) / 名前「{x['name']}」に括弧がある。名前はそのままイベント文と manifest に入るので、注記は note に書く")

    # ---------- Examinables (contracts 2.12, 1.7) / 調べられる物 ----------
    objects = {x["id"]: x for x in world.get("objects", [])}
    for ob in objects.values():
        if not ob["id"].startswith("obj."):
            err(f"{ob['id']}: examinable IDs start with obj. / 調べられる物の ID は obj. で始まる")
        if ob.get("place") not in places:
            err(f"{ob['id']}: place does not exist / 場所が存在しない: {ob.get('place')}")
        elif scene_of.get(ob["place"]) is None:
            err(f"{ob['id']}: place {ob['place']} has no scene, so no examinable can go there / 場所 {ob['place']} にシーンがなく、調べられる物を置けない")
        elif "spot" in ob:
            check_spot(ob["place"], ob["spot"], f"{ob['id']}.spot")
        if not ob.get("label"):
            err(f"{ob['id']}: label must not be empty / label は空にできない")

    # ---------- Set pieces (contracts 2.11, 1.7, S-080 ④) / 固定演出 ----------
    piece_ids = {x["id"] for x in world.get("setPieces", [])}
    cmap = {c["id"]: c for c in world["characters"]}
    # Moment → the first set piece at this moment with no conditions at all: anything after it never gets its turn
    # タイミング → このタイミングで最初の、条件が何もない固定演出：その後に並ぶものは永遠に順番が回ってこない
    unconditional = {}
    for sg in world.get("setPieces", []):
        w2, on = sg["id"], sg.get("on", {})
        if "beat" in on:
            hook = ("beat", on["beat"])
            if on["beat"] not in beats:
                err(f"{w2}: on.beat does not exist / on.beat が存在しない: {on['beat']}")
        else:
            hook = ("act", on.get("act"), on.get("target"), on.get("refused", False))
            tgt, kind = on.get("target"), on.get("act")
            if kind not in UX_ACTIONS | {"move"}:
                err(f"{w2}: on.act is not an api-contract 3.8 action / on.act が api-contract 3.8 のアクションではない: {kind}")
            if tgt is None:
                pass
            elif kind in ("move", "go"):
                if tgt not in places:
                    err(f"{w2}: the target of {kind} must be an existing place (for go, the place the exit leads to) / {kind} の target は存在する場所（go なら出口の行き先）でなければならない: {tgt}")
            elif kind == "examine":
                if tgt not in objects:
                    err(f"{w2}: the target of examine must be an examinable in objects (2.12) / examine の target は objects の調べられる物でなければならない: {tgt}")
            elif tgt not in chars:
                err(f"{w2}: the target of {kind} must be an existing character / {kind} の target は存在する登場人物でなければならない: {tgt}")
        for k in ("after", "before"):
            for b in sg.get(k, []):
                if b not in beats:
                    err(f"{w2}: beat in {k} does not exist / {k} のビートが存在しない: {b}")
        if set(sg.get("after", [])) & set(sg.get("before", [])):
            err(f"{w2}: the same beat cannot be in both after and before / 同じビートを after と before の両方に入れられない")
        for kn in sg.get("knows", []):
            if kn["character"] not in chars:
                err(f"{w2}: character in knows does not exist / knows の登場人物が存在しない: {kn['character']}")
            if kn["fact"] not in facts:
                err(f"{w2}: fact in knows does not exist / knows の事実が存在しない: {kn['fact']}")
        for k in ("played", "notPlayed"):
            for x in sg.get(k, []):
                if x not in piece_ids or x == w2:
                    err(f"{w2}: {k} must reference another set piece / {k} はほかの固定演出を参照しなければならない: {x}")
        for cnd in sg.get("when", []):
            check_value(cnd["var"], cnd["value"], f"{w2}.when")
        if not sg.get("lines"):
            err(f"{w2}: lines must not be empty / lines は空にできない")
        for ln in sg.get("lines", []):
            if "speaker" in ln and ln["speaker"] not in chars:
                err(f"{w2}: speaker does not exist / speaker が存在しない: {ln['speaker']}")
        sure = {"pre", *sg.get("after", [])}  # Certainly happened when it plays / 上演時に必ず起きているもの
        speakers = {ln["speaker"] for ln in sg.get("lines", []) if ln.get("speaker") in chars}
        # S-077 ⑪: what is said must be true when it plays, and the speaker must know it
        # S-077 ⑪：語られることは上演時に必ず成立し、話し手は必ずそれを知っている
        for ln in sg.get("learns", []):
            if ln["character"] != "player" and ln["character"] not in chars:
                err(f"{w2}: character in learns does not exist / learns の登場人物が存在しない: {ln['character']}")
            f = facts.get(ln["fact"])
            if f is None:
                err(f"{w2}: fact in learns does not exist / learns の事実が存在しない: {ln['fact']}")
                continue
            if f["trueFrom"] not in sure:
                err(f"{w2}: learns {ln['fact']} only becomes true from {f['trueFrom']}; add it to after / learns {ln['fact']} は {f['trueFrom']} から成立するので、after に書く")
            if speakers and not any(
                k["fact"] == ln["fact"] and k["since"] in sure for c in speakers for k in cmap[c].get("knows", [])
            ):
                err(f"{w2}: learns {ln['fact']}: the speakers {sorted(speakers)} do not necessarily know it when it plays (the since of knows must be in after) / 話し手 {sorted(speakers)} が上演時に知っているとは限らない（knows の since を after に入れる）")
        if hook in unconditional:
            err(f"{w2}: at the same moment {unconditional[hook]} comes first with no conditions, so this one never gets its turn / 同じタイミングで {unconditional[hook]} が条件なしで先に並ぶので、これは永遠に順番が回ってこない")
        elif not any(sg.get(k) for k in ("after", "before", "knows", "played", "notPlayed", "when", "once")):
            unconditional[hook] = w2

    # ---------- Characters' states on beats, when lines and motives take effect (contracts 2.1, 2.4, 1.1)
    # ビート上の登場人物の状態、セリフと動機の有効時期 ----------
    ACTIVITIES = {"idle", "walk", "run", "talk", "work", "sleep", "absent"}
    for b in world["beats"]:
        for x in b.get("activities", []):
            if x.get("character") not in chars or x.get("activity") not in ACTIVITIES:
                err(f"{b['id']}.activities: wrong character or state / 登場人物か状態が正しくない: {x}")
    for c in world["characters"]:
        if c.get("initialActivity", "idle") not in ACTIVITIES:
            err(f"{c['id']}: initialActivity is not in / initialActivity が次にない: {sorted(ACTIVITIES)}")
        rows = [("traits", x) for x in c["traits"]] + [("goals", x) for x in c["goals"]] + \
               [("sampleLines", x) for x in c["speech"]["sampleLines"]] + \
               [("designLines", x) for x in c["speech"].get("designLines", [])]
        for part, x in rows:
            for k in ("since", "until"):
                if k in x and x[k] not in beats:
                    err(f"{c['id']}.{part}: beat in {k} does not exist / {k} のビートが存在しない: {x[k]}")
            for cnd in x.get("when", []):                 # 1.4
                check_value(cnd["var"], cnd["value"], f"{c['id']}.{part}.when")
            if part == "designLines" and (not x.get("text") or x.get("inferred") is not True):
                err(f"{c['id']}.designLines: needs text and inferred: true (lines from the source go in sampleLines) / text と inferred: true が必要（原文のセリフは sampleLines に入れる）")
            if "since" in x and "until" in x and beat_t(x["since"]) >= beat_t(x["until"]):
                err(f"{c['id']}.{part}: since must be earlier than until / since は until より前でなければならない")

    # ---------- World endings (S-007, S-034) and the ending signature (S-031 ⑤) / 世界の結末と結末のシグネチャ ----------
    ending_defs = sorted(world.get("endings", {}).get("world", []), key=lambda x: x["order"])
    for en in ending_defs:
        for cnd in en["when"]:
            check_value(cnd["var"], cnd["value"], f"endings.{en['id']}")
    sig = world.get("endings", {}).get("signature", {})
    for v in sig.get("vars", []):
        if v not in svars:
            err(f"endings.signature: state variable does not exist / 状態変数が存在しない: {v}")
    for b in sig.get("beats", []):
        if b not in beats:
            err(f"endings.signature: beat does not exist / ビートが存在しない: {b}")
    wb = clk["deadline"].get("watchBeat")
    if wb is not None and wb not in beats:
        err(f"clock.deadline.watchBeat: beat does not exist / ビートが存在しない: {wb}")
    ea = clk["deadline"].get("earliestArrival")          # 1.4, S-066
    if ea is not None and (wb not in beats or not isinstance(ea, int)
                           or not beats[wb]["window"]["earliest"] <= ea <= clk["deadline"]["t"]):
        err(f"clock.deadline.earliestArrival {ea!r} must be an integer, with watchBeat, between watchBeat's earliest and the deadline / 整数で、watchBeat があり、watchBeat の earliest と期限の間でなければならない")
    # 1.5, S-066 ①: the line said the first time the floor is reached / 初めて下限に達したときに言う一文
    cue = clk["deadline"].get("earliestArrivalCue")
    if cue is not None:
        if ea is None:
            err("clock.deadline.earliestArrivalCue must be written together with earliestArrival / clock.deadline.earliestArrivalCue は earliestArrival と一緒に書く")
        if cue.get("speaker") not in chars:
            err(f"clock.deadline.earliestArrivalCue: character does not exist / 登場人物が存在しない: {cue.get('speaker')}")
        if not all(isinstance(cue.get(k), str) and cue.get(k) for k in ("line", "narration")) or cue.get("inferred") is not True:
            err("clock.deadline.earliestArrivalCue needs line (said when the character is present), narration (narrated when absent) and inferred: true / clock.deadline.earliestArrivalCue には line（登場人物が在場なら言う）、narration（不在なら語る）、inferred: true が必要")
    for k, v in world.get("pacing", {}).items():
        if not isinstance(v, (int, float)) or v < 0:
            err(f"pacing.{k} must be a non-negative number / pacing.{k} は 0 以上の数でなければならない")

    for an in world["anchors"]:
        if an not in beats and an not in facts:
            err(f"Anchor reference does not exist / アンカーの参照先が存在しない: {an}")
        if an in beats and beats[an]["kind"] != "anchor":
            err(f"{an} is in anchors but its kind is not anchor / anchors にあるのに kind が anchor ではない")
    for b in world["beats"]:
        if b["kind"] == "anchor" and b["id"] not in world["anchors"]:
            err(f"{b['id']} has kind anchor but is not in the anchors list / kind が anchor なのに anchors の一覧にない")

    # ---------- Scenario simulation (original path + rerouting scenarios) / シナリオのシミュレーション ----------
    sim = Sim(world)
    # The original path and scenarios simulate with the first role (a scenario can name another with role)
    # 原作の経路とシナリオは最初のロールでシミュレーションする（シナリオは role で別のロールを指定できる）
    role0 = world["roles"][0]["id"]

    def simulate(sc):
        r = sim.run(sc, role=sc.get("role", role0))
        return r["outcome"], r["status"], r["times"], r["state"], r["variant"], r["violations"]

    # 1.4: melosMinutes on an act 4 button = how many minutes earlier or later Melos reaches the execution ground
    # (watchBeat) on the original path when only this one action is taken. Minutes still count when he arrives past the
    # deadline (the button says 「六十分遅れる」), so simulate on a copy with window.latest removed.
    # 1.4：第四幕のボタンの melosMinutes = このアクションだけを行ったとき、原作の経路でメロスが刑場（watchBeat）に何分
    # 早く／遅く着くか。期限を過ぎて着く場合も分数は数える（ボタンには「六十分遅れる」と書く）ので、window.latest を
    # 外したコピーでシミュレーションする。
    if wb in beats:
        loose = json.loads(json.dumps(world))
        for b in loose["beats"]:
            b["window"]["latest"] = 10 ** 9
        lsim = Sim(loose)
        for af in world.get("affordances", []):
            if not af.get("melos") or not isinstance(af.get("melosMinutes"), int):
                continue
            over = {e["beat"]: {k: v for k, v in e.items() if k not in ("op", "beat")} for e in af["effects"] if e.get("op") == "beat"}
            got = lsim.run({"beats": over}, role=role0)["shift"].get(wb, 0)
            if got != af["melosMinutes"]:
                err(f"{af['id']}: melosMinutes says {af['melosMinutes']:+d}, but the shared rules give {got:+d} on the original path / melosMinutes は {af['melosMinutes']:+d} だが、共有ルールでは原作の経路で {got:+d}")
        # 1.5: interlude options are chosen when closing the act, and non-beat effects (such as stamina) count too; use
        # the shared rules' arrival_delta (like the server: schedule once with and once without doing it)
        # 1.5：幕間の選択肢は幕を閉じるときに選び、ビート以外の効果（体力など）も含める。共有ルールの arrival_delta を
        # 使う（サーバーと同じく、実行した場合としない場合でそれぞれスケジュールを組む）
        for where_, x, t_ in enroute_minutes:
            got = sim.arrival_delta({}, x["effects"], t_, role=role0)["minutes"]
            if got != x["melosMinutes"]:
                err(f"{where_}: melosMinutes says {x['melosMinutes']:+d}, but the shared rules give {got:+d} on the original path / melosMinutes は {x['melosMinutes']:+d} だが、共有ルールでは原作の経路で {got:+d}")

    scenarios = [{"id": "sc.canon", "note": "原著どおり（プレイヤーは何もしない）", "expect": "canon-reunion"}]
    if a.scenarios:
        scenarios += json.loads(Path(a.scenarios).read_text(encoding="utf-8"))
    sim_rows, reached, sigs = [], set(), set()
    canon_status = canon_times = None
    for sc in scenarios:
        for bid, o in sc.get("beats", {}).items():
            if bid not in beats:
                err(f"{sc['id']}: beat does not exist / ビートが存在しない: {bid}")
            check_effects([{"op": "beat", "beat": bid, **o}], sc["id"])
        for ev in sc.get("events", []):
            check_effects(ev["effects"], sc["id"])
        outcome, status, times, state, variant, violations = simulate(sc)
        for t_, x in violations:                 # 1.6: scenario events obey valueRequires too / シナリオのイベントも従う
            err(f"{sc['id']}: t={t_} sets {x['var']} to {x['value']!r} but the condition {x['when']} does not hold ({x['note']}) / t={t_} に {x['var']} を {x['value']!r} に変えるが、条件 {x['when']} が成り立たない")
        if sc["id"] == "sc.canon":
            canon_status, canon_times = status, times
            for bid, st in status.items():
                if st != "happened":
                    err(f"Original path: {bid} did not happen ({st}) / 原作の経路：{bid} が起きなかった（{st}）")
        if outcome:
            reached.add(outcome)
        if sc.get("gap"):
            warn(f"{sc['id']}: {sc['note']} → fits no class of world ending ({outcome or 'none'}); PM/UX must decide / どの種類の世界の結末にも入らない（{outcome or 'なし'}）。PM/UX の判断が必要")
        elif outcome != sc.get("expect"):
            err(f"{sc['id']}: expected ending {sc.get('expect')}, got {outcome} / 期待した結末 {sc.get('expect')}、実際 {outcome}")
        for var, val in sc.get("expectVars", {}).items():
            if state.get(var) != val:
                err(f"{sc['id']}: expected {var} = {val!r}, got {state.get(var)!r} / 期待 {var} = {val!r}、実際 {state.get(var)!r}")
        for bid, want in sc.get("expectBeats", {}).items():     # 1.4: happened / altered / not-happened
            st = status.get(bid)
            got = st if st in ("happened", "altered") else "not-happened"
            if got != want:
                err(f"{sc['id']}: expected {bid} {want}, got {st} / 期待 {bid} {want}、実際 {st}")
        for bid, want in sc.get("expectTimes", {}).items():      # 1.4: expected time / 期待する発生時刻
            if times.get(bid) != want:
                err(f"{sc['id']}: expected {bid} to happen at {want}, got {times.get(bid)} / {bid} は {want} に起きるはずが、実際 {times.get(bid)}")
        for bid, want in sc.get("expectVariant", {}).items():
            if variant.get(bid) != want:
                err(f"{sc['id']}: expected {bid} to play as variant {want}, got {variant.get(bid)} / {bid} はバリアント {want} で演じるはずが、実際 {variant.get(bid)}")
        sigs.add(json.dumps([state.get(v) for v in sig.get("vars", [])] + [status.get(b) == "happened" for b in sig.get("beats", [])]))
        b24 = times.get("beat.24")
        sim_rows.append((sc["id"], sc["note"], outcome or "(none / なし)", status.get("beat.24"), b24,
                         state["var.hostage.fate"], state["var.king.disposition"],
                         f"{status.get('beat.s2', '—')} / {variant.get('beat.25', status.get('beat.25', '—'))}"))
    for en in ending_defs:
        if en["id"] not in reached:
            err(f"World ending {en['id']} is not reached by any scenario / 世界の結末 {en['id']} に到達するシナリオがない")

    # ---------- Output / 出力 ----------
    Path(a.out).write_text(json.dumps(world, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    cited = sorted(used)
    uncited = [i for i in range(1, len(paras) + 1) if i not in used]
    n_cites = sum(len(v) for v in used.values())
    rep = ["# World model validation report / 世界モデル検証レポート", "",
           f"- Source file / ソースファイル: `{a.src}`",
           f"- Source text / 原文: `{a.text}` ({len(paras)} paragraphs / 段落, sha256 `{sha}`)",
           f"- Citation source ID / 出典 ID: `{source_id}`",
           f"- Characters / 登場人物 {len(world['characters'])}, places / 場所 {len(world['places'])}, facts / 事実 {len(world['facts'])}, "
           f"beats / ビート {len(world['beats'])}, causal edges / 因果エッジ {len(world['causal'])}, "
           f"state variables / 状態変数 {len(world['stateVars'])}, roles / ロール {len(world['roles'])}, anchors / アンカー {len(world['anchors'])}",
           f"- Citations / 出典数: {n_cites}; cited paragraphs / 引用された段落 {len(cited)}/{len(paras)} ({len(cited) * 100 // len(paras)}%)",
           f"- **Errors / エラー {len(errors)}, warnings / 警告 {len(warnings)}**", ""]
    rep += ["## Errors / エラー", ""] + ([f"- {e}" for e in errors] or ["(none / なし)"]) + [""]
    rep += ["## Warnings / 警告", ""] + ([f"- {w}" for w in warnings] or ["(none / なし)"]) + [""]
    def fmt(t):
        if t is None:
            return "—"
        d, m = divmod(t, 1440)
        return f"Day {d} {m // 60:02d}:{m % 60:02d}"
    n_aid = sum(len(c.get("mutualAid", [])) for c in world["characters"])
    rep += [f"- Scenes / シーン {len(scenes)}, acts / 幕 {len(acts)}, world endings / 世界の結末 {len(ending_defs)} "
            f"(reachable by scenarios / シナリオで到達可能 {len(reached)}), "
            f"talkable characters / 会話できる登場人物 {sum(c['talkable'] for c in world['characters'])}, "
            f"release-1 roles / 第 1 版のロール {sum(r['release'] == 1 for r in world['roles'])}, "
            f"mutual help / 助け合い {n_aid}, situational actions / 状況アクション {len(world.get('affordances', []))} "
            f"(act 4 / 第四幕 {sum(af.get('act') == 'act.4' for af in world.get('affordances', []))}), "
            f"items / アイテム {len(world.get('items', []))} "
            f"(portable / 持ち歩ける {sum(bool(x.get('portable')) for x in world.get('items', []))})", ""]
    rep += [f"{len(sim_rows)} scenarios, {len(sigs)} distinct world ending signatures (endings.signature)."
            f" / シナリオ {len(sim_rows)} 件、世界の結末のシグネチャ（endings.signature）は {len(sigs)} 種類。", ""]
    rep += ["## Scenario simulation (which world endings are reachable) / シナリオのシミュレーション（世界の結末に到達できるか）", "",
            "Last column: how beat.s2 (セリヌンティウスがちらと疑う) / beat.25 (殴り合い) played."
            " / 最後の列：beat.s2（セリヌンティウスがちらと疑う）/ beat.25（殴り合い）の演じ方。", "",
            "| Scenario / シナリオ | Description / 説明 | World ending / 世界の結末 | beat.24 | Arrival / 到着 | Hostage / 身代わり"
            " | King / 王 | Doubt / Fight (疑い / 殴り合い) |", "|---|---|---|---|---|---|---|---|"]
    for row in sim_rows:
        rep.append(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {fmt(row[4])} | {row[5]} | {row[6]} | {row[7]} |")
    rep += ["", "## Timeline of the original path / 原作の経路のタイムライン", "",
            "| Beat / ビート | Story time / 物語の時刻 | Status / 状態 |", "|---|---|---|"]
    for b in sorted(world["beats"], key=lambda b: (canon_times.get(b["id"], 10**9), b["order"])):
        rep.append(f"| {b['id']} {b['title']} | {fmt(canon_times.get(b['id']))} | {canon_status.get(b['id'])} |")
    rep += ["", "## Uncited paragraphs / 引用されていない段落", ""]
    rep += [f"- Paragraph / 第 {i} 段落: {paras[i - 1][:40]}…" for i in uncited] or ["(none / なし)"]
    Path(a.report).write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep[:12]))
    for e in errors:
        print("ERROR", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
