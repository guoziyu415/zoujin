"""B-11：断线后续玩（假 Live）。

30 秒内重连接着用同一条会话；超过 30 秒新会话带最近对话；说到一半断的那个人物重建；4009 新标签页接手；
`forget`、关机丢掉寄存的；Trace。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Coroutine
from typing import Any

import pytest
from zoujin_backend.gateway import voice

from . import test_gateway_b4 as b4
from .conftest import OLD, Env
from .test_gateway import Player
from .test_gateway_b4 import InProc, Make, Play

inproc = b4.inproc  # pytest 的 fixture 按名字找
play = b4.play

pytestmark = pytest.mark.db

SPEED = 0.05


def wait_for(cond: object, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not cond():  # type: ignore[operator]
        assert time.monotonic() < deadline, "等不到"
        time.sleep(0.02)


def drop(p: Player) -> None:
    """断网：客户端这边关掉连接（服务端随后发现）。"""
    assert p.ws is not None
    p.ws.close()
    p.ws = None


def back(p: Player) -> Any:
    p.connect(last_seq=p.last_seq)
    return p.expect("welcome")


def spans(s: InProc, name: str) -> list[dict[str, object]]:
    return [dict(x) for x in s.gw.tracer.named(name)]


def on_gateway(session: Any, coro: Coroutine[Any, Any, Any]) -> None:
    """在网关的事件循环里跑（假会话记着它开在哪个循环上）。"""
    asyncio.run_coroutine_threadsafe(coro, session.loop).result(timeout=10)


def talk(p: Player, line: str) -> str:
    t = p.text(line)
    p.expect("turn_settled", turnId=t)
    return t


def test_reconnect_within_hold_reuses_the_same_session(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    p.focus(OLD)
    talk(p, "こんにちは。")
    session = s.live.live_sessions(OLD)[0]
    drop(p)
    wait_for(lambda: p.pid in s.gw.parked)
    assert not session.closed
    back(p)
    start = len(p.log)
    t0 = time.monotonic()
    p.focus(OLD)
    ready_s = time.monotonic() - t0
    assert ready_s < 1.0  # 加上前端 1〜2 秒的退避，5 秒以内（S-024）
    assert not [m for m in p.log[start:] if m["type"] == "session_preparing"]
    assert len(s.live.opened) == 1 and s.live.live_sessions(OLD) == [session]
    talk(p, "この市は、ずいぶん静かですね。")
    assert session.turns == 2  # 会话轮数接着算（第 8 轮照样重建）
    resume = spans(s, "gateway.resume")[-1]
    assert resume["resume_kind"] == "carried" and resume["carried"] == 1 and resume["recent_turns"] == 1
    assert resume["reconnect"] is True and int(str(resume["gap_ms"])) >= 0
    ready = spans(s, "gateway.resume_ready")[-1]
    assert ready["reused"] is True
    dumped = repr(s.gw.tracer.spans)
    assert "こんにちは" not in dumped


def test_after_the_hold_a_new_session_carries_recent_dialogue(
    env: Env, inproc: Make, play: Play, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(voice, "RESUME_HOLD_S", 2.0)  # × 0.05 = 0.1 秒
    s = inproc(SPEED)
    p = play(s)
    p.focus(OLD)
    talk(p, "こんにちは。")
    session = s.live.live_sessions(OLD)[0]
    drop(p)
    wait_for(lambda: session.closed)
    assert p.pid in s.gw.parked  # 最近对话还在
    back(p)
    p.send({"type": "focus", "character": OLD})
    p.expect("session_preparing", character=OLD, reason="switch")
    p.expect("session_ready", character=OLD)
    assert len(s.live.opened) == 2
    assert "# さっきまでの会話" in s.live.opened[1].system and "こんにちは。" in s.live.opened[1].system
    assert spans(s, "gateway.resume")[-1]["resume_kind"] == "recent"
    assert spans(s, "gateway.resume_ready")[-1]["reused"] is False


def test_recent_dialogue_is_dropped_after_its_hold(
    env: Env, inproc: Make, play: Play, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(voice, "RESUME_HOLD_S", 2.0)
    monkeypatch.setattr(voice, "RECENT_HOLD_S", 4.0)  # × 0.05 = 0.2 秒
    s = inproc(SPEED)
    p = play(s)
    p.focus(OLD)
    talk(p, "こんにちは。")
    drop(p)
    wait_for(lambda: p.pid in s.gw.parked)
    wait_for(lambda: p.pid not in s.gw.parked)
    back(p)
    p.focus(OLD)
    assert "# さっきまでの会話" not in s.live.opened[-1].system
    assert spans(s, "gateway.resume")[-1]["resume_kind"] == "cold"


def test_cut_mid_reply_rebuilds_that_character(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(1.0)  # 人物按真实节奏说话，断线时还在说
    p = play(s)
    p.focus(OLD)
    first = talk(p, "こんにちは。")
    session = s.live.live_sessions(OLD)[0]
    lost = p.text("この市は、ずいぶん静かですね。")
    p.expect("#audio")
    drop(p)
    wait_for(lambda: session.closed)  # 人物听到了叙事者没处理的一轮：不接着用
    welcome = back(p)
    assert welcome["lastTurn"]["turnId"] == lost and welcome["lastTurn"]["status"] == "lost"
    p.send({"type": "focus", "character": OLD})
    p.expect("session_ready", character=OLD, timeout=10)
    system = s.live.opened[-1].system
    assert "こんにちは。" in system and "静かですね" not in system  # 没交的那一轮不在最近对话里
    assert first


def test_other_tab_takes_over_the_session(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    p.focus(OLD)
    talk(p, "こんにちは。")
    session = s.live.live_sessions(OLD)[0]
    p.connect(last_seq=p.last_seq)  # 新标签页：旧连接被 4009 踢掉
    p.expect("welcome")
    start = len(p.log)
    p.focus(OLD)
    assert not [m for m in p.log[start:] if m["type"] == "session_preparing"]
    time.sleep(0.3)  # 旧连接收尾也不关它
    assert not session.closed and s.live.live_sessions(OLD) == [session]
    talk(p, "また来ます。")
    assert spans(s, "gateway.resume")[-1]["carried"] == 1


def test_forget_and_shutdown_drop_what_is_parked(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(SPEED)
    p = play(s)
    p.focus(OLD)
    talk(p, "こんにちは。")
    session = s.live.live_sessions(OLD)[0]
    drop(p)
    wait_for(lambda: p.pid in s.gw.parked)
    parked = s.gw.parked[p.pid]
    on_gateway(session, s.gw.forget(p.pid))
    assert session.closed and p.pid not in s.gw.parked and not parked.recent

    q = play(s)
    q.focus(OLD)
    talk(q, "こんにちは。")
    other = s.live.live_sessions(OLD)[-1]
    drop(q)
    wait_for(lambda: q.pid in s.gw.parked)
    on_gateway(other, s.gw.goaway())
    assert other.closed and not s.gw.parked
