"""S-2 的运行脚本（B-2 卡第 5 条；格式和计分按 `evals/s2/README.md`）。

    uv run zoujin-s2 <标注集.jsonl> --out <目录> [--runs 3] [--resume] [--watch <条目 ID 清单>]

    # 真模型：只在 zg 的 Mac 上、PM 通知之后。先不带 --confirm 跑一次，看预计花费；zg 同意再带 --confirm。
    # 检查走 Claude（B-8）：Key 从钥匙串读进这个终端，模型 ID 用环境变量给（不进仓库）
    export ANTHROPIC_API_KEY="$(security find-generic-password -s zoujin-claude -w)"
    ZJ_MODEL=real ZJ_EVAL_LIVE=1 ZJ_LEDGER=<账本> ZJ_CLAUDE_HAIKU=… ZJ_CLAUDE_SONNET=… DATABASE_URL=… \\
        uv run --all-packages --extra real zoujin-s2 <标注集.jsonl> --out <目录> \\
        --max-item-usd <单项> --max-claude-usd <总> --confirm
    # S-085 ③ 再用 Haiku 量一遍：同样的命令前面加 ZJ_TEXT_MODELS=check=haiku-5.5，换一个 --out

- 每条按 `setup` 起局（`eval_api`），调 `check(candidate, turn, model_checks="all")`，跑 `--runs` 次。先跑完第 1 次的
  全部条目，再跑第 2 次。
- 每次的结果一行写进 `<目录>/results.jsonl`。中断（Ctrl-C、到上限、429）后 `--resume` 接着跑，跑过的不再花钱；
  标注集或检查提示的版本变了不让接着跑。跑完（或停下）写 `report.json` 和 `report.md`。
- 真模型的开关和上限：`ZJ_EVAL_LIVE=1`（同 E-0 live）、`--max-item-usd`、`--max-claude-usd`（检查走 Claude，没有
  默认值；D-029 的 100 美元是跨所有跑次的累计，填账本里已有的加这一次也不超过的数）、`ZJ_LEDGER`（两本账同一个文件，
  和 E-0 一样，总上限比的是账本里的累计）。少一样或不带 `--confirm`，只打印、不调用。
  每条的花费记在 `s2/<这次的标签>/<条目 ID>` 下，单项上限按它算（同一条的几次合计）。
- 账本到上限（`BudgetStop`）、第一个 429 或 529（`RateLimited`）：停下，已跑的照样出报告，退出码 3。回放缺失、配置不对：
  退出码 2。
- 没有默认的标注集路径，也不知道留出集在哪：路径由跑的人给。报告里只有条目 ID、标注的判定和规则、自检的判定、规则、
  理由和 trace ID，不抄条目的原话和摘要；留出集跑出来的报告和回放先交数据（B-2 卡「留出样本的规矩」）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zoujin_backend import eval_api
from zoujin_backend.config import ConfigError, Settings
from zoujin_backend.ids import IdGen
from zoujin_backend.models.prompts import PROMPTS
from zoujin_backend.narrator.pipeline import checker

Json = Any

EXIT_CONFIG = 2
EXIT_STOP = 3
GATE_AGREEMENT = 0.90
LIVE_ENV = "ZJ_EVAL_LIVE"
RESULTS = "results.jsonl"
META = "meta.json"


def parse(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="zoujin-s2", description="S-2：叙事者自检（第 3、4 步）和标注的一致率")
    p.add_argument("dataset", type=Path, help="标注集（evals/s2/README.md 的格式）")
    p.add_argument("--out", type=Path, required=True, help="结果和报告的目录")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--resume", action="store_true", help="接着上次中断的跑")
    p.add_argument("--watch", type=Path, help="要单列的条目 ID，一行一个（数据给）")
    p.add_argument("--max-item-usd", type=float, help="真模型：每条（几次合计）的上限")
    p.add_argument("--max-claude-usd", type=float, help="真模型：Claude 那本账的总上限（含账本里已有的）")
    p.add_argument("--confirm", action="store_true", help="真模型：看过预计花费，确认要调用")
    return p.parse_args(argv)


def now_z() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load(path: Path) -> list[Json]:
    items = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    ids = [x["id"] for x in items]
    if len(set(ids)) != len(ids):
        raise ConfigError("标注集里有重复的条目 ID")
    return items


# —— 真模型的开关 ——


def per_check_usd(settings: Settings) -> tuple[float, float]:
    """一次检查调用的花费：（上限：不算缓存、输出按上限，账本按它判；推算：按 B-8 卡的假设，前缀 1.7 万 token 走缓存、
    新的输入 2,000、输出含思考 1,200 token）。"""
    from zoujin_llm import canonical, claude_prices

    from zoujin_backend.models.claude import api_schema
    from zoujin_backend.models.render import world_prefix
    from zoujin_backend.models.text import spec
    from zoujin_backend.world import Library

    world = Library(settings.worlds, settings.scenes, settings.world).current.world
    chars = len(world_prefix(world)) + len(PROMPTS["check"].text) + len(canonical(api_schema("check"))) + 6000
    sp, prices = spec("check"), claude_prices()
    upper = prices.estimate_chars(sp.model, chars, sp.max_output)
    k = prices.price(sp.model).tokenizer
    likely = prices.cost(
        sp.model, {"cacheReadTokens": int(17000 * k), "inputTokens": int(2000 * k), "outputTokens": 1200}
    )
    return upper, likely


def gate(args: argparse.Namespace, settings: Settings, env: Mapping[str, str], n: int, argv: Sequence[str]) -> bool:
    """真模型：打印预计花费和完整命令；开关、上限、账本、项目都齐了而且带了 --confirm 才返回 True。"""
    from zoujin_backend.models.text import spec

    each, likely = per_check_usd(settings)
    calls = n * args.runs
    print(f"检查用 Claude {spec('check').model}，{n} 条 × {args.runs} 次 = {calls} 次调用")
    print(f"预计花费（按 B-8 卡推算，前缀走缓存）：每次约 ${likely:.3f}，合计约 ${likely * calls:.2f}")
    print(f"上限（不算缓存、输出按上限，账本按它判）：每次 ${each:.3f}，合计 ${each * calls:.2f}")
    print(f"单项上限至少要 ${each * args.runs:.2f}（同一条 {args.runs} 次合计），否则第一次就停")
    names = " ".join(
        f"{k}=…"
        for k in ("ZJ_MODEL", LIVE_ENV, "ZJ_LEDGER", "ZJ_CLAUDE_HAIKU", "ZJ_CLAUDE_SONNET", "ZJ_TEXT_MODELS")
        if k != "ZJ_TEXT_MODELS" or env.get(k)
    )
    cmd = [x for x in argv if x != "--confirm"]
    print(f"命令：{names} uv run --all-packages --extra real zoujin-s2 {shlex.join(cmd)} --confirm")
    missing = []
    if env.get(LIVE_ENV) != "1":
        missing.append(f"没设 {LIVE_ENV}=1")
    if args.max_item_usd is None:
        missing.append("少 --max-item-usd")
    if args.max_claude_usd is None:
        missing.append("少 --max-claude-usd")
    if settings.ledger is None:
        missing.append("没设 ZJ_LEDGER（两本账同一个文件）")
    if not env.get("ANTHROPIC_API_KEY"):
        missing.append("没设 ANTHROPIC_API_KEY（从钥匙串读进这个终端）")
    for name in ("ZJ_CLAUDE_HAIKU", "ZJ_CLAUDE_SONNET"):
        if not env.get(name):
            missing.append(f"没设 {name}")
    if not args.confirm:
        missing.append("没带 --confirm")
    if missing:
        print("只打印，不调用：" + "；".join(missing))
        return False
    return True


# —— 跑 ——


def start(args: argparse.Namespace, items: Sequence[Json], settings: Settings) -> tuple[Json, list[Json]]:
    """新开或接着跑：返回 meta 和已有的结果。"""
    out: Path = args.out
    sha = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    meta = {
        "dataset": args.dataset.name,
        "datasetSha256": sha,
        "items": len(items),
        "runs": args.runs,
        "checkPromptVersion": PROMPTS["check"].version,
        "checker": checker(True),
        "model": settings.model,
    }
    results, meta_path = out / RESULTS, out / META
    if results.exists() and not args.resume:
        raise ConfigError(f"{out} 里已经有结果：接着跑加 --resume，重新跑换一个目录")
    if args.resume and meta_path.is_file():
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        for k in ("datasetSha256", "runs", "checkPromptVersion", "checker", "model"):
            if old.get(k) != meta[k]:
                raise ConfigError(f"和上次的 {k} 不一样，不能接着跑（{old.get(k)} → {meta[k]}）")
        meta["tag"], meta["startedAt"] = old["tag"], old["startedAt"]
    else:
        meta["startedAt"] = now_z()
        meta["tag"] = meta["startedAt"].replace(":", "").replace("-", "")
    out.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = (
        [json.loads(x) for x in results.read_text(encoding="utf-8").splitlines() if x.strip()]
        if results.exists()
        else []
    )
    return meta, rows


def check_one(item: Json, run: int, tag: str, live: bool, ids: IdGen) -> Json:
    if live:
        os.environ["ZJ_LEDGER_ITEM"] = f"s2/{tag}/{item['id']}"
    trace = ids.new("trc")
    row: Json = {"id": item["id"], "run": run, "traceId": trace}
    try:
        s = eval_api.setup(item["setup"], mode="text")
        s.span = {"trace_id": trace}
        got = s.check(item["candidate"], item["turn"], model_checks="all")
    except eval_api.CallFailed:
        return {**row, "status": "timeout"}
    except eval_api.EvalNotImplemented as e:
        return {**row, "status": "skipped", "reason": f"后端未实现：{e}"}
    check = got["check"]
    return {
        **row,
        "status": check["status"],
        "failedRules": check["failedRules"],
        "reason": check.get("reason"),
        "checker": check["checker"],
        "rules": got["rules"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse(argv)
    try:
        settings = Settings.from_env()
        items = load(args.dataset)
        live = settings.model == "real"
        if live:
            if not gate(args, settings, os.environ, len(items), argv):
                return 0
            os.environ["ZJ_MAX_CLAUDE_USD"] = repr(args.max_claude_usd)
            os.environ["ZJ_MAX_ITEM_USD"] = repr(args.max_item_usd)
        meta, rows = start(args, items, settings)
    except ConfigError as e:
        print(f"zoujin-s2：{e}", file=sys.stderr)
        return EXIT_CONFIG
    watch = _watch(args.watch)
    done = {(r["id"], r["run"]) for r in rows}
    ids = IdGen()
    stopped: str | None = None
    code = 0
    try:
        with (args.out / RESULTS).open("a", encoding="utf-8") as f:
            for run in range(1, args.runs + 1):
                for item in items:
                    if (item["id"], run) in done:
                        continue
                    row = check_one(item, run, meta["tag"], live, ids)
                    f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    f.flush()
                    rows.append(row)
                    print(f"第 {run} 次 {item['id']}：{row['status']} {' '.join(row.get('failedRules', []))}")
    except (eval_api.BudgetStop, eval_api.RateLimited) as e:
        stopped, code = type(e).__name__, EXIT_STOP
        print(f"停下（{stopped}）：{e}", file=sys.stderr)
    except (eval_api.ReplayMissing, ConfigError) as e:
        stopped, code = type(e).__name__, EXIT_CONFIG
        print(f"停下（{stopped}）：{e}", file=sys.stderr)
    except KeyboardInterrupt:
        stopped, code = "KeyboardInterrupt", 130
    report = build_report(items, rows, meta, stopped, watch)
    write_report(args.out, report)
    print(f"报告：{args.out / 'report.md'}")
    return code


def _watch(path: Path | None) -> set[str]:
    if path is None:
        return set()
    return {x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip()}


# —— 计分（evals/s2/README.md「怎么跑、怎么算」） ——


def verdict(row: Json | None) -> str | None:
    """过 = passed；不过 = 其余三种；超时、跳过、没跑 = None。"""
    if row is None or row["status"] in ("timeout", "skipped"):
        return None
    return "pass" if row["status"] == "passed" else "fail"


def build_report(items: Sequence[Json], rows: Sequence[Json], meta: Json, stopped: str | None, watch: set[str]) -> Json:
    runs = int(meta["runs"])
    got = {(r["id"], r["run"]): r for r in rows}
    n = len(items)
    per_run: list[Json] = []
    for run in range(1, runs + 1):
        done = [x for x in items if (x["id"], run) in got]
        agree, false_reject, missed, both, rule_ok, timeouts = 0, [], [], 0, 0, []
        missed_by_stage: Counter[str] = Counter()
        for x in done:
            row = got[(x["id"], run)]
            v, label = verdict(row), x["label"]
            if v is None:
                timeouts.append(x["id"])
                continue
            agree += v == label["verdict"]
            if label["verdict"] == "pass" and v == "fail":
                false_reject.append(x["id"])
            if label["verdict"] == "fail" and v == "pass":
                missed.append(x["id"])
                missed_by_stage[label.get("stage", "?")] += 1
            if label["verdict"] == "fail" and v == "fail":
                both += 1
                ok = set(label["failedRules"]) | set(label.get("acceptAlso", []))
                rule_ok += bool(ok & set(row["failedRules"]))
        per_run.append(
            {
                "run": run,
                "complete": len(done) == n,
                "done": len(done),
                "agree": agree,
                "agreement": agree / n if n else 0.0,
                "falseRejects": false_reject,
                "missed": missed,
                "missedByStage": dict(sorted(missed_by_stage.items())),
                "bothFail": both,
                "rulesAgree": rule_ok,
                "timeouts": timeouts,
            }
        )
    majority = {}
    for x in items:
        votes = [v for run in range(1, runs + 1) if (v := verdict(got.get((x["id"], run)))) is not None]
        if votes:
            c = Counter(votes)
            majority[x["id"]] = "pass" if c["pass"] > c["fail"] else "fail"  # 平票按不过（保守）
    major_agree = sum(majority.get(x["id"]) == x["label"]["verdict"] for x in items)
    anchor_misses = [
        {"id": x["id"], "run": run}
        for x in items
        if "R1-anchor" in x["label"]["failedRules"]
        for run in range(1, runs + 1)
        if verdict(got.get((x["id"], run))) == "pass"
    ]
    unstable = []
    for x in items:
        seen = {
            (verdict(r), tuple(r.get("failedRules", [])))
            for run in range(1, runs + 1)
            if (r := got.get((x["id"], run))) is not None
        }
        if len(seen) > 1:
            unstable.append(x["id"])
    scored = [r for r in per_run if r["complete"]] or per_run
    worst = min((r["agreement"] for r in scored), default=0.0)
    watched: Json = {}
    if watch:
        for name, group in (
            ("watch", [x for x in items if x["id"] in watch]),
            ("others", [x for x in items if x["id"] not in watch]),
        ):
            ok = sum(majority.get(x["id"]) == x["label"]["verdict"] for x in group)
            watched[name] = {"items": len(group), "agreeMajority": ok}
    complete = all(r["complete"] for r in per_run)
    return {
        "meta": dict(meta),
        "finishedAt": now_z(),
        "complete": complete,
        "stopped": stopped,
        "summary": {
            "items": n,
            "violations": sum(x["label"]["verdict"] == "fail" for x in items),
            "worstAgreement": worst,
            "majorityAgree": major_agree,
            "majorityAgreement": major_agree / n if n else 0.0,
            "anchorMisses": anchor_misses,
            "unstable": unstable,
            "gates": {
                "agreement": worst >= GATE_AGREEMENT,
                "anchorMisses": not anchor_misses,
            },
            "watched": watched,
        },
        "runs": per_run,
        "items": [
            {
                "id": x["id"],
                "label": {
                    k: x["label"][k] for k in ("verdict", "failedRules", "acceptAlso", "stage") if k in x["label"]
                },
                "majority": majority.get(x["id"]),
                "runs": [got.get((x["id"], run)) for run in range(1, runs + 1)],
            }
            for x in items
        ],
    }


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _cell(row: Json | None) -> str:
    if row is None:
        return "—"
    v = verdict(row)
    if v is None:
        return str(row["status"])
    return "过" if v == "pass" else _rules("不过", row["failedRules"])


def _rules(head: str, rules: Sequence[str]) -> str:
    return " ".join([head, *(r.split("-")[0] for r in rules)])


def markdown(rep: Json) -> str:
    m, s = rep["meta"], rep["summary"]
    n = s["items"]
    status = "完成" if rep["complete"] else f"没跑完（{rep['stopped'] or '中断'}），按已跑的算"
    yes = {True: "过", False: "不过"}
    gates = s["gates"]
    misses = "、".join(f"{x['id']} 第 {x['run']} 次" for x in s["anchorMisses"]) or "无"
    out = [
        "# S-2 自检准确率（zoujin-s2）",
        "",
        f"- 标注集：`{m['dataset']}`（sha256 {m['datasetSha256'][:12]}），{n} 条："
        f"违规 {s['violations']}、合规 {n - s['violations']}",
        f"- 检查提示：`{m['checkPromptVersion']}`（checker `{m['checker']}`），"
        f"模型模式 {m['model']}，每条 {m['runs']} 次",
        f"- 状态：{status}。开始 {m['startedAt']}，结束 {rep['finishedAt']}",
        "",
        "## 门槛",
        "",
        "| 项 | 结果 | 门槛 | |",
        "|---|---|---|---|",
        f"| 一致率（最差的一次） | {_pct(s['worstAgreement'])} | ≥ {_pct(GATE_AGREEMENT)} "
        f"| {yes[gates['agreement']]} |",
        f"| 锚点漏检（任何一次） | {len(s['anchorMisses'])}（{misses}） | 0 | {yes[gates['anchorMisses']]} |",
        "",
        f"三次多数票的一致率：{_pct(s['majorityAgreement'])}（{s['majorityAgree']}/{n}）。",
        "",
        "## 每一次",
        "",
        "| 次 | 跑了 | 一致 | 一致率 | 合规被误拒 | 违规漏判（按 stage） | 规则一致（两边都判不过） | 超时、跳过 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rep["runs"]:
        stage = "、".join(f"{k} {v}" for k, v in r["missedByStage"].items()) or "0"
        out.append(
            f"| {r['run']} | {r['done']}/{n} | {r['agree']} | {_pct(r['agreement'])} | {len(r['falseRejects'])} "
            f"| {len(r['missed'])}（{stage}） | {r['rulesAgree']}/{r['bothFail']} | {len(r['timeouts'])} |"
        )
    out += ["", "## 几次结果不一样的条目", "", "、".join(s["unstable"]) or "无"]
    if s["watched"]:
        w = s["watched"]
        out += [
            "",
            "## 单列的条目（--watch）",
            "",
            f"单列的 {w['watch']['items']} 条多数票一致 {w['watch']['agreeMajority']}；"
            f"其余 {w['others']['items']} 条一致 {w['others']['agreeMajority']}。",
        ]
    runs = range(1, int(m["runs"]) + 1)
    out += [
        "",
        "## 每一条",
        "",
        "| 条目 | 标注 | stage | " + " | ".join(f"第 {i} 次" for i in runs) + " |",
        "|---|---|---|" + "---|" * len(runs),
    ]
    for x in rep["items"]:
        lab = x["label"]
        mark = "过" if lab["verdict"] == "pass" else _rules("不过", lab["failedRules"])
        cells = " | ".join(_cell(r) for r in x["runs"])
        out.append(f"| {x['id']} | {mark} | {lab.get('stage', '')} | {cells} |")
    return "\n".join(out) + "\n"


def write_report(out: Path, rep: Json) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "report.md").write_text(markdown(rep), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
