"""記憶帳（api-contract 2.7，ux-design 10.1，B-13）：只列玩家见过的人物，每人四栏（约定、为你做的、你做的、记忆）。

- 见过 = 按事件重放，这个人物在某一刻和玩家在同一个地点（能对话、不是一群人的），或者已经有他的约定、记忆。
- 约定：现在的状态里和玩家有关的，`voided` 照给（前端不显示）。
- してくれたこと / あなたがしたこと：提交了的事件里，他为玩家做的（actor = 他、beneficiary = player）、玩家为他做的
  （actor = player、beneficiary = 他）；句子是事件的 summary，身份名换成「あなた」。
- 记忆：没删的，按时间排。关系按没删的记忆算（`narrator/memory.py`）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection
from zoujin_worldsim import apply, initial_state

from zoujin_backend.db import store
from zoujin_backend.narrator import memory
from zoujin_backend.projection import as_you, committed
from zoujin_backend.world import Book

Json = Any


def _direction(p: Json) -> tuple[str, str] | None:
    if p["from"] == "player":
        return str(p["to"]), "playerToCharacter"
    if p["to"] == "player":
        return str(p["from"]), "characterToPlayer"
    return None


async def view(c: AsyncConnection, book: Book, pid: str, role_id: str) -> Json:
    log_ = await store.event_log(c, pid, book.version)
    state = initial_state(book.world, role_id)
    seen: dict[str, None] = {}

    def look(st: Any) -> None:
        here = st["vars"]["var.player.location"]
        for ch, place in st["locations"].items():
            if place == here and memory.talkable(book, ch):
                seen.setdefault(ch, None)

    look(state)
    did: dict[str, list[Json]] = {}
    you: dict[str, list[Json]] = {}
    for ev in log_:
        state = apply(book.world, state, ev)
        look(state)
        if not committed(ev):
            continue
        b = ev.get("beneficiary")
        if b == "player" and memory.talkable(book, ev["actor"]):
            did.setdefault(ev["actor"], []).append(ev)
        elif ev["actor"] == "player" and b and memory.talkable(book, b):
            you.setdefault(b, []).append(ev)
    promises: dict[str, list[Json]] = {}
    for promise_id, p in (state.get("promises") or {}).items():
        d = _direction(p)
        if d is None or not memory.talkable(book, d[0]):
            continue
        promises.setdefault(d[0], []).append(
            {
                "promiseId": promise_id,
                "text": p["text"],
                "direction": d[1],
                "status": p["status"],
                "eventId": p["madeBy"],
            }
        )
    mems: dict[str, list[Json]] = {}
    for row in await memory.alive(c, pid):
        mems.setdefault(row["character"], []).append(
            {
                "memoryId": row["memory_id"],
                "kind": row["kind"],
                "text": row["text"],
                "t": row["t"],
                "tLabel": book.label(row["t"]),
                "via": row["via"] or "witnessed",
                "promiseId": row["promise_id"],
            }
        )
    for ch in (*promises, *mems):
        seen.setdefault(ch, None)

    def line(ev: Json) -> Json:
        return {"eventId": ev["eventId"], "text": as_you(book, role_id, str(ev["summary"]))}

    out = []
    for ch in seen:
        label, level = await memory.relation_of(c, book, pid, role_id, ch)
        out.append(
            {
                "character": ch,
                "relationLabel": label,
                "relationLevel": level,
                "promises": promises.get(ch, []),
                "didForYou": [line(e) for e in did.get(ch, [])],
                "youDid": [line(e) for e in you.get(ch, [])],
                "memories": mems.get(ch, []),
            }
        )
    return {"characters": out}
