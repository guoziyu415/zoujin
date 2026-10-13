"""S-1b: a minimal voice proxy for the phone test, speaking a subset of api-contract §3, plus its smoke test.

  uv run python -m zj_spike.s1b_proxy newcode              # one-time test code into ~/.zoujin-spike/ (never printed)
  uv run python -m zj_spike.s1b_proxy serve                # http://localhost:8080 — part one, no deployment
  uv run python -m zj_spike.s1b_proxy smoke                # auth checks + voice turns against localhost
  uv run python -m zj_spike.s1b_proxy smoke --url-file     # same against the address s1b_deploy.sh saved
  uv run python -m zj_spike.s1b_proxy smoke --anon-only    # only: anonymous access is refused
  python -m zj_spike.s1b_proxy selfcheck                    # inside the built image, before s1b_deploy.sh pushes it
  ZJ_IMPERSONATE_SA=… uv run python -m zj_spike.s1b_proxy sacheck   # Live as the service account, before deploying

Plan and rules: backend/spikes/s1b-plan.md. One character (メロス), no narrator, no database.
Nothing the player says is stored or logged: log lines carry timings, sizes and costs only.

Supported (api-contract v0.3): POST /v1/auth/login, /logout, GET /v1/me, POST /v1/telemetry;
WebSocket /v1/playthroughs/s1b/live with hello/welcome, near/far, focus/unfocus, session_preparing/
session_ready, activity_start/activity_end, 0x01/0x02 audio frames, text, transcript, interrupted,
turn_complete (with serverReleaseToFirstAudioMs), degraded, goaway, ping/pong, error.
Not supported: retract (needs the narrator), commit/turn_settled, suggestions and everything after them.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import struct
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import Request, WebSocket  # module level: FastAPI resolves the string annotations from here
from google.genai import types

from . import common
from .live_util import CHUNK_BYTES, CHUNK_MS, IN_RATE, JA_RULE, live_config
from .s1_live import PROPER_NOUNS

SECRET_DIR = Path(os.environ.get("ZJ_S1B_SECRET_DIR", Path.home() / ".zoujin-spike"))
CODE_FILE = SECRET_DIR / "s1b-code"
ENV_FILE = SECRET_DIR / "s1b.env"
URL_FILE = SECRET_DIR / "s1b-url"

PLAYTHROUGH = "s1b"
CHARACTER = "char.melos"
COOKIE = "sid"  # neutral on purpose: nothing the phone sees names the product (D-017)
SESSION_TTL_S = 12 * 3600
UP, DOWN = 0x01, 0x02
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # no 0/O, 1/I/L

PERSONA = (
    "あなたは太宰治『走れメロス』のメロスです。村の牧人で、妹の婚礼の支度のために、"
    "十里はなれたシラクスの市に来たところです。まっすぐで激しやすく、人を疑うことを恥だと思っています。"
    "町が妙に静かなことに気づき、王が人を殺すと聞いて、腹を立てています。"
    "話し相手は、この広場で出会った旅人です。一度に二文までで、短く答えてください。"
    "これから先に起こることは知りません。ゲームや AI の話はしません。"
) + JA_RULE


# ---------------------------------------------------------------- the one-time test code


def new_code() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(12))  # ≈ 59 bits
    return "-".join(raw[i : i + 4] for i in range(0, 12, 4))


def _norm_code(code: str) -> bytes:
    return re.sub(r"[\s-]", "", code).upper().encode()


def hash_code(code: str, *, salt: bytes | None = None, iterations: int = 200_000) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", _norm_code(code), salt, iterations)
    return f"pbkdf2_sha256:{iterations}:{salt.hex()}:{dk.hex()}"


def check_code(code: str, stored: str) -> bool:
    try:
        algo, iterations, salt, want = stored.split(":")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256" or not code or len(code) > 40:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", _norm_code(code), bytes.fromhex(salt), int(iterations))
    return hmac.compare_digest(dk.hex(), want)


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)


def code_hash_from_env() -> str | None:
    if os.environ.get("ZJ_S1B_CODE_HASH"):
        return os.environ["ZJ_S1B_CODE_HASH"]
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("ZJ_S1B_CODE_HASH="):
                return line.split("=", 1)[1].strip()
    return None


# ---------------------------------------------------------------- server state


@dataclass
class Limits:
    max_usd: float = float(os.environ.get("ZJ_S1B_MAX_USD", "3"))
    max_conns: int = int(os.environ.get("ZJ_S1B_MAX_CONNS", "4"))
    conn_max_s: float = float(os.environ.get("ZJ_S1B_CONN_MAX_MIN", "30")) * 60
    login_fail_per_ip: int = 5
    login_fail_window_s: float = 600
    login_fail_total: int = 100
    extra_origins: tuple[str, ...] = tuple(o for o in os.environ.get("ZJ_S1B_EXTRA_ORIGINS", "").split(",") if o)
    voice: str = os.environ.get("ZJ_S1B_VOICE", "Puck")
    thinking: str | None = os.environ.get("ZJ_S1B_THINKING") or None


class Hub:
    """Everything shared by all connections. The service runs as one instance, so memory is the store."""

    def __init__(self, code_hash: str, client_factory, limits: Limits | None = None, log_path: Path | None = None):
        self.code_hash = code_hash
        self.client_factory = client_factory
        self.limits = limits or Limits()
        self.log_path = log_path
        self.tokens: dict[str, float] = {}
        self.failures: dict[str, list[float]] = {}
        self.failures_total = 0
        self.spent = 0.0
        self.conns = 0
        self.voice_off_reason: str | None = None
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = self.client_factory()
        return self._client

    def log(self, event: str, **fields) -> None:
        """One JSON line: Cloud Run turns it into jsonPayload. Only numbers, booleans and fixed words, plus a failed
        model call's error message with project, addresses and accounts removed (common.upstream_error)."""
        line = json.dumps({"severity": "INFO", "kind": "s1b", "event": event, **fields}, ensure_ascii=False)
        print(line, flush=True)
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a") as f:
                f.write(line + "\n")

    def charge(self, usd: float, what: str) -> None:
        self.spent += usd
        try:
            common.charge(usd, what)
        except common.BudgetExceeded:
            self.voice_off_reason = "budget"
        if self.spent >= self.limits.max_usd and self.voice_off_reason is None:
            self.voice_off_reason = "budget"
            self.log("voice_off", reason="budget", spentUsd=round(self.spent, 4))

    def valid(self, token: str | None) -> bool:
        exp = self.tokens.get(token or "")
        if exp is None:
            return False
        if exp < time.time():
            self.tokens.pop(token, None)
            return False
        return True

    def login_blocked(self, ip: str) -> int | None:
        """Seconds to wait, or None when this address may try again."""
        if self.failures_total >= self.limits.login_fail_total:
            return 3600
        now = time.time()
        recent = [t for t in self.failures.get(ip, []) if now - t < self.limits.login_fail_window_s]
        self.failures[ip] = recent
        if len(recent) >= self.limits.login_fail_per_ip:
            return int(self.limits.login_fail_window_s - (now - recent[0])) + 1
        return None

    def login_failed(self, ip: str) -> None:
        self.failures.setdefault(ip, []).append(time.time())
        self.failures_total += 1


