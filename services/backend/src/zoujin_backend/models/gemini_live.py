"""真的 Gemini Live（B-10）：网关里一个人物一条会话，实现 `models/live.py` 的 `LiveSession`，网关不分真假。

- 直接用 `websockets` 连 Vertex AI 的 `BidiGenerateContent`（握手、`Auth` 和 B-6 的 `voice/models.py` 一样），不加 SDK。
  消息的形状照 google-genai SDK 对 Vertex 发的（`spikes/backend/zj_spike` 用 SDK 在 Mac 上跑通过），字段用 camelCase。
- setup：只出音频、这个人物的声音、系统指令（`gateway/brief.py`）、两边的转写（玩家一侧带 ja-JP 和专有名词偏置，S-025；
  被拒时 `ZJ_LIVE_TRANSCRIBE_HINTS=0` 去掉）、关自动语音检测（按住说话）、新活动打断旧回答、
  默认不设思考等级：S-090 在 Mac 上 `probe` 实测，设了 `thinkingConfig`（MINIMAL、LOW 都一样）Vertex 以 1007「项目不在
  允许名单」关连接；`ZJ_LIVE_THINKING=minimal` 留给拿到名单以后（S-1：minimal 首音中位 628 ms，不设 868 ms）。
  **不开会话恢复**（backend-design 5.4：开了 Google 会在服务端存这条会话最长 24 小时）。
- 一个读任务持有连接，按顺序把消息交给当前这一轮；一个写任务按顺序发。`audio_in` 保持同步：音频进发送队列，
  读任务收到的玩家转写在下一帧时作为半句吐出（40 ms 一帧）。
- 一轮的收尾（backend-design 3.1）：`turnComplete` 之后继续收转写，两边的文字都到、静默 0.6 秒，或最多 3 秒，再吐
  `output_final`（一个字都没有就是 None，网关补转写）。用量取这一轮最大的那条，`turnComplete` 后 1.5 秒内没到按 0.01
  美元记（同 S-1、B-6：不让它看起来是免费的）。
- 打断：上一轮的回答还在出、新的一轮开始了，旧回答剩下的消息丢掉，直到它的 `interrupted` 或 `turnComplete`（最多 2 秒，
  同 S-1b 的 `DRAIN_MAX_S`）。丢掉的那段的用量记到下一轮上。
- 连接断了：`alive = False`、叫 `on_change`，正在进行的一轮抛 `LiveLost`。配额、429 的抛 `LiveLost(quota=True)`。
- 日志和异常里不写原话、系统指令、项目和地址。建会话时服务端关了连接，异常里带关闭码和 Google 给的原因（`close_note`：
  去掉项目路径、模型名、邮箱和长数字，最多 160 字），一眼看出 setup 哪个字段不收。
- `probe`：只发 setup、收到 `setupComplete` 就关，不说话、不花钱，几种 setup 各试一次（`zoujin-live probe`，S-090）。
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

IN_RATE = 16_000  # 上行 PCM16（api-contract 3.1）
OUT_RATE = 24_000  # 下行
SETUP_TIMEOUT_S = 5.0  # 玩家在等（focus、重建）：契约第 6 节重建 ≤ 1 s，S-1 实测 0.4〜1.1 s（#111 前端评审）
TURN_TIMEOUT_S = 30.0  # 松开到 turnComplete
TAIL_QUIET_S = 0.6
TAIL_CAP_S = 3.0
USAGE_WAIT_S = 1.5
DRAIN_MAX_S = 2.0
PROPER_NOUNS = ("メロス", "セリヌンティウス", "ディオニス", "シラクス", "フィロストラトス")  # S-025
THINKING_ENV = "ZJ_LIVE_THINKING"
HINTS_ENV = "ZJ_LIVE_TRANSCRIBE_HINTS"
QUOTA_MARKS = ("RESOURCE_EXHAUSTED", "429", "QUOTA", "529")

# 人物先开口（落地、意图确认的反问）时送进去的提示：不让 Live 照读台词（S-071），让人物用自己的话说
ARRIVAL_CUE = "（旅人がすぐ近くに来た。あなたから一言、短く声をかけてください。）"
ASK_CUE = "（次のことを、あなたの言葉で短く尋ねてください：{line}）"


class LiveLostQuota(LiveLost):
    """配额、限流：不是这条连接的问题，换会话也没用（网关降级）。"""


def setup_message(
    *,
    model_path: str,
    voice: str,
    system: str,
    thinking: str | None = None,
    hints: bool = True,
) -> Json:
    """setup 的整条消息（测试查：声音、ja-JP、偏置词、关自动检测、没有会话恢复）。"""
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
        self._busy = False  # 模型在出上一轮的回答（松开以后、turnComplete / interrupted 之前）
        self._drain_until = 0.0
        self._orphan: Json | None = None  # 丢掉的那段回答的用量：记到下一轮
        self._quota = False
        self._reader: asyncio.Task[None] | None = None
        self._writer: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._reader = asyncio.ensure_future(self._read())
        self._writer = asyncio.ensure_future(self._write())

    # —— 连接 ——

    def _lost(self, why: str) -> None:
        if not self.alive:
            return
        self.alive = False
        log.info("Live 会话断了（%s）", why)
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
            except Exception as e:  # noqa: BLE001 - 发不出去就是断了
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
        except Exception as e:  # noqa: BLE001 - 关闭码、网络错误、坏消息都当断了
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
            log.info("Live 发了 GoAway（剩 %s）", self.going_away_left)
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

    # —— 一轮 ——

    def _begin(self, mode: str) -> _Turn:
        if self._busy:  # 上一轮的回答还在出：剩下的丢掉，直到它的 interrupted / turnComplete（最多 2 秒）
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
        """中途更新局势（S-1 midsession：role=system、turnComplete=false，不触发回答，3/3）。"""
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
            # 收尾：两边的文字都到、静默 0.6 秒，或最多 3 秒
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
    """`LiveModel` 的真实现。voices：人物 → 声音（`voice/hashire-merosu.json`，D-025）。

    `connect` 给测试接本机的假 Vertex Live 服务；真的时候按地区连 Vertex，带 ADC 的令牌。"""

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
        self.setup_ms: list[int] = []  # 最近几次建会话的毫秒（Trace 也记）

    def voice(self, character: str) -> str:
        v = self._voices.get(character)
        if not v:
            raise LiveLost(f"{character} 没有定声音（voice/hashire-merosu.json）")
        return v

    async def open(self, character: str, recent: Sequence[Recent] = (), system: str = "") -> GeminiLiveSession:
        voice = self.voice(character)
        t0 = time.monotonic()
        try:
            ws = await asyncio.wait_for(self._connect(), timeout=SETUP_TIMEOUT_S)
        except Exception as e:  # noqa: BLE001 - 握手失败：不记地址
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 429:
                raise LiveLostQuota("Live 握手回 429") from None
            raise LiveLost(f"Live 连不上（{type(e).__name__}{f' HTTP {status}' if status else ''}）") from None
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
                raise LiveLostQuota("Live 回配额或限流错误") from None
            note = close_note(e, self._model_path)
            raise LiveLost(f"Live 会话没建起来（{type(e).__name__}{'，' + note if note else ''}）") from None
        if "setupComplete" not in first:
            with contextlib.suppress(Exception):
                await ws.close()
            raise LiveLost("Live 会话没建起来：第一条消息不是 setupComplete")
        self.setup_ms = [*self.setup_ms[-19:], round((time.monotonic() - t0) * 1000)]
        session = GeminiLiveSession(ws, character)
        session.start()
        return session

    def transcriber(self) -> Any:
        """幕末用声音说打算：只转写（3.11）。真的时候攒下音频、松开以后补转写一次（没有半句字幕）。"""
        if self._transcriber_factory is None:
            raise LiveLost("没有配补转写")
        return self._transcriber_factory()


_SCRUB = (
    (re.compile(r"projects/[^/\s'\"]+"), "projects/…"),
    (re.compile(r"models/[^\s'\",]+"), "models/…"),
    (re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"), "…@…"),
    (re.compile(r"[0-9a-f]{8}-[0-9a-f-]+"), "…"),
    (re.compile(r"\d{6,}"), "…"),
)


def close_note(e: BaseException, model_path: str = "") -> str:
    """服务端关连接时的关闭码和原因（原因是 Google 写的，不含玩家的话）。去掉项目、模型、邮箱、会话 ID、长数字；
    `model_path` 里的项目、地区、模型名按字面也换掉（原因里可能直接写裸名字，#140 数据评审）。"""
    rcvd = getattr(e, "rcvd", None)
    if rcvd is None:
        return ""
    reason = str(getattr(rcvd, "reason", "") or "")
    for literal in sorted(_literals(model_path), key=len, reverse=True):
        reason = reason.replace(literal, "…")
    for pattern, repl in _SCRUB:
        reason = pattern.sub(repl, reason)
    reason = reason[:160]
    return f"关闭码 {getattr(rcvd, 'code', '?')}" + (f"：{reason}" if reason else "")


