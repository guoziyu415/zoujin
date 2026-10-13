"""The new probe path uses production knowledge, not the historical rank-only judge context."""

import argparse
import unittest

from zj_spike import s3_runtime as runtime
from zj_spike import s3_spoiler as old
from zoujin_backend.gateway import brief
from zoujin_backend.narrator.view import situation, state_view
from zoujin_backend.world import Book


class RuntimeSpoilerTests(unittest.TestCase):
    def test_unknown_selected_question_does_not_silently_reduce_coverage(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp:
            selected = Path(temp) / "questions.json"
            selected.write_text(json.dumps([{"scenario": "missing", "question": "missing"}]))
            args = argparse.Namespace(spec="probes", only_flagged=None, questions_file=selected, repeat=1, limit=None)
            with self.assertRaisesRegex(SystemExit, "refusing partial coverage"):
                runtime.prepare(args)

    def test_rejudge_keeps_original_prompt_and_rejects_tampered_evidence(self):
        import json
        import tempfile
        from pathlib import Path

        args = argparse.Namespace(spec="probes", only_flagged=None, repeat=1, limit=1)
        _, cases = runtime.prepare(args)
        original = dict(cases[0])
        row = {**original, "reply": "それは、存じません。"}
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)
            (source / "cases.json").write_text(json.dumps([original]))
            (source / "results.jsonl").write_text(json.dumps(row) + "\n")
            cases[0]["system"] = "a later runtime prompt"
            cases[0]["briefHash"] = runtime.digest(cases[0]["system"])
            runtime.saved_replies(cases, source)
            self.assertEqual(original["system"], cases[0]["system"])
            row["briefHash"] = "changed"
            (source / "results.jsonl").write_text(json.dumps(row) + "\n")
            with self.assertRaisesRegex(SystemExit, "stored generation prompt disagree"):
                runtime.saved_replies(cases, source)
            row["briefHash"] = original["briefHash"]
            row["failureStage"] = "live"
            (source / "results.jsonl").write_text(json.dumps(row) + "\n")
            with self.assertRaisesRegex(SystemExit, "Source generation failed"):
                runtime.saved_replies(cases, source)

    def test_all_current_probe_questions_and_runtime_context_agree(self):
        args = argparse.Namespace(spec="probes,probes2,scenarios", only_flagged=None, repeat=1, limit=None)
        world, cases = runtime.prepare(args)
        self.assertEqual(497, len(cases))
        self.assertEqual(497, len({(c["character"], c["after"], c["question"]) for c in cases}))
        scenarios, _ = old.load_specs(args.spec.split(","), world)
        book = Book(world.w["book"]["id"], world.w)
        for sc in scenarios:
            state = runtime.canonical_state(world, sc)
            ctx = runtime.context(book, state, sc["character"])
            sit = situation(book, state, sc["character"], state_view(book, state))
            self.assertEqual(sorted(sit["knows"]), ctx["knownIds"])
            prompt = brief.build(book, state, sc["character"]).system
            for fact in ctx["known"]:
                self.assertIn(fact.split("：", 1)[1], prompt)
            for lived in ctx["lived"]:
                self.assertIn(lived, prompt)
            self.assertFalse(any("雨は翌朝まで続く" in x for x in ctx["lived"]))
            self.assertFalse(any("一生ここにいたい" in x for x in ctx["lived"]))

    def test_sister_after_departure_does_not_inherit_hostage_knowledge(self):
        world = old.World(runtime.REPO / "worlds/hashire-merosu/1.0.0-draft/world.json")
        scenarios, _ = old.load_specs(["probes"], world)
        sc = next(s for s in scenarios if s["id"] == "p-sister-after-departure")
        state = runtime.canonical_state(world, sc)
        book = Book(world.w["book"]["id"], world.w)
        ctx = runtime.context(book, state, sc["character"])
        self.assertNotIn("fact.promise", ctx["knownIds"])
        self.assertTrue(any(s.startswith("fact.promise：") for s in ctx["unknown_now"]))
        self.assertFalse(any(s.startswith("fact.promise：") for s in ctx["future"]))

    def test_resume_rejects_missing_execution_fingerprint_before_calling_models(self):
        import asyncio
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            (out / "metadata.json").write_text(json.dumps({"caseHash": "legacy"}))
            args = argparse.Namespace(
                spec="probes",
                only_flagged=None,
                repeat=1,
                limit=1,
                concurrency=1,
                max_item_usd=1,
                max_total_usd=1,
                out=out,
                confirm=True,
                replies_from=None,
            )
            with patch.object(runtime.claude_judge, "ClaudeJudge") as client:
                with self.assertRaisesRegex(SystemExit, "Refusing resume"):
                    asyncio.run(runtime.run(args))
                client.assert_not_called()


