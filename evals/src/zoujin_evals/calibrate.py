"""评审员校准（data-design 7.3）：命令 zoujin-judge。

- calibrate：评审员把校准样本（evals/judge/calibration.jsonl，50 条）各判 --repeat 次，和数据标的分比，
  按判定线（>=4/5）分过 / 不过算一致率。每一次判分各算一次，≥ 90% 才采用这个模型和 effort。
- agree：zg 盲标的 20 条（labels-zg.json）和数据标的分比，≥ 18/20 这 50 条才当标准答案用。不花钱。

calibrate --mode replay 只读回放，不花钱；--mode live 只在 zg 的 Mac 上：要 ZJ_EVAL_LIVE=1、账本 ZJ_LEDGER、
--max-claude-usd 和 --max-item-usd（没有默认值）。不带 --confirm 只打印预计花费和完整命令，zg 同意后才带它再跑。
模型 ID 用 --model 或 ZJ_JUDGE_MODEL 给，仓库里不写。
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import mean
from typing import Any, cast

from .judge import (
    EFFORTS,
    PROMPT_VERSION,
    AnthropicTransport,
    BudgetStop,
    ClaudeLedger,
    ClaudePrices,
    Item,
    Judge,
    RateLimited,
    ReplayStore,
    Transport,
    Verdict,
    replay_key,
    threshold,
)
from .live import LIVE_SWITCH

ITEMS = Path("evals/judge/calibration.jsonl")
REPLAYS = Path("evals/judge/replays")
PRICES = Path("evals/config/claude-prices.json")
LIVE_COST = Path("evals/config/live-cost.json")
OUT = Path("evals/out/judge")
LEDGER_ITEM = "judge-calibration"  # 账本里记在这一项下（m2-model-budget「评审员校准」）
BAR = 0.9  # 评审员和标注的一致率
ZG_BAR = 18  # zg 盲标的 20 条里至少几条和数据一致
ZG_N = 20

type Json = Any


def load_items(path: Path) -> list[Json]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def passed(item: Mapping[str, Json], score: int) -> bool:
    return score >= threshold(item["pass"])


# —— calibrate ——


def summarize(items: Sequence[Json], verdicts: Sequence[Verdict], expected: int) -> Json:
    """expected：这次应判的次数（条目 × repeat）。中途停了、有没判出来的，都不算过。"""
    by_id = {x["id"]: x for x in items}
    judged = [v for v in verdicts if v.score is not None]
    agree = [v for v in judged if v.passed == passed(by_id[v.item], by_id[v.item]["label"]["score"])]
    exact = [v for v in judged if v.score == by_id[v.item]["label"]["score"]]
    near = [v for v in judged if v.score is not None and abs(v.score - by_id[v.item]["label"]["score"]) <= 1]
    per_item: dict[str, list[Verdict]] = {}
    for v in verdicts:
        per_item.setdefault(v.item, []).append(v)
    rows = []
    for it in items:
        vs = per_item.get(it["id"], [])
        scores = [v.score for v in vs if v.score is not None]
        label = it["label"]["score"]
        rows.append(
            {
                "id": it["id"],
                "case": it["case"],
                "label": label,
                "scores": scores,
                "errors": [v.error for v in vs if v.error],
                "agree": sum(passed(it, s) == passed(it, label) for s in scores),
                "stable": len({passed(it, s) for s in scores}) <= 1,
                "reasons": [v.reason for v in vs if v.score is not None],
                "why": it["label"]["why"],
            }
        )
    outs = [v.usage.get("outputTokens", 0) for v in judged]
    rate = len(agree) / len(judged) if judged else 0.0
    return {
        "judged": len(judged),
        "agree": len(agree),
        "rate": round(rate, 4),
        "bar": BAR,
        "expected": expected,
        "ok": len(judged) == expected > 0 and rate >= BAR,
        "exact": len(exact),
        "within1": len(near),
        "unstable": [r["id"] for r in rows if not r["stable"]],
        "errors": dict(Counter(v.error.split("：")[0] for v in verdicts if v.error)),
        "costUsd": round(sum(v.cost_usd for v in verdicts), 4),
        "meanOutputTokens": round(mean(outs), 1) if outs else None,
        "maxOutputTokens": max(outs) if outs else None,
        "items": rows,
    }


def markdown(meta: Mapping[str, Json], s: Mapping[str, Json]) -> str:
    verdict = "过" if s["ok"] else "没过"
    lines = [
        f"# 评审员校准：{verdict}",
        "",
        f"- 模型 {meta['model']}，effort {meta['effort']}，提示 {meta['promptVersion']}，"
        f"{meta['items']} 条 × {meta['repeat']} 次，{meta['mode']}{'，走 Batch' if meta['batch'] else ''}",
        f"- 一致率（过 / 不过和数据的标注一样）：{s['agree']}/{s['judged']} = {s['rate']:.1%}（要 ≥ {s['bar']:.0%}）",
        f"- 分数一样 {s['exact']}/{s['judged']}，差 1 分以内 {s['within1']}/{s['judged']}",
        f"- 几次判得不一样（过 / 不过）的条目：{'、'.join(s['unstable']) or '没有'}",
        f"- 没判出来：{json.dumps(s['errors'], ensure_ascii=False) if s['errors'] else '没有'}",
        f"- 这次花费 ${s['costUsd']:.4f}；输出 token（含思考）"
        f"平均 {s['meanOutputTokens']}、最多 {s['maxOutputTokens']}",
        "",
        "## 和标注不一致的",
        "",
        "| 条目 | 用例 | 标注 | 评审员 | 评审员的理由（第一次） | 标注的理由 |",
        "|---|---|---:|---|---|---|",
    ]
    for r in s["items"]:
        if r["scores"] and r["agree"] == len(r["scores"]) and not r["errors"]:
            continue
        reason = r["reasons"][0] if r["reasons"] else "；".join(r["errors"])
        lines.append(
            f"| {r['id']} | {r['case']} | {r['label']} | {', '.join(map(str, r['scores'])) or '—'} "
            f"| {reason.replace('|', '／')} | {r['why'].replace('|', '／')} |"
        )
    return "\n".join(lines) + "\n"


def estimate_text(a: argparse.Namespace, argv: Sequence[str], judge: Judge, todo: Sequence[tuple[Item, int]]) -> str:
    cost = json.loads(a.live_cost.read_text(encoding="utf-8"))["judge"]["claude"]  # 走 Batch 一次（推算）
    per_call = cost if a.batch else cost / judge.prices.batch_discount
    new = [(i, s) for i, s in todo if judge.replays.get(replay_key(judge.model, judge.request(i, s))) is None]
    upper = max((judge.prices.estimate(judge.model, judge.request(i, s), batch=a.batch) for i, s in new), default=0.0)
    cmd = ["uv", "run", "zoujin-judge", *argv]
    if "--confirm" not in cmd:
        cmd.append("--confirm")
    return "\n".join(
        [
            f"评审员校准要调 {len(new)} 次（{len(todo)} 次里 {len(todo) - len(new)} 次已有回放，不调）"
            f"{'，走 Batch' if a.batch else '，不走 Batch'}。",
            f"预计约 ${len(new) * per_call:.2f}（每次约 ${per_call:.3f}，推算，见 {a.live_cost}）；"
            f"账本按每次最多 ${upper:.3f}（输出用到上限）判。",
            f"Claude 总上限 ${a.max_claude_usd:.2f}，单项「{LEDGER_ITEM}」上限 ${a.max_item_usd:.2f}（两本账合起来）。",
            "",
            "zg 同意后在 Mac 上跑（Key 在 ANTHROPIC_API_KEY 里，账本是 ZJ_LEDGER）：",
            "",
            f"    {LIVE_SWITCH}=1 {shlex.join(cmd)}",
        ]
    )


def calibrate(a: argparse.Namespace, argv: Sequence[str], transport: Transport | None = None) -> int:
    items = load_items(a.items)
    if a.only:
        items = [x for x in items if x["id"] in a.only]
    if not a.model:
        print("要给评审员的模型 ID：--model 或 ZJ_JUDGE_MODEL（仓库里不写）。", file=sys.stderr)
        return 2
    prices = ClaudePrices.from_json(json.loads(a.prices.read_text(encoding="utf-8")))
    todo = [(cast(Item, it), s) for s in range(1, a.repeat + 1) for it in items]
    replays = ReplayStore(a.replays)
    ledger = None
    if a.mode == "live":
        if os.environ.get(LIVE_SWITCH) != "1":
            print(f"live 要调真模型，只在 zg 的 Mac 上跑：没有设 {LIVE_SWITCH}=1，退出。", file=sys.stderr)
            return 2
        missing = [
            n for n, v in (("--max-claude-usd", a.max_claude_usd), ("--max-item-usd", a.max_item_usd)) if v is None
        ]
        if missing:
            print(f"live 要显式给上限，没有默认值。少了 {' '.join(missing)}，退出。", file=sys.stderr)
            return 2
        if not os.environ.get("ZJ_LEDGER"):
            print("live 要账本：设 ZJ_LEDGER（和后端同一个 JSONL 文件），退出。", file=sys.stderr)
            return 2
        ledger = ClaudeLedger(Path(os.environ["ZJ_LEDGER"]), a.max_claude_usd, a.max_item_usd, LEDGER_ITEM)
        if not a.confirm:
            dry = Judge(a.model, a.effort, a.max_tokens, replays, prices)
            print(estimate_text(a, argv, dry, todo))
            return 0
        transport = transport or AnthropicTransport()
    judge = Judge(
        a.model,
        a.effort,
        a.max_tokens,
        replays,
        prices,
        ledger,
        transport if a.mode == "live" else None,
        progress=lambda m: print(m, file=sys.stderr),
    )
    verdicts: list[Verdict] = []
    stopped = None
    try:
        if a.batch:
            verdicts = judge.batch(todo, a.out / "pending-batch.json")
        else:
            for item, sample in todo:
                verdicts.append(judge.one(item, sample))
    except (BudgetStop, RateLimited) as e:
        stopped = str(e)
    meta = {
        "model": a.model,
        "effort": a.effort,
        "maxTokens": a.max_tokens,
        "promptVersion": PROMPT_VERSION,
        "repeat": a.repeat,
        "items": len(items),
        "mode": a.mode,
        "batch": a.batch,
        "stopped": stopped,
    }
    s = summarize(items, verdicts, len(todo))
    a.out.mkdir(parents=True, exist_ok=True)
    report = {**meta, **s, "verdicts": [v.to_json() for v in verdicts]}
    (a.out / "calibration.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (a.out / "calibration.md").write_text(markdown(meta, s), encoding="utf-8")
    print(f"一致率 {s['agree']}/{s['judged']}；报告：{a.out / 'calibration.md'}")
    if stopped:
        print(f"中途停了：{stopped}。已判的存进了回放，再跑会接着判。", file=sys.stderr)
        return 1
    return 0


# —— agree ——


def agree(a: argparse.Namespace) -> int:
    items = {x["id"]: x for x in load_items(a.items)}
    want = sorted(i for i, x in items.items() if x["zgSample"])
    labels: dict[str, Json] = json.loads(a.zg.read_text(encoding="utf-8"))["labels"]
    if sorted(labels) != want or len(want) != ZG_N:
        print(
            f"labels 的条目和 zgSample 的 {len(want)} 条对不上：多了 {sorted(set(labels) - set(want))}，"
            f"少了 {sorted(set(want) - set(labels))}",
            file=sys.stderr,
        )
        return 2
    rows = []
    for i in want:
        it, zg = items[i], int(labels[i]["score"])
        data = it["label"]["score"]
        rows.append(
            (i, it["case"], zg, data, passed(it, zg) == passed(it, data), labels[i].get("note", ""), it["label"]["why"])
        )
    same = sum(r[4] for r in rows)
    lines = [
        f"# zg 盲标和数据的标注：{'过' if same >= ZG_BAR else '没过'}",
        "",
        f"- 过 / 不过一样：{same}/{ZG_N}（要 ≥ {ZG_BAR}）",
        f"- 分数一样 {sum(r[2] == r[3] for r in rows)}/{ZG_N}，"
        f"差 1 分以内 {sum(abs(r[2] - r[3]) <= 1 for r in rows)}/{ZG_N}",
        "",
        "| 条目 | 用例 | zg | 数据 | 一致 | zg 的备注 | 数据的理由 |",
        "|---|---|---:|---:|---|---|---|",
    ]
    lines += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {'✓' if r[4] else '✗'} | {r[5]} | {r[6]} |" for r in rows]
    text = "\n".join(lines) + "\n"
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "agree-zg.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


def parse(argv: Sequence[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="zoujin-judge", description="评审员校准（data-design 7.3）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calibrate", help="评审员判校准样本，和数据的标注比一致率")
    c.add_argument("--mode", choices=("replay", "live"), default="replay")
    c.add_argument("--model", default=os.environ.get("ZJ_JUDGE_MODEL"), help="评审员的模型 ID（默认读 ZJ_JUDGE_MODEL）")
    c.add_argument("--effort", choices=EFFORTS, default="low")
    c.add_argument("--repeat", type=int, default=3, help="每条判几次")
    c.add_argument("--max-tokens", type=int, default=2048, help="输出上限（思考也算在里面）")
    c.add_argument("--batch", action="store_true", help="走 Batch（半价，慢）；校准默认不走")
    c.add_argument("--only", action="append", default=[], help="只判这一条（可以给多次），先试几条量输出 token 用")
    c.add_argument("--items", type=Path, default=ITEMS)
    c.add_argument("--replays", type=Path, default=REPLAYS)
    c.add_argument("--prices", type=Path, default=PRICES)
    c.add_argument("--live-cost", type=Path, default=LIVE_COST)
    c.add_argument("--out", type=Path, default=OUT)
    c.add_argument("--max-claude-usd", type=float, help="Claude 账的总上限（美元），live 必填")
    c.add_argument("--max-item-usd", type=float, help=f"「{LEDGER_ITEM}」这一项的上限（美元），live 必填")
    c.add_argument("--confirm", action="store_true", help="zg 看过预计花费、同意了")
    g = sub.add_parser("agree", help="zg 盲标的 20 条和数据的标注比")
    g.add_argument("--zg", type=Path, required=True, help="zg 的标注（labels-zg.json）")
    g.add_argument("--items", type=Path, default=ITEMS)
    g.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    if a.cmd == "calibrate" and a.repeat < 1:
        ap.error("--repeat 至少 1")
    return a


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    a = parse(argv)
    if a.cmd == "agree":
        return agree(a)
    return calibrate(a, argv)


if __name__ == "__main__":
    sys.exit(main())
