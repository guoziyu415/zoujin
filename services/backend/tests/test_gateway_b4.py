"""B-4 在 WebSocket 上（验收第 1〜4 组）：作废和重建、提交窗口、识别改正、幕末用声音说的打算、意图确认的推送顺序、
超时和重连。

网关和叙事者都在测试进程里（`InProc`）：网关是后台线程里的 uvicorn，叙事者在另一个线程自己的事件循环里，网关照常
「叫」它（`InThread`）。这样测试拿得到假 Live（重建时带进新会话的「最近的对话」）。世界模型用切片版；
`ZJ_SPEED` 按每个测试要的窗口给（作废的窗口 3 秒、确认的 30 秒都按它缩短）。
"""

from __future__ import annotations

import asyncio
import socket
import threading
import time
from collections.abc import Callable, Coroutine, Iterator
from dataclasses import replace
from typing import Any, cast

import pytest
import uvicorn
from sqlalchemy import select
from zoujin_backend.config import Settings, async_url
from zoujin_backend.db import store
from zoujin_backend.db.tables import playthrough_metrics, playthroughs, turns, utterances
from zoujin_backend.gateway import app as gateway_app
from zoujin_backend.gateway.ws import SERVER_SEQ
from zoujin_backend.models.live import FakeLive, Recent
from zoujin_backend.narrator import app as narrator_app
from zoujin_backend.narrator.core import Narrator

from .conftest import OLD, Env
from .test_b3 import SLICE
from .test_b4 import MELOS, OFFER, QUESTION, STAY
from .test_gateway import Player, invite

pytestmark = pytest.mark.db

type Make = Callable[[float], "InProc"]
type Play = Callable[..., Player]

Json = Any

OPTIONS = [{"optionId": "yes", "label": "本気だ"}, {"optionId": "no", "label": "いや、違う"}]
REFUSED = "メロスを追いかけて、村まで一緒に行きます。"  # 假模型判不成行


class InThread:
    """网关调叙事者：交给叙事者那个线程的事件循环做，等它做完（形状同 `HttpNarrator`）。"""

    def __init__(self, narrator: Narrator, loop: asyncio.AbstractEventLoop) -> None:
        self.narrator = narrator
        self.loop = loop

    async def run(self, pid: str) -> int:
        done = await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(self.narrator.run(pid), self.loop))
        return len(done)


class InProc:
    def __init__(self, url: str, speed: float) -> None:
        self.settings = replace(Settings(database_url=async_url(url)), dev=True, speed=speed, world=SLICE)
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.loop_thread.start()
        self.narrator = narrator_app.build(self.settings)
        self.gw = gateway_app.build(self.settings, InThread(self.narrator, self.loop))
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.base = f"http://127.0.0.1:{self.sock.getsockname()[1]}"
        config = uvicorn.Config(
            gateway_app.create_app(self.settings, self.gw),
            ws="websockets-sansio",
            log_level="warning",
            log_config=None,
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, kwargs={"sockets": [self.sock]}, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 15
        while not self.server.started:
            assert time.monotonic() < deadline, "网关没起来"
            time.sleep(0.01)

    @property
    def live(self) -> FakeLive:
        return cast(FakeLive, self.gw.live)

    def call[T](self, coro: Coroutine[Any, Any, T]) -> T:
        """在叙事者的事件循环里跑（直接叫叙事者，和网关叫的是同一个）。"""
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout=60)

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=15)
        self.sock.close()
        self.call(self.narrator.engine.dispose())
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.loop_thread.join(timeout=5)


@pytest.fixture
def inproc(migrated: str) -> Iterator[Callable[[float], InProc]]:
    made: list[InProc] = []

    def make(speed: float) -> InProc:
        s = InProc(migrated, speed)
        made.append(s)
        return s

    try:
        yield make
    finally:
        for s in made:
            s.stop()


@pytest.fixture
def play(env: Env) -> Iterator[Callable[..., Player]]:
    """登录、开局；connect=True 时连上、收到 welcome。"""
    made: list[Player] = []

    def make(s: InProc, *, connect: bool = True) -> Player:
        p = Player(s.base)
        made.append(p)
        p.login(invite(env))
        p.start()
        if connect:
            p.connect(last_seq=p.last_seq)
            p.expect("welcome")
        return p

    try:
        yield make
    finally:
        for p in made:
            p.close()


