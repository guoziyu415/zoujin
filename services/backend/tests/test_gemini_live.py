"""B-10：真 Live 客户端对着本机的假 Vertex Live 服务（不连外网）。"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any, cast

import pytest
from websockets.asyncio.client import connect
from zoujin_backend.models import gemini_live
from zoujin_backend.models.gemini_live import GeminiLive, LiveLostQuota, setup_message
from zoujin_backend.models.live import LiveEvent, LiveLost, Recent
from zoujin_backend.voice.models import NO_USAGE_USD

from .fake_vertex_live import FakeVertexLive, Reply, Script, running

VOICES = {"char.melos": "Fenrir", "char.old-man": "Sadaltager"}
MIC = bytes(1280)


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gemini_live, "TAIL_QUIET_S", 0.1)
    monkeypatch.setattr(gemini_live, "TAIL_CAP_S", 0.5)
    monkeypatch.setattr(gemini_live, "USAGE_WAIT_S", 0.3)
    monkeypatch.setattr(gemini_live, "SETUP_TIMEOUT_S", 1.0)
    monkeypatch.setattr(gemini_live, "TURN_TIMEOUT_S", 2.0)


def model(fake: FakeVertexLive) -> GeminiLive:
    async def dial() -> Any:
        return await connect(fake.url)

    return GeminiLive(model_path="projects/p/locations/l/publishers/google/models/m", voices=VOICES, connect=dial)


def run(fn: Callable[[], Awaitable[None]]) -> None:
    asyncio.run(fn())  # type: ignore[arg-type]


async def collect(it: Any) -> list[LiveEvent]:
    return [ev async for ev in it]


def kinds(evs: list[LiveEvent]) -> list[str]:
    out: list[str] = []
    for e in evs:
        if not out or out[-1] != e.kind or e.kind not in ("audio", "output_partial"):
            out.append(e.kind)
    return out


def test_setup_is_push_to_talk_japanese_and_never_resumable() -> None:
    msg = setup_message(model_path="m", voice="Fenrir", system="SYS")["setup"]
    assert msg["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Fenrir"
    assert msg["generationConfig"]["responseModalities"] == ["AUDIO"]
    assert msg["inputAudioTranscription"]["languageCodes"] == ["ja-JP"]
    assert "セリヌンティウス" in msg["inputAudioTranscription"]["customVocabulary"]
    assert msg["outputAudioTranscription"] == {}
    assert msg["realtimeInputConfig"]["automaticActivityDetection"] == {"disabled": True}
    assert "sessionResumption" not in msg and "session_resumption" not in str(msg)
    assert msg["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "MINIMAL"}
    bare = setup_message(model_path="m", voice="Fenrir", system="SYS", thinking=None, hints=False)["setup"]
    assert bare["inputAudioTranscription"] == {} and "thinkingConfig" not in bare["generationConfig"]


def test_voice_turn_streams_audio_and_both_transcripts() -> None:
    async def main() -> None:
        reply = Reply(player="こんにちは", text=["村から", "来た。"], chunks=3, late=["妹の婚礼だ。"])
        async with running(Script([reply])) as fake:
            s = await model(fake).open("char.melos", [Recent("前の", "答え")], "SYSTEM")
            assert fake.conns[0].setup["systemInstruction"]["parts"][0]["text"] == "SYSTEM"
            assert s.audio_in(MIC) == []
            s.audio_in(MIC)
            evs = await collect(s.respond(None))
            assert kinds(evs) == [
                "audio",
                "output_partial",
                "audio",
                "output_partial",
                "audio",
                "turn_complete",
                "input_final",
                "output_final",
                "usage",
            ]
            final = next(e for e in evs if e.kind == "output_final")
            assert final.text == "村から来た。妹の婚礼だ。"  # turnComplete 之后到的也收进定稿
            assert next(e for e in evs if e.kind == "input_final").text == "こんにちは"
            usage = evs[-1]
            assert usage.usd > 0 and usage.usage is not None and usage.usage["outputAudioTokens"] == 50
            assert s.turns == 1 and s.audio_seconds > 0
            sent = fake.conns[0].sent("realtimeInput")
            assert "activityStart" in sent[0]["realtimeInput"] and "activityEnd" in sent[-1]["realtimeInput"]
            audio = [m for m in sent if "audio" in m["realtimeInput"]]
            assert len(audio) == 2 and base64.b64decode(audio[0]["realtimeInput"]["audio"]["data"]) == MIC
            await s.close()

    run(main)


def test_text_turn_note_and_speak_first() -> None:
    async def main() -> None:
        async with running(Script([Reply(text=["ああ。"]), Reply(text=["よう。"])])) as fake:
            s = await model(fake).open("char.old-man")
            evs = await collect(s.respond("こんばんは"))
            assert next(e for e in evs if e.kind == "output_final").text == "ああ。"
            assert not [e for e in evs if e.kind == "input_final"]  # 文字一轮没有玩家转写
            await s.note("【状況の変化】\n- 時：夜")
            evs = await collect(s.speak_first())
            assert next(e for e in evs if e.kind == "output_final").text == "よう。"
            got = fake.conns[0].sent("clientContent")
            assert got[0]["clientContent"]["turns"][0] == {"role": "user", "parts": [{"text": "こんばんは"}]}
            assert got[1]["clientContent"] == {
                "turns": [{"role": "system", "parts": [{"text": "【状況の変化】\n- 時：夜"}]}],
                "turnComplete": False,
            }
            assert got[2]["clientContent"]["turns"][0]["parts"][0]["text"] == gemini_live.ARRIVAL_CUE
            await s.close()

    run(main)


def test_no_text_and_missing_usage() -> None:
    async def main() -> None:
        async with running(Script([Reply(text=[], usage=None)])) as fake:
            s = await model(fake).open("char.melos")
            evs = await collect(s.respond("…"))
            assert next(e for e in evs if e.kind == "output_final").text is None  # 网关补转写
            assert evs[-1].kind == "usage" and evs[-1].usd == NO_USAGE_USD  # 用量没来：不算免费
            await s.close()

    run(main)


def test_goaway_is_flagged_and_reported() -> None:
    async def main() -> None:
        async with running(Script([Reply(goaway=True)])) as fake:
            s = await model(fake).open("char.melos")
            seen: list[bool] = []
            s.on_change = lambda: seen.append(s.going_away)
            await collect(s.respond("x"))
            assert s.going_away and seen == [True] and s.alive
            await s.close()

    run(main)


def test_drop_mid_reply_raises_live_lost() -> None:
    async def main() -> None:
        async with running(Script([Reply(drop_after_audio=True)])) as fake:
            s = await model(fake).open("char.melos")
            changed: list[bool] = []
            s.on_change = lambda: changed.append(s.alive)
            got: list[LiveEvent] = []
            with pytest.raises(LiveLost):
                async for ev in s.respond("x"):
                    got.append(ev)
            assert [e.kind for e in got] == ["audio"] and not s.alive and changed == [False]
            await s.close()

    run(main)


def test_interrupted_reply_is_drained_before_the_next_turn() -> None:
    async def main() -> None:
        slow = Reply(text=["長い", "長い", "話"], chunks=6, delay=0.05)
        async with running(Script([slow, Reply(text=["次。"])])) as fake:
            s = await model(fake).open("char.melos")
            it = cast(AsyncGenerator[LiveEvent], s.respond("一つ目"))
            first = await it.__anext__()
            assert first.kind == "audio"
            await it.aclose()  # 网关的 _cut：取消转发
            evs = await collect(s.respond("二つ目"))
            final = next(e for e in evs if e.kind == "output_final")
            assert final.text == "次。"  # 旧回答剩下的分片和文字都没混进来
            await s.close()

    run(main)


@pytest.mark.parametrize("how", ["close", "wrong", "silent"])
def test_setup_failures(how: str) -> None:
    async def main() -> None:
        async with running(Script(setup=how)) as fake:
            with pytest.raises(LiveLost):
                await model(fake).open("char.melos")

    run(main)


def test_unknown_voice_and_quota() -> None:
    async def main() -> None:
        async with running(Script()) as fake:
            with pytest.raises(LiveLost):
                await model(fake).open("char.nobody")

            async def refused() -> Any:
                class Resp:
                    status_code = 429

                e = RuntimeError("429")
                e.response = Resp()  # type: ignore[attr-defined]
                raise e

            m = GeminiLive(model_path="m", voices=VOICES, connect=refused)
            with pytest.raises(LiveLostQuota):
                await m.open("char.melos")

    run(main)
