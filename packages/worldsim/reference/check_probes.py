"""核对防剧透探针题（PM S-068）：evals/probes/s3_spoiler_probes.json 是否和世界模型一致、能直接给后端的 s3 用。

  uv run python -I packages/worldsim/reference/check_probes.py --world worlds/hashire-merosu/1.0.0-draft/world.json \
      --probes evals/probes/s3_spoiler_probes.json [--existing 后端原有的 s3_scenarios.json] [--existing 第一组探针题 …]

查的是：
- 格式和 s3_scenarios.json 一样（about / partner / scenarios / common_questions / keywords；情景的 id、character、after、place、when、voice、questions），
  另加 probes（和 questions 一一对应：targets、style）。
- character 是能对话的人物；after 是节拍或 "pre"；place 是这个人物在 after 刚发生时（原作时间表）所在的地点；
  when 等于世界时钟在那一刻的标签（「三日目の午後」）。
- 每题的 targets 都是这个人物此刻不该知道的：节拍要在 after 之后（按 order，和 s3 的 World.rank 一样）；
  事实要不在他此刻的 knows 里。open 题里不能出现目标事实的 spoilerTerms（open = 问题本身不带答案）。
- 题目不重复（也不和 --existing 给的题集重复：后端现有的 S-3 原题；查第二组时再加第一组）；每个人物 20〜30 问。
只用标准库。有错误时退出码 1。
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from zoujin_worldsim import Sim  # 和 build_world.py 共用的推演规则（W-1 的包）

SCENARIO_KEYS = {"id", "character", "after", "place", "when", "voice", "questions"}
STYLES = {"open", "leading"}
PER_CHAR = (20, 30)


def check(world, spec, existing=None):
    """existing：已有的题集，一个或一串（查重复题）。"""
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
            err(f"缺少顶层字段 {k}")
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
            warn(f"keywords 少了已有题集的：{missing_kw}")
    old_ids = {s["id"] for ex in olds for s in ex["scenarios"]}
    per_char = defaultdict(int)
    styles = Counter()
    echo = 0
    ids = Counter(s.get("id") for s in spec["scenarios"])
    for i, n in ids.items():
        if n > 1:
            err(f"情景 ID 重复：{i}")
        if i in old_ids:
            err(f"情景 ID 和已有题集重复：{i}")

    for s in spec["scenarios"]:
        sid = s.get("id", "?")
        miss = SCENARIO_KEYS - set(s)
        if miss:
            err(f"{sid}：缺少字段 {sorted(miss)}")
            continue
        cid, after = s["character"], s["after"]
        if cid not in talkable:
            err(f"{sid}：{cid} 不是能对话的人物")
            continue
        if after != "pre" and after not in beats:
            err(f"{sid}：after {after} 不是节拍")
            continue
        t, where = moment(cid, after)
        if s["place"] != where:
            err(f"{sid}：place {s['place']}，但 {after} 刚发生时 {cid} 在 {where}")
        if s["when"] != label(t):
            err(f"{sid}：when「{s['when']}」，按时钟应为「{label(t)}」（t={t}）")
        if not isinstance(s["voice"], str) or not s["voice"]:
            err(f"{sid}：voice 为空")
        qs, probes = s["questions"], s.get("probes")
        if not qs:
            err(f"{sid}：没有题目")
        if probes is None or len(probes) != len(qs):
            err(f"{sid}：probes 要和 questions 一样多（{len(qs)} 问，probes {len(probes or [])}）")
            probes = [None] * len(qs)
        kn = known(cid, after)
        r = rank(after)
        per_char[cid] += len(qs)
        for j, (q, p) in enumerate(zip(qs, probes), 1):
            where_q = f"{sid} 第 {j} 问「{q[:20]}…」"
            seen[q] += 1
            if q in old_q:
                err(f"{where_q}：和已有题集的题重复")
            if q[-1] not in "。？?":
                warn(f"{where_q}：结尾不是「。」或「？」")
            if any(k in q for k in spec["keywords"]):
                echo += 1
            if p is None:
                continue
            style, targets = p.get("style"), p.get("targets") or []
            styles[style] += 1
            if style not in STYLES:
                err(f"{where_q}：style 要是 open 或 leading")
            if not targets:
                err(f"{where_q}：没有 targets")
            for x in targets:
                if x in beats:
                    if beats[x]["order"] <= r:
                        err(f"{where_q}：{x} 在 {after} 之前已经发生，不是未来的事（过去没见到的事请用事实）")
                elif x in facts:
                    if x in kn:
                        err(f"{where_q}：{cid} 在 {after} 已经知道 {x}，不算剧透")
                    if style == "open":
                        hit = [w for w in facts[x].get("spoilerTerms", []) if w in q]
                        if hit:
                            err(f"{where_q}：open 题里出现了 {x} 的剧透词 {hit}，应标 leading")
                else:
                    err(f"{where_q}：targets 里的 {x} 不是节拍也不是事实")

    for q, n in seen.items():
        if n > 1:
            err(f"题目重复 {n} 次：「{q}」")
    for q in spec["common_questions"]:
        if q in old_q:
            err(f"通用题和已有题集的重复：「{q}」")
        if q in seen:
            err(f"通用题和情景题重复：「{q}」")
    for cid in sorted(talkable):
        n = per_char.get(cid, 0)
        if not PER_CHAR[0] <= n <= PER_CHAR[1]:
            err(f"{cid}：{n} 问，S-068 要每人 {PER_CHAR[0]}〜{PER_CHAR[1]} 问")
    kc = Counter(spec["keywords"])
    for k, n in kc.items():
        if n > 1:
            err(f"keywords 重复：{k}")

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
                    help="已有的题集（后端的 s3_scenarios.json、第一组探针题），用来查重复题；可以给多次")
    a = ap.parse_args()
    world = json.loads(Path(a.world).read_text(encoding="utf-8"))
    spec = json.loads(Path(a.probes).read_text(encoding="utf-8"))
    existing = [json.loads(Path(x).read_text(encoding="utf-8")) for x in a.existing]
    errs, warns, st = check(world, spec, existing)
    for e in errs:
        print("错误：" + e)
    for w in warns:
        print("警告：" + w)
    if st:
        print(f"{st['scenarios']} 个情景；专题 {st['targeted']} 问 + 通用题 {st['common']} × {st['scenarios']} = 每种写法 {st['per_condition']} 问"
              + (f"（加上已有题集的 {st['existing_per_condition']} 问 = {st['per_condition'] + st['existing_per_condition']}）" if "existing_per_condition" in st else ""))
        print("每个人物：" + "、".join(f"{c[5:]} {n}" for c, n in st["per_char"].items()))
        print(f"写法：open {st['styles'].get('open', 0)}、leading {st['styles'].get('leading', 0)}；"
              f"题目本身带关键词的 {st['with_keyword']} 问（回复复述问题时 keyword_hits 会误报）")
    print(f"错误 {len(errs)}，警告 {len(warns)}")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
