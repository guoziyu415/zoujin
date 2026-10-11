"""B-9 在 WebSocket 和 REST 上（验收第 9、10 条）：触发那一次的推送顺序、结局开始以后不收输入、人物这一句说完再关
Live、重连补推、`GET …/ending` 的 404 / 202 / 200 / 403、`/v1/me`。两个进程用切片版的世界模型（`ZJ_WORLD`）。"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import delete, select, update
from zoujin_backend.config import REPO
from zoujin_backend.db.tables import endings, turns

from .conftest import OLD, Env
from .test_gateway import Player, Services, invite
from .test_gateway_b3 import advance_to

pytestmark = pytest.mark.db

Json = Any

SLICE = REPO / "worlds" / "hashire-merosu" / "1.0.0-slice" / "world.json"
CITY = "exit.1.city"


def services(migrated: str, speed: str) -> Iterator[Services]:
    s = Services(migrated, speed=speed, extra={"ZJ_WORLD": str(SLICE)})
    try:
        yield s
    finally:
        s.stop()


@pytest.fixture(scope="module")
def sliced(migrated: str) -> Iterator[Services]:
    yield from services(migrated, "0")


@pytest.fixture(scope="module")
def slow_slice(migrated: str) -> Iterator[Services]:
    """ZJ_SPEED=1：人物按真实节奏说话，进结局时他还在说。"""
    yield from services(migrated, "1")


def to_act4(env: Env, s: Services, p: Player) -> None:
    """开局、推到第一幕末、选「市に残り」：落在第四幕的刑场（5370）。"""
    p.start()
    advance_to(env, s, p.pid, 1430)
    p.connect(last_seq=p.last_seq)
    p.expect("welcome")
    p.send({"type": "act_choose", "clientMsgId": "go", "optionId": CITY})
    p.expect("act_transition", timeout=30)


def rows(env: Env, pid: str) -> list[Json]:
    async def main() -> list[Json]:
        engine = env.engine()
        try:
            async with engine.connect() as c:
                q = select(turns.c.turn_id, turns.c.kind, turns.c.status).where(turns.c.playthrough_id == pid)
                return [dict(r) for r in (await c.execute(q)).mappings()]
        finally:
            await engine.dispose()

    return asyncio.run(main())


def test_ending_over_the_socket(env: Env, sliced: Services) -> None:
    p = Player(sliced.base)
    p.login(invite(env))
    try:
        to_act4(env, sliced, p)
        ending = f"/v1/playthroughs/{p.pid}/ending"
        p.call("ending", 404, "GET", ending)  # 还没进结局

        # 等的动作：beat.s1，再 beat.24 进结局
        last = ""
        for i in range(4):
            last = f"w{i}"
            p.send({"type": "action", "clientMsgId": last, "kind": "wait"})
            p.expect("action_result", clientMsgId=last, timeout=30)
            if [m for m in p.log if m["type"] == "ending_started"]:
                break
        started = p.find("ending_started")
        assert started["trigger"] == "story-closed"
        at = p.log.index(started)
        result = p.index("action_result", clientMsgId=last)
        assert p.log[at + 1]["type"] == "commit"  # ending_started → commit → 收幕的 set_piece → action_result
        pieces = [i for i, m in enumerate(p.log) if m["type"] == "set_piece" and i > at]
        assert pieces and all(at + 1 < i < result for i in pieces)
        ready = p.expect("ending_ready", timeout=30)
        assert p.log.index(ready) > result

        # 进了结局：对话、动作、选去处都回 invalid_request，不写任务
        before = rows(env, p.pid)
        p.text("……")
        assert p.expect("error")["error"]["code"] == "invalid_request"
        p.send({"type": "action", "clientMsgId": "after", "kind": "wait"})
        assert p.expect("error")["error"]["code"] == "invalid_request"
        p.send({"type": "act_choose", "clientMsgId": "again", "optionId": CITY})
        assert p.expect("error")["error"]["code"] == "invalid_request"
        assert rows(env, p.pid) == before

        # REST：200，过 Schema（Player.call 查），没有内部字段
        view = p.call("ending", 200, "GET", ending)
        assert view["endingId"] == ready["endingId"]
        assert view["card"]["fallbackImageUrl"] == "/endings/canon-reunion.webp"
        for key in ("signature", "finalVars", "changedBeats", "causedBy"):
            assert key not in str(view)
        assert p.call("me", 200, "GET", "/v1/me")["activePlaythrough"] is None  # ended 的局不算进行中

        # 重连：welcome → ending_started（存的那份 staging）→ ending_ready
        assert p.ws is not None
        p.ws.close()
        mark = len(p.log)
        p.connect(last_seq=p.last_seq)
        p.expect("welcome")
        again = p.expect("ending_started")
        assert again["staging"] == started["staging"] and again["trigger"] == "story-closed"
        assert p.expect("ending_ready") == ready
        types = [m["type"] for m in p.log[mark:]]
        assert types[:3] == ["welcome", "ending_started", "ending_ready"] and types.count("ending_started") == 1

        # 别人的局 403
        q = Player(sliced.base)
        q.login(invite(env))
        try:
            q.call("ending", 403, "GET", ending)
        finally:
            q.close()

        # 结局任务还没好：202，etaSeconds 在 5〜30
        async def unready() -> None:
            engine = env.engine()
            try:
                async with engine.begin() as c:
                    await c.execute(delete(endings).where(endings.c.playthrough_id == p.pid))
                    await c.execute(
                        update(turns)
                        .where(turns.c.playthrough_id == p.pid, turns.c.kind == "ending")
                        .values(status="pending")
                    )
            finally:
                await engine.dispose()

        asyncio.run(unready())
        pending = p.call("ending", 202, "GET", ending)
        assert pending["status"] == "pending" and 5 <= pending["etaSeconds"] <= 30
    finally:
        p.close()


def test_the_line_being_spoken_is_not_cut(env: Env, slow_slice: Services) -> None:
    """进结局时人物正在说：接着转发到这一句说完（最多约 3 秒），再关会话；这一轮不交，记成 lost；之后的音频丢掉。"""
    p = Player(slow_slice.base)
    p.login(invite(env))
    try:
        to_act4(env, slow_slice, p)
        advance_to(env, slow_slice, p.pid, 5450)
        p.focus(OLD)
        turn = p.text("もうすぐ日が沈みますね。")
        p.expect("transcript", turnId=turn, speaker=OLD, final=False, timeout=30)
        advance_to(env, slow_slice, p.pid, 5470)  # beat.24 在 5460
        started = p.expect("ending_started", timeout=30)
        at = p.log.index(started)
        deadline = time.monotonic() + 8
        while not [m for m in p.log[at:] if m["type"] in ("turn_complete", "interrupted") and m.get("turnId") == turn]:
            assert time.monotonic() < deadline, [m["type"] for m in p.log[at:]]
            p._read(0.5)
        assert [m for m in p.log[at:] if m.get("turnId") == turn]  # ending_started 之后还在转发这一轮
        deadline = time.monotonic() + 8
        while (status := {r["turn_id"]: r["status"] for r in rows(env, p.pid)}.get(turn)) is None:
            assert time.monotonic() < deadline
            time.sleep(0.2)
        assert status == "lost"
        assert not [m for m in p.log if m["type"] == "turn_settled" and m.get("turnId") == turn]
        assert p.ws is not None
        p.ws.send(bytes([0x01]) + (99).to_bytes(4, "big") + bytes(1280))  # 上行音频丢掉，不回任何消息
        p.text("……")
        assert p.expect("error")["error"]["code"] == "invalid_request"
    finally:
        p.close()
