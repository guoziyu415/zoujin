"""Deletion from the 記憶帳 (memory book) (B-13, contract section 4 deletion semantics, data-design 5.2 L1 / L2,
api-contract 2.7, 2.9). Shared by REST and the eval entry point.

Deleting one memory (L1), in a single transaction:
1. set this memory's `text` and `keeps` to null and write `deleted_at` (the row stays, for audit);
2. follow `from_events → events.turn_id → utterances.turn_id` to clear the original words of those whole turns (both
   the player's and the character's), clear the retelling of end-of-act plans in those turns the B-3 way
   (`store.clear_plan_texts`), and drop the intent-confirmation drafts open on those turns;
3. if `promise_id` points to an open promise → append a `forget` event (`origin: "memory"`, `actor: "player"`,
   `dt: 0`, promise `voided`) hung on a task row with `kind = forget`, NOTIFY as usual, and the gateway pushes `commit`
   (`memories[]` carries `deleted`); promises already `kept` / `broken` are untouched;
4. recompute the relationship from the remaining memories.
After the transaction the gateway drops those turns' recent dialogue held in memory and rebuilds this character's open
session (`gateway/rest.py`). Consequences in the world are not undone.

Deleting a whole playthrough (L2): the playthrough's rows are deleted by foreign-key cascade (one `playthroughs` row;
every other table hangs off it).

記憶帳の削除（B-13、契約第 4 節の削除の意味論、data-design 5.2 L1 / L2、api-contract 2.7・2.9）。
REST と評価の入口で共有する。

記憶 1 件の削除（L1）。同じトランザクションの中で：
1. この記憶の `text`・`keeps` を null にし、`deleted_at` を書く（行は監査用に残す）。
2. `from_events → events.turn_id → utterances.turn_id` をたどってそのターン全体の発話の原文（プレイヤーと登場人物の
   両方）を消し、そのターンの幕末のプランの言い換えを B-3 のやり方で消し（`store.clear_plan_texts`）、そのターンで
   開いている意図確認の草稿を捨てる。
3. `promise_id` が開いている約束を指していれば → `forget` イベントを 1 件追加し（`origin: "memory"`、
   `actor: "player"`、`dt: 0`、約束は `voided`）、`kind = forget` のタスク行にぶら下げ、通常どおり NOTIFY して、
   ゲートウェイが `commit`（`memories[]` に `deleted`）を送る。すでに `kept` / `broken` の約束には触れない。
4. 残った記憶から関係を計算し直す。
トランザクションの後、ゲートウェイはそのターンのメモリ上の最近の会話を捨て、この登場人物の開いているセッションを
作り直す（`gateway/rest.py`）。世界での結果は取り消さない。

プレイ全体の削除（L2）：このプレイの行を外部キーのカスケードで削除する（`playthroughs` の 1 行。ほかのテーブルは
すべてそれにぶら下がっている）。
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

# Task row that records the forget event (not in the narrator's queue; written already done)
# forget イベントを記録するタスク行（ナレーターのキューには入らず、書いた時点で done）
KIND = "forget"
CHECKER = "b13:forget"


class NotFound(LookupError):
    """No such memory (or playthrough), or it is already deleted.

    その記憶（またはプレイ）がない、またはすでに削除されている。
    """


@dataclass(frozen=True)
class Deleted:
    memory_id: str
    character: str
    relation_label: str
    relation_level: int
    promise_voided: str | None
    # Turns whose original words were cleared (the gateway drops the recent dialogue held in memory)
    # 発話の原文を消したターン（ゲートウェイはメモリ上の最近の会話を捨てる）
    turn_ids: tuple[str, ...]
    # When a forget event was written, this playthrough's new lastSeq
    # forget イベントを書いたときの、このプレイの新しい lastSeq
    seq: int | None = None

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
    """Delete one memory inside the caller's transaction (see the module docstring). Missing or already deleted →
    NotFound.

    呼び出し側のトランザクション内で記憶を 1 件削除する（モジュールの説明を参照）。ない、または削除済み → NotFound。
    """
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
    """The forget event that voids a promise: one task row (done) + one event; update world_state and lastSeq,
    NOTIFY. Returns the new seq.

    約束を無効にする forget イベント：タスク行 1 件（done）+ イベント 1 件。world_state と lastSeq を更新し、
    NOTIFY する。新しい seq を返す。
    """
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
            # A neutral line: never 「覚えていない」 or 「忘れた」 (UX review: deletion must leave no trace in the
            # story); this character's situation brief does not include it
            # 中立的な一文：「覚えていない」「忘れた」とは書かない（UX レビュー：削除が物語に痕跡を残してはならない）。
            # この登場人物の状況説明には含めない
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
    """L2: delete all of this playthrough's rows (other tables cascade by foreign key). Returns whether anything was
    deleted.

    L2：このプレイの行をすべて削除する（ほかのテーブルは外部キーでカスケード）。削除できたかどうかを返す。
    """
    res = await c.execute(
        delete(playthroughs).where(playthroughs.c.playthrough_id == pid).returning(playthroughs.c.playthrough_id)
    )
    return res.first() is not None
