"""给文本模型的请求里的世界状态和人物（B-2；backend-design 2.3、2.4）。

- `state_view`：此刻的世界状态，紧凑、确定（同样的局面每次一样，回放的键才对得上）。约定和即兴设定的 ID 是提交时随机
  分配的，请求里换成按内容排序的别名（`prm#1`、`rf#1`）；模型输出里的别名按同一个 `View` 换回真 ID。
- `persona`、`situation`：文字模式人物回答（`reply`）用的 2.3 第 2 段（按此刻裁剪的人设）和最小的局势说明（时刻、地点、
  在场的人、此刻知道的事实；不知道日名那条事实的人物只给时段；这三天里亲历的节拍是今天、昨天还是前天）。完整的局势说明、
  记忆和圆回提示是后续卡。

这里只有世界模型和状态里的东西，没有玩家的原话（原话只在请求的 `turn` 里）。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from zoujin_backend.narrator.rules import absent, index
from zoujin_backend.world import Book
from zoujin_worldsim import OCCURRED, SimState, activity, flat, knows

Json = Any


@dataclass(frozen=True)
class View:
    doc: Json
    out: Mapping[str, str]  # 真 ID → 别名
    back: Mapping[str, str]  # 别名 → 真 ID

    def alias(self, x: Any) -> Any:
        return self.out.get(x, x) if isinstance(x, str) else x

    def real(self, x: Any) -> Any:
        return self.back.get(x, x) if isinstance(x, str) else x


def _content(x: Mapping[str, Any], drop: tuple[str, ...]) -> str:
    return json.dumps({k: v for k, v in x.items() if k not in drop}, sort_keys=True, ensure_ascii=False)


def aliases(state: SimState) -> dict[str, str]:
    """约定和即兴设定的真 ID → 别名。按内容排序，不按 ID（ID 带时间和随机数）。"""
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
    for c in sorted(state["locations"]):
        people[c] = {"place": state["locations"][c], "activity": activity(book.world, state, c)}
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
        "vars": dict(sorted(state["vars"].items())),
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


# —— 文字模式的人物回答（2.3 第 2、4 段 + 最小的局势说明） ——


def _live(state: SimState, cur: Mapping[str, Any], x: Mapping[str, Any], book: Book) -> bool:
    """人设的一条此刻还算不算：`since` 的节拍发生了（或 pre）、`until` 的节拍还没发生、`when` 成立。"""
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
    """时刻、地点、在场的人（不含不在场的）、他此刻知道的事实（事实 ID 和即兴设定的别名）、他参与的最近的节拍。

    时刻：日名带着情节（`clock.labels.daysKnownBy`）而这个人物不知道那条事实时，只给时段（S-086：「約束の日」「三日目」
    是从约定那天数的，不知道约定的人物说出来就是知情越界）。

    最近的节拍（`recent`，S-092）：他参与的、已发生的节拍（不是他经历的全部；「亲历」的规则等数据在 worldsim 加
    `lived`），按发生时刻和节拍顺序排，按变体演了的带变体 ID，各带 UX 定的说法（「今朝」「昨夜」
    「おととい」……；S-068 里人物把当天早上的事说成昨天，婚礼办完了还说明天的婚礼）。再早的不给。
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
        if state["beats"].get(b) in OCCURRED
        and who in beats.get(b, {}).get("participants", [])
        and (day := book.labels.ago(t, state["t"])) is not None
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
    """2.3 第 4 段：玩家是谁（身份名、这个人物认不认识这个身份）。"""
    role = book.roles[state["role"]]
    return {"role": role["id"], "name": role["name"], "knownToYou": who in role.get("knownCharacters", [])}
