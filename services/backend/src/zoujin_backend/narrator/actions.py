"""玩家的动作（B-3 第 2 条；api-contract 3.8，契约 2.10、2.11、2.12）：先判后演。

叙事者按 `kind` 判：
- `move`：同一场景里换地点。进得去写一条 move 事件（0 分，不过模型）；进不去 refused，不写事件；带
  `params.crossing`（过河的走法）而走不通的记一条被否决的 move（effects 空，R2-precondition，E5-008）。
- `examine`：玩家这个地点的可调查物（objects）。0 分，不写事件；有固定演出就演，没有说一行。
- `go`：场景出口（`way.*`，或地点 ID），候选 = 玩家走到那里，过第 3〜5 步；被拦下按契约第 3 节写 rejected 事件。
- 有对应情境动作的（`actionId`，或评测只给 kind + target 时唯一的那条）：效果模板过第 3〜5 步，dt = minutes。
- `give` 没有对应情境动作的：交出 `params.item`，过第 3〜5 步（物品不在世界模型里、不在手上 → R7）。
- 别的：走提取（输入多一个 `<action>`），0〜3 个候选过第 3〜5 步，花 `pacing.situationalMinMinutes`。
- `wait`：跳到这个地点的下一个节拍（本幕收幕之前），结算到它刚发生之后；没有 → refused。

判定（调模型的那几步）在提交的事务外做；写事件在事务里（`write`），同样的判定、同样的状态写出同样的事件。
固定演出要看写完以后的状态，所以先在状态的副本上写一遍，知道有没有固定演出接管，再决定要不要调 `narrate` 写一行。
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from zoujin_backend.db.store import Run
from zoujin_backend.ids import IdGen
from zoujin_backend.narrator.pipeline import CallFailed, Counts, Spend, TurnInput
from zoujin_backend.narrator.plans import clean, narrate_fallback
from zoujin_backend.narrator.rules import Checked, reach
from zoujin_backend.narrator.rules import index as rules_index
from zoujin_backend.narrator.view import state_view
from zoujin_backend.narrator.writer import CHECKER_PIECE, Writer
from zoujin_backend.projection import action_id, affordance_minutes, open_affordances
from zoujin_backend.world import Book
from zoujin_worldsim import SimState, flat, pick_set_piece, travel_minutes

if TYPE_CHECKING:
    from zoujin_backend.narrator.core import Narrator, Planned, Result, Task

log = logging.getLogger("zoujin.narrator")

Json = Any

FOR_TARGET = ("help", "give")  # 这两种情境动作是为对象人物做的：事件带 beneficiary = 对象
CHECKER_MOVE = "b3:move"  # 同一场景里换地点：只看身份进不进得去，不过模型（api-contract 3.8）
ACT_ENDED_LINE = "この幕は、もう終わった。"  # 收幕时队列里的动作（B-3 第 4 条）
ACT_ENDED = "act-ended"  # turns.result.reason：和判定拒绝分开数（data-design 第 3 节）


@dataclass
class Decision:
    """一个动作的判定（事务外）：写什么、对象是什么（固定演出的 target）。"""

    kind: str  # move / examine / go / affordance / give / free / wait / invalid
    act: str  # 前端的 kind
    target: str | None  # 固定演出的 target：人物、地点，go 是出口通往的地点，examine 是 obj.*
    ok: bool = True  # move / examine / wait：能不能做
    affordance: Json | None = None
    checked: list[Checked] = field(default_factory=list)
    minutes: int = 0  # 情境动作的 minutes、go 的路程、提取的动作的 situationalMinMinutes
    beat: str | None = None  # wait 跳到的节拍
    at: int = 0  # 它的排定时刻
    counts: Counts = field(default_factory=Counts)
    narration: str | None = None
    crossing: str | None = None  # move 的 params.crossing（过河的走法：bridge 等）


@dataclass
class Outcome:
    status: str
    minutes: int
    piece: Json | None
    failed: list[str]


def status_of(checked: list[Checked]) -> str:
    """全部提交（passed / rewritten）→ done；有降级的、或部分被否决 → partial；全被否决、或没有候选 → refused。"""
    if not checked:
        return "refused"
    st = [c.check["status"] for c in checked]
    if all(s == "rejected" for s in st):
        return "refused"
    if all(s in ("passed", "rewritten") for s in st):
        return "done"
    return "partial"


def failed_rules(checked: list[Checked]) -> list[str]:
    return list(dict.fromkeys(r for c in checked if not c.passed for r in c.check["failedRules"]))


def same_scene(book: Book, a: str, b: str) -> bool:
    """`move` 是在一个 3D 场景里走过去：两个地点都在同一个场景的布局里。还没有布局的场景（归途、村子，M3）不收
    `move`：路上的走法（路程、过河）跟 S-081 的停靠点一起做。"""
    pa, pb = book.places.get(a), book.places.get(b)
    if not (pa and pb and pa.get("sceneRef") is not None and pa.get("sceneRef") == pb.get("sceneRef")):
        return False
    scene = book.scenes.get(str(pa["sceneRef"]))
    return scene is not None and a in scene.places and b in scene.places


def find_affordance(book: Book, state: SimState, req: Mapping[str, Any]) -> Json | None:
    """前端给的 actionId（所有情境动作里找，条件不成立的交给第 3 步判）；评测只给 kind + target 时，此刻成立的
    情境动作里 kind、target 对得上的唯一一条。"""
    aid = req.get("actionId")
    if aid:
        return next((a for a in book.world.get("affordances", []) if action_id(a["id"]) == aid), None)
    found = [
        a
        for a in open_affordances(book, state)
        if a["kind"] == req["kind"]
        and a.get("target") == req.get("target")
        and (a.get("item") is None or a.get("item") == (req.get("params") or {}).get("item"))
    ]
    return found[0] if len(found) == 1 else None


def exit_place(book: Book, state: SimState, target: str | None) -> str | None:
    """go 的对象：布局的出口（`way.*`）换成它通往的地点；也认地点 ID。"""
    if target is None:
        return None
    place = state["vars"]["var.player.location"]
    scene = book.scenes.get(book.scene_of(place, book.act_of(state["vars"])))
    for ex in scene.exits if scene else ():
        if target in (ex["spot"], ex["place"]):
            return ex["place"]
    return target if target in book.places else None


def next_beat(book: Book, state: SimState, sched: Mapping[str, int]) -> str | None:
    """wait：这个地点的下一个节拍（排定时刻在此刻之后、在本幕收幕之前）。"""
    place = state["vars"]["var.player.location"]
    act = book.acts[book.act_of(state["vars"])]
    limit = act["end"]["atLatest"] if act.get("exits") else None
    best: tuple[int, int, str] | None = None
    for b, t in sched.items():
        if book.beats[b]["place"] != place or t <= state["t"] or (limit is not None and t > limit):
            continue
        key = (t, int(book.beats[b]["order"]), b)
        best = key if best is None or key < best else best
    return best[2] if best else None


def role_name(book: Book, state: SimState) -> str:
    return str(book.roles[state["role"]]["name"])


# —— 判定（事务外，调模型） ——


async def decide(
    n: Narrator, book: Book, state: SimState, req: Mapping[str, Any], spend: Spend, span: Mapping[str, Any]
) -> Decision:
    from zoujin_backend.narrator.acts import schedule

    kind = str(req["kind"])
    target = req.get("target")
    params = dict(req.get("params") or {})
    place = state["vars"]["var.player.location"]
    who = role_name(book, state)
    if kind == "move":
        ok = (
            target in book.places
            and target != place
            and same_scene(book, place, target)
            and target in reach(rules_index(book.world), state, flat(state))
        )
        crossing = params.get("crossing")
        return Decision("move", kind, target, ok=bool(ok), crossing=str(crossing) if crossing else None)
    if kind == "examine":
        obj = next((o for o in book.world.get("objects", []) if o["id"] == target), None)
        return Decision("examine", kind, target, ok=obj is not None and obj["place"] == place)
    aff = find_affordance(book, state, req)
    if kind == "wait" and aff is None:
        sched = schedule(book, state)
        beat = next_beat(book, state, sched)
        return Decision("wait", kind, None, ok=beat is not None, beat=beat, at=sched.get(beat or "", 0))
    if kind == "go":
        dest = exit_place(book, state, target)
        if dest is None:
            return Decision("invalid", kind, target, ok=False)
        cand = {
            "actor": "player",
            "type": "move",
            "origin": "action",
            "summary": f"{who}は{book.places[dest]['name']}へ向かった",
            "causes": [],
            "effects": [{"op": "set", "var": "var.player.location", "value": dest}],
        }
        minutes = travel_minutes(book.world, place, dest) or 0
        turn = TurnInput(character=None, player=None, act={"kind": "go", "target": dest})
        v = await n.pipeline.verify(book, state, [cand], turn, minutes, spend, span)
        return Decision("go", kind, dest, checked=v.checked, minutes=minutes, counts=v.counts)
    if aff is not None:
        cand = {
            "actor": "player",
            "type": "action",
            "origin": "action",
            "summary": f"{who}は、{aff['pastLabel']}",  # 契约 1.8：做完以后的句子，带对象（下发时身份名换成「あなた」）
            "causes": [],
            "effects": copy.deepcopy(aff.get("effects", [])),
        }
        if kind in FOR_TARGET and aff.get("target") in book.characters:
            cand["beneficiary"] = aff["target"]  # 为对象人物做的（契约 2.8 的 beneficiary；记忆和结局看它）
        minutes = affordance_minutes(book, aff)
        act = {"affordance": aff["id"], "kind": kind, "target": target, "params": params}
        turn = TurnInput(character=aff.get("target"), player=None, act=act)
        v = await n.pipeline.verify(book, state, [cand], turn, minutes, spend, span)
        return Decision(
            "affordance", kind, aff.get("target"), affordance=aff, checked=v.checked, minutes=minutes, counts=v.counts
        )
    minutes = int(book.world["pacing"]["situationalMinMinutes"])
    turn = TurnInput(
        character=target if target in book.characters else None,
        player=None,
        act={"kind": kind, "target": target, "params": params},
    )
    if kind == "give":
        item = params.get("item")
        known = next((x for x in book.world.get("items", []) if x["id"] == item), None)
        to = book.characters.get(target or "", {}).get("name", "相手")
        cand = {
            "actor": "player",
            "type": "action",
            "origin": "action",
            "summary": f"{who}は、{to}に{known['name'] if known else '持っていない物'}を渡した",  # 做不到的检查会拒
            "causes": [],
            "effects": [{"op": "hold", "item": item or "item.unknown", "to": target}],
        }
        if target in book.characters:
            cand["beneficiary"] = target
        v = await n.pipeline.verify(book, state, [cand], turn, minutes, spend, span)
        return Decision("give", kind, target, checked=v.checked, minutes=minutes, counts=v.counts)
    ex = await n.pipeline.extract(book, state, turn, spend, span)
    counts = ex.counts
    checked: list[Checked] = []
    if not ex.timed_out and ex.candidates:
        cands = [{**c, "origin": "action"} for c in ex.candidates]
        v = await n.pipeline.verify(book, state, cands, turn, minutes, spend, span)
        checked, counts = v.checked, counts + v.counts
    return Decision("free", kind, target, checked=checked, minutes=minutes, counts=counts)


# —— 写事件（事务里，也在副本上先写一遍） ——


def write(w: Writer, book: Book, turn_id: str, d: Decision) -> Outcome:
    """按判定写事件、结算，问动作时机的固定演出。返回状态、分钟和演的固定演出。"""
    t0 = w.state["t"]
    place = w.player_place
    who = role_name(book, w.state)
    status = "done"
    failed: list[str] = []
    if d.kind == "move":
        if d.ok:
            assert d.target is not None
            w.add(
                w.full(
                    t=t0,
                    dt=0,
                    actor="player",
                    type="move",
                    origin="action",
                    place=place,
                    summary=f"{who}は{book.places[d.target]['name']}へ移った",
                    effects=[{"op": "set", "var": "var.player.location", "value": d.target}],
                    check={"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER_MOVE},
                    turn_id=turn_id,
                )
            )
            w.run.player_spot = None  # 换了地点：站这个地点的起点（契约 3.1）
        elif d.crossing and d.target in book.places:
            # 过河的走法走不通（桥冲毁了还要走桥，E5-008；契约 3.8 的 move 没有 params，只有评测这样发）：照别的动作
            # 被否决的写法记一条被否决的 move（effects 空、dt 0），玩家不动
            status, failed = "refused", ["R2-precondition"]
            w.add(
                w.full(
                    t=t0,
                    dt=0,
                    actor="player",
                    type="move",
                    origin="action",
                    place=place,
                    summary=f"{who}は{book.places[d.target]['name']}へ渡ろうとした",
                    effects=[],
                    check={"status": "rejected", "attempts": 1, "failedRules": failed, "checker": CHECKER_MOVE},
                    turn_id=turn_id,
                )
            )
        else:
            status, failed = "refused", ["R7-capability"]
    elif d.kind in ("examine", "invalid"):
        if not d.ok:
            status, failed = "refused", ["R7-capability"]
    elif d.kind == "wait":
        if d.ok and d.beat is not None:
            w.settle(d.at, stop_after=d.beat)
        else:
            status, failed = "refused", ["R2-precondition"]
    else:
        status, failed = _candidates(w, book, turn_id, d)
    minutes = 0 if status == "refused" else w.state["t"] - t0
    hook = {"act": d.act, "target": d.target, "refused": status == "refused"}
    piece = pick_set_piece(book.world, w.state, {k: v for k, v in hook.items() if v is not None}, w.run.played)
    if piece is not None:
        w.play(piece)
        w.piece_learn(piece, w.state["t"], origin="action")
    return Outcome(status, minutes, piece, failed)


def _candidates(w: Writer, book: Book, turn_id: str, d: Decision) -> tuple[str, list[str]]:
    """go、情境动作、give、提取的动作：判过的候选按顺序写（被否决的 effects 为空，dt 0）。情境动作和 go 的那一条
    带 dt；提取的动作做成了另写一条只推进时钟的事件（同对话那一条）。写完结算这段时间里到点的节拍。"""
    t0 = w.state["t"]
    place = w.player_place
    timed = d.kind in ("go", "affordance")
    for c in d.checked:
        cand = c.candidate
        extra = {k: cand[k] for k in ("beneficiary", "confirmed") if k in cand}
        w.add(
            w.full(
                t=t0,
                dt=d.minutes if timed and c.passed else 0,
                actor=cand.get("actor", "player"),
                type=cand.get("type", "action"),
                origin="action",
                place=cand.get("place", place),
                summary=cand["summary"],
                effects=c.effects if c.passed else [],
                causes=cand.get("causes", []),
                check=c.check,
                turn_id=turn_id,
                **extra,
            )
        )
    status = status_of(d.checked)
    if status != "refused" and not timed and d.minutes:
        w.add(
            w.full(
                t=t0,
                dt=d.minutes,
                actor="player",
                type="action",
                origin="action",
                place=place,
                summary=f"{role_name(book, w.state)}は、しばらく動いた",
                effects=[],
                check={"status": "passed", "attempts": 1, "failedRules": [], "checker": "b0:clock"},
                turn_id=turn_id,
            )
        )
    if status != "refused" and d.kind == "affordance" and d.affordance and d.affordance.get("playerSpot"):
        w.run.player_spot = d.affordance["playerSpot"]
    w.settle(w.state["t"])
    return status, failed_rules(d.checked)


def dry_run(book: Book, pid: str, state: SimState, run: Run, turn_id: str, d: Decision, ids: IdGen) -> Outcome:
    """在状态的副本上写一遍：知道状态、有没有固定演出接管（不调模型、不写库）。"""
    w = Writer(book, pid, copy.deepcopy(state), key_base=f"{turn_id}/dry", turn_id=turn_id, ids=ids, now="")
    w.run = copy.deepcopy(run)
    return write(w, book, turn_id, d)


async def narrate(
    n: Narrator, book: Book, state: SimState, d: Decision, out: Outcome, spend: Spend, span: Mapping[str, Any]
) -> str:
    """一行地の文（提示 `narrate`）：按动作、判定结果和失败的规则。两次都不行、或过滤不过，用固定的一句。"""
    act: Json = {"kind": d.act, "target": d.target}
    if d.kind == "give":
        act["item"] = d.checked[0].candidate["effects"][0].get("item") if d.checked else None
    request = {
        "worldModelVersion": book.version,
        "state": state_view(book, state).doc,
        "act": act,
        "status": out.status,
        "failedRules": out.failed,
    }
    try:
        # Span 的 status 是这次调用的状态；动作的结果在 narrator.action 上（data-design 第 8 节）
        r = await n.pipeline.call("narrate", request, spend, span=span)
    except CallFailed:
        return narrate_fallback(out.status)
    return clean(str(r.output["text"]), "", frozenset(), limit=60) or narrate_fallback(out.status)


async def run_action(n: Narrator, task: Task) -> Result:
    """一个动作：读 → 判定 → 副本上写一遍（看固定演出）→ 没有固定演出就写一行 → 单事务提交。lastSeq 变了从判定重来。"""
    from zoujin_backend.narrator.core import MAX_STALE, Stale

    req = dict(task.request or {})
    for _ in range(MAX_STALE):
        pt, state = await n.read(task.pid)
        run = Run.of(pt)
        book = n.library.version(pt["world_model_version"])
        if run.act_end is not None:  # 收幕以后：0 分、不写事件、不调模型（B-3 第 4 条）
            return await n._commit(task, pt["last_seq"], lambda w, b: ended(w, req))
        spend = task.spend  # 跟着任务走：重来的、没提交的也算（B-8 第 7 条）
        span = {"playthrough_id": task.pid, "turn_id": task.turn_id, "world_model_version": book.version}
        d = await decide(n, book, state, req, spend, span)
        out = dry_run(book, task.pid, state, run, task.turn_id, d, n.ids)
        if out.piece is None:
            d.narration = await narrate(n, book, state, d, out, spend, span)
        if n.before_commit is not None:
            await n.before_commit(task)

        def write(w: Writer, b: Book, d: Decision = d) -> Planned:
            return written(n, w, b, task, req, d)

        try:
            return await n._commit(task, pt["last_seq"], write, spend=spend, counts=d.counts)
        except Stale:
            log.info("lastSeq 变了，%s 从判定重来", task.turn_id)
    raise RuntimeError(f"{task.turn_id}：lastSeq 一直在变")


def written(n: Narrator, w: Writer, book: Book, task: Task, req: Mapping[str, Any], d: Decision) -> Planned:
    from zoujin_backend.narrator.core import Planned

    with n.tracer.span(
        "narrator.action",
        playthrough_id=task.pid,
        turn_id=task.turn_id,
        world_model_version=book.version,
        action_kind=d.act,
    ) as sp:
        out = write(w, book, task.turn_id, d)
        sp.set(status=out.status, failed_rules=out.failed)
        if out.piece is not None:
            sp.set(piece_id=out.piece["id"])
    own = [e for e in w.events if e.get("turnId") == task.turn_id]
    seen = set(w.seen)
    msg: Json = {
        "type": "action_result",
        "clientMsgId": req.get("clientMsgId") or task.turn_id,
        "status": out.status,
        "eventIds": [e["eventId"] for e in own if e["eventId"] in seen],
        "minutes": out.minutes,
    }
    push: list[Json] = []
    if out.piece is not None:
        msg["setPiece"] = out.piece["id"]
        push = [msg, {"type": "set_piece", "pieceId": out.piece["id"], "lines": [dict(x) for x in out.piece["lines"]]}]
    else:
        msg["narration"] = d.narration or narrate_fallback(out.status)
        push = [msg]
    info: Json = {"status": out.status, "minutes": out.minutes}
    if out.piece is not None:
        info["setPiece"] = out.piece["id"]
    else:
        info["narration"] = msg["narration"]
    if d.affordance and d.affordance.get("aid") and out.status != "refused":
        info["aid"] = d.affordance["aid"]
    extra: Json = {}
    if d.affordance and d.affordance.get("playerSpot") and out.status != "refused":
        extra["playerSpot"] = d.affordance["playerSpot"]
    return Planned(minutes=out.minutes, checked=d.checked, push=push, info=info, extra=extra, actions=1)


def ended(w: Writer, req: Mapping[str, Any]) -> Planned:
    """收幕以后才轮到的动作：refused、0 分、没有事件，一句固定的话（前端靠 clientMsgId 收掉待定的动作）。"""
    from zoujin_backend.narrator.core import Planned

    msg: Json = {
        "type": "action_result",
        "clientMsgId": req.get("clientMsgId") or "-",
        "status": "refused",
        "eventIds": [],
        "minutes": 0,
        "narration": ACT_ENDED_LINE,
    }
    info = {"status": "refused", "minutes": 0, "narration": ACT_ENDED_LINE}
    return Planned(push=[msg], info=info, extra={"reason": ACT_ENDED}, actions_ended=1)


__all__ = ["ACT_ENDED", "ACT_ENDED_LINE", "CHECKER_MOVE", "CHECKER_PIECE", "Decision", "run_action"]
