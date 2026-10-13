"""記憶帳 (the memory book; api-contract 2.7, ux-design 10.1, B-13): lists only the characters the player has met,
with four columns each (promises, what they did for you, what you did, memories).

- Met = replaying the events, the character was at some moment in the same place as the player (one you can talk to,
  not a crowd), or already has promises or memories involving them.
- Promises: the ones in the current state that involve the player; `voided` ones are included too (the frontend
  doesn't show them).
- してくれたこと / あなたがしたこと: among committed events, what the character did for the player (actor = them,
  beneficiary = player) and what the player did for the character (actor = player, beneficiary = them); the sentence
  is the event's summary with the player's role name replaced by 「あなた」.
- Memories: the ones not deleted, in time order. The relationship is computed from the memories not deleted
  (`narrator/memory.py`).

記憶帳（api-contract 2.7、ux-design 10.1、B-13）：プレイヤーが会ったことのある登場人物だけを並べ、各人 4 欄
（約束、してくれたこと、あなたがしたこと、記憶）。

- 会った = イベントをリプレイして、その登場人物がある時点でプレイヤーと同じ場所にいた（会話でき、群衆ではない）、
  あるいはすでにその人との約束や記憶がある。
- 約束：現在の状態でプレイヤーに関わるもの。`voided` もそのまま渡す（フロントエンドは表示しない）。
- してくれたこと / あなたがしたこと：commit 済みのイベントのうち、その人がプレイヤーのためにしたこと（actor = その人、
  beneficiary = player）と、プレイヤーがその人のためにしたこと（actor = player、beneficiary = その人）。文はイベントの
  summary で、役名を「あなた」に置き換える。
- 記憶：削除されていないものを時刻順に。関係は削除されていない記憶から計算する（`narrator/memory.py`）。
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
