"""Gemini Live helpers shared by s0/s1/s3: session config, a receive pump with arrival times, audio files."""

from __future__ import annotations

import asyncio
import collections
import os
import shutil
import subprocess
import tempfile
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path

from google.genai import types

from . import common

IN_RATE = 16_000  # uplink PCM16 mono, as in api-contract 3.1
OUT_RATE = 24_000  # downlink PCM16 mono
CHUNK_MS = 40
CHUNK_BYTES = IN_RATE * 2 * CHUNK_MS // 1000

JA_RULE = "必ず日本語だけで話してください。相手が別の言語で話しかけても、日本語で答えてください。"

# Transcripts can arrive after turn_complete (the API reference says so for the player's side; S-1 voices
# lost the reply text in 19 of 30 sessions that were closed right after turn_complete). After a turn
# completes, keep reading transcript and usage messages: until TAIL_QUIET_S of silence once some reply text
# has arrived, and up to TAIL_CAP_S while the reply had audio but no text yet.
TAIL_QUIET_S = 0.6
TAIL_CAP_S = 3.0
SETUP_TIMEOUT_S = 30.0


def live_config(
    system_text: str,
    voice: str | None = None,
    *,
    push_to_talk: bool = True,
    resume_handle: str | None = None,
    resumable: bool = False,
    thinking_level: str | None = None,
    transcribe_lang: str | None = None,
    vocabulary: list[str] | None = None,
    reply_lang: str | None = None,
) -> types.LiveConnectConfig:
    """The production shape: audio out, both transcripts, push-to-talk (manual activity signals).

    The player's transcript gets a ja-JP hint unless ZJ_TRANSCRIBE_LANG is set to empty
    (s0_check suggests that if the endpoint rejects the hint).
    """
    lang = os.environ.get("ZJ_TRANSCRIBE_LANG", "ja-JP") if transcribe_lang is None else transcribe_lang
    cfg = dict(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(parts=[types.Part(text=system_text)]),
        input_audio_transcription=types.AudioTranscriptionConfig(
            language_codes=[lang] if lang else None, custom_vocabulary=vocabulary or None
        ),
        # reply_lang: a language hint for the character's transcript (the default is automatic detection).
        output_audio_transcription=types.AudioTranscriptionConfig(language_codes=[reply_lang] if reply_lang else None),
    )
    if voice:
        cfg["speech_config"] = types.SpeechConfig(
            voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice))
        )
    if push_to_talk:
        cfg["realtime_input_config"] = types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=True),
            activity_handling=types.ActivityHandling.START_OF_ACTIVITY_INTERRUPTS,
        )
    if resumable or resume_handle:
        cfg["session_resumption"] = types.SessionResumptionConfig(handle=resume_handle)
    if thinking_level:
        cfg["thinking_config"] = types.ThinkingConfig(thinking_level=thinking_level.upper())
    return types.LiveConnectConfig(**cfg)


