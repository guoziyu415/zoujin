"""补转写（S-071，backend-design 3.1）和幕末打算的真转写（B-10）。

- 人物这一轮有声音、到收尾时一个字的文字都没有（真 Live 偶尔这样）：网关立即用这一轮的声音调轻量模型转写，3 秒截止、
  不重试。结果标 `source: "fallback"`；失败也发 `text: null` 的定稿。古语常听错，所以叙事者把它当作可能有误。
- 幕末用声音说打算（3.11）只转写、没有人物回答：真 Live 下攒下这一轮的上行音频，松开以后转写一次
  （`BufferedTranscriber`）。
  假 Live 照旧用 `FakeTranscriber`（有半句）。
- 真的转写在 Mac 上用 Vertex 的 `generateContent`（B-6 的 `RestTranscriber` 的同一个请求，音频按自己的采样率包成 WAV）；
  假的按设好的文字回，可以设成慢、失败。
"""

from __future__ import annotations

import asyncio
import base64
import logging
from dataclasses import dataclass, field
from typing import Protocol

from zoujin_backend.models.ledger import cost_usd
from zoujin_backend.models.live import LiveEvent
from zoujin_backend.voice import audio
from zoujin_backend.voice.models import TRANSCRIBE_MODEL, TRANSCRIBE_PROMPT, Heard, RestTranscriber

log = logging.getLogger("zoujin.gateway")

FALLBACK_CAP_S = 2.5  # 补转写的截止：收尾最多 3 秒 + 2.5 秒，定稿在 turn_complete 后 6 秒内（#111 前端评审）
PLAN_CAP_S = 10.0  # 打算的转写：玩家在等结果，但不是 3 秒的字幕
UP_RATE = 16_000
DOWN_RATE = 24_000


class AudioTranscriber(Protocol):
    async def transcribe(self, pcm: bytes, rate: int) -> Heard: ...


@dataclass
class VertexTranscriber:  # pragma: no cover - 只在 Mac 上
    inner: RestTranscriber

    async def transcribe(self, pcm: bytes, rate: int) -> Heard:
        data = base64.b64encode(audio.wav(pcm, rate)).decode("ascii")
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"inlineData": {"mimeType": "audio/wav", "data": data}}, {"text": TRANSCRIBE_PROMPT}],
                }
            ],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 256},
        }
        got = await self.inner.transport.generate(self.inner.model, body)
        return Heard(got.text.strip(), got.usage, cost_usd(TRANSCRIBE_MODEL, got.usage, regional=self.inner.regional))


@dataclass
class FakeAudioTranscriber:
    """测试用：回 `text`；`delay` 秒以后才回（超时的测试），`fail` 抛错。"""

    text: str = "……ああ。"
    delay: float = 0.0
    fail: bool = False
    calls: list[tuple[int, int]] = field(default_factory=list)  # (字节数, 采样率)

    async def transcribe(self, pcm: bytes, rate: int) -> Heard:
        self.calls.append((len(pcm), rate))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("假的补转写失败")
        return Heard(self.text, {"inputTokens": 50, "outputTokens": 10}, 0.0002)


async def fallback_text(tr: AudioTranscriber, pcm: bytes, cap_s: float = FALLBACK_CAP_S) -> Heard | None:
    """人物的声音 → 文字；超时、出错、空的都回 None（定稿发 `text: null`）。"""
    try:
        heard = await asyncio.wait_for(tr.transcribe(pcm, DOWN_RATE), timeout=cap_s)
    except TimeoutError:
        log.info("补转写 %.0f 秒没回来", cap_s)
        return None
    except Exception as e:  # noqa: BLE001 - 补转写只是后备，失败不影响这一轮
        log.info("补转写失败（%s）", type(e).__name__)
        return None
    return heard if heard.text else None


class BufferedTranscriber:
    """幕末用声音说打算（真 Live 时）：攒下音频，松开转写一次。没有半句字幕。"""

    def __init__(self, tr: AudioTranscriber) -> None:
        self.tr = tr
        self.pcm = bytearray()
        self.usd = 0.0

    def audio_in(self, pcm: bytes) -> list[LiveEvent]:
        self.pcm.extend(pcm)
        return []

    async def finish(self) -> str | None:
        if not self.pcm:
            return ""
        try:
            heard = await asyncio.wait_for(self.tr.transcribe(bytes(self.pcm), UP_RATE), timeout=PLAN_CAP_S)
        except Exception as e:  # noqa: BLE001
            log.info("打算的转写失败（%s）", type(e).__name__)
            return None
        self.usd = heard.cost
        return heard.text
