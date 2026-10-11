"""Live（人物的语音会话）的接口和假实现（B-0 第 6 条）。真 Live 的代理不在这里（M2）。

假 Live 读 `fixtures/fake-voice/lines.json`：每个人物一串「玩家说的话 + 人物的回答」，按轮次依次用（用完从头再来）。
语音一轮的玩家字幕就是这一条的 `player`（假的没有语音识别）；文字一轮只用 `reply`。
B-3：落地时先开口的人物说 `openers` 里他的一句（`speak_first`）；幕末用声音说打算时只转写，玩家字幕是 `planLines`
依次用（`transcriber`）。
B-4：意图确认的反问也是人物先开口，说给定的那一句（`speak_first(line)`）。作废以后会话重建：`open` 收「最近的对话」
（这条连接上和这个人物最近几轮的文字，跳过作废的），假 Live 记下收到了什么（`opened`），测试查作废的那一轮不在里面。
最近的对话只在网关内存里，不落库、不进 Trace。
人物的音频是按回答的长短合成的 24 kHz PCM（`zoujin_backend.audio`），不放任何真人或模型录的声音。

B-10：真 Live 在 `models/gemini_live.py`，和这里的假 Live 实现同一个接口。会话多了几样网关要看的：活着没有（`alive`）、
收到 GoAway 没有（`going_away`）、完成了几轮（`turns`）、会话里已有多少秒音频（`audio_seconds`，对账用）、有变化时叫一下
网关（`on_change`）、中途更新局势（`note`，不触发回答）。每轮说完吐一个 `usage`（这一轮的美元和用量）。
`open` 收系统指令（`gateway/brief.py` 拼的人设、局势、最近的对话）；假 Live 只记下来给测试看。
假 Live 的测试开关：`fail_opens`（接下来几次开会话失败）、`textless`（有声音没文字）、会话的 `goaway()`、`die()`。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from zoujin_backend import audio

type LiveEventKind = Literal[
    "input_partial", "input_final", "audio", "output_partial", "output_final", "turn_complete", "usage"
]

FIRST_AUDIO_MS = 900  # 松开到第一个音频分片（S-017 实测的服务端中位数附近）
CHUNK_MS = 40
SECONDS_PER_CHAR = 0.16  # 回答的音频长度按字数估


@dataclass(frozen=True)
class LiveEvent:
    """`output_final` 的 text 为 None：这一轮人物一个字的文字都没有（真 Live 偶尔这样，S-071，网关补转写）。
    `usage`：这一轮的花费（`usd`）和用量（`usage`，只有数字），在 `output_final` 之后。"""

    kind: LiveEventKind
    text: str | None = None
    pcm: bytes = b""
    usd: float = 0.0
    usage: Mapping[str, int] | None = None


class LiveLost(RuntimeError):
    """Live 的连接断了（中途、开不起来）。消息里不带原话、地址和项目。"""


class LiveSession(Protocol):
    character: str
    alive: bool
    going_away: bool
    turns: int
    audio_seconds: float
    on_change: Callable[[], None] | None

    def audio_in(self, pcm: bytes) -> list[LiveEvent]: ...
    def respond(self, text: str | None) -> AsyncIterator[LiveEvent]: ...
    def speak_first(self, line: str | None = None) -> AsyncIterator[LiveEvent]: ...
    async def note(self, text: str) -> None: ...
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
    async def open(self, character: str, recent: Sequence[Recent] = (), system: str = "") -> LiveSession: ...
    def transcriber(self) -> Transcriber: ...


@dataclass(frozen=True)
class Line:
    player: str
    reply: str


class FakeLiveSession:
    def __init__(
        self,
        character: str,
        lines: list[Line],
        speed: float,
        opener: str = "……",
        *,
        textless: bool = False,
        turn_usd: float = 0.0,
    ) -> None:
        self.character = character
        self.lines = lines
        self.speed = speed
        self.opener = opener
        self.textless = textless  # 有声音、没有人物的文字（补转写的测试）
        self.turn_usd = turn_usd
        self.n = 0
        self.heard = False  # 这一轮收到过玩家的音频（第一帧时出半句玩家字幕）
        self.alive = True
        self.going_away = False
        self.turns = 0
        self.audio_seconds = 0.0
        self.on_change: Callable[[], None] | None = None
        self.notes: list[str] = []  # 测试看：送进来的局势更新
        self.closed = False
        self.dying = False  # die(after_audio=True)：下一段回答说到一半断

    def goaway(self) -> None:
        """测试用：Live 说这条连接快到期了。"""
        self.going_away = True
        if self.on_change is not None:
            self.on_change()

    def die(self, *, mid_reply: bool = False) -> None:
        """测试用：连接断了。mid_reply：等下一段回答出了第一个音频再断。"""
        if mid_reply:
            self.dying = True
            return
        self.alive = False
        if self.on_change is not None:
            self.on_change()

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
        if not self.alive:
            raise LiveLost("假 Live：会话已经断了")
        await self._sleep(FIRST_AUDIO_MS)
        seconds = max(0.6, len(reply) * SECONDS_PER_CHAR)
        pcm = list(audio.chunks(seconds, CHUNK_MS))
        marks = {len(pcm) // 3: 1, 2 * len(pcm) // 3: 2}
        for i, chunk in enumerate(pcm):
            yield LiveEvent("audio", pcm=chunk)
            if self.dying:
                self.dying = False
                self.die()
                raise LiveLost("假 Live：说到一半断了")
            if i in marks and not self.textless:
                yield LiveEvent("output_partial", reply[: len(reply) * marks[i] // 3] or reply)
            await self._sleep(CHUNK_MS)
        self.turns += 1
        self.audio_seconds += seconds
        yield LiveEvent("turn_complete")
        yield LiveEvent("output_final", None if self.textless else reply)
        yield LiveEvent("usage", usd=self.turn_usd, usage={"outputAudioTokens": round(seconds * 25)})

    async def note(self, text: str) -> None:
        self.notes.append(text)

    async def close(self) -> None:
        self.closed = True
        self.alive = False


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


@dataclass
class Opened:
    """测试看：开了谁的会话、带了哪些最近的对话、系统指令。按 (人物, 最近的对话) 比较时和 B-4 的元组一样。"""

    character: str
    recent: list[Recent]
    system: str = ""
    session: FakeLiveSession | None = field(default=None, compare=False, repr=False)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, tuple):
            return (self.character, self.recent) == other
        if isinstance(other, Opened):
            return (self.character, self.recent, self.system) == (other.character, other.recent, other.system)
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]


class FakeLive:
    def __init__(self, fixtures: Path, speed: float = 1.0) -> None:
        doc = json.loads((fixtures / "lines.json").read_text(encoding="utf-8"))
        self.lines = {k: [Line(x["player"], x["reply"]) for x in v] for k, v in doc["characters"].items()}
        self.openers: dict[str, str] = doc.get("openers", {})
        self.plan_lines: list[str] = doc.get("planLines") or ["……"]
        self.planned = 0
        self.speed = speed
        self.opened: list[Opened] = []  # 测试看：开了谁的会话、带了哪些最近的对话
        self.fail_opens = 0  # 测试用：接下来几次开会话失败
        self.textless = False  # 测试用：之后开的会话有声音没文字
        self.turn_usd = 0.0  # 测试用：每轮记多少美元

    async def open(self, character: str, recent: Sequence[Recent] = (), system: str = "") -> FakeLiveSession:
        if self.fail_opens > 0:
            self.fail_opens -= 1
            raise LiveLost("假 Live：会话没建起来")
        opener = self.openers.get(character) or self.openers.get("default") or "……"
        lines = self.lines.get(character) or self.lines["default"]
        session = FakeLiveSession(character, lines, self.speed, opener, textless=self.textless, turn_usd=self.turn_usd)
        self.opened.append(Opened(character, list(recent), system, session))
        return session

    def live_sessions(self, character: str | None = None) -> list[FakeLiveSession]:
        """测试看：还开着的会话。"""
        return [
            o.session
            for o in self.opened
            if o.session is not None and not o.session.closed and character in (None, o.character)
        ]

    def transcriber(self) -> FakeTranscriber:
        line = self.plan_lines[self.planned % len(self.plan_lines)]
        self.planned += 1
        return FakeTranscriber(line)
