"""記憶帳的删除（B-13，契约第 4 节删除语义、data-design 5.2 L1 / L2、api-contract 2.7、2.9）。REST 和评测入口共用。

删一条记忆（L1），同一个事务里：
1. 这条记忆 `text`、`keeps` 置空、写 `deleted_at`（行留着，审计）；
2. 顺着 `from_events → events.turn_id → utterances.turn_id` 清空整轮原话（玩家和人物的），这几轮里幕末打算的转述按
   B-3 的写法清掉（`store.clear_plan_texts`），这几轮开着的意图确认草稿丢掉；
3. `promise_id` 指向开着的约定 → 追加一条 `forget` 事件（`origin: "memory"`、`actor: "player"`、`dt: 0`，
   约定 `voided`），挂在一条 `kind = forget` 的任务行上，照常 NOTIFY，网关推 `commit`（`memories[]` 带 `deleted`）；
   已经 `kept` / `broken` 的约定不动；
4. 关系按剩下的记忆重算。
事务之后网关丢掉那几轮在内存里的最近对话、重建这个人物开着的会话（`gateway/rest.py`）。世界的后果不撤销。

删整局（L2）：这一局的行按外键级联删掉（`playthroughs` 一行，别的表都挂在它上面）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from zoujin_backend.db import store
from zoujin_backend.db.events import recorded_at, to_row
from zoujin_backend.db.tables import drafts, memory_items, playthrough_metrics, playthroughs, turns, utterances
from zoujin_backend.db.tables import events as events_t
from zoujin_backend.db.tables import world_state as world_state_t
from zoujin_backend.ids import IdGen
from zoujin_backend.narrator import memory
from zoujin_backend.narrator.core import CHANNEL
from zoujin_backend.narrator.writer import Writer
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.world import Library

Json = Any

KIND = "forget"  # 记下 forget 事件的任务行（不进叙事者的队列，写的时候就是 done）
CHECKER = "b13:forget"


class NotFound(LookupError):
    """没有这条记忆（或这一局），或者已经删了。"""


@dataclass(frozen=True)
class Deleted:
    memory_id: str
    character: str
    relation_label: str
    relation_level: int
    promise_voided: str | None
    turn_ids: tuple[str, ...]  # 清了原话的那几轮（网关丢掉内存里的最近对话）
    seq: int | None = None  # 写了 forget 事件时，这一局新的 lastSeq

    def response(self, *, rebuilt: bool) -> Json:
        return {
            "memoryId": self.memory_id,
            "deleted": True,
            "character": self.character,
            "relationLabel": self.relation_label,
            "relationLevel": self.relation_level,
            "promiseVoided": self.promise_voided,
            "sessionRebuilt": rebuilt,
        }


async def delete_memory(
    c: AsyncConnection, library: Library, ids: IdGen, schemas: SchemaBook, pid: str, memory_id: str
) -> Deleted:
    """在调用方的事务里删一条记忆（见模块说明）。没有、已删 → NotFound。"""
    pt = (
        (await c.execute(select(playthroughs).where(playthroughs.c.playthrough_id == pid).with_for_update()))
        .mappings()
        .first()
    )
    if pt is None:
        raise NotFound(pid)
    row = (
        (
            await c.execute(
                select(memory_items)
                .where(
                    memory_items.c.memory_id == memory_id,
                    memory_items.c.playthrough_id == pid,
                    memory_items.c.deleted_at.is_(None),
                )
                .with_for_update()
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise NotFound(memory_id)
    book = library.version(pt["world_model_version"])
    who = str(row["character"])
    await c.execute(
        update(memory_items)
        .where(memory_items.c.memory_id == memory_id)
        .values(text=None, keeps=None, deleted_at=func.now())
    )
    turn_ids = tuple(
        sorted(
            {
                str(t)
                for t in (
                    await c.scalars(
                        select(events_t.c.turn_id).where(
                            events_t.c.playthrough_id == pid,
                            events_t.c.event_id.in_(list(row["from_events"])),
                            events_t.c.turn_id.is_not(None),
                        )
                    )
                ).all()
            }
        )
    )
    if turn_ids:
        await c.execute(
            update(utterances)
            .where(utterances.c.turn_id.in_(turn_ids), utterances.c.deleted_at.is_(None))
            .values(text=None, deleted_at=func.now())
        )
        await store.clear_plan_texts(c, pid, list(turn_ids))
        await c.execute(delete(drafts).where(drafts.c.playthrough_id == pid, drafts.c.turn_id.in_(turn_ids)))

    label, level = await memory.relation_of(c, book, pid, str(pt["role_id"]), who)
    voided: str | None = None
    seq: int | None = None
    state = await store.sim_state(c, pid)
    promise = (state.get("promises") or {}).get(row["promise_id"] or "") if state is not None else None
    if state is not None and promise is not None and promise["status"] == "open":
        voided = str(row["promise_id"])
        seq = await _forget(c, book, ids, schemas, pid, dict(pt), state, who, voided, memory_id, label, level)
    m = playthrough_metrics.c
    await c.execute(
        update(playthrough_metrics).where(m.playthrough_id == pid).values(memories_deleted=m.memories_deleted + 1)
    )
    return Deleted(memory_id, who, label, level, voided, turn_ids, seq)


async def _forget(
    c: AsyncConnection,
    book: Any,
    ids: IdGen,
    schemas: SchemaBook,
    pid: str,
    pt: dict[str, Any],
    state: Any,
    who: str,
    promise_id: str,
    memory_id: str,
    label: str,
    level: int,
) -> int:
    """约定作废的 forget 事件：一条任务行（done）+ 一条事件，更新 world_state 和 lastSeq，NOTIFY。返回新的 seq。"""
    turn_id = ids.new("turn")
    w = Writer(book, pid, state, key_base=turn_id, turn_id=None, ids=ids, now=recorded_at())
    name = book.characters[who]["name"]
    ev = w.add(
        w.full(
            t=state["t"],
            dt=0,
            actor="player",
            type="forget",
            origin="memory",
            place=w.player_place,
            # 中立的一句：不写「覚えていない」「忘れた」（UX 评审：删除不能在故事里留下痕迹）；这个人物的局势说明不带它
            summary=f"{name}との約束は、なかったことになった",
            effects=[{"op": "promise", "promiseId": promise_id, "change": "voided"}],
            check={"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER},
        )
    )
    schemas.event(ev)
    change = {
        "character": who,
        "change": "deleted",
        "memoryId": memory_id,
        "relationLabel": label,
        "relationLevel": level,
    }
    await c.execute(
        insert(turns).values(
            turn_id=turn_id,
            playthrough_id=pid,
            kind=KIND,
            character=who,
            status="done",
            idempotency_key=turn_id,
            minutes=0,
            settled_at=func.now(),
            result={"push": [], "seq": w.state["seq"], "memories": [change]},
        )
    )
    await c.execute(insert(events_t), [to_row(ev)])
    await c.execute(
        update(world_state_t)
        .where(world_state_t.c.playthrough_id == pid)
        .values(as_of_seq=w.state["seq"], state=w.state)
    )
    await c.execute(
        update(playthroughs)
        .where(playthroughs.c.playthrough_id == pid)
        .values(last_seq=w.state["seq"], last_active_at=func.now())
    )
    payload = {"pid": pid, "seq": w.state["seq"], "kind": KIND, "turnId": turn_id, "outcome": None}
    await c.execute(select(func.pg_notify(CHANNEL, json.dumps(payload))))
    return int(w.state["seq"])


async def delete_playthrough(c: AsyncConnection, pid: str) -> bool:
    """L2：这一局的行全删（别的表按外键级联）。返回删没删到。"""
    res = await c.execute(
        delete(playthroughs).where(playthroughs.c.playthrough_id == pid).returning(playthroughs.c.playthrough_id)
    )
    return res.first() is not None
