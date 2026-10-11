"""生成 evals/probes/s3_probe_knows.json：防剧透探针（两组都算）每个情景里，这个人物「此刻」是什么人、知道什么（PM S-086 ⑥）。
S-068 重测的两种判定都不看人物此刻知道什么，认不出「时点串了」（后一个时点的身份、处境漏到前一个时点）。下次重测把这份
交给判定：人物的回答只能用 knows 里的事；notYet 里的事他之后才知道，回答里当成已经知道就算越界。

  uv run python -I evals/gen_probe_knows.py evals/probes/s3_probe_knows.json

全部从世界模型（1.0.0-draft 的 world.json）按情景的 after 切，不手写：
- now：人物的 summary（只写开局就成立的事，契约 2.1），加上此刻成立的 traits、goals（since 已发生、until 还没发生）。
- knows：人物的 knows 里 since 已发生的事实（和 worldsim 的 knows()、check_probes 的同一个判法：按节拍的 order 比，
  pre 最早），事实的 trueFrom 也要已发生。
- notYet：人物的 knows 里 since 还没发生的事实（他之后才知道）。
只用标准库。"""

import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parents[1]
WORLD = DATA / "worlds" / "hashire-merosu" / "1.0.0-draft" / "world.json"
PROBES = [DATA / "evals" / "probes" / "s3_spoiler_probes.json", DATA / "evals" / "probes" / "s3_spoiler_probes_2.json"]

ABOUT = (
    "防剧透探针（evals/probes/s3_spoiler_probes.json 和第二组 s3_spoiler_probes_2.json）每个情景里，人物此刻是什么人、"
    "知道什么（PM S-086 ⑥）。"
    "由 evals/gen_probe_knows.py 从世界模型 1.0.0-draft 按情景的 after 生成，不要手改。"
    "判定用法：回答里人物说的身份、处境要和 now 对得上；只能把 knows 里的事当成知道的；"
    "把 notYet 里的事当成已经知道（说本来就知道、确认是真的、当成前提接着说）就算知情越界或时点串了。"
    "玩家刚说出的事，人物当作第一次听到（「そうですか」「初めて聞きました」、顺着问下去）不算；"
    "说自己本来就知道，或者补出玩家没说的细节，才算（S-068 人工复核的分法，UX #87 评审）。"
)


def build(world, probes):
    beats = {b["id"]: b for b in world["beats"]}
    facts = {f["id"]: f for f in world["facts"]}
    chars = {c["id"]: c for c in world["characters"]}
    places = {p["id"]: p for p in world["places"]}

    def rank(ref):
        return 0.0 if ref == "pre" else float(beats[ref]["order"])

    def active(entries, r):
        return [
            e["text"]
            for e in entries
            if rank(e.get("since", "pre")) <= r and ("until" not in e or r < rank(e["until"]))
        ]

    out = {}
    for s in probes["scenarios"]:
        c = chars[s["character"]]
        r = rank(s["after"])
        known, later = [], []
        for k in c.get("knows", []):
            f = facts[k["fact"]]
            row = {"fact": f["id"], "statement": f["statement"]}
            if rank(k["since"]) <= r and rank(f["trueFrom"]) <= r:
                known.append(row)
            else:
                later.append({**row, "since": k["since"]})
        out[s["id"]] = {
            "character": c["id"],
            "name": c["name"],
            "after": s["after"],
            "afterTitle": "原作の始まり" if s["after"] == "pre" else beats[s["after"]]["title"],
            "when": s["when"],
            "place": places[s["place"]]["name"],
            "now": {
                "summary": c["summary"],
                "traits": active(c.get("traits", []), r),
                "goals": active(c.get("goals", []), r),
            },
            "knows": known,
            "notYet": later,
        }
    return {"about": ABOUT, "worldModelVersion": world["worldModelVersion"], "scenarios": out}


def main():
    if len(sys.argv) != 2:
        sys.exit("用法：gen_probe_knows.py <输出的 json>")
    world = json.loads(WORLD.read_text(encoding="utf-8"))
    scenarios = [s for p in PROBES for s in json.loads(p.read_text(encoding="utf-8"))["scenarios"]]
    doc = build(world, {"scenarios": scenarios})
    Path(sys.argv[1]).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(doc['scenarios'])} 个情景 → {sys.argv[1]}")


if __name__ == "__main__":
    main()
