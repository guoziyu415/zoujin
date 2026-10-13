"""Runner script for S-2 (card B-2 item 5; format and scoring per `evals/s2/README.md`).

    uv run zoujin-s2 <labelled-set.jsonl> --out <dir> [--runs 3] [--resume] [--watch <item ID list>]

    # Real model: only on zg's Mac, after the PM's notice. First run once without --confirm to see the estimated
    # cost; add --confirm once zg agrees. The check goes to Claude (B-8): the key is read from the keychain into this
    # terminal, and model IDs are given via env vars (kept out of the repo)
    # 本物のモデル：zg の Mac 上だけ、PM の連絡の後で。まず --confirm なしで 1 回実行して予想費用を確認し、
    # zg が同意したら --confirm を付ける。チェックは Claude を使う（B-8）：
    # キーはキーチェーンからこのターミナルに読み込み、モデル ID は環境変数で渡す（リポジトリには入れない）
    export ANTHROPIC_API_KEY="$(security find-generic-password -s zoujin-claude -w)"
    ZJ_MODEL=real ZJ_EVAL_LIVE=1 ZJ_LEDGER=<ledger> ZJ_CLAUDE_HAIKU=… ZJ_CLAUDE_SONNET=… DATABASE_URL=… \\
        uv run --all-packages --extra real zoujin-s2 <labelled-set.jsonl> --out <dir> \\
        --max-item-usd <per item> --max-claude-usd <total> --confirm
    # S-085 ③, measure again with Haiku: prefix the same command with ZJ_TEXT_MODELS=check=haiku-5.5 and use another
    # --out
    # S-085 ③ で Haiku でもう一度測る：同じコマンドの前に ZJ_TEXT_MODELS=check=haiku-5.5 を付け、別の --out にする

- Each item starts a playthrough from its `setup` (`eval_api`) and calls `check(candidate, turn, model_checks="all")`,
  `--runs` times. All items of run 1 finish before run 2 starts.
- Each result is written as one line to `<dir>/results.jsonl`. After an interruption (Ctrl-C, cap reached, 429),
  `--resume` continues and nothing already run is paid for again; if the labelled set or the check prompt version
  changed, resuming is refused. When finished (or stopped) it writes `report.json` and `report.md`.
- Real-model switch and caps: `ZJ_EVAL_LIVE=1` (same as E-0 live), `--max-item-usd`, `--max-claude-usd` (the check
  goes to Claude; no defaults; D-029's 100 dollars accumulate across all runs, so give a number that stays within it
  including what the ledger already has), `ZJ_LEDGER` (both accounts in one file, as in E-0; the total cap is compared
  with the accumulated total in the ledger). If any is missing or `--confirm` is not given, it only prints and makes
  no calls. Each item's spend is recorded under `s2/<this run's tag>/<item ID>`, and the item cap applies to it (the
  sum of that item's runs).
- Ledger cap reached (`BudgetStop`), or the first 429 or 529 (`RateLimited`): stop, still write the report for what
  ran, exit code 3. Missing replay or bad configuration: exit code 2.
- Once the check prompt is final (`CHECK_FINAL`), labelled sets other than the public 10 items (the holdout set) are
  run on the real model only with the final prompt; a non-final one exits with code 2.
- There is no default labelled-set path and this script does not know where the holdout set is: whoever runs it gives
  the path. The report contains only item IDs, the labelled verdicts and rules, the self-check's verdicts, rules,
  reasons and trace IDs, never the items' original words or summaries; reports and replays from the holdout set go to
  data first (card B-2 "rules for holdout samples").

S-2 の実行スクリプト（B-2 カード第 5 項。形式と採点は `evals/s2/README.md` に従う）。

- 各項目は `setup` からプレイを開始し（`eval_api`）、`check(candidate, turn, model_checks="all")` を `--runs` 回呼ぶ。
  1 回目の全項目を終えてから 2 回目を実行する。
- 毎回の結果を `<dir>/results.jsonl` に 1 行ずつ書く。中断（Ctrl-C、上限到達、429）の後は `--resume` で続きから実行し、
  実行済みのものには二度と費用をかけない。ラベル付きセットかチェックプロンプトのバージョンが変わっていれば続行させない。
  終わったら（または止まったら）`report.json` と `report.md` を書く。
- 本物のモデルのスイッチと上限：`ZJ_EVAL_LIVE=1`（E-0 live と同じ）、`--max-item-usd`、`--max-claude-usd`（チェックは
  Claude を使う。デフォルトはない。D-029 の 100 ドルはすべての実行の累計なので、
  台帳にすでにある分と今回を足しても超えない数を入れる）、`ZJ_LEDGER`（2 つの勘定は同じファイルで E-0 と同じ。
  総上限は台帳の累計と比べる）。1 つでも欠けるか `--confirm` がなければ、表示だけで呼び出さない。
  各項目の費用は `s2/<今回のタグ>/<項目 ID>` に記録し、項目の上限はこれで計算する（同じ項目の各回の合計）。
- 台帳が上限に達した（`BudgetStop`）、最初の 429 か 529（`RateLimited`）：止まり、
  実行済みの分のレポートはそのまま出力し、終了コード 3。リプレイがない、設定が正しくない：終了コード 2。
- チェックプロンプトが確定版になった後（`CHECK_FINAL`）、公開の 10 件以外のラベル付きセット（ホールドアウトセット）
  は確定版のプロンプトでのみ本物のモデルを実行し、確定版でなければ終了コード 2。
- ラベル付きセットのデフォルトのパスはなく、ホールドアウトセットの場所も知らない：パスは実行する人が渡す。
  レポートには項目 ID、ラベルの判定とルール、自己チェックの判定・ルール・理由、trace ID だけを書き、
  項目の発話の原文や要約は写さない。ホールドアウトセットで出たレポートとリプレイはまずデータ担当に渡す（B-2
  カード「ホールドアウトサンプルの決まり」）。
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
# The final check prompt (card B-2 "final"): on 2026-10-11 the public 10 items × 3 runs were run on the Mac; Sonnet
# scored 100% all three times and Haiku 90% in its worst run, no anchors were missed, and both tiers passed the gates.
# If the check text or Schema changes after this, this S-2 run no longer represents the new prompt: data must produce
# a new measurement set (`evals/s2/README.md`) before this is changed.
# チェックプロンプトの確定版（B-2 カード「確定」）：2026-10-11 に Mac で公開の 10 件 × 3 回を実行し、
# Sonnet は 3 回とも 100%、Haiku は最も低い回で 90%、アンカーの見逃しはなく、どちらのティアもゲートを通った。
# 確定後に check のテキストか Schema を変えると、今回の S-2 は新しいプロンプトを表さなくなる：
# データ担当が新しい測定セットを作ってから（`evals/s2/README.md`）ここを変える。
CHECK_FINAL = "p48aa3f14c44b"
# The public 10 items: for tuning the prompt, whether final or not
# 公開の 10 件：プロンプトの調整用。確定版かどうかに関係なく使える
DEV_SET = "s2_dev.jsonl"


def parse(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="zoujin-s2",
        description="S-2: agreement between the narrator's self-check (steps 3, 4) and the labels / "
        "S-2：ナレーターの自己チェック（第 3・4 段階）とラベルの一致率",
    )
    p.add_argument(
        "dataset",
        type=Path,
        help="Labelled set (format of evals/s2/README.md) / ラベル付きセット（evals/s2/README.md の形式）",
    )
    p.add_argument(
        "--out", type=Path, required=True, help="Directory for results and reports / 結果とレポートのディレクトリ"
    )
    p.add_argument("--runs", type=int, default=3)
    p.add_argument(
        "--resume", action="store_true", help="Continue the last interrupted run / 前回中断した実行の続きから"
    )
    p.add_argument(
        "--watch",
        type=Path,
        help="Item IDs to list separately, one per line (given by data) / "
        "個別に集計する項目 ID、1 行に 1 つ（データ担当が渡す）",
    )
    p.add_argument(
        "--max-item-usd",
        type=float,
        help="Real model: cap per item (sum of its runs) / 本物のモデル：項目ごと（各回の合計）の上限",
    )
    p.add_argument(
        "--max-claude-usd",
        type=float,
        help="Real model: total cap of Claude's ledger (including what the ledger already has) / "
        "本物のモデル：Claude の台帳の総上限（台帳にすでにある分を含む）",
    )
    p.add_argument(
        "--confirm",
        action="store_true",
        help="Real model: the estimated cost was seen and the calls are confirmed / "
        "本物のモデル：予想費用を確認し、呼び出すことを確定した",
    )
    return p.parse_args(argv)


def now_z() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load(path: Path) -> list[Json]:
    items = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    ids = [x["id"] for x in items]
    if len(set(ids)) != len(ids):
        raise ConfigError("Duplicate item IDs in the labelled set / ラベル付きセットに重複した項目 ID がある")
    return items


# —— Real-model switch / 本物のモデルのスイッチ ——


def per_check_usd(settings: Settings) -> tuple[float, float]:
    """Cost of one check call: (cap: no cache, output at the limit, which the ledger checks against; estimate: per
    card B-8's assumptions, a 17,000-token prefix from the cache, 2,000 new input tokens, 1,200 output tokens including
    thinking).

    チェック 1 回の呼び出しの費用：（上限：キャッシュを数えず出力は上限で、台帳はこれで判定する。推算：
    B-8 カードの仮定に従い、プレフィックス 1.7 万トークンはキャッシュ、新しい入力 2,000、
    思考を含む出力 1,200 トークン）。
    """
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
    """Real model: print the estimated cost and the full command; return True only if the switch, caps, ledger and
    project are all present and --confirm was given.

    本物のモデル：予想費用と完全なコマンドを表示する。スイッチ、上限、台帳、
    プロジェクトがすべて揃っていて --confirm があるときだけ True を返す。
    """
    from zoujin_backend.models.text import spec

    each, likely = per_check_usd(settings)
    calls = n * args.runs
    print(
        f"Check uses Claude {spec('check').model}, {n} items × {args.runs} runs = {calls} calls / "
        f"チェックは Claude {spec('check').model}、{n} 件 × {args.runs} 回 = {calls} 回の呼び出し"
    )
    print(
        f"Estimated cost (per card B-8, prefix cached): about ${likely:.3f} per call, about ${likely * calls:.2f} "
        f"in total / 予想費用（B-8 カードで推算、プレフィックスはキャッシュ）：1 回約 ${likely:.3f}、合計約 "
        f"${likely * calls:.2f}"
    )
    print(
        f"Cap (no cache, output at the limit; the ledger checks against it): ${each:.3f} per call, "
        f"${each * calls:.2f} in total / 上限（キャッシュなし、出力は上限、台帳はこれで判定）：1 回 ${each:.3f}、"
        f"合計 ${each * calls:.2f}"
    )
    print(
        f"The item cap must be at least ${each * args.runs:.2f} (one item's {args.runs} runs together), otherwise it "
        f"stops at the first call / 項目の上限は少なくとも ${each * args.runs:.2f}（同じ項目の {args.runs} 回の合計）"
        "必要で、足りなければ最初の 1 回で止まる"
    )
    names = " ".join(
        f"{k}=…"
        for k in ("ZJ_MODEL", LIVE_ENV, "ZJ_LEDGER", "ZJ_CLAUDE_HAIKU", "ZJ_CLAUDE_SONNET", "ZJ_TEXT_MODELS")
        if k != "ZJ_TEXT_MODELS" or env.get(k)
    )
    cmd = [x for x in argv if x != "--confirm"]
    print(f"Command / コマンド: {names} uv run --all-packages --extra real zoujin-s2 {shlex.join(cmd)} --confirm")
    missing = []
    if env.get(LIVE_ENV) != "1":
        missing.append(f"{LIVE_ENV}=1 not set / {LIVE_ENV}=1 が未設定")
    if args.max_item_usd is None:
        missing.append("missing --max-item-usd / --max-item-usd がない")
    if args.max_claude_usd is None:
        missing.append("missing --max-claude-usd / --max-claude-usd がない")
    if settings.ledger is None:
        missing.append("ZJ_LEDGER not set (both accounts in one file) / ZJ_LEDGER が未設定（2 つの勘定は同じファイル）")
    if not env.get("ANTHROPIC_API_KEY"):
        missing.append(
            "ANTHROPIC_API_KEY not set (read it from the keychain into this terminal) / "
            "ANTHROPIC_API_KEY が未設定（キーチェーンからこのターミナルに読み込む）"
        )
    for name in ("ZJ_CLAUDE_HAIKU", "ZJ_CLAUDE_SONNET"):
        if not env.get(name):
            missing.append(f"{name} not set / {name} が未設定")
    if not args.confirm:
        missing.append("no --confirm / --confirm がない")
    if missing:
        print("Printing only, no calls / 表示のみで呼び出さない: " + "; ".join(missing))
        return False
    return True


# —— Run / 実行 ——


def start(args: argparse.Namespace, items: Sequence[Json], settings: Settings) -> tuple[Json, list[Json]]:
    """Start fresh or resume: return meta and the existing results.

    新しく始めるか続きから実行する：meta と既存の結果を返す。
    """
    out: Path = args.out
    sha = hashlib.sha256(args.dataset.read_bytes()).hexdigest()
    meta = {
        "dataset": args.dataset.name,
        "datasetSha256": sha,
        "items": len(items),
        "runs": args.runs,
        "checkPromptVersion": PROMPTS["check"].version,
        "checkPromptFinal": PROMPTS["check"].version == CHECK_FINAL,
        "checker": checker(True),
        "model": settings.model,
    }
    results, meta_path = out / RESULTS, out / META
    if results.exists() and not args.resume:
        raise ConfigError(
            f"{out} already has results: add --resume to continue, or use another directory to start over / "
            f"{out} にはすでに結果がある：続けるなら --resume を付け、やり直すなら別のディレクトリにする"
        )
    if args.resume and meta_path.is_file():
        old = json.loads(meta_path.read_text(encoding="utf-8"))
        for k in ("datasetSha256", "runs", "checkPromptVersion", "checker", "model"):
            if old.get(k) != meta[k]:
                raise ConfigError(
                    f"{k} differs from last time, cannot resume ({old.get(k)} → {meta[k]}) / "
                    f"{k} が前回と違うので続きから実行できない（{old.get(k)} → {meta[k]}）"
                )
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
        return {**row, "status": "skipped", "reason": f"Not implemented in the backend / バックエンド未実装: {e}"}
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
            version = PROMPTS["check"].version
            if args.dataset.name != DEV_SET and version != CHECK_FINAL:
                raise ConfigError(
                    f"Check prompt {version} is not the final {CHECK_FINAL}: beyond the public 10 items only the "
                    f"final prompt is run / チェックプロンプト {version} は確定版の {CHECK_FINAL} ではない："
                    "公開の 10 件以外は確定版のプロンプトでのみ実行する"
                )
            if not gate(args, settings, os.environ, len(items), argv):
                return 0
            os.environ["ZJ_MAX_CLAUDE_USD"] = repr(args.max_claude_usd)
            os.environ["ZJ_MAX_ITEM_USD"] = repr(args.max_item_usd)
        meta, rows = start(args, items, settings)
    except ConfigError as e:
        print(f"zoujin-s2: {e}", file=sys.stderr)
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
                    print(f"Run / 回 {run} {item['id']}: {row['status']} {' '.join(row.get('failedRules', []))}")
    except (eval_api.BudgetStop, eval_api.RateLimited) as e:
        stopped, code = type(e).__name__, EXIT_STOP
        print(f"Stopped / 停止 ({stopped}): {e}", file=sys.stderr)
    except (eval_api.ReplayMissing, ConfigError) as e:
        stopped, code = type(e).__name__, EXIT_CONFIG
        print(f"Stopped / 停止 ({stopped}): {e}", file=sys.stderr)
    except KeyboardInterrupt:
        stopped, code = "KeyboardInterrupt", 130
    report = build_report(items, rows, meta, stopped, watch)
    write_report(args.out, report)
    print(f"Report / レポート: {args.out / 'report.md'}")
    return code


def _watch(path: Path | None) -> set[str]:
    if path is None:
        return set()
    return {x.strip() for x in path.read_text(encoding="utf-8").splitlines() if x.strip()}


# —— Scoring (evals/s2/README.md "how to run, how to score") / 採点（evals/s2/README.md「実行方法と計算方法」） ——


def verdict(row: Json | None) -> str | None:
    """pass = passed; fail = the other three; timeout, skipped, not run = None.

    合格 = passed、不合格 = ほかの 3 種類、タイムアウト・スキップ・未実行 = None。
    """
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
            # A tie counts as fail (conservative) / 同数なら不合格とする（保守的）
            majority[x["id"]] = "pass" if c["pass"] > c["fail"] else "fail"
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
    return "pass" if v == "pass" else _rules("fail", row["failedRules"])


def _rules(head: str, rules: Sequence[str]) -> str:
    return " ".join([head, *(r.split("-")[0] for r in rules)])


def markdown(rep: Json) -> str:
    m, s = rep["meta"], rep["summary"]
    n = s["items"]
    status = (
        "complete / 完了"
        if rep["complete"]
        else f"not finished ({rep['stopped'] or 'interrupted'}), scored on what ran / "
        f"未完了（{rep['stopped'] or '中断'}）、実行済みの分で計算"
    )
    yes = {True: "pass / 合格", False: "fail / 不合格"}
    gates = s["gates"]
    misses = ", ".join(f"{x['id']} run {x['run']}" for x in s["anchorMisses"]) or "none / なし"
    final = " (final / 確定版)" if m.get("checkPromptFinal") else " (not final / 確定版ではない)"
    out = [
        "# S-2 self-check accuracy / 自己チェックの正確さ (zoujin-s2)",
        "",
        f"- Labelled set / ラベル付きセット: `{m['dataset']}` (sha256 {m['datasetSha256'][:12]}), {n} items / 件: "
        f"violations / 違反 {s['violations']}, compliant / 適合 {n - s['violations']}",
        f"- Check prompt / チェックプロンプト: `{m['checkPromptVersion']}`{final} (checker `{m['checker']}`), "
        f"model mode / モデルモード {m['model']}, {m['runs']} runs per item / 1 件あたり {m['runs']} 回",
        f"- Status / 状態: {status}. Started / 開始 {m['startedAt']}, finished / 終了 {rep['finishedAt']}",
        "",
        "## Gates / ゲート",
        "",
        "| Item / 項目 | Result / 結果 | Gate / ゲート | |",
        "|---|---|---|---|",
        f"| Agreement (worst run) / 一致率（最も低い回） | {_pct(s['worstAgreement'])} | ≥ {_pct(GATE_AGREEMENT)} "
        f"| {yes[gates['agreement']]} |",
        f"| Anchor misses (any run) / アンカーの見逃し（いずれかの回） | {len(s['anchorMisses'])} ({misses}) | 0 "
        f"| {yes[gates['anchorMisses']]} |",
        "",
        f"Agreement of the majority vote over the runs / 各回の多数決の一致率: {_pct(s['majorityAgreement'])} "
        f"({s['majorityAgree']}/{n}).",
        "",
        "## Each run / 各回",
        "",
        "| Run / 回 | Done / 実行 | Agree / 一致 | Agreement / 一致率 | Compliant falsely rejected / 適合の誤却下 "
        "| Violations missed (by stage) / 違反の見逃し（stage 別） "
        "| Rules agree (both fail) / ルールの一致（両方とも不合格） | Timeouts, skipped / タイムアウト・スキップ |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rep["runs"]:
        stage = ", ".join(f"{k} {v}" for k, v in r["missedByStage"].items()) or "0"
        out.append(
            f"| {r['run']} | {r['done']}/{n} | {r['agree']} | {_pct(r['agreement'])} | {len(r['falseRejects'])} "
            f"| {len(r['missed'])} ({stage}) | {r['rulesAgree']}/{r['bothFail']} | {len(r['timeouts'])} |"
        )
    out += [
        "",
        "## Items whose results differ between runs / 回によって結果が違う項目",
        "",
        ", ".join(s["unstable"]) or "none / なし",
    ]
    if s["watched"]:
        w = s["watched"]
        out += [
            "",
            "## Items listed separately (--watch) / 個別に集計した項目（--watch）",
            "",
            f"The {w['watch']['items']} listed items agree by majority vote in {w['watch']['agreeMajority']}; "
            f"the other {w['others']['items']} items agree in {w['others']['agreeMajority']}. / "
            f"個別の {w['watch']['items']} 件は多数決で {w['watch']['agreeMajority']} 件一致、"
            f"ほかの {w['others']['items']} 件は {w['others']['agreeMajority']} 件一致。",
        ]
    runs = range(1, int(m["runs"]) + 1)
    out += [
        "",
        "## Each item / 各項目",
        "",
        "| Item / 項目 | Label / ラベル | stage | " + " | ".join(f"Run {i} / {i} 回目" for i in runs) + " |",
        "|---|---|---|" + "---|" * len(runs),
    ]
    for x in rep["items"]:
        lab = x["label"]
        mark = "pass" if lab["verdict"] == "pass" else _rules("fail", lab["failedRules"])
        cells = " | ".join(_cell(r) for r in x["runs"])
        out.append(f"| {x['id']} | {mark} | {lab.get('stage', '')} | {cells} |")
    return "\n".join(out) + "\n"


def write_report(out: Path, rep: Json) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "report.md").write_text(markdown(rep), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
