"""B-3 在 WebSocket 上（验收第 8 组）：动作的 commit 在 action_result 之前，收幕以后对话和动作回 invalid_request，
说打算、选去处、重连补 pending、落地让 opener 先开口。两个进程用切片版的世界模型（`ZJ_WORLD`）。

时间不够到第一幕末的地方，测试自己往任务表里写一条 advance、叫一次叙事者（评测入口也是这么推进的）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import httpx
import pytest
from sqlalchemy import select
from zoujin_backend.config import REPO
from zoujin_backend.db import store
from zoujin_backend.db.tables import turns
from zoujin_backend.gateway.ws import SERVER_SEQ
from zoujin_backend.ids import IdGen
from zoujin_backend.narrator.plans import NOT_HEARD

from .conftest import OLD, Env
from .test_gateway import Player, Services, invite

pytestmark = pytest.mark.db

SLICE = "worlds/hashire-merosu/1.0.0-slice/world.json"
GROUND = "place.execution-ground"
HOME = "exit.1.old-man"
HELP = {"actionId": "act_walk-old-man-home", "kind": "help", "target": OLD}
IDS = IdGen()


@pytest.fixture(scope="module")
def sliced(migrated: str) -> Iterator[Services]:
    s = Services(migrated, extra={"ZJ_WORLD": str(REPO / SLICE)})
    try:
        yield s
    finally:
        s.stop()


@pytest.fixture
def player(env: Env, sliced: Services) -> Iterator[Player]:
    p = Player(sliced.base)
    p.login(invite(env))
    try:
        yield p
    finally:
        p.close()


def advance_to(env: Env, s: Services, pid: str, t: int) -> None:
    """把这一局的钟推到 t：写一条 advance 任务、叫叙事者做完（网关收到 NOTIFY 照常推 commit）。"""

    async def main() -> None:
        engine = env.engine()
        try:
            async with engine.begin() as c:
                st = await store.sim_state(c, pid)
                assert st is not None and st["t"] <= t
                await store.enqueue(c, IDS, pid, kind="advance", minutes=t - st["t"])
        finally:
            await engine.dispose()

    asyncio.run(main())
    r = httpx.post(f"{s.narrator_url}/internal/v1/playthroughs/{pid}/run", timeout=30)
    assert r.status_code == 200, r.text


def plan_turns(env: Env, pid: str) -> list[str]:
    async def main() -> list[str]:
        engine = env.engine()
        try:
            async with engine.connect() as c:
                q = select(turns.c.turn_id).where(turns.c.playthrough_id == pid, turns.c.kind == "plan")
                return list((await c.execute(q)).scalars())
        finally:
            await engine.dispose()

    return asyncio.run(main())


def test_actions_act_end_choose_and_arrival(env: Env, sliced: Services, player: Player) -> None:
    p = player
    made = p.start()
    assert [a["actionId"] for a in made["snapshot"]["actions"]] == [HELP["actionId"]]
    p.connect(last_seq=p.last_seq)
    assert p.expect("welcome")["pending"]["actEnd"] is None

    # 情境动作：commit（位置点变了）在 action_result 之前（3.8）
    start = len(p.log)
    p.send({"type": "action", "clientMsgId": "c1", **HELP})
    done = p.expect("action_result", clientMsgId="c1")
    assert (done["status"], done["minutes"]) == ("done", 30)
    commit = p.find("commit", seq=p.last_seq)
    assert p.log.index(commit) < p.log.index(done) and p.log.index(commit) >= start
    assert commit["patch"]["player"] == {"spot": "old-man-house-side"}

    # 换地方：patch.player 只带 place，不带 spot
    p.send({"type": "action", "clientMsgId": "c2", "kind": "move", "target": GROUND})
    moved = p.expect("action_result", clientMsgId="c2")
    assert moved["status"] == "done"
    assert p.find("commit", seq=p.last_seq)["patch"]["player"] == {"place": GROUND}

    # 推到 beat.07 前一点，再说一轮：这一轮的 10 分钟里收幕
    seq = p.last_seq
    advance_to(env, sliced, p.pid, 1420)
    p.expect("commit", fromSeq=seq + 1)
    p.focus(OLD)
    turn = p.text("……")
    settled = p.expect("turn_settled", turnId=turn)
    ended = p.expect("act_ended")
    assert p.log.index(settled) < p.log.index(ended)
    assert [o["optionId"] for o in ended["options"]] == ["exit.1.city", HOME]
    assert ended["freeform"] == {"allowed": True, "triesLeft": 2}

    # 收了幕：对话、动作都回 invalid_request，不写任务
    p.text("……")
    assert p.expect("error")["error"]["code"] == "invalid_request"
    p.send({"type": "action", "clientMsgId": "c3", "kind": "move", "target": "place.syracuse-square"})
    assert p.expect("error")["error"]["code"] == "invalid_request"

    # 文字说打算，没成行：一次机会用掉
    p.send({"type": "act_propose", "clientMsgId": "c4", "text": "メロスを追いかけて、村まで一緒に行きます。"})
    refused = p.expect("act_plan_result", clientMsgId="c4")
    assert refused["accepted"] is False and refused["triesLeft"] == 1 and "turnId" not in refused

    # 选去处：commit 在 act_transition 之前；落地带 opener
    p.send({"type": "act_choose", "clientMsgId": "c5", "optionId": HOME})
    moved_on = p.expect("act_transition")
    assert (moved_on["fromActId"], moved_on["toActId"]) == ("act.1", "act.4")
    assert moved_on["arrival"]["opener"] == OLD and moved_on["arrival"]["line"]
    assert moved_on["snapshot"]["lastSeq"] == p.last_seq
    assert p.log.index(p.find("commit", seq=p.last_seq)) < p.log.index(moved_on)

    # 断线重连：welcome.pending 补上待落地的 arrival，幕末已经清掉
    assert p.ws is not None
    p.ws.close()
    p.connect(last_seq=p.last_seq)
    welcome = p.expect("welcome")
    assert welcome["pending"]["actEnd"] is None
    assert welcome["pending"]["arrival"] == {"line": moved_on["arrival"]["line"], "opener": OLD}

    # 落地：服务端起一轮（turnSeq 从 0x80000001 起），opener 先开口；不推 turn_settled
    p.send({"type": "act_landed", "actId": "act.4"})
    started = p.expect("turn_started", reason="arrival")
    assert (started["speaker"], started["turnSeq"]) == (OLD, SERVER_SEQ)
    p.expect("turn_complete", turnId=started["turnId"])
    said = p.expect("transcript", turnId=started["turnId"], final=True)
    assert said["speaker"] == OLD and said["text"] == "……間に合うたか。わしも、ここで待つとしよう。"
    p.send({"type": "act_landed", "actId": "act.4"})  # 第二次忽略
    with pytest.raises(AssertionError):
        p.expect("turn_started", timeout=1.5, reason="arrival")
    assert not [m for m in p.log if m["type"] == "turn_settled" and m.get("turnId") == started["turnId"]]
    p.connect(last_seq=p.last_seq)
    assert "arrival" not in p.expect("welcome")["pending"]


def test_a_spoken_plan(env: Env, sliced: Services, player: Player) -> None:
    """用声音说打算：activity_start 带 purpose；转写的定稿推回来；结果带这一轮的 turnId。"""
    p = player
    p.start()
    advance_to(env, sliced, p.pid, 1430)
    p.connect(last_seq=p.last_seq)
    ended = p.expect("welcome")["pending"]["actEnd"]
    assert [o["optionId"] for o in ended["options"]] == ["exit.1.city"]  # 没送过老爺：一个去处

    # 误按：没有一帧声音就松开。不写任务、不算试次，不推定稿
    silent = p.turn_id()
    p.send({"type": "activity_start", "turnId": silent, "turnSeq": 1, "purpose": "act_plan"})
    p.send({"type": "activity_end", "turnId": silent, "turnSeq": 1})
    nothing = p.expect("act_plan_result", turnId=silent)
    assert nothing == {
        "type": "act_plan_result",
        "turnId": silent,
        "accepted": False,
        "narration": [NOT_HEARD],
        "triesLeft": 2,
    }
    assert not [m for m in p.log if m["type"] == "transcript" and m.get("turnId") == silent]
    assert plan_turns(env, p.pid) == []

    turn_id, seq = p.turn_id(), 2
    p.send({"type": "activity_start", "turnId": turn_id, "turnSeq": seq, "purpose": "act_plan"})
    assert p.ws is not None
    for _ in range(3):
        p.ws.send(bytes([0x01]) + seq.to_bytes(4, "big") + bytes(1280))
    p.send({"type": "activity_end", "turnId": turn_id, "turnSeq": seq})
    heard = p.expect("transcript", turnId=turn_id, final=True)
    assert heard["speaker"] == "player" and "約束" in heard["text"]
    assert p.log.index(p.find("transcript", turnId=turn_id, final=False)) < p.log.index(heard)
    result = p.expect("act_plan_result", turnId=turn_id)
    assert result["accepted"] is True and "clientMsgId" not in result
    assert result["narration"] == ["あなたは、メロスの約束を、町の人々に知らせて回ることにした。"]
    moved_on = p.expect("act_transition")
    assert p.log.index(p.find("commit", seq=p.last_seq)) < p.log.index(result) < p.log.index(moved_on)
    assert moved_on["toActId"] == "act.4" and "opener" not in moved_on["arrival"]
    assert plan_turns(env, p.pid) == [turn_id]
