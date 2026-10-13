"""Finite real-model batches: one subprocess per game, evidence kept game by game, resumable, and an interrupted game
is never replayed automatically.

python -m zoujin_evals.batch --plan simulations --seeds 2 … estimates the price first; only --confirm makes calls.
The four-act text stand-in eval is not the Live voice acceptance check; the judge, not yet calibrated, is not run.

有限の実モデルバッチ：1 局に 1 つのサブプロセス、局ごとに証拠を残し、再開でき、中断した局を自動で再実行することは
決してない。

python -m zoujin_evals.batch --plan simulations --seeds 2 … はまず見積もる。--confirm があって初めて呼び出す。
四幕のテキスト代役による評価は Live 音声の受け入れ確認ではない。まだキャリブレーションしていない judge は実行しない。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

from zoujin_llm import Stop
from zoujin_llm.errors import BatchHalted

from . import live, report
from .api import load_backend
from .cases import load_cases
from .checks import WorldIndex
from .cli import PRICES, WORLD, players
from .player import MAX_STEPS
from .runner import Options, run_cases

REPO = Path(__file__).resolve().parents[3]


def plan(kind: str, seeds: int, *, repo: Path = REPO) -> list[dict[str, Any]]:
    if not 1 <= seeds <= 20:
        raise ValueError(
            "seeds must be 1–20 (formal denominator: 10 personas × 20 seeds)"
            " / seeds は 1–20 でなければならない（正式な分母：10 ペルソナ × 20 seed）"
        )
    first = load_cases(repo / "evals/seeds")
    if kind == "simulations":
        original = [c for c in first if c["id"] in {f"E7-{n:03}" for n in range(1, 11)}]
        if len(original) != 10 or len({c["setup"]["persona"] for c in original}) != 10:
            raise ValueError(
                "The planned 10 personas are missing or duplicated / 予定の 10 種のペルソナが欠けているか重複している"
            )
        return [
            {**c, "id": f"{c['id']}-seed-{seed:02}", "runs": 1, "setup": {**c["setup"], "seed": seed}}
            for seed in range(1, seeds + 1)
            for c in original
        ]
    cases = first + [c for act in range(2, 5) for c in load_cases(repo / f"evals/acts/act{act}")]
    return [{**c, "id": f"{c['id']}-run-{i:02}", "runs": 1} for c in cases for i in range(1, c.get("runs", 5) + 1)]


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def source_hash(repo: Path = REPO) -> str:
    """Bind the evidence to content rather than to the git SHA: commits from other threads do not invalidate the same
    content.

    証拠を git SHA ではなく内容に結び付ける：他のスレッドのコミットで同じ内容が無効にならない。
    """
    roots = ("evals/src", "services/backend/src", "packages/worldsim/src", "packages/llm/src", "worlds", "prompts")
    h = hashlib.sha256()
    for root in roots:
        for path in sorted((repo / root).rglob("*")):
            if path.is_file() and path.suffix in {".py", ".json", ".jsonl", ".txt"}:
                h.update(str(path.relative_to(repo)).encode())
                h.update(path.read_bytes())
    # Persona text is model input, including the act-specific evaluation sets.
    for path in [repo / "evals/personas.json", *sorted((repo / "evals/acts").glob("*/personas.json"))]:
        if path.is_file():
            h.update(str(path.relative_to(repo)).encode())
            h.update(path.read_bytes())
    # Book.Scene.read uses this semantic projection for player movement/observations.
    # Render-only bytes, bake hashes and lighting do not enter text evaluations.
    for path in sorted((repo / "assets/scenes").glob("*/scene.json")):
        doc = json.loads(path.read_text())
        layout = {
            "sceneId": doc["sceneId"],
            "defaultPlace": doc["defaultPlace"],
            "places": [p["id"] for p in doc.get("places", [])],
            "spots": [(k, v["place"], v.get("auto") is False) for k, v in doc.get("spots", {}).items()],
            "exits": [(e["place"], e["spot"]) for e in doc.get("exits", [])],
            "startSpots": doc.get("startSpots", {}),
        }
        h.update(str(path.relative_to(repo)).encode())
        h.update(json.dumps(layout, sort_keys=True).encode())
    return h.hexdigest()


def runtime_config() -> dict[str, Any]:
    from dataclasses import asdict

    from zoujin_backend.config import TEXT, text_spec
    from zoujin_llm import model_tag

    ids = {key: os.environ.get(key, "") for key in ("ZJ_PLAYER_MODEL", "ZJ_CLAUDE_SONNET", "ZJ_CLAUDE_HAIKU")}
    return {
        "models": {key: {"tag": model_tag(value), "idHash": digest(value)} for key, value in ids.items()},
        "textSpecs": {kind: asdict(text_spec(kind)) for kind in TEXT},
        "release": os.environ.get("ZJ_RELEASE", "1"),
        "vertexLocation": os.environ.get("ZJ_VERTEX_LOCATION", ""),
        "armorTemplateHash": digest(os.environ.get("ZJ_ARMOR_TEMPLATE", "")),
    }


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Workers can trigger a halt at the same time; the temporary file is exclusive and replacing the target stays
    # atomic.
    # 各 worker が同時に halt を起こしうる。一時ファイルは排他的で、対象の置き換えはアトミックに保たれる。
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=f".{path.name}.", delete=False) as f:
        tmp = Path(f.name)
        f.write(json.dumps(value, ensure_ascii=False, indent=1) + "\n")
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def strict_result(case: Mapping[str, Any], result: Mapping[str, Any], ledger: list[dict[str, Any]]) -> list[str]:
    reasons = []
    runs = result.get("results", [])
    if result.get("skip") or len(runs) != 1:
        return ["missing-run"]
    run = runs[0]
    # Judge-only cases still run the real steps, but this round must not pretend that judging is done.
    # judge だけのケースも実際のステップは実行するが、今回は採点済みのふりをしてはならない。
    judge_only = "judge" in case.get("expect", {}) and not case["expect"].get("deterministic")
    if run.get("status") != "pass" and not (judge_only and run.get("skip", {}).get("code") == "needs-live-model"):
        reasons.append("failed-or-skipped-check")
    if "persona" in case["setup"]:
        sim = run.get("sim", {})
        if sim.get("status") != "ended" or sim.get("stopped") or not sim.get("ending", {}).get("signature"):
            reasons.append("incomplete-ending")
        diagnostics = sim.get("player", {})
        if diagnostics.get("observationVersion") != 3:
            reasons.append("unverified-public-observation")
        if diagnostics.get("freshCalls") != sim.get("steps"):
            reasons.append("player-call-count-mismatch")
        if diagnostics.get("bad", 0) or diagnostics.get("replayHits", 0):
            reasons.append("player-fallback-or-replay")
        if not any(r.get("kind") == "player" and r.get("costUsd", 0) > 0 for r in ledger):
            reasons.append("no-real-player-call")
    return reasons


def simulation_quality(sim: Mapping[str, Any]) -> dict[str, Any]:
    """Keep sample validity, real fallbacks and request retries apart; old records lacking diagnostics are explicitly
    unknown.

    サンプルの有効性、実際のフォールバック、リクエストのリトライを分ける。診断のない旧記録は明示的に unknown とする。
    """
    player = sim.get("player", {})
    valid = (
        sim.get("status") == "ended"
        and not sim.get("stopped")
        and bool(sim.get("ending", {}).get("signature"))
        and player.get("freshCalls") == sim.get("steps")
        and player.get("replayHits") == 0
        and player.get("bad") == 0
        and player.get("observationVersion") == 3
    )
    backend = sim.get("backend", {})
    calls = backend.get("pipelineCalls", [])
    recovered = sum(c.get("status") == "ok" and len(c.get("attempts", [])) > 1 for c in calls)
    metrics = backend.get("metrics", {})
    known_degraded = (
        backend.get("budgetTier") == "degraded"
        or backend.get("characterTextMissing", 0) > 0
        or any(metrics.get(k) for k in ("turns_timed_out", "ending_template", "memories_failed", "safety_unscreened"))
        or any(c.get("status") == "failed" for c in calls)
    )
    dialogue = sim.get("dialogue")
    if dialogue:
        valid = valid and dialogue.get("aligned", False) and not dialogue.get("inconsistent", 0)
        known_degraded = known_degraded or dialogue.get("missing", 0) > 0
    # The observer does not cover the fixed fallbacks after output sanitising, so zero known failures cannot certify
    # zero degradation.
    # 観測器は出力内容のサニタイズ後の固定フォールバックをカバーしていないので、既知の失敗が 0 でも劣化が 0 とは
    # 認定できない。
    return {
        "valid": bool(valid),
        "degradation": "known-degraded" if known_degraded else "unknown",
        "recovered": recovered,
    }


def worker(path: Path) -> int:
    job = json.loads(path.read_text())
    case = job["case"]
    out = path.parent
    os.environ["ZJ_EVAL_BATCH_HALT"] = str((out.parent.parent / "halted.json").resolve())
    if source_hash() != job["sourceHash"] or runtime_config() != job["runtimeConfig"]:
        save(
            out / "result.json",
            {
                "case": case,
                "status": "stopped",
                "issues": ["source-or-runtime-changed"],
                "costUsd": {p: 0 for p in live.PROVIDERS},
            },
        )
        return 2
    os.environ.update(live.backend_env(item=case["id"], max_item_usd=job["itemCap"], caps=job["caps"]))
    os.environ.update(ZJ_WORLD=job["world"], ZJ_LEDGER=str(out / "ledger.jsonl"))
    args = argparse.Namespace(
        player="claude",
        mode="live",
        player_model=os.environ["ZJ_PLAYER_MODEL"],
        player_replays=out / "player-replays",
        out=out,
        max_claude_usd=job["caps"]["claude"],
        max_item_usd=job["itemCap"],
        item=case["id"],
    )
    opts = Options(
        deterministic_only=True,
        timeout_s=job["timeout"],
        timeout_retries=0,
        max_steps=job.get("maxSteps", MAX_STEPS),
        player=players(args),
        progress=lambda message: print(message, flush=True),
    )
    record: dict[str, Any] = {"case": case, "sourceHash": job["sourceHash"], "status": "running"}
    try:
        world = WorldIndex(json.loads(Path(job["world"]).read_text()))
        record["result"] = run_cases(load_backend(), [case], world, opts)[0]
        record["status"] = "completed"
    except Stop as exc:
        record.update(status="stopped", stopType=type(exc).__name__, stopDiagnostics=getattr(exc, "diagnostics", {}))
        if not isinstance(exc, BatchHalted):
            save(out.parent.parent / "halted.json", {"caseId": case["id"], "stopType": type(exc).__name__})
    except BaseException as exc:
        record.update(status="interrupted", stopType=type(exc).__name__)
    ledger_path = out / "ledger.jsonl"
    rows = [json.loads(s) for s in ledger_path.read_text().splitlines()] if ledger_path.exists() else []
    record["costUsd"] = {p: sum(float(r["costUsd"]) for r in rows if r.get("provider") == p) for p in live.PROVIDERS}
    record["calls"] = dict(Counter(f"{r.get('provider')}:{r.get('model')}:{r.get('status', 'ok')}" for r in rows))
    record["issues"] = strict_result(case, record["result"], rows) if "result" in record else [record["status"]]
    save(out / "result.json", record)
    return int(bool(record["issues"]))


def summarize(out: Path, jobs: list[dict[str, Any]], metadata: Mapping[str, Any]) -> dict[str, Any]:
    records = []
    for path in sorted((out / "units").glob("*/result.json")):
        record = json.loads(path.read_text())
        if "result" in record and "case" in record:
            ledger_path = path.parent / "ledger.jsonl"
            rows = [json.loads(line) for line in ledger_path.read_text().splitlines()] if ledger_path.exists() else []
            record["originalIssues"] = record.get("issues", [])
            record["issues"] = strict_result(record["case"], record["result"], rows)
        records.append(record)
    # Sum the ledgers directly, including half games that are running, stopped by the budget, or interrupted without a
    # result.
    # 台帳を直接合計する。実行中、予算で停止、中断されて result のない途中の局も含む。
    ledger = [json.loads(line) for p in (out / "units").glob("*/ledger.jsonl") for line in p.read_text().splitlines()]
    results = [r["result"] for r in records if "result" in r]
    summary = {
        **metadata,
        "measurementVersion": 2,
        "planned": len(jobs),
        "recorded": len(records),
        "completed": sum(r["status"] == "completed" for r in records),
        "clean": sum(not r["issues"] for r in records),
        "issues": dict(Counter(issue for r in records for issue in r["issues"])),
        "costUsd": {p: sum(r["costUsd"] for r in ledger if r.get("provider") == p) for p in live.PROVIDERS},
        "costBasis": "usage-priced estimate; timeout reservations may overestimate; not provider invoice",
        "providerStatuses": dict(Counter(r.get("status", "ok") for r in ledger)),
        "judge": "deferred",
        "liveVoice": "not-tested",
        "units": records,
    }
    simulations = [r["sim"] for c in results for r in c.get("results", []) if "sim" in r]
    ended = [s for s in simulations if s.get("status") == "ended" and s.get("ending", {}).get("signature")]
    outcomes = Counter(s["ending"]["outcome"] for s in ended)
    signatures = {digest(s["ending"]["signature"]) for s in ended}
    measurement = [simulation_quality(s) for s in simulations]
    summary["measurementCompleteness"] = {
        "measured": len(measurement),
        "valid": sum(m["valid"] for m in measurement),
        "invalid": sum(not m["valid"] for m in measurement),
        "unmeasured": len(jobs) - len(measurement),
    }
    summary["productDegradation"] = dict(Counter(m["degradation"] for m in measurement))
    summary["requestRetries"] = {
        "scope": "observed pipeline logical calls; other provider retries unknown",
        "observedGames": sum("backend" in s for s in simulations),
        "recovered": sum(m["recovered"] for m in measurement),
        "rawFailures": sum(r.get("status") in {"error", "timeout", "bad-output"} for r in ledger),
    }
    complete = (
        metadata.get("plan") == "simulations"
        and len(jobs) == len(ended) == 200
        and all(m["valid"] for m in measurement)
    )
    summary["diversity"] = {
        "denominator": len(jobs),
        "endedWithSignature": len(ended),
        "outcomes": dict(outcomes),
        "signatures": len(signatures),
        "largestShare": max(outcomes.values(), default=0) / len(jobs),
        "gateMet": (len(outcomes) == 5 and len(signatures) >= 8 and max(outcomes.values()) <= 120)
        if complete
        else None,
        "gateReason": "complete-200" if complete else "requires-200-valid-completed-simulations",
    }
    save(out / ("summary.json" if metadata.get("measurementVersion") == 2 else "summary-v2.json"), summary)
    rep = report.build(results, {"mode": "live", "deterministicOnly": True, "cases": len(jobs)})
    suffix = "" if metadata.get("measurementVersion") == 2 else "-v2"
    save(out / f"report{suffix}.json", rep)
    (out / f"report{suffix}.md").write_text(report.markdown(rep))
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--plan", choices=("simulations", "four-act"), default="simulations")
    parser.add_argument("--seeds", type=int, default=2)
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    parser.add_argument(
        "--resume-after-stop",
        action="store_true",
        help="Explicitly resume after a rate-limit stop; start only samples not yet started, never rerun failed games"
        " / レート制限の停止点から明示的に再開する。未開始のサンプルだけを開始し、失敗した局は再実行しない",
    )
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--world", type=Path, default=WORLD)
    parser.add_argument("--max-item-usd", type=float, default=10)
    parser.add_argument("--max-google-usd", type=float, default=100)
    parser.add_argument("--max-claude-usd", type=float, default=300)
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Keep running the next case after a failed check; the budget or rate limits still stop"
        " / チェックが不合格でも次のケースを実行する。予算やレート制限では引き続き停止する",
    )
    args = parser.parse_args(argv)
    if args.worker:
        return worker(args.worker)
    if args.out is None:
        parser.error(
            "--out must be given explicitly (private evidence directory)"
            " / --out を明示する必要がある（非公開の証拠ディレクトリ）"
        )
    if min(args.max_item_usd, args.max_google_usd, args.max_claude_usd, args.timeout, args.max_steps) <= 0:
        parser.error("Budgets and time limits must be positive / 予算と時間制限は正の数でなければならない")
    cases = plan(args.plan, args.seeds)
    caps = {"google": args.max_google_usd, "claude": args.max_claude_usd}
    code, message = live.gate(
        os.environ,
        max_item_usd=args.max_item_usd,
        caps=caps,
        confirm=args.confirm,
        cases=cases,
        prices=live.Prices.from_json(json.loads(PRICES.read_text())),
        deterministic_only=True,
        argv=list(argv or sys.argv[1:]),
        item="finite-batch",
        player_model=os.environ.get("ZJ_PLAYER_MODEL"),
    )
    print(message.replace("uv run zoujin-eval", "uv run python -m zoujin_evals.batch"))
    if code is not None:
        print(
            "Plan only; nothing has run yet. To run or resume, use the same batch arguments with --confirm."
            " / 計画のみ。まだ実行していない。実行・再開には同じバッチ引数と --confirm を使う。"
            if code == 0
            else "Not run. / 実行していない。"
        )
        return code
    metadata = {
        "plan": args.plan,
        "measurementVersion": 2,
        "maxSteps": args.max_steps,
        "sourceHash": source_hash(),
        "casesHash": digest(cases),
        "worldHash": hashlib.sha256(args.world.read_bytes()).hexdigest(),
        "runtimeConfig": runtime_config(),
    }
    manifest = args.out / "manifest.json"
    if manifest.exists() and json.loads(manifest.read_text()) != metadata:
        raise SystemExit(
            "The source, world or cases have changed: an old batch cannot take new results, use a new directory."
            " / ソース、世界、ケースのいずれかが変わった：旧バッチに新しい結果を混ぜられないので、"
            "新しいディレクトリを使う。"
        )
    halted = args.out / "halted.json"
    if halted.exists() and not args.resume_after_stop:
        raise SystemExit(
            "The last run stopped on a rate limit or the budget; check the cause first, then explicitly pass"
            " --resume-after-stop. Old failed games are not rerun. / 前回はレート制限か予算で停止した。まず原因を"
            "確認し、それから明示的に --resume-after-stop を付ける。失敗した旧局は再実行しない。"
        )
    if halted.exists():
        history = args.out / "halt-history"
        history.mkdir(exist_ok=True)
        save(history / f"{len(list(history.glob('*.json'))) + 1:04}.json", json.loads(halted.read_text()))
        halted.unlink()
    save(manifest, metadata)
    pending = []
    for case in cases:
        directory = args.out / "units" / case["id"]
        if (directory / "result.json").exists():
            continue
        job_path = directory / "job.json"
        if (directory / "started.json").exists():
            raise SystemExit(
                f"{case['id']} was interrupted last time and has no result; automatic repeat payment is forbidden,"
                f" check that process and the database first. / {case['id']} は前回中断され結果がない。自動で"
                "再度課金することは禁止。まずそのプロセスとデータベースを確認する。"
            )
        save(
            job_path,
            {
                "case": case,
                **metadata,
                "world": str(args.world.resolve()),
                "itemCap": args.max_item_usd,
                "caps": caps,
                "timeout": args.timeout,
                "maxSteps": args.max_steps,
            },
        )
        pending.append(job_path)
    stopped = False

    def launch(path: Path) -> int:
        save(path.parent / "started.json", {"pid": os.getpid()})
        with (path.parent / "worker.log").open("w") as log:
            return subprocess.run(
                [sys.executable, "-m", "zoujin_evals.batch", "--worker", str(path)],
                stdout=log,
                stderr=log,
                timeout=args.timeout + 120,
            ).returncode

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        active: dict[Future[int], Path] = {}
        while pending or active:
            summary = summarize(args.out, cases, metadata)
            while pending and len(active) < args.jobs and not stopped:
                if halted.exists():
                    stopped = True
                    break
                # Reserve a whole item's quota for each running worker; concurrency cannot get around the two
                # total ledgers.
                # 実行中の各 worker に項目の枠全体を予約する。並行実行で 2 つの総台帳をすり抜けることはない。
                reserved = args.max_item_usd * (len(active) + 1)
                if any(summary["costUsd"][p] + reserved > caps[p] for p in caps):
                    stopped = True
                    break
                if source_hash() != metadata["sourceHash"]:
                    stopped = True
                    print(
                        "The source changed during the batch; stopping dispatch and keeping the evidence already run."
                        " / バッチ中にソースが変わった。派遣を停止し、実行済みの証拠は保持する。"
                    )
                    break
                path = pending.pop(0)
                active[pool.submit(launch, path)] = path
            if not active:
                break
            done, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in done:
                path = active.pop(future)
                try:
                    rc = future.result()
                except subprocess.TimeoutExpired:
                    rc = 2
                    save(
                        path.parent / "result.json",
                        {
                            "case": json.loads(path.read_text())["case"],
                            "status": "interrupted",
                            "stopType": "WorkerTimeout",
                            "issues": ["worker-timeout"],
                        },
                    )
                    save(halted, {"caseId": path.parent.name, "stopType": "WorkerTimeout"})
                result_path = path.parent / "result.json"
                record = json.loads(result_path.read_text()) if result_path.exists() else {"status": "interrupted"}
                if rc and (not args.keep_going or record["status"] != "completed"):
                    stopped = True
                print(
                    f"{path.parent.name}: {record['status']}; issues={record.get('issues', ['missing-result'])}",
                    flush=True,
                )
            if stopped:
                pending.clear()
    summary = summarize(args.out, cases, metadata)
    return int(summary["clean"] != summary["planned"])


if __name__ == "__main__":
    sys.exit(main())
