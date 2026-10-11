"""照读（Live）和补转写的真实现、假实现。

真的只在 zg 的 Mac 上（`ZJ_MODEL=real`，G-7）：
- 照读：Vertex AI 的 Live（WebSocket，`BidiGenerateContent`），一条会话一个声音、一份系统指令，每句作为一轮文字送进去，
  收 PCM16、24 kHz、单声道。消息的形状照 google-genai SDK 发的（`spikes/backend/zj_spike` 用 SDK 在 Mac 上跑通过）；
  这里直接用 `websockets`，不为一个构建脚本给后端加 SDK 依赖。
- 补转写：Vertex AI 的 `generateContent`（`models/vertex.py` 的 REST 传输层），文本模型听这一遍的音频写出文字
  （S-071 ③）。
  Claude 不收音频，所以这一步和照读一样留在 Google（D-028）。
- 认证用 Mac 上的 ADC；项目 ID 和地区只从显式设的环境变量读，不进日志、账本和异常消息。

假的（CI、项目线程）：按句子的拍数合成「说话」的声音，可以设成截断、读两遍、太长、没声音、出错、429；补转写从假的
照读那里查这段声音「说了」什么。不放任何真人或模型录的声音。
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

LIVE_MODEL = "gemini-3.8-live"  # backend-design 第 7 节（us-central1）
TRANSCRIBE_MODEL = "gemini-3.5-flash-lite"  # S-071 ③ 的补转写
LIVE_LOCATION_ENV = "ZJ_LIVE_LOCATION"
LIVE_LOCATION = "us-central1"  # Live 只在美欧（backend-design 第 7 节）
# Live 的价目（每 100 万 token 的美元，docs/data/cost/pricing-2026-10-06.md 第 1 节）。音频 25 token/秒
LIVE_PRICES = {"inText": 0.75, "inAudio": 3.00, "outText": 4.50, "outAudio": 12.00}
AUDIO_TOKENS_PER_S = 25
TURN_TIMEOUT_S = 30.0
SETUP_TIMEOUT_S = 30.0
TAIL_QUIET_S = 0.6  # turnComplete 以后再等一会儿收晚到的用量
NO_USAGE_USD = 0.01  # 这一轮没收到用量：按这个记，不让它看起来是免费的（同 S-1）
TRANSCRIBE_PROMPT = (
    "次の音声は日本語の台詞です。聞こえたとおりに書き起こしてください。"
    "書き起こした文だけを出力し、説明や引用符は付けないでください。"
)


@dataclass(frozen=True)
class Spoken:
    """照读的一轮：声音、Live 自己的文字（照读时常常没有，S-071，只记不用）、用量和花费。"""

    pcm: bytes
    live_text: str
    usage: dict[str, int]
    cost: float


class ReadFailed(RuntimeError):
    """这一轮没读成（超时、连接断了）：记进审查单，这一遍算不过，不停下整个跑。"""


class ReaderSession(Protocol):
    async def read(self, text: str) -> Spoken:
        """送一轮文字（照读时是「」括起来的台词，自由对话时是问题），收这一轮的声音。"""
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


# —— 预计花费（调用前判上限，偏高） ——


def live_turn_estimate(system: str, text: str, history_s: float, history_chars: int) -> float:
    """一轮照读：输入 = 系统指令和这条会话里前面的文字（一字一个 token）+ 前面几轮的声音（每轮都重新计费）；
    输出 = 这句的声音按拍数估的上限 + 1 秒，加同样长的文字转写。"""
    out_s = mora(text) * 0.25 + 1.0
    usd = (len(system) + history_chars + len(text) + 20) * LIVE_PRICES["inText"]
    usd += history_s * AUDIO_TOKENS_PER_S * LIVE_PRICES["inAudio"]
    usd += out_s * AUDIO_TOKENS_PER_S * LIVE_PRICES["outAudio"] + (len(text) * 2 + 20) * LIVE_PRICES["outText"]
    return usd / 1_000_000


def transcribe_estimate(seconds: float, *, regional: bool) -> float:
    """补转写：音频按每秒 32 token（generateContent 的音频）、提示约 100 token，输出按 256 的上限。"""
    usage = {"inputTokens": int(seconds * 32) + 100, "outputTokens": 256}
    return cost_usd(TRANSCRIBE_MODEL, usage, regional=regional)


def live_cost(usage: Mapping[str, int]) -> float:
    """按 Live 用量的分项算（文字、音频分开；没有分项的输入按音频、输出按音频，偏高）。思考按输出文字。"""
    p = LIVE_PRICES
    usd = usage.get("inputTextTokens", 0) * p["inText"] + usage.get("inputAudioTokens", 0) * p["inAudio"]
    usd += usage.get("outputTextTokens", 0) * p["outText"] + usage.get("outputAudioTokens", 0) * p["outAudio"]
    usd += usage.get("thoughtTokens", 0) * p["outText"]
    return usd / 1_000_000


def live_cost_parts(usage: Mapping[str, int]) -> tuple[float, float]:
    """`live_cost` 分成输入、输出两半（美元）。S-090 对账只拿输入那一半和 results-s1 8.5 的公式比（#111 数据评审）。"""
    p = LIVE_PRICES
    inp = usage.get("inputTextTokens", 0) * p["inText"] + usage.get("inputAudioTokens", 0) * p["inAudio"]
    return inp / 1_000_000, live_cost(usage) - inp / 1_000_000


def live_usage(meta: Json) -> dict[str, int]:
    """Vertex 的 usageMetadata → 账本的 usage（只有数字）。"""
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


# —— 真的：Live 照读 ——


