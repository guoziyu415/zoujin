"""网关、叙事者、评测入口共用的读写：开局、排一轮、读事件和状态。

事务由调用方开（`async with engine.begin() as c`），这里只在给定的连接上执行。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, cast

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection
from zoujin_worldsim import SimState, apply, initial_state

from zoujin_backend.db.events import from_row
from zoujin_backend.db.tables import drafts, events, playthrough_metrics, playthroughs, turns, utterances, world_state
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
    commit_after: float | None = None,
    created_at: Any = None,
    flags: Iterable[str] | None = None,
) -> str:
    """排一个叙事者任务。幂等键就是 turnId：重试用同一个，这一轮写的事件的键都以它开头。
    created_at 用 clock_timestamp()，同一个事务里排的几个也分得出先后。
    status="lost"：断线时人物还没说完的一轮，只留记录（welcome 的 lastTurn），叙事者不处理。
    request：动作和幕末的请求（B-3），不放原话（原话在 utterances）。
    commit_after：叙事者最早在几秒以后提交（B-4 作废的窗口，按库的时钟算）；None = 判完就提交。
    created_at：排队的时刻（草稿到期的超时任务排在到期那一刻，B-4）。
    flags：第 0 步安全筛查的标记（B-12），叙事者按它们判。"""
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
            created_at=func.clock_timestamp() if created_at is None else created_at,
            commit_after=None if commit_after is None else func.clock_timestamp() + timedelta(seconds=commit_after),
            flags=sorted(flags) if flags else None,
        )
    )
    return turn_id


# —— 作废（B-4，api-contract 3.6）——

RETRACTABLE = ("talk", "plan")


async def retract_queued(c: AsyncConnection, pid: str, turn_id: str) -> str | None:
    """已经交给叙事者、还没提交的一轮（pending / leased）改成 retracted，原话清空、记 deleted_at（行留着），
    turns_retracted 加 1。和叙事者的提交谁先拿到这一轮的行锁谁算数（叙事者只认 leased）。返回这一轮的 kind；
    已经提交了、不认识、不能作废的返回 None（too_late）。"""
    row = (
        await c.execute(
            update(turns)
            .where(
                turns.c.turn_id == turn_id,
                turns.c.playthrough_id == pid,
                turns.c.kind.in_(RETRACTABLE),
                turns.c.status.in_(("pending", "leased")),
            )
            .values(
                status="retracted", outcome="retracted", minutes=0, lease_until=None, settled_at=func.now(), flags=None
            )
            .returning(turns.c.kind)
        )
    ).first()
    if row is None:
        return None
    await c.execute(update(utterances).where(utterances.c.turn_id == turn_id).values(text=None, deleted_at=func.now()))
    await count_retracted(c, pid)
    return str(row.kind)


async def count_retracted(c: AsyncConnection, pid: str) -> None:
    m = playthrough_metrics.c
    await c.execute(
        update(playthrough_metrics).where(m.playthrough_id == pid).values(turns_retracted=m.turns_retracted + 1)
    )


# —— 意图确认的草稿（B-4，api-contract 3.9）——


async def count(c: AsyncConnection, pid: str, **by: float) -> None:
    """playthrough_metrics 的计数、花费加几（B-12 的安全和输出侧；行不存在就不加，局已经删了）。"""
    if not by:
        return
    await c.execute(
        update(playthrough_metrics)
        .where(playthrough_metrics.c.playthrough_id == pid)
        .values({k: getattr(playthrough_metrics.c, k) + v for k, v in by.items()})
    )


async def safety_state(c: AsyncConnection, pid: str, *, lock: bool = False) -> dict[str, Any]:
    """这一局安全筛查的状态（B-12）：{paused, hinted, ambiguous}。"""
    q = select(playthroughs.c.safety).where(playthroughs.c.playthrough_id == pid)
    if lock:
        q = q.with_for_update()
    got = await c.scalar(q)
    return dict(got or {})


async def set_safety(c: AsyncConnection, pid: str, state: Mapping[str, Any]) -> None:
    await c.execute(update(playthroughs).where(playthroughs.c.playthrough_id == pid).values(safety=dict(state)))


async def open_draft(c: AsyncConnection, pid: str, *, lock: bool = False) -> dict[str, Any] | None:
    """这一局开着的草稿（最多一个）。lock：锁住这一行（写回答的任务、关掉草稿时）。"""
    q = select(drafts).where(drafts.c.playthrough_id == pid).order_by(drafts.c.created_at).limit(1)
    if lock:
        q = q.with_for_update()
    row = (await c.execute(q)).mappings().first()
    return dict(row) if row is not None else None


async def answered(c: AsyncConnection, pid: str, draft_id: str) -> bool:
    """这个草稿已经有一行回答的任务（按钮、声音、超时，谁先写谁算）。做失败了的不算：草稿还开着，超时还能关掉它。"""
    found = await c.scalar(
        select(turns.c.turn_id).where(
            turns.c.playthrough_id == pid,
            turns.c.kind == "confirm",
            turns.c.request["draftId"].astext == draft_id,
            turns.c.status != "failed",
        )
    )
    return found is not None


async def answer_draft(
    c: AsyncConnection, ids: IdGen, pid: str, draft_id: str, option_id: str | None, by: str, *, at: Any = None
) -> str | None:
    """给开着的草稿写一行 `kind: "confirm"` 的任务（叙事者按局排队处理）。草稿不在了、已经有回答的，什么都不写，
    返回 None。锁住草稿那一行再查，按钮、声音和超时同时来时只写一行。"""
    row = await c.scalar(
        select(drafts.c.draft_id).where(drafts.c.draft_id == draft_id, drafts.c.playthrough_id == pid).with_for_update()
    )
    if row is None or await answered(c, pid, draft_id):
        return None
    return await enqueue(
        c, ids, pid, kind="confirm", request={"draftId": draft_id, "optionId": option_id, "by": by}, created_at=at
    )


async def expire_drafts(c: AsyncConnection, ids: IdGen, pid: str) -> list[str]:
    """到期了、还没有回答的草稿写超时的任务，排在到期的那一刻（之前来的回答先算）。返回写了的草稿 ID。"""
    rows = (
        await c.execute(
            select(drafts.c.draft_id, drafts.c.expires_at)
            .where(drafts.c.playthrough_id == pid, drafts.c.expires_at <= func.now())
            .with_for_update()
        )
    ).all()
    out = []
    for draft_id, at in rows:
        if await answer_draft(c, ids, pid, draft_id, None, "timeout", at=at) is not None:
            out.append(draft_id)
    return out


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
