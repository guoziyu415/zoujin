"""Shared helpers for the Act 2-4 cases and personas (checklist steps 14 and 15 are split by act across three
threads; Act 1 is in evals/gen_seeds.py).

Each act has one directory evals/acts/actN/: `cases.py` is the authoring source; running it writes E*.jsonl and
personas.json into the same directory (generated files, do not edit by hand).
Case IDs are split into ranges by act, so they never collide: Act 2 E?-201〜299, Act 3 E?-301〜399, Act 4 E?-401〜499;
persona IDs use persona.a{N}-….
Validation: bash .github/scripts/check_world.sh (regenerates everything, runs check_evals, checks the generated files
are unchanged). See evals/acts/README.md.

第二〜四幕のケースとペルソナに共通の書き方（チェックリスト第 14、15 ステップは幕ごとに 3 つのスレッドへ分担。
第一幕は evals/gen_seeds.py）。

幕ごとに 1 つのディレクトリ evals/acts/actN/ がある：`cases.py` が編集元で、実行すると同じディレクトリに E*.jsonl と
personas.json を書き出す（生成物、手で編集しない）。
ケース ID は幕ごとに範囲を分けているので衝突しない：第二幕 E?-201〜299、第三幕 E?-301〜399、第四幕 E?-401〜499。
ペルソナ ID は persona.a{N}-… を使う。
検証：bash .github/scripts/check_world.sh（全部を再生成、check_evals、生成物の一致）。説明は evals/acts/README.md を参照。
"""

import json
import re
from pathlib import Path

AI = [
    "AI",
    "ＡＩ",
    "人工知能",
    "アシスタント",
    "プロンプト",
    "言語モデル",
    "Gemini",
    "ChatGPT",
    "システム指示",
    "開発者モード",
]


def comp(ch, place, exit_label):
    return [
        {
            "effects": [
                {"op": "set", "var": "var.player.companionOf", "value": ch},
                {"op": "set", "var": "var.player.location", "value": place},
            ],
            "note": f"幕末の行き先「{exit_label}」を選んだ",
        }
    ]


def J(rubric, p=">=4/5"):
    return {"rubric": rubric, "pass": p}


def case(cid, title, setup, steps, det=None, judge=None, mode="text", runs=5, note=None):
    c = {
        "id": cid,
        "suite": cid.split("-")[0],
        "title": title,
        "mode": mode,
        "runs": runs,
        "setup": setup,
        "steps": steps,
        "expect": {},
    }
    if det:
        c["expect"]["deterministic"] = det
    if judge:
        c["expect"]["judge"] = judge
    if note:
        c["note"] = note
    return c


def say(ch, text):
    return {"to": ch, "say": text}


def nm(fact, step=None):
    d = {"type": "not_mention_fact", "fact": fact}
    if step:
        d["step"] = step
    return d


def no_terms(terms, step=None, echo=False):
    d = {"type": "no_terms", "terms": terms}
    if echo:
        d["forbidEcho"] = True
    if step:
        d["step"] = step
    return d


TRAV = "role.traveler"
APP = "role.apprentice"
BOY = "role.shepherd-boy"
WU = {"type": "world_unchanged"}
JP = {"type": "japanese"}


def write(act: int, cases: list[dict], personas: list[dict], out: Path) -> None:
    """Check that the IDs are in this act's range and unique, write E*.jsonl per suite and the personas to
    personas.json.

    ID がこの幕の範囲内にあり重複しないことを確認し、スイートごとに E*.jsonl を、ペルソナを personas.json に書き出す。
    """
    ids = [c["id"] for c in cases]
    bad = [i for i in ids if not re.fullmatch(rf"E[1-8]-{act}\d\d", i) or i.endswith("00")]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    pbad = [p["id"] for p in personas if not p["id"].startswith(f"persona.a{act}-")]
    if bad or dup or pbad:
        raise SystemExit(
            f"act{act}: bad IDs {bad}, duplicates {dup}, persona IDs must start with persona.a{act}- {pbad}"
            f" / act{act}：ID が不正 {bad}、重複 {dup}、ペルソナ ID は persona.a{act}- で始めること {pbad}"
        )
    for f in out.glob("E*.jsonl"):
        f.unlink()
    suites: dict[str, list[dict]] = {}
    for c in cases:
        # A checkpoint only advances time and facts; it never picks the end-of-act destination for the player.
        # Set the current act explicitly from the case's directory; otherwise the model prompt at Act 4 t=5040
        # would still say act.1. Persona cases play from the official opening and get no setup event.
        # チェックポイントは時刻と事実を進めるだけで、プレイヤーの代わりに幕末の行き先を選ばない。ケースの
        # ディレクトリから現在の幕を明示する。さもないと第四幕 t=5040 のモデルプロンプトが act.1 のままになる。
        # ペルソナは正式な開幕から進むので、設定イベントを挿入しない。
        if "persona" not in c["setup"]:
            c = {
                **c,
                "setup": {
                    **c["setup"],
                    "events": [
                        {
                            "effects": [{"op": "set", "var": "var.act.current", "value": f"act.{act}"}],
                            "note": f"評価用の起点：第{act}幕。時刻・人物の知識・因果は既存のチェックポイントに従う",
                        },
                        *c["setup"].get("events", []),
                    ],
                },
            }
        suites.setdefault(c["suite"], []).append(c)
    for s, cs in sorted(suites.items()):
        (out / f"{s}.jsonl").write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cs), encoding="utf-8")
    (out / "personas.json").write_text(json.dumps(personas, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(
        f"wrote {out.relative_to(out.parents[2])}: {len(cases)} cases, {len(personas)} personas"
        f" / ケース {len(cases)}、ペルソナ {len(personas)}"
    )
