"""Finite spoiler evaluation through the production Live transport and brief.

Run from the root Python environment, with spikes/backend on PYTHONPATH and the
spike dependencies installed. No deployment, stored audio or credential output.
The fixture is the canonical sequence through each probe's `after`, not a claim
that a simulated playthrough reached it. Both Live and judges use that same state.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from pathlib import Path

from zoujin_backend.gateway import brief
from zoujin_backend.models.gemini_live import GeminiLive, real_connect
from zoujin_backend.narrator.view import persona, situation, state_view
from zoujin_backend.voice.models import LIVE_MODEL
from zoujin_backend.world import Book
from zoujin_llm import Ledger
from zoujin_worldsim import OCCURRED, apply, initial_state, knows

from . import claude_judge
from . import s3_spoiler as old

REPO = Path(__file__).resolve().parents[3]
ITEM = "deferred-spoiler-runtime"


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def canonical_state(world, scenario):
    state = initial_state(world.w, "role.traveler")
    occurred = [b for b in world.w["beats"] if b["order"] <= world.rank(scenario["after"])]
    for b in sorted(occurred, key=lambda b: (b["window"]["canonical"], b["order"])):
        effects = [{"op": "relocate", "character": p, "place": b["place"]} for p in b["participants"]]
        effects += [{"op": "beat", "beat": b["id"], "to": "happened"}, *b["outcomes"]]
        state = apply(
            world.w, state, {"origin": "schedule", "type": "beat", "t": b["window"]["canonical"], "effects": effects}
        )
    state["t"] = world.t(scenario["after"])
    # Probe fixtures specify a conversation location independently of the canonical itinerary.
    state["locations"][scenario["character"]] = scenario["place"]
    state["vars"]["var.player.location"] = scenario["place"]
    return state


def context(book, state, who):
    p = persona(book, state, who)
    s = situation(book, state, who, state_view(book, state))
    known = {f["id"] for f in book.world["facts"] if knows(book.world, state, who, f["id"])}

    def occurred(ref):
        return ref == "pre" or state["beats"].get(ref) in OCCURRED

    future = [f"{b['id']} {b['title']}：{b['summary']}" for b in book.world["beats"] if not occurred(b["id"])]
    future += [f"{f['id']}：{f['statement']}" for f in book.world["facts"] if not occurred(f["trueFrom"])]
    lived = [
        line.removeprefix("これまでに見聞きしたこと：")
        for line in brief.situation_facts(book, state, who)
        if line.startswith("これまでに見聞きしたこと：")
    ]
    return {
        "name": p["name"],
        "when": s["time"],
        "place": book.places[s["place"]]["name"],
        "now": [
            p.get("summary", ""),
            *p["traits"],
            *p["goals"],
            *[f"口ぶりの例：{line}" for line in p.get("speech", {}).get("sampleLines", [])[:4]],
        ],
        "known": [f"{f['id']}：{f['statement']}" for f in book.world["facts"] if f["id"] in known],
        "knownIds": sorted(known),
        "lived": lived,
        "unknown_now": [
            f"{f['id']}：{f['statement']}"
            for f in book.world["facts"]
            if occurred(f["trueFrom"]) and f["id"] not in known
        ],
        "future": future,
    }


def judge_prompt(ctx, after, question, reply, audit=False):
    vals = {
        k: "\n".join(f"- {v}" for v in ctx[k]) or "- (none)" for k in ("now", "known", "lived", "unknown_now", "future")
    }
    system = (old.AUDIT_SYSTEM if audit else old.JUDGE_SYSTEM).format(
        **vals, **{k: ctx[k] for k in ("name", "when", "place")}, after=after
    )
    user = (old.AUDIT_USER if audit else old.JUDGE_USER).format(question=question, reply=reply or "(no speech)")
    return system, user


def prepare(args):
    world = old.World(REPO / "worlds/hashire-merosu/1.0.0-draft/world.json")
    book = Book(world.w["book"]["id"], world.w)
    scenarios, _ = old.load_specs(args.spec.split(","), world)
    selected = old.flagged_questions(Path(args.only_flagged)) if args.only_flagged else None
    if getattr(args, "questions_file", None):
        if selected is not None:
            raise SystemExit("Choose either questions-file or only-flagged")
        selected = {(c["scenario"], c["question"]) for c in json.loads(args.questions_file.read_text())}
    if selected is None and getattr(args, "replies_from", None):
        selected = {(c["scenario"], c["question"]) for c in json.loads((args.replies_from / "cases.json").read_text())}
    cases = []
    for sc in scenarios:
        state = canonical_state(world, sc)
        prompt = brief.build(book, state, sc["character"]).system
        ctx = context(book, state, sc["character"])
        assert ctx["knownIds"] == sorted(situation(book, state, sc["character"], state_view(book, state))["knows"])
        for item in sc["items"]:
            if selected is not None and (sc["id"], item["q"]) not in selected:
                continue
            for rep in range(1, args.repeat + 1):
                cases.append(
                    {
                        "scenario": sc["id"],
                        "character": sc["character"],
                        "after": sc["after"],
                        "question": item["q"],
                        "style": item["style"],
                        "targets": item["targets"],
                        "rep": rep,
                        "system": prompt,
                        "context": ctx,
                        "stateHash": digest(state),
                        "briefHash": digest(prompt),
                    }
                )
    if selected is not None and selected - {(c["scenario"], c["question"]) for c in cases}:
        raise SystemExit("Some selected questions do not exist in the requested specs; refusing partial coverage")
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("No matching cases; refusing an empty coverage run")
    return world, cases


def saved_replies(cases, source_dir):
    """Keep actual generation prompts even when a later runtime fix changes brief.build."""

    def key(c):
        return c["scenario"], c["question"], c["rep"]

    source_cases = {key(c): c for c in json.loads((source_dir / "cases.json").read_text())}
    replies = {
        key(r): r for r in map(json.loads, (source_dir / "results.jsonl").read_text().splitlines()) if r.get("reply")
    }
    for c in cases:
        original, reply = source_cases.get(key(c)), replies.get(key(c))
        if not original or not reply or original["stateHash"] != c["stateHash"]:
            raise SystemExit("Source replies missing or generation state changed; refusing mixed evidence")
        if reply.get("failureStage") == "live":
            raise SystemExit("Source generation failed; refusing to turn a partial reply into completed evidence")
        if original["briefHash"] != digest(original["system"]) or any(
            reply.get(k) != original[k] for k in ("stateHash", "briefHash")
        ):
            raise SystemExit("Source reply and stored generation prompt disagree")
        # The state and world are unchanged. The current judge gains complete persona
        # examples, but the supplied Live prompt remains exactly the one that generated it.
        c["system"], c["briefHash"] = original["system"], original["briefHash"]
    return replies


async def run(args):
    world, cases = prepare(args)
    reused = saved_replies(cases, args.replies_from) if args.replies_from else {}
    execution = {
        "liveModel": LIVE_MODEL,
        "judgeModel": claude_judge.TAG,
        "judgeModelIdHash": digest(os.environ.get("ZJ_CLAUDE_SONNET", "unset")),
        "liveThinking": os.environ.get("ZJ_LIVE_THINKING") or None,
        "transcribeHints": os.environ.get("ZJ_LIVE_TRANSCRIBE_HINTS", "1") != "0",
        "judgePromptHash": digest(
            [old.JUDGE_SYSTEM, old.JUDGE_USER, old.JUDGE_SCHEMA, old.AUDIT_SYSTEM, old.AUDIT_USER, old.AUDIT_SCHEMA]
        ),
        "sources": {
            str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                Path(__file__),
                Path(old.__file__),
                Path(claude_judge.__file__),
                Path(brief.__file__),
                REPO / "services/backend/src/zoujin_backend/models/gemini_live.py",
                REPO / "services/backend/src/zoujin_backend/narrator/view.py",
                REPO / "services/backend/voice/hashire-merosu.json",
            )
        },
    }
    meta = {
        "schema": 2,
        "transport": "production GeminiLive.open/respond",
        "fixture": "fixed-moment condition probes; canonical beat effects, role.traveler; no act navigation or DB",
        "worldHash": digest(world.w),
        "briefVersion": brief.version(),
        "judgeRules": old.JUDGE_RULES,
        "caseHash": digest(cases),
        "execution": execution,
        "executionHash": digest(execution),
        "planned": len(cases),
        "uniqueQuestions": len({(c["scenario"], c["question"]) for c in cases}),
        "concurrency": args.concurrency,
        "item": ITEM,
        "maxItemUsd": args.max_item_usd,
        "estimatedUsd": round(len(cases) * 0.04, 2),
        "maxTotalUsd": args.max_total_usd,
        "calibration": "not performed; existing s092.3 judges only; flags need human review",
    }
    if args.replies_from:
        source = args.replies_from / "results.jsonl"
        generation_meta = json.loads((args.replies_from / "metadata.json").read_text())
        if generation_meta["worldHash"] != meta["worldHash"]:
            raise SystemExit("Source world changed; refusing mixed evidence")
        meta["briefVersion"] = generation_meta["briefVersion"]
        meta["repliesFrom"] = args.replies_from.name
        meta["sourceRepliesHash"] = hashlib.sha256(source.read_bytes()).hexdigest()
        meta["generationMetadataHash"] = hashlib.sha256((args.replies_from / "metadata.json").read_bytes()).hexdigest()
        meta["generationSourceFingerprint"] = (
            "See source run metadata; missing fingerprints are unknown, not reconstructed"
        )
    print(json.dumps(meta, ensure_ascii=False), flush=True)
    if not args.confirm:
        return
    args.out.mkdir(parents=True, exist_ok=True)
    mpath = args.out / "metadata.json"
    if mpath.exists():
        previous = json.loads(mpath.read_text())
        if any(
            previous.get(k) != meta.get(k)
            for k in ("caseHash", "executionHash", "sourceRepliesHash", "generationMetadataHash")
        ):
            raise SystemExit("Refusing resume: cases, state, models, prompts or code changed; use another directory")
    mpath.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    (args.out / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2))
    dest = args.out / "results.jsonl"
    rows = [json.loads(s) for s in dest.read_text().splitlines()] if dest.exists() else []

    def key(c):
        return c["scenario"], c["question"], c["rep"]

    latest = {key(r): r for r in rows}
    previous_lines = {key(r): i for i, r in enumerate(rows, 1)}

    # A failed generation is evidence, not permission to draw a replacement sample.
    def generation_failed(r):
        return not r.get("complete") and (r.get("failureStage") == "live" or not r.get("reply"))

    done = {k for k, r in latest.items() if r.get("complete") or generation_failed(r)}
    cj = claude_judge.ClaudeJudge(max_total_usd=args.max_total_usd, max_item_usd=args.max_item_usd)
    ledger_path = Path(os.environ["ZJ_CLAUDE_LEDGER"]).expanduser()
    cj.ledger = Ledger(ledger_path, "claude", args.max_total_usd, args.max_item_usd, ITEM, "eval")
    live_ledger = Ledger(ledger_path, "google", args.max_total_usd, args.max_item_usd, ITEM, "eval")
    live = None
    if not args.replies_from and any(key(c) not in latest for c in cases):
        connect, model_path = real_connect(os.environ)
        voices_doc = json.loads((REPO / "services/backend/voice/hashire-merosu.json").read_text())
        voices = {cid: r["voice"] for cid, r in voices_doc["speakers"].items()}
        live = GeminiLive(
            model_path=model_path,
            voices=voices,
            connect=connect,
            thinking=execution["liveThinking"],
            hints=execution["transcribeHints"],
        )
    sem = asyncio.Semaphore(args.concurrency)
    stop = asyncio.Event()

    async def one(c):
        async with sem:
            if getattr(args, "stop_file", None) and args.stop_file.exists():
                stop.set()
            if stop.is_set() or key(c) in done:
                return
            row = {k: v for k, v in c.items() if k not in ("context", "system")}
            row["condition"] = "runtime"
            row["keyword_hits"] = []
            row["callAttempts"] = []
            row["requestId"] = digest([meta["caseHash"], c["scenario"], c["question"], c["rep"]])
            row["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            began = time.perf_counter()
            stage = "live"
            try:
                previous = latest.get(key(c))
                if previous or reused:
                    source = previous or reused[key(c)]
                    text = source["reply"]
                    row.update(
                        reply=text,
                        liveCostUsd=0,
                        replyReusedFrom=source.get("replyReusedFrom", "same run")
                        if previous
                        else args.replies_from.name,
                        originalLiveCostUsd=source.get("originalLiveCostUsd", source.get("liveCostUsd")),
                        originalUsageMissing=source.get(
                            "originalUsageMissing", source.get("usageMissing", "unrecorded")
                        ),
                        originalCostBasis=source.get("originalCostBasis", source.get("costBasis", "unrecorded")),
                    )
                    if previous:
                        row["resumedFromRow"] = previous_lines[key(c)]
                        # Retain completed grading stages; append only the missing judgments.
                        for field in (*old.JUDGE_SCHEMA["properties"], "claims2", "leak2"):
                            if field in previous:
                                row[field] = previous[field]
                else:
                    text, cost, usage = "", 0.01, {}
                    live_started = time.perf_counter()
                    live_attempt = {"stage": "live", "attempt": 1}
                    try:
                        with live_ledger.timed(kind="spoiler-live", model=LIVE_MODEL, estimate=0.02) as bill:
                            async with asyncio.timeout(60):
                                session = await live.open(c["character"], system=c["system"])
                                try:
                                    async for e in session.respond(c["question"]):
                                        if e.kind == "output_final":
                                            text = e.text or ""
                                        elif e.kind == "usage":
                                            cost, usage = e.usd, e.usage or {}
                                finally:
                                    await session.close()
                            bill.done(usage, cost, ok=bool(text))
                        live_attempt["status"] = "ok" if text else "bad-output"
                    except Exception as exc:
                        live_attempt.update(
                            status="timeout" if isinstance(exc, TimeoutError) else "error",
                            errorType=type(exc).__name__,
                        )
                        raise
                    finally:
                        live_attempt["ms"] = round((time.perf_counter() - live_started) * 1000)
                        row["callAttempts"].append(live_attempt)
                        # Preserve received text even if stream completion/close fails.
                        row.update(
                            reply=text,
                            liveCostUsd=cost
                            if live_attempt.get("status") in ("ok", "bad-output")
                            else (0.02 if live_attempt.get("status") == "timeout" else 0),
                            usageMissing=not bool(usage),
                            costBasis=("usage" if usage else "conservative estimate")
                            if live_attempt.get("status") in ("ok", "bad-output")
                            else "ledger failure accounting; provider cost unknown",
                        )
                if not text:
                    raise RuntimeError("empty transcript: ungraded, not a pass")
                for audit in (False, True):
                    stage = "audit" if audit else "judge"
                    if (audit and "claims2" in row and "leak2" in row) or (
                        not audit and all(field in row for field in old.JUDGE_SCHEMA["required"])
                    ):
                        continue
                    system, user = judge_prompt(c["context"], c["after"], c["question"], text, audit)
                    verdict = await cj(
                        "audit" if audit else "judge",
                        system,
                        user,
                        old.AUDIT_SCHEMA if audit else old.JUDGE_SCHEMA,
                        attempts=row["callAttempts"],
                    )
                    if audit:
                        row.update(claims2=verdict["claims"], leak2=old.audit_leak(verdict["claims"]))
                    else:
                        row.update(verdict)
                row.update(complete=True, disagree=old.disagree(row, row["leak2"]))
            except Exception as e:
                # Never emit provider exception bodies, which may include credential-bearing addresses.
                row.update(complete=False, errorType=type(e).__name__, failureStage=stage)
                stop.set()
            row["seconds"] = round(time.perf_counter() - began, 2)
            rows.append(row)
            with dest.open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(
                f"{len(rows)}/{len(cases)} {c['scenario']} complete={row['complete']} "
                f"flagged={old.any_leak(row) if row['complete'] else '?'}",
                flush=True,
            )

    await asyncio.gather(*(one(c) for c in cases))
    case_keys = {key(c) for c in cases}
    latest = {key(r): r for r in rows if key(r) in case_keys}
    complete = [
        dict(keyword_hits=[], **{k: v for k, v in r.items() if k != "keyword_hits"})
        for r in latest.values()
        if r.get("complete")
    ]
    flags = [r for r in complete if old.any_leak(r)]
    failed = [r for r in latest.values() if not r.get("complete")]
    automated = old.summarize(complete, ["runtime"])
    # Content rates use fully graded replies; errors cover all attempted cases.
    automated["runtime"]["errors"] = len(failed)
    summary = {
        **meta,
        "completed": len(complete),
        "missing": len(cases) - len(complete),
        "generated": sum(bool(r.get("reply")) for r in latest.values()),
        "generationFailed": sum(generation_failed(r) for r in failed),
        "judgeFailed": sum(not generation_failed(r) for r in failed),
        "notStarted": len(case_keys - latest.keys()),
        "failedAttempts": sum(not r.get("complete") for r in rows if key(r) in case_keys),
        "failureCountsBasis": "latest attempt per case; failedAttempts counts all historical failed case rows",
        "flaggedReplies": len(flags),
        "flaggedQuestions": len({(r["scenario"], r["question"]) for r in flags}),
        "outOfRole": sum(r["out_of_role"] for r in complete),
        "stopRequested": bool(getattr(args, "stop_file", None) and args.stop_file.exists()),
        "disagreements": sum(r["disagree"] for r in complete),
        "automatedSummary": automated,
        "notReleasePass": True,
    }
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    (args.out / "flagged.json").write_text(json.dumps(flags, ensure_ascii=False, indent=2))
    review = [
        r
        for r in complete
        if old.any_leak(r)
        or r["disagree"]
        or r["leak"] != "none"
        or r["leak2"] != "none"
        or r["out_of_role"]
        or not r["japanese_only"]
    ]
    (args.out / "review-candidates.json").write_text(json.dumps(review, ensure_ascii=False, indent=2))
    (args.out / "read-all.md").write_text(
        "\n\n".join(
            f"## {i}. {r['scenario']} / {r['rep']}\n\n"
            f"Status: {'complete' if r.get('complete') else 'FAILED / ' + r.get('failureStage', 'ungraded')}\n\n"
            f"Q: {r['question']}\n\nA: {r.get('reply', '[no reply received]')}"
            for i, r in enumerate(latest.values(), 1)
        )
    )
    print(
        json.dumps({k: summary[k] for k in ("planned", "completed", "missing", "flaggedReplies", "outOfRole")}),
        flush=True,
    )
    if len(complete) != len(cases):
        raise SystemExit(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--spec", default="probes,probes2,scenarios")
    ap.add_argument("--only-flagged")
    ap.add_argument(
        "--questions-file", type=Path, help="Explicit scenario/question pairs for a finite fresh regression"
    )
    ap.add_argument("--replies-from", type=Path, help="Rejudge saved replies with current context; no Live calls")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--concurrency", type=int, default=3, choices=range(1, 5))
    ap.add_argument("--max-item-usd", type=float, default=100)
    ap.add_argument("--max-total-usd", type=float, default=10000)
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--stop-file", type=Path, help="Finish active calls, then stop dispatch when this file exists")
    args = ap.parse_args()
    if args.repeat < 1 or args.limit is not None and args.limit < 1:
        ap.error("positive repeat/limit required")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
