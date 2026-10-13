"""The interface of Live (the characters' voice sessions) and its fake implementation (B-0 item 6). The real Live proxy
is not here (M2).

The fake Live reads `fixtures/fake-voice/lines.json`: for each character, a series of "what the player says + the
character's answer", used turn by turn (restarting from the beginning when exhausted). The player subtitle of a voice
turn is that entry's `player` (the fake has no speech recognition); a text turn uses only `reply`.
B-3: on landing, the character who speaks first says their line from `openers` (`speak_first`); when a plan is spoken
by voice at the end of an act, it is only transcribed, and the player subtitles come from `planLines` in turn
(`transcriber`).
B-4: the clarifying question of intent confirmation is also the character speaking first, saying the given line
(`speak_first(line)`). After a turn is voided, the session is rebuilt: `open` receives the "recent conversation" (the
text of the last few turns with this character on this connection, skipping voided ones), and the fake Live records
what it received (`opened`), so tests can check that the voided turn is not in it. The recent conversation lives only
in the gateway's memory and is never stored in the database or the Trace.
Character audio is 24 kHz PCM synthesized from the length of the answer (`zoujin_backend.audio`); no voice recorded
from real people or models is used.

B-10: the real Live is in `models/gemini_live.py` and implements the same interface as the fake Live here. Sessions
have a few more things for the gateway to watch: whether it is alive (`alive`), whether a GoAway was received
(`going_away`), how many turns were completed (`turns`), how many seconds of audio the session already holds
(`audio_seconds`, for reconciliation), a call to the gateway when something changes (`on_change`), and updating the
situation mid-session (`note`, which does not trigger an answer). Each finished turn emits one `usage` (this turn's
dollars and usage).
`open` receives the system instruction (persona, situation and recent conversation assembled by `gateway/brief.py`);
the fake Live only records it for tests to look at.
The fake Live's test switches: `fail_opens` (the next few session opens fail), `textless` (audio without text), and
the session's `goaway()`, `die()`.

Live（登場人物の音声セッション）のインターフェースと偽の実装（B-0 第 6 項）。本物の Live
のプロキシはここにはない（M2）。

偽 Live は `fixtures/fake-voice/lines.json` を読む：登場人物ごとに「プレイヤーの発言 + 登場人物の返答」の列があり、
ターンごとに順に使う（尽きたら最初に戻る）。音声ターンのプレイヤー字幕はその項目の `player`（偽物には音声認識がない）、
テキストターンは `reply` だけを使う。
B-3：着地時に先に話す登場人物は `openers` にある自分の一言を話す（`speak_first`）。
幕末にプランを声で話すときは書き起こしだけを行い、プレイヤー字幕は `planLines` を順に使う（`transcriber`）。
B-4：意図確認の聞き返しも登場人物が先に話し、与えられた一言を話す（`speak_first(line)`）。無効にした後はセッションを
再構築する：`open` は「直近の会話」（この接続でのこの登場人物との直近数ターンのテキスト。無効にしたものは飛ばす）を
受け取り、偽 Live は受け取った内容を記録する（`opened`）。テストは無効にしたターンが含まれていないことを確認する。
直近の会話はゲートウェイのメモリにだけあり、データベースにも Trace にも入れない。
登場人物の音声は返答の長さから合成した 24 kHz の PCM（`zoujin_backend.audio`）で、実在の人やモデルが録った声は使わない。

B-10：本物の Live は `models/gemini_live.py` にあり、ここの偽 Live と同じインターフェースを実装する。セッションには
ゲートウェイが見るものがいくつか増えた：生きているか（`alive`）、GoAway を受け取ったか（`going_away`）、何ターン
終えたか（`turns`）、セッション内にすでに何秒の音声があるか（`audio_seconds`、突き合わせ用）、変化があったときに
ゲートウェイを呼ぶ（`on_change`）、途中で状況を更新する（`note`、返答は起こさない）。各ターンの終わりに `usage`
（このターンのドルと使用量）を 1 つ出す。
`open` はシステム指示（`gateway/brief.py` が組み立てた人物設定、状況、直近の会話）を受け取る。偽 Live はテストが
見るために記録するだけ。
偽 Live のテスト用スイッチ：`fail_opens`（この後の何回かのセッション開始が失敗する）、`textless`（音声はあるが
テキストがない）、セッションの `goaway()`、`die()`。
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

# From release to the first audio chunk (near the server-side median measured in S-017)
# ボタンを離してから最初の音声チャンクまで（S-017 で実測したサーバー側の中央値付近）
FIRST_AUDIO_MS = 900
CHUNK_MS = 40
SECONDS_PER_CHAR = 0.16  # answer audio length estimated from the character count / 返答の音声の長さは文字数から見積もる


@dataclass(frozen=True)
class LiveEvent:
    """`output_final` with text None: the character produced not a single character of text in this turn (the real Live
    occasionally does this, S-071; the gateway fills in a transcription). `usage`: this turn's cost (`usd`) and usage
    (`usage`, numbers only), after `output_final`.

    text が None の `output_final`：このターンで登場人物のテキストが 1 文字もない（本物の Live でもまれに起きる、S-071。
    ゲートウェイが書き起こしで補う）。`usage`：このターンの費用（`usd`）と使用量（`usage`、数値のみ）。`output_final`
    の後に来る。
    """

    kind: LiveEventKind
    text: str | None = None
    pcm: bytes = b""
    usd: float = 0.0
    usage: Mapping[str, int] | None = None


class LiveLost(RuntimeError):
    """The Live connection was lost (mid-session, or it could not be opened). The message carries no original words,
    address or project.

    Live の接続が切れた（途中で、または開けなかった）。メッセージには元の発言、アドレス、プロジェクトを入れない。
    """


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
    """Transcription only, with no answer from a character (B-3: speaking a plan by voice at the end of an act,
    `activity_start purpose: "act_plan"`).

    書き起こしだけで、登場人物は答えない（B-3：幕末にプランを声で話す。`activity_start purpose: "act_plan"`）。
    """

    def audio_in(self, pcm: bytes) -> list[LiveEvent]: ...
    async def finish(self) -> str | None: ...


@dataclass(frozen=True)
class Recent:
    """One recent turn of conversation (carried into the new session when a session is rebuilt): what the player said
    and what the character answered.

    直近の会話の 1 ターン（セッション再構築時に新しいセッションへ持ち込む）：プレイヤーの発言と登場人物の返答。
    """

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
        # Audio without character text (test of filled-in transcription)
        # 音声のみ（書き起こし補完のテスト）
        self.textless = textless
        self.turn_usd = turn_usd
        self.n = 0
        # Player audio was received in this turn (the first frame yields half a line of player subtitles)
        # このターンでプレイヤーの音声を受け取った（最初のフレームでプレイヤー字幕を半分出す）
        self.heard = False
        self.alive = True
        self.going_away = False
        self.turns = 0
        self.audio_seconds = 0.0
        self.on_change: Callable[[], None] | None = None
        self.notes: list[str] = []  # for tests: situation updates sent in / テスト用：送られてきた状況の更新
        self.closed = False
        self.dying = False  # die(mid_reply=True): drops halfway through the next answer / 次の返答の途中で切れる
        # die(before_audio=True): drops before the next answer's audio
        # die(before_audio=True)：次の返答の音声前に切れる
        self.dying_early = False
        try:
            self.loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = None

    def _later(self, fn: Callable[[], None]) -> None:
        """Called from the test thread: run it back on the session's event loop.

        テストのスレッドから呼ばれる：セッションのあるイベントループに戻して実行する。
        """
        if self.loop is None:
            fn()
            return
        try:
            same = asyncio.get_running_loop() is self.loop
        except RuntimeError:
            same = False
        if same:
            fn()
        else:
            self.loop.call_soon_threadsafe(fn)

    def goaway(self) -> None:
        """For tests: Live says this connection is about to expire.

        テスト用：Live がこの接続はまもなく期限切れだと伝える。
        """

        def go() -> None:
            self.going_away = True
            if self.on_change is not None:
                self.on_change()

        self._later(go)

    def die(self, *, mid_reply: bool = False, before_audio: bool = False) -> None:
        """For tests: the connection drops. mid_reply: drop after the next answer's first audio; before_audio: drop as
        soon as the next answer starts.

        テスト用：接続が切れる。mid_reply：次の返答の最初の音声が出てから切れる。before_audio：次の返答が始まるとすぐに
        切れる。
        """
        if mid_reply:
            self.dying = True
            return
        if before_audio:
            self.dying_early = True
            return

        def go() -> None:
            self.alive = False
            if self.on_change is not None:
                self.on_change()

        self._later(go)

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
        """text None: a voice turn (after activity_end); otherwise a text turn.

        text が None：音声ターン（activity_end の後）。それ以外はテキストターン。
        """
        line = self._line()
        self.n += 1
        self.heard = False
        if text is None:
            yield LiveEvent("input_final", line.player)
        async for ev in self._say(line.reply):
            yield ev

    async def speak_first(self, line: str | None = None) -> AsyncIterator[LiveEvent]:
        """The character speaks first (the opener on landing; for the clarifying question of intent confirmation, the
        given line): no player words, only one line from the character.

        登場人物が先に話す（着地時の opener。意図確認の聞き返しでは与えられた line）：プレイヤーの発言はなく、登場人物の
        一言だけ。
        """
        async for ev in self._say(line or self.opener):
            yield ev

    async def _say(self, reply: str) -> AsyncIterator[LiveEvent]:
        if not self.alive:
            raise LiveLost("Fake Live: the session is already gone / 偽 Live：セッションはすでに切れている")
        await self._sleep(FIRST_AUDIO_MS)
        if self.dying_early:
            self.dying_early = False
            self.alive = False
            if self.on_change is not None:
                self.on_change()
            raise LiveLost("Fake Live: dropped before speaking / 偽 Live：声を出す前に切れた")
        seconds = max(0.6, len(reply) * SECONDS_PER_CHAR)
        pcm = list(audio.chunks(seconds, CHUNK_MS))
        marks = {len(pcm) // 3: 1, 2 * len(pcm) // 3: 2}
        for i, chunk in enumerate(pcm):
            yield LiveEvent("audio", pcm=chunk)
            if self.dying:
                self.dying = False
                self.alive = False
                if self.on_change is not None:
                    self.on_change()
                raise LiveLost("Fake Live: dropped halfway through speaking / 偽 Live：話している途中で切れた")
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
    """Fake transcription: half a line on the first frame, the whole line on release (`planLines` in turn); if not a
    single frame was received (nothing was said), an empty string on release.

    偽の書き起こし：最初のフレームで半分、離したときに全文（`planLines` を順に使う）。1 フレームも受け取らなかった
    （声が出なかった）ときは、離したときに空文字列。
    """

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
    """For tests: whose session was opened, which recent conversation it carried, and the system instruction. Compared
    by (character, recent conversation), it equals B-4's tuples.

    テスト用：誰のセッションを開いたか、どの直近の会話を持ち込んだか、システム指示。（登場人物、直近の会話）で比べると
    B-4 のタプルと等しい。
    """

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
        # For tests: whose sessions were opened, carrying which recent conversation
        # テスト用：誰のセッションを開いたか、どの直近の会話を持ち込んだか
        self.opened: list[Opened] = []
        # For tests: the next few session opens fail
        # テスト用：この後の何回かのセッション開始が失敗
        self.fail_opens = 0
        self.textless = False  # for tests: sessions opened later have audio but no text / テスト用：以後は音声のみ
        self.turn_usd = 0.0  # for tests: dollars recorded per turn / テスト用：1 ターンあたりに記録するドル

    async def open(self, character: str, recent: Sequence[Recent] = (), system: str = "") -> FakeLiveSession:
        if self.fail_opens > 0:
            self.fail_opens -= 1
            raise LiveLost("Fake Live: the session could not be opened / 偽 Live：セッションを開けなかった")
        opener = self.openers.get(character) or self.openers.get("default") or "……"
        lines = self.lines.get(character) or self.lines["default"]
        session = FakeLiveSession(character, lines, self.speed, opener, textless=self.textless, turn_usd=self.turn_usd)
        self.opened.append(Opened(character, list(recent), system, session))
        return session

    def live_sessions(self, character: str | None = None) -> list[FakeLiveSession]:
        """For tests: the sessions still open.

        テスト用：まだ開いているセッション。
        """
        return [
            o.session
            for o in self.opened
            if o.session is not None and not o.session.closed and character in (None, o.character)
        ]

    def transcriber(self) -> FakeTranscriber:
        line = self.plan_lines[self.planned % len(self.plan_lines)]
        self.planned += 1
        return FakeTranscriber(line)
