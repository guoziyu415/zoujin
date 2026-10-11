"""Offline self-test: runs every spike end to end against a fake Live server, fake text model and fake Claude.

  uv run python -m unittest tests.test_offline -v

No network, no credentials, no cost. It checks the plumbing (turn bookkeeping, cost ledger, budget stop,
quota stop, result files), not model behaviour.
"""

from __future__ import annotations

import asyncio
import csv
import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest import mock

TMP = Path(tempfile.mkdtemp(prefix="zj-offline-"))
os.environ.update(ZJ_PROJECT="offline-test", ZJ_OUT=str(TMP / "out"), ZJ_LEDGER=str(TMP / "ledger.json"))

from google.genai import types  # noqa: E402

from zoujin_llm import ModelCallFailed, RateLimited  # noqa: E402
from zoujin_llm.claude import Reply  # noqa: E402

from zj_spike import claude_judge, common, live_util, s0_check, s1_live, s3_spoiler, s4_model_armor  # noqa: E402

WORLD = s3_spoiler.world_path()
live_util.TAIL_QUIET_S = 0.05  # keep the fake runs fast; a late transcript still gets the full TAIL_CAP_S


def usage(prompt=400, out=120):
    return types.UsageMetadata(
        prompt_token_count=prompt, response_token_count=out, total_token_count=prompt + out,
        prompt_tokens_details=[types.ModalityTokenCount(modality=types.MediaModality.TEXT, token_count=prompt)],
        response_tokens_details=[types.ModalityTokenCount(modality=types.MediaModality.AUDIO, token_count=out)],
    )


class FakeSession:
    """Mimics AsyncSession: replies after activity_end or a complete text turn; activity_start barges in."""

    def __init__(self, config, fail_with=None, late_transcript=False, drop_text_when=None):
        self.config = config
        self.drop_text_when = drop_text_when  # replies to a turn containing this send audio but never their text
        self.q: asyncio.Queue = asyncio.Queue()
        self.reply_task = None
        self.history: list[str] = []
        self.fail_with = fail_with
        self.late_transcript = late_transcript  # the reply's text arrives after turn_complete

    def _say(self, text: str, chunks: int = 6, gap: float = 0.03, drop_text: bool = False):
        async def run():
            await asyncio.sleep(0.05)
            text_msg = types.LiveServerMessage(server_content=types.LiveServerContent(
                output_transcription=types.Transcription(text=text)))
            if drop_text:
                pass
            elif not self.late_transcript:
                await self.q.put(text_msg)
            for _ in range(chunks):
                await self.q.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                    model_turn=types.Content(parts=[types.Part(inline_data=types.Blob(data=b"\x01\x00" * 960, mime_type="audio/pcm;rate=24000"))]))))
                await asyncio.sleep(gap)
            await self.q.put(types.LiveServerMessage(usage_metadata=usage()))
            await self.q.put(types.LiveServerMessage(server_content=types.LiveServerContent(turn_complete=True)))
            if self.late_transcript and not drop_text:
                await asyncio.sleep(0.3)
                await self.q.put(text_msg)
            if self.config.session_resumption is not None:
                await self.q.put(types.LiveServerMessage(session_resumption_update=types.LiveServerSessionResumptionUpdate(
                    new_handle="h-" + "|".join(self.history), resumable=True)))
        self.reply_task = asyncio.create_task(run())

    def _answer(self, text: str) -> str:
        if self.fail_with:
            raise self.fail_with
        if "長く" in text:
            return "長い話" * 20
        if "鐘" in "".join(self.history) and "音" in text:
            return "ええ、鐘が三度鳴りましたな。"
        if "名前" in text and "覚えて" in text and any("ケン" in h for h in self.history):
            return "ケンさん、でしたな。"
        return "さようでございますか。"

    async def send_client_content(self, *, turns=None, turn_complete=True):
        text = "".join(p.text or "" for p in turns.parts)
        self.history.append(text)
        if turn_complete:
            drop = bool(self.drop_text_when) and self.drop_text_when in text
            self._say(self._answer(text), chunks=60 if "長く" in text else 6, drop_text=drop)

    async def send_realtime_input(self, *, audio=None, activity_start=None, activity_end=None, text=None):
        if activity_start is not None and self.reply_task and not self.reply_task.done():
            self.reply_task.cancel()
            await self.q.put(types.LiveServerMessage(server_content=types.LiveServerContent(interrupted=True)))
            await self.q.put(types.LiveServerMessage(usage_metadata=usage()))
            await self.q.put(types.LiveServerMessage(server_content=types.LiveServerContent(turn_complete=True)))
        if activity_end is not None:
            await self.q.put(types.LiveServerMessage(server_content=types.LiveServerContent(
                input_transcription=types.Transcription(text="（音声）"))))
            self._say(self._answer("音声"))

    async def receive(self):
        while True:
            msg = await self.q.get()
            yield msg
            if msg.server_content and msg.server_content.turn_complete:
                return


class FakeModels:
    def __init__(self, judge_leak="none", slow_judges=0, audit_claims=None):
        self.judge_leak = judge_leak
        self.slow_judges = slow_judges  # this many calls hang (to test the judge time limit)
        self.audit_claims = audit_claims or []  # what the S-3 audit judge extracts from every reply
        self.classify_temperatures: set = set()

    async def generate_content(self, model, contents, config):
        if self.slow_judges > 0:
            self.slow_judges -= 1
            await asyncio.sleep(3600)
        if config.response_json_schema and "self_harm" in config.response_json_schema["properties"]:
            self.classify_temperatures.add(config.temperature)
            said = contents.rsplit("発話：", 1)[-1]
            if "毒の作り方" in said:  # the real model's safety filter answers nothing to this one
                return types.GenerateContentResponse(
                    candidates=[types.Candidate(content=types.Content(parts=[]), finish_reason=types.FinishReason.SAFETY)],
                    usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=300, candidates_token_count=0))
            text = json.dumps({"self_harm": "signal" if "死にたい" in said else "none",
                               "injection": "指示" in said, "reason": "fake"})
        elif config.response_json_schema and "claims" in config.response_json_schema["properties"]:
            text = json.dumps({"claims": self.audit_claims, "reason": "fake"})
        elif config.response_json_schema:
            text = json.dumps({"leak": self.judge_leak, "leaked_items": [], "knowledge_violation": False,
                               "out_of_role": False, "japanese_only": True, "reason": "fake"})
        else:
            text = "はい"
        return types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(parts=[types.Part(text=text)]))],
            usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=300, candidates_token_count=40),
        )


