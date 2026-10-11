"""身份的开局（B-19；ux-design 5.1，S-002、S-048）：先开口的人物、人物怎么称呼玩家、开局的双向小互助。

- 开局的互助是世界模型里人物的 `mutualAid` 里 `opening` 等于这个身份的那几条（数据写的）。
- 先开口的人 = 开局互助里「你为他」（`fromYou`）那一条的人物：旅人是老爺、石屋の弟子是セリヌンティウス、村の牧童是
  メロス。开局时这一局的 `arrival` 带上他（和幕切换落地同一套，api-contract 3.11）：前端显示第一行地の文
  （身份的 `summary`）以后发 `act_landed`，人物先开口。
- 称呼按 ux-design 5.1 的表，世界模型的 `Role` 还没有这一项，先放这里〔暂定，数据把它加进契约以后改读世界模型〕。

只读世界模型，不碰原话。
"""

from __future__ import annotations

from typing import Any

from zoujin_backend.world import Book

Json = Any

ADDRESS: dict[str, str] = {
    "role.traveler": "旅の方",
    "role.apprentice": "おまえ／弟子よ",
    "role.shepherd-boy": "坊主",
}


def opening_aids(book: Book, role: str, character: str | None = None) -> list[tuple[str, Json]]:
    """(人物, 互助) 这个身份开局的双向小互助，按世界模型里的顺序。character 给了就只要他的。"""
    return [
        (c["id"], a)
        for c in book.world["characters"]
        if character is None or c["id"] == character
        for a in c.get("mutualAid", [])
        if a.get("opening") == role
    ]


def opener(book: Book, role: str) -> str | None:
    """开局先开口的人物：开局互助里「你为他」的那个人；没有就没人先开口（玩家先说）。"""
    return next((c for c, a in opening_aids(book, role) if a.get("direction") == "fromYou"), None)


def start_arrival(book: Book, role: str) -> Json | None:
    """开局的 `playthroughs.arrival`：{actId, line, opener}。没有先开口的人 → None。"""
    who = opener(book, role)
    r = book.roles.get(role)
    if who is None or r is None or who not in book.characters:
        return None
    act = r.get("startAct") or book.world["acts"][0]["id"]
    return {"actId": act, "line": r.get("summary") or "", "opener": who}


def act_at(book: Book, t: int) -> str | None:
    """时刻 t 落在哪一幕（按各幕的 `start.t`）。"""
    cur = None
    for a in sorted(book.world["acts"], key=lambda a: a.get("order", 0)):
        if a.get("start", {}).get("t", 0) <= t:
            cur = a["id"]
    return cur


def brief_lines(book: Book, role: str, character: str, t: int) -> list[str]:
    """Live 局势说明「# 話し相手」下面的几行：怎么称呼对方；开局那一幕里对方能为你做的小互助（人物视角）。

    「他为你」的那条不给人物：那是之后才会发生的事（例：深夜被召之前托付工房），说出来就是剧透（S-092）；
    叙事者看世界模型里的 `mutualAid` 判。"""
    out: list[str] = []
    if role in ADDRESS:
        out.append(f"呼び方：{ADDRESS[role]}")
    start = (book.roles.get(role) or {}).get("startAct")
    now = act_at(book, t)  # 开局事件写之前（t 还是 0）当作开局那一幕
    if start is not None and now is not None and now != start:
        return out
    for _, a in opening_aids(book, role, character):
        if a.get("direction") == "fromYou":
            out.append(f"相手があなたにしてくれそうなこと：{a['text']}")
    return out
