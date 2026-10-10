"""网关、叙事者、评测入口共用的读写：开局、排一轮、读事件和状态。

事务由调用方开（`async with engine.begin() as c`），这里只在给定的连接上执行。
"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection
from zoujin_worldsim import SimState, apply, initial_state

from zoujin_backend.db.events import from_row
from zoujin_backend.db.tables import events, playthrough_metrics, playthroughs, turns, utterances, world_state
from zoujin_backend.ids import IdGen
from zoujin_backend.world import Book

Json = Any


async def create_playthrough(c: AsyncConnection, ids: IdGen, *, user_id: str, book: Book, role_id: str) -> str:
    """开局：一局的行、指标行和一个 open 任务（叙事者写开局事件）。返回 playthroughId。"""
    pid = ids.new("pt")
    await c.execute(
        insert(playthroughs).values(
            playthrough_id=pid,
            user_ref=user_id,
            book_id=book.book_id,
            world_model_version=book.version,
            role_id=role_id,
            status="active",
        )
    )
    await c.execute(insert(playthrough_metrics).values(playthrough_id=pid))
    await enqueue(c, ids, pid, kind="open")
    return pid


async def enqueue(
    c: AsyncConnection,
    ids: IdGen,
    pid: str,
    *,
    kind: str,
    turn_id: str | None = None,
    input_mode: str | None = None,
    character: str | None = None,
    turn_seq: int | None = None,
    minutes: int | None = None,
    status: str = "pending",
) -> str:
    """排一个叙事者任务。幂等键就是 turnId：重试用同一个，这一轮写的事件的键都以它开头。
    created_at 用 clock_timestamp()，同一个事务里排的几个也分得出先后。
    status="lost"：断线时人物还没说完的一轮，只留记录（welcome 的 lastTurn），叙事者不处理。"""
    turn_id = turn_id or ids.new("turn")
    await c.execute(
        insert(turns).values(
            turn_id=turn_id,
            playthrough_id=pid,
            kind=kind,
            input_mode=input_mode,
            character=character,
            turn_seq=turn_seq,
            minutes=minutes,
            status=status,
            idempotency_key=turn_id,
            created_at=func.clock_timestamp(),
        )
    )
    return turn_id


async def add_utterance(
    c: AsyncConnection,
    ids: IdGen,
    pid: str,
    turn_id: str,
    *,
    speaker: str,
    text: str | None,
    t: int,
    source: str | None = None,
) -> str:
    utterance_id = ids.new("utt")
    await c.execute(
        insert(utterances).values(
            utterance_id=utterance_id,
            playthrough_id=pid,
            turn_id=turn_id,
            speaker=speaker,
            text=text,
            source=source,
            t=t,
            recorded_at=func.clock_timestamp(),
        )
    )
    return utterance_id


async def playthrough(c: AsyncConnection, pid: str) -> dict[str, Any] | None:
    row = (await c.execute(select(playthroughs).where(playthroughs.c.playthrough_id == pid))).mappings().first()
    return dict(row) if row is not None else None


async def sim_state(c: AsyncConnection, pid: str) -> SimState | None:
    """world_state 缓存里的 SimState（开局任务还没做完时为 None）。"""
    st = await c.scalar(select(world_state.c.state).where(world_state.c.playthrough_id == pid))
    return cast(SimState, st) if st is not None else None


async def event_log(
    c: AsyncConnection, pid: str, version: str, *, after_seq: int = 0, upto_seq: int | None = None
) -> list[Json]:
    """事件日志里 after_seq 之后（到 upto_seq 为止）的完整事件，按 seq。"""
    q = select(events).where(events.c.playthrough_id == pid, events.c.seq > after_seq)
    if upto_seq is not None:
        q = q.where(events.c.seq <= upto_seq)
    rows = (await c.execute(q.order_by(events.c.seq))).mappings().all()
    return [from_row(dict(r), version) for r in rows]


def replay(book: Book, role_id: str, log: list[Json], upto_seq: int | None = None) -> SimState:
    """初值 + 按 seq 应用全部事件（data-design 4.4）。"""
    state = initial_state(book.world, role_id)
    for ev in log:
        if upto_seq is not None and ev["seq"] > upto_seq:
            break
        state = apply(book.world, state, ev)
    return state
