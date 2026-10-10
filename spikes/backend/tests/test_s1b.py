"""Offline self-test for the S-1b voice proxy: a real HTTP/WebSocket server on 127.0.0.1, a fake Live.

  uv run python -m unittest tests.test_s1b -v

No network beyond localhost, no credentials, no cost.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import struct
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from tests.test_offline import TMP, FakeClient  # sets ZJ_PROJECT / ZJ_OUT / ZJ_LEDGER for the run

os.environ["ZJ_S1B_SECRET_DIR"] = str(TMP / "secret")

import uvicorn  # noqa: E402
from websockets.asyncio.client import connect  # noqa: E402

from zj_spike import common, s1b_proxy as sp  # noqa: E402

SPIKES = Path(__file__).resolve().parents[1]
CODE = "ABCD-EFGH-JKMN"
PCM = b"\x00\x00" * 3200  # 0.2 s of silence


class Server:
    """Runs the proxy app on a free localhost port inside the test's event loop."""

    def __init__(self, hub: sp.Hub):
        self.hub = hub
        self.server = uvicorn.Server(uvicorn.Config(sp.create_app(hub), host="127.0.0.1", port=0, log_level="error",
                                                    access_log=False, server_header=False))

    async def __aenter__(self):
        self.task = asyncio.create_task(self.server.serve())
        while not self.server.started:
            await asyncio.sleep(0.01)
        port = self.server.servers[0].sockets[0].getsockname()[1]
        self.base = f"http://127.0.0.1:{port}"
        self.ws = f"ws://127.0.0.1:{port}/v1/playthroughs/s1b/live"
        return self

    async def __aexit__(self, *exc):
        self.server.should_exit = True
        await self.task


def make_hub(client=None, **limits) -> sp.Hub:
    log = TMP / "s1b-log" / f"{id(client)}.jsonl"
    return sp.Hub(sp.hash_code(CODE, iterations=1000), client_factory=lambda: client or FakeClient(),
                  limits=sp.Limits(**limits), log_path=log)


async def login(base: str) -> str:
    import httpx

    async with httpx.AsyncClient() as http:
        r = await http.post(f"{base}/v1/auth/login", json={"inviteCode": CODE.lower()}, headers={"Origin": base})
        assert r.status_code == 200, r.text
        return r.cookies[sp.COOKIE]


async def recv_until(ws, kind: str, timeout=5.0):
    """Collect messages until one of `kind` arrives; returns (that message, everything seen)."""
    seen = []
    while True:
        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
        seen.append(raw)
        if isinstance(raw, str) and json.loads(raw)["type"] == kind:
            return json.loads(raw), seen


async def press(ws, seq: int, pcm: bytes = PCM, release: bool = True):
    await ws.send(json.dumps({"type": "activity_start", "turnId": f"t{seq}", "turnSeq": seq}))
    for i in range(0, len(pcm), sp.CHUNK_BYTES):
        await ws.send(bytes([sp.UP]) + struct.pack(">I", seq) + pcm[i : i + sp.CHUNK_BYTES])
    if release:
        await ws.send(json.dumps({"type": "activity_end", "turnId": f"t{seq}", "turnSeq": seq}))


