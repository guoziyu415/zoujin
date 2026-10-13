"""Judge calibration (data-design 7.3): the zoujin-judge command.

- calibrate: the judge scores each calibration sample (evals/judge/calibration.jsonl, 48 items) --repeat times; the
  scores are compared with the data's labels, split into pass / fail by the pass line (>=4/5), to compute the
  agreement rate. Each judging counts once; the model and effort are adopted only at ≥ 90%.
- agree: zg's 20 blind labels (labels-zg.json) are compared with the data's labels; only at ≥ 18/20 are these 48
  items used as the reference answers. Costs nothing.

calibrate --mode replay only reads replays and costs nothing; --mode live runs only on zg's Mac: it needs
ZJ_EVAL_LIVE=1, the ledger ZJ_LEDGER, --max-claude-usd and --max-item-usd (no defaults). Without --confirm it only
prints the estimated cost and the full command; it is run again with --confirm once zg agrees.
The model ID is given by --model or ZJ_JUDGE_MODEL and is not written in the repo.

審査員のキャリブレーション（data-design 7.3）：コマンド zoujin-judge。

- calibrate：審査員がキャリブレーションサンプル（evals/judge/calibration.jsonl、48 件）をそれぞれ --repeat 回採点し、
  データのラベルの点数と比べ、合格ライン（>=4/5）で合格 / 不合格に分けて一致率を計算する。採点 1 回ごとに 1 回と
  数え、≥ 90% のときだけそのモデルと effort を採用する。
- agree：zg のブラインドラベル 20 件（labels-zg.json）をデータのラベルと比べ、≥ 18/20 のときだけこの 48 件を正解と
  して使う。費用はかからない。

calibrate --mode replay はリプレイを読むだけで費用はかからない。--mode live は zg の Mac でのみ：ZJ_EVAL_LIVE=1、台帳
ZJ_LEDGER、--max-claude-usd と --max-item-usd（デフォルト値なし）が必要。--confirm なしでは見積もり費用と完全な
コマンドを表示するだけで、zg の同意後に --confirm を付けて再実行する。
モデル ID は --model または ZJ_JUDGE_MODEL で与え、リポジトリには書かない。
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

from zoujin_llm import PRICES_PATH

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
PRICES = PRICES_PATH  # the one in the shared package zoujin_llm (B-8) / 共有パッケージ zoujin_llm にあるもの（B-8）
LIVE_COST = Path("evals/config/live-cost.json")
OUT = Path("evals/out/judge")
# recorded under this ledger item (m2-model-budget "judge calibration")
# 台帳ではこの項目に記録する（m2-model-budget「審査員のキャリブレーション」）
LEDGER_ITEM = "judge-calibration"
BAR = 0.9  # agreement rate between the judge and the labels / 審査員とラベルの一致率
# how many of zg's 20 blind labels must at least agree with the data
# zg のブラインドラベル 20 件のうちデータと一致すべき最低件数
ZG_BAR = 18
ZG_N = 20

type Json = Any


def load_items(path: Path) -> list[Json]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def passed(item: Mapping[str, Json], score: int) -> bool:
    return score >= threshold(item["pass"])


# —— calibrate ——


def summarize(items: Sequence[Json], verdicts: Sequence[Verdict], expected: int) -> Json:
    """expected: how many judgings this run should have (items × repeat). Stopping midway, or anything not judged,
    means not passed.

    expected：今回採点すべき回数（項目 × repeat）。途中で止まったり、採点できなかったものがあれば合格としない。
    """
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
    en_verdict, ja_verdict = ("passed", "合格") if s["ok"] else ("not passed", "不合格")
    batch_en, batch_ja = (", via Batch", "、Batch 経由") if meta["batch"] else ("", "")
    times = f"{meta['items']} items × {meta['repeat']} times"
    lines = [
        f"# Judge calibration: {en_verdict} / 審査員のキャリブレーション：{ja_verdict}",
        "",
        f"- Model {meta['model']}, effort {meta['effort']}, prompt {meta['promptVersion']}, {times},"
        f" {meta['mode']}{batch_en} / モデル {meta['model']}、effort {meta['effort']}、プロンプト"
        f" {meta['promptVersion']}、{meta['items']} 件 × {meta['repeat']} 回、{meta['mode']}{batch_ja}",
        f"- Agreement (pass / fail same as the data's label): {s['agree']}/{s['judged']} = {s['rate']:.1%}"
        f" (need ≥ {s['bar']:.0%}) / 一致率（合格 / 不合格がデータのラベルと同じ）：{s['agree']}/{s['judged']}"
        f" = {s['rate']:.1%}（≥ {s['bar']:.0%} が必要）",
        f"- Same score {s['exact']}/{s['judged']}, within 1 point {s['within1']}/{s['judged']}"
        f" / 同じ点数 {s['exact']}/{s['judged']}、差 1 点以内 {s['within1']}/{s['judged']}",
        f"- Items judged differently across runs (pass / fail): {', '.join(s['unstable']) or 'none'}"
        f" / 回によって判定（合格 / 不合格）が異なる項目：{'、'.join(s['unstable']) or 'なし'}",
        "- Not judged / 採点できなかったもの: "
        + (json.dumps(s["errors"], ensure_ascii=False) if s["errors"] else "none / なし"),
        f"- Cost this time ${s['costUsd']:.4f}; output tokens (including thinking)"
        f" mean {s['meanOutputTokens']}, max {s['maxOutputTokens']}"
        f" / 今回の費用 ${s['costUsd']:.4f}。出力トークン（思考を含む）"
        f"平均 {s['meanOutputTokens']}、最大 {s['maxOutputTokens']}",
        "",
        "## Disagreeing with the label / ラベルと一致しないもの",
        "",
        "| Item / 項目 | Case / ケース | Label / ラベル | Judge / 審査員 "
        "| Judge's reason (first run) / 審査員の理由（1 回目） | Label's reason / ラベルの理由 |",
        "|---|---|---:|---|---|---|",
    ]
    for r in s["items"]:
        if r["scores"] and r["agree"] == len(r["scores"]) and not r["errors"]:
            continue
        reason = r["reasons"][0] if r["reasons"] else "; ".join(r["errors"])
        lines.append(
            f"| {r['id']} | {r['case']} | {r['label']} | {', '.join(map(str, r['scores'])) or '—'} "
            f"| {reason.replace('|', '／')} | {r['why'].replace('|', '／')} |"
        )
    return "\n".join(lines) + "\n"


def estimate_text(a: argparse.Namespace, argv: Sequence[str], judge: Judge, todo: Sequence[tuple[Item, int]]) -> str:
    # one call via Batch (extrapolated) / Batch 経由で 1 回（推算）
    cost = json.loads(a.live_cost.read_text(encoding="utf-8"))["judge"]["claude"]
    per_call = cost if a.batch else cost / judge.prices.batch_discount
    new = [(i, s) for i, s in todo if judge.replays.get(replay_key(judge.tag, judge.request(i, s))) is None]
    upper = max((judge.prices.estimate(judge.model, judge.request(i, s), batch=a.batch) for i, s in new), default=0.0)
    cmd = ["uv", "run", "zoujin-judge", *argv]
    if "--confirm" not in cmd:
        cmd.append("--confirm")
    return "\n".join(
        [
            f"Judge calibration needs {len(new)} calls ({len(todo) - len(new)} of {len(todo)} already have replays and"
            f" are not called), {'via Batch' if a.batch else 'not via Batch'}. / 審査員のキャリブレーションには"
            f" {len(new)} 回の呼び出しが必要（{len(todo)} 回のうち {len(todo) - len(new)} 回はリプレイがあるので"
            f"呼ばない）。{'Batch 経由' if a.batch else 'Batch は使わない'}。",
            f"Estimated about ${len(new) * per_call:.2f} (about ${per_call:.3f} per call, extrapolated, see"
            f" {a.live_cost}); the ledger checks each call at up to ${upper:.3f} (output up to the cap)."
            f" / 見積もり約 ${len(new) * per_call:.2f}（1 回あたり約 ${per_call:.3f}、推算、{a.live_cost} を参照）。"
            f"台帳は 1 回あたり最大 ${upper:.3f}（出力が上限まで）で判定する。",
            f'Claude total cap ${a.max_claude_usd:.2f}, cap for the item "{LEDGER_ITEM}" ${a.max_item_usd:.2f} (both'
            f" ledgers combined). / Claude の総上限 ${a.max_claude_usd:.2f}、項目「{LEDGER_ITEM}」の上限"
            f" ${a.max_item_usd:.2f}（2 つの台帳の合算）。",
            "",
            "Once zg agrees, run on the Mac (the key is in ANTHROPIC_API_KEY, the ledger is ZJ_LEDGER):"
            " / zg の同意後、Mac で実行する（キーは ANTHROPIC_API_KEY、台帳は ZJ_LEDGER）：",
            "",
            f"    {LIVE_SWITCH}=1 {shlex.join(cmd)}",
        ]
    )


def calibrate(a: argparse.Namespace, argv: Sequence[str], transport: Transport | None = None) -> int:
    items = load_items(a.items)
    if a.only:
        items = [x for x in items if x["id"] in a.only]
    if not a.model:
        print(
            "The judge's model ID is needed: --model or ZJ_JUDGE_MODEL (not written in the repo)."
            " / 審査員のモデル ID が必要：--model または ZJ_JUDGE_MODEL（リポジトリには書かない）。",
            file=sys.stderr,
        )
        return 2
    prices = ClaudePrices.from_json(json.loads(a.prices.read_text(encoding="utf-8")))
    todo = [(cast(Item, it), s) for s in range(1, a.repeat + 1) for it in items]
    replays = ReplayStore(a.replays)
    ledger = None
    if a.mode == "live":
        if os.environ.get(LIVE_SWITCH) != "1":
            print(
                f"live calls real models and runs only on zg's Mac: {LIVE_SWITCH}=1 is not set, exiting."
                f" / live は実モデルを呼ぶので zg の Mac でのみ実行する：{LIVE_SWITCH}=1 が設定されていないため"
                "終了する。",
                file=sys.stderr,
            )
            return 2
        missing = [
            n for n, v in (("--max-claude-usd", a.max_claude_usd), ("--max-item-usd", a.max_item_usd)) if v is None
        ]
        if missing:
            flags = " ".join(missing)
            print(
                f"live needs explicit caps; there are no defaults. Missing {flags}, exiting."
                f" / live では上限を明示する必要があり、デフォルト値はない。{flags} が足りないため終了する。",
                file=sys.stderr,
            )
            return 2
        if not os.environ.get("ZJ_LEDGER"):
            print(
                "live needs a ledger: set ZJ_LEDGER (the same JSONL file as the backend), exiting."
                " / live には台帳が必要：ZJ_LEDGER を設定する（バックエンドと同じ JSONL ファイル）。終了する。",
                file=sys.stderr,
            )
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
        "model": judge.tag,  # tier name plus version, never the model ID / ティア名とバージョン。モデル ID は書かない
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
    print(f"Agreement / 一致率 {s['agree']}/{s['judged']}; report / レポート: {a.out / 'calibration.md'}")
    if stopped:
        print(
            f"Stopped midway / 途中で停止: {stopped}. What was judged is saved in the replays, and a rerun continues"
            " from there. / 採点済みのものはリプレイに保存した。再実行すると続きから採点する。",
            file=sys.stderr,
        )
        return 1
    return 0


# —— agree ——


def agree(a: argparse.Namespace) -> int:
    items = {x["id"]: x for x in load_items(a.items)}
    want = sorted(i for i, x in items.items() if x["zgSample"])
    labels: dict[str, Json] = json.loads(a.zg.read_text(encoding="utf-8"))["labels"]
    if sorted(labels) != want or len(want) != ZG_N:
        print(
            f"The items in labels do not match the {len(want)} zgSample items / labels の項目が zgSample の"
            f" {len(want)} 件と一致しない: extra / 余分 {sorted(set(labels) - set(want))},"
            f" missing / 不足 {sorted(set(want) - set(labels))}",
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
    en_verdict, ja_verdict = ("passed", "合格") if same >= ZG_BAR else ("not passed", "不合格")
    exact = sum(r[2] == r[3] for r in rows)
    within1 = sum(abs(r[2] - r[3]) <= 1 for r in rows)
    lines = [
        f"# zg's blind labels vs the data's labels: {en_verdict} / zg のブラインドラベルとデータのラベル：{ja_verdict}",
        "",
        f"- Same pass / fail: {same}/{ZG_N} (need ≥ {ZG_BAR})"
        f" / 合格 / 不合格が同じ：{same}/{ZG_N}（≥ {ZG_BAR} が必要）",
        f"- Same score {exact}/{ZG_N}, within 1 point {within1}/{ZG_N}"
        f" / 同じ点数 {exact}/{ZG_N}、差 1 点以内 {within1}/{ZG_N}",
        "",
        "| Item / 項目 | Case / ケース | zg | Data / データ | Agree / 一致 | zg's note / zg のメモ "
        "| Data's reason / データの理由 |",
        "|---|---|---:|---:|---|---|---|",
    ]
    lines += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {'✓' if r[4] else '✗'} | {r[5]} | {r[6]} |" for r in rows]
    text = "\n".join(lines) + "\n"
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "agree-zg.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


def parse(argv: Sequence[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="zoujin-judge",
        description="Judge calibration (data-design 7.3) / 審査員のキャリブレーション（data-design 7.3）",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser(
        "calibrate",
        help="The judge scores the calibration samples, and the agreement rate with the data's labels is computed"
        " / 審査員がキャリブレーションサンプルを採点し、データのラベルとの一致率を計算する",
    )
    c.add_argument("--mode", choices=("replay", "live"), default="replay")
    c.add_argument(
        "--model",
        default=os.environ.get("ZJ_JUDGE_MODEL"),
        help="The judge's model ID (defaults to ZJ_JUDGE_MODEL) / 審査員のモデル ID（デフォルトは ZJ_JUDGE_MODEL）",
    )
    c.add_argument("--effort", choices=EFFORTS, default="low")
    c.add_argument("--repeat", type=int, default=3, help="How many times to judge each item / 各項目を何回採点するか")
    c.add_argument(
        "--max-tokens",
        type=int,
        default=2048,
        help="Output cap (thinking counts too) / 出力の上限（思考も含む）",
    )
    c.add_argument(
        "--batch",
        action="store_true",
        help="Go through Batch (half price, slow); calibration does not by default"
        " / Batch を使う（半額、遅い）。キャリブレーションはデフォルトでは使わない",
    )
    c.add_argument(
        "--only",
        action="append",
        default=[],
        help="Judge only this item (can be given several times); for trying a few first to measure output tokens"
        " / この項目だけを採点する（複数回指定可）。まず数件試して出力トークンを測るため",
    )
    c.add_argument("--items", type=Path, default=ITEMS)
    c.add_argument("--replays", type=Path, default=REPLAYS)
    c.add_argument("--prices", type=Path, default=PRICES)
    c.add_argument("--live-cost", type=Path, default=LIVE_COST)
    c.add_argument("--out", type=Path, default=OUT)
    c.add_argument(
        "--max-claude-usd",
        type=float,
        help="Total cap of the Claude ledger (US dollars); required for live"
        " / Claude 台帳の総上限（米ドル）。live では必須",
    )
    c.add_argument(
        "--max-item-usd",
        type=float,
        help=f'Cap for the item "{LEDGER_ITEM}" (US dollars); required for live'
        f" / 項目「{LEDGER_ITEM}」の上限（米ドル）。live では必須",
    )
    c.add_argument(
        "--confirm",
        action="store_true",
        help="zg has seen the estimated cost and agreed / zg が見積もり費用を確認し、同意した",
    )
    g = sub.add_parser(
        "agree",
        help="Compare zg's 20 blind labels with the data's labels"
        " / zg のブラインドラベル 20 件をデータのラベルと比べる",
    )
    g.add_argument(
        "--zg", type=Path, required=True, help="zg's labels (labels-zg.json) / zg のラベル（labels-zg.json）"
    )
    g.add_argument("--items", type=Path, default=ITEMS)
    g.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    if a.cmd == "calibrate" and a.repeat < 1:
        ap.error("--repeat must be at least 1 / --repeat は 1 以上")
    return a


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    a = parse(argv)
    if a.cmd == "agree":
        return agree(a)
    return calibrate(a, argv)


if __name__ == "__main__":
    sys.exit(main())
