"""Live（人物的语音会话）的接口和假实现（B-0 第 6 条）。真 Live 的代理不在这里（M2）。

假 Live 读 `fixtures/fake-voice/lines.json`：每个人物一串「玩家说的话 + 人物的回答」，按轮次依次用（用完从头再来）。
语音一轮的玩家字幕就是这一条的 `player`（假的没有语音识别）；文字一轮只用 `reply`。
B-3：落地时先开口的人物说 `openers` 里他的一句（`speak_first`）；幕末用声音说打算时只转写，玩家字幕是 `planLines`
依次用（`transcriber`）。
B-4：意图确认的反问也是人物先开口，说给定的那一句（`speak_first(line)`）。作废以后会话重建：`open` 收「最近的对话」
（这条连接上和这个人物最近几轮的文字，跳过作废的），假 Live 记下收到了什么（`opened`），测试查作废的那一轮不在里面。
真 Live 的重建跟真 Live 的卡一起做；最近的对话只在网关内存里，不落库、不进 Trace。
人物的音频是按回答的长短合成的 24 kHz PCM（`zoujin_backend.audio`），不放任何真人或模型录的声音。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
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
    def speak_first(self, line: str | None = None) -> AsyncIterator[LiveEvent]: ...
    async def close(self) -> None: ...


class Transcriber(Protocol):
    """只转写、人物不回答（B-3：幕末用声音说打算，`activity_start purpose: "act_plan"`）。"""

    def audio_in(self, pcm: bytes) -> list[LiveEvent]: ...
    async def finish(self) -> str | None: ...


@dataclass(frozen=True)
class Recent:
    """最近的一轮对话（会话重建时带进新会话）：玩家说的、人物答的。"""

    player: str | None
    reply: str | None


class LiveModel(Protocol):
    async def open(self, character: str, recent: Sequence[Recent] = ()) -> LiveSession: ...
    def transcriber(self) -> Transcriber: ...


@dataclass(frozen=True)
class Line:
    player: str
    reply: str


class FakeLiveSession:
    def __init__(self, character: str, lines: list[Line], speed: float, opener: str = "……") -> None:
        self.character = character
        self.lines = lines
        self.speed = speed
        self.opener = opener
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
        async for ev in self._say(line.reply):
            yield ev

    async def speak_first(self, line: str | None = None) -> AsyncIterator[LiveEvent]:
        """人物先开口（落地的 opener；意图确认的反问说给定的 line）：没有玩家的话，只有人物的一句。"""
        async for ev in self._say(line or self.opener):
            yield ev

    async def _say(self, reply: str) -> AsyncIterator[LiveEvent]:
        await self._sleep(FIRST_AUDIO_MS)
        pcm = list(audio.chunks(max(0.6, len(reply) * SECONDS_PER_CHAR), CHUNK_MS))
        marks = {len(pcm) // 3: 1, 2 * len(pcm) // 3: 2}
        for i, chunk in enumerate(pcm):
            yield LiveEvent("audio", pcm=chunk)
            if i in marks:
                yield LiveEvent("output_partial", reply[: len(reply) * marks[i] // 3] or reply)
            await self._sleep(CHUNK_MS)
        yield LiveEvent("turn_complete")
        yield LiveEvent("output_final", reply)

    async def close(self) -> None:
        return None


class FakeTranscriber:
    """假的转写：第一帧给半句，松开给整句（`planLines` 依次用）；一帧都没收到（没出声）松开给空串。"""

    def __init__(self, line: str) -> None:
        self.line = line
        self.heard = False

    def audio_in(self, pcm: bytes) -> list[LiveEvent]:
        if self.heard:
            return []
        self.heard = True
        return [LiveEvent("input_partial", self.line[: max(1, len(self.line) // 2)])]

    async def finish(self) -> str | None:
        return self.line if self.heard else ""


class FakeLive:
    def __init__(self, fixtures: Path, speed: float = 1.0) -> None:
        doc = json.loads((fixtures / "lines.json").read_text(encoding="utf-8"))
        self.lines = {k: [Line(x["player"], x["reply"]) for x in v] for k, v in doc["characters"].items()}
        self.openers: dict[str, str] = doc.get("openers", {})
        self.plan_lines: list[str] = doc.get("planLines") or ["……"]
        self.planned = 0
        self.speed = speed
        self.opened: list[tuple[str, list[Recent]]] = []  # 测试看：开了谁的会话、带了哪些最近的对话

    async def open(self, character: str, recent: Sequence[Recent] = ()) -> FakeLiveSession:
        self.opened.append((character, list(recent)))
        opener = self.openers.get(character) or self.openers.get("default") or "……"
        return FakeLiveSession(character, self.lines.get(character) or self.lines["default"], self.speed, opener)

    def transcriber(self) -> FakeTranscriber:
        line = self.plan_lines[self.planned % len(self.plan_lines)]
        self.planned += 1
        return FakeTranscriber(line)
