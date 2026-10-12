"""第二〜四幕的用例和画像共用的写法（清单第 14、15 步按幕分给三个线程写；第一幕在 evals/gen_seeds.py）。

每一幕一个目录 evals/acts/actN/：`cases.py` 是编写源，跑它写出同目录的 E*.jsonl 和 personas.json（生成物，不要手改）。
用例 ID 按幕分段，不会撞：第二幕 E?-201〜299，第三幕 E?-301〜399，第四幕 E?-401〜499；画像 ID 用 persona.a{N}-…。
校验：bash .github/scripts/check_world.sh（重新生成全部、check_evals、生成物一致）。说明见 evals/acts/README.md。
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
            "note": f"幕末の去処「{exit_label}」を選んだ",
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
    """检查 ID 在这一幕的段里、不重复，按套件写 E*.jsonl，画像写 personas.json。"""
    ids = [c["id"] for c in cases]
    bad = [i for i in ids if not re.fullmatch(rf"E[1-8]-{act}\d\d", i) or i.endswith("00")]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    pbad = [p["id"] for p in personas if not p["id"].startswith(f"persona.a{act}-")]
    if bad or dup or pbad:
        raise SystemExit(f"act{act}：ID 不对 {bad}、重复 {dup}、画像 ID 要以 persona.a{act}- 开头 {pbad}")
    for f in out.glob("E*.jsonl"):
        f.unlink()
    suites: dict[str, list[dict]] = {}
    for c in cases:
        # 检查点只推时间/事实，不会替玩家选幕末去处。按该用例目录明确当前幕；
        # 否则第四幕 t=5040 的模型提示仍说 act.1。persona 从正式开局走，不插布置事件。
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
    print(f"wrote {out.relative_to(out.parents[2])}: 用例 {len(cases)}，画像 {len(personas)}")
