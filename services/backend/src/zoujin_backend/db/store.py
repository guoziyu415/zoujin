"""网关、叙事者、评测入口共用的读写：开局、排一轮、读事件和状态。

事务由调用方开（`async with engine.begin() as c`），这里只在给定的连接上执行。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from sqlalchemy import func, insert, select, update
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
    client_msg_id: str | None = None,
    request: Json | None = None,
) -> str:
    """排一个叙事者任务。幂等键就是 turnId：重试用同一个，这一轮写的事件的键都以它开头。
    created_at 用 clock_timestamp()，同一个事务里排的几个也分得出先后。
    status="lost"：断线时人物还没说完的一轮，只留记录（welcome 的 lastTurn），叙事者不处理。
    request：动作和幕末的请求（B-3），不放原话（原话在 utterances）。"""
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
            client_msg_id=client_msg_id,
            request=request,
            created_at=func.clock_timestamp(),
        )
    )
    return turn_id


@dataclass
class Run:
    """一局上不是事件、不进 WorldState 的几样（B-3，迁移 0003）：叙事者在提交的事务里读、改、写回，网关只读。"""

    player_spot: str | None = None
    played: list[str] = field(default_factory=list)
    act_end: Json | None = None
    plan_tries: int = 0
    plan_alternative: Json | None = None
    arrival: Json | None = None

    @classmethod
    def of(cls, row: Mapping[str, Any]) -> Run:
        return cls(
            player_spot=row.get("player_spot"),
            played=list(row.get("played_pieces") or []),
            act_end=row.get("act_end"),
            plan_tries=int(row.get("plan_tries") or 0),
            plan_alternative=row.get("plan_alternative"),
            arrival=row.get("arrival"),
        )

    def values(self) -> dict[str, Any]:
        return {
            "player_spot": self.player_spot,
            "played_pieces": list(self.played),
            "act_end": self.act_end,
            "plan_tries": self.plan_tries,
            "plan_alternative": self.plan_alternative,
            "arrival": self.arrival,
        }


PLAN_TEXT_CLEARED = "cleared"


async def clear_plan_texts(c: AsyncConnection, pid: str, turn_ids: list[str] | None = None) -> int:
    """幕末打算的转述（label、narration、替代去处的 label）从 turns.result 里清掉（B-3 第 4 条，data-design 5.2、5.3）：
    記憶帳按轮删除（L1）给那几轮，结局以后给 None（这一局全部）。事件里的 plan.label 不动（事件不删，写入前已过滤）。
    返回清了几轮。"""
    q = select(turns.c.turn_id, turns.c.result).where(turns.c.playthrough_id == pid, turns.c.kind == "plan")
    if turn_ids is not None:
        q = q.where(turns.c.turn_id.in_(turn_ids))
    n = 0
    for turn_id, result in (await c.execute(q)).all():
        if not result or result.get(PLAN_TEXT_CLEARED):
            continue
        kept = []
        for m in result.get("push", []):
            if m.get("type") == "act_plan_result":
                m = {k: v for k, v in m.items() if k != "narration"}
                if m.get("alternative"):
                    m["alternative"] = {k: v for k, v in m["alternative"].items() if k != "label"}
            kept.append(m)
        await c.execute(
            update(turns)
            .where(turns.c.turn_id == turn_id)
            .values(result={**result, "push": kept, PLAN_TEXT_CLEARED: True})
        )
        n += 1
    return n


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
