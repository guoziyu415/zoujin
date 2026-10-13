"""Checks the anti-spoiler probe questions (PM S-068): whether evals/probes/s3_spoiler_probes.json agrees with the
world model and can be used directly by the backend's s3.

  uv run python -I packages/worldsim/reference/check_probes.py --world worlds/hashire-merosu/1.0.0-draft/world.json \
      --probes evals/probes/s3_spoiler_probes.json [--existing the backend's original s3_scenarios.json] \
      [--existing the first probe set …]

What it checks:
- The format is the same as s3_scenarios.json (about / partner / scenarios / common_questions / keywords; a
  scenario's id, character, after, place, when, voice, questions), plus probes (one per question: targets, style).
- character is a talkable character; after is a beat or "pre"; place is where this character is right after `after`
  happens (on the original timetable); when equals the world clock's label at that moment (「三日目の午後」).
- Every question's targets are things this character should not know right now: beats must come after `after` (by
  order, like s3's World.rank); facts must not be in their current knows. An open question must not contain the
  spoilerTerms of a target fact (open = the question itself does not carry the answer).
- No duplicate questions (nor duplicates of the sets given with --existing: the backend's existing S-3 questions,
  plus the first set when checking the second); 20〜30 questions per character.
Standard library only. Exit code 1 on errors.

ネタバレ防止プローブの問い（PM S-068）を照合する：evals/probes/s3_spoiler_probes.json が世界モデルと一致し、
バックエンドの s3 でそのまま使えるか。

  uv run python -I packages/worldsim/reference/check_probes.py --world worlds/hashire-merosu/1.0.0-draft/world.json \
      --probes evals/probes/s3_spoiler_probes.json [--existing バックエンドの元の s3_scenarios.json] \
      [--existing 第 1 組のプローブ …]

確認すること：
- 形式は s3_scenarios.json と同じ（about / partner / scenarios / common_questions / keywords。シナリオの id、
  character、after、place、when、voice、questions）、加えて probes（questions と 1 対 1：targets、style）。
- character は会話できる登場人物。after はビートか "pre"。place はその登場人物が after の直後（原作の時刻表）に
  いる場所。when はその時点の世界の時計のラベル（「三日目の午後」）と等しい。
- 各問いの targets はその登場人物が今知っているはずのないもの：ビートは after より後（order 順、s3 の World.rank と
  同じ）、事実はその時点の knows にない。open の問いには対象の事実の spoilerTerms を入れてはいけない（open = 問い
  自体に答えを含まない）。
- 問いが重複しない（--existing で与えた問いの集合とも重複しない：バックエンドの既存の S-3 の問い。第 2 組を確認する
  ときは第 1 組も加える）。登場人物ごとに 20〜30 問。
標準ライブラリのみ。エラーがあれば終了コード 1。
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from zoujin_worldsim import Sim  # Simulation rules shared with build_world.py (W-1 package) / build_world.py と共有

SCENARIO_KEYS = {"id", "character", "after", "place", "when", "voice", "questions"}
STYLES = {"open", "leading"}
PER_CHAR = (20, 30)


def check(world, spec, existing=None):
    """existing: existing question sets, one or a list (to check for duplicates).

    existing：既存の問いの集合。1 つまたは複数（重複の確認用）。
    """
    errs, warns = [], []
    err, warn = errs.append, warns.append
    sim = Sim(world)
    beats = {b["id"]: b for b in world["beats"]}
    facts = {f["id"]: f for f in world["facts"]}
    chars = {c["id"]: c for c in world["characters"]}
    talkable = {c for c, x in chars.items() if x.get("talkable")}
    clock = world["clock"]
    lab = clock["labels"]

    def rank(ref):
        return 0 if ref == "pre" else float(beats[ref]["order"])

    def known(cid, after):
        r = rank(after)
        return {k["fact"] for k in chars[cid].get("knows", []) if rank(k["since"]) <= r}

    def moment(cid, after):
        if after == "pre":
            return clock["startT"], chars[cid].get("initialPlace")
        res = sim.run({}, until=("beat", after), role=world["roles"][0]["id"])
        return res["t"], res["where"].get(cid)

    def label(t):
        band = [b for m, b in lab["bands"] if m <= t % 1440][-1]
        return f"{lab['days'][t // 1440]}の{band}"

    for k in ("about", "partner", "scenarios", "common_questions", "keywords"):
        if k not in spec:
            err(f"Missing top-level field / トップレベルのフィールドがない: {k}")
    if errs:
        return errs, warns, {}

    seen = Counter()
    old_q = set()
    olds = [existing] if isinstance(existing, dict) else list(existing or [])
    for ex in olds:
        for s in ex["scenarios"]:
            old_q.update(s["questions"])
        old_q.update(ex["common_questions"])
        missing_kw = [k for k in ex["keywords"] if k not in spec["keywords"]]
        if missing_kw:
            warn(f"keywords is missing some from the existing sets / keywords に既存の集合のものが欠けている: {missing_kw}")
    old_ids = {s["id"] for ex in olds for s in ex["scenarios"]}
    per_char = defaultdict(int)
    styles = Counter()
    echo = 0
    ids = Counter(s.get("id") for s in spec["scenarios"])
    for i, n in ids.items():
        if n > 1:
            err(f"Duplicate scenario ID / シナリオ ID の重複: {i}")
        if i in old_ids:
            err(f"Scenario ID duplicates an existing set / シナリオ ID が既存の集合と重複: {i}")

    for s in spec["scenarios"]:
        sid = s.get("id", "?")
        miss = SCENARIO_KEYS - set(s)
        if miss:
            err(f"{sid}: missing fields / フィールドがない: {sorted(miss)}")
            continue
        cid, after = s["character"], s["after"]
        if cid not in talkable:
            err(f"{sid}: {cid} is not a talkable character / {cid} は会話できる登場人物ではない")
            continue
        if after != "pre" and after not in beats:
            err(f"{sid}: after {after} is not a beat / after {after} はビートではない")
            continue
        t, where = moment(cid, after)
        if s["place"] != where:
            err(f"{sid}: place {s['place']}, but right after {after} happens {cid} is at {where} / place は {s['place']} だが、{after} の直後に {cid} は {where} にいる")
        if s["when"] != label(t):
            err(f"{sid}: when 「{s['when']}」 should be 「{label(t)}」 by the clock (t={t}) / when「{s['when']}」は時計では「{label(t)}」のはず")
        if not isinstance(s["voice"], str) or not s["voice"]:
            err(f"{sid}: voice is empty / voice が空")
        qs, probes = s["questions"], s.get("probes")
        if not qs:
            err(f"{sid}: no questions / 問いがない")
        if probes is None or len(probes) != len(qs):
            err(f"{sid}: probes must match questions in number ({len(qs)} questions, {len(probes or [])} probes) / probes は questions と同数が必要（{len(qs)} 問、probes {len(probes or [])}）")
            probes = [None] * len(qs)
        kn = known(cid, after)
        r = rank(after)
        per_char[cid] += len(qs)
        for j, (q, p) in enumerate(zip(qs, probes), 1):
            where_q = f"{sid} question / 第 {j} 問「{q[:20]}…」"
            seen[q] += 1
            if q in old_q:
                err(f"{where_q}: duplicates a question in an existing set / 既存の集合の問いと重複")
            if q[-1] not in "。？?":
                warn(f"{where_q}: does not end in 「。」 or 「？」 / 末尾が「。」でも「？」でもない")
            if any(k in q for k in spec["keywords"]):
                echo += 1
            if p is None:
                continue
            style, targets = p.get("style"), p.get("targets") or []
            styles[style] += 1
            if style not in STYLES:
                err(f"{where_q}: style must be open or leading / style は open か leading")
            if not targets:
                err(f"{where_q}: no targets / targets がない")
            for x in targets:
                if x in beats:
                    if beats[x]["order"] <= r:
                        err(f"{where_q}: {x} has already happened before {after}, so it is not in the future (use a fact for past events they did not see) / {x} は {after} より前に起きていて未来のことではない（見ていない過去のことは事実を使う）")
                elif x in facts:
                    if x in kn:
                        err(f"{where_q}: {cid} already knows {x} at {after}, so it is not a spoiler / {cid} は {after} の時点で {x} を知っており、ネタバレにならない")
                    if style == "open":
                        hit = [w for w in facts[x].get("spoilerTerms", []) if w in q]
                        if hit:
                            err(f"{where_q}: an open question contains spoiler terms of {x} {hit}; mark it leading / open の問いに {x} のネタバレ語 {hit} がある。leading にする")
                else:
                    err(f"{where_q}: {x} in targets is neither a beat nor a fact / targets の {x} はビートでも事実でもない")

    for q, n in seen.items():
        if n > 1:
            err(f"Question repeated {n} times / 問いが {n} 回重複: 「{q}」")
    for q in spec["common_questions"]:
        if q in old_q:
            err(f"Common question duplicates an existing set / 共通の問いが既存の集合と重複: 「{q}」")
        if q in seen:
            err(f"Common question duplicates a scenario question / 共通の問いがシナリオの問いと重複: 「{q}」")
    for cid in sorted(talkable):
        n = per_char.get(cid, 0)
        if not PER_CHAR[0] <= n <= PER_CHAR[1]:
            err(f"{cid}: {n} questions; S-068 requires {PER_CHAR[0]}〜{PER_CHAR[1]} per character / {n} 問。S-068 では 1 人 {PER_CHAR[0]}〜{PER_CHAR[1]} 問")
    kc = Counter(spec["keywords"])
    for k, n in kc.items():
        if n > 1:
            err(f"Duplicate keywords / keywords の重複: {k}")

    n_sc = len(spec["scenarios"])
    n_q = sum(per_char.values())
    stats = {"scenarios": n_sc, "targeted": n_q, "common": len(spec["common_questions"]),
             "per_condition": n_q + len(spec["common_questions"]) * n_sc,
             "per_char": dict(sorted(per_char.items())), "styles": dict(styles), "with_keyword": echo}
    if olds:
        stats["existing_per_condition"] = sum(len(s["questions"]) + len(ex["common_questions"])
                                              for ex in olds for s in ex["scenarios"])
    return errs, warns, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--world", required=True)
    ap.add_argument("--probes", required=True)
    ap.add_argument("--existing", action="append", default=[],
                    help="Existing question sets (the backend's s3_scenarios.json, the first probe set) to check for"
                         " duplicates; may be given several times / 既存の問いの集合（バックエンドの s3_scenarios.json、"
                         "第 1 組のプローブ）。重複の確認に使う。複数回指定できる")
    a = ap.parse_args()
    world = json.loads(Path(a.world).read_text(encoding="utf-8"))
    spec = json.loads(Path(a.probes).read_text(encoding="utf-8"))
    existing = [json.loads(Path(x).read_text(encoding="utf-8")) for x in a.existing]
    errs, warns, st = check(world, spec, existing)
    for e in errs:
        print("Error / エラー: " + e)
    for w in warns:
        print("Warning / 警告: " + w)
    if st:
        print(f"{st['scenarios']} scenarios; {st['targeted']} targeted questions + {st['common']} common × {st['scenarios']}"
              f" = {st['per_condition']} per condition / シナリオ {st['scenarios']} 件、個別の問い {st['targeted']} 問 +"
              f" 共通の問い {st['common']} × {st['scenarios']} = 条件ごとに {st['per_condition']} 問"
              + (f" (with the existing sets' {st['existing_per_condition']} = {st['per_condition'] + st['existing_per_condition']}"
                 f" / 既存の集合の {st['existing_per_condition']} 問を加えて {st['per_condition'] + st['existing_per_condition']})"
                 if "existing_per_condition" in st else ""))
        print("Per character / 登場人物ごと: " + "、".join(f"{c[5:]} {n}" for c, n in st["per_char"].items()))
        print(f"Styles / 書き方: open {st['styles'].get('open', 0)}, leading {st['styles'].get('leading', 0)}; "
              f"{st['with_keyword']} questions contain a keyword themselves (keyword_hits gives false positives when a reply"
              f" repeats the question) / 問い自体にキーワードを含むものが {st['with_keyword']} 問（返答が問いを繰り返すと"
              f" keyword_hits が誤検出する）")
    print(f"Errors / エラー {len(errs)}, warnings / 警告 {len(warns)}")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
