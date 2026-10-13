"""The world state and characters in requests to the text model (B-2; backend-design 2.3, 2.4).

- `state_view`: the current world state, compact and deterministic (the same situation gives the same result every
  time, so replay keys match). Promise and improvised-fact IDs are assigned randomly at commit, so the request uses
  aliases sorted by content (`prm#1`, `rf#1`); aliases in the model output are mapped back to real IDs with the same
  `View`.
- `persona`, `situation`: section 2 of 2.3 (the persona trimmed to the current moment) and the minimal situation notes
  (time, place, who is present, the facts known right now; characters who don't know the day-name fact get only the
  time band; whether beats lived through in these three days were today, yesterday or the day before) used for text-mode
  character replies (`reply`). The full situation notes, memories and smoothing-over hints are later cards.

Only things from the world model and the state are here, never the player's own words (those are only in the request's
`turn`).

テキストモデルへのリクエストに入れる世界状態と登場人物（B-2。backend-design 2.3、2.4）。

- `state_view`：現在の世界状態。簡潔で決定的（同じ局面なら毎回同じになり、リプレイのキーが一致する）。約束と即興設定の
  ID はコミット時にランダムに割り当てるので、リクエストでは内容順に並べた別名（`prm#1`、`rf#1`）に置き換える。
  モデル出力の別名は同じ `View` で本当の ID に戻す。
- `persona`、`situation`：テキストモードの登場人物の返答（`reply`）に使う、2.3 第 2 段
  （現在に合わせて切り詰めた人物設定）と最小限の状況説明（時刻、場所、その場にいる人、いま知っている事実。
  日名の事実を知らない登場人物には時間帯だけを渡す。この三日間に自分で経験したビートが今日か昨日かおとといか）。
  完全な状況説明、記憶、取り繕いのヒントは後のカード。

ここには世界モデルと状態にあるものだけを入れ、プレイヤーの発話そのものは入れない
（発話はリクエストの `turn` にだけある）。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from zoujin_backend.narrator.rules import absent, index
from zoujin_backend.world import Book
from zoujin_worldsim import OCCURRED, SimState, activity, flat, knows, lived

Json = Any


@dataclass(frozen=True)
class View:
    doc: Json
    out: Mapping[str, str]  # real ID → alias / 本当の ID → 別名
    back: Mapping[str, str]  # alias → real ID / 別名 → 本当の ID

    def alias(self, x: Any) -> Any:
        return self.out.get(x, x) if isinstance(x, str) else x

    def real(self, x: Any) -> Any:
        return self.back.get(x, x) if isinstance(x, str) else x


def _content(x: Mapping[str, Any], drop: tuple[str, ...]) -> str:
    return json.dumps({k: v for k, v in x.items() if k not in drop}, sort_keys=True, ensure_ascii=False)


def aliases(state: SimState) -> dict[str, str]:
    """Real IDs of promises and improvised facts → aliases. Sorted by content, not by ID (IDs contain a time and a
    random number).

    約束と即興設定の本当の ID → 別名。ID ではなく内容で並べる（ID には時刻と乱数が入る）。
    """
    proms = sorted(state["promises"].values(), key=lambda p: _content(p, ("promiseId", "madeBy", "resolvedBy")))
    facts = sorted(state["runFacts"].values(), key=lambda f: (f["character"], f["statement"]))
    out = {p["promiseId"]: f"prm#{i}" for i, p in enumerate(proms, 1)}
    out |= {f["factId"]: f"rf#{i}" for i, f in enumerate(facts, 1)}
    return out


def state_view(book: Book, state: SimState) -> View:
    out = aliases(state)

    def a(x: str) -> str:
        return out.get(x, x)

    people: dict[str, Json] = {}
    variables = dict(state["vars"])
    for c in sorted(state["locations"]):
        people[c] = {"place": state["locations"][c], "activity": activity(book.world, state, c)}
        # relocate updates locations. Keep worlds' old location variables in step so the model is never given two
        # places at once; this only builds the request projection: it doesn't change the stored state or invent
        # variables for other books.
        # relocate は locations を更新する。世界に残る古い位置変数と合わせ、
        # モデルに 2 つの場所を同時に渡さないようにする。
        # ここではリクエスト用の投影を作るだけで、保存された状態は変えず、ほかの本に変数を勝手に足すこともしない。
        if c.startswith("char."):
            alias = f"var.{c.removeprefix('char.')}.location"
            if alias in variables:
                variables[alias] = state["locations"][c]
    promises = [
        {"ref": a(p["promiseId"]), **{k: p[k] for k in ("from", "to", "text", "status", "due", "template") if k in p}}
        for p in sorted(state["promises"].values(), key=lambda p: a(p["promiseId"]))
    ]
    run_facts = [
        {"ref": a(f["factId"]), "character": f["character"], "statement": f["statement"]}
        for f in sorted(state["runFacts"].values(), key=lambda f: a(f["factId"]))
    ]
    doc = {
        "t": state["t"],
        "time": book.label(state["t"]),
        "act": book.act_of(state["vars"]),
        "role": state["role"],
        "vars": dict(sorted(variables.items())),
        "beats": dict(sorted(state["beats"].items())),
        "beatTimes": dict(sorted(state["times"].items())),
        "beatChanges": {b: dict(o) for b, o in sorted(state["overrides"].items())},
        "people": people,
        "holdings": dict(sorted(state["holdings"].items())),
        "learned": {w: [a(f) for f in fs] for w, fs in sorted(state["knowledge"].items())},
        "promises": promises,
        "runFacts": run_facts,
    }
    return View(doc, out, {v: k for k, v in out.items()})


# —— Text-mode character replies (2.3 sections 2 and 4 + minimal situation notes) ——
# —— テキストモードの登場人物の返答（2.3 第 2・4 段 + 最小限の状況説明） ——


def _live(state: SimState, cur: Mapping[str, Any], x: Mapping[str, Any], book: Book) -> bool:
    """Whether a persona entry still holds right now: the `since` beat has happened (or is pre), the `until` beat hasn't
    happened yet, and `when` holds.

    人物設定の 1 項目がいまも有効か：`since` のビートが起きた（または pre）、`until` のビートがまだ起きていない、
    `when` が成り立つ。
    """
    beats = state["beats"]
    since = x.get("since")
    if since not in (None, "pre") and beats.get(since) not in OCCURRED:
        return False
    if x.get("until") is not None and beats.get(x["until"]) in OCCURRED:
        return False
    return not x.get("when") or index(book.world).sim.holds(x["when"], cur)


def persona(book: Book, state: SimState, who: str) -> Json:
    c = book.characters[who]
    cur = flat(state)

    def keep(xs: list[Json]) -> list[str]:
        return [x["text"] for x in xs if _live(state, cur, x, book)]

    speech = c.get("speech", {})
    out: Json = {
        "id": who,
        "name": c["name"],
        "summary": c.get("summary", ""),
        "traits": keep(c.get("traits", [])),
        "goals": keep(c.get("goals", [])),
    }
    out["speech"] = {k: speech[k] for k in ("firstPerson", "register") if k in speech} | {
        "sampleLines": [x["quote"] for x in speech.get("sampleLines", []) if _live(state, cur, x, book)]
    }
    return out


def situation(book: Book, state: SimState, who: str, view: View) -> Json:
    """Time, place, who is present (not counting the absent), the facts this character knows right now (fact IDs and
    improvised-fact aliases), and the recent beats they lived through.

    Time: when the day names carry plot (`clock.labels.daysKnownBy`) and this character doesn't know that fact, give
    only the time band (S-086: 「約束の日」 and 「三日目」 count from the day of the promise, so a character who doesn't
    know about the promise saying them would be knowing more than they should).

    Recent beats (`recent`, S-092): beats the character lived through (worldsim's `lived()`: happened, and either they
    took part, or it has no participating characters and lands in the same scene they were in at the time, e.g. the
    heavy rain; being at the beat's place without taking part doesn't count), sorted by time and beat order, with the
    variant ID when it played out as a variant, each with the wording UX decided (「今朝」「昨夜」「おととい」...; in
    S-068 a character called that morning's events yesterday, and spoke of tomorrow's wedding after it was over).
    Nothing earlier is given.

    時刻、場所、その場にいる人（いない者は除く）、この登場人物がいま知っている事実（事実 ID と即興設定の別名）、
    自分で経験した最近のビート。

    時刻：日名が筋を含み（`clock.labels.daysKnownBy`）、この登場人物がその事実を知らないときは時間帯だけを渡す
    （S-086：「約束の日」「三日目」は約束の日から数えるので、約束を知らない登場人物が口にすれば知りすぎになる）。

    最近のビート（`recent`、S-092）：自分で経験したビート（worldsim の `lived()`：起きたもので、本人が参加したもの、
    または参加する登場人物がおらず、本人がそのときいた場面と同じ場面で起きたもの、たとえば大雨。ビートの場所にいても
    参加していなければ数えない）を、起きた時刻とビートの順に並べ、変種で演じられたものは変種 ID を付け、それぞれに
    UX が決めた言い方（「今朝」「昨夜」「おととい」……。S-068 では登場人物がその日の朝のことを昨日と言い、
    婚礼が済んだのに明日の婚礼と言った）を付ける。それより前のものは渡さない。
    """
    ix = index(book.world)
    place = state["locations"].get(who, state["vars"]["var.player.location"])
    here = [c for c, p in sorted(state["locations"].items()) if p == place and c != who and not absent(ix, state, c)]
    known = [f["id"] for f in book.world["facts"] if knows(book.world, state, who, f["id"])]
    known += [view.alias(r) for r in sorted(state["runFacts"], key=view.alias) if knows(book.world, state, who, r)]
    by = book.labels.days_known_by
    beats = {b["id"]: b for b in book.world["beats"]}
    recent = [
        {"beat": b, "day": day} | ({"variant": state["variants"][b]} if b in state["variants"] else {})
        for b, t in sorted(state["times"].items(), key=lambda x: (x[1], beats.get(x[0], {}).get("order", 0)))
        if lived(book.world, state, who, b) and (day := book.labels.ago(t, state["t"])) is not None
    ]
    return {
        "t": state["t"],
        "time": book.labels.band(state["t"]) if by and by not in known else book.label(state["t"]),
        "place": place,
        "present": here,
        "knows": known,
        "recent": recent,
    }


def player_card(book: Book, state: SimState, who: str) -> Json:
    """2.3 section 4: who the player is (the role name, and whether this character knows that role).

    2.3 第 4 段：プレイヤーが誰か（役柄名と、この登場人物がその役柄を知っているか）。
    """
    role = book.roles[state["role"]]
    return {"role": role["id"], "name": role["name"], "knownToYou": who in role.get("knownCharacters", [])}
