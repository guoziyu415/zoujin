"""Finite narration regressions through real eval_api decide/verify/DB transactions.

Checkpoint setup is explicit act.3, not a full opening-to-ending playthrough.
Credentials and a dedicated local DATABASE_URL must be supplied by a private loader.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from zoujin_backend import eval_api
from zoujin_backend.models.prompts import PROMPTS
from zoujin_backend.projection import action_id

from .s3_narrate import Recorded
from .s3_runtime import REPO, digest

CASES = [
    {"id": "open-groom-prep", "after": "beat.09", "target": "char.groom", "button": True},
    {"id": "generic-melos-after-agreement", "after": "beat.10", "target": "char.melos"},
    {"id": "absent-king-help", "after": "beat.10", "target": "char.king"},
    {"id": "stale-groom-prep", "after": "beat.10", "target": "char.groom", "stale": True},
]


def run(args):
    planned = len(CASES) * args.repeat
    metadata = {
        "planned": planned,
        "scope": "real checkpoint DB actions, not full playthrough or Live character dialogue",
        "promptVersion": PROMPTS["narrate"].version,
        "modelIdHash": digest(os.environ.get("ZJ_CLAUDE_SONNET", "unset")),
        "sources": {
            str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (
                Path(__file__),
                REPO / "services/backend/src/zoujin_backend/eval_api.py",
                REPO / "services/backend/src/zoujin_backend/narrator/actions.py",
                REPO / "services/backend/src/zoujin_backend/narrator/view.py",
                REPO / "services/backend/src/zoujin_backend/models/prompt_texts/narrate.txt",
                REPO / "worlds/hashire-merosu/1.0.0-draft/world.json",
            )
        },
        "estimatedUsd": planned * 0.3,
        "maxItemUsd": os.environ.get("ZJ_MAX_ITEM_USD"),
    }
    print(json.dumps(metadata), flush=True)
    if not args.confirm:
        return
    if os.environ.get("ZJ_MODEL") != "real":
        raise SystemExit("Real mode required; refusing fake evidence")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    rows = []
    for c in CASES:
        for rep in range(1, args.repeat + 1):
            session = None
            row = {"case": c["id"], "rep": rep}
            try:
                setup = {
                    "role": "role.traveler",
                    "checkpoint": f"sc.canon@{c['after']}",
                    "place": "place.groom-house",
                    "events": [
                        {
                            "effects": [{"op": "set", "var": "var.act.current", "value": "act.3"}],
                            "note": "評価の幕をチェックポイントに合わせる",
                        }
                    ],
                }
                session = eval_api.setup(setup, mode="text")
                recorded = Recorded(session.text)
                session.text = recorded
                view = session.view()
                before = session.state()
                aid = None
                if c.get("button"):
                    options = view["snapshot"]["actions"]
                    selected = next(a for a in options if a["kind"] == "help" and a.get("target") == c["target"])
                    aid = selected["actionId"]
                elif c.get("stale"):
                    aid = action_id("aff.groom-prep")
                result = session.act("help", c["target"], {}, action_id=aid)
                row.update(
                    setup=setup,
                    playthroughId=session.pid,
                    before=before,
                    result=result,
                    after=session.state(),
                    events=session.events(),
                    modelCalls=recorded.calls,
                    complete=True,
                )
                narration_calls = [r for r in recorded.calls if r["kind"] == "narrate"]
                row["narrationCallCount"] = len(narration_calls)
                row["narrationFallback"] = bool(result.get("narration")) and (
                    not narration_calls or narration_calls[-1]["output"].get("text") != result["narration"]
                )
            except Exception as exc:
                row.update(complete=False, errorType=type(exc).__name__)
            finally:
                if session is not None:
                    session.close()
            rows.append(row)
            with (args.out / "results.jsonl").open("a") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"{len(rows)}/{planned} {c['id']} complete={row['complete']}", flush=True)
            if not row["complete"]:
                raise SystemExit(2)
    (args.out / "summary.json").write_text(
        json.dumps(
            {
                "planned": planned,
                "completed": len(rows),
                "fallbacks": sum(r["narrationFallback"] for r in rows),
                "review": "pending agent review; not a release pass",
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if args.repeat < 1 or args.repeat > 5:
        parser.error("repeat must be 1..5")
    if args.confirm and (args.out / "results.jsonl").exists():
        parser.error("Use a fresh output directory")
    run(args)


if __name__ == "__main__":
    main()