class S1b(unittest.TestCase):
    def setUp(self):
        Path(os.environ["ZJ_LEDGER"]).unlink(missing_ok=True)

    def test_code_hash(self):
        h = sp.hash_code(CODE, iterations=1000)
        self.assertTrue(sp.check_code("abcd efgh jkmn", h))
        self.assertFalse(sp.check_code("ABCD-EFGH-JKMP", h))
        self.assertFalse(sp.check_code("", h))
        self.assertRegex(sp.new_code(), r"^[2-9A-HJKMNP-Z]{4}-[2-9A-HJKMNP-Z]{4}-[2-9A-HJKMNP-Z]{4}$")

    def test_newcode_writes_private_files_and_prints_no_code(self):
        with mock.patch("builtins.print") as p:
            sp.cmd_newcode(type("A", (), {"force": True})())
        code = sp.CODE_FILE.read_text().strip()
        self.assertEqual(sp.CODE_FILE.stat().st_mode & 0o777, 0o600)
        self.assertEqual(sp.ENV_FILE.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(code, " ".join(str(a) for c in p.call_args_list for a in c.args))
        self.assertTrue(sp.check_code(code, sp.code_hash_from_env()))

    def test_telemetry_keeps_numbers_and_fixed_words_only(self):
        clean = sp.sanitize_telemetry({"item": "t1", "route": "airpods", "clientReleaseToAudibleMs": 1480.26,
                                       "text": "王城に行く", "route2": "x", "network": "4G LTE!", "turnSeq": 3, "ok": True})
        self.assertEqual(clean, {"item": "t1", "route": "airpods", "clientReleaseToAudibleMs": 1480.3, "turnSeq": 3})

    def test_smoke_passes_against_local_server(self):
        async def run():
            hub = make_hub()
            async with Server(hub) as srv:
                res = await sp.smoke(srv.base, code=CODE, anon_only=False, utterances=[("a", PCM), ("b", PCM)])
            return hub, res

        hub, res = asyncio.run(run())
        failed = [c for c in res.checks if not c.ok]
        self.assertEqual(failed, [])
        self.assertEqual(len(res.turns), 2)
        self.assertTrue(all(t["serverReleaseToFirstAudioMs"] is not None for t in res.turns))
        self.assertEqual(res.turns[0]["playerTranscript"], "（音声）")
        self.assertGreater(hub.spent, 0)
        # The log never carries what anyone said.
        log = hub.log_path.read_text()
        self.assertNotIn("音声", log)
        self.assertNotIn("さようで", log)
        self.assertIn('"event": "turn"', log)

    def test_smoke_runs_once_more_when_only_voice_failed(self):
        """up's smoke test: a new service account's Gemini permission can lag; one retry, voice failures only."""
        async def run(fail_first_connects: int):
            async with Server(make_hub(FakeClient(fail_first_connects=fail_first_connects))) as srv:
                with redirect_stdout(io.StringIO()):
                    return await sp.smoke_retrying_voice(srv.base, retry_s=0.01, code=CODE, anon_only=False,
                                                         utterances=[("a", PCM)])

        self.assertTrue(asyncio.run(run(1)).ok)
        failed = [c.name for c in asyncio.run(run(2)).checks if not c.ok]
        self.assertEqual(failed, ["会话就绪"])

    def test_only_voice_failures_qualify_for_the_retry(self):
        def result(*failed):
            r = sp.SmokeResult()
            for name in ["没有 Cookie 时 REST 被拒", "正确的测试码能登录", "会话就绪", "第 1 轮有声音回答"]:
                r.checks.append(sp.Check(name, name not in failed))
            return r

        self.assertTrue(sp.only_voice_failed(result("会话就绪")))
        self.assertTrue(sp.only_voice_failed(result("第 1 轮有声音回答")))
        self.assertFalse(sp.only_voice_failed(result()))
        self.assertFalse(sp.only_voice_failed(result("会话就绪", "没有 Cookie 时 REST 被拒")))
        self.assertFalse(sp.only_voice_failed(result("正确的测试码能登录")))

    def test_nothing_the_phone_sees_names_the_product(self):
        """D-017: no product name in the page, headers or cookie; welcome says the cookie arrived."""
        async def run():
            import httpx

            async with Server(make_hub()) as srv:
                async with httpx.AsyncClient() as http:
                    page = await http.get(f"{srv.base}/")
                    me = await http.get(f"{srv.base}/v1/me")
                    login = await http.post(f"{srv.base}/v1/auth/login", json={"inviteCode": CODE}, headers={"Origin": srv.base})
                token = login.cookies[sp.COOKIE]
                async with connect(srv.ws, origin=srv.base, additional_headers={"Cookie": f"{sp.COOKIE}={token}"}) as ws:
                    await ws.send(json.dumps({"type": "hello", "lastSeq": 0}))
                    welcome, _ = await recv_until(ws, "welcome")
                    await ws.send(json.dumps({"type": "focus", "character": "char.king"}))
                    error, _ = await recv_until(ws, "error")
            return page, me, login, welcome, error

        page, me, login, welcome, error = asyncio.run(run())
        seen = " ".join([page.text, me.text, login.text, json.dumps(error, ensure_ascii=False)]
                        + [f"{k}: {v}" for r in (page, me, login) for k, v in r.headers.items()]).lower()
        for word in ("zoujin", "走进物语", "zj_", "uvicorn"):
            self.assertNotIn(word, seen)
        self.assertTrue(welcome["cookieSeen"])
        self.assertEqual(json.loads((Path(sp.__file__).parent / "data" / "s1b_lines.json").read_text())["phone"][1],
                         "メロスという男を知っていますか。")

    def test_anon_only_smoke(self):
        async def run():
            async with Server(make_hub()) as srv:
                return await sp.smoke(srv.base, code=None, anon_only=True, utterances=[])

        res = asyncio.run(run())
        self.assertTrue(res.ok, res.checks)
        self.assertEqual(len(res.checks), 3)

    def test_barge_in_drops_old_audio_and_completes_new_turn(self):
        async def run():
            client = FakeClient()
            hub = make_hub(client)
            async with Server(hub) as srv:
                token = await login(srv.base)
                async with connect(srv.ws, origin=srv.base, additional_headers={"Cookie": f"{sp.COOKIE}={token}"}) as ws:
                    await ws.send(json.dumps({"type": "hello", "lastSeq": 0}))
                    await recv_until(ws, "welcome")
                    await ws.send(json.dumps({"type": "focus", "character": sp.CHARACTER}))
                    await recv_until(ws, "session_ready")
                    # A long reply, then the player presses again while it is still coming.
                    await ws.send(json.dumps({"type": "text", "turnId": "t1", "turnSeq": 1, "text": "長く話して"}))
                    while True:
                        raw = await asyncio.wait_for(ws.recv(), 5)
                        if isinstance(raw, bytes):
                            break
                    await press(ws, 2, release=False)
                    interrupted, _ = await recv_until(ws, "interrupted")
                    await ws.send(json.dumps({"type": "activity_end", "turnId": "t2", "turnSeq": 2}))
                    done, seen = await recv_until(ws, "turn_complete")
                    return interrupted, done, seen, client

        interrupted, done, seen, client = asyncio.run(run())
        self.assertEqual(interrupted["turnId"], "t1")
        self.assertEqual(done["turnId"], "t2")
        self.assertTrue(done["audio"])
        seqs = {struct.unpack(">I", f[1:5])[0] for f in seen if isinstance(f, bytes)}
        self.assertEqual(seqs, {2})  # nothing from turn 1 after the barge
        self.assertEqual(len(client.sessions), 1)

    def test_late_reply_transcript_still_reaches_the_page(self):
        async def run():
            client = FakeClient(late_transcript=True)
            async with Server(make_hub(client)) as srv:
                token = await login(srv.base)
                async with connect(srv.ws, origin=srv.base, additional_headers={"Cookie": f"{sp.COOKIE}={token}"}) as ws:
                    await ws.send(json.dumps({"type": "hello", "lastSeq": 0}))
                    await recv_until(ws, "welcome")
                    await ws.send(json.dumps({"type": "focus", "character": sp.CHARACTER}))
                    await recv_until(ws, "session_ready")
                    await ws.send(json.dumps({"type": "text", "turnId": "t1", "turnSeq": 1, "text": "こんばんは"}))
                    await recv_until(ws, "turn_complete")
                    late, _ = await recv_until(ws, "transcript")
                    return late

        late = asyncio.run(run())
        self.assertEqual((late["turnId"], late["speaker"], late["final"]), ("t1", sp.CHARACTER, True))
        self.assertTrue(late["text"])

    def test_origin_cookie_and_busy_guards(self):
        async def run():
            hub = make_hub(max_conns=1)
            async with Server(hub) as srv:
                import httpx

                async with httpx.AsyncClient() as http:
                    no_ct = await http.post(f"{srv.base}/v1/auth/login", content=json.dumps({"inviteCode": CODE}),
                                            headers={"Origin": srv.base, "Content-Type": "text/plain"})
                    tele = await http.post(f"{srv.base}/v1/telemetry", json={"events": []}, headers={"Origin": srv.base})
                token = await login(srv.base)
                hdr = {"Cookie": f"{sp.COOKIE}={token}"}
                async with connect(srv.ws, origin=srv.base, additional_headers=hdr):
                    async with connect(srv.ws, origin=srv.base, additional_headers=hdr) as second:
                        try:
                            await asyncio.wait_for(second.recv(), 3)
                            busy = None
                        except Exception as e:  # ConnectionClosed
                            busy = e.rcvd.code
                return no_ct.status_code, tele.status_code, busy

        no_ct, tele, busy = asyncio.run(run())
        self.assertEqual(no_ct, 403)
        self.assertEqual(tele, 401)
        self.assertEqual(busy, 4290)

    def test_login_rate_limit(self):
        async def run():
            import httpx

            async with Server(make_hub()) as srv:
                async with httpx.AsyncClient() as http:
                    codes = [(await http.post(f"{srv.base}/v1/auth/login", json={"inviteCode": "NOPE-NOPE-NOPE"},
                                              headers={"Origin": srv.base})).status_code for _ in range(6)]
                    good = await http.post(f"{srv.base}/v1/auth/login", json={"inviteCode": CODE}, headers={"Origin": srv.base})
            return codes, good.status_code

        codes, good = asyncio.run(run())
        self.assertEqual(codes, [401] * 5 + [429])
        self.assertEqual(good, 429)  # the address stays blocked for the window, even with the right code

    def test_budget_cap_turns_voice_off(self):
        async def run():
            hub = make_hub(max_usd=0.0001)
            async with Server(hub) as srv:
                first = await sp.smoke(srv.base, code=CODE, anon_only=False, utterances=[("a", PCM)])
                await asyncio.sleep(0.1)
                token = await login(srv.base)
                async with connect(srv.ws, origin=srv.base, additional_headers={"Cookie": f"{sp.COOKIE}={token}"}) as ws:
                    await ws.send(json.dumps({"type": "hello", "lastSeq": 0}))
                    welcome, _ = await recv_until(ws, "welcome")
                    await ws.send(json.dumps({"type": "focus", "character": sp.CHARACTER}))
                    degraded, _ = await recv_until(ws, "degraded")
            return first, welcome, degraded

        first, welcome, degraded = asyncio.run(run())
        self.assertTrue(first.ok)
        self.assertFalse(welcome["voice"]["enabled"])
        self.assertEqual(degraded["reason"], "budget")

    def test_quota_error_turns_voice_off(self):
        err = RuntimeError("1011 RESOURCE_EXHAUSTED: Quota exceeded")
        err._on_connect = True

        async def run():
            hub = make_hub(FakeClient(fail_with=err))
            async with Server(hub) as srv:
                res = await sp.smoke(srv.base, code=CODE, anon_only=False, utterances=[("a", PCM)])
            return hub, res

        hub, res = asyncio.run(run())
        self.assertFalse(res.ok)
        self.assertEqual(hub.voice_off_reason, "service")


class Image(unittest.TestCase):
    """The image runs as a non-root user. S-1b part 2 (2026-10-07) failed on Cloud Run because the build directory was
    copied under the deploy script's umask 077, so every code file in the image was 600 root:root."""

    def page(self, mode: int) -> Path:
        page = Path(tempfile.mkdtemp(dir=TMP))
        (page / "index.html").write_text("<p>s1b</p>")
        os.chmod(page / "index.html", mode)
        os.chmod(page, 0o700)
        return page

    def test_build_directory_is_readable_by_other_users(self):
        page = self.page(0o600)
        ctx = Path(tempfile.mkdtemp(dir=TMP))
        subprocess.run(["bash", str(SPIKES / "s1b_deploy.sh"), "_stage", str(ctx)], check=True, capture_output=True,
                       env={**os.environ, "ZJ_S1B_PAGE": str(page)})
        for name in ["Dockerfile", "pyproject.toml", "uv.lock", "zj_spike/s1b_proxy.py", "page/index.html"]:
            self.assertTrue((ctx / name).is_file(), name)
        self.assertEqual(list(ctx.rglob("__pycache__")), [])
        for p in [ctx, *ctx.rglob("*")]:
            want = 0o005 if p.is_dir() else 0o004
            self.assertEqual(p.stat().st_mode & want, want, f"{p.relative_to(ctx)} {oct(p.stat().st_mode)}")

    def test_selfcheck_passes_and_serves_the_page(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"ZJ_S1B_STATIC": str(self.page(0o644))}), redirect_stdout(out):
            self.assertEqual(sp.cmd_selfcheck(None), 0, out.getvalue())
        self.assertIn("测试页", out.getvalue())

    def test_no_path_cloud_run_reserves(self):
        """Cloud Run answers paths ending in "z" (e.g. /healthz) and /_ah/* at its front end, before IAM or the
        container, so the deploy script's private-service check always saw 404 (S-1b part 2, 2026-10-07)."""
        paths = [r.path for r in sp.create_app(make_hub()).routes]
        paths += re.findall(r'\$url(/[^"\s)]*)', (SPIKES / "s1b_deploy.sh").read_text())
        self.assertIn("/health", paths)
        self.assertIn("/", paths)
        for p in paths:
            self.assertFalse(p.rstrip("/").endswith("z") or p.startswith("/_ah/"), p)

    @unittest.skipIf(os.geteuid() == 0, "root can read every file, so this needs a normal user")
    def test_selfcheck_fails_on_unreadable_files(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"ZJ_S1B_STATIC": str(self.page(0o000))}), redirect_stdout(out):
            self.assertEqual(sp.cmd_selfcheck(None), 1)
        self.assertIn("index.html", out.getvalue())



