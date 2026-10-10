"""Live（人物的语音会话）的接口和假实现（B-0 第 6 条）。真 Live 的代理不在这里（M2）。

假 Live 读 `fixtures/fake-voice/lines.json`：每个人物一串「玩家说的话 + 人物的回答」，按轮次依次用（用完从头再来）。
语音一轮的玩家字幕就是这一条的 `player`（假的没有语音识别）；文字一轮只用 `reply`。
人物的音频是按回答的长短合成的 24 kHz PCM（`zoujin_backend.audio`），不放任何真人或模型录的声音。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from zoujin_backend import audio

type LiveEventKind = Literal["input_partial", "input_final", "audio", "output_partial", "output_final", "turn_complete"]

FIRST_AUDIO_MS = 900  # 松开到第一个音频分片（S-017 实测的服务端中位数附近）
CHUNK_MS = 40
SECONDS_PER_CHAR = 0.16  # 回答的音频长度按字数估


@dataclass(frozen=True)
class LiveEvent:
    kind: LiveEventKind
    text: str | None = None
    pcm: bytes = b""


class LiveSession(Protocol):
    character: str

    def audio_in(self, pcm: bytes) -> list[LiveEvent]: ...
    def respond(self, text: str | None) -> AsyncIterator[LiveEvent]: ...
    async def close(self) -> None: ...


class LiveModel(Protocol):
    async def open(self, character: str) -> LiveSession: ...


@dataclass(frozen=True)
class Line:
    player: str
    reply: str


class FakeLiveSession:
    def __init__(self, character: str, lines: list[Line], speed: float) -> None:
        self.character = character
        self.lines = lines
        self.speed = speed
        self.n = 0
        self.heard = False  # 这一轮收到过玩家的音频（第一帧时出半句玩家字幕）

    def _line(self) -> Line:
        return self.lines[self.n % len(self.lines)]

    def audio_in(self, pcm: bytes) -> list[LiveEvent]:
        if self.heard:
            return []
        self.heard = True
        p = self._line().player
        return [LiveEvent("input_partial", p[: max(1, len(p) // 2)])]

    async def _sleep(self, ms: float) -> None:
        if self.speed:
            await asyncio.sleep(ms / 1000 * self.speed)

    async def respond(self, text: str | None) -> AsyncIterator[LiveEvent]:
        """text 为 None：语音一轮（activity_end 之后）；否则是文字一轮。"""
        line = self._line()
        self.n += 1
        self.heard = False
        if text is None:
            yield LiveEvent("input_final", line.player)
        await self._sleep(FIRST_AUDIO_MS)
        pcm = list(audio.chunks(max(0.6, len(line.reply) * SECONDS_PER_CHAR), CHUNK_MS))
        marks = {len(pcm) // 3: 1, 2 * len(pcm) // 3: 2}
        for i, chunk in enumerate(pcm):
            yield LiveEvent("audio", pcm=chunk)
            if i in marks:
                yield LiveEvent("output_partial", line.reply[: len(line.reply) * marks[i] // 3] or line.reply)
            await self._sleep(CHUNK_MS)
        yield LiveEvent("turn_complete")
        yield LiveEvent("output_final", line.reply)

    async def close(self) -> None:
        return None


class FakeLive:
    def __init__(self, fixtures: Path, speed: float = 1.0) -> None:
        doc = json.loads((fixtures / "lines.json").read_text(encoding="utf-8"))
        self.lines = {k: [Line(x["player"], x["reply"]) for x in v] for k, v in doc["characters"].items()}
        self.speed = speed

    async def open(self, character: str) -> FakeLiveSession:
        return FakeLiveSession(character, self.lines.get(character) or self.lines["default"], self.speed)
