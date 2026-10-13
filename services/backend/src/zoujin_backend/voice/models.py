"""Real and fake implementations of read-aloud (Live) and transcript backfill.

The real ones run only on zg's Mac (`ZJ_MODEL=real`, G-7):
- Read-aloud: Vertex AI Live (WebSocket, `BidiGenerateContent`), one voice and one system instruction per session, each
  line sent as one text turn, receiving PCM16, 24 kHz, mono. The message shapes follow what the google-genai SDK sends
  (`spikes/backend/zj_spike` ran it with the SDK on the Mac); here `websockets` is used directly, so the backend does
  not take an SDK dependency for one build script.
- Transcript backfill: Vertex AI `generateContent` (the REST transport in `models/vertex.py`); a text model listens to
  the take's audio and writes down the text (S-071 ③).
  Claude does not accept audio, so this step stays on Google like read-aloud (D-028).
- Authentication uses ADC on the Mac; the project ID and location are read only from explicitly set environment
  variables and never go into logs, the ledger or exception messages.

The fake ones (CI, project threads): synthesize a "speaking" sound from the line's mora count, and can be set to
truncate, read twice, run too long, be silent, fail, or return 429; the fake transcript backfill looks up what that
audio "said" from the fake read-aloud. No recorded human or model voice is included.

読み上げ（Live）と文字起こしの補完の本実装・偽実装。

本物は zg の Mac でのみ動く（`ZJ_MODEL=real`、G-7）：
- 読み上げ：Vertex AI の Live（WebSocket、`BidiGenerateContent`）。1 セッションに声 1 つ、システム指示 1 つで、
  各セリフを 1 ターンの文字として送り、PCM16・24 kHz・モノラルを受け取る。メッセージの形は google-genai SDK が送る
  ものに合わせている（`spikes/backend/zj_spike` で SDK を使って Mac 上で動作確認済み）。ここでは `websockets` を
  直接使い、1 つのビルドスクリプトのためにバックエンドへ SDK の依存を加えない。
- 文字起こしの補完：Vertex AI の `generateContent`（`models/vertex.py` の REST 転送層）。テキストモデルがそのテイクの
  音声を聞いて文字を書き出す（S-071 ③）。
  Claude は音声を受け付けないので、この工程は読み上げと同じく Google に残す（D-028）。
- 認証は Mac 上の ADC。プロジェクト ID とリージョンは明示的に設定した環境変数からのみ読み、ログ・台帳・例外
  メッセージには入れない。

偽物（CI、プロジェクトスレッド）：セリフのモーラ数から「話している」音を合成し、途切れ・二度読み・長すぎ・無音・
エラー・429 を起こすよう設定できる。文字起こしの補完は、その音声が何を「言った」かを偽の読み上げから引く。実在の人や
モデルが録音した声は一切含まない。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import math
import time
from array import array
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from zoujin_backend.config import PRICES, ConfigError
from zoujin_backend.models.ledger import cost_usd
from zoujin_backend.models.text import ModelCallFailed, RateLimited
from zoujin_backend.models.vertex import Auth, RestTransport
from zoujin_backend.voice import audio
from zoujin_backend.voice.checks import mora

Json = Any
log = logging.getLogger("zoujin.voice")

LIVE_MODEL = "gemini-3.8-live"  # backend-design section 7 (us-central1) / backend-design 第 7 節（us-central1）
TRANSCRIBE_MODEL = "gemini-3.5-flash-lite"  # Transcript backfill of S-071 ③ / S-071 ③ の文字起こしの補完
LIVE_LOCATION_ENV = "ZJ_LIVE_LOCATION"
# Live is only in the US and Europe (backend-design section 7) / Live は米国と欧州のみ（backend-design 第 7 節）
LIVE_LOCATION = "us-central1"
# Live prices (USD per million tokens, docs/data/cost/pricing-2026-10-06.md section 1). Audio is 25 tokens/s
# Live の価格（100 万トークンあたりの米ドル、docs/data/cost/pricing-2026-10-06.md 第 1 節）。音声は 25 トークン/秒
LIVE_PRICES = {"inText": 0.75, "inAudio": 3.00, "outText": 4.50, "outAudio": 12.00}
AUDIO_TOKENS_PER_S = 25
TURN_TIMEOUT_S = 30.0
SETUP_TIMEOUT_S = 30.0
# After turnComplete, wait a little longer for late usage / turnComplete の後、遅れて届く使用量を少し待つ
TAIL_QUIET_S = 0.6
# No usage received for the turn: record this so it doesn't look free (same as S-1)
# このターンの使用量が届かなかったとき：無料に見えないようこの額で記録する（S-1 と同じ）
NO_USAGE_USD = 0.01
TRANSCRIBE_PROMPT = (
    "次の音声は日本語の台詞です。聞こえたとおりに書き起こしてください。"
    "書き起こした文だけを出力し、説明や引用符は付けないでください。"
)


@dataclass(frozen=True)
class Spoken:
    """One read-aloud turn: audio, Live's own text (often missing when reading aloud, S-071; recorded but unused),
    usage and cost.

    読み上げの 1 ターン：音声、Live 自身の文字（読み上げでは出ないことが多い、S-071。記録するだけで使わない）、
    使用量と費用。
    """

    pcm: bytes
    live_text: str
    usage: dict[str, int]
    cost: float


class ReadFailed(RuntimeError):
    """The turn wasn't read (timeout, dropped connection): goes into the audit sheet, the take counts as failed, and the
    whole run doesn't stop.

    このターンは読めなかった（タイムアウト、接続切れ）：監査シートに記録し、このテイクは不合格として扱い、実行全体は
    止めない。
    """


class ReaderSession(Protocol):
    async def read(self, text: str) -> Spoken:
        """Send one text turn (a line in 「」 when reading aloud, a question in free talk) and receive its audio.

        1 ターンの文字を送り（読み上げでは「」で囲んだセリフ、自由会話では質問）、そのターンの音声を受け取る。
        """
        ...

    async def close(self) -> None: ...


class Reader(Protocol):
    async def open(self, voice: str, system: str) -> ReaderSession: ...


@dataclass(frozen=True)
class Heard:
    text: str
    usage: dict[str, int]
    cost: float


class Transcriber(Protocol):
    async def transcribe(self, pcm: bytes) -> Heard: ...


# —— Estimated cost (checked against the caps before calling; errs high) ——
# —— 見積もり費用（呼び出し前に上限と照らす。高めに見積もる） ——


def live_turn_estimate(system: str, text: str, history_s: float, history_chars: int) -> float:
    """One read-aloud turn: input = the system instruction and the earlier text in this session (one token per
    character) + the earlier turns' audio (billed again every turn); output = the line's audio at the mora-based upper
    bound + 1 second, plus a text transcript of the same length.

    読み上げ 1 ターン：入力 = システム指示とこのセッションのそれまでの文字（1 字 1 トークン）+ それまでのターンの音声
    （毎ターン課金し直される）。出力 = このセリフの音声をモーラ数で見積もった上限 + 1 秒と、同じ長さの文字起こし。
    """
    out_s = mora(text) * 0.25 + 1.0
    usd = (len(system) + history_chars + len(text) + 20) * LIVE_PRICES["inText"]
    usd += history_s * AUDIO_TOKENS_PER_S * LIVE_PRICES["inAudio"]
    usd += out_s * AUDIO_TOKENS_PER_S * LIVE_PRICES["outAudio"] + (len(text) * 2 + 20) * LIVE_PRICES["outText"]
    return usd / 1_000_000


def transcribe_estimate(seconds: float, *, regional: bool) -> float:
    """Transcript backfill: audio at 32 tokens per second (generateContent audio), about 100 prompt tokens, output at
    the 256 cap.

    文字起こしの補完：音声は毎秒 32 トークン（generateContent の音声）、プロンプトは約 100 トークン、出力は上限の 256。
    """
    usage = {"inputTokens": int(seconds * 32) + 100, "outputTokens": 256}
    return cost_usd(TRANSCRIBE_MODEL, usage, regional=regional)


def live_cost(usage: Mapping[str, int]) -> float:
    """Computed from Live's usage breakdown (text and audio separately; without a breakdown, input and output are both
    priced as audio, erring high). Thinking is priced as output text.

    Live の使用量の内訳から計算する（文字と音声を分ける。内訳がなければ入力も出力も音声として計算し、高めになる）。
    思考は出力の文字として計算する。
    """
    p = LIVE_PRICES
    usd = usage.get("inputTextTokens", 0) * p["inText"] + usage.get("inputAudioTokens", 0) * p["inAudio"]
    usd += usage.get("outputTextTokens", 0) * p["outText"] + usage.get("outputAudioTokens", 0) * p["outAudio"]
    usd += usage.get("thoughtTokens", 0) * p["outText"]
    return usd / 1_000_000


def live_cost_parts(usage: Mapping[str, int]) -> tuple[float, float]:
    """`live_cost` split into input and output halves (USD). S-090 reconciliation compares only the input half with the
    results-s1 8.5 formula (#111 data review).

    `live_cost` を入力と出力の 2 つに分ける（米ドル）。S-090 の照合では入力側だけを results-s1 8.5 の式と比べる
    （#111 データレビュー）。
    """
    p = LIVE_PRICES
    inp = usage.get("inputTextTokens", 0) * p["inText"] + usage.get("inputAudioTokens", 0) * p["inAudio"]
    return inp / 1_000_000, live_cost(usage) - inp / 1_000_000


def live_usage(meta: Json) -> dict[str, int]:
    """Vertex usageMetadata → the ledger's usage (numbers only).

    Vertex の usageMetadata → 台帳の usage（数値のみ）。
    """
    u = {"inputTokens": int(meta.get("promptTokenCount", 0)), "outputTokens": int(meta.get("candidatesTokenCount", 0))}
    u["thoughtTokens"] = int(meta.get("thoughtsTokenCount", 0))
    for side, details, total in (
        ("input", meta.get("promptTokensDetails"), u["inputTokens"]),
        ("output", meta.get("candidatesTokensDetails") or meta.get("responseTokensDetails"), u["outputTokens"]),
    ):
        text = audio_ = 0
        if details:
            for d in details:
                n = int(d.get("tokenCount", 0))
                if str(d.get("modality", "")).upper().endswith("TEXT"):
                    text += n
                else:
                    audio_ += n
        else:
            audio_ = total
        u[f"{side}TextTokens"] = text
        u[f"{side}AudioTokens"] = audio_
    return u


# —— Real: Live read-aloud / 本物：Live の読み上げ ——


def _stop_if_quota(text: str) -> None:
    t = text.upper()
    if "RESOURCE_EXHAUSTED" in t or "429" in t or "QUOTA" in t or "529" in t:
        raise RateLimited(
            "Live returned a quota or rate-limit error; stopping / "
            "Live がクォータまたはレート制限のエラーを返したので止める"
        )


def _no_turn_complete() -> str:
    s = f"{TURN_TIMEOUT_S:.0f}"
    return f"No turnComplete within {s} seconds / {s} 秒以内に turnComplete が届かなかった"


class LiveSession:
    def __init__(self, ws: Any) -> None:
        self._ws = ws
        self._chars = 0

    async def _next(self, timeout: float) -> Json:
        import websockets

        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
        except websockets.ConnectionClosed as e:
            reason = f"{e.rcvd.code} {e.rcvd.reason}" if e.rcvd else "1006"
            _stop_if_quota(reason)
            raise ReadFailed(f"Live connection dropped ({reason[:4]}) / Live の接続が切れた（{reason[:4]}）") from None
        return json.loads(raw)

    async def read(self, text: str) -> Spoken:
        content = {"turns": [{"parts": [{"text": text}], "role": "user"}], "turnComplete": True}
        await self._ws.send(json.dumps({"client_content": content}, ensure_ascii=False))
        pcm = bytearray()
        heard = ""
        usage: Json = None
        deadline = time.monotonic() + TURN_TIMEOUT_S
        done = False
        while True:
            left = deadline - time.monotonic() if not done else TAIL_QUIET_S
            if left <= 0:
                raise ReadFailed(_no_turn_complete())
            try:
                msg = await self._next(left)
            except TimeoutError:
                if done:
                    break
                raise ReadFailed(_no_turn_complete()) from None
            meta = msg.get("usageMetadata")
            if meta and (usage is None or meta.get("totalTokenCount", 0) >= usage.get("totalTokenCount", 0)):
                usage = meta
            sc = msg.get("serverContent") or {}
            for part in (sc.get("modelTurn") or {}).get("parts") or []:
                data = (part.get("inlineData") or {}).get("data")
                if data:
                    pcm.extend(base64.b64decode(data))
            heard += (sc.get("outputTranscription") or {}).get("text") or ""
            if sc.get("turnComplete"):
                done = True
                if usage is not None:
                    break  # Usage already arrived; stop waiting / 使用量はもう届いたので待たない
        self._chars += len(text) + len(heard)
        if usage is None:
            return Spoken(bytes(pcm), heard, {}, NO_USAGE_USD)
        u = live_usage(usage)
        return Spoken(bytes(pcm), heard, u, live_cost(u))

    async def close(self) -> None:
        try:
            await self._ws.close()
        except Exception:  # noqa: BLE001 - errors on close don't matter / 閉じるときのエラーは無視
            pass


class LiveReader:
    """Vertex AI Live. The setup shape matches what google-genai 2.x sends to Vertex: the model as a full path, audio
    output, transcription of the character's side turned on.

    Vertex AI の Live。setup の形は google-genai 2.x が Vertex に送るものと同じ：モデルはフルパスで書き、音声を出力し、
    人物側の文字起こしを有効にする。
    """

    def __init__(self, project: str, location: str, auth: Auth, model: str = LIVE_MODEL) -> None:
        self._project = project
        self._location = location
        self._auth = auth
        self._model = model

    @property
    def url(self) -> str:
        host = f"{self._location}-aiplatform.googleapis.com"
        return f"wss://{host}/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent"

    def setup(self, voice: str, system: str) -> Json:
        model = f"projects/{self._project}/locations/{self._location}/publishers/google/models/{self._model}"
        return {
            "setup": {
                "model": model,
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voice_name": voice}}},
                },
                "systemInstruction": {"parts": [{"text": system}]},
                "outputAudioTranscription": {},
            }
        }

    async def open(self, voice: str, system: str) -> LiveSession:  # pragma: no cover - Mac only / Mac のみ
        import websockets

        headers = {"Authorization": f"Bearer {self._auth.token()}"}
        try:
            ws = await asyncio.wait_for(
                websockets.connect(self.url, additional_headers=headers, max_size=16 * 1024 * 1024),
                timeout=SETUP_TIMEOUT_S,
            )
        except websockets.InvalidStatus as e:
            if e.response.status_code == 429:
                raise RateLimited("Live returned 429; stopping / Live が 429 を返したので止める") from None
            code = e.response.status_code
            raise ModelCallFailed(
                f"Live handshake HTTP {code} (message not logged) / "
                f"Live のハンドシェイク HTTP {code}（メッセージは記録しない）"
            ) from None
        except (OSError, TimeoutError):
            raise ModelCallFailed(
                "Can't connect to Live (message not logged) / Live に接続できない（メッセージは記録しない）"
            ) from None
        session = LiveSession(ws)
        await ws.send(json.dumps(self.setup(voice, system), ensure_ascii=False))
        try:
            first = await session._next(SETUP_TIMEOUT_S)
        except (TimeoutError, ReadFailed):
            await session.close()
            raise ModelCallFailed(
                "Live session not set up (message not logged) / "
                "Live のセッションが確立できなかった（メッセージは記録しない）"
            ) from None
        if "setupComplete" not in first:
            await session.close()
            raise ModelCallFailed(
                "Live session not set up: the first message isn't setupComplete / "
                "Live のセッションが確立できなかった：最初のメッセージが setupComplete ではない"
            )
        return session


# —— Real: transcript backfill / 本物：文字起こしの補完 ——


@dataclass
class RestTranscriber:
    transport: RestTransport
    regional: bool
    model: str = TRANSCRIBE_MODEL

    async def transcribe(self, pcm: bytes) -> Heard:  # pragma: no cover - Mac only / Mac のみ
        data = base64.b64encode(audio.wav(pcm)).decode("ascii")
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"inlineData": {"mimeType": "audio/wav", "data": data}}, {"text": TRANSCRIBE_PROMPT}],
                }
            ],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 256},
        }
        got = await self.transport.generate(self.model, body)
        return Heard(got.text.strip(), got.usage, cost_usd(self.model, got.usage, regional=self.regional))


def real_models(env: Mapping[str, str]) -> tuple[LiveReader, RestTranscriber]:  # pragma: no cover - Mac only / Mac のみ
    from zoujin_backend.models.vertex import AdcAuth, vertex_env

    project, location = vertex_env(env)
    if TRANSCRIBE_MODEL not in PRICES:
        raise ConfigError(f"{TRANSCRIBE_MODEL} is not in config.PRICES / config.PRICES に {TRANSCRIBE_MODEL} がない")
    auth = AdcAuth()
    live_location = env.get(LIVE_LOCATION_ENV) or LIVE_LOCATION
    reader = LiveReader(project, live_location, auth)
    transcriber = RestTranscriber(RestTransport(project, location, auth), regional=location != "global")
    return reader, transcriber


# —— Fake / 偽物 ——

FAULTS = ("truncated", "double", "long", "silent", "error", "rate_limit")
FAKE_SEC_PER_MORA = 0.13
FAKE_PAD_S = 0.3


def _tone(seconds: float, *, fade_out: bool = True) -> array[int]:
    n = max(1, round(seconds * audio.RATE))
    fade = audio.RATE // 200  # 5 ms
    out = array("h")
    for i in range(n):
        env = min(1.0, i / fade, (n - i) / fade) if fade_out else min(1.0, i / fade)
        out.append(int(3000 * env * math.sin(2 * math.pi * 180 * i / audio.RATE)))
    return out


def _silence(seconds: float) -> array[int]:
    return array("h", bytes(2 * round(seconds * audio.RATE)))


@dataclass
class FakeReader:
    """faults: text sent to Live → what goes wrong on the nth read of that line (the list is used in order, None =
    normal). rate_limit_at: the read-aloud call (counting from 1 across the whole run) that returns 429.

    faults：Live に送る文字 → そのセリフを何回目に読んだときに何が起きるか（リストを順に使い、None = 正常）。
    rate_limit_at：実行全体で何回目（1 から数える）の読み上げで 429 を返すか。
    """

    faults: dict[str, list[str | None]] = field(default_factory=dict)
    rate_limit_at: int | None = None
    calls: int = 0
    reads: dict[str, int] = field(default_factory=dict)
    # (voice, system instruction); tests check the grouping / （声、システム指示）。テストがグループ分けを確認する
    sessions: list[tuple[str, str]] = field(default_factory=list)
    # Audio sha256 → what it "said" (for the fake transcript backfill)
    # 音声の sha256 → 何を「言った」か（偽の文字起こし用）
    said: dict[str, str] = field(default_factory=dict)

    async def open(self, voice: str, system: str) -> FakeReaderSession:
        self.sessions.append((voice, system))
        return FakeReaderSession(self)

    def speak(self, sent: str) -> Spoken:
        """When reading aloud, sent is a line in 「」: read the text inside the brackets; in free talk, "answer" with a
        length based on the question itself.

        読み上げでは sent は「」で囲んだセリフなので、括弧の中の文字を読む。自由会話では質問そのものの長さで「答える」。
        """
        text = sent[1:-1] if sent.startswith("「") and sent.endswith("」") else sent
        self.calls += 1
        if self.rate_limit_at is not None and self.calls == self.rate_limit_at:
            raise RateLimited("Fake Live returned 429 / 偽 Live が 429 を返した")
        n = self.reads.get(text, 0)
        self.reads[text] = n + 1
        plan = self.faults.get(text, [])
        fault = plan[n] if n < len(plan) else None
        speech = max(0.2, mora(text) * FAKE_SEC_PER_MORA)
        said = text
        if fault == "error":
            raise ReadFailed("Fake Live: this turn wasn't read / 偽 Live：このターンは読めなかった")
        if fault == "rate_limit":
            raise RateLimited("Fake Live returned 429 / 偽 Live が 429 を返した")
        if fault == "silent":
            a = _silence(1.0)
        elif fault == "truncated":
            a = _silence(FAKE_PAD_S) + _tone(speech * 0.6, fade_out=False)
            said = text[: max(1, len(text) // 2)]
        elif fault == "double":
            a = _silence(FAKE_PAD_S) + _tone(speech) + _silence(0.4) + _tone(speech) + _silence(FAKE_PAD_S)
            said = text + text
        elif fault == "long":
            a = _silence(FAKE_PAD_S) + _tone(speech * 3) + _silence(FAKE_PAD_S)
        else:
            a = _silence(FAKE_PAD_S) + _tone(speech) + _silence(FAKE_PAD_S)
        pcm = audio.to_bytes(a)
        self.said[hashlib.sha256(pcm).hexdigest()] = "" if fault == "silent" else said
        usage = {"inputTokens": 100, "outputTokens": round(len(pcm) / 2 / audio.RATE * AUDIO_TOKENS_PER_S)}
        return Spoken(pcm, "", usage, 0.001)


@dataclass
class FakeReaderSession:
    reader: FakeReader

    async def read(self, text: str) -> Spoken:
        return self.reader.speak(text)

    async def close(self) -> None:
        return None


@dataclass
class FakeTranscriber:
    reader: FakeReader
    # What was originally "said" → what the transcript backfill writes instead (misreading)
    # もともと何を「言った」か → 文字起こしの補完で何と書くか（読み誤り）
    wrong: dict[str, str] = field(default_factory=dict)
    calls: int = 0

    async def transcribe(self, pcm: bytes) -> Heard:
        self.calls += 1
        said = self.reader.said.get(hashlib.sha256(pcm).hexdigest(), "")
        return Heard(self.wrong.get(said, said), {"inputTokens": 50, "outputTokens": 20}, 0.0002)