@dataclass
class Turn:
    """One model turn as seen by the client. Times are time.perf_counter() values."""

    started: float  # when the client finished its part (activity_end sent, or text sent)
    first_audio: float | None = None
    first_text: float | None = None
    first_in_text: float | None = None  # first piece of the player's own transcript
    interrupted_at: float | None = None
    completed: float | None = None
    audio: bytearray = field(default_factory=bytearray)
    out_text: str = ""
    in_text: str = ""
    usage: object | None = None
    usage_msgs: int = 0
    cost: float = 0.0
    audio_after: list[float] = field(default_factory=list)  # arrival times of audio chunks
    late_text: float | None = None  # last transcript piece that arrived after turn_complete
    # What the server sent about the reply's transcript (S-1 casting: 43/168 turns had audio and no text).
    out_msgs: int = 0  # output_transcription messages, empty ones included
    out_finished: bool = False  # one of them carried finished=True
    generation_complete: float | None = None
    complete_reason: str | None = None
    log: list | None = None  # set to [] to keep every non-audio message (the transcripts diagnostic)

    def ms(self, t: float | None) -> int | None:
        return None if t is None else round((t - self.started) * 1000)

    @property
    def audio_seconds(self) -> float:
        return len(self.audio) / 2 / OUT_RATE

    def to_dict(self) -> dict:
        u = self.usage
        return {
            "first_audio_ms": self.ms(self.first_audio),
            "first_text_ms": self.ms(self.first_text),
            "first_user_transcript_ms": self.ms(self.first_in_text),
            "interrupted_ms": self.ms(self.interrupted_at),
            "complete_ms": self.ms(self.completed),
            "audio_s": round(self.audio_seconds, 2),
            "user_transcript": self.in_text.strip(),
            "reply_transcript": self.out_text.strip(),
            # > 0: some of the transcript arrived this long after turn_complete
            "transcript_late_ms": None if self.late_text is None or self.completed is None
            else round((self.late_text - self.completed) * 1000),
            "out_transcription_msgs": self.out_msgs,
            "out_transcription_finished": self.out_finished,
            "generation_complete_ms": self.ms(self.generation_complete),
            "turn_complete_reason": self.complete_reason,
            "usage_msgs": self.usage_msgs,
            "prompt_tokens": getattr(u, "prompt_token_count", None),
            "response_tokens": getattr(u, "response_token_count", None),
            "thought_tokens": getattr(u, "thoughts_token_count", None),
            "cost_usd": round(self.cost, 6),
        }


class Probe:
    """Owns the only reader of a Live session and timestamps every message on arrival.

    session.receive() stops at each turn_complete, so the pump calls it in a loop.
    """

    def __init__(self, session):
        self.session = session
        self.queue: asyncio.Queue = asyncio.Queue()
        self.pending: collections.deque = collections.deque()
        self.resume_handle: str | None = None
        self.go_away_left: str | None = None
        self._task = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        try:
            while True:
                async for msg in self.session.receive():
                    now = time.perf_counter()
                    upd = msg.session_resumption_update
                    if upd and upd.resumable and upd.new_handle:
                        self.resume_handle = upd.new_handle
                    if msg.go_away:
                        self.go_away_left = str(msg.go_away.time_left)
                    await self.queue.put((now, msg))
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # surfaced to whoever reads next
            await self.queue.put((time.perf_counter(), exc))

    async def get(self, timeout: float):
        if self.pending:
            return self.pending.popleft()
        now, item = await asyncio.wait_for(self.queue.get(), timeout=timeout)
        if isinstance(item, Exception):
            common.stop_on_quota(item)
            raise item
        return now, item

    async def close(self) -> None:
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass

    def absorb(self, turn: Turn, now: float, msg) -> bool:
        """Fold one message into the turn. Returns True when the turn is complete."""
        if msg.usage_metadata is not None:
            turn.usage_msgs += 1
            prev = turn.usage
            if prev is None or (msg.usage_metadata.total_token_count or 0) >= (prev.total_token_count or 0):
                turn.usage = msg.usage_metadata
        sc = msg.server_content
        if sc is None:
            return False
        if sc.model_turn and sc.model_turn.parts:
            for part in sc.model_turn.parts:
                if part.inline_data and part.inline_data.data:
                    if turn.first_audio is None:
                        turn.first_audio = now
                    turn.audio.extend(part.inline_data.data)
                    turn.audio_after.append(now)
        if sc.output_transcription:
            turn.out_msgs += 1
            turn.out_finished = turn.out_finished or bool(sc.output_transcription.finished)
        if sc.output_transcription and sc.output_transcription.text:
            if turn.first_text is None:
                turn.first_text = now
            turn.out_text += sc.output_transcription.text
        if sc.input_transcription and sc.input_transcription.text:
            if turn.first_in_text is None:
                turn.first_in_text = now
            turn.in_text += sc.input_transcription.text
        if sc.interrupted and turn.interrupted_at is None:
            turn.interrupted_at = now
        if sc.generation_complete and turn.generation_complete is None:
            turn.generation_complete = now
        if sc.turn_complete_reason:
            turn.complete_reason = str(sc.turn_complete_reason.value if hasattr(sc.turn_complete_reason, "value") else sc.turn_complete_reason)
        if turn.log is not None:
            entry = {k: v for k, v in {
                "ms": turn.ms(now),
                "out_text": sc.output_transcription.text if sc.output_transcription else None,
                "out_finished": sc.output_transcription.finished if sc.output_transcription else None,
                "in_text": sc.input_transcription.text if sc.input_transcription else None,
                "generation_complete": sc.generation_complete, "turn_complete": sc.turn_complete,
                "turn_complete_reason": turn.complete_reason if sc.turn_complete_reason else None,
                "interrupted": sc.interrupted, "waiting_for_input": sc.waiting_for_input,
            }.items() if v is not None}
            if len(entry) > 1:
                turn.log.append(entry)
        idle = sc.interaction_status is not None and sc.interaction_status == types.InteractionStatus.IDLE
        return bool(sc.turn_complete) or idle

    async def finish(self, turn: Turn, *, timeout: float, what: str, tail_cap: float | None = None) -> Turn:
        """Read until the turn completes, then wait briefly for a trailing usage message and charge it."""
        deadline = time.perf_counter() + timeout
        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise TimeoutError(f"{what}: no turn_complete within {timeout:.0f}s")
            now, msg = await self.get(remaining)
            if self.absorb(turn, now, msg):
                turn.completed = now
                break
        await self.tail(turn, TAIL_CAP_S if tail_cap is None else tail_cap)
        turn.cost = common.live_usage_cost(turn.usage)
        if turn.usage is None:
            # Never let a missing usage block make a turn look free: charge a conservative flat amount.
            turn.cost = 0.01
        common.charge(turn.cost, what)
        return turn


    async def tail(self, turn: Turn, cap: float = TAIL_CAP_S) -> None:
        """After turn_complete: collect the transcript pieces and usage that trail it (see TAIL_QUIET_S).

        Anything that belongs to the next turn (audio, `interrupted`, the player's next words) is put back
        for the next reader and ends the wait.
        """
        start = time.perf_counter()
        while True:
            elapsed = time.perf_counter() - start
            waiting_for_text = bool(turn.audio) and not turn.out_text
            budget = (cap if waiting_for_text else TAIL_QUIET_S) - (elapsed if waiting_for_text else 0)
            budget = min(budget, cap - elapsed)
            if budget <= 0:
                return
            try:
                now, msg = await self.get(budget)
            except asyncio.TimeoutError:
                return
            sc = msg.server_content
            if sc is not None and ((sc.model_turn and sc.model_turn.parts) or sc.interrupted):
                self.pending.append((now, msg))
                return
            if sc is not None and sc.input_transcription and sc.input_transcription.text and turn.interrupted_at is not None:
                # A barge-in: these are the words that interrupted this turn, so they start the next one.
                self.pending.append((now, msg))
                return
            had = len(turn.out_text) + len(turn.in_text)
            self.absorb(turn, now, msg)
            if len(turn.out_text) + len(turn.in_text) > had:
                turn.late_text = now