class Upstream(unittest.TestCase):
    """S-1b part 2's third attempt failed on Cloud Run with a bare APIError: the Live refusal was never written down,
    and nothing had tried the service account's identity before deploying (2026-10-07)."""

    MESSAGE = ("Permission 'aiplatform.endpoints.predict' denied on resource '//aiplatform.googleapis.com/projects/"
               "offline-test/locations/us-central1/publishers/google/models/m' for s1b-proxy@offline-test.iam."
               "gserviceaccount.com (project 123456789012), see https://console.cloud.google.com/x")

    def refused(self):
        from google.genai import errors

        err = errors.APIError(1008, self.MESSAGE, None)  # what google-genai raises when Live closes the socket
        err._on_connect = True
        return err

    def test_redact_keeps_the_reason_and_drops_names(self):
        out = common.redact(self.MESSAGE, "offline-test")
        self.assertIn("aiplatform.endpoints.predict", out)
        for gone in ("offline-test", "123456789012", "@", "https://"):
            self.assertNotIn(gone, out)

    def test_upstream_kind(self):
        class E(Exception):
            def __init__(self, code, text="", status=None):
                super().__init__(text)
                self.code, self.status = code, status

        self.assertEqual(common.upstream_kind(E(1008, "Permission denied")), "permission")
        self.assertEqual(common.upstream_kind(E(1008, "policy")), "policy")
        self.assertEqual(common.upstream_kind(E(1007, "invalid argument")), "invalid")
        self.assertEqual(common.upstream_kind(E(1011, "RESOURCE_EXHAUSTED")), "quota")
        self.assertEqual(common.upstream_kind(E(404, "", "NOT_FOUND")), "not_found")
        self.assertEqual(common.upstream_kind(E(1011, "internal")), "unavailable")
        self.assertEqual(common.upstream_kind(E(None, "boom")), "other")

    def test_refused_session_is_logged_redacted_and_the_phone_gets_one_word(self):
        async def run():
            hub = make_hub(FakeClient(fail_with=self.refused()))
            async with Server(hub) as srv:
                with redirect_stdout(io.StringIO()):
                    res = await sp.smoke(srv.base, code=CODE, anon_only=False, utterances=[("a", PCM)])
            return hub, res

        hub, res = asyncio.run(run())
        failed = [c for c in res.checks if not c.ok]
        self.assertEqual([c.name for c in failed], ["会话就绪"])
        sent = json.loads(failed[0].detail)["error"]
        self.assertEqual(sent["upstream"], "permission")
        self.assertNotIn("aiplatform", failed[0].detail)  # the phone never sees the upstream text
        row = next(json.loads(l) for l in hub.log_path.read_text().splitlines() if '"session_error"' in l)
        self.assertEqual(row["upstreamCode"], 1008)
        self.assertIn("aiplatform.endpoints.predict", row["upstreamMessage"])
        for gone in ("offline-test", "123456789012", "@", "https://"):
            self.assertNotIn(gone, row["upstreamMessage"])
        self.assertIsNone(hub.voice_off_reason)  # not a quota error: voice stays on for the next try

    def test_impersonation_borrows_the_account_without_a_quota_project(self):
        from google.auth import impersonated_credentials
        from google.oauth2.credentials import Credentials

        calls = []

        def fake_default(scopes=None, quota_project_id=None):
            calls.append(quota_project_id)
            return Credentials(token="t", quota_project_id=quota_project_id), None

        with mock.patch("google.auth.default", fake_default):
            with mock.patch.dict(os.environ, {"ZJ_IMPERSONATE_SA": "s1b-proxy@offline-test.iam.gserviceaccount.com"}):
                creds = common.credentials()
                with mock.patch.dict(os.environ, {"K_SERVICE": "s-test"}):
                    on_run = common.credentials()
        self.assertIsInstance(creds, impersonated_credentials.Credentials)
        self.assertEqual(creds.service_account_email, "s1b-proxy@offline-test.iam.gserviceaccount.com")
        self.assertIsNone(creds.quota_project_id)  # the model calls look exactly like Cloud Run's
        self.assertEqual(calls[0], "offline-test")  # the token request itself is billed to this project
        self.assertNotIsInstance(on_run, impersonated_credentials.Credentials)

    def sacheck(self, client, wait=5.0):
        import argparse

        out = io.StringIO()
        with mock.patch.object(common, "genai_client", lambda location: client), \
             mock.patch.dict(os.environ, {"ZJ_IMPERSONATE_SA": "s1b-proxy@offline-test.iam.gserviceaccount.com"}), \
             redirect_stdout(out):
            code = sp.cmd_sacheck(argparse.Namespace(wait=wait, interval=0.01))
        return code, out.getvalue()

    def test_sacheck_waits_for_the_permission(self):
        client = FakeClient(fail_first_connects=2)
        code, out = self.sacheck(client)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(client.connect_configs), 3)
        self.assertIn("第 3 次", out)

    def test_sacheck_stops_at_once_on_quota_and_gives_up_after_wait(self):
        quota = RuntimeError("1011 RESOURCE_EXHAUSTED: Quota exceeded")
        quota._on_connect = True
        client = FakeClient(fail_with=quota)
        code, out = self.sacheck(client)
        self.assertEqual((code, len(client.connect_configs)), (1, 1))
        code, out = self.sacheck(FakeClient(fail_with=self.refused()), wait=0.05)
        self.assertEqual(code, 1)
        self.assertNotIn("offline-test", out)

    def test_deploy_needs_sacheck_and_cleans_it_up(self):
        script = (SPIKES / "s1b_deploy.sh").read_text()
        body = lambda name: re.search(rf"\n{name}\(\) \{{\n(.*?)\n\}}\n", script, re.S).group(1)
        self.assertIn('[[ -f "$SA_OK_FILE" ]] || die', body("cmd_up"))
        self.assertIn('"$SA_OK_FILE"', body("cmd_down"))
        self.assertIn("iamcredentials.googleapis.com", body("cmd_prepare"))
        self.assertIn("show_session_errors", body("cmd_up"))

if __name__ == "__main__":
    unittest.main()
