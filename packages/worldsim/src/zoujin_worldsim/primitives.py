"""叙事者的确定性规则要用、推演里原来没有的两个原语（B-2 卡：后端提，数据加，后端评审）。

- knows()：R4（契约 2.1 防剧透规则）。人物 C 此刻知道的 = `C.knows` 里 `since` 已发生的（或 `pre`）+ 这一局 `learn`
  学到的（含别人的即兴设定）+ C 自己的即兴设定；玩家 = 身份的 `initialKnowledge`。世界事实的 `trueFrom` 这一局没发生，
  谁都不算知道（契约 2.3，1.4）。和评测的 evals/s2_check.py（S-2 标注用的判法）一致。
- travel_minutes()：R3 的路程（契约 2.2 `adjacent`，api-contract 3.7、3.8）。按 `places.adjacent` 的步行分钟取最短路；
  同一场景里的两个地点之间按 `pacing.sceneWalkMinutes`（S-038：场景内走动 0 分）。只量玩家的移动和排程以外的
  `relocate`；按排程走的人物看排程（backend-design 2.4）。

不在这里的：`crossing`（过河的分钟）和归途的走法。归途四个地点同在 `scene.homeward-road`，按上面的规则互相 0 分，
和真实路程（45〜180 分）对不上：UX 设计归途走法时已经提出，PM 定了走法以后（M3）和 `crossing` 一起改。切片没有归途。
"""

from __future__ import annotations

import heapq

from .incremental import SimState
from .sim import OCCURRED, World, role_of


def knows(world: World, state: SimState, who: str, fact: str) -> bool:
    """who（人物 ID 或 "player"）此刻知不知道 fact（事实 ID，或即兴设定的 rf_ ID）。"""
    beats = state["beats"]
    f = next((x for x in world["facts"] if x["id"] == fact), None)
    if f is not None and f["trueFrom"] != "pre" and beats.get(f["trueFrom"]) not in OCCURRED:
        return False
    if who == "player":
        return f is not None and fact in role_of(world, state["role"]).get("initialKnowledge", [])
    if fact in state["knowledge"].get(who, []):
        return True
    rf = state["runFacts"].get(fact)
    if rf is not None and rf.get("character") == who:
        return True
    c = next((x for x in world["characters"] if x["id"] == who), None)
    return c is not None and any(
        k["fact"] == fact and (k["since"] == "pre" or beats.get(k["since"]) in OCCURRED) for k in c.get("knows", [])
    )


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
