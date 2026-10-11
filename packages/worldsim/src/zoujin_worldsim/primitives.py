"""叙事者的确定性规则要用、推演里原来没有的几个原语（B-2 卡：后端提，数据加，后端评审；spoilers 是 B-12 评审时加的）。

- knows()：R4（契约 2.1 防剧透规则）。人物 C 此刻知道的 = `C.knows` 里 `since` 已发生的（或 `pre`）+ 这一局 `learn`
  学到的（含别人的即兴设定）+ C 自己的即兴设定；（1.7）玩家 = 身份的 `initialKnowledge` + 这一局学到的（人物告诉的，
  和节拍发生时玩家在场、settle 写进系统事件的 public 事实）。世界事实的 `trueFrom` 这一局没发生，谁都不算知道
  （契约 2.3，1.4）。和评测的 evals/s2_check.py（S-2 标注用的判法）一致。
- travel_minutes()：R3 的路程（契约 2.2 `adjacent`，api-contract 3.7、3.8）。按 `places.adjacent` 的步行分钟取最短路；
  同一场景里的两个地点之间按 `pacing.sceneWalkMinutes`（S-038：场景内走动 0 分）。只量玩家的移动和排程以外的
  `relocate`；按排程走的人物看排程（backend-design 2.4）。
- spoilers()：人物说的话里有没有他此刻不该知道的事实（`Fact.spoilerTerms` 出现在话里，而他不 `knows` 这条事实）。
  叙事者 R4 查即兴设定、网关的输出侧监控（B-12，backend-design 2.11）、评测入口的 `monitor.spoilers` 共用这一个；
  和评测 E2 的 `not_mention_fact` 同一个口径（E2 只看出题时指定的那一条，自检保证人物在检查点不知道它）。
- lived()（1.12 补）：人物亲历了哪个已发生的节拍，叙事者给人物的「最近的节拍」用（S-092）。和 sees()（1.12）同一条
  场景规则，但人物只算参与的节拍和没有参与人物、落在同一场景的节拍（天气、天灾），不算「人在节拍的地点」：人物知道
  什么按 `Character.knows`（原作的在场已写好）和 `learn`，不按在场自动学（契约 2.1 ②），在场却不参与的节拍给了他，
  他就会说出不知道的事。节拍那一刻他在哪用 place_at()：和 activity() 同一套重放，是「按节拍该在哪」。
- activity()：人物此刻在做什么（契约 2.4 的 Activity，1.1）。R7（对象不在场、`absent` 的人物不能对话）和快照的
  `characters[].activity` 用（api-contract 2.3）。只算世界模型给的那一部分，叙事者按对话再推（backend-design 2.7）。

不在这里的：`crossing`（过河的分钟，M3 和归途的停留点一起做）。归途的四个地点（川、峠、泉、野の道）各是一个场景
（S-081：停留点之间是跑的路段，「ひとりで先へ行く」要花路上的时间），所以按 `adjacent` 的步行分钟算，不是场景内的 0 分。
切片没有归途。
"""

from __future__ import annotations

import heapq
from typing import Any

from .incremental import SimState
from .sim import OCCURRED, World, role_of
from .visibility import same_scene


def knows(world: World, state: SimState, who: str, fact: str) -> bool:
    """who（人物 ID 或 "player"）此刻知不知道 fact（事实 ID，或即兴设定的 rf_ ID）。"""
    beats = state["beats"]
    f = next((x for x in world["facts"] if x["id"] == fact), None)
    if f is not None and f["trueFrom"] != "pre" and beats.get(f["trueFrom"]) not in OCCURRED:
        return False
    if fact in state["knowledge"].get(who, []):
        return True
    if who == "player":
        return fact in role_of(world, state["role"]).get("initialKnowledge", [])
    rf = state["runFacts"].get(fact)
    if rf is not None and rf.get("character") == who:
        return True
    c = next((x for x in world["characters"] if x["id"] == who), None)
    return c is not None and any(
        k["fact"] == fact and (k["since"] == "pre" or beats.get(k["since"]) in OCCURRED) for k in c.get("knows", [])
    )


def spoilers(world: World, state: SimState, who: str, text: str, said: str = "") -> dict[str, list[str]]:
    """who 说的 text 里，他此刻不知道的事实的剧透词：{事实 ID: 出现的词}，按世界模型里事实的顺序，没有就是空的。

    「不知道」就是 `not knows()`，已经含「这条事实这一局还没成立」（契约 2.3，1.4）。比对是原样的子串，不做假名、
    全角的归一，和 E2、S-2 的 `s2_check.py` 一样。said = 同一轮玩家说的话：玩家自己说出的词，人物接着说不算（E2 出题
    也是这个规则：玩家的问题里不能有剧透词）。"""
    hits: dict[str, list[str]] = {}
    for f in world["facts"]:
        terms = [t for t in f.get("spoilerTerms") or () if t in text and t not in said]
        if terms and not knows(world, state, who, f["id"]):
            hits[f["id"]] = terms
    return hits