def _expected_origin(scheme: str, host: str | None) -> str | None:
    if not host:
        return None
    return f"{'https' if scheme in ('https', 'wss') else 'http'}://{host}"


def same_origin(hub: Hub, headers, scheme: str) -> bool:
    origin = headers.get("origin")
    return bool(origin) and (origin == _expected_origin(scheme, headers.get("host")) or origin in hub.limits.extra_origins)


# ---------------------------------------------------------------- one WebSocket connection


@dataclass
class TurnState:
    turn_id: str
    seq: int
    via: str
    pressed: float
    released: float | None = None
    first_audio: float | None = None
    first_in_text: float | None = None
    up_bytes: int = 0
    down_bytes: int = 0
    player_text: str = ""
    char_text: str = ""
    completed: bool = False
    completed_at: float | None = None
    interrupted: bool = False


@dataclass
class Counters:
    dropped_up: int = 0
    dropped_down: int = 0
    stale_completes: int = 0
    drain_timeouts: int = 0
    turns: int = 0
    barges: int = 0


class LiveConn:
    DRAIN_MAX_S = 1.5  # after a barge, old audio is dropped until Live confirms, at most this long
    STALE_COMPLETE_S = 0.5  # a turn_complete this soon after Live's `interrupted` belongs to the old turn
    LATE_TEXT_S = 3.0  # transcripts can trail turn_complete (S-1 voices); keep them for the last turn this long

    def __init__(self, hub: Hub, ws):
        self.hub, self.ws = hub, ws
        self.lock = asyncio.Lock()
        self.holder: asyncio.Task | None = None
        self.ready: asyncio.Future | None = None
        self.session = None
        self.open_started: float | None = None
        self.focused = False
        self.turn: TurnState | None = None
        self.model_open = False
        self.drain_until = 0.0
        self.interrupted_at = 0.0
        self.pending_usage = None
        self.late: set[asyncio.Task] = set()
        self.n = Counters()
        self.started = time.monotonic()

    # -- sending

    async def send(self, obj: dict) -> None:
        async with self.lock:
            await self.ws.send_text(json.dumps(obj, ensure_ascii=False))

    async def send_audio(self, seq: int, pcm: bytes) -> None:
        async with self.lock:
            await self.ws.send_bytes(bytes([DOWN]) + struct.pack(">I", seq) + pcm)

    async def error(self, code: str, message: str, retryable: bool = False, upstream: str | None = None) -> None:
        body = {"code": code, "message": message, "retryable": retryable, "retryAfterSeconds": None}
        if upstream:
            body["upstream"] = upstream  # one fixed word (common.upstream_kind), never the upstream text
        await self.send({"type": "error", "error": body})

    # -- main loop

    async def run(self) -> None:
        deadline = self.started + self.hub.limits.conn_max_s
        try:
            while True:
                left = deadline - time.monotonic()
                if left <= 0:
                    await self.send({"type": "goaway", "reason": "maintenance", "reconnectAfterMs": 1000})
                    await self.ws.close(code=1000)
                    break
                try:
                    msg = await asyncio.wait_for(self.ws.receive(), timeout=left)
                except asyncio.TimeoutError:
                    continue
                if msg["type"] == "websocket.disconnect":
                    break
                if msg.get("bytes") is not None:
                    await self.on_audio(msg["bytes"])
                elif msg.get("text") is not None:
                    try:
                        data = json.loads(msg["text"])
                    except ValueError:
                        await self.error("bad_request", "JSON ではありません")
                        continue
                    if isinstance(data, dict):
                        await self.on_json(data)
        finally:
            await self.close_session()
            for t in list(self.late):
                t.cancel()
            self.hub.log("conn_end", seconds=round(time.monotonic() - self.started), turns=self.n.turns, barges=self.n.barges,
                         droppedUp=self.n.dropped_up, droppedDown=self.n.dropped_down,
                         staleCompletes=self.n.stale_completes, drainTimeouts=self.n.drain_timeouts)

    async def on_json(self, m: dict) -> None:
        kind = m.get("type")
        if kind == "hello":
            self.turn, self.model_open = None, False
            off = self.hub.voice_off_reason
            # cookieSeen: reaching here means the handshake carried a valid cookie (without one the socket
            # is closed with 4001 before any message), which is what the in-app-browser check needs.
            await self.send({"type": "welcome", "lastSeq": 0, "cookieSeen": True,
                             "voice": {"enabled": off is None, "degraded": off is not None, "minutesLeftToday": 60},
                             "lastTurn": None,
                             "pending": {"reveal": None, "confirm": None, "actEnd": None, "safetyPause": False, "approach": None}})
        elif kind == "near":
            if m.get("character") == CHARACTER and self.hub.voice_off_reason is None:
                self.start_open()
        elif kind == "far":
            if not self.focused:
                await self.close_session()
        elif kind == "focus":
            await self.on_focus(m.get("character"))
        elif kind == "unfocus":
            self.focused = False
            await self.close_session()
        elif kind == "activity_start":
            await self.begin_turn(str(m.get("turnId", "")), int(m.get("turnSeq", 0)), "voice")
        elif kind == "activity_end":
            await self.on_release(str(m.get("turnId", "")))
        elif kind == "text":
            await self.on_text(m)
        elif kind == "ping":
            await self.send({"type": "pong"})
        else:
            await self.error("unsupported", "この試験版では使えません")

    # -- the Live session (one task owns it from open to close)

    def start_open(self) -> None:
        if self.session is not None or (self.holder and not self.holder.done()):
            return
        loop = asyncio.get_running_loop()
        self.ready = loop.create_future()
        self.ready.add_done_callback(lambda f: f.cancelled() or f.exception())
        self.open_started = time.perf_counter()
        self.holder = asyncio.create_task(self._hold(self.ready))

    async def ensure_open(self) -> None:
        self.start_open()
        if self.session is None:
            await asyncio.shield(self.ready)

    async def _hold(self, ready: asyncio.Future) -> None:
        lim = self.hub.limits
        cfg = live_config(PERSONA, lim.voice, push_to_talk=True, thinking_level=lim.thinking, vocabulary=PROPER_NOUNS)
        reason = "closed"
        try:
            async with self.hub.client.aio.live.connect(model=common.settings().live_model, config=cfg) as session:
                self.session = session
                self.hub.log("session_open", setupMs=round((time.perf_counter() - self.open_started) * 1000))
                ready.set_result(True)
                await self._pump(session)
        except asyncio.CancelledError:
            reason = "closed"
            raise
        except Exception as exc:
            reason = "quota" if common.is_quota_error(exc) else "error"
            if reason == "quota":
                self.hub.voice_off_reason = "service"
            self.hub.log("session_error", reason=reason, errorType=type(exc).__name__, **common.upstream_error(exc))
            if not ready.done():
                ready.set_exception(exc)
            else:
                await self._lost(reason)
        finally:
            self.session = None
            self.model_open = False

    async def _lost(self, reason: str) -> None:
        """Live dropped mid-conversation: tell the page; the next press opens a new session."""
        try:
            if reason == "quota":
                await self.send({"type": "degraded", "voice": False, "reason": "service"})
            else:
                await self.error("voice_unavailable", "声が届きませんでした。もう一度話しかけてください。", retryable=True)
        except Exception:
            pass

    async def close_session(self) -> None:
        task, self.holder = self.holder, None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self.session = None

    async def on_focus(self, character) -> None:
        if character != CHARACTER:
            await self.error("not_found", "この人物とは話せません")
            return
        self.focused = True
        if self.hub.voice_off_reason:
            await self.send({"type": "degraded", "voice": False, "reason": self.hub.voice_off_reason})
            await self.send({"type": "session_ready", "character": CHARACTER, "voiceAvailable": False})
            return
        t0 = time.perf_counter()
        warm = self.session is not None
        if not warm:
            await self.send({"type": "session_preparing", "character": CHARACTER, "reason": "switch", "etaMs": 800})
        if not await self._open_or_report():
            return
        await self.send({"type": "session_ready", "character": CHARACTER, "voiceAvailable": True})
        self.hub.log("focus", warm=warm, focusToReadyMs=round((time.perf_counter() - t0) * 1000))

    async def _open_or_report(self) -> bool:
        try:
            await self.ensure_open()
            return True
        except Exception as exc:
            off = self.hub.voice_off_reason
            if off:
                await self.send({"type": "degraded", "voice": False, "reason": off})
            else:
                await self.error("voice_unavailable", "いまは声で話せません。文字で話しかけてください。", retryable=True,
                                 upstream=common.upstream_kind(exc))
            return False

    # -- turns

    async def begin_turn(self, turn_id: str, seq: int, via: str) -> bool:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", turn_id) or not (0 < seq < 0x80000000):
            await self.error("bad_request", "turnId / turnSeq が正しくありません")
            return False
        if self.hub.voice_off_reason:
            await self.send({"type": "degraded", "voice": False, "reason": self.hub.voice_off_reason})
            return False
        if self.session is None:
            await self.send({"type": "session_preparing", "character": CHARACTER, "reason": "rebuild", "etaMs": 1000})
            if not await self._open_or_report():
                return False
            await self.send({"type": "session_ready", "character": CHARACTER, "voiceAvailable": True})
        old = self.turn
        if old and self.model_open and not old.completed:
            old.interrupted = True
            self.model_open = False
            self.drain_until = time.perf_counter() + self.DRAIN_MAX_S
            self.n.barges += 1
            await self.send({"type": "interrupted", "turnId": old.turn_id})
            self._log_turn(old)
        self.turn = TurnState(turn_id, seq, via, pressed=time.perf_counter())
        if via == "voice":
            await self.session.send_realtime_input(activity_start=types.ActivityStart())
        return True

    async def on_release(self, turn_id: str) -> None:
        t = self.turn
        if t is None or t.turn_id != turn_id or t.released is not None or self.session is None:
            return
        await self.session.send_realtime_input(activity_end=types.ActivityEnd())
        t.released = time.perf_counter()
        self.model_open = True

    async def on_text(self, m: dict) -> None:
        text = str(m.get("text", ""))[:200].strip()
        if not text:
            return
        if not await self.begin_turn(str(m.get("turnId", "")), int(m.get("turnSeq", 0)), "typed"):
            return
        await self.session.send_client_content(turns=types.Content(role="user", parts=[types.Part(text=text)]), turn_complete=True)
        self.turn.released = time.perf_counter()
        self.model_open = True

    async def on_audio(self, data: bytes) -> None:
        t = self.turn
        if len(data) < 6 or data[0] != UP or (len(data) - 5) % 2:
            self.n.dropped_up += 1
            return
        seq = struct.unpack(">I", data[1:5])[0]
        if t is None or seq != t.seq or t.released is not None or t.via != "voice" or self.session is None:
            self.n.dropped_up += 1
            return
        t.up_bytes += len(data) - 5
        await self.session.send_realtime_input(audio=types.Blob(data=data[5:], mime_type=f"audio/pcm;rate={IN_RATE}"))

    # -- what Live sends back

    async def _pump(self, session) -> None:
        while True:
            got = False
            async for msg in session.receive():
                got = True
                await self.on_live(msg, time.perf_counter())
            if not got:
                await asyncio.sleep(0.05)

    def _draining(self, now: float) -> bool:
        if self.drain_until and now >= self.drain_until:
            self.drain_until = 0.0
            self.n.drain_timeouts += 1
        return self.drain_until > 0

    async def on_live(self, msg, now: float) -> None:
        if msg.usage_metadata is not None:
            prev = self.pending_usage
            if prev is None or (msg.usage_metadata.total_token_count or 0) >= (prev.total_token_count or 0):
                self.pending_usage = msg.usage_metadata
        if msg.go_away:
            self.hub.log("live_goaway")
        sc = msg.server_content
        if sc is None:
            return
        t = self.turn
        draining = self._draining(now)
        if sc.model_turn and sc.model_turn.parts:
            for part in sc.model_turn.parts:
                if not (part.inline_data and part.inline_data.data):
                    continue
                if draining or t is None or t.released is None or t.completed:
                    self.n.dropped_down += 1
                    continue
                if t.first_audio is None:
                    t.first_audio = now
                t.down_bytes += len(part.inline_data.data)
                await self.send_audio(t.seq, part.inline_data.data)
        late = (t is not None and t.completed and not t.interrupted and t.completed_at is not None
                and now - t.completed_at <= self.LATE_TEXT_S)
        if sc.output_transcription and sc.output_transcription.text and not draining and t and t.released and not t.completed:
            t.char_text += sc.output_transcription.text
            await self.send({"type": "transcript", "turnId": t.turn_id, "speaker": CHARACTER, "text": t.char_text, "final": False})
        elif sc.output_transcription and sc.output_transcription.text and late:
            t.char_text += sc.output_transcription.text
            await self.send({"type": "transcript", "turnId": t.turn_id, "speaker": CHARACTER, "text": t.char_text, "final": True})
            self.hub.log("late_transcript", turnSeq=t.seq, speaker="character", afterCompleteMs=_ms(t.completed_at, now))
        if sc.input_transcription and sc.input_transcription.text and t and not t.completed and t.via == "voice":
            if t.first_in_text is None:
                t.first_in_text = now
            t.player_text += sc.input_transcription.text
            await self.send({"type": "transcript", "turnId": t.turn_id, "speaker": "player", "text": t.player_text, "final": False})
        elif sc.input_transcription and sc.input_transcription.text and late and t.via == "voice":
            t.player_text += sc.input_transcription.text
            await self.send({"type": "transcript", "turnId": t.turn_id, "speaker": "player", "text": t.player_text, "final": True})
            self.hub.log("late_transcript", turnSeq=t.seq, speaker="player", afterCompleteMs=_ms(t.completed_at, now))
        if sc.interrupted:
            self.interrupted_at = now
            if self.drain_until:
                self.drain_until = 0.0
                self.settle_usage("s1b interrupted")
        idle = sc.interaction_status is not None and sc.interaction_status == types.InteractionStatus.IDLE
        if sc.turn_complete or idle:
            if self.drain_until:  # Live finished the interrupted turn without saying `interrupted`
                self.drain_until = 0.0
                self.settle_usage("s1b interrupted")
            elif t is None or t.released is None or t.completed:
                self.n.stale_completes += 1
                self.settle_usage("s1b stale")
            elif now - self.interrupted_at < self.STALE_COMPLETE_S and t.first_audio is None and not t.char_text:
                self.n.stale_completes += 1
            else:
                await self.complete(t)

    async def complete(self, t: TurnState) -> None:
        t.completed = True
        t.completed_at = time.perf_counter()
        self.model_open = False
        if t.player_text:
            await self.send({"type": "transcript", "turnId": t.turn_id, "speaker": "player", "text": t.player_text, "final": True})
        if t.char_text:
            await self.send({"type": "transcript", "turnId": t.turn_id, "speaker": CHARACTER, "text": t.char_text, "final": True})
        await self.send({"type": "turn_complete", "turnId": t.turn_id, "audio": t.first_audio is not None,
                         "metrics": {"serverReleaseToFirstAudioMs": _ms(t.released, t.first_audio)}})
        usd = self.settle_usage("s1b turn")
        self._log_turn(t, usd)

    def _log_turn(self, t: TurnState, usd: float | None = None) -> None:
        self.n.turns += 1
        self.hub.log("turn", turnSeq=t.seq, via=t.via, interrupted=t.interrupted,
                     speechMs=round(t.up_bytes / 2 / IN_RATE * 1000) if t.via == "voice" else None,
                     pressToReleaseMs=_ms(t.pressed, t.released),
                     serverReleaseToFirstAudioMs=_ms(t.released, t.first_audio),
                     firstPlayerTranscriptMs=_ms(t.released, t.first_in_text),
                     replyAudioS=round(t.down_bytes / 2 / 24_000, 2), usd=None if usd is None else round(usd, 6))

    def settle_usage(self, what: str) -> float | None:
        """Charge the turn's usage. Live may send it just after turn_complete, so wait briefly when it is missing."""
        if self.pending_usage is not None:
            usd = common.live_usage_cost(self.pending_usage)
            self.pending_usage = None
            self.hub.charge(usd, what)
            return usd
        task = asyncio.create_task(self._late_usage(what))
        self.late.add(task)
        task.add_done_callback(self.late.discard)
        return None

    async def _late_usage(self, what: str) -> None:
        await asyncio.sleep(1.5)
        usage, self.pending_usage = self.pending_usage, None
        # Never let a missing usage block make a turn look free (same rule as live_util.Probe.finish).
        self.hub.charge(common.live_usage_cost(usage) if usage is not None else 0.01, what)


