"""Read-only projection for the study: the catalog comes from explicitly opened versions; progress and endings come
only from the current account's persisted records.

書斎の読み取り専用の投影：目録は明示的に公開されたバージョンから、進行状況とエンディングは現在のアカウントの
永続化された記録だけから作る。
"""

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
    # One query pins owner + status, then left-joins the game's single ending. The client never passes the owner, and
    # history is never filled in from localStorage.
    # 1 つのクエリで owner と status を固定し、そのゲーム唯一のエンディングを左結合する。owner をクライアントから
    # 受け取ることはなく、localStorage から履歴を補うこともない。
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
        # Unfinished or abandoned records, or ones missing an end time, must not pose as finished endings.
        # 未完了・放棄、または終了時刻のない記録を完了したエンディングに見せかけてはならない。
        if row["ended_at"] is None:
            continue
        book = gw.library.by_version.get(version)
        if book is not None and book.book_id != bid:
            # A broken cross-book version mapping must not project as another book.
            # 本をまたいだ壊れたバージョン対応を別の本として投影してはならない。
            continue
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
