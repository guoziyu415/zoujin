"""书房的只读投影：目录来自明确开放的版本；进度和结局只来自当前账号的持久化记录。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from zoujin_backend.db.events import recorded_at
from zoujin_backend.db.tables import endings, playthroughs
from zoujin_backend.gateway.core import Gateway
from zoujin_backend.world import Book

Json = Any


def book_summary(book: Book, available: bool) -> Json:
    meta = book.world["book"]
    return {
        "bookId": book.book_id,
        "worldModelVersion": book.version,
        "title": meta["title"],
        "author": meta["author"],
        "year": meta["year"],
        "description": "本を開いて、物語の世界へ。",
        "availability": "available" if available else "unavailable",
        "manifestUrl": f"/v1/books/{book.book_id}/manifest",
    }


def catalog(gw: Gateway) -> Json:
    return {
        "books": [
            book_summary(book, bool((m := gw.manifests.get(bid)) is not None and m.doc["roles"]))
            for bid, book in gw.library.available.items()
        ]
    }


async def history(gw: Gateway, c: AsyncConnection, user_id: str) -> Json:
    # 同一个查询固定 owner + status，再左连该局唯一的结局。不接受客户端传 owner，也不从 localStorage 补历史。
    rows = (
        await c.execute(
            select(playthroughs, endings.c.ending_id, endings.c.body)
            .outerjoin(endings, endings.c.playthrough_id == playthroughs.c.playthrough_id)
            .where(playthroughs.c.user_ref == user_id, playthroughs.c.status.in_(("active", "ended")))
            .order_by(playthroughs.c.ended_at.desc().nulls_last(), playthroughs.c.playthrough_id.desc())
        )
    ).mappings()
    active = None
    ready: list[Json] = []
    pending: list[Json] = []
    for row in rows:
        bid, version = row["book_id"], row["world_model_version"]
        if row["status"] == "active":
            pt = await gw.pt(c, row["playthrough_id"])
            if pt is not None:
                active = {**await gw.active_ref(c, pt), "bookId": bid, "worldModelVersion": version}
            continue
        # 未完成、放弃或缺结束时间的记录不能伪装成完成结局。
        if row["ended_at"] is None:
            continue
        book = gw.library.by_version.get(version)
        if book is not None and book.book_id != bid:
            continue  # 损坏的跨书版本映射不能投影成另一本书
        item = {
            "playthroughId": row["playthrough_id"],
            "bookId": bid,
            "worldModelVersion": version,
            "bookTitle": book.world["book"]["title"] if book is not None else bid,
            "roleId": row["role_id"],
            "roleName": book.roles[row["role_id"]]["name"] if book is not None else row["role_id"],
            "endedAt": recorded_at(row["ended_at"]),
        }
        body = row["body"]
        if body is None:
            pending.append(item)
        elif (
            body.get("worldModelVersion") == version
            and body.get("playthroughId") == row["playthrough_id"]
            and body.get("endingId") == row["ending_id"]
            and body.get("trigger") in ("deadline", "story-closed")
        ):
            ready.append({**item, "endingId": row["ending_id"], **{k: body["card"][k] for k in ("title", "subtitle")}})
    return {"activePlaythrough": active, "endings": ready, "pendingEndings": pending}
