"""B-10：网关的 Live 会话管理（假 Live）。

预热、定期重建、GoAway、中途断了、开不起来、中途更新局势、补转写、花费、闲置。
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any, cast

import pytest
from zoujin_backend.gateway.fallback import FakeAudioTranscriber
from zoujin_backend.models.live import Recent

from . import test_gateway_b4 as b4
from .conftest import OLD, Env
from .test_b4 import MELOS
from .test_gateway_b4 import InProc, Make, Play, advance_to, metrics, of, said, settle, turn_row

inproc = b4.inproc  # pytest 的 fixture 按名字找
play = b4.play

pytestmark = pytest.mark.db

Json = Any
SPEED = 0.05  # 去抖 0.1 秒、建会话 0.04 秒


def wait_for(cond: Any, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not cond():
        assert time.monotonic() < deadline, "等不到"
        time.sleep(0.02)


def spans(s: InProc, name: str) -> list[Json]:
    return [dict(x) for x in s.gw.tracer.named(name)]


def test_near_warms_and_focus_is_ready_at_once(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    p.send({"type": "near", "character": OLD})
    wait_for(lambda: len(s.live.opened) == 1)
    time.sleep(0.1)
    start = len(p.log)
    p.focus(OLD)
    assert not [m for m in p.log[start:] if m["type"] == "session_preparing"]  # 预热命中：直接就绪
    assert spans(s, "live.session")[0]["reason"] == "warm"
    assert "# いまの状況" in s.live.opened[0].system and "時：" in s.live.opened[0].system


def test_near_then_far_within_the_debounce_opens_nothing(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(0.5)  # 去抖 1 秒
    p = play(s)
    p.send({"type": "near", "character": OLD})
    p.send({"type": "far", "character": OLD})
    time.sleep(1.3)
    settle(p)
    assert s.live.opened == []


def test_focus_during_the_debounce_opens_at_once_and_only_once(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(0.5)  # 去抖 1 秒
    p = play(s)
    p.send({"type": "near", "character": OLD})
    p.send({"type": "focus", "character": OLD})
    p.expect("session_preparing", character=OLD, reason="switch")
    p.expect("session_ready", character=OLD, timeout=3)  # 不等剩下的去抖
    time.sleep(1.3)  # 去抖到点也不再开
    assert len(s.live.opened) == 1


def test_warming_another_closes_the_old_warm(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    p.send({"type": "near", "character": OLD})
    wait_for(lambda: len(s.live.opened) == 1)
    p.send({"type": "near", "character": MELOS})
    wait_for(lambda: len(s.live.opened) == 2)
    wait_for(lambda: [x.character for x in s.live.opened if x.session and not x.session.closed] == [MELOS])


def test_rebuild_after_n_turns_is_silent_and_carries_recent(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    s.gw.settings = replace(s.gw.settings, live_rebuild_turns=2)
    p = play(s)
    p.focus(OLD)
    start = len(p.log)
    first = p.text("こんにちは。")
    p.expect("turn_settled", turnId=first)
    second = p.text("この市は、ずいぶん静かですね。")
    p.expect("turn_settled", turnId=second)
    wait_for(lambda: len(s.live.opened) == 2)
    wait_for(lambda: len(s.live.live_sessions(OLD)) == 1 and s.live.live_sessions(OLD)[0] is s.live.opened[1].session)
    replies = [p.find("transcript", turnId=t, speaker=OLD, final=True)["text"] for t in (first, second)]
    assert s.live.opened[1].recent == [
        Recent("こんにちは。", replies[0]),
        Recent("この市は、ずいぶん静かですね。", replies[1]),
    ]
    assert "# さっきまでの会話" in s.live.opened[1].system
    settle(p)
    assert not [m for m in p.log[start:] if m["type"] in ("session_preparing", "session_ready")]
    assert spans(s, "live.session")[-1]["reason"] == "rebuild_turns"
    third = p.text("また来ます。")  # 新会话上照常说
    p.expect("turn_settled", turnId=third)


def test_goaway_swaps_at_the_next_pause(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    p.focus(OLD)
    old = s.live.live_sessions(OLD)[0]
    old.goaway()
    wait_for(lambda: len(s.live.opened) == 2 and old.closed)
    assert spans(s, "live.session")[-1]["reason"] == "rebuild_goaway"
    t = p.text("こんにちは。")
    p.expect("turn_settled", turnId=t)


def test_live_dropping_mid_reply_ends_the_turn_then_rebuilds(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    p.focus(OLD)
    s.live.live_sessions(OLD)[0].die(mid_reply=True)
    t = p.text("こんにちは。")
    done = p.expect("turn_complete", turnId=t)  # 不是 interrupted：那只表示玩家打断（#111 前端评审）
    assert done["audio"] is True and done["metrics"]["serverReleaseToFirstAudioMs"] is not None
    final = p.expect("transcript", turnId=t, speaker=OLD, final=True)
    assert final["source"] == "fallback"  # 出声了、还没出字：补转写
    p.expect("session_preparing", character=OLD, reason="rebuild")
    p.expect("session_ready", character=OLD)
    p.expect("turn_settled", turnId=t)  # 不是 lost：照常交给叙事者
    assert not of(p, t, "interrupted")
    assert turn_row(env, t)["status"] != "lost"
    assert [x for x in spans(s, "live.turn") if x.get("status") == "lost"]
    again = p.text("聞こえますか。")
    p.expect("turn_settled", turnId=again)


def test_live_dropping_before_any_audio_is_no_response(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    p.focus(OLD)
    s.live.live_sessions(OLD)[0].die(before_audio=True)
    t = p.text("こんにちは。")
    done = p.expect("turn_complete", turnId=t)
    assert done["audio"] is False
    settled = p.expect("turn_settled", turnId=t)
    assert (settled["outcome"], settled["minutes"]) == ("no_response", 0)
    assert not of(p, t, "interrupted")
    p.expect("session_preparing", character=OLD, reason="rebuild")
    p.expect("session_ready", character=OLD)
    again = p.text("聞こえますか。")
    p.expect("turn_settled", turnId=again)


def test_two_failed_opens_degrade_then_focus_retries(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    s.live.fail_opens = 2
    p.send({"type": "focus", "character": OLD})
    p.expect("session_preparing", character=OLD, reason="switch")
    assert p.expect("degraded")["reason"] == "service"
    assert p.expect("session_ready", character=OLD)["voiceAvailable"] is False
    t = p.text("こんにちは。")
    assert p.expect("error")["error"]["code"] == "voice_unavailable"
    assert not of(p, t, "turn_complete")
    p.focus(OLD)  # 再 focus 再试
    t = p.text("こんにちは。")
    p.expect("turn_settled", turnId=t)


def test_commit_sends_a_situation_note(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    p.focus(OLD)
    session = s.live.live_sessions(OLD)[0]
    advance_to(env, s, p.pid, 1050 + 300)  # 时刻变了：局势说明里「時」那一条变了
    p.expect("commit")
    wait_for(lambda: bool(session.notes))
    assert session.notes[0].startswith("【状況の変化】") and "時：" in session.notes[0]
    assert spans(s, "live.note")


def test_fallback_transcript_when_live_gives_no_text(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    s.live.textless = True
    tr = cast(FakeAudioTranscriber, s.gw.transcriber)
    tr.text = "……ほう。"
    p = play(s)
    p.focus(OLD)
    t = p.text("こんにちは。")
    final = p.expect("transcript", turnId=t, speaker=OLD, final=True)
    assert (final["text"], final["source"]) == ("……ほう。", "fallback")
    assert tr.calls and tr.calls[0][1] == 24_000
    p.expect("turn_settled", turnId=t)
    assert said(env, t)[1][:2] == (OLD, "……ほう。")
    assert turn_row(env, t)["character_text_missing"] is False

    tr.fail = True
    t2 = p.text("この市は、ずいぶん静かですね。")
    final = p.expect("transcript", turnId=t2, speaker=OLD, final=True)
    assert (final["text"], final["source"]) == (None, "fallback")
    p.expect("turn_settled", turnId=t2)
    assert turn_row(env, t2)["character_text_missing"] is True


def test_cost_and_trace_without_words(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    s.live.turn_usd = 0.002
    p = play(s)
    p.focus(OLD)
    t = p.text("こんにちは。")
    p.expect("turn_settled", turnId=t)
    wait_for(lambda: float(metrics(env, p.pid)["cost_live_usd"]) > 0)
    assert float(metrics(env, p.pid)["cost_live_usd"]) == pytest.approx(0.002)
    turn = spans(s, "live.turn")[-1]
    assert turn["session_turn"] == 1 and turn["cost_usd"] == 0.002 and turn["first_audio_ms"] >= 0
    dumped = repr(s.gw.tracer.spans)
    assert "こんにちは" not in dumped and "旅" not in dumped  # 原话、系统指令都不进 Trace


def test_idle_session_is_closed(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    p.focus(OLD)
    s.gw.conns[p.pid].voices.idle_s = 0.2
    p.send({"type": "unfocus", "reason": "walk_away"})
    wait_for(lambda: not s.live.live_sessions(OLD))