def travel_minutes(world: World, src: str, dst: str) -> int | None:
    """从 src 走到 dst 最少几分钟。同一地点 0；走不到（或地点不存在）None。"""
    places = {p["id"]: p for p in world["places"]}
    if src not in places or dst not in places:
        return None
    in_scene = world.get("pacing", {}).get("sceneWalkMinutes", 0)
    best, q = {src: 0}, [(0, src)]
    while q:
        d, p = heapq.heappop(q)
        if p == dst:
            return d
        if d > best[p]:
            continue
        scene = places[p]["sceneRef"]
        for e in places[p]["adjacent"]:
            n = e["place"]
            nd = d + (in_scene if scene is not None and places[n]["sceneRef"] == scene else e["travelMinutes"])
            if nd < best.get(n, nd + 1):
                best[n] = nd
                heapq.heappush(q, (nd, n))
    return None


def activity(world: World, state: SimState, who: str) -> str:
    """who（人物 ID）此刻在做什么。不是人物（含 "player"）给 idle。

    契约 2.4（1.1）：开局是 `initialActivity`（省略 = idle）；节拍发生后是这个节拍 `activities` 里给他的，
    「到他下一个带 activity 的节拍或移动为止」。移动了、新地方又没给 = idle（S-077 ⑩：屋里干活的人被节拍带走以后
    不再 absent）。SimState 不记事件的历史，所以按发生时刻重放已发生的节拍，算出他按节拍「该在」的地点；
    此刻的 `locations` 和它不同 = 节拍以外（人物的事件、叙事者）挪过他 = idle。
    """
    r = _replay(world, state, who)
    if r is None:
        return "idle"
    place, act = r
    return act if state["locations"].get(who) == place else "idle"


def place_at(world: World, state: SimState, who: str, beat: str) -> str | None:
    """beat 发生那一刻 who（人物 ID）按节拍该在的地点：按发生时刻重放 beat 之前已发生的节拍（和 activity() 同一套）。

    SimState 不记事件的历史，节拍以外（人物的事件、叙事者的 relocate）挪过他的那几次算不出来，
    所以这是「按节拍该在哪」，不是他真的在哪。不是人物（含 "player"）、beat 不存在或这一局没发生给 None。
    """
    beats = {b["id"]: b for b in world["beats"]}
    if beat not in beats or state["beats"].get(beat) not in OCCURRED:
        return None
    r = _replay(world, state, who, (state["times"].get(beat, 0), beats[beat]["order"]))
    return None if r is None else r[0]


def lived(world: World, state: SimState, who: str, beat: str) -> bool:
    """人物 who 亲历了 beat：这一局发生了（happened / altered），而且他是参与人物，或者 beat 没有参与人物、
    落在他当时（place_at）所在的同一个场景。没发生的、不是人物的（含 "player"）都是 False。"""
    b = next((x for x in world["beats"] if x["id"] == beat), None)
    if b is None or state["beats"].get(beat) not in OCCURRED:
        return False
    if who in b["participants"]:
        return True
    if b["participants"]:
        return False
    where = place_at(world, state, who, beat)
    return where is not None and same_scene(world, b["place"], where)


def _replay(world: World, state: SimState, who: str, before: tuple[int, int] | None = None) -> tuple[str, str] | None:
    """按发生时刻（同一时刻按 `order`）重放已发生的节拍，给 who 按节拍该在的（地点, activity）。

    before 给了就只重放排在它前面的节拍（(时刻, order)）。不是人物给 None。
    """
    c = next((x for x in world["characters"] if x["id"] == who), None)
    if c is None:
        return None
    act: str = c.get("initialActivity", "idle")
    place: str = c["initialPlace"]
    beats = {b["id"]: b for b in world["beats"]}
    done = sorted(
        (b for b, st in state["beats"].items() if st in OCCURRED and b in beats),
        key=lambda b: (state["times"].get(b, 0), beats[b]["order"]),
    )
    for b in done:
        x = beats[b]
        if before is not None and (state["times"].get(b, 0), x["order"]) >= before:
            break
        after = x["place"] if who in x["participants"] else place  # 参与人物先移到节拍地点（契约 3.1）
        for e in _outcomes(x, state):
            if e.get("op") == "relocate" and e.get("character") == who:
                after = e["place"]
        given = next((a["activity"] for a in x.get("activities", []) if a["character"] == who), None)
        if given is not None:
            act = given
        elif after != place:
            act = "idle"
        place = after
    return place, act


def _outcomes(beat: dict[str, Any], state: SimState) -> list[dict[str, Any]]:
    """这一局这个节拍实际用的结果：变体的、玩家事先改的（altered），或原作的。"""
    vid = state["variants"].get(beat["id"])
    if vid is not None:
        v = next((v for v in beat.get("variants", []) if v["id"] == vid), None)
        if v is not None:
            return list(v["outcomes"])
    o = state["overrides"].get(beat["id"], {})
    if state["beats"].get(beat["id"]) == "altered" and o.get("to") == "altered":
        return list(o.get("outcomes", []))
    return list(beat["outcomes"])
