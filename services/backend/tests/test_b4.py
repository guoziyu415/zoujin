"""B-4（意图确认、作废）在叙事者和评测入口这一层的验收：第 1 组（作废和提交谁先拿到行锁、提交窗口）、
第 4 组（意图确认）、第 5 组（评测入口）、第 6 组（不记原话）、第 7 组（迁移）。
WebSocket 上的顺序、重建、改正和幕末的打算在 `test_gateway_b4.py`。

意图确认走评测入口（和网关同一条路：写任务、叫叙事者），世界模型用切片版；假模型的提取用
`fixtures/fake-text/b4-confirm.json`（「身代わりになる」→ 人物没在反问，「代わりに残る」→ 已经在反问）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from alembic import command
from sqlalchemy import delete, func, insert, inspect, select, update
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from zoujin_backend import eval_api
from zoujin_backend.config import REPO, async_url
from zoujin_backend.db import store
from zoujin_backend.db.events import recorded_at, to_row
from zoujin_backend.db.tables import (
    PER_PLAYTHROUGH,
    drafts,
    events,
    playthroughs,
    turns,
    utterances,
    world_state,
)
from zoujin_backend.models.text import FakeText
from zoujin_backend.narrator import confirm
from zoujin_backend.narrator.core import Task
from zoujin_backend.narrator.writer import Writer
from zoujin_backend.trace import Tracer

from .conftest import OLD, Env, alembic_config, truncate
from .test_b3 import SLICE, WALKED, Game, types

pytestmark = pytest.mark.db

Json = Any

MELOS = "char.melos"
OFFER = "私がメロスの身代わりになるよ"  # 人物这一轮没在反问（asked: false）
STAY = "私がメロスの代わりに残るよ"  # 人物这一轮已经在反问（asked: true）
QUESTION = "……君が、私の代わりに人質になるというのか。"
SUMMARY = "旅人は、メロスに代わって人質になると申し出た"
GROUND = "place.execution-ground"
FAKE_TEXT = REPO / "fixtures" / "fake-text"


@pytest.fixture
def game(env: Env, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., Game]]:
    monkeypatch.setenv("DATABASE_URL", env.url)
    monkeypatch.setenv("ZJ_WORLD", str(SLICE))
    monkeypatch.delenv("ZJ_MODEL", raising=False)

    def make(checkpoint: str = "sc.canon@beat.03", *, walked: bool = False) -> Game:
        doc: Json = {"role": "role.traveler", "checkpoint": checkpoint}
        if walked:
            doc["events"] = [WALKED]
        return Game(eval_api.setup(doc, mode="text"))

    yield make


def queue(g: Game, kind: str, **kw: Any) -> str:
    """不经评测入口写一行任务、叫叙事者做完（评测入口的下一步会先把开着的草稿按超时关掉）。"""

    async def main() -> str:
        engine = g._engine()
        try:
            async with engine.begin() as c:
                turn_id = await store.enqueue(c, g.s.ids, g.s.pid, kind=kind, **kw)
            await g.s._narrator(engine).run(g.s.pid)
            return turn_id
        finally:
            await engine.dispose()

    return eval_api._run(main())


def plant(g: Game, effects: list[Json]) -> None:
    """测试在中间直接写一条事件（让草稿的前提不成立）。"""

    async def main() -> None:
        engine = g._engine()
        try:
            async with engine.begin() as c:
                st = await store.sim_state(c, g.s.pid)
                assert st is not None
                w = Writer(
                    g.s.book, g.s.pid, st, key_base=f"{g.s.pid}/plant", turn_id=None, ids=g.s.ids, now=recorded_at()
                )
                w.add(
                    w.full(
                        t=st["t"],
                        dt=0,
                        actor="system",
                        type="action",
                        place=w.player_place,
                        summary="評価の設定",
                        effects=effects,
                        check=eval_api.SETUP_PASSED,
                    )
                )
                await c.execute(insert(events), [to_row(e) for e in w.events])
                await c.execute(
                    update(world_state)
                    .where(world_state.c.playthrough_id == g.s.pid)
                    .values(as_of_seq=w.state["seq"], state=w.state)
                )
                await c.execute(
                    update(playthroughs).where(playthroughs.c.playthrough_id == g.s.pid).values(last_seq=w.state["seq"])
                )
        finally:
            await engine.dispose()

    eval_api._run(main())


def rows(g: Game, table: Any, **where: Any) -> list[Json]:
    async def main() -> list[Json]:
        engine = g._engine()
        try:
            async with engine.connect() as c:
                q = select(table).where(*(table.c[k] == v for k, v in where.items()))
                return [dict(r) for r in (await c.execute(q)).mappings()]
        finally:
            await engine.dispose()

    return eval_api._run(main())


def confirm_turns(g: Game) -> list[Json]:
    found = rows(g, turns, playthrough_id=g.s.pid, kind="confirm")
    return sorted(found, key=lambda r: r["created_at"])


def counts(g: Game) -> tuple[int, ...]:
    m = g.metrics()
    names = ("confirms_asked", "confirms_yes", "confirms_no", "confirms_timeout", "confirms_rejected")
    return (*(int(m[n]) for n in names), int(m["candidates_confirm_dropped"]))


def closed_msg(draft_id: str, option: str | None, by: str) -> Json:
    return {"type": "confirm_closed", "draftId": draft_id, "optionId": option, "by": by}


# —— 第 4 组：意图确认 ——


def test_a_draft_is_not_logged_and_yes_commits_it_on_the_original_turn(game: Callable[..., Game]) -> None:
    g = game()
    here = g.s.state()["vars"]["var.player.location"]
    step = g.s.say(MELOS, OFFER)
    asking = step["confirm"]
    draft_id = asking["draftId"]
    assert asking == {"draftId": draft_id, "character": MELOS, "prompt": QUESTION}
    assert draft_id.startswith("draft_") and step["clockMinutes"] == 10
    assert SUMMARY not in [e["summary"] for e in step["events"]]  # 草稿不进事件日志，这一轮其他的照常提交
    turn = g.turn(step["traceId"])
    assert turn["result"]["confirm"] == {**asking, "asked": False}
    assert types(turn["result"]["push"]) == ["turn_settled"] and turn["result"]["push"][0]["minutes"] == 10
    (draft,) = rows(g, drafts, playthrough_id=g.s.pid)
    assert (draft["turn_id"], draft["character"], draft["asked"], draft["prompt"]) == (
        step["traceId"],
        MELOS,
        False,
        QUESTION,
    )
    assert draft["candidate"]["place"] == here and "needsConfirm" not in draft["candidate"]

    # 玩家这期间走开了：答「是」以后那条事件的地点照草稿里候选原来的
    queue(g, "action", client_msg_id="c1", request={"clientMsgId": "c1", "kind": "move", "target": GROUND})
    assert g.s.state()["vars"]["var.player.location"] == GROUND
    seq = g.seq
    yes = g.s.confirm("yes")
    assert (yes["result"], yes["clockMinutes"]) == ("committed", 0) and "narration" not in yes
    (ev,) = yes["events"]
    assert (ev["summary"], ev["confirmed"], ev["dt"], ev["turnId"], ev["place"]) == (
        SUMMARY,
        True,
        0,
        step["traceId"],
        here,
    )
    assert ev["check"]["status"] == "passed" and ev["t"] == g.s.state()["t"]
    assert g.s.state()["vars"]["var.hostage.who"] == "player"
    (commit,) = g.commits(seq)
    assert commit["turnId"] == step["traceId"] and commit["narration"] == []
    assert [(e["dt"], e["turnId"]) for e in commit["events"]] == [(0, step["traceId"])]
    (answer,) = confirm_turns(g)
    assert answer["request"] == {"draftId": draft_id, "optionId": "yes", "by": "button"}
    assert answer["result"]["push"] == [closed_msg(draft_id, "yes", "button")]
    assert rows(g, drafts, playthrough_id=g.s.pid) == []
    assert counts(g) == (1, 1, 0, 0, 0, 0)


def test_no_and_no_answer_drop_the_draft_and_the_clock_stays(game: Callable[..., Game]) -> None:
    g = game()
    first = g.s.say(MELOS, OFFER)
    t = g.s.state()["t"]
    no = g.s.confirm("no")
    assert (no["result"], no["events"], no["clockMinutes"]) == ("discarded", [], 0)
    assert g.s.state()["t"] == t and g.s.state()["vars"]["var.hostage.who"] != "player"
    assert confirm_turns(g)[-1]["result"]["push"] == [closed_msg(first["confirm"]["draftId"], "no", "button")]

    second = g.s.say(MELOS, OFFER)  # 第二次问
    none = g.s.confirm(None)  # 没答：当作超时
    assert (none["result"], none["events"]) == ("discarded", [])
    assert confirm_turns(g)[-1]["result"]["push"] == [closed_msg(second["confirm"]["draftId"], None, "timeout")]

    third = g.s.say(MELOS, OFFER)  # 第三次问；下一步不是回答：按超时关掉
    later = g.s.advance(10)
    assert SUMMARY not in [e["summary"] for e in later["events"]]
    assert confirm_turns(g)[-1]["result"]["push"] == [closed_msg(third["confirm"]["draftId"], None, "timeout")]
    late = g.s.confirm("yes")
    assert late.pop("elapsedMs") >= 0 and late == {"events": [], "clockMinutes": 0, "error": "no_draft"}

    fourth = g.s.say(MELOS, OFFER)  # 一局最多问 3 次：第 4 次丢掉
    assert "confirm" not in fourth and SUMMARY not in [e["summary"] for e in fourth["events"]]
    assert "confirm" not in g.turn(fourth["traceId"])["result"]
    assert counts(g) == (3, 0, 1, 2, 0, 1)


def test_one_draft_at_a_time(game: Callable[..., Game]) -> None:
    """草稿开着时又提出一个：丢掉（candidates_confirm_dropped），不另存。"""
    g = game()
    first = g.s.say(MELOS, OFFER)
    again = g.s.say(MELOS, STAY)  # 叙事者判这一轮时第一个草稿还开着；判完评测入口按超时关掉第一个
    assert "confirm" not in again
    (closing,) = confirm_turns(g)
    assert closing["result"]["push"] == [closed_msg(first["confirm"]["draftId"], None, "timeout")]
    assert rows(g, drafts, playthrough_id=g.s.pid) == []
    assert counts(g) == (1, 0, 0, 1, 0, 1)


def test_asked_true_keeps_the_characters_own_question(game: Callable[..., Game]) -> None:
    g = game()
    step = g.s.say(MELOS, STAY)
    assert step["confirm"]["prompt"] == "……本気で言っているのか。"
    assert g.turn(step["traceId"])["result"]["confirm"]["asked"] is True


def test_a_spoken_answer_is_a_normal_turn_then_the_draft(game: Callable[..., Game]) -> None:
    """用声音（评测里是 say）回答：那一轮照常 10 分钟，判出 confirmAnswer 以后同一次提交里写回答的任务；
    顺序是那一轮的 commit → turn_settled → 草稿的 commit → confirm_closed（by: voice）。"""
    g = game()
    first = g.s.say(MELOS, OFFER)
    draft_id = first["confirm"]["draftId"]
    seq = g.seq
    answer = g.s.say(MELOS, "本気だ。逃げも隠れもしない。")
    assert answer["clockMinutes"] == 10 and "confirm" not in answer
    (ev,) = [e for e in answer["events"] if e["summary"] == SUMMARY]
    assert ev["confirmed"] is True and ev["turnId"] == first["traceId"] and ev["dt"] == 0
    extract = [r for k, r in g.s.text.calls if k == "extract"][-1]  # type: ignore[attr-defined]
    assert extract["confirm"] == {"prompt": QUESTION, "summary": SUMMARY}
    (closing,) = confirm_turns(g)
    assert closing["request"] == {"draftId": draft_id, "optionId": "yes", "by": "voice"}
    talk = g.turn(answer["traceId"])
    assert talk["result"]["seq"] < closing["result"]["seq"] and talk["settled_at"] < closing["settled_at"]
    commits = g.commits(seq)
    assert [c.get("turnId") for c in commits] == [answer["traceId"], first["traceId"]]
    # 一条连接推到最后：那一轮的 turn_settled 在前，confirm_closed 在后
    (pushed,) = g.results(g.seq)
    assert [(m["type"], m.get("turnId") or m.get("draftId")) for m in pushed] == [
        ("turn_settled", first["traceId"]),
        ("turn_settled", answer["traceId"]),
        ("confirm_closed", draft_id),
    ]
    assert pushed[-1] == closed_msg(draft_id, "yes", "voice")

    # 说「やめておく」：不是
    h = game()
    h.s.say(MELOS, OFFER)
    refused = h.s.say(MELOS, "やめておく。今のは忘れてくれ。")
    assert SUMMARY not in [e["summary"] for e in refused["events"]] and refused["clockMinutes"] == 10
    assert confirm_turns(h)[-1]["request"]["by"] == "voice" and counts(h) == (1, 0, 1, 0, 0, 0)

    # 不是对着反问的人物说的：不判回答，下一步之前按超时关掉
    k = game()
    k.s.say(MELOS, OFFER)
    k.s.say(OLD, "本気だ。")
    assert confirm_turns(k)[-1]["request"]["by"] == "timeout" and counts(k) == (1, 0, 0, 1, 0, 0)


def test_yes_after_the_world_changed_writes_a_rejected_event(game: Callable[..., Game]) -> None:
    g = game()
    step = g.s.say(MELOS, OFFER)
    plant(g, [{"op": "set", "var": "var.player.custody", "value": "executed"}])  # 期间前提不成立了
    seq = g.seq
    yes = g.s.confirm("yes")
    assert yes["result"] == "rejected" and len(yes["narration"]) == 1 and yes["narration"][0]
    (ev,) = yes["events"]
    assert (ev["confirmed"], ev["turnId"], ev["dt"]) == (True, step["traceId"], 0)
    assert ev["check"]["status"] == "rejected" and "R2-precondition" in ev["check"]["failedRules"]
    assert ev["effects"]  # 评测给候选原本的 effects；日志里那条是空的
    (logged,) = [e for e in g.s.events() if e["eventId"] == ev["eventId"]]
    assert logged["effects"] == [] and logged["confirmed"] is True
    (commit,) = g.commits(seq)
    assert commit["turnId"] == step["traceId"] and commit["narration"] == yes["narration"]
    assert confirm_turns(g)[-1]["result"]["push"] == [closed_msg(step["confirm"]["draftId"], "yes", "button")]
    assert counts(g) == (1, 1, 0, 0, 1, 0)


def test_act_end_closes_the_open_draft_before_act_ended(game: Callable[..., Game]) -> None:
    g = game("sc.canon@beat.06", walked=True)
    step = g.s.say(MELOS, OFFER)
    draft_id = step["confirm"]["draftId"]
    advance = queue(g, "advance", minutes=600)  # 不经评测入口：草稿开着时收幕
    push = g.turn(advance)["result"]["push"]
    assert types(push)[-2:] == ["confirm_closed", "act_ended"]
    assert push[-2] == closed_msg(draft_id, None, "timeout")
    assert rows(g, drafts, playthrough_id=g.s.pid) == []
    assert counts(g) == (1, 0, 0, 1, 0, 0)

    # 幕末待选时答：草稿已经不在，不写任务
    async def late() -> str | None:
        engine = g._engine()
        try:
            async with engine.begin() as c:
                return await store.answer_draft(c, g.s.ids, g.s.pid, draft_id, "yes", "button")
        finally:
            await engine.dispose()

    assert eval_api._run(late()) is None and confirm_turns(g) == []


def test_a_proposal_in_the_turn_that_ends_the_act_is_not_asked(game: Callable[..., Game]) -> None:
    g = game("sc.canon@beat.06", walked=True)
    g.s.advance(1420 - g.s.state()["t"])  # 下一轮的 10 分钟里收幕（同 test_gateway_b3）
    step = g.s.say(MELOS, OFFER)
    assert g.row()["act_end"] is not None
    assert "confirm" not in step and "confirm" not in g.turn(step["traceId"])["result"]
    assert types(g.turn(step["traceId"])["result"]["push"]) == ["turn_settled", "act_ended"]
    assert rows(g, drafts, playthrough_id=g.s.pid) == []
    assert counts(g) == (0, 0, 0, 0, 0, 1)


def test_a_bad_question_is_replaced() -> None:
    said = "王様の前で、私が人質になってもいい"
    for q in ("連絡は090-1234-5678まで", f"……{said}と？", "あ" * 31, None, ""):
        assert confirm.question_of({"question": q}, said) == confirm.QUESTION_FALLBACK, q
    assert confirm.question_of({"question": QUESTION}, said) == QUESTION


def test_a_question_with_a_phone_number_is_not_asked_aloud(game: Callable[..., Game]) -> None:
    g = game()
    g.s.text = FakeText(
        FAKE_TEXT,
        rules=[
            {
                "kind": "extract",
                "when": {"playerContains": "電話"},
                "output": {
                    "candidates": [
                        {
                            "actor": "player",
                            "type": "say",
                            "origin": "turn",
                            "summary": "旅人は、自分が人質になると言った",
                            "causes": [],
                            "effects": [{"op": "set", "var": "var.hostage.who", "value": "player"}],
                            "needsConfirm": True,
                            "asked": False,
                            "question": "電話は090-1234-5678か",
                        }
                    ]
                },
            }
        ],
    )
    step = g.s.say(MELOS, "電話するより、私が人質に行く")
    assert step["confirm"]["prompt"] == confirm.QUESTION_FALLBACK


# —— 第 5 组：评测入口的 hold 和作废 ——


def test_hold_then_retract_leaves_nothing(game: Callable[..., Game]) -> None:
    g = game()
    before = g.s.state()
    held = g.s.say(OLD, "こんにちは。", hold=True)
    assert (held["held"], held["events"], held["clockMinutes"]) == (True, [], 0) and held["reply"]
    r = g.s.retract(1)
    assert (r["retract"], r["events"], r["clockMinutes"], r["traceId"]) == ("retracted", [], 0, held["traceId"])
    assert g.s.utterance_cleared(1) is True
    assert g.s.state() == before
    turn = g.turn(held["traceId"])
    assert (turn["status"], turn["outcome"], turn["minutes"]) == ("retracted", "retracted", 0)
    assert all(u["deleted_at"] is not None for u in rows(g, utterances, turn_id=held["traceId"]))
    assert g.metrics()["turns_retracted"] == 1


def test_hold_then_the_next_step_commits_it_first(game: Callable[..., Game]) -> None:
    g = game()
    t = g.s.state()["t"]
    held = g.s.say(OLD, "こんにちは。", hold=True)
    nxt = g.s.say(OLD, "この市は、ずいぶん静かですね。")
    assert nxt["clockMinutes"] == 20 and g.s.state()["t"] == t + 20
    assert {e["turnId"] for e in nxt["events"] if e.get("turnId")} == {held["traceId"], nxt["traceId"]}
    assert g.s.retract(1)["retract"] == "too_late" and g.s.utterance_cleared(1) is False
    held2 = g.s.say(OLD, "では、また。", hold=True)  # 第 4 步
    assert [e["turnId"] for e in g.s.events() if e.get("turnId") == held2["traceId"]]  # 查询之前也先提交
    assert g.s.retract(4)["retract"] == "too_late" and g.metrics()["turns_retracted"] == 0


# —— 第 1 组（叙事者这一层）：提交窗口、作废和提交同时来 ——


def test_the_narrator_waits_out_the_window_and_a_retract_inside_it_wins(env: Env) -> None:
    async def talk(engine: Any, pid: str, window: float) -> str:
        async with engine.begin() as c:
            turn_id = await store.enqueue(
                c, env.ids, pid, kind="talk", input_mode="text", character=OLD, commit_after=window
            )
            await store.add_utterance(c, env.ids, pid, turn_id, speaker="player", text="……", t=0)
            await store.add_utterance(c, env.ids, pid, turn_id, speaker=OLD, text="……", t=0, source="live")
        return turn_id

    async def main() -> None:
        engine = env.engine()
        try:
            pid = await env.opened(engine)
            last = await last_seq(engine, pid)
            started = time.monotonic()
            turn_id = await talk(engine, pid, 0.8)

            async def retract_when_leased() -> str | None:
                while True:  # 叙事者取了任务、判完在等窗口时作废
                    async with engine.connect() as c:
                        status = await c.scalar(select(turns.c.status).where(turns.c.turn_id == turn_id))
                    if status == "leased":
                        break
                    await asyncio.sleep(0.02)
                await asyncio.sleep(0.1)
                async with engine.begin() as c:
                    return await store.retract_queued(c, pid, turn_id)

            kind, done = await asyncio.gather(retract_when_leased(), env.narrator(engine).run(pid))
            assert kind == "talk" and done == []
            assert time.monotonic() - started >= 0.75  # 叙事者等到 commit_after 才去提交，发现作废了
            assert await last_seq(engine, pid) == last
            async with engine.connect() as c:
                status = await c.scalar(select(turns.c.status).where(turns.c.turn_id == turn_id))
                texts = (await c.execute(select(utterances.c.text).where(utterances.c.turn_id == turn_id))).all()
            assert status == "retracted" and texts == [(None,), (None,)]

            # 没人作废：窗口过了才提交
            started = time.monotonic()
            turn2 = await talk(engine, pid, 0.4)
            (r,) = await env.narrator(engine).run(pid)
            assert r.task.turn_id == turn2 and time.monotonic() - started >= 0.35
        finally:
            await engine.dispose()

    asyncio.run(main())


async def last_seq(engine: Any, pid: str) -> int:
    async with engine.connect() as c:
        return int(await c.scalar(select(playthroughs.c.last_seq).where(playthroughs.c.playthrough_id == pid)) or 0)


def test_retract_and_commit_at_the_same_time_only_one_wins(env: Env) -> None:
    """叙事者判完、提交之前（before_commit）作废：作废算数，叙事者丢掉结果。叙事者已经锁住这一轮在提交（fault
    「apply」时）才来的作废：等锁放开，发现已经提交了，too_late。"""

    async def main() -> None:
        engine = env.engine()
        try:
            pid = await env.opened(engine)
            first = await env.talk(engine, pid)
            last = await last_seq(engine, pid)
            won: list[str | None] = []

            async def hook(task: Task) -> None:
                async with engine.begin() as c:
                    won.append(await store.retract_queued(c, pid, task.turn_id))

            assert await env.narrator(engine, before_commit=hook).run(pid) == []
            assert won == ["talk"] and await last_seq(engine, pid) == last
            async with engine.connect() as c:
                assert await c.scalar(select(turns.c.status).where(turns.c.turn_id == first)) == "retracted"

            second = await env.talk(engine, pid)
            late: list[asyncio.Task[str | None]] = []

            async def retract() -> str | None:
                async with engine.begin() as c:  # 叙事者锁着这一轮：这里等它提交完
                    return await store.retract_queued(c, pid, second)

            def fault(step: str) -> None:
                if step == "apply" and not late:
                    late.append(asyncio.ensure_future(retract()))

            (r,) = await env.narrator(engine, fault=fault).run(pid)
            assert r.task.turn_id == second and await late[0] is None
            async with engine.connect() as c:
                assert await c.scalar(select(turns.c.status).where(turns.c.turn_id == second)) == "done"
                texts = (await c.execute(select(utterances.c.text).where(utterances.c.turn_id == second))).scalars()
                assert all(t is not None for t in texts)
            assert await last_seq(engine, pid) > last
        finally:
            await engine.dispose()

    asyncio.run(main())


def test_a_failed_answer_does_not_block_the_timeout(game: Callable[..., Game]) -> None:
    """回答的任务三次都没做成（failed）：草稿还开着，超时还能关掉它（`store.answered` 不算 failed 的）。"""
    g = game()
    step = g.s.say(MELOS, OFFER)
    draft_id = step["confirm"]["draftId"]

    async def main() -> tuple[str | None, str | None]:
        engine = g._engine()
        try:
            async with engine.begin() as c:
                first = await store.answer_draft(c, g.s.ids, g.s.pid, draft_id, "yes", "button")
                await c.execute(update(turns).where(turns.c.turn_id == first).values(status="failed"))
                again = await store.answer_draft(c, g.s.ids, g.s.pid, draft_id, None, "timeout")
                twice = await store.answer_draft(c, g.s.ids, g.s.pid, draft_id, "no", "button")
            return again, twice
        finally:
            await engine.dispose()

    again, twice = eval_api._run(main())
    assert again is not None and twice is None


# —— 第 6 组：不记原话 ——


def test_no_words_in_logs_or_spans(game: Callable[..., Game], caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    g = game()
    g.s.tracer = Tracer()
    marker = "合言葉はミズイロノカサ"
    step = g.s.say(MELOS, f"{marker}。{OFFER}")
    assert step["confirm"]["prompt"] == QUESTION
    g.s.confirm("yes")
    g.s.say(MELOS, f"{marker}。{OFFER}", hold=True)
    g.s.retract(3)
    h = game()
    h.s.tracer = g.s.tracer
    h.s.say(MELOS, OFFER)
    plant(h, [{"op": "set", "var": "var.player.custody", "value": "executed"}])
    rejected = h.s.confirm("yes")
    spans = json.dumps([s.attrs for s in g.s.tracer.spans], ensure_ascii=False)
    names = {s.name for s in g.s.tracer.spans}
    assert "narrator.confirm" in names
    for word in (marker, QUESTION, SUMMARY, OFFER, *rejected["narration"]):
        assert word not in caplog.text and word not in spans, word
    confirmed = [s.attrs for s in g.s.tracer.spans if s.name == "narrator.confirm"]
    assert [(a["answer"], a["by"], a["result"], a["nth"]) for a in confirmed] == [
        ("yes", "button", "committed", 1),
        ("yes", "button", "rejected", 1),
    ]


# —— 第 7 组：迁移、删除整局 ——


def test_migration_0004_goes_down_and_up(migrated: str) -> None:
    truncate(migrated)
    cfg = alembic_config(migrated)
    engine = create_async_engine(async_url(migrated), poolclass=NullPool)

    async def columns(table: str) -> set[str]:
        async with engine.connect() as c:
            return set(await c.run_sync(lambda sc: {x["name"] for x in inspect(sc).get_columns(table)}))

    async def tables() -> set[str]:
        async with engine.connect() as c:
            return set(await c.run_sync(lambda sc: inspect(sc).get_table_names()))

    try:
        command.downgrade(cfg, "0003")
        assert "drafts" not in eval_api._run(tables())
        assert "commit_after" not in eval_api._run(columns("turns"))
        assert "confirms_asked" not in eval_api._run(columns("playthrough_metrics"))
        command.upgrade(cfg, "head")
        assert "drafts" in eval_api._run(tables())
        assert "commit_after" in eval_api._run(columns("turns"))
        assert {
            "confirms_asked",
            "confirms_yes",
            "confirms_no",
            "confirms_timeout",
            "confirms_rejected",
        } <= eval_api._run(columns("playthrough_metrics"))
    finally:
        command.upgrade(cfg, "head")
        eval_api._run(engine.dispose())


def test_deleting_a_playthrough_takes_its_drafts(game: Callable[..., Game]) -> None:
    assert "drafts" in PER_PLAYTHROUGH
    g = game()
    g.s.say(MELOS, OFFER)
    assert len(rows(g, drafts, playthrough_id=g.s.pid)) == 1

    async def main() -> int:
        engine = g._engine()
        try:
            async with engine.begin() as c:
                await c.execute(delete(playthroughs).where(playthroughs.c.playthrough_id == g.s.pid))
            async with engine.connect() as c:
                return int(
                    await c.scalar(select(func.count()).select_from(drafts).where(drafts.c.playthrough_id == g.s.pid))
                    or 0
                )
        finally:
            await engine.dispose()

    assert eval_api._run(main()) == 0