def _stop_if_quota(text: str) -> None:
    t = text.upper()
    if "RESOURCE_EXHAUSTED" in t or "429" in t or "QUOTA" in t or "529" in t:
        raise RateLimited("Live 回配额或限流错误，停下")


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
            raise ReadFailed(f"Live 连接断了（{reason[:4]}）") from None
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
                raise ReadFailed(f"{TURN_TIMEOUT_S:.0f} 秒内没收到 turnComplete")
            try:
                msg = await self._next(left)
            except TimeoutError:
                if done:
                    break
                raise ReadFailed(f"{TURN_TIMEOUT_S:.0f} 秒内没收到 turnComplete") from None
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
                    break  # 用量已经到了，不再等
        self._chars += len(text) + len(heard)
        if usage is None:
            return Spoken(bytes(pcm), heard, {}, NO_USAGE_USD)
        u = live_usage(usage)
        return Spoken(bytes(pcm), heard, u, live_cost(u))

    async def close(self) -> None:
        try:
            await self._ws.close()
        except Exception:  # noqa: BLE001 - 关的时候出错不影响结果
            pass


class LiveReader:
    """Vertex AI 的 Live。setup 的形状和 google-genai 2.x 对 Vertex 发的一样：模型写全路径，输出音频，开人物一侧的
    转写。"""

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

    async def open(self, voice: str, system: str) -> LiveSession:  # pragma: no cover - 只在 Mac 上
        import websockets

        headers = {"Authorization": f"Bearer {self._auth.token()}"}
        try:
            ws = await asyncio.wait_for(
                websockets.connect(self.url, additional_headers=headers, max_size=16 * 1024 * 1024),
                timeout=SETUP_TIMEOUT_S,
            )
        except websockets.InvalidStatus as e:
            if e.response.status_code == 429:
                raise RateLimited("Live 回 429，停下") from None
            raise ModelCallFailed(f"Live 握手 HTTP {e.response.status_code}（消息不记）") from None
        except (OSError, TimeoutError):
            raise ModelCallFailed("Live 连不上（消息不记）") from None
        session = LiveSession(ws)
        await ws.send(json.dumps(self.setup(voice, system), ensure_ascii=False))
        try:
            first = await session._next(SETUP_TIMEOUT_S)
        except (TimeoutError, ReadFailed):
            await session.close()
            raise ModelCallFailed("Live 会话没建起来（消息不记）") from None
        if "setupComplete" not in first:
            await session.close()
            raise ModelCallFailed("Live 会话没建起来：第一条消息不是 setupComplete")
        return session


# —— 真的：补转写 ——


@dataclass
class RestTranscriber:
    transport: RestTransport
    regional: bool
    model: str = TRANSCRIBE_MODEL

    async def transcribe(self, pcm: bytes) -> Heard:  # pragma: no cover - 只在 Mac 上
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


def real_models(env: Mapping[str, str]) -> tuple[LiveReader, RestTranscriber]:  # pragma: no cover - 只在 Mac 上
    from zoujin_backend.models.vertex import AdcAuth, vertex_env

    project, location = vertex_env(env)
    if TRANSCRIBE_MODEL not in PRICES:
        raise ConfigError(f"config.PRICES 里没有 {TRANSCRIBE_MODEL}")
    auth = AdcAuth()
    live_location = env.get(LIVE_LOCATION_ENV) or LIVE_LOCATION
    reader = LiveReader(project, live_location, auth)
    transcriber = RestTranscriber(RestTransport(project, location, auth), regional=location != "global")
    return reader, transcriber


# —— 假的 ——

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
    """faults：送给 Live 的文字 → 第几次读到这句时出什么问题（列表按次序用，None = 正常）。
    rate_limit_at：整个跑里第几次照读（从 1 起）回 429。"""

    faults: dict[str, list[str | None]] = field(default_factory=dict)
    rate_limit_at: int | None = None
    calls: int = 0
    reads: dict[str, int] = field(default_factory=dict)
    sessions: list[tuple[str, str]] = field(default_factory=list)  # (声音, 系统指令)，测试看分组
    said: dict[str, str] = field(default_factory=dict)  # 声音的 sha256 → 「说了」什么（给假的补转写）

    async def open(self, voice: str, system: str) -> FakeReaderSession:
        self.sessions.append((voice, system))
        return FakeReaderSession(self)

    def speak(self, sent: str) -> Spoken:
        """照读时 sent 是「」括起来的台词：按括号里的文字读；自由对话时按问题本身长短「回答」。"""
        text = sent[1:-1] if sent.startswith("「") and sent.endswith("」") else sent
        self.calls += 1
        if self.rate_limit_at is not None and self.calls == self.rate_limit_at:
            raise RateLimited("假的 Live 回 429")
        n = self.reads.get(text, 0)
        self.reads[text] = n + 1
        plan = self.faults.get(text, [])
        fault = plan[n] if n < len(plan) else None
        speech = max(0.2, mora(text) * FAKE_SEC_PER_MORA)
        said = text
        if fault == "error":
            raise ReadFailed("假的 Live：这一轮没读成")
        if fault == "rate_limit":
            raise RateLimited("假的 Live 回 429")
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
    wrong: dict[str, str] = field(default_factory=dict)  # 原来「说了」什么 → 补转写写成什么（读错）
    calls: int = 0

    async def transcribe(self, pcm: bytes) -> Heard:
        self.calls += 1
        said = self.reader.said.get(hashlib.sha256(pcm).hexdigest(), "")
        return Heard(self.wrong.get(said, said), {"inputTokens": 50, "outputTokens": 20}, 0.0002)