def db[T](env: Env, fn: Callable[[Any], Coroutine[Any, Any, T]]) -> T:
    async def main() -> T:
        engine = env.engine()
        try:
            async with engine.begin() as c:
                return await fn(c)
        finally:
            await engine.dispose()

    return asyncio.run(main())


def turn_row(env: Env, turn_id: str) -> Json:
    async def get(c: Any) -> Json:
        return dict((await c.execute(select(turns).where(turns.c.turn_id == turn_id))).mappings().one())

    return db(env, get)


def said(env: Env, turn_id: str) -> list[tuple[str, str | None, bool]]:
    """这一轮的原话：（谁、文字、清空了没有）。"""

    async def get(c: Any) -> list[tuple[str, str | None, bool]]:
        q = (
            select(utterances.c.speaker, utterances.c.text, utterances.c.deleted_at)
            .where(utterances.c.turn_id == turn_id)
            .order_by(utterances.c.recorded_at)
        )
        return [(r.speaker, r.text, r.deleted_at is not None) for r in (await c.execute(q)).all()]

    return db(env, get)


def metrics(env: Env, pid: str) -> Json:
    async def get(c: Any) -> Json:
        q = select(playthrough_metrics).where(playthrough_metrics.c.playthrough_id == pid)
        return dict((await c.execute(q)).mappings().one())

    return db(env, get)


def plan_tries(env: Env, pid: str) -> int:
    async def get(c: Any) -> int:
        q = select(playthroughs.c.plan_tries).where(playthroughs.c.playthrough_id == pid)
        return int(await c.scalar(q) or 0)

    return db(env, get)


def advance_to(env: Env, s: InProc, pid: str, t: int) -> None:
    async def queue(c: Any) -> None:
        st = await store.sim_state(c, pid)
        assert st is not None and st["t"] <= t
        await store.enqueue(c, env.ids, pid, kind="advance", minutes=t - st["t"])

    db(env, queue)
    s.call(s.narrator.run(pid))


def settle(p: Player) -> None:
    """等网关把手上的推完：ping 的 pong 回来之前到的都收进 log。"""
    p.send({"type": "ping"})
    p.expect("pong")


def of(p: Player, turn_id: str, *types: str) -> list[Json]:
    return [m for m in p.log if m.get("turnId") == turn_id and (not types or m["type"] in types)]


def correction(p: Player, replaces: str, text: str) -> str:
    turn_id, seq = p.turn_id(), p.seq + 1
    p.seq = seq
    p.send({"type": "text", "turnId": turn_id, "turnSeq": seq, "text": text, "via": "correction", "replaces": replaces})
    return turn_id


def voice_plan(p: Player, *, release: bool = True) -> str:
    turn_id, seq = p.turn_id(), p.seq + 1
    p.seq = seq
    p.send({"type": "activity_start", "turnId": turn_id, "turnSeq": seq, "purpose": "act_plan"})
    assert p.ws is not None
    for _ in range(3):
        p.ws.send(bytes([0x01]) + seq.to_bytes(4, "big") + bytes(1280))
    if release:
        p.send({"type": "activity_end", "turnId": turn_id, "turnSeq": seq})
    return turn_id


def retract(p: Player, turn_id: str) -> str:
    p.send({"type": "turn_retract", "turnId": turn_id})
    return str(p.expect("turn_retract_result", turnId=turn_id)["status"])


# —— 第 1 组：作废 ——