def _literals(model_path: str) -> list[str]:
    """`projects/<项目>/locations/<地区>/publishers/google/models/<模型>` 里的三个值（太短的不换，免得把原因换花）。"""
    parts = model_path.split("/")
    keys = {"projects", "locations", "models"}
    return [parts[i + 1] for i, k in enumerate(parts[:-1]) if k in keys and len(parts[i + 1]) >= 4]


def setup_variants(*, model_path: str, voice: str, system: str) -> list[tuple[str, Json]]:
    """`probe` 试的几种 setup：现在的配置，各去掉一样，最后是 B-6 预录那样的最简（它在 Mac 上跑通过）。"""

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
        ("现在的配置（不设思考）", make(lambda s: None)),
        ("思考 MINIMAL（ZJ_LIVE_THINKING=minimal）", make(level("MINIMAL"))),
        ("思考 LOW（ZJ_LIVE_THINKING=low）", make(level("LOW"))),
        ("不带偏置词（ZJ_LIVE_TRANSCRIBE_HINTS=0）", make(no_hints)),
        ("不带按住说话（realtimeInputConfig）", make(no_ptt)),
        ("最简（同 B-6 预录）", make(bare)),
    ]


async def probe(connect: Callable[[], Awaitable[Any]], msg: Json) -> str:
    """只建会话：收到 `setupComplete` 就关。回 "ok"，或去敏的失败原因。"""
    path = str(msg.get("setup", {}).get("model", ""))
    try:
        ws = await asyncio.wait_for(connect(), timeout=SETUP_TIMEOUT_S)
    except Exception as e:  # noqa: BLE001
        status = getattr(getattr(e, "response", None), "status_code", None)
        return f"连不上（{type(e).__name__}{f' HTTP {status}' if status else ''}）"
    try:
        await ws.send(json.dumps(msg, ensure_ascii=False))
        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=SETUP_TIMEOUT_S))
        return "ok" if "setupComplete" in first else "第一条消息不是 setupComplete"
    except Exception as e:  # noqa: BLE001
        note = close_note(e, path)
        return f"{type(e).__name__}{'，' + note if note else ''}"
    finally:
        with contextlib.suppress(Exception):
            await ws.close()


def model_path(project: str, location: str, model: str = LIVE_MODEL) -> str:
    return f"projects/{project}/locations/{location}/publishers/google/models/{model}"


def vertex_url(location: str) -> str:
    host = f"{location}-aiplatform.googleapis.com"
    return f"wss://{host}/ws/google.cloud.aiplatform.v1beta1.LlmBidiService/BidiGenerateContent"


def real_connect(env: Mapping[str, str]) -> tuple[Callable[[], Awaitable[Any]], str]:  # pragma: no cover
    """只在 Mac 上：连 Vertex Live 的函数和模型路径。项目和地区只从显式设的环境变量读（同 B-6 的 `real_models`）。"""
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
    """只在 Mac 上（`ZJ_LIVE=real`）。"""
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
