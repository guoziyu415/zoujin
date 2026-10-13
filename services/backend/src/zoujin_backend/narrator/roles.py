"""Role openings (B-19; ux-design 5.1, S-002, S-048): who speaks first, how characters address the player, and the
small two-way mutual aid at the start.

- The opening mutual aid is the entries of a character's `mutualAid` in the world model whose `opening` equals this
  role (written by the data side).
- The one who speaks first = the character of the opening aid entry "you for them" (`fromYou`): 老爺 for
  旅人, セリヌンティウス for 石屋の弟子, メロス for 村の牧童. At the start the game's `arrival` carries them (the same
  mechanism as landing after an act transition, api-contract 3.11): after the frontend shows the first 地の文 line
  (the role's `summary`) it sends `act_landed`, and the character speaks first.
- Forms of address follow the table in ux-design 5.1; the world model's `Role` doesn't have this field yet, so it lives
  here for now [provisional: read it from the world model once the data side adds it to the contract].

Only reads the world model; never touches the original text.

役柄の始まり（B-19。ux-design 5.1、S-002、S-048）：最初に話しかける登場人物、登場人物によるプレイヤーの呼び方、
開始時の双方向の小さな助け合い。

- 開始時の助け合いは、世界モデルの登場人物の `mutualAid` のうち、`opening` がこの役柄に等しいもの（データ側が書く）。
- 最初に話しかけるのは、開始時の助け合いのうち「あなたが相手に」（`fromYou`）の登場人物：旅人なら老爺、
  石屋の弟子ならセリヌンティウス、村の牧童ならメロス。開始時にこのゲームの `arrival` がその人物を持つ
  （幕切り替えの着地と同じ仕組み、api-contract 3.11）：フロントエンドが最初の地の文（役柄の `summary`）を
  表示したあと `act_landed` を送り、登場人物が先に話す。
- 呼び方は ux-design 5.1 の表に従う。世界モデルの `Role` にはまだこの項目がないので、ひとまずここに置く
  〔暫定。データ側が契約に加えたら世界モデルから読むように変える〕。

世界モデルを読むだけで、原文には触れない。
"""

from __future__ import annotations

from typing import Any

from zoujin_backend.world import Book
from zoujin_worldsim import SimState

Json = Any

ADDRESS: dict[str, str] = {
    "role.traveler": "旅の方",
    "role.apprentice": "おまえ／弟子よ",
    "role.shepherd-boy": "坊主",
}


def opening_aids(book: Book, role: str, character: str | None = None) -> list[tuple[str, Json]]:
    """(character, aid) pairs of this role's small two-way opening aid, in world model order. If character is given,
    only theirs.

    （登場人物, 助け合い）：この役柄の開始時の双方向の小さな助け合い。世界モデルの順。
    character を渡せばその人物の分だけ。
    """
    return [
        (c["id"], a)
        for c in book.world["characters"]
        if character is None or c["id"] == character
        for a in c.get("mutualAid", [])
        if a.get("opening") == role
    ]


def opener(book: Book, role: str) -> str | None:
    """The character who speaks first at the start: the one in the opening aid's "you for them" entry; if
    there is none, nobody speaks first (the player talks first).

    開始時に最初に話しかける登場人物：開始時の助け合いのうち「あなたが相手に」の人物。いなければ誰も先に話さない
    （プレイヤーが先に話す）。
    """
    return next((c for c, a in opening_aids(book, role) if a.get("direction") == "fromYou"), None)


def start_arrival(book: Book, role: str) -> Json | None:
    """The opening `playthroughs.arrival`: {actId, line, opener}. Nobody speaks first → None.

    開始時の `playthroughs.arrival`：{actId, line, opener}。最初に話しかける人物がいなければ None。
    """
    who = opener(book, role)
    r = book.roles.get(role)
    if who is None or r is None or who not in book.characters:
        return None
    act = r.get("startAct") or book.world["acts"][0]["id"]
    return {"actId": act, "line": r.get("summary") or "", "opener": who}


def act_at(book: Book, t: int) -> str | None:
    """Which act time t falls in (by each act's `start.t`).

    時刻 t がどの幕に入るか（各幕の `start.t` で判断）。
    """
    cur = None
    for a in sorted(book.world["acts"], key=lambda a: a.get("order", 0)):
        if a.get("start", {}).get("t", 0) <= t:
            cur = a["id"]
    return cur


def done(state: SimState, aid: Json) -> bool:
    """This aid has been done: all its effects (`set`) hold in this game. One without effects can't be told, so it
    counts as not done.

    この助け合いはもう済んだ：その効果（`set`）がこのゲームですべて成り立っている。効果のないものは判断できないので、
    済んでいないとみなす。
    """
    sets = [e for e in aid.get("effects", []) if e.get("op") == "set"]
    return bool(sets) and all(state["vars"].get(e["var"]) == e["value"] for e in sets)


def brief_lines(book: Book, state: SimState, character: str) -> list[str]:
    """The lines under 「# 話し相手」 in the Live situation brief: how to address the other person, and in the opening
    act the small aid the other person can do for you (from the character's point of view).

    The "they for you" entry isn't given to the character: it is something that only happens later (e.g.
    entrusting the workshop before being summoned late at night), so saying it would be a spoiler (S-092); the
    narrator judges it from the world model's `mutualAid`.

    Live の状況説明「# 話し相手」の下に入る行：相手の呼び方と、開始の幕で相手があなたにしてくれる小さな助け合い
    （登場人物の視点）。

    「相手があなたに」の項目は登場人物に渡さない：それはあとで起きること（例：深夜に召される前に工房を託す）で、
    口にすればネタバレになる（S-092）。ナレーターが世界モデルの `mutualAid` を見て判断する。
    """
    role, t = state["role"], state["t"]
    out: list[str] = []
    if role in ADDRESS:
        out.append(f"呼び方：{ADDRESS[role]}")
    start = (book.roles.get(role) or {}).get("startAct")
    # Before the opening events are written (t is still 0), treat it as the opening act.
    # 開始のイベントを書く前（t がまだ 0）は開始の幕とみなす。
    now = act_at(book, t)
    if start is not None and now is not None and now != start:
        return out
    for _, a in opening_aids(book, role, character):
        if a.get("direction") == "fromYou" and not done(state, a):
            out.append(f"相手があなたにしてくれそうなこと：{a['text']}")
    return out