async def open_session(client, model: str, cfg, timeout: float | None = None):
    """Open a Live session and return (context manager, session, setup_ms).

    The SDK waits for the server's setup_complete with no time limit; a stuck setup here becomes a
    TimeoutError the caller can record and retry. Quota errors stop the run.
    """
    timeout = SETUP_TIMEOUT_S if timeout is None else timeout
    t0 = time.perf_counter()
    cm = client.aio.live.connect(model=model, config=cfg)
    try:
        session = await asyncio.wait_for(cm.__aenter__(), timeout=timeout)
    except asyncio.TimeoutError:
        raise TimeoutError(f"Live setup took more than {timeout:.0f}s") from None
    except Exception as exc:
        common.stop_on_quota(exc)
        raise
    return cm, session, round((time.perf_counter() - t0) * 1000)


async def close_session(cm, probe: "Probe | None") -> None:
    if probe:
        await probe.close()
    try:
        await cm.__aexit__(None, None, None)
    except Exception:
        pass


async def send_text_turn(session, text: str, role: str = "user") -> float:
    await session.send_client_content(
        turns=types.Content(role=role, parts=[types.Part(text=text)]), turn_complete=True
    )
    return time.perf_counter()


async def stream_utterance(session, pcm: bytes, *, realtime: bool = True) -> float:
    """Push-to-talk: activity_start, 40 ms chunks paced like a microphone, activity_end.

    Returns the time activity_end was sent (the moment the player lets go).
    """
    await session.send_realtime_input(activity_start=types.ActivityStart())
    t0 = time.perf_counter()
    for i in range(0, len(pcm), CHUNK_BYTES):
        chunk = pcm[i : i + CHUNK_BYTES]
        await session.send_realtime_input(audio=types.Blob(data=chunk, mime_type=f"audio/pcm;rate={IN_RATE}"))
        if realtime:
            target = t0 + (i // CHUNK_BYTES + 1) * CHUNK_MS / 1000
            delay = target - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
    await session.send_realtime_input(activity_end=types.ActivityEnd())
    return time.perf_counter()


# ---------------------------------------------------------------- audio files


def save_wav(path: Path, pcm: bytes, rate: int = OUT_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(pcm))


def read_pcm16k(path: Path) -> bytes:
    """Read a WAV as 16 kHz mono PCM16, converting with ffmpeg when it is in another format."""
    with wave.open(str(path), "rb") as w:
        ok = w.getframerate() == IN_RATE and w.getnchannels() == 1 and w.getsampwidth() == 2
        if ok:
            return w.readframes(w.getnframes())
    if not shutil.which("ffmpeg"):
        raise SystemExit(f"{path} 不是 16 kHz 单声道 16 位 WAV，且没有 ffmpeg 可转换")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "conv.wav"
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", str(path), "-ac", "1", "-ar", str(IN_RATE), "-sample_fmt", "s16", str(out)],
            check=True,
        )
        with wave.open(str(out), "rb") as w:
            return w.readframes(w.getnframes())