class FakeClient:
    def __init__(self, fail_with=None, judge_leak="none", fail_first_connects=0, late_transcript=False,
                 hang_first_connects=0, slow_judges=0, audit_claims=None, drop_text_when=None):
        self.fail_with = fail_with
        self.fail_first_connects = fail_first_connects
        self.hang_first_connects = hang_first_connects  # setup_complete never arrives for these
        self.late_transcript = late_transcript
        self.drop_text_when = drop_text_when
        self.sessions: list[FakeSession] = []
        self.connect_configs: list = []
        live = self

        class Live:
            @contextlib.asynccontextmanager
            async def connect(self_inner, model, config):
                await asyncio.sleep(0.01)
                if live.hang_first_connects > 0:
                    live.hang_first_connects -= 1
                    await asyncio.sleep(3600)
                live.connect_configs.append((model, config))
                if live.fail_first_connects > 0:
                    live.fail_first_connects -= 1
                    raise RuntimeError("1007 invalid argument: language_codes")
                if live.fail_with and getattr(live.fail_with, "_on_connect", False):
                    raise live.fail_with
                sess = FakeSession(config, fail_with=None if getattr(live.fail_with, "_on_connect", False) else live.fail_with,
                                   late_transcript=live.late_transcript, drop_text_when=live.drop_text_when)
                if config.session_resumption and config.session_resumption.handle:
                    sess.history = config.session_resumption.handle[2:].split("|")
                live.sessions.append(sess)
                yield sess

        class Aio:
            pass

        self.aio = Aio()
        self.aio.live = Live()
        self.aio.models = FakeModels(judge_leak, slow_judges, audit_claims)


class FakeClaude:
    """Stands in for zoujin_llm's AsyncTransport behind the S-3 judges (Claude since D-028): no network, no key."""

    def __init__(self, judge_leak="none", audit_claims=None, knowledge_violation=False, slow=0, fail=None):
        self.judge_leak = judge_leak
        self.audit_claims = audit_claims or []
        self.knowledge_violation = knowledge_violation
        self.slow = slow  # this many calls hang (to test the judge time limit)
        self.fail = fail  # raised on every call
        self.calls: list[dict] = []

    async def create(self, params):
        self.calls.append(params)
        if self.slow > 0:
            self.slow -= 1
            await asyncio.sleep(3600)
        if self.fail:
            raise self.fail
        if "claims" in params["output_config"]["format"]["schema"]["properties"]:
            out = {"claims": self.audit_claims, "reason": "fake"}
        else:
            out = {"leak": self.judge_leak, "leaked_items": [], "knowledge_violation": self.knowledge_violation,
                   "out_of_role": False, "japanese_only": True, "reason": "fake"}
        usage = {"inputTokens": 120, "cacheReadTokens": 2500, "cacheWriteTokens": 0, "outputTokens": 300}
        return Reply(json.dumps(out, ensure_ascii=False), "end_turn", usage)


KEY = "sk-ant-test-marker-0000"
CLAUDE_LEDGER = TMP / "claude-ledger.jsonl"
CLAUDE_ENV = {"ANTHROPIC_API_KEY": KEY, "ZJ_CLAUDE_SONNET": "test-sonnet-5-5-idmark", "ZJ_CLAUDE_LEDGER": str(CLAUDE_LEDGER)}


def run_s3(argv, client, claude=None):
    """S-3 with its gate passed (--confirm, the Claude cap, the env the Mac sets) and the fake Claude behind it."""
    claude = claude or FakeClaude()
    with mock.patch.dict(os.environ, CLAUDE_ENV), mock.patch.object(claude_judge, "AsyncTransport", lambda: claude):
        run_cli(s3_spoiler, [*argv, "--confirm", "--max-claude-usd", "100", "--max-item-usd", "15"], client)
    return claude