def _ms(a: float | None, b: float | None) -> int | None:
    return None if a is None or b is None else round((b - a) * 1000)


# ---------------------------------------------------------------- HTTP app

TELEMETRY_NUM = re.compile(r"^[a-zA-Z][a-zA-Z0-9]{0,40}(Ms|Count|Pct)$")
TELEMETRY_ENUM_KEYS = {"item", "route", "network", "browser", "mode", "phase", "device"}
TELEMETRY_ENUM_VAL = re.compile(r"^[a-z0-9_.-]{1,24}$")
TURN_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

PLACEHOLDER = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>test</title><p style="font:16px system-ui;margin:24px">準備中です。</p>"""  # no product name anywhere (D-017)


def sanitize_telemetry(event: dict) -> dict:
    out = {}
    for k, v in event.items():
        if TELEMETRY_NUM.match(k) and isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) < 1e7:
            out[k] = round(v, 1)
        elif k in TELEMETRY_ENUM_KEYS and isinstance(v, str) and TELEMETRY_ENUM_VAL.match(v):
            out[k] = v
        elif k == "turnSeq" and isinstance(v, int) and not isinstance(v, bool):
            out[k] = v
        elif k == "turnId" and isinstance(v, str) and TURN_ID.match(v):
            out[k] = v
    return out


def create_app(hub: Hub, static_dir: Path | None = None):
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def err(status: int, code: str, message: str, retry_after: int | None = None) -> JSONResponse:
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        return JSONResponse({"error": {"code": code, "message": message, "retryable": retry_after is not None,
                                       "retryAfterSeconds": retry_after}}, status_code=status, headers=headers)

    def me() -> dict:
        left = max(0, round((hub.limits.max_usd - hub.spent) / hub.limits.max_usd * 60))
        return {"user": {"userRef": "u_s1b"}, "limits": {"runsToday": 0, "runsPerDay": 1, "voiceMinutesLeft": left},
                "activePlaythrough": None}

    def guard(request: Request, *, json_body: bool) -> JSONResponse | None:
        if not same_origin(hub, request.headers, request.url.scheme):
            return err(403, "forbidden", "このページからは使えません")
        if json_body and not request.headers.get("content-type", "").startswith("application/json"):
            return err(403, "forbidden", "このページからは使えません")
        return None

    @app.middleware("http")
    async def headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/v1/") or request.url.path == "/health":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    # Not /healthz: Cloud Run reserves paths ending in "z" and answers them 404 at its front end (S-1b, 2026-10-07).
    @app.get("/health")
    async def health():
        return PlainTextResponse("ok")

    @app.post("/v1/auth/login")
    async def login(request: Request):
        if (bad := guard(request, json_body=True)) is not None:
            return bad
        ip = request.client.host if request.client else "?"
        if (wait := hub.login_blocked(ip)) is not None:
            hub.log("login", ok=False, blocked=True)
            return err(429, "rate_limited", "しばらくしてから試してください", retry_after=wait)
        try:
            body = await request.json()
            code = str(body.get("inviteCode", ""))
        except Exception:
            code = ""
        ok = await asyncio.to_thread(check_code, code, hub.code_hash)
        hub.log("login", ok=ok)
        if not ok:
            hub.login_failed(ip)
            return err(401, "invalid_invite", "コードが違います")
        token = secrets.token_urlsafe(32)
        hub.tokens[token] = time.time() + SESSION_TTL_S
        resp = JSONResponse(me())
        resp.set_cookie(COOKIE, token, max_age=SESSION_TTL_S, path="/", httponly=True, samesite="lax",
                        secure=request.url.scheme == "https")
        return resp

    @app.post("/v1/auth/logout")
    async def logout(request: Request):
        if (bad := guard(request, json_body=False)) is not None:
            return bad
        hub.tokens.pop(request.cookies.get(COOKIE, ""), None)
        resp = Response(status_code=204)
        resp.delete_cookie(COOKIE, path="/")
        return resp

    @app.get("/v1/me")
    async def get_me(request: Request):
        if not hub.valid(request.cookies.get(COOKIE)):
            return err(401, "unauthenticated", "コードを入れてください")
        return JSONResponse(me())

    @app.post("/v1/telemetry")
    async def telemetry(request: Request):
        if (bad := guard(request, json_body=True)) is not None:
            return bad
        if not hub.valid(request.cookies.get(COOKIE)):
            return err(401, "unauthenticated", "コードを入れてください")
        try:
            body = await request.json()
            events = body.get("events", []) if isinstance(body, dict) else []
        except Exception:
            events = []
        for e in events[:50] if isinstance(events, list) else []:
            if isinstance(e, dict) and (clean := sanitize_telemetry(e)):
                hub.log("client", **clean)
        return Response(status_code=204)

    @app.websocket("/v1/playthroughs/{pid}/live")
    async def live(ws: WebSocket, pid: str):
        if not same_origin(hub, ws.headers, ws.url.scheme):
            hub.log("ws_refused", reason="origin")
            await ws.close(code=1008)  # before accept → the handshake is refused (HTTP 403)
            return
        await ws.accept()
        if not hub.valid(ws.cookies.get(COOKIE)):
            hub.log("ws_refused", reason="unauthenticated")
            await ws.close(code=4001)
            return
        if pid != PLAYTHROUGH:
            await ws.close(code=4004)
            return
        if hub.conns >= hub.limits.max_conns:
            hub.log("ws_refused", reason="busy")
            await ws.close(code=4290)
            return
        hub.conns += 1
        hub.log("conn_start", conns=hub.conns)
        try:
            await LiveConn(hub, ws).run()
        finally:
            hub.conns -= 1

    if static_dir and (static_dir / "index.html").exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=static_dir, html=True), name="page")
    else:
        @app.get("/")
        async def index():
            return HTMLResponse(PLACEHOLDER)

    return app


# ---------------------------------------------------------------- smoke test (also step 2 and 4 of the launch order)


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class SmokeResult:
    checks: list[Check] = field(default_factory=list)
    turns: list[dict] = field(default_factory=list)
    focus_to_ready_ms: int | None = None

    def add(self, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append(Check(name, ok, detail))
        print(f"  [{'OK' if ok else 'NG'}] {name}{(': ' + detail) if detail else ''}", flush=True)
        return ok

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)


async def _anon_ws_refused(ws_url: str, origin: str, headers: dict) -> tuple[bool, str]:
    from websockets.asyncio.client import connect
    from websockets.exceptions import ConnectionClosed, InvalidStatus

    try:
        async with connect(ws_url, origin=origin, additional_headers=headers, open_timeout=15) as ws:
            try:
                await asyncio.wait_for(ws.recv(), timeout=10)
                return False, "got a message after connecting / 接続後にメッセージを受信"
            except ConnectionClosed as e:
                code = e.rcvd.code if e.rcvd else None
                return code == 4001, f"close code / クローズコード {code}"
            except asyncio.TimeoutError:
                return False, "the connection was not closed / 接続が閉じられなかった"
    except InvalidStatus as e:
        return True, f"handshake refused / ハンドシェイク拒否 (HTTP {e.response.status_code})"


async def smoke(base: str, *, code: str | None, anon_only: bool, utterances: list[tuple[str, bytes]],
                id_token: str | None = None) -> SmokeResult:
    import httpx
    from websockets.asyncio.client import connect
    from websockets.exceptions import InvalidStatus

    base = base.rstrip("/")
    ws_base = ("wss://" + base[len("https://"):]) if base.startswith("https://") else ("ws://" + base[len("http://"):])
    ws_url = f"{ws_base}/v1/playthroughs/{PLAYTHROUGH}/live"
    gate = {"Authorization": f"Bearer {id_token}"} if id_token else {}  # only while the service is still private
    r = SmokeResult()
    async with httpx.AsyncClient(timeout=20, headers=gate) as http:
        resp = await http.get(f"{base}/v1/me")
        r.add("REST refused without a cookie / Cookie なしの REST は拒否", resp.status_code in (401, 403), f"HTTP {resp.status_code}")
        ok, detail = await _anon_ws_refused(ws_url, base, gate)
        r.add("WebSocket refused without a cookie / Cookie なしの WebSocket は拒否", ok, detail)
        resp = await http.post(f"{base}/v1/auth/login", json={"inviteCode": "WRONG-CODE-0000"}, headers={"Origin": base})
        r.add("Wrong test code refused / 誤ったテストコードは拒否", resp.status_code in (401, 403), f"HTTP {resp.status_code}")
        if anon_only:
            return r
        if not code:
            r.add("Read the test code / テストコードの読み込み", False,
                  f"no / なし {CODE_FILE}; run newcode first / 先に newcode を実行")
            return r
        resp = await http.post(f"{base}/v1/auth/login", json={"inviteCode": code}, headers={"Origin": "https://evil.example"})
        r.add("Login from another site refused / 他サイトからのログインは拒否", resp.status_code == 403, f"HTTP {resp.status_code}")
        resp = await http.post(f"{base}/v1/auth/login", json={"inviteCode": code}, headers={"Origin": base})
        token = resp.cookies.get(COOKIE)
        if not r.add("Correct test code logs in / 正しいテストコードでログイン可", resp.status_code == 200 and bool(token), f"HTTP {resp.status_code}"):
            return r
        cookie = {**gate, "Cookie": f"{COOKIE}={token}"}
        try:
            async with connect(ws_url, origin="https://evil.example", additional_headers=cookie, open_timeout=15):
                r.add("WebSocket from another site refused / 他サイトからの WebSocket は拒否", False,
                      "it connected / 接続できてしまった")
        except InvalidStatus as e:
            r.add("WebSocket from another site refused / 他サイトからの WebSocket は拒否", True,
                  f"HTTP {e.response.status_code}")

    async with connect(ws_url, origin=base, additional_headers=cookie, open_timeout=15, max_size=None) as ws:
        async def next_json(timeout=30.0) -> dict:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                if isinstance(raw, str):
                    return json.loads(raw)

        await ws.send(json.dumps({"type": "hello", "lastSeq": 0, "clientVersion": "s1b-smoke"}))
        welcome = await next_json()
        if not r.add("hello → welcome", welcome.get("type") == "welcome" and welcome["voice"]["enabled"], json.dumps(welcome.get("voice"))):
            return r
        await ws.send(json.dumps({"type": "near", "character": CHARACTER}))
        t0 = time.perf_counter()
        await ws.send(json.dumps({"type": "focus", "character": CHARACTER}))
        while (m := await next_json())["type"] != "session_ready":
            if m["type"] in ("error", "degraded"):
                r.add("Session ready / セッション準備完了", False, json.dumps(m, ensure_ascii=False))
                return r
        r.focus_to_ready_ms = round((time.perf_counter() - t0) * 1000)
        r.add("Session ready / セッション準備完了", m.get("voiceAvailable") is True, f"{r.focus_to_ready_ms} ms")

        for seq, (label, pcm) in enumerate(utterances, 1):
            turn_id = f"smoke_{seq:02d}"
            await ws.send(json.dumps({"type": "activity_start", "turnId": turn_id, "turnSeq": seq}))
            start = time.perf_counter()
            for i in range(0, len(pcm), CHUNK_BYTES):
                await ws.send(bytes([UP]) + struct.pack(">I", seq) + pcm[i : i + CHUNK_BYTES])
                delay = start + (i // CHUNK_BYTES + 1) * CHUNK_MS / 1000 - time.perf_counter()
                if delay > 0:
                    await asyncio.sleep(delay)
            await ws.send(json.dumps({"type": "activity_end", "turnId": turn_id, "turnSeq": seq}))
            released = time.perf_counter()
            first_audio, done, said = None, None, ""
            while done is None:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
                if isinstance(raw, bytes):
                    if raw[0] == DOWN and struct.unpack(">I", raw[1:5])[0] == seq and first_audio is None:
                        first_audio = time.perf_counter()
                    continue
                m = json.loads(raw)
                if m["type"] == "transcript" and m["speaker"] == "player" and m.get("final"):
                    said = m["text"]
                elif m["type"] == "turn_complete" and m["turnId"] == turn_id:
                    done = m
                elif m["type"] in ("error", "degraded"):
                    r.add(f"Turn {seq} / 第 {seq} ターン", False, json.dumps(m, ensure_ascii=False))
                    return r
            row = {"turnSeq": seq, "label": label, "audio": done["audio"],
                   "serverReleaseToFirstAudioMs": done["metrics"]["serverReleaseToFirstAudioMs"],
                   "clientReleaseToFirstAudioMs": _ms(released, first_audio), "playerTranscript": said}
            r.turns.append(row)
            r.add(f"Turn {seq} has a voice reply / 第 {seq} ターンに音声の返答あり", bool(done["audio"]),
                  f"server / サーバー {row['serverReleaseToFirstAudioMs']} ms, "
                  f"this machine / 本機 {row['clientReleaseToFirstAudioMs']} ms")
        await ws.send(json.dumps({"type": "unfocus", "reason": "menu"}))
    return r


VOICE_STEPS = ("Session ready", "Turn ")  # the only checks a not-yet-effective Gemini permission can fail


def only_voice_failed(result: SmokeResult) -> bool:
    failed = [c for c in result.checks if not c.ok]
    return bool(failed) and all(c.name.startswith(VOICE_STEPS) for c in failed)


async def smoke_retrying_voice(base: str, *, retry_s: float, **kw) -> SmokeResult:
    """A new service account's Gemini permission can take minutes to apply. When only the voice steps failed and every
    access check passed, wait and run the whole smoke test once more."""
    result = await smoke(base, **kw)
    if result.ok or not retry_s or not only_voice_failed(result):
        return result
    print(f"Only the voice step failed; every access-protection check passed. A new service account's Gemini "
          f"permission sometimes takes a few minutes to apply, so the whole suite runs again in {round(retry_s)} s. / "
          f"音声のステップだけが失敗し、アクセス保護のチェックはすべて合格しました。新しいサービスアカウントの Gemini "
          f"権限は反映に数分かかることがあるため、{round(retry_s)} 秒後に全体をもう一度実行します。", flush=True)
    await asyncio.sleep(retry_s)
    return await smoke(base, **kw)


SMOKE_LINES = ["メロスさん、王城に行くのですか。", "気をつけてくださいね。"]


def cmd_smoke(args) -> int:
    if args.url_file:
        if not URL_FILE.exists():
            sys.exit(f"No {URL_FILE} (s1b_deploy.sh up writes it) / {URL_FILE} がありません（s1b_deploy.sh up が書き出す）")
        base, where = URL_FILE.read_text().strip(), (
            "the deployed service (address in ~/.zoujin-spike/s1b-url, not shown) / "
            "デプロイ済みサービス（アドレスは ~/.zoujin-spike/s1b-url、表示しない）"
        )
    else:
        base, where = args.base, args.base
    code = CODE_FILE.read_text().strip() if CODE_FILE.exists() else None
    utterances: list[tuple[str, bytes]] = []
    if not args.anon_only:
        from .live_util import load_wav_dir, synth_utterances

        if args.wav_dir:
            utterances = load_wav_dir(Path(args.wav_dir))
        else:
            utterances = synth_utterances(SMOKE_LINES, common.settings().out_dir / "s1b" / "say")
    print(f"Smoke test / スモークテスト: {where}", flush=True)
    result = asyncio.run(smoke_retrying_voice(base, retry_s=args.voice_retry, code=code, anon_only=args.anon_only,
                                              utterances=utterances, id_token=os.environ.get("ZJ_S1B_ID_TOKEN") or None))
    out = common.settings().out_dir / "s1b" / f"smoke-{time.strftime('%Y%m%d-%H%M%S')}.json"
    common.write_json(out, {"target": "deployed" if args.url_file else "local", "anonOnly": args.anon_only, "ok": result.ok,
                            "checks": [c.__dict__ for c in result.checks], "focusToReadyMs": result.focus_to_ready_ms,
                            "turns": result.turns})
    verdict = "all passed / すべて合格" if result.ok else "some checks failed / 不合格の項目あり"
    print(f"{verdict}; results written to / 結果の保存先 {out}", flush=True)
    return 0 if result.ok else 1


# ---------------------------------------------------------------- CLI


def cmd_newcode(args) -> None:
    if CODE_FILE.exists() and not args.force:
        sys.exit(f"{CODE_FILE} already has a test code. For a new one, add --force (the old one stops working at once and "
                 f"the service must be redeployed). / {CODE_FILE} にはすでにテストコードがあります。新しくするには --force を付けて"
                 f"ください（古いコードは即座に無効になり、再デプロイが必要）。")
    code = new_code()
    _write_private(CODE_FILE, code + "\n")
    _write_private(ENV_FILE, f"ZJ_S1B_CODE_HASH={hash_code(code)}\n")
    print(f"Test code written to {CODE_FILE} (readable only by you). / テストコードを {CODE_FILE} に書き出しました"
          f"（読めるのはあなただけ）。\n"
          f"For zg's eyes only: run cat {CODE_FILE} in a terminal. Do not paste it into chat, docs or screenshots. / "
          f"zg だけが見ること：端末で cat {CODE_FILE} を実行。チャット・文書・スクリーンショットに貼らないでください。")


def cmd_serve(args) -> None:
    import uvicorn

    code_hash = code_hash_from_env()
    if not code_hash:
        sys.exit("No test code. First run: uv run python -m zj_spike.s1b_proxy newcode / "
                 "テストコードがありません。先に uv run python -m zj_spike.s1b_proxy newcode を実行してください")
    s = common.settings()
    on_cloud_run = bool(os.environ.get("K_SERVICE"))
    log_path = None if on_cloud_run else s.out_dir / "s1b" / f"serve-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    hub = Hub(code_hash, client_factory=lambda: common.genai_client(s.live_location), log_path=log_path)
    static = Path(os.environ["ZJ_S1B_STATIC"]) if os.environ.get("ZJ_S1B_STATIC") else None
    port = int(os.environ.get("PORT", args.port))
    if not on_cloud_run:
        print(f"Running at http://localhost:{port} (reachable only from this Mac); Ctrl+C to stop. Timing log: {log_path} / "
              f"http://localhost:{port} で実行中（この Mac からのみアクセス可）。Ctrl+C で停止。計時ログ: {log_path}", flush=True)
    uvicorn.run(create_app(hub, static), host=args.host, port=port, log_level="warning", access_log=False,
                server_header=False, proxy_headers=True, forwarded_allow_ips="*" if on_cloud_run else "127.0.0.1")


def cmd_selfcheck(args) -> int:
    """Run inside the built image as its non-root user: every code and page file is readable, and the app answers
    /health and serves the page. No network, no credentials (S-1b part 2 failed on unreadable code, 2026-10-07)."""
    import httpx

    static = Path(os.environ["ZJ_S1B_STATIC"]) if os.environ.get("ZJ_S1B_STATIC") else None
    paths = [p for root in [Path(__file__).resolve().parent, static] if root for p in [root, *root.rglob("*")]]
    bad = [p for p in paths if not os.access(p, (os.R_OK | os.X_OK) if p.is_dir() else os.R_OK)]
    print(f"user uid={os.getuid()}: checked {len(paths)} files and directories, {len(bad)} unreadable / "
          f"ユーザー uid={os.getuid()}: {len(paths)} 個のファイルとディレクトリを確認、読めないもの {len(bad)} 個", flush=True)
    for p in bad[:20]:
        print(f"  unreadable / 読めない: {p}", flush=True)
    if bad:
        return 1
    has_page = bool(static and (static / "index.html").exists())
    app = create_app(Hub("selfcheck", client_factory=lambda: None), static)

    async def fetch():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://selfcheck") as c:
            return await c.get("/health"), await c.get("/")

    health, page = asyncio.run(fetch())
    ok = health.status_code == 200 and page.status_code == 200
    kind = "frontend test page / フロントエンドのテストページ" if has_page else "placeholder page / プレースホルダーページ"
    print(f"/health → {health.status_code}, / → {page.status_code} ({kind})", flush=True)
    print("Image check passed / イメージチェック合格" if ok else "Image check failed / イメージチェック不合格", flush=True)
    return 0 if ok else 1


async def live_open_once(client, model: str) -> int:
    """Open one Live session with the proxy's exact settings and close it again; returns the setup time in ms.
    Nothing is said, so nothing is billed."""
    lim = Limits()
    cfg = live_config(PERSONA, lim.voice, push_to_talk=True, thinking_level=lim.thinking, vocabulary=PROPER_NOUNS)
    t0 = time.perf_counter()
    async with client.aio.live.connect(model=model, config=cfg):
        return round((time.perf_counter() - t0) * 1000)


def cmd_sacheck(args) -> int:
    """Before deploying: open a Live session from this Mac as the service account the service will run as
    (impersonated through zg's login, no key). A new account's permission can take minutes to apply, so retry until
    args.wait runs out; the first quota error stops at once. S-1b part 2's third attempt failed exactly here."""
    if not os.environ.get("ZJ_IMPERSONATE_SA"):
        sys.exit("ZJ_IMPERSONATE_SA is not set (./s1b_deploy.sh sacheck sets it) / "
                 "ZJ_IMPERSONATE_SA が設定されていません（./s1b_deploy.sh sacheck が設定する）")
    s = common.settings()
    deadline = time.monotonic() + args.wait
    attempt = 0
    while True:
        attempt += 1
        try:
            ms = asyncio.run(live_open_once(common.genai_client(s.live_location), s.live_model))
            print(f"  [OK] The service account can reach Live / サービスアカウントで Live に接続可 "
                  f"({s.live_location}, attempt {attempt} / 第 {attempt} 回, session setup {ms} ms)", flush=True)
            return 0
        except Exception as exc:
            info, kind = common.upstream_error(exc), common.upstream_kind(exc)
            print(f"  [NG] attempt {attempt} / 第 {attempt} 回: {type(exc).__name__} / {kind} / code={info['upstreamCode']} "
                  f"status={info['upstreamStatus']}: {info['upstreamMessage']}", flush=True)
            if kind == "quota":
                print("Hit a quota limit; stopping at once without retrying, as the rules say. / "
                      "クォータ制限に達したため、ルールどおり再試行せず直ちに停止します。", flush=True)
                return 1
            if time.monotonic() + args.interval > deadline:
                print(f"Still cannot connect after about {round(args.wait)} s. Do not run up; forward the lines above to the "
                      f"backend (project ID, address and account already removed). / 約 {round(args.wait)} 秒待っても"
                      f"接続できません。up は実行せず、上の数行をバックエンドに伝えてください（プロジェクト ID・アドレス・"
                      f"アカウントは除去済み）。", flush=True)
                return 1
            time.sleep(args.interval)


def main() -> None:
    ap = argparse.ArgumentParser(description="S-1b voice proxy (a subset of api-contract §3) / S-1b 音声プロキシ（api-contract 第 3 節のサブセット）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("newcode", help="generate a one-time test code (written to ~/.zoujin-spike/, not shown) / "
                                               "使い捨てテストコードを生成（~/.zoujin-spike/ に書き出し、表示しない）")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("serve", help="start the proxy / プロキシを起動")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p = sub.add_parser("smoke", help="smoke test / スモークテスト")
    p.add_argument("--base", default="http://localhost:8080")
    p.add_argument("--url-file", action="store_true", help="connect to the address s1b_deploy.sh saved (not shown) / "
                   "s1b_deploy.sh が保存したアドレスに接続（アドレスは表示しない）")
    p.add_argument("--anon-only", action="store_true", help="only check that anonymous access is refused / 匿名アクセスが拒否されることだけを確認")
    p.add_argument("--wav-dir", help="use your own recorded WAVs instead of lines synthesized by say / "
                   "say で合成した文の代わりに自分で録音した WAV を使う")
    p.add_argument("--voice-retry", type=float, default=0, help="when only voice failed and every access check passed, wait this many seconds and run the whole suite "
                   "again / 音声だけが失敗しアクセス保護がすべて合格したとき、この秒数待ってから全体をもう一度実行")
    sub.add_parser("selfcheck", help="check inside the image that the service user can read all code and pages (run automatically by "
                   "s1b_deploy.sh build before pushing) / イメージ内で、サービスユーザーがすべてのコードとページを読めるか"
                   "確認（s1b_deploy.sh build がプッシュ前に自動実行）")
    p = sub.add_parser("sacheck", help="before deploying, connect to Live once from this machine as the service account (called by "
                   "./s1b_deploy.sh sacheck) / デプロイ前に本機からサービスアカウントとして Live に一度接続"
                   "（./s1b_deploy.sh sacheck が呼ぶ）")
    p.add_argument("--wait", type=float, default=420, help="maximum seconds to wait (a new service account's permission takes time to apply) / "
                   "最大待ち秒数（新しいサービスアカウントの権限反映には時間がかかる）")
    p.add_argument("--interval", type=float, default=20)
    args = ap.parse_args()
    if args.cmd == "newcode":
        cmd_newcode(args)
    elif args.cmd == "serve":
        cmd_serve(args)
    elif args.cmd == "selfcheck":
        sys.exit(cmd_selfcheck(args))
    elif args.cmd == "sacheck":
        sys.exit(cmd_sacheck(args))
    else:
        sys.exit(cmd_smoke(args))


if __name__ == "__main__":
    main()
