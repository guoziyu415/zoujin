"""Finite supplementary spoiler inspection of the production Claude narrate path.

Uses actions.narrate -> Pipeline.call -> ClaudeText; retains raw and delivered text
so fallback responses cannot be counted as model passes. Canonical snapshot probes,
not full gateway/DB playthroughs. Results require human review, no new judge rules.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

from zoujin_backend.config import Settings
from zoujin_backend.ids import IdGen
from zoujin_backend.models.claude import claude_text
from zoujin_backend.models.prompts import PROMPTS
from zoujin_backend.narrator.actions import Decision, Outcome, narrate
from zoujin_backend.narrator.pipeline import Pipeline, Spend
from zoujin_backend.narrator.rules import Checked
from zoujin_backend.schemas import SchemaBook
from zoujin_llm import Ledger
from zoujin_worldsim import knows, spoilers

from . import s3_runtime as runtime
from . import s3_spoiler as old


class Recorded:
    def __init__(self, inner):
        self.inner = inner
        self.mode = inner.mode
        self.calls = []

    def cancelled_cost(self, kind, req):
        return self.inner.cancelled_cost(kind, req)

    async def call(self, kind, req):
        result = await self.inner.call(kind, req)
        self.calls.append({"kind": kind, "request": req, "output": result.output, "usd": result.cost_usd})
        return result


async def run(args):
    world = old.World(runtime.REPO / "worlds/hashire-merosu/1.0.0-draft/world.json")
    book = runtime.Book(world.w["book"]["id"], world.w)
    scenarios, _ = old.load_specs(["probes", "probes2", "scenarios"], world)
    selected = {}
    for s in scenarios:
        selected.setdefault(s["after"], s)
    cases = []
    for after, s in selected.items():
        if args.only_after and after != args.only_after:
            continue
        for kind, target, status in [
            ("wait", None, "done"),
            ("go", "place.castle", "refused"),
            # Without verified candidates production status_of() returns refused.
            ("help", s["character"], "refused"),
        ]:
            cases.append((s, kind, target, status))
    if args.affordance:
        aff = next(a for a in world.w["affordances"] if a["id"] == args.affordance)
        cases = [(s, aff["kind"], aff.get("target"), "partial") for s, kind, target, status in cases if kind == "help"]
    cases = cases * args.repeat
    if not cases:
        raise SystemExit("No matching cases; refusing an empty coverage run")
    print(
        json.dumps(
            {
                "planned": len(cases),
                "moments": len(selected),
                "estimatedUsd": round(len(cases) * 0.03, 2),
                "maxItemUsd": args.max_item_usd,
                "promptVersion": PROMPTS["narrate"].version,
            }
        ),
        flush=True,
    )
    if not args.confirm:
        return
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "metadata.json").write_text(
        json.dumps(
            {
                "model": "sonnet-5.5",
                "modelIdHash": runtime.digest(os.environ.get("ZJ_CLAUDE_SONNET", "unset")),
                "worldHash": runtime.digest(world.w),
                "promptVersion": PROMPTS["narrate"].version,
                "planned": len(cases),
                "fixtureAct": args.fixture_act,
                "affordance": args.affordance,
                "scope": "fixed-moment conditional narration; no action resolution, navigation or DB",
                "sources": {
                    str(p.relative_to(runtime.REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (
                        Path(__file__),
                        Path(runtime.__file__),
                        runtime.REPO / "services/backend/src/zoujin_backend/narrator/view.py",
                        runtime.REPO / "services/backend/src/zoujin_backend/narrator/actions.py",
                        runtime.REPO / "services/backend/src/zoujin_backend/models/prompt_texts/narrate.txt",
                    )
                },
            },
            indent=2,
        )
    )
    ledger = Ledger(
        Path(os.environ["ZJ_CLAUDE_LEDGER"]).expanduser(),
        "claude",
        args.max_total_usd,
        args.max_item_usd,
        "deferred-spoiler-narrate",
        "eval",
    )
    settings = Settings(database_url="", model="real")
    text = Recorded(claude_text(settings, ledger=ledger))
    pipe = Pipeline(text, SchemaBook(settings.schemas), IdGen())
    rows = []
    for i, (s, kind, target, status) in enumerate(cases, 1):
        state = runtime.canonical_state(world, s)
        if args.fixture_act:
            state["vars"]["var.act.current"] = args.fixture_act
        text.calls = []
        spend = Spend()
        decision = Decision(kind, kind, target)
        if args.affordance:
            aff = next(a for a in world.w["affordances"] if a["id"] == args.affordance)
            decision = Decision(
                "affordance",
                kind,
                target,
                affordance=aff,
                checked=[
                    Checked({"summary": f"旅人は{aff['pastLabel']}"}, aff.get("effects", []), {"status": "downgraded"})
                ],
            )
        value = await narrate(
            SimpleNamespace(pipeline=pipe),
            book,
            state,
            decision,
            Outcome(status, 0, None, ["R7-capability"] if status == "refused" else []),
            spend,
            {},
        )
        row = {
            "scenario": s["id"],
            "after": s["after"],
            "action": kind,
            "target": target,
            "status": status,
            "delivered": value,
            "modelCalls": text.calls,
            "fallback": not text.calls or value != str(text.calls[-1]["output"]["text"]),
            "spent": spend.usd,
            "worldHash": runtime.digest(world.w),
            "stateHash": runtime.digest(state),
            "promptVersion": PROMPTS["narrate"].version,
            "playerKnows": [f["id"] for f in world.w["facts"] if knows(world.w, state, "player", f["id"])],
            "termFlags": spoilers(world.w, state, "player", value),
        }
        rows.append(row)
        with (args.out / "results.jsonl").open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{i}/{len(cases)} {s['id']} {kind} fallback={row['fallback']}", flush=True)
    (args.out / "summary.json").write_text(
        json.dumps(
            {
                "planned": len(cases),
                "completed": len(rows),
                "fallbacks": sum(r["fallback"] for r in rows),
                "review": "pending human read; not a release pass",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--confirm", action="store_true")
    p.add_argument("--only-after")
    p.add_argument("--affordance")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--fixture-act", choices=("act.1", "act.2", "act.3", "act.4"))
    p.add_argument("--max-item-usd", type=float, default=20)
    p.add_argument("--max-total-usd", type=float, default=10000)
    a = p.parse_args()
    if a.repeat < 1:
        p.error("positive repeat required")
    if a.confirm and (a.out / "results.jsonl").exists():
        p.error("Use a fresh directory; no silent duplicate run")
    asyncio.run(run(a))


if __name__ == "__main__":
    main()