def write_wavs(d: Path, n: int = 3) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        with wave.open(str(d / f"u{i}.wav"), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
            w.writeframes(b"\x00\x00" * (16000 // 5))  # 0.2 s
    return d


def run_cli(module, argv, client):
    with mock.patch.object(sys, "argv", ["x", *argv]), \
         mock.patch.object(common, "genai_client", lambda loc: client), \
         mock.patch.object(common, "credentials", lambda: None):
        module.main()


class Offline(unittest.TestCase):
    def setUp(self):
        Path(os.environ["ZJ_LEDGER"]).unlink(missing_ok=True)
        CLAUDE_LEDGER.unlink(missing_ok=True)

    def test_cost_functions(self):
        c = common.live_usage_cost(usage(1_000_000, 1_000_000))
        self.assertAlmostEqual(c, 0.75 + 12.00)
        self.assertEqual(common.percentile([5, 1, 3, 2, 4], 50), 3)
        self.assertEqual(common.summarize_ms([None])["n"], 0)

    def test_s1_latency_and_ledger(self):
        client = FakeClient()
        wavs = write_wavs(TMP / "wavs")
        run_cli(s1_live, ["latency", "--sessions", "2", "--wav-dir", str(wavs), "--pause", "0"], client)
        res = sorted((TMP / "out" / "s1").glob("latency-default-*/result.json"))[-1]
        data = json.loads(res.read_text())
        self.assertEqual(len(data["turns"]), 6)
        self.assertTrue(all(t["first_audio_ms"] is not None and t["first_audio_ms"] >= 40 for t in data["turns"]))
        self.assertEqual(data["summary"]["release_to_first_audio_ms"]["n"], 6)
        self.assertGreater(common.spent(), 0)
        self.assertTrue(all(t["usage_msgs"] == 1 for t in data["turns"]))

    def test_s1_latency_vocab_and_cer(self):
        client = FakeClient()
        lines = ["セリヌンティウスさんの仕事場は、どちらですか。", "こんばんは。"]
        with mock.patch.object(s1_live, "synth_utterances", lambda ls, d: [(l, b"\x00\x00" * 3200) for l in lines]):
            run_cli(s1_live, ["latency", "--sessions", "1", "--vocab", "--pause", "0"], client)
        data = json.loads(sorted((TMP / "out" / "s1").glob("latency-default-vocab-*/result.json"))[-1].read_text())
        self.assertEqual(client.connect_configs[-1][1].input_audio_transcription.custom_vocabulary, s1_live.PROPER_NOUNS)
        self.assertEqual(data["summary"]["proper_noun_mentions"], 1)
        self.assertEqual(data["summary"]["proper_noun_misses"], 1)  # the fake transcribes everything as （音声）
        self.assertGreater(data["summary"]["transcript_cer_mean"], 0.5)

    def test_s1_barge(self):
        client = FakeClient()
        with mock.patch.object(s1_live, "synth_utterances", lambda lines, d: [(lines[0], b"\x00\x00" * 3200)]):
            run_cli(s1_live, ["barge", "--reps", "2", "--after", "0.3"], client)
        data = json.loads(sorted((TMP / "out" / "s1").glob("barge-*/result.json"))[-1].read_text())
        self.assertEqual(data["summary"]["press_to_interrupted_ms"]["n"], 2)
        self.assertIsNotNone(data["reps"][0]["reply_after_barge"]["first_audio_ms"])

    def test_s1_voices_midsession_resume(self):
        client = FakeClient()
        run_cli(s1_live, ["voices", "--only", "Kore,Puck"], client)
        self.assertTrue((TMP / "out" / "s1" / "voices" / "Kore.wav").exists())
        self.assertTrue((TMP / "out" / "s1" / "voices" / "voices.csv").exists())
        run_cli(s1_live, ["midsession", "--reps", "1"], client)
        mid = json.loads(sorted((TMP / "out" / "s1").glob("midsession-*/result.json"))[-1].read_text())
        self.assertEqual(mid["summary"]["system"]["mentions_bell"], 1)
        self.assertEqual(mid["summary"]["none"]["mentions_bell"], 0)
        run_cli(s1_live, ["resume", "--reps", "1"], client)
        res = json.loads(sorted((TMP / "out" / "s1").glob("resume-*/result.json"))[-1].read_text())
        self.assertTrue(res["reps"][0]["remembers"])
        self.assertFalse(res["reps"][1]["remembers"])  # control without handle
        self.assertEqual([r["used_handle"] for r in res["reps"]], [True, False])

    def test_quota_error_stops_everything(self):
        err = RuntimeError("1011 RESOURCE_EXHAUSTED: Quota exceeded")
        err._on_connect = True
        with self.assertRaises(SystemExit) as cm:
            run_cli(s1_live, ["voices", "--only", "Kore,Puck"], FakeClient(fail_with=err))
        self.assertEqual(cm.exception.code, 4)

    def test_budget_cap_stops(self):
        with mock.patch.object(common, "BUDGET_USD", 0.0101):
            with self.assertRaises(SystemExit) as cm:
                run_cli(s1_live, ["midsession", "--reps", "3"], FakeClient())
        self.assertEqual(cm.exception.code, 3)

    def test_s0_check(self):
        client = FakeClient()

        class FakeArmor:
            def __init__(self, **kw):
                pass

            def list_templates(self, parent):
                return []

        with mock.patch.object(common, "genai_client", lambda loc: client), \
             mock.patch.object(common, "credentials", lambda: object()), \
             mock.patch("google.cloud.modelarmor_v1.ModelArmorClient", FakeArmor):
            common.run(s0_check.main)
        self.assertTrue((TMP / "out" / "s0" / "result.json").exists())

    def test_s0_live_fallback_without_language_hint(self):
        client = FakeClient(fail_first_connects=1)

        class FakeArmor:
            def __init__(self, **kw):
                pass

            def list_templates(self, parent):
                return []

        with mock.patch.object(common, "genai_client", lambda loc: client), \
             mock.patch.object(common, "credentials", lambda: object()), \
             mock.patch("google.cloud.modelarmor_v1.ModelArmorClient", FakeArmor):
            common.run(s0_check.main)
        res = json.loads((TMP / "out" / "s0" / "result.json").read_text())
        self.assertEqual(res["live"]["needs"], "ZJ_TRANSCRIBE_LANG=")
        first, second = client.connect_configs[0][1], client.connect_configs[1][1]
        self.assertEqual(first.input_audio_transcription.language_codes, ["ja-JP"])
        self.assertIsNone(second.input_audio_transcription.language_codes)

    @unittest.skipUnless(WORLD.exists(), "world.json not found")
    def test_s3_spoiler(self):
        run_s3(["--only", "king-after-promise,selinuntius-hostage"], FakeClient(), FakeClaude(judge_leak="hint"))
        out = sorted((TMP / "out" / "s3").iterdir())[-1]
        summary = json.loads((out / "summary.json").read_text())["summary"]
        self.assertEqual(summary["guard"]["n"], 20)
        self.assertEqual(summary["naive"]["leak_hint"], 20)
        personas = (out / "personas.md").read_text()
        # The time-cut personas must not carry later lines; the naive one does.
        guard_king = personas.split("## king-after-promise / guard")[1].split("## ")[0]
        naive_king = personas.split("## king-after-promise / naive")[1].split("## ")[0]
        self.assertNotIn("仲間に入れて", guard_king)
        self.assertIn("仲間に入れて", naive_king)
        guard_sel = personas.split("## selinuntius-hostage / guard")[1].split("## ")[0]
        self.assertNotIn("一度だけ友を疑った", guard_sel)
        self.assertIn("知識の境界", guard_sel)
        # Time-cut goals reach base/guard too (S-068: the wedding date is not set before beat.08).
        self.assertIn("いまの目的", guard_king)
        world = s3_spoiler.World(WORLD)
        scenarios, _ = s3_spoiler.load_specs(["scenarios"], world)
        melos = next(sc for sc in scenarios if sc["id"] == "melos-square")
        self.assertIn("日取りはまだ決まっていない", s3_spoiler.persona(world, melos, melos["partner"], "guard"))

    @unittest.skipUnless(WORLD.exists(), "world.json not found")
    def test_s3_repeat_and_audit(self):
        # S-068: every question asked twice; a second, claim-by-claim judge; disagreements and a random
        # sample of passed replies go to people in audit.md.
        claims = [{"text": "明日には婚礼がある", "kind": "future_match", "as_fact": True}]
        run_s3(["--only", "king-after-promise", "--conditions", "guard", "--repeat", "2"], FakeClient(),
               FakeClaude(audit_claims=claims))
        out = sorted((TMP / "out" / "s3").iterdir())[-1]
        summary = json.loads((out / "summary.json").read_text())["summary"]["guard"]
        self.assertEqual(summary["n"], 20)
        self.assertEqual((summary["leak_explicit"], summary["audit_explicit"], summary["disagree"]), (0, 20, 20))
        rows = [json.loads(x) for x in (out / "results.jsonl").read_text().splitlines()]
        self.assertEqual(sorted({r["rep"] for r in rows}), [1, 2])
        audit = (out / "audit.md").read_text()
        self.assertIn("两边不一致（20 条）", audit)
        self.assertIn("明日には婚礼がある", audit)
        self.assertEqual(s3_spoiler.audit_leak([{"text": "", "kind": "future_match", "as_fact": False}]), "hint")
        self.assertEqual(s3_spoiler.audit_leak([{"text": "", "kind": "future_other", "as_fact": True}]), "none")
        # The guard prompt now also forbids stating undecided dates (the one S-3 guard leak).
        self.assertIn("日取り", (out / "personas.md").read_text())

    @unittest.skipUnless(WORLD.exists(), "world.json not found")
    def test_s3_probe_set_bounds_and_resume(self):
        # Data engineering's probe set: no "when" (taken from the beat's clock), a style and targets per question.
        spec = {"partner": "旅人", "keywords": ["改心"], "common_questions": ["結末を教えて。"], "scenarios": [
            {"id": "p-king-day2", "character": "char.king", "after": "beat.11", "place": "place.castle", "voice": "Charon",
             "questions": ["あの男は戻ると思うか。", "いつか改心なさるのでしょう？"],
             "probes": [{"targets": ["beat.24"], "style": "open"}, {"targets": ["beat.26"], "style": "leading"}]}]}
        path = TMP / "probes.json"
        path.write_text(json.dumps(spec, ensure_ascii=False))
        claims = [{"text": "王は改心する", "kind": "future_match", "as_fact": True}]
        client, claude = FakeClient(), FakeClaude(audit_claims=claims)
        args = ["--spec", f"{path},scenarios", "--only", "p-king-day2,king-after-promise", "--conditions", "guard", "--repeat", "2"]
        run_s3(args, client, claude)
        out = sorted((TMP / "out" / "s3").iterdir())[-1]
        v = json.loads((out / "summary.json").read_text())["summary"]["guard"]
        self.assertEqual((v["n"], v["questions"], v["leak_any"], v["questions_leaked"]), (26, 13, 26, 13))
        self.assertEqual(v["by_style"]["leading"], {"n": 2, "leak_any": 2, "leak_explicit": 0, "audit_explicit": 2})
        self.assertEqual(sorted(v["by_style"]), ["common", "leading", "open", "original"])
        self.assertIn("いまは二日目の真昼", (out / "personas.md").read_text())
        self.assertIn("题型：leading；想引出：beat.26", (out / "audit.md").read_text())
        # 0 in 299 is the first count under 1%; 0 in 252 is not.
        self.assertLessEqual(s3_spoiler.upper95(0, 299), 0.01)
        self.assertGreater(s3_spoiler.upper95(0, 252), 0.01)
        self.assertAlmostEqual(s3_spoiler.upper95(1, 473), 0.01, places=3)
        # A stopped run: drop the last two replies and turn one into an error; --resume asks only those three again.
        rows = (out / "results.jsonl").read_text().splitlines()
        broken = {**json.loads(rows[0]), "error": "TimeoutError"}
        broken.pop("leak")
        (out / "results.jsonl").write_text("\n".join([json.dumps(broken, ensure_ascii=False), *rows[1:-2]]) + "\n")
        before = len(client.sessions)
        run_s3([*args, "--resume", str(out)], client, claude)
        self.assertEqual(len(client.sessions) - before, 3)
        rows = [json.loads(x) for x in (out / "results.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 26)
        self.assertTrue(all("leak" in r for r in rows))
        self.assertTrue((out / "results.jsonl.bak").exists())

    def test_s1_transcripts_diagnostic(self):
        # results-s1.md 2.3: some replies come with audio and no text at all. Four setups, every server message
        # about the transcript logged, and every reply transcribed again by a text model (the fallback).
        client = FakeClient(drop_text_when="風が強い")
        run_cli(s1_live, ["transcripts", "--voices", "Kore:melos", "--repeat", "1", "--wait", "0.3"], client)
        out = sorted((TMP / "out" / "s1" / "transcripts").iterdir())[-1]
        v = json.loads((out / "summary.json").read_text())["summary"]
        self.assertEqual({m: v[m]["empty"] for m in v}, {"multi": 1, "fresh": 1, "ja": 1, "talk": 0})
        self.assertEqual(v["multi"]["empty_by_position"], [0, 0, 0, 0, 0, 1, 0])
        self.assertEqual(v["multi"]["empty_with_no_transcript_msgs"], 1)
        self.assertEqual(v["multi"]["late_text"], 0)
        self.assertEqual((v["multi"]["fallback_errors"], v["multi"]["fallback_ms"]["n"]), (0, 7))
        self.assertEqual(len(client.sessions), 1 + 7 + 1 + 1)  # fresh = one session per line
        langs = [c.output_audio_transcription.language_codes for _, c in client.connect_configs]
        self.assertEqual(sum(l == ["ja-JP"] for l in langs), 1)
        self.assertEqual(len(list((out / "wav").glob("*.wav"))), 3)
        logs = [json.loads(x) for x in (out / "log.jsonl").read_text().splitlines()]
        self.assertEqual(len(logs), 28)
        self.assertTrue(any(e.get("out_text") for x in logs for e in x["log"]))
        self.assertTrue(all(any(e.get("turn_complete") for e in x["log"]) for x in logs))

    def test_late_transcript_is_kept(self):
        # S-1 voices lost the reply text in 19/30 sessions: it can arrive after turn_complete.
        client = FakeClient(late_transcript=True)
        run_cli(s1_live, ["voices", "--only", "Kore"], client)
        rows = list(csv.DictReader(open(TMP / "out" / "s1" / "voices" / "voices.csv", encoding="utf-8-sig")))
        self.assertTrue(rows[0]["transcript"])
        self.assertGreater(int(rows[0]["transcript_late_ms"]), 200)

    @unittest.skipUnless(WORLD.exists(), "world.json not found")
    def test_s3_late_text_and_time_limits(self):
        client = FakeClient(late_transcript=True, hang_first_connects=1)
        with mock.patch.object(live_util, "SETUP_TIMEOUT_S", 0.3), mock.patch.object(claude_judge, "TIMEOUT_S", 0.3):
            run_s3(["--only", "king-after-promise", "--conditions", "guard"], client, FakeClaude(slow=1))
        out = sorted((TMP / "out" / "s3").iterdir())[-1]
        data = json.loads((out / "summary.json").read_text())
        self.assertEqual(data["summary"]["guard"]["errors"], 0)  # one hung setup and one hung judge, both retried
        self.assertEqual(data["summary"]["guard"]["empty_reply"], 0)
        self.assertEqual(data["timing"]["judge_s"]["n"], 10)
        rows = [json.loads(x) for x in (out / "results.jsonl").read_text().splitlines()]
        self.assertTrue(all(r["reply"] and r["transcript_late_ms"] > 200 for r in rows))
        self.assertTrue(all("at" in r and "setup_ms" in r and "judge_s" in r for r in rows))
        # The hung judge call is booked at the high estimate (it may have been billed), then the retry at its usage.
        ledger = [json.loads(x) for x in CLAUDE_LEDGER.read_text().splitlines()]
        self.assertEqual(len(ledger), 20 + 1)
        self.assertEqual(ledger[0]["usage"], {})

    @unittest.skipUnless(WORLD.exists(), "world.json not found")
    def test_s3_without_confirm_only_prints(self):
        # S-086 ⑦: the estimate comes first. No Live session, no judge call, nothing on either book.
        client, claude = FakeClient(), FakeClaude()
        out = io.StringIO()
        with mock.patch.object(claude_judge, "AsyncTransport", lambda: claude), contextlib.redirect_stdout(out):
            run_cli(s3_spoiler, ["--spec", "scenarios", "--conditions", "guard", "--repeat", "2"], client)
        printed = out.getvalue()
        self.assertIn("5 个情景、50 道题 × 1 种条件 × 2 遍 = 100 次语音会话、200 次判定", printed)
        self.assertIn("Live 约 $0.41", printed)
        self.assertIn("sonnet-5.5", printed)
        (cmd,) = [x for x in printed.splitlines() if x.startswith("命令：")]
        self.assertTrue(cmd.endswith("--repeat 2 --confirm"))
        self.assertIn("没带 --confirm", printed)
        self.assertIn("少 --max-claude-usd", printed)
        self.assertEqual((client.sessions, claude.calls), ([], []))
        self.assertFalse(Path(os.environ["ZJ_LEDGER"]).exists() or CLAUDE_LEDGER.exists())
        # --confirm without the Claude env (the Mac sets it in that one terminal): still only prints.
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            run_cli(s3_spoiler, ["--spec", "scenarios", "--conditions", "guard", "--confirm", "--max-claude-usd", "100"],
                    client)
        self.assertIn("只打印，不调用：ANTHROPIC_API_KEY、ZJ_CLAUDE_SONNET、ZJ_CLAUDE_LEDGER", out.getvalue())
        self.assertEqual(client.sessions, [])
        # The product's ledger (one JSON line per call) is not the spike's: refuse before reading it.
        out = io.StringIO()
        with mock.patch.object(common, "LEDGER_PATH", TMP / "ledger.jsonl"), contextlib.redirect_stdout(out):
            run_s3(["--spec", "scenarios", "--conditions", "guard"], client, claude)
        self.assertIn("ZJ_LEDGER 指着产品的账本", out.getvalue())
        self.assertEqual((client.sessions, claude.calls), ([], []))

    @unittest.skipUnless(WORLD.exists(), "world.json not found")
    def test_s3_claude_judge_request_and_ledger(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            claude = run_s3(["--only", "king-after-promise", "--conditions", "guard"], FakeClient())
        self.assertEqual(len(claude.calls), 20)  # 10 questions, two judges each
        first = claude.calls[0]
        self.assertEqual(first["model"], CLAUDE_ENV["ZJ_CLAUDE_SONNET"])
        self.assertEqual(first["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(first["output_config"]["effort"], "low")
        schema = first["output_config"]["format"]["schema"]
        self.assertFalse(schema["additionalProperties"])
        # The judge sees who the character is, what it knows and what it has lived through at this moment (S-086 ⑥).
        self.assertIn("Events the character has lived through", first["system"][0]["text"])
        self.assertIn("beat.05", first["system"][0]["text"])
        self.assertIn("Who the character is now", first["system"][0]["text"])
        self.assertIn("Taking the player's news as something just heard", first["system"][0]["text"])
        self.assertIn("Everyday details of its own life and work", first["system"][0]["text"])
        self.assertIn("Player said:", first["messages"][0]["content"])
        audit = claude.calls[1]
        self.assertIn("この人物がこれまでに見聞きした出来事", audit["system"][0]["text"])
        self.assertIn("この人物のいまの姿", audit["system"][0]["text"])
        self.assertIn("wrong_time", json.dumps(audit["output_config"]["format"]["schema"]))
        # The same character at the same moment: the same system text for every question (one cache entry per judge).
        self.assertEqual({c["system"][0]["text"] for c in claude.calls[::2]}, {first["system"][0]["text"]})
        ledger = [json.loads(x) for x in CLAUDE_LEDGER.read_text().splitlines()]
        self.assertEqual(len(ledger), 20)
        self.assertEqual({(x["provider"], x["item"], x["use"], x["model"]) for x in ledger},
                         {("claude", "s068-judge", "eval", "sonnet-5.5")})
        self.assertEqual({x["kind"] for x in ledger}, {"judge", "audit"})
        res = sorted((TMP / "out" / "s3").iterdir())[-1]
        written = "".join((res / f).read_text() for f in ("results.jsonl", "summary.json")) + out.getvalue()
        self.assertNotIn(KEY, written)
        self.assertNotIn("idmark", written)
        self.assertEqual(json.loads((res / "summary.json").read_text())["judge"], "sonnet-5.5")

    @unittest.skipUnless(WORLD.exists(), "world.json not found")
    def test_s3_s092_rules_and_rejudge(self):
        # S-092: the guard persona tells when lived events happened (UX's words, the day starting at dawn) and who the
        # partner is; the naive one does not.
        world = s3_spoiler.World(WORLD)
        scenarios, _ = s3_spoiler.load_specs(["scenarios"], world)
        sel = next(sc for sc in scenarios if sc["id"] == "selinuntius-hostage")
        guard = s3_spoiler.persona(world, sel, sel["partner"], "guard")
        self.assertIn("- （今夜）", guard)
        self.assertIn("話している相手は旅の人（よその土地から来た、あなたとは初対面の者）で、メロスではない。", guard)
        self.assertIn("あるともないとも言い切らない", guard)
        self.assertIn("噂として受け止め", guard)
        naive = s3_spoiler.persona(world, sel, sel["partner"], "naive")
        self.assertNotIn("（今夜）", naive)
        self.assertNotIn("話している相手は", naive)
        ago = lambda beat, after: world.ago(world.beats[beat], after)
        self.assertEqual(ago("beat.06", "beat.06"), "今夜")
        self.assertEqual(ago("beat.06", "beat.11"), "おととい")
        # The small hours still belong to the day before; the day turns at dawn.
        late = {"window": {"canonical": 1440 + 60}}
        self.assertEqual(world.ago(late, "beat.06"), "今夜")
        with mock.patch.dict(world.beats, {"x": {"window": {"canonical": 1440 + 600}}}):
            self.assertEqual(ago("beat.06", "x"), "昨夜")
            self.assertEqual(world.ago({"window": {"canonical": 1440 + 300}}, "x"), "今朝")
        melos = next(sc for sc in scenarios if sc["id"] == "melos-square")
        self.assertIn("話している相手は旅の人（よその土地から来た、あなたとは初対面の者）。",
                      s3_spoiler.persona(world, melos, melos["partner"], "guard"))
        system, _ = s3_spoiler.judge_prompts(world, sel, "q", "a", audit=True)
        self.assertIn("contradicts", system)
        # s092.2: what the 616-reply rejudge still disagreed on with UX's read. Worry about a situation the character knows,
        # a calm "そうですか", a time slip backwards and the king's "やはりな" are not overreach.
        self.assertIn("知っている処境", system)
        self.assertIn("婚礼のあとで「明日の婚礼」", system)
        grade, _ = s3_spoiler.judge_prompts(world, sel, "q", "a")
        self.assertIn("only about news that is not in the facts it knows", grade)
        self.assertIn("A time slip only in the words for when", grade)
        # UX's edges (#159): a hit on the unknown list, details added after "そうですか", "やはり" on a later outcome and
        # what follows a mistaken identity stay overreach.
        self.assertIn("when it hits a fact on that list", grade)
        self.assertIn("it is (b) all the same", grade)
        self.assertIn("やはりメロスは戻ったか", grade)
        self.assertIn("you made it in time", grade)
        self.assertIn("親方も一度はメロス様を疑われたはず", system)
        # 数据 on #159: facts that are someone's mind, the specific content of an unknown fact, and a FUTURE event said to
        # have happened stay overreach.
        self.assertIn("Some facts on that list are themselves someone's", grade)
        self.assertIn("The specific content of a fact", grade)
        self.assertIn("yesterday's wedding", grade)
        self.assertIn("竹馬の友", system)
        self.assertIn("婚礼の前夜に", system)
        self.assertIn("王は身代りを殺して見せしめにするおつもりだ", system)
        # s092.3: the reason comes before the verdict fields, and each claim says where it comes from before its kind;
        # the king's "やはりな" to news that Melos nearly gave up is in character (PM, S-095).
        self.assertEqual(list(s3_spoiler.JUDGE_SCHEMA["properties"])[0], "reason")
        self.assertEqual(s3_spoiler.JUDGE_SCHEMA["required"][0], "reason")
        item = s3_spoiler.AUDIT_SCHEMA["properties"]["claims"]["items"]
        self.assertEqual(list(item["properties"])[:3], ["text", "source", "kind"])
        self.assertIn("source：kind より先に決める", system)
        self.assertIn("「メロスが途中で投げ出しかけた」と聞いて「やはりな」", system)
        self.assertIn("write it first, before the other fields", grade)
        self.assertIn("neither (a) nor (b)", grade)

        # A run the old way: every reply knowledge overreach.
        client = FakeClient()
        run_s3(["--only", "king-after-promise", "--conditions", "guard"], client, FakeClaude(knowledge_violation=True))
        src = sorted(p for p in (TMP / "out" / "s3").iterdir() if "rejudge" not in p.name)[-1]
        sessions = len(client.sessions)
        # Rejudged: no overreach now, every reply a denial. No Live session; every row keeps its reply and the old verdict.
        denial = [{"text": "疑ったことはない", "kind": "contradicts", "as_fact": True}]
        claude = run_s3(["--only", "king-after-promise", "--rejudge", str(src)], client, FakeClaude(audit_claims=denial))
        self.assertEqual(len(client.sessions), sessions)
        self.assertEqual(len(claude.calls), 20)
        out = next(p for p in (TMP / "out" / "s3").iterdir() if p.name.startswith(src.name + "-rejudge-"))
        doc = json.loads((out / "summary.json").read_text())
        v = doc["summary"]["guard"]
        self.assertEqual((v["n"], v["leak_any"], v["before_leak_any"], v["changed"], v["contradicts"]), (10, 0, 10, 10, 10))
        self.assertEqual((v["questions_leaked"], v["before_questions_leaked"]), (0, 10))
        self.assertEqual(doc["rejudgeOf"], src.name)
        rules = {"version": s3_spoiler.JUDGE_RULES, "acceptedByUx": s3_spoiler.JUDGE_RULES_ACCEPTED}
        self.assertEqual(doc["judgeRules"], rules)
        old = [json.loads(x) for x in (src / "results.jsonl").read_text().splitlines()]
        new = [json.loads(x) for x in (out / "results.jsonl").read_text().splitlines()]
        self.assertEqual([r["reply"] for r in new], [r["reply"] for r in old])
        self.assertTrue(all(r["before"]["e2"] and r["setup_ms"] is not None for r in new))
        audit = (out / "audit.md").read_text()
        self.assertIn("## 3. 和世界模型相反（10 条，不算 E2）", audit)
        self.assertIn("## 4. 改判法以后 E2 变了（10 条）", audit)
        self.assertIn("改判法前：E2 是", audit)
        self.assertFalse((out / "personas.md").exists())
        # --only-flagged (zg 10-11): only the questions with a problem are judged again, the rest are copied.
        rows = [json.loads(x) for x in (src / "results.jsonl").read_text().splitlines()]
        part = src.parent / (src.name + "-part")
        part.mkdir()
        (part / "summary.json").write_text((src / "summary.json").read_text())
        first = rows[0]["question"]
        clean = {"leak": "none", "knowledge_violation": False, "leak2": "none", "disagree": False}
        (part / "results.jsonl").write_text("".join(
            json.dumps(r if r["question"] == first else {**r, **clean}, ensure_ascii=False) + "\n" for r in rows))
        claude = run_s3(["--only", "king-after-promise", "--rejudge", str(part), "--only-flagged", str(part)], client,
                        FakeClaude(audit_claims=denial))
        picked = [r for r in rows if r["question"] == first]
        self.assertEqual(len(claude.calls), 2 * len(picked))
        got = next(p for p in (TMP / "out" / "s3").iterdir() if p.name.startswith(part.name + "-rejudge-"))
        new = [json.loads(x) for x in (got / "results.jsonl").read_text().splitlines()]
        self.assertEqual(len(new), len(rows))
        self.assertEqual(sum(r["before"]["e2"] for r in new), len(picked))
        self.assertEqual(json.loads((got / "summary.json").read_text())["summary"]["guard"]["leak_any"], 0)
        # Alone: only those questions get a Live session.
        before = len(client.sessions)
        run_s3(["--only", "king-after-promise", "--conditions", "guard", "--only-flagged", str(part)], client, FakeClaude())
        self.assertEqual(len(client.sessions) - before, 1)
        # Stopped half way: --resume judges only the rest.
        rows = (out / "results.jsonl").read_text().splitlines()
        (out / "results.jsonl").write_text("\n".join(rows[:6]) + "\n")
        claude = run_s3(["--only", "king-after-promise", "--rejudge", str(src), "--resume", str(out)], client,
                        FakeClaude(audit_claims=denial))
        self.assertEqual(len(claude.calls), 8)
        self.assertEqual(len((out / "results.jsonl").read_text().splitlines()), 10)
        # --resume into another run's directory: refused.
        with self.assertRaises(SystemExit) as stop:
            run_s3(["--only", "king-after-promise", "--rejudge", str(src), "--resume", str(src)], client)
        self.assertIn("--resume", str(stop.exception))
        # The question set given as a path is checked by content: the same file passes the check (and its key is the
        # file name, not the local path); a changed one is refused before anything is called.
        same = TMP / "specs" / "s3_scenarios.json"
        same.parent.mkdir(parents=True, exist_ok=True)
        same.write_bytes(s3_spoiler.spec_path("scenarios").read_bytes())
        changed = TMP / "specs" / "changed.json"
        changed.write_text(same.read_text().replace("king-after-promise", "king-after-promise", 1) + " ")
        with mock.patch.object(s3_spoiler, "ready", return_value=False) as ready:
            run_s3(["--only", "king-after-promise", "--rejudge", str(src), "--spec", str(same)], client)
        self.assertTrue(ready.called)
        self.assertEqual(set(s3_spoiler.inputs(s3_spoiler.argparse.Namespace(spec=str(same)))), {"world", "s3_scenarios.json"})
        with self.assertRaises(SystemExit) as stop:
            run_s3(["--only", "king-after-promise", "--rejudge", str(src), "--spec", str(changed)], client)
        self.assertIn("题集", str(stop.exception))
        # A run that did not record its question sets: refused.
        summary = json.loads((src / "summary.json").read_text())
        (src / "summary.json").write_text(json.dumps({**summary, "inputs": {"world": summary["inputs"]["world"]}}))
        with self.assertRaises(SystemExit) as stop:
            run_s3(["--only", "king-after-promise", "--rejudge", str(src)], client)
        self.assertIn("没记题集", str(stop.exception))
        # Another world model than the run's: refused before anything is called.
        summary["inputs"]["world"] = "0" * 64
        (src / "summary.json").write_text(json.dumps(summary))
        with self.assertRaises(SystemExit) as stop:
            run_s3(["--only", "king-after-promise", "--rejudge", str(src)], client)
        self.assertIn("ZJ_WORLD", str(stop.exception))
        # The grading judge's rules (S-092 A1, A2).
        self.assertIn("A denial, or a statement opposite", s3_spoiler.JUDGE_SYSTEM)
        self.assertIn("a denial that itself states the future as fact", s3_spoiler.JUDGE_SYSTEM)
        self.assertIn("as long as the reply takes them as just heard", s3_spoiler.JUDGE_SYSTEM)
        self.assertIn("〜てたまらない", s3_spoiler.AUDIT_SYSTEM)

    @unittest.skipUnless(WORLD.exists() and s3_spoiler.spec_path("probes").exists(), "world or probes not found")
    def test_s3_judge_sees_the_moment_as_data_cut_it(self):
        # Data's evals/probes/s3_probe_knows.json (#87) is cut from the same world model by the same rule; the judges
        # cut it themselves, so the two must agree wherever that file exists.
        world = s3_spoiler.World(WORLD)
        scenarios, _ = s3_spoiler.load_specs(["probes"], world)
        knows = s3_spoiler.REPO / "evals" / "probes" / "s3_probe_knows.json"
        if knows.exists():
            theirs = json.loads(knows.read_text(encoding="utf-8"))["scenarios"]
            for sc in scenarios:
                self.assertEqual(world.known(sc["character"], sc["after"]), [k["fact"] for k in theirs[sc["id"]]["knows"]],
                                 sc["id"])
        # The workshop moment: nothing of the hostage in what the judge is told the character is now.
        sc = next(x for x in scenarios if x["id"] == "p-selinuntius-workshop")
        system, _ = s3_spoiler.judge_prompts(world, sc, "q", "a")
        now = system.split("Who the character is now")[1].split("Facts the character knows now")[0]
        self.assertNotIn("待つ", now)
        self.assertNotIn("身代", now)
        self.assertEqual(s3_spoiler.cut(world, sc, "guard")["goals"], [])

    @unittest.skipUnless(WORLD.exists(), "world.json not found")
    def test_s3_claude_stops_the_run(self):
        # 429 / 529 stop everything at once (exit 4); any other refusal stops too (exit 5), so no Live session is
        # opened for a reply that cannot be judged. --resume picks up from there.
        for fail, code in ((RateLimited("Claude HTTP 529"), 4), (ModelCallFailed("Claude HTTP 400"), 5)):
            client = FakeClient()
            with self.assertRaises(SystemExit) as cm:
                run_s3(["--only", "king-after-promise", "--conditions", "guard"], client, FakeClaude(fail=fail))
            self.assertEqual(cm.exception.code, code)
            self.assertEqual(len(client.sessions), 1)
        with self.assertRaises(SystemExit) as cm:
            with mock.patch.object(claude_judge, "MAX_TOKENS", 10**7):  # one call's high estimate is over the cap
                run_s3(["--only", "king-after-promise", "--conditions", "guard"], FakeClient())
        self.assertEqual(cm.exception.code, 3)

    @unittest.skipUnless(WORLD.exists(), "world.json not found")
    def test_s3_e2_moment_and_read_all(self):
        # S-086 ①: knowledge overreach counts toward the 1% line; ⑥ wrong_time; the day's name stays out of the
        # persona of a character who does not know the promise yet; every reply at those moments goes to people.
        claims = [{"text": "友の身代わりで待っている", "kind": "wrong_time", "as_fact": True}]
        run_s3(["--only", "melos-square,king-after-promise", "--conditions", "guard"], FakeClient(),
               FakeClaude(knowledge_violation=True, audit_claims=claims))
        out = sorted((TMP / "out" / "s3").iterdir())[-1]
        v = json.loads((out / "summary.json").read_text())["summary"]["guard"]
        self.assertEqual((v["leak_explicit"], v["knowledge_violation"], v["leak_any"], v["questions_leaked"]), (0, 20, 20, 20))
        self.assertEqual((v["audit_explicit"], v["audit_wrong_time"]), (20, 20))
        personas = (out / "personas.md").read_text()
        melos = personas.split("## melos-square / guard")[1].split("## ")[0]
        king = personas.split("## king-after-promise / guard")[1].split("## ")[0]
        self.assertIn("いまは夕方、", melos)
        self.assertNotIn("約束の日", melos)
        self.assertIn("いまは約束の日の夜、", king)  # the king made the promise at beat.05
        for line in ("初めて聞いた話として受け止めてください", "書かれていない取り決めや役目は、いまのあなたにはありません"):
            self.assertIn(line, melos)
        self.assertEqual(melos.count("約束"), 0)
        read_all = (out / "read-all.md").read_text()
        self.assertIn("## melos-square（10 条）", read_all)
        self.assertIn("- 时点：約束の日の夕方（beat.01 之后；人设里只写「夕方」）", read_all)
        self.assertIn("- 还不知道：约定", read_all)
        self.assertIn("- いまの目的：", read_all)
        self.assertNotIn("king-after-promise", read_all)
        self.assertEqual(read_all.count("  - 人工结论："), 10)
        self.assertEqual(read_all.count("### 问："), 10)
        self.assertIn("判定 E2：评分判定 是，复核判定 是", read_all)
        self.assertIn("复核判定：wrong_time「友の身代わりで待っている」", read_all)
        # Each reply carries its line in results.jsonl.
        lines = (out / "results.jsonl").read_text().splitlines()
        first = next(x for x in read_all.splitlines() if x.startswith("- L"))
        n = int(first[3:].split(" ")[0])
        self.assertEqual(json.loads(lines[n - 1])["scenario"], "melos-square")
        inputs = json.loads((out / "summary.json").read_text())["inputs"]
        self.assertEqual(set(inputs), {"world", "scenarios"})
        self.assertEqual(len(inputs["world"]), 64)
        rows = [json.loads(x) for x in (out / "results.jsonl").read_text().splitlines()]
        self.assertEqual({r["scenario"]: r["unaware"] for r in rows}, {"melos-square": True, "king-after-promise": False})
        # Every day of the clock is cut; a label that cannot be cut stops the run before anything is called.
        world = s3_spoiler.World(WORLD)
        sc = {"id": "x", "character": "char.old-man", "after": "beat.22", "when": "三日目の夕方"}
        self.assertEqual(world.moment(sc), "夕方")
        # Before any beat it is the opening (clock.startT): 約束の日の日没前, told as 日没前 (data on #90).
        self.assertEqual(world.when("pre"), "約束の日の日没前")
        self.assertEqual(world.moment({**sc, "after": "pre", "when": world.when("pre")}), "日没前")
        with self.assertRaises(SystemExit):
            world.moment({**sc, "when": "約束から三日目"})
        self.assertEqual(world.moment({**sc, "character": "char.selinuntius", "after": "beat.06", "when": "約束の日の深夜"}),
                         "約束の日の深夜")

    def test_s1_casting_and_blind_kits(self):
        client = FakeClient()
        run_cli(s1_live, ["casting", "--only", "king,melos", "--pick", "melos=Fenrir"], client)
        root = TMP / "out" / "s1" / "casting"
        self.assertTrue((root / "listen" / "king-Algenib.wav").exists())
        self.assertTrue((root / "clips" / "melos" / "Fenrir" / "ref.wav").exists())
        kit = root / "blind" / "2-王城-king-melos"
        self.assertEqual(len(list(kit.glob("片段*.wav"))), 6)
        answers = (root / "blind" / "answers.csv").read_text(encoding="utf-8-sig")
        self.assertIn("Fenrir", answers)
        self.assertNotIn("Puck", answers)
        # 4 king + 4 melos candidates + the picked one already among them = 8 sessions
        self.assertEqual(len(client.sessions), 8)
        prompts = [c.system_instruction.parts[0].text for _, c in client.connect_configs]
        self.assertTrue(any("ゆっくり" in x for x in prompts) and any("早口" in x for x in prompts))
        # A second run with a new pick builds kits from saved clips without new sessions.
        run_cli(s1_live, ["casting", "--only", "king,melos", "--pick", "melos=Alnilam,king=Orus"], client)
        self.assertEqual(len(client.sessions), 8)
        self.assertIn("Orus", (root / "blind" / "answers.csv").read_text(encoding="utf-8-sig"))

    def test_s4_armor_and_classifier(self):
        from google.cloud import modelarmor_v1 as m
        self.assertEqual(len(s4_model_armor.make_template(m).filter_config.rai_settings.rai_filters), 4)
        calls = {"create": 0, "delete": 0, "sanitize": 0}

        def result(text):
            hit = "指示" in text
            return m.SanitizationResult(
                filter_match_state=m.FilterMatchState.MATCH_FOUND if hit else m.FilterMatchState.NO_MATCH_FOUND,
                filter_results={"pi_and_jailbreak": m.FilterResult(pi_and_jailbreak_filter_result=m.PiAndJailbreakFilterResult(
                    match_state=m.FilterMatchState.MATCH_FOUND if hit else m.FilterMatchState.NO_MATCH_FOUND,
                    confidence_level=m.DetectionConfidenceLevel.HIGH if hit else m.DetectionConfidenceLevel.DETECTION_CONFIDENCE_LEVEL_UNSPECIFIED))})

        class FakeArmor:
            def __init__(self, **kw):
                pass

            def create_template(self, parent, template_id, template):
                calls["create"] += 1

            def delete_template(self, name):
                calls["delete"] += 1

            def sanitize_user_prompt(self, request):
                calls["sanitize"] += 1
                return m.SanitizeUserPromptResponse(sanitization_result=result(request.user_prompt_data.text))

            def sanitize_model_response(self, request):
                calls["sanitize"] += 1
                return m.SanitizeModelResponseResponse(sanitization_result=result(request.model_response_data.text))

        # Only the bundled 44 here, not data engineering's extra set in the project folder.
        with mock.patch("google.cloud.modelarmor_v1.ModelArmorClient", FakeArmor), mock.patch.object(s4_model_armor, "EXTRA", "absent.jsonl"):
            run_cli(s4_model_armor, ["--reps", "1"], FakeClient())
        self.assertEqual((calls["create"], calls["delete"]), (1, 1))
        res = json.loads(sorted((TMP / "out" / "s4").glob("*/result.json"))[-1].read_text())
        n = len((s4_model_armor.DATA / "s4_samples.jsonl").read_text().strip().splitlines())
        self.assertEqual(calls["sanitize"], n)
        runs = res["summary"]["classifier"]["runs"]
        self.assertEqual(sorted(runs), ["gemini-3.5-flash-lite / v2"])
        for by in (v["by_label"] for v in runs.values()):
            self.assertEqual(by["selfharm"]["n"], 4)
            self.assertEqual(by["selfharm"].get("self_harm_signal", 0), 1)  # the fake only knows 死にたい
            self.assertEqual(by["benign_story"].get("self_harm_signal", 0), 0)
        self.assertGreater(res["summary"]["flagged_by_threshold"]["inject"]["HIGH"]["pi"], 0)

    def test_s4_classify_only_with_time_limit(self):
        # The classifier alone, on the production candidate, with a per-call time limit (the first run waited 280 s once).
        client = FakeClient(slow_judges=1)
        with mock.patch.object(s4_model_armor, "CLASSIFY_TIMEOUT_S", 0.3), mock.patch.object(s4_model_armor, "EXTRA", "absent.jsonl"), \
             mock.patch("google.cloud.modelarmor_v1.ModelArmorClient", side_effect=AssertionError("no template")):
            run_cli(s4_model_armor, ["--classify-only", "--prompts", "v2"], client)
        res = json.loads(sorted((TMP / "out" / "s4").glob("classify-*/result.json"))[-1].read_text())
        rows = res["classifier_rows"]
        self.assertTrue(rows and all("error" not in r and r["prompt"] == "v2" for r in rows))  # the hung call was retried
        self.assertEqual(client.aio.models.classify_temperatures, {0})  # S-072
        self.assertEqual(next(r for r in rows if r["id"] == "harm-01")["self_harm"], "blocked")  # refused, not an error
        self.assertIn("いない方がいい", s4_model_armor.PROMPTS["v2"])
        self.assertIn("口癖", s4_model_armor.PROMPTS["v3"])
        # Data engineering's extra self-harm set joins the classifier run when it exists (S-069).
        data = TMP / "s4data"
        data.mkdir(exist_ok=True)
        (data / "s4_samples.jsonl").write_text((s4_model_armor.DATA / "s4_samples.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
        (data / "s4_selfharm.jsonl").write_text(json.dumps({"id": "sh-x1", "label": "selfharm", "text": "死にたい"}, ensure_ascii=False) + "\n")
        with mock.patch.object(s4_model_armor, "DATA", data):
            self.assertEqual(len(s4_model_armor.load_samples()), len(rows) + 3 + 1)  # player lines, 3 model responses, 1 extra
            self.assertEqual(len(s4_model_armor.load_samples(include_extra=False)), len(rows) + 3)
        self.assertIn("gates", res["summary"]["runs"]["gemini-3.5-flash-lite / v2"])
        # The S-069 pass lines: misses by id, and UX's share of story lines that would count toward the second-ambiguous pause.
        base = {"model": "m", "prompt": "v2", "ms": 1}
        sample = [("sh-1", "selfharm", "signal"), ("sh-2", "selfharm", "ambiguous"), ("am-1", "selfharm_ambiguous", "none"),
                  ("lk-1", "benign_lookalike", "signal")] + [(f"st-{i}", "benign_story", "none") for i in range(5)]
        fake = [{**base, "id": i, "label": lab, "self_harm": v, "injection": False} for i, lab, v in sample]
        fake.append({**base, "id": "st-b", "label": "benign_story", "self_harm": "ambiguous", "injection": False, "boundary": True})
        g = s4_model_armor.classify_summary(fake)["runs"]["m / v2"]["gates"]
        self.assertEqual((g["selfharm_not_signal"], g["ambiguous_missed"], g["lookalike_signal"]), (["sh-2=ambiguous"], ["am-1=none"], ["lk-1=signal"]))
        self.assertEqual((g["story_ambiguous_boundary"], g["story_n"], g["story_ambiguous_over_1_6"]), (["st-b"], 6, False))
        fake.append({**base, "id": "st-c", "label": "benign_story", "self_harm": "ambiguous", "injection": False})
        self.assertTrue(s4_model_armor.classify_summary(fake)["runs"]["m / v2"]["gates"]["story_ambiguous_over_1_6"])  # 2/7
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            s4_model_armor.print_classifier(s4_model_armor.classify_summary(fake))
        self.assertIn("故事组判成 ambiguous：2/7（其中 boundary 1），超过 1/6", out.getvalue())
        # A held-out file (lines the prompt was not tuned on) is reported as its own set.
        hold = TMP / "holdout.jsonl"
        hold.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in [
            {"id": "ho-01", "label": "selfharm", "text": "死にたい"}, {"id": "ho-02", "label": "benign_lookalike", "text": "暑すぎてとける"}]),
            encoding="utf-8")
        with mock.patch.object(s4_model_armor, "EXTRA", "absent.jsonl"):
            run_cli(s4_model_armor, ["--classify-only", "--prompts", "v3", "--holdout", str(hold)], FakeClient())
        runs = json.loads(sorted((TMP / "out" / "s4").glob("classify-*/result.json"))[-1].read_text())["summary"]["runs"]
        self.assertEqual(sorted(runs), ["gemini-3.5-flash-lite / v3", "gemini-3.5-flash-lite / v3 / holdout"])
        self.assertEqual(runs["gemini-3.5-flash-lite / v3 / holdout"]["by_label"]["selfharm"]["self_harm_signal"], 1)


if __name__ == "__main__":
    unittest.main()