def japanese_say_voice() -> str:
    """Pick a Japanese macOS `say` voice, preferring Kyoko."""
    if not shutil.which("say"):
        raise SystemExit("找不到 macOS 的 say 命令。请在 Mac 上运行，或用 --wav-dir 指定自己录的 WAV。")
    listing = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, check=True).stdout
    names = [line.split()[0] for line in listing.splitlines() if "ja_JP" in line and line.split()]
    if not names:
        raise SystemExit("这台 Mac 没有日语朗读声音。系统设置 → 辅助功能 → 朗读内容 → 系统声音里添加 Kyoko，或用 --wav-dir。")
    return "Kyoko" if "Kyoko" in names else names[0]


def synth_utterances(lines: list[str], out_dir: Path, trailing_silence_ms: int = 150) -> list[tuple[str, bytes]]:
    """Synthesize test lines with `say` as 16 kHz PCM16 and keep the WAVs for reference."""
    voice = japanese_say_voice()
    out_dir.mkdir(parents=True, exist_ok=True)
    result = []
    for i, line in enumerate(lines, 1):
        path = out_dir / f"u{i:02d}.wav"
        if not path.exists():
            subprocess.run(
                ["say", "-v", voice, "-o", str(path), "--file-format=WAVE", "--data-format=LEI16@16000", line],
                check=True,
            )
        pcm = read_pcm16k(path) + b"\x00\x00" * (IN_RATE * trailing_silence_ms // 1000)
        result.append((line, pcm))
    return result


def load_wav_dir(wav_dir: Path) -> list[tuple[str, bytes]]:
    files = sorted(p for p in wav_dir.iterdir() if p.suffix.lower() == ".wav")
    if not files:
        raise SystemExit(f"{wav_dir} 里没有 .wav 文件")
    return [(p.name, read_pcm16k(p)) for p in files]


# ---------------------------------------------------------------- transcript accuracy

_PUNCT = set(" 　、。，．,.!?！？「」『』（）()・…ー〜~")


def _norm(text: str) -> str:
    return "".join(ch for ch in text if ch not in _PUNCT)


def cer(reference: str, hypothesis: str) -> float | None:
    """Character error rate after dropping punctuation and spaces (long vowel marks too, which ASR varies on)."""
    ref, hyp = _norm(reference), _norm(hypothesis)
    if not ref:
        return None
    prev = list(range(len(hyp) + 1))
    for i, rc in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, hc in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc))
        prev = cur
    return round(prev[-1] / len(ref), 3)