class JudgeAttemptTests(unittest.IsolatedAsyncioTestCase):
    async def test_recovered_timeout_retains_both_attempts_and_cost(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import AsyncMock

        from zoujin_llm import Ledger
        from zoujin_llm.claude import Reply

        judge = object.__new__(runtime.claude_judge.ClaudeJudge)
        judge.model_id = "test-sonnet-5-5"
        judge.transport = AsyncMock()
        judge.transport.create.side_effect = [TimeoutError(), Reply('{"ok": true}', "end_turn", {})]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "ledger.jsonl"
            judge.ledger = Ledger(path, "claude", 100, 100, "test", "eval")
            attempts = []
            result = await judge("judge", "system", "user", {}, attempts=attempts)
            self.assertEqual({"ok": True}, result)
            self.assertEqual(["timeout", "ok"], [a["status"] for a in attempts])
            self.assertEqual([1, 2], [a["attempt"] for a in attempts])
            rows = [json.loads(r) for r in path.read_text().splitlines()]
            self.assertEqual(["timeout", "ok"], [r["status"] for r in rows])
            self.assertGreater(rows[0]["costUsd"], 0)

    async def test_rate_limit_stops_without_retry_and_invalid_json_is_not_ok(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import AsyncMock

        from zj_spike.common import QuotaHit
        from zoujin_llm import Ledger, RateLimited
        from zoujin_llm.claude import Reply

        for response, error, status in [
            (RateLimited("HTTP 429"), QuotaHit, "error"),
            (Reply("not json", "end_turn", {}), ValueError, "bad-output"),
        ]:
            judge = object.__new__(runtime.claude_judge.ClaudeJudge)
            judge.model_id = "test-sonnet-5-5"
            judge.transport = AsyncMock()
            if isinstance(response, Exception):
                judge.transport.create.side_effect = response
            else:
                judge.transport.create.return_value = response
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "ledger.jsonl"
                judge.ledger = Ledger(path, "claude", 100, 100, "test", "eval")
                attempts = []
                with self.assertRaises(error):
                    await judge("audit", "system", "user", {}, attempts=attempts)
                judge.transport.create.assert_awaited_once()
                self.assertEqual(status, attempts[0]["status"])
                self.assertEqual(status, json.loads(path.read_text())["status"])


class LiveAttemptTests(unittest.IsolatedAsyncioTestCase):
    async def test_resume_only_finishes_missing_judgments_without_redrawing_reply(self):
        import json
        import os
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        from zj_spike.common import QuotaHit

        verdict = {
            "leak": "explicit",
            "leaked_items": ["fact.promise"],
            "knowledge_violation": True,
            "out_of_role": False,
            "japanese_only": True,
            "reason": "offline retained verdict",
        }
        # Test both grading stages, including two consecutive failed recoveries.
        for fail_audit in (False, True):
            with self.subTest(fail_audit=fail_audit), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                args = argparse.Namespace(
                    spec="probes",
                    only_flagged=None,
                    repeat=1,
                    limit=1,
                    concurrency=1,
                    max_item_usd=100,
                    max_total_usd=100,
                    out=root / "run",
                    confirm=True,
                    replies_from=None,
                )

                async def respond(question):
                    yield SimpleNamespace(kind="output_final", text="ORIGINAL_REPLY")
                    yield SimpleNamespace(kind="usage", usd=0.0123, usage={"input_tokens": 10})

                live = AsyncMock()
                live.open.return_value = SimpleNamespace(respond=respond, close=AsyncMock())
                failures = [QuotaHit("offline"), QuotaHit("offline again")]
                judge = AsyncMock(
                    side_effect=([verdict] + failures + [{"claims": []}])
                    if fail_audit
                    else (failures + [verdict, {"claims": []}])
                )
                with (
                    patch.dict(os.environ, {"ZJ_CLAUDE_LEDGER": str(root / "ledger.jsonl")}),
                    patch.object(runtime, "real_connect", return_value=(None, "test")) as connect,
                    patch.object(runtime, "GeminiLive", return_value=live),
                    patch.object(runtime.claude_judge, "ClaudeJudge", return_value=judge),
                ):
                    for attempt in range(2):
                        with self.assertRaises(SystemExit):
                            await runtime.run(args)
                        summary = json.loads((args.out / "summary.json").read_text())
                        self.assertEqual(1, summary["generated"])
                        self.assertEqual(1, summary["judgeFailed"])
                        self.assertEqual(0, summary["generationFailed"])
                        self.assertEqual(0, summary["notStarted"])
                        self.assertEqual(attempt + 1, summary["failedAttempts"])
                        self.assertEqual(1, summary["automatedSummary"]["runtime"]["errors"])
                        self.assertIn("ORIGINAL_REPLY", (args.out / "read-all.md").read_text())
                        if attempt == 0:
                            original_line = (args.out / "results.jsonl").read_text()
                    await runtime.run(args)
                live.open.assert_awaited_once()
                connect.assert_called_once()
                self.assertTrue((args.out / "results.jsonl").read_text().startswith(original_line))
                rows = [json.loads(s) for s in (args.out / "results.jsonl").read_text().splitlines()]
                self.assertEqual(["ORIGINAL_REPLY"] * 3, [r["reply"] for r in rows])
                self.assertEqual([False, False, True], [r["complete"] for r in rows])
                self.assertEqual(0, rows[-1]["liveCostUsd"])
                self.assertEqual(0.0123, rows[-1]["originalLiveCostUsd"])
                self.assertEqual(False, rows[-1]["originalUsageMissing"])
                self.assertEqual(2, rows[-1]["resumedFromRow"])
                self.assertEqual("explicit", rows[-1]["leak"])
                stages = [c.args[0] for c in judge.await_args_list]
                self.assertEqual(
                    ["judge", "audit", "audit", "audit"] if fail_audit else ["judge", "judge", "judge", "audit"], stages
                )
                summary = json.loads((args.out / "summary.json").read_text())
                self.assertEqual(1, summary["completed"])
                self.assertEqual(1, summary["flaggedReplies"])
                self.assertEqual(2, summary["failedAttempts"])
                self.assertEqual(0, summary["automatedSummary"]["runtime"]["errors"])

    async def test_failed_generation_is_not_retried_but_unstarted_cases_continue(self):
        import json
        import os
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        # A transcript received before stream/close failure must survive too.
        for after_reply in (False, True):
            with self.subTest(after_reply=after_reply), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                args = argparse.Namespace(
                    spec="probes",
                    only_flagged=None,
                    repeat=1,
                    limit=2,
                    concurrency=1,
                    max_item_usd=100,
                    max_total_usd=100,
                    out=root / "run",
                    confirm=True,
                    replies_from=None,
                )

                async def respond(question):
                    yield SimpleNamespace(kind="output_final", text="SAVED_REPLY")

                session = SimpleNamespace(respond=respond, close=AsyncMock())
                live = AsyncMock()
                if after_reply:
                    session.close.side_effect = [TimeoutError(), None]
                    live.open.return_value = session
                else:
                    live.open.side_effect = [TimeoutError(), session]
                judge = AsyncMock(
                    side_effect=[
                        {
                            "leak": "none",
                            "leaked_items": [],
                            "knowledge_violation": False,
                            "out_of_role": False,
                            "japanese_only": True,
                            "reason": "offline",
                        },
                        {"claims": []},
                    ]
                )
                with (
                    patch.dict(os.environ, {"ZJ_CLAUDE_LEDGER": str(root / "ledger.jsonl")}),
                    patch.object(runtime, "real_connect", return_value=(None, "test")),
                    patch.object(runtime, "GeminiLive", return_value=live),
                    patch.object(runtime.claude_judge, "ClaudeJudge", return_value=judge),
                ):
                    with self.assertRaises(SystemExit):
                        await runtime.run(args)
                    summary = json.loads((args.out / "summary.json").read_text())
                    self.assertEqual(
                        (1, 0, 1), tuple(summary[k] for k in ("generationFailed", "judgeFailed", "notStarted"))
                    )
                    first_line = (args.out / "results.jsonl").read_text()
                    for _ in range(2):
                        with self.assertRaises(SystemExit):
                            await runtime.run(args)
                self.assertEqual(2, live.open.await_count)
                self.assertEqual(2, judge.await_count)
                self.assertTrue((args.out / "results.jsonl").read_text().startswith(first_line))
                rows = [json.loads(s) for s in (args.out / "results.jsonl").read_text().splitlines()]
                self.assertEqual(2, len(rows))
                self.assertEqual("live", rows[0]["failureStage"])
                self.assertEqual("SAVED_REPLY" if after_reply else "", rows[0]["reply"])
                summary = json.loads((args.out / "summary.json").read_text())
                self.assertEqual(
                    (1, 1, 0, 0, 1),
                    tuple(
                        summary[k]
                        for k in ("completed", "generationFailed", "judgeFailed", "notStarted", "failedAttempts")
                    ),
                )
                self.assertEqual(1, summary["automatedSummary"]["runtime"]["errors"])

    async def test_live_connect_timeout_is_recorded_and_stops_before_judging(self):
        import json
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import AsyncMock, patch

        with tempfile.TemporaryDirectory() as temp:
            ledger = Path(temp) / "ledger.jsonl"
            out = Path(temp) / "run"
            args = argparse.Namespace(
                spec="probes",
                only_flagged=None,
                repeat=1,
                limit=2,
                concurrency=1,
                max_item_usd=100,
                max_total_usd=100,
                out=out,
                confirm=True,
                replies_from=None,
            )
            live = AsyncMock()
            live.open.side_effect = TimeoutError()
            judge = AsyncMock()
            with (
                patch.dict(os.environ, {"ZJ_CLAUDE_LEDGER": str(ledger)}),
                patch.object(runtime, "real_connect", return_value=(None, "test")),
                patch.object(runtime, "GeminiLive", return_value=live),
                patch.object(runtime.claude_judge, "ClaudeJudge", return_value=judge),
            ):
                with self.assertRaises(SystemExit):
                    await runtime.run(args)
            live.open.assert_awaited_once()
            judge.assert_not_awaited()
            row = json.loads((out / "results.jsonl").read_text())
            self.assertFalse(row["complete"])
            self.assertEqual("timeout", row["callAttempts"][0]["status"])
            self.assertEqual("TimeoutError", row["callAttempts"][0]["errorType"])
            self.assertEqual("timeout", json.loads(ledger.read_text())["status"])
            self.assertEqual(2, json.loads((out / "summary.json").read_text())["missing"])

    async def test_stop_file_finishes_active_reply_before_stopping_dispatch(self):
        import json
        import os
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        with tempfile.TemporaryDirectory() as temp:
            ledger = Path(temp) / "ledger.jsonl"
            out, stop_file = Path(temp) / "run", Path(temp) / "stop"
            args = argparse.Namespace(
                spec="probes",
                only_flagged=None,
                repeat=1,
                limit=2,
                concurrency=1,
                max_item_usd=100,
                max_total_usd=100,
                out=out,
                confirm=True,
                replies_from=None,
                stop_file=stop_file,
            )

            async def respond(question):
                stop_file.touch()
                yield SimpleNamespace(kind="output_final", text="分かりません。")

            session = SimpleNamespace(respond=respond, close=AsyncMock())
            live = AsyncMock()
            live.open.return_value = session
            judge = AsyncMock(
                side_effect=[
                    {
                        "leak": "none",
                        "leaked_items": [],
                        "knowledge_violation": False,
                        "out_of_role": False,
                        "japanese_only": True,
                        "reason": "offline",
                    },
                    {"claims": []},
                ]
            )
            with (
                patch.dict(os.environ, {"ZJ_CLAUDE_LEDGER": str(ledger)}),
                patch.object(runtime, "real_connect", return_value=(None, "test")),
                patch.object(runtime, "GeminiLive", return_value=live),
                patch.object(runtime.claude_judge, "ClaudeJudge", return_value=judge),
            ):
                with self.assertRaises(SystemExit):
                    await runtime.run(args)
            live.open.assert_awaited_once()
            session.close.assert_awaited_once()
            self.assertEqual(2, judge.await_count)
            row = json.loads((out / "results.jsonl").read_text())
            self.assertTrue(row["complete"])
            summary = json.loads((out / "summary.json").read_text())
            self.assertTrue(summary["stopRequested"])
            self.assertEqual(1, summary["completed"])
            self.assertEqual(1, summary["missing"])
