"""The real Gemini Live (B-10): one session per character in the gateway, implementing `LiveSession` from
`models/live.py`; the gateway does not distinguish real from fake.

- Connects directly to Vertex AI's `BidiGenerateContent` with `websockets` (handshake and `Auth` the same as B-6's
  `voice/models.py`), without an SDK. The message shapes follow what the google-genai SDK sends to Vertex
  (`spikes/backend/zj_spike` ran it on the Mac with the SDK), with camelCase fields.
- setup: audio output only, this character's voice, the system instruction (`gateway/brief.py`), transcription on both
  sides (the player side with ja-JP and proper-noun bias, S-025; removed with `ZJ_LIVE_TRANSCRIBE_HINTS=0` if
  rejected), automatic voice activity detection off (push to talk), a new activity interrupts the old answer, and by
  default no thinking level: S-090 measured with `probe` on the Mac that with `thinkingConfig` set (MINIMAL and LOW
  alike) Vertex closes the connection with 1007 "project not on the allowlist"; `ZJ_LIVE_THINKING=minimal` is kept
  for after getting on the list (S-1: minimal first-audio median 628 ms, unset 868 ms).
  **No session resumption** (backend-design 5.4: if on, Google stores the session server-side for up to 24 hours).
- One reader task owns the connection and hands messages to the current turn in order; one writer task sends in order.
  `audio_in` stays synchronous: audio goes into the send queue, and the player transcription received by the reader
  is emitted as a partial line on the next frame (one frame every 40 ms).
- Closing a turn (backend-design 3.1): after `turnComplete`, keep collecting transcriptions until the text of both
  sides has arrived and 0.6 s of silence has passed, or at most 3 s, then emit `output_final` (None if there is not a
  single character, and the gateway fills in a transcription). Usage takes the largest record of the turn; if none
  arrives within 1.5 s after `turnComplete`, 0.01 dollars is recorded (as in S-1, B-6: so it does not look free).
- Interruption: if the previous answer is still coming out when a new turn starts, the rest of the old answer's
  messages are dropped until its `interrupted` or `turnComplete` (at most 2 s, same as S-1b's `DRAIN_MAX_S`). The usage
  of the dropped part is charged to the next turn.
- Connection lost: `alive = False`, call `on_change`, and the turn in progress raises `LiveLost`. Quota and 429 raise
  `LiveLost(quota=True)`.
- Logs and exceptions never contain original words, the system instruction, the project or the address. If the server
  closes the connection while a session is being opened, the exception carries the close code and Google's reason
  (`close_note`: with project paths, model names, email addresses and long numbers removed, at most 160 characters),
  so it is clear at a glance which setup field was rejected.
- `probe`: sends only setup and closes on `setupComplete`, without speaking or spending money, trying each of several
  setups once (`zoujin-live probe`, S-090).

本物の Gemini Live（B-10）：ゲートウェイ内で登場人物ごとに 1 セッション。`models/live.py` の `LiveSession` を実装し、
ゲートウェイは本物と偽物を区別しない。

- `websockets` で Vertex AI の `BidiGenerateContent` に直接接続し（ハンドシェイクと `Auth` は B-6 の `voice/models.py`
  と同じ）、SDK は使わない。メッセージの形は google-genai SDK が Vertex に送るものに合わせ（`spikes/backend/zj_spike`
  で SDK を使って Mac 上で動作確認済み）、フィールドは camelCase。
- setup：音声出力のみ、この登場人物の声、システム指示（`gateway/brief.py`）、両側の書き起こし（プレイヤー側は ja-JP と
  固有名詞のバイアス付き、S-025。拒否されたら `ZJ_LIVE_TRANSCRIBE_HINTS=0` で外す）、自動音声検出オフ（プッシュ
  トゥトーク）、新しいアクティビティが古い返答を中断する。デフォルトでは思考レベルを設定しない：S-090 で Mac 上の
  `probe` で実測したところ、`thinkingConfig` を設定すると（MINIMAL も LOW も同じ）Vertex は 1007「プロジェクトが
  許可リストにない」で接続を閉じた。`ZJ_LIVE_THINKING=minimal` はリストに載った後のために残す（S-1：minimal の最初の
  音声の中央値 628 ms、設定なし 868 ms）。
  **セッション再開は使わない**（backend-design 5.4：使うと Google がサーバー側でこのセッションを最長 24 時間保存する）。
- 読み取りタスク 1 つが接続を持ち、メッセージを順に現在のターンへ渡す。書き込みタスク 1 つが順に送る。`audio_in` は
  同期のまま：音声は送信キューに入り、読み取りタスクが受け取ったプレイヤーの書き起こしは次のフレームで途中経過として
  出す（40 ms で 1 フレーム）。
- ターンの締めくくり（backend-design 3.1）：`turnComplete` の後も書き起こしを受け続け、両側のテキストがそろって
  0.6 秒静かになるか、最大 3 秒で `output_final` を出す（1 文字もなければ None で、ゲートウェイが書き起こしで補う）。
  使用量はこのターンで最大のものを取り、`turnComplete` から 1.5 秒以内に来なければ 0.01 ドルとして記録する（S-1、B-6
  と同じ：無料に見えないようにする）。
- 割り込み：前のターンの返答がまだ出ている間に新しいターンが始まったら、古い返答の残りのメッセージは、その
  `interrupted` か `turnComplete` まで捨てる（最大 2 秒、S-1b の `DRAIN_MAX_S` と同じ）。捨てた部分の使用量は次の
  ターンに付ける。
- 接続が切れた：`alive = False`、`on_change` を呼び、進行中のターンは `LiveLost` を投げる。利用枠、429 は
  `LiveLost(quota=True)` を投げる。
- ログと例外には元の発言、システム指示、プロジェクト、アドレスを書かない。セッション開始時にサーバーが接続を閉じたら、
  例外にはクローズコードと Google が示した理由を入れる（`close_note`：プロジェクトのパス、モデル名、メールアドレス、
  長い数字を除き、最大 160 文字）。setup のどのフィールドが拒否されたかがひと目で分かる。
- `probe`：setup だけを送り、`setupComplete` を受け取ったら閉じる。話さず、費用もかからない。いくつかの setup を
  1 回ずつ試す（`zoujin-live probe`、S-090）。
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from zoujin_backend.models.live import LiveEvent, LiveLost, Recent
from zoujin_backend.voice.models import LIVE_LOCATION, LIVE_MODEL, NO_USAGE_USD, live_cost, live_usage

Json = Any
log = logging.getLogger("zoujin.live")

IN_RATE = 16_000  # upstream PCM16 (api-contract 3.1) / 上り PCM16（api-contract 3.1）
OUT_RATE = 24_000  # downstream / 下り
# The player is waiting (focus, rebuild): contract section 6 says rebuild ≤ 1 s, S-1 measured 0.4〜1.1 s (#111 frontend
# review)
# プレイヤーが待っている（focus、再構築）：契約第 6 節では再構築 ≤ 1 s、S-1 の実測は 0.4〜1.1 s（#111 フロントエンドの
# レビュー）
SETUP_TIMEOUT_S = 5.0
TURN_TIMEOUT_S = 30.0  # from release to turnComplete / 離してから turnComplete まで
TAIL_QUIET_S = 0.6
TAIL_CAP_S = 3.0
USAGE_WAIT_S = 1.5
DRAIN_MAX_S = 2.0
PROPER_NOUNS = ("メロス", "セリヌンティウス", "ディオニス", "シラクス", "フィロストラトス")  # S-025
THINKING_ENV = "ZJ_LIVE_THINKING"
HINTS_ENV = "ZJ_LIVE_TRANSCRIBE_HINTS"
QUOTA_MARKS = ("RESOURCE_EXHAUSTED", "429", "QUOTA", "529")

# The cue sent in when a character speaks first (landing, the clarifying question of intent confirmation): so Live does
# not read the line out verbatim (S-071), and the character says it in their own words
# 登場人物が先に話すとき（着地、意図確認の聞き返し）に送る合図：Live にセリフをそのまま読ませず（S-071）、登場人物
# 自身の言葉で話させる
ARRIVAL_CUE = "（旅人がすぐ近くに来た。あなたから一言、短く声をかけてください。）"
ASK_CUE = "（次のことを、あなたの言葉で短く尋ねてください：{line}）"


class LiveLostQuota(LiveLost):
    """Quota, rate limit: not a problem with this connection, and switching sessions does not help (the gateway
    degrades).

    利用枠、レート制限：この接続の問題ではなく、セッションを替えても役に立たない（ゲートウェイは劣化動作に入る）。
    """


def setup_message(
    *,
    model_path: str,
    voice: str,
    system: str,
    thinking: str | None = None,
    hints: bool = True,
) -> Json:
    """The whole setup message (tests check: voice, ja-JP, bias words, automatic detection off, no session resumption).

    setup のメッセージ全体（テストが確認する：声、ja-JP、バイアス語、自動検出オフ、セッション再開なし）。
    """
    gen: Json = {
        "responseModalities": ["AUDIO"],
        "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
    }
    if thinking:
        gen["thinkingConfig"] = {"thinkingLevel": thinking.upper()}
    heard: Json = {}
    if hints:
        heard = {"languageCodes": ["ja-JP"], "customVocabulary": list(PROPER_NOUNS)}
    return {
        "setup": {
            "model": model_path,
            "generationConfig": gen,
            "systemInstruction": {"parts": [{"text": system}]},
            "inputAudioTranscription": heard,
            "outputAudioTranscription": {},
            "realtimeInputConfig": {
                "automaticActivityDetection": {"disabled": True},
                "activityHandling": "START_OF_ACTIVITY_INTERRUPTS",
            },
        }
    }


@dataclass
class _Turn:
    mode: str  # voice / text / cue
    q: asyncio.Queue[Json | None] = field(default_factory=asyncio.Queue)
    in_text: str = ""
    reported: str = ""
    usage: Json | None = None
    up_bytes: int = 0


class GeminiLiveSession:
    def __init__(self, ws: Any, character: str) -> None:
        self._ws = ws
        self.character = character
        self.alive = True
        self.going_away = False
        self.going_away_left: str | None = None
        self.turns = 0
        self.audio_seconds = 0.0
        self.on_change: Callable[[], None] | None = None
        self._out: asyncio.Queue[Json | None] = asyncio.Queue()
        self._turn: _Turn | None = None
        # The model is producing the previous turn's answer (after release, before turnComplete / interrupted)
        # モデルが前のターンの返答を出している（離した後、turnComplete / interrupted の前）
        self._busy = False
        self._drain_until = 0.0
        # Usage of the dropped part of an answer: charged to the next turn / 捨てた返答の使用量：次のターンに付ける
        self._orphan: Json | None = None
        self._quota = False
        self._reader: asyncio.Task[None] | None = None
        self._writer: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._reader = asyncio.ensure_future(self._read())
        self._writer = asyncio.ensure_future(self._write())

    # —— Connection / 接続 ——

    def _lost(self, why: str) -> None:
        if not self.alive:
            return
        self.alive = False
        log.info("Live session lost / Live セッションが切れた (%s)", why)
        if self._turn is not None:
            self._turn.q.put_nowait(None)
        self._out.put_nowait(None)
        if self.on_change is not None:
            self.on_change()

    async def _write(self) -> None:
        while True:
            msg = await self._out.get()
            if msg is None:
                return
            try:
                await self._ws.send(json.dumps(msg, ensure_ascii=False))
            except Exception as e:  # noqa: BLE001 - failing to send means lost / 送れなければ切れている
                self._lost(type(e).__name__)
                return

    async def _read(self) -> None:
        try:
            while True:
                raw = await self._ws.recv()
                msg = json.loads(raw)
                self._dispatch(msg)
        except asyncio.CancelledError:
            raise
        # Close codes, network errors and bad messages all count as lost
        # クローズコード、ネットワークエラー、壊れたメッセージはすべて切断とみなす
        except Exception as e:  # noqa: BLE001
            reason = ""
            rcvd = getattr(e, "rcvd", None)
            if rcvd is not None:
                reason = f"{rcvd.code} {rcvd.reason}"
            if any(m in reason.upper() for m in QUOTA_MARKS):
                self._quota = True
            self._lost(type(e).__name__ + (f" {reason[:4]}" if reason else ""))

    def _dispatch(self, msg: Json) -> None:
        if "goAway" in msg:
            self.going_away = True
            self.going_away_left = str((msg.get("goAway") or {}).get("timeLeft", ""))
            log.info("Live sent GoAway (time left / 残り %s) / Live が GoAway を送った", self.going_away_left)
            if self.on_change is not None:
                self.on_change()
        meta = msg.get("usageMetadata")
        sc = msg.get("serverContent")
        if self._drain_until:
            if time.monotonic() >= self._drain_until:
                self._drain_until = 0.0
            else:
                if meta:
                    self._orphan = _max_usage(self._orphan, meta)
                if sc and (sc.get("interrupted") or sc.get("turnComplete")):
                    self._drain_until = 0.0
                    self._busy = False
                return
        t = self._turn
        if meta:
            if t is not None:
                t.usage = _max_usage(t.usage, meta)
            else:
                self._orphan = _max_usage(self._orphan, meta)
        if sc is None:
            return
        if t is None:
            if sc.get("turnComplete") or sc.get("interrupted"):
                self._busy = False
            return
        heard = (sc.get("inputTranscription") or {}).get("text")
        if heard:
            t.in_text += heard
        t.q.put_nowait(sc)

    # —— One turn / 1 ターン ——

    def _begin(self, mode: str) -> _Turn:
        # The previous answer is still coming out: drop the rest until its interrupted / turnComplete (at most 2 s)
        # 前のターンの返答がまだ出ている：残りは、その interrupted / turnComplete まで捨てる（最大 2 秒）
        if self._busy:
            self._drain_until = time.monotonic() + DRAIN_MAX_S
        self._turn = _Turn(mode)
        if mode == "voice":
            self._out.put_nowait({"realtimeInput": {"activityStart": {}}})
        return self._turn

    def audio_in(self, pcm: bytes) -> list[LiveEvent]:
        if not self.alive:
            return []
        t = self._turn
        if t is None or t.mode != "voice":
            t = self._begin("voice")
        t.up_bytes += len(pcm)
        data = base64.b64encode(pcm).decode("ascii")
        self._out.put_nowait({"realtimeInput": {"audio": {"data": data, "mimeType": f"audio/pcm;rate={IN_RATE}"}}})
        if t.in_text != t.reported:
            t.reported = t.in_text
            return [LiveEvent("input_partial", t.in_text)]
        return []

    def respond(self, text: str | None) -> AsyncIterator[LiveEvent]:
        if text is None:
            t = self._turn if self._turn is not None and self._turn.mode == "voice" else self._begin("voice")
            self._out.put_nowait({"realtimeInput": {"activityEnd": {}}})
        else:
            t = self._begin("text")
            self._send_text(text, "user", complete=True)
        return self._answer(t)

    def speak_first(self, line: str | None = None) -> AsyncIterator[LiveEvent]:
        t = self._begin("cue")
        self._send_text(ASK_CUE.format(line=line) if line else ARRIVAL_CUE, "user", complete=True)
        return self._answer(t)

    def _send_text(self, text: str, role: str, *, complete: bool) -> None:
        content = {"turns": [{"role": role, "parts": [{"text": text}]}], "turnComplete": complete}
        self._out.put_nowait({"clientContent": content})

    async def note(self, text: str) -> None:
        """Update the situation mid-session (S-1 midsession: role=system, turnComplete=false,
        does not trigger an answer, 3/3).

        途中で状況を更新する（S-1 midsession：role=system、turnComplete=false。返答を起こさない、3/3）。
        """
        if self.alive:
            self._send_text(text, "system", complete=False)

    async def _answer(self, t: _Turn) -> AsyncIterator[LiveEvent]:
        self._busy = True
        out_text = ""
        down = 0
        done = False
        try:
            deadline = time.monotonic() + TURN_TIMEOUT_S
            while not done:
                sc = await self._next(t, deadline - time.monotonic(), "turnComplete")
                for part in (sc.get("modelTurn") or {}).get("parts") or []:
                    data = (part.get("inlineData") or {}).get("data")
                    if data:
                        pcm = base64.b64decode(data)
                        down += len(pcm)
                        yield LiveEvent("audio", pcm=pcm)
                said = (sc.get("outputTranscription") or {}).get("text")
                if said:
                    out_text += said
                    yield LiveEvent("output_partial", out_text)
                if sc.get("turnComplete") or sc.get("interrupted"):
                    done = True
            self._busy = False
            yield LiveEvent("turn_complete")
            # Closing: text from both sides has arrived and 0.6 s of silence, or at most 3 s
            # 締めくくり：両側のテキストがそろって 0.6 秒静か、または最大 3 秒
            cap = time.monotonic() + TAIL_CAP_S
            while True:
                have = bool(out_text) and (t.mode != "voice" or bool(t.in_text))
                wait = min(TAIL_QUIET_S if have else TAIL_CAP_S, cap - time.monotonic())
                if wait <= 0:
                    break
                try:
                    sc = await asyncio.wait_for(t.q.get(), timeout=wait)
                except TimeoutError:
                    break
                if sc is None:
                    break
                said = (sc.get("outputTranscription") or {}).get("text")
                if said:
                    out_text += said
            if t.mode == "voice":
                yield LiveEvent("input_final", t.in_text or None)
            yield LiveEvent("output_final", out_text or None)
            if t.usage is None and self.alive:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._usage_of(t), timeout=USAGE_WAIT_S)
            self.turns += 1
            self.audio_seconds += t.up_bytes / 2 / IN_RATE + down / 2 / OUT_RATE
            yield self._charge(t)
        finally:
            if self._turn is t:
                self._turn = None

    async def _usage_of(self, t: _Turn) -> None:
        while t.usage is None:
            await asyncio.sleep(0.05)

    def _charge(self, t: _Turn) -> LiveEvent:
        meta = t.usage
        orphan, self._orphan = self._orphan, None
        if meta is None:
            usage: dict[str, int] = {}
            usd = NO_USAGE_USD
        else:
            usage = live_usage(meta)
            usd = live_cost(usage)
        if orphan is not None:
            u2 = live_usage(orphan)
            usd += live_cost(u2)
            for k, v in u2.items():
                usage[k] = usage.get(k, 0) + v
        return LiveEvent("usage", usd=usd, usage=usage)

    async def _next(self, t: _Turn, left: float, what: str) -> Json:
        if left <= 0:
            self._lost(f"no {what} within {TURN_TIMEOUT_S:.0f} s / {TURN_TIMEOUT_S:.0f} 秒以内に {what} がない")
            raise LiveLost("Live turn timed out / Live のこのターンがタイムアウト")
        try:
            sc = await asyncio.wait_for(t.q.get(), timeout=left)
        except TimeoutError:
            self._lost(f"no {what} within {TURN_TIMEOUT_S:.0f} s / {TURN_TIMEOUT_S:.0f} 秒以内に {what} がない")
            raise LiveLost("Live turn timed out / Live のこのターンがタイムアウト") from None
        if sc is None:
            raise (LiveLostQuota if self._quota else LiveLost)("Live connection lost / Live の接続が切れた")
        return sc

    async def close(self) -> None:
        self.alive = False
        self._out.put_nowait(None)
        for task in (self._reader, self._writer):
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        with contextlib.suppress(Exception):
            await self._ws.close()


def _max_usage(old: Json | None, new: Json) -> Json:
    if old is None or int(new.get("totalTokenCount", 0)) >= int(old.get("totalTokenCount", 0)):
        return new
    return old


class GeminiLive:
    """The real implementation of `LiveModel`. voices: character → voice (`voice/hashire-merosu.json`, D-025).

    `connect` lets tests attach to a local fake Vertex Live service; for real, it connects to Vertex by region with an
    ADC token.

    `LiveModel` の本物の実装。voices：登場人物 → 声（`voice/hashire-merosu.json`、D-025）。

    `connect` はテストではローカルの偽 Vertex Live サービスにつなぐ。本物ではリージョンに応じて Vertex に ADC の
    トークン付きで接続する。
    """

    def __init__(
        self,
        *,
        model_path: str,
        voices: Mapping[str, str],
        connect: Callable[[], Awaitable[Any]],
        thinking: str | None = None,
        hints: bool = True,
        transcriber_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._model_path = model_path
        self._voices = voices
        self._connect = connect
        self._thinking = thinking
        self._hints = hints
        self._transcriber_factory = transcriber_factory
        # Milliseconds of the last few session setups (also recorded in the Trace)
        # 直近数回のセッション開始にかかったミリ秒（Trace にも記録）
        self.setup_ms: list[int] = []

    def voice(self, character: str) -> str:
        v = self._voices.get(character)
        if not v:
            raise LiveLost(
                f"{character} has no voice assigned / {character} の声が決まっていない (voice/hashire-merosu.json)"
            )
        return v

    async def open(self, character: str, recent: Sequence[Recent] = (), system: str = "") -> GeminiLiveSession:
        voice = self.voice(character)
        t0 = time.monotonic()
        try:
            ws = await asyncio.wait_for(self._connect(), timeout=SETUP_TIMEOUT_S)
        # Handshake failed: the address is not logged / ハンドシェイク失敗：アドレスは記録しない
        except Exception as e:  # noqa: BLE001
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 429:
                raise LiveLostQuota("Live handshake returned 429 / Live のハンドシェイクが 429 を返した") from None
            raise LiveLost(
                f"Live unreachable / Live に接続できない ({type(e).__name__}{f' HTTP {status}' if status else ''})"
            ) from None
        msg = setup_message(
            model_path=self._model_path, voice=voice, system=system, thinking=self._thinking, hints=self._hints
        )
        try:
            await ws.send(json.dumps(msg, ensure_ascii=False))
            first = json.loads(await asyncio.wait_for(ws.recv(), timeout=SETUP_TIMEOUT_S))
        except Exception as e:  # noqa: BLE001
            with contextlib.suppress(Exception):
                await ws.close()
            text = str(getattr(getattr(e, "rcvd", None), "reason", "")).upper()
            if any(m in text for m in QUOTA_MARKS):
                raise LiveLostQuota(
                    "Live returned a quota or rate-limit error / Live が利用枠またはレート制限のエラーを返した"
                ) from None
            note = close_note(e, self._model_path)
            raise LiveLost(
                f"Live session could not be opened / Live セッションを開けなかった "
                f"({type(e).__name__}{', ' + note if note else ''})"
            ) from None
        if "setupComplete" not in first:
            with contextlib.suppress(Exception):
                await ws.close()
            raise LiveLost(
                "Live session could not be opened: the first message is not setupComplete / "
                "Live セッションを開けなかった：最初のメッセージが setupComplete ではない"
            )
        self.setup_ms = [*self.setup_ms[-19:], round((time.monotonic() - t0) * 1000)]
        session = GeminiLiveSession(ws, character)
        session.start()
        return session

    def transcriber(self) -> Any:
        """Speaking a plan by voice at the end of an act: transcription only (3.11). For real, the audio is buffered and
        transcribed once after release (no partial subtitles).

        幕末にプランを声で話す：書き起こしだけ（3.11）。本物では音声をためておき、
        離した後に 1 回だけ書き起こす（途中経過の字幕はない）。
        """
        if self._transcriber_factory is None:
            raise LiveLost("No fallback transcriber configured / 補完の書き起こしが設定されていない")
        return self._transcriber_factory()


_SCRUB = (
    (re.compile(r"projects/[^/\s'\"]+"), "projects/…"),
    (re.compile(r"models/[^\s'\",]+"), "models/…"),
    (re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"), "…@…"),
    (re.compile(r"[0-9a-f]{8}-[0-9a-f-]+"), "…"),
    (re.compile(r"\d{6,}"), "…"),
)


def close_note(e: BaseException, model_path: str = "") -> str:
    """The close code and reason when the server closes the connection (the reason is written by Google and contains
    no player words). Projects, models, email addresses, session IDs and long numbers are removed; the project, region
    and model name in `model_path` are also replaced literally (the reason may contain the bare names, #140 data
    review).

    サーバーが接続を閉じたときのクローズコードと理由（理由は Google が書いたもので、プレイヤーの発言は含まない）。
    プロジェクト、モデル、メールアドレス、セッション ID、長い数字を除く。`model_path` にあるプロジェクト、リージョン、
    モデル名も文字どおりに置き換える（理由に名前がそのまま書かれていることがある、#140 データ担当のレビュー）。
    """
    rcvd = getattr(e, "rcvd", None)
    if rcvd is None:
        return ""
    reason = str(getattr(rcvd, "reason", "") or "")
    for literal in sorted(_literals(model_path), key=len, reverse=True):
        reason = reason.replace(literal, "…")
    for pattern, repl in _SCRUB:
        reason = pattern.sub(repl, reason)
    reason = reason[:160]
    return f"close code / クローズコード {getattr(rcvd, 'code', '?')}" + (f": {reason}" if reason else "")


def _literals(model_path: str) -> list[str]:
    """The three values in `projects/<project>/locations/<region>/publishers/google/models/<model>` (too-short ones are
    not replaced, so the reason does not get mangled).

    `projects/<プロジェクト>/locations/<リージョン>/publishers/google/models/<モデル>` の 3 つの値（短すぎるものは
    置き換えない。理由が崩れないようにするため）。
    """
    parts = model_path.split("/")
    keys = {"projects", "locations", "models"}
    return [parts[i + 1] for i, k in enumerate(parts[:-1]) if k in keys and len(parts[i + 1]) >= 4]


def setup_variants(*, model_path: str, voice: str, system: str) -> list[tuple[str, Json]]:
    """The setups `probe` tries: the current configuration, each with one thing removed, and finally the minimal one
    like B-6's pre-recording (which ran on the Mac).

    `probe` が試す setup：現在の設定、1 つずつ外したもの、最後に B-6 の事前収録のような最小構成（Mac
    上で動作確認済み）。
    """

    def make(edit: Callable[[Json], None]) -> Json:
        msg = setup_message(model_path=model_path, voice=voice, system=system)
        edit(msg["setup"])
        return msg

    def no_thinking(s: Json) -> None:
        s["generationConfig"].pop("thinkingConfig", None)

    def level(name: str) -> Callable[[Json], None]:
        def edit(s: Json) -> None:
            s["generationConfig"]["thinkingConfig"] = {"thinkingLevel": name}

        return edit

    def no_hints(s: Json) -> None:
        s["inputAudioTranscription"] = {}

    def no_ptt(s: Json) -> None:
        s.pop("realtimeInputConfig", None)

    def bare(s: Json) -> None:
        no_thinking(s)
        no_ptt(s)
        s.pop("inputAudioTranscription", None)

    return [
        ("current configuration (no thinking) / 現在の設定（思考なし）", make(lambda s: None)),
        ("thinking MINIMAL (ZJ_LIVE_THINKING=minimal) / 思考 MINIMAL", make(level("MINIMAL"))),
        ("thinking LOW (ZJ_LIVE_THINKING=low) / 思考 LOW", make(level("LOW"))),
        ("no bias words (ZJ_LIVE_TRANSCRIBE_HINTS=0) / バイアス語なし", make(no_hints)),
        ("no push-to-talk (realtimeInputConfig) / プッシュトゥトークなし", make(no_ptt)),
        ("minimal (same as B-6 pre-recording) / 最小構成（B-6 の事前収録と同じ）", make(bare)),
    ]


async def probe(connect: Callable[[], Awaitable[Any]], msg: Json) -> str:
    """Only open a session: close on `setupComplete`. Returns "ok", or the scrubbed failure reason.

    セッションを開くだけ：`setupComplete` を受け取ったら閉じる。"ok"、またはマスキングした失敗理由を返す。
    """
    path = str(msg.get("setup", {}).get("model", ""))
    try:
        ws = await asyncio.wait_for(connect(), timeout=SETUP_TIMEOUT_S)
    except Exception as e:  # noqa: BLE001
        status = getattr(getattr(e, "response", None), "status_code", None)
        return f"unreachable / 接続できない ({type(e).__name__}{f' HTTP {status}' if status else ''})"
    try:
        await ws.send(json.dumps(msg, ensure_ascii=False))
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=SETUP_TIMEOUT_S))
        return (
            "ok"
            if "setupComplete" in first
            else "first message is not setupComplete / 最初のメッセージが setupComplete ではない"
        )
    except Exception as e:  # noqa: BLE001
        note = close_note(e, path)
        return f"{type(e).__name__}{', ' + note if note else ''}"
    finally:
        with contextlib.suppress(Exception):
            await ws.close()


def model_path(project: str, location: str, model: str = LIVE_MODEL) -> str:
    return f"projects/{project}/locations/{location}/publishers/google/models/{model}"


def vertex_url(location: str) -> str:
    host = f"{location}-aiplatform.googleapis.com"
    return f"wss://{host}/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent"


def real_connect(env: Mapping[str, str]) -> tuple[Callable[[], Awaitable[Any]], str]:  # pragma: no cover
    """Only on the Mac: the function that connects to Vertex Live, and the model path. The project and region are read
    only from explicitly set environment variables (same as B-6's `real_models`).

    Mac 上のみ：Vertex Live に接続する関数とモデルのパス。プロジェクトとリージョンは明示的に設定した環境変数からだけ読む
    （B-6 の `real_models` と同じ）。
    """
    import websockets

    from zoujin_backend.models.vertex import AdcAuth, vertex_env
    from zoujin_backend.voice.models import LIVE_LOCATION_ENV

    project, _ = vertex_env(env)
    location = env.get(LIVE_LOCATION_ENV) or LIVE_LOCATION
    auth = AdcAuth()
    url = vertex_url(location)

    async def connect() -> Any:
        return await websockets.connect(
            url, additional_headers={"Authorization": f"Bearer {auth.token()}"}, max_size=16 * 1024 * 1024
        )

    return connect, model_path(project, location)


def real_live(env: Mapping[str, str], voices: Mapping[str, str], transcriber: Any) -> GeminiLive:  # pragma: no cover
    """Only on the Mac (`ZJ_LIVE=real`).

    Mac 上のみ（`ZJ_LIVE=real`）。
    """
    from zoujin_backend.gateway.fallback import BufferedTranscriber

    connect, path = real_connect(env)
    return GeminiLive(
        model_path=path,
        voices=voices,
        connect=connect,
        thinking=env.get(THINKING_ENV, "") or None,
        hints=env.get(HINTS_ENV, "1") != "0",
        transcriber_factory=lambda: BufferedTranscriber(transcriber),
    )
