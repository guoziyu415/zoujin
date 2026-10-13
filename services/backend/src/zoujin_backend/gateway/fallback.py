"""Fallback transcription (S-071, backend-design 3.1) and the real transcription of end-of-act plans (B-10).

- The character's turn has audio but not a single character of text by the wrap-up (real Live does this now and
  then): the gateway immediately has a lightweight model transcribe the turn's audio, with a 3-second deadline and no
  retry. The result is marked `source: "fallback"`; on failure a final with `text: null` is still sent. Archaic
  speech is often misheard, so the narrator treats it as possibly wrong.
- Saying a plan by voice at the end of an act (3.11) is transcribed only, with no character answer: with real Live
  the turn's upstream audio is buffered and transcribed once after release (`BufferedTranscriber`).
  The fake Live keeps using `FakeTranscriber` (with partial lines).
- Real transcription runs on the Mac with Vertex `generateContent` (the same request as B-6's `RestTranscriber`, with
  the audio wrapped as WAV at its own sample rate); the fake one answers with preset text and can be set to be slow
  or fail.

補完の文字起こし（S-071、backend-design 3.1）と、幕末のプランの本物の文字起こし（B-10）。

- 登場人物のターンに音声はあるのに、締めくくりまでに文字が 1 文字もない（本物の Live でときどき起こる）：
  ゲートウェイはすぐにそのターンの音声を軽量モデルで文字起こしする。締め切り 3 秒、再試行なし。結果には
  `source: "fallback"` を付け、失敗しても `text: null` の確定文を送る。古い言葉はよく聞き違えるので、
  ナレーターはこれを誤りがありうるものとして扱う。
- 幕末に声でプランを言う（3.11）ときは文字起こしだけで、登場人物は答えない：本物の Live ではそのターンの上り音声を
  ためておき、離したあとに 1 回だけ文字起こしする（`BufferedTranscriber`）。
  偽 Live は従来どおり `FakeTranscriber`（途中の文あり）を使う。
- 本物の文字起こしは Mac 上で Vertex の `generateContent` を使う（B-6 の `RestTranscriber` と同じリクエストで、
  音声は自分のサンプルレートで WAV に包む）。偽物は設定した文字を返し、遅くしたり失敗させたりできる。
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

# Fallback transcription deadline: wrap-up at most 3 s + 2.5 s, so the final lands within 6 s of turn_complete
# (#111 frontend review).
# 補完の文字起こしの締め切り：締めくくり最大 3 秒 + 2.5 秒で、確定文は turn_complete から 6 秒以内
# （#111 フロントエンドのレビュー）。
FALLBACK_CAP_S = 2.5
# Plan transcription: the player is waiting for the result, but it isn't a 3-second subtitle.
# プランの文字起こし：プレイヤーは結果を待っているが、3 秒の字幕ではない。
PLAN_CAP_S = 10.0
UP_RATE = 16_000
DOWN_RATE = 24_000


class AudioTranscriber(Protocol):
    async def transcribe(self, pcm: bytes, rate: int) -> Heard: ...


@dataclass
class VertexTranscriber:  # pragma: no cover - Mac only / Mac 上のみ
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
    """For tests: answers `text`; only after `delay` seconds (timeout tests); `fail` raises.

    テスト用：`text` を返す。`delay` 秒後にだけ返し（タイムアウトのテスト）、`fail` なら例外を投げる。
    """

    text: str = "……ああ。"
    delay: float = 0.0
    fail: bool = False
    calls: list[tuple[int, int]] = field(default_factory=list)  # (bytes, sample rate) / (バイト数, サンプルレート)

    async def transcribe(self, pcm: bytes, rate: int) -> Heard:
        self.calls.append((len(pcm), rate))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fail:
            raise RuntimeError("Fake fallback transcription failed / 偽の補完文字起こしが失敗")
        return Heard(self.text, {"inputTokens": 50, "outputTokens": 10}, 0.0002)


async def fallback_text(tr: AudioTranscriber, pcm: bytes, cap_s: float = FALLBACK_CAP_S) -> Heard | None:
    """The character's voice → text; None on timeout, error or empty (the final is sent with `text: null`).

    登場人物の声 → 文字。タイムアウト、エラー、空ならどれも None（確定文は `text: null` で送る）。
    """
    try:
        heard = await asyncio.wait_for(tr.transcribe(pcm, DOWN_RATE), timeout=cap_s)
    except TimeoutError:
        log.info("Fallback transcription didn't return within %.0f s / 補完の文字起こしが時間内に戻らない", cap_s)
        return None
    # It's only a fallback; failing doesn't affect the turn. / 補完は予備にすぎず、失敗してもターンには影響しない。
    except Exception as e:  # noqa: BLE001
        log.info("Fallback transcription failed (%s) / 補完の文字起こしが失敗", type(e).__name__)
        return None
    return heard if heard.text else None


class BufferedTranscriber:
    """Saying a plan by voice at the end of an act (with real Live): buffer the audio and transcribe once on release.
    No partial subtitles.

    幕末に声でプランを言う（本物の Live のとき）：音声をためて、離したら 1 回だけ文字起こしする。途中の字幕はない。
    """

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
            log.info("Plan transcription failed (%s) / プランの文字起こしが失敗", type(e).__name__)
            return None
        self.usd = heard.cost
        return heard.text