def test_retract_before_the_character_speaks(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(0.3)
    p = play(s)
    p.focus(OLD)
    first = p.text("こんにちは。")
    p.expect("turn_settled", turnId=first)
    reply = p.find("transcript", turnId=first, speaker=OLD, final=True)["text"]
    seq = p.last_seq

    second = p.text("さっきのは、")
    second_seq = p.seq
    assert retract(p, second) == "retracted"  # 人物开口（假 Live 约 0.3 秒后）之前
    assert p.expect("turn_settled", turnId=second) == {
        "type": "turn_settled",
        "turnId": second,
        "outcome": "retracted",
        "eventIds": [],
        "minutes": 0,
    }
    preparing = p.expect("session_preparing", character=OLD, reason="rebuild")
    assert preparing["etaMs"] > 0
    p.expect("session_ready", character=OLD)
    time.sleep(1.5)  # 原来那句要说的时间过去了
    settle(p)
    cut = p.index("turn_retract_result", turnId=second)
    assert not [m for m in p.log[cut:] if m["type"] == "#audio" and m["turnSeq"] == second_seq]
    assert not of(p, second, "transcript", "turn_complete", "interrupted", "commit")
    assert p.last_seq == seq  # 没有 commit，时钟不动
    row = turn_row(env, second)
    assert (row["status"], row["outcome"], row["minutes"]) == ("retracted", "retracted", 0)
    assert said(env, second) == []  # 没交给叙事者：不写原话
    # 新会话只带作废之前的那一轮
    assert s.live.opened[-1] == (OLD, [Recent("こんにちは。", reply)])
    assert metrics(env, p.pid)["turns_retracted"] == 1


def test_retract_inside_the_commit_window(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(0.5)  # 窗口 1.5 秒
    p = play(s)
    p.focus(OLD)
    first = p.text("こんにちは。")
    p.expect("turn_complete", turnId=first)
    done = time.monotonic()
    p.expect("commit", turnId=first)
    assert time.monotonic() - done >= 1.2  # turn_complete 之后 3 秒（× ZJ_SPEED）之内没有 commit
    p.expect("turn_settled", turnId=first)
    reply = p.find("transcript", turnId=first, speaker=OLD, final=True)["text"]
    seq = p.last_seq

    second = p.text("この市は、ずいぶん静かですね。")
    p.expect("transcript", turnId=second, speaker=OLD, final=True)  # 人物说完了，叙事者在判、等窗口
    assert retract(p, second) == "retracted"
    assert p.expect("turn_settled", turnId=second)["outcome"] == "retracted"
    p.expect("session_preparing", character=OLD, reason="rebuild")
    p.expect("session_ready", character=OLD)
    time.sleep(2.5)  # 窗口过了：叙事者判完也不提交
    settle(p)
    assert not of(p, second, "commit") and len(of(p, second, "turn_settled")) == 1
    assert p.last_seq == seq
    row = turn_row(env, second)
    assert (row["status"], row["minutes"]) == ("retracted", 0)
    assert [(who, text, gone) for who, text, gone in said(env, second)] == [("player", None, True), (OLD, None, True)]
    assert s.live.opened[-1] == (OLD, [Recent("こんにちは。", reply)])

    # 已经提交的：too_late，世界不变
    assert retract(p, first) == "too_late"
    settle(p)
    assert p.last_seq == seq and turn_row(env, first)["status"] == "done"
    assert metrics(env, p.pid)["turns_retracted"] == 1

    # 重连：lastTurn 是作废的那一轮，settled，文字都是 null
    assert p.ws is not None
    p.ws.close()
    p.connect(last_seq=p.last_seq)
    assert p.expect("welcome")["lastTurn"] == {
        "turnId": second,
        "character": OLD,
        "status": "settled",
        "playerText": None,
        "characterText": None,
    }


# —— 第 2 组：识别改正 ——


def test_a_correction_waits_for_the_rebuilt_session(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(0.5)
    p = play(s)
    p.focus(OLD)
    wrong = p.text("往生は、どっちですか。")
    p.expect("transcript", turnId=wrong, speaker=OLD, final=True)
    p.send({"type": "turn_retract", "turnId": wrong})
    fixed = correction(p, wrong, "王城は、どっちですか。")
    fixed_seq = p.seq
    assert p.expect("turn_retract_result", turnId=wrong)["status"] == "retracted"
    p.expect("turn_settled", turnId=fixed, timeout=30)
    ready = _rebuilt(p, OLD)
    first_out = min(
        i
        for i, m in enumerate(p.log)
        if (m["type"] == "#audio" and m["turnSeq"] == fixed_seq) or (m.get("turnId") == fixed)
    )
    assert ready < first_out  # 新的一轮在会话重建好之后才送进去
    assert of(p, fixed, "commit") and turn_row(env, wrong)["status"] == "retracted"
    assert said(env, fixed)[0] == ("player", "王城は、どっちですか。", False)

    # 旧的一轮已经提交：too_late，新的一轮照常判，旧的事件还在
    done = p.text("こんにちは。")
    p.expect("turn_settled", turnId=done)
    old_events = [e["eventId"] for e in p.find("commit", turnId=done)["events"]]
    rebuilds = len([m for m in p.log if m["type"] == "session_preparing" and m["reason"] == "rebuild"])
    p.send({"type": "turn_retract", "turnId": done})
    again = correction(p, done, "こんばんは。")
    assert p.expect("turn_retract_result", turnId=done)["status"] == "too_late"
    p.expect("turn_settled", turnId=again, timeout=30)
    assert len([m for m in p.log if m["type"] == "session_preparing" and m["reason"] == "rebuild"]) == rebuilds
    assert turn_row(env, done)["status"] == "done" and len(of(p, done, "commit")) == 1
    assert [e["eventId"] for e in p.find("commit", turnId=done)["events"]] == old_events


def _rebuilt(p: Player, character: str) -> int:
    """最后一次重建的 session_ready 的位置。"""
    preparing = max(
        i
        for i, m in enumerate(p.log)
        if m["type"] == "session_preparing" and m["reason"] == "rebuild" and m["character"] == character
    )
    return next(
        i for i, m in enumerate(p.log) if i > preparing and m["type"] == "session_ready" and m["character"] == character
    )


# —— 第 3 组：幕末用声音说的打算 ——


def test_a_spoken_plan_can_be_retracted(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(0.5)  # 窗口 1.5 秒（从定稿推出起算）
    p = play(s, connect=False)
    advance_to(env, s, p.pid, 1430)
    p.connect(last_seq=p.last_seq)
    assert p.expect("welcome")["pending"]["actEnd"] is not None

    # 还在说时作废：没有转写的定稿，不写任务
    speaking = voice_plan(p, release=False)
    assert retract(p, speaking) == "retracted"
    p.send({"type": "activity_end", "turnId": speaking, "turnSeq": p.seq})
    settle(p)
    assert not of(p, speaking, "act_plan_result", "turn_settled")
    assert not [m for m in of(p, speaking, "transcript") if m["final"]]

    # 松开以后马上作废：没有 act_plan_result，不算试次，原话清空
    released = voice_plan(p)
    p.expect("transcript", turnId=released, speaker="player", final=True)
    assert retract(p, released) == "retracted"
    time.sleep(2.5)
    settle(p)
    assert not of(p, released, "act_plan_result", "turn_settled")
    row = turn_row(env, released)
    assert (row["kind"], row["status"]) == ("plan", "retracted")
    assert said(env, released) == [("player", None, True)]
    assert plan_tries(env, p.pid) == 0
    assert metrics(env, p.pid)["turns_retracted"] == 2

    # 作废的两次不算：文字说一个不成行的，还剩 1 次
    p.send({"type": "act_propose", "clientMsgId": "c1", "text": REFUSED})
    refused = p.expect("act_plan_result", clientMsgId="c1")
    assert (refused["accepted"], refused["triesLeft"]) == (False, 1)

    # 判完以后作废：too_late，成行的照样转场
    going = voice_plan(p)
    assert p.expect("act_plan_result", turnId=going, timeout=30)["accepted"] is True
    p.expect("act_transition")
    assert retract(p, going) == "too_late"
    assert turn_row(env, going)["status"] == "done"


# —— 第 4 组：意图确认 ——


def test_confirm_order_buttons_and_a_spoken_answer(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(0.1)  # 确认的计时 3 秒
    p = play(s)
    p.focus(MELOS)

    # asked: false：turn_settled → 服务端起一轮反问 → confirm；反问那一轮没有 turn_settled
    offer = p.text(OFFER)
    settled = p.expect("turn_settled", turnId=offer)
    assert settled["minutes"] == 10
    started = p.expect("turn_started", reason="confirm", speaker=MELOS)
    asked = started["turnId"]
    assert started["turnSeq"] >= SERVER_SEQ
    p.expect("turn_complete", turnId=asked)
    question = p.expect("transcript", turnId=asked, speaker=MELOS, final=True)
    assert question["text"] == QUESTION
    c = p.expect("confirm")
    draft = c["draftId"]
    assert c == {
        "type": "confirm",
        "draftId": draft,
        "character": MELOS,
        "prompt": QUESTION,
        "options": OPTIONS,
        "timeoutSec": 30,
    }
    assert p.log.index(settled) < p.log.index(started) < p.log.index(question) < p.log.index(c)
    assert not of(p, asked, "turn_settled", "commit")
    assert (MELOS, QUESTION, False) in said(env, offer)  # 反问的原话挂在原来那一轮下面

    # 按钮答「是」：草稿的 commit（dt 0，原来那一轮）→ confirm_closed
    p.send({"type": "confirm_answer", "draftId": draft, "optionId": "yes"})
    closed = p.expect("confirm_closed", draftId=draft)
    assert closed == {"type": "confirm_closed", "draftId": draft, "optionId": "yes", "by": "button"}
    first_commit, draft_commit = of(p, offer, "commit")
    assert p.log.index(draft_commit) < p.log.index(closed)
    assert [(e["dt"], e["turnId"], e["summary"]) for e in draft_commit["events"]] == [
        (0, offer, "あなたは、メロスに代わって人質になると申し出た")
    ]
    assert first_commit["patch"]["clock"]["t"] == draft_commit["events"][0]["t"]

    # asked: true：turn_settled 之后直接 confirm；按钮答「不是」：只推 confirm_closed，不花时间
    stay = p.text(STAY)
    settled = p.expect("turn_settled", turnId=stay)
    c = p.expect("confirm")
    assert c["prompt"] == "……本気で言っているのか。"
    between = p.log[p.log.index(settled) : p.log.index(c)]
    assert not [m for m in between if m["type"] == "turn_started"]
    seq = p.last_seq
    p.send({"type": "confirm_answer", "draftId": c["draftId"], "optionId": "no"})
    assert p.expect("confirm_closed", draftId=c["draftId"])["optionId"] == "no"
    p.send({"type": "confirm_answer", "draftId": c["draftId"], "optionId": "yes"})  # 关掉了的再答：忽略
    settle(p)
    assert len([m for m in p.log if m["type"] == "confirm_closed" and m["draftId"] == c["draftId"]]) == 1
    assert p.last_seq == seq

    # 用声音答（评测里是文字的一轮）：那一轮 commit → turn_settled → 草稿的 commit → confirm_closed（voice）
    again = p.text(OFFER)
    c = p.expect("confirm")
    answer = p.text("本気だ。逃げも隠れもしない。")
    closed = p.expect("confirm_closed", draftId=c["draftId"], timeout=30)
    assert (closed["optionId"], closed["by"]) == ("yes", "voice")
    order = [
        p.index("commit", turnId=answer),
        p.index("turn_settled", turnId=answer),
        p.log.index(of(p, again, "commit")[-1]),
        p.log.index(closed),
    ]
    assert order == sorted(order) and of(p, answer, "turn_settled")[0]["minutes"] == 10

    # 一局问满 3 次：第 4 次不问
    fourth = p.text(OFFER)
    p.expect("turn_settled", turnId=fourth)
    time.sleep(0.5)
    settle(p)
    assert not [m for m in p.log[p.index("turn_settled", turnId=fourth) :] if m["type"] in ("confirm", "turn_started")]
    m = metrics(env, p.pid)
    assert (m["confirms_asked"], m["confirms_yes"], m["confirms_no"], m["confirms_timeout"]) == (3, 2, 1, 0)
    assert m["candidates_confirm_dropped"] == 1


def test_confirm_times_out_and_comes_back_after_a_reconnect(env: Env, inproc: Make, play: Play) -> None:
    s = inproc(0.1)  # 确认的计时 3 秒
    p = play(s)
    p.focus(MELOS)
    offer = p.text(OFFER)
    c = p.expect("confirm")
    seq = p.last_seq
    closed = p.expect("confirm_closed", draftId=c["draftId"], timeout=10)
    assert (closed["optionId"], closed["by"]) == (None, "timeout")
    assert p.last_seq == seq and len(of(p, offer, "commit")) == 1  # 没有草稿的事件

    # 玩家已经不看着他：不起反问的一轮，直接推 confirm
    second = p.text(OFFER)
    p.send({"type": "unfocus", "reason": "walk_away"})
    settled = p.expect("turn_settled", turnId=second)
    c = p.expect("confirm")
    assert not [m for m in p.log[p.log.index(settled) :] if m["type"] == "turn_started"]

    # 断线重连：没过期的给 remainingSec
    assert p.ws is not None
    p.ws.close()
    p.connect(last_seq=p.last_seq)
    pending = p.expect("welcome")["pending"]["confirm"]
    assert {k: pending[k] for k in ("draftId", "character", "prompt", "options", "timeoutSec")} == {
        "draftId": c["draftId"],
        "character": MELOS,
        "prompt": QUESTION,
        "options": OPTIONS,
        "timeoutSec": 30,
    }
    assert 1 <= pending["remainingSec"] <= 3

    # 过期了才重连：pending.confirm 是 null，草稿按超时关掉
    assert p.ws is not None
    p.ws.close()
    time.sleep(3.5)
    p.connect(last_seq=p.last_seq)
    assert p.expect("welcome")["pending"]["confirm"] is None
    late = p.expect("confirm_closed", draftId=c["draftId"], timeout=10)
    assert (late["optionId"], late["by"]) == (None, "timeout")
    assert metrics(env, p.pid)["confirms_timeout"] == 2
