"""Player actions (B-3 item 2; api-contract 3.8, contract 2.10, 2.11, 2.12): judge first, then play out.

The narrator judges by `kind`:
- `move`: change place within one scene. If the place can be entered, write a move event (0 minutes, no model);
  if not, refused and no event; with `params.crossing` (how to cross the river) and no way through, record a rejected
  move (empty effects, R2-precondition, E5-008).
- `examine`: an examinable object (objects) at the player's place. 0 minutes, no event; play a set piece if there is
  one, otherwise say one line.
- `go`: a scene exit (`way.*`, or a place ID); the candidate = the player walks there, through steps 3-5; if blocked,
  write a rejected event per contract section 3.
- With a matching situational action (`actionId`, or the single one when an eval only gives kind + target): the effect
  template goes through steps 3-5, dt = minutes.
- `give` with no matching situational action: hand over `params.item`, through steps 3-5 (item not in the world model
  or not in hand → R7).
- Anything else: goes through extraction (the input gets an extra `<action>`), 0-3 candidates go through steps 3-5,
  spending `pacing.situationalMinMinutes`.
- `wait`: jump to the next beat at this place (before this act closes) and settle until just after it happens; none →
  refused.

Judging (the steps that call models) happens outside the commit transaction; writing events happens inside it
(`write`), and the same judgment on the same state writes the same events. Set pieces depend on the state after writing,
so first write once on a copy of the state to learn whether a set piece takes over, then decide whether to call
`narrate` for a line.

プレイヤーのアクション（B-3 第 2 項。api-contract 3.8、契約 2.10、2.11、2.12）：先に判定し、それから演じる。

ナレーターは `kind` で判定する：
- `move`：同じ場面の中で場所を変える。入れれば move イベントを 1 つ書く（0 分、モデルは通さない）。入れなければ
  refused でイベントは書かない。`params.crossing`（川の渡り方）付きで通れないときは、却下された move を 1 つ記録する
  （effects は空、R2-precondition、E5-008）。
- `examine`：プレイヤーのいる場所の調べられる物（objects）。0 分でイベントは書かない。
  演出があれば演じ、なければ 1 行言う。
- `go`：場面の出口（`way.*`、または場所 ID）。候補 = プレイヤーがそこへ歩く、を第 3〜5 ステップに通す。止められたら
  契約第 3 節に従って rejected のイベントを書く。
- 対応する状況アクションがあるもの（`actionId`、または評価が kind + target だけを渡したときの唯一のもの）：
  効果のテンプレートを第 3〜5 ステップに通し、dt = minutes。
- 対応する状況アクションのない `give`：`params.item` を渡す。第 3〜5 ステップに通す（物が世界モデルにない、
  手元にない → R7）。
- それ以外：抽出を通し（入力に `<action>` が 1 つ増える）、0〜3 個の候補を第 3〜5 ステップに通し、
  `pacing.situationalMinMinutes` を使う。
- `wait`：この場所の次のビート（この幕を閉じる前）まで飛び、それが起きた直後まで精算する。なければ refused。

判定（モデルを呼ぶステップ）はコミットのトランザクションの外で行い、イベントの書き込みはトランザクションの中で行う
（`write`）。同じ判定、同じ状態からは同じイベントが書かれる。演出は書いたあとの状態で決まるので、まず状態のコピーに
一度書いてみて演出が引き取るかを確かめ、そのうえで `narrate` を呼んで 1 行書くかを決める。
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

# These two kinds of situational action are done for the target character: the event gets beneficiary = target.
# この 2 種類の状況アクションは対象の登場人物のために行うもの：イベントに beneficiary = 対象を付ける。
FOR_TARGET = ("help", "give")
# Changing place within one scene: only checks whether the role may enter, no model (api-contract 3.8).
# 同じ場面の中で場所を変える：役柄が入れるかだけを見て、モデルは通さない（api-contract 3.8）。
CHECKER_MOVE = "b3:move"
# For actions still queued when the act closes (B-3 item 4).
# 幕を閉じたときキューに残っていたアクション用（B-3 第 4 項）。
ACT_ENDED_LINE = "この幕は、もう終わった。"
# turns.result.reason: counted separately from judgment refusals (data-design section 3).
# turns.result.reason：判定による拒否とは別に数える（data-design 第 3 節）。
ACT_ENDED = "act-ended"


@dataclass
class Decision:
    """The judgment of one action (outside the transaction): what to write and what the target is (the set piece's
    target).

    1 つのアクションの判定（トランザクションの外）：何を書くか、対象は何か（演出の target）。
    """

    kind: str  # move / examine / go / affordance / give / free / wait / invalid
    act: str  # the frontend's kind / フロントエンドの kind
    # The set piece's target: a character or place; for go, the place the exit leads to; for examine, obj.*.
    # 演出の target：登場人物か場所。go なら出口の行き先の場所、examine なら obj.*。
    target: str | None
    ok: bool = True  # move / examine / wait: whether it can be done / 実行できるか
    affordance: Json | None = None
    checked: list[Checked] = field(default_factory=list)
    # The situational action's minutes, the go distance, or situationalMinMinutes for an extracted action.
    # 状況アクションの minutes、go の道のり、抽出したアクションの situationalMinMinutes。
    minutes: int = 0
    # The beat wait jumps to (None: no beats left at this place, so wait until the act closes).
    # wait が飛ぶ先のビート（None：この場所にもうビートがないので、幕を閉じるまで待つ）。
    beat: str | None = None
    at: int = 0  # its scheduled time / その予定時刻
    counts: Counts = field(default_factory=Counts)
    narration: str | None = None
    # move's params.crossing (how to cross the river: bridge etc.) / move の params.crossing（川の渡り方：bridge など）
    crossing: str | None = None


@dataclass
class Outcome:
    status: str
    minutes: int
    piece: Json | None
    failed: list[str]


def status_of(checked: list[Checked]) -> str:
    """All committed (passed / rewritten) → done; some downgraded or partly rejected → partial; all rejected or no
    candidates → refused.

    すべてコミット（passed / rewritten）→ done。格下げがある、または一部が却下 → partial。すべて却下、
    または候補なし → refused。
    """
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
    """`move` means walking over within one 3D scene: both places are in the same scene's layout. Scenes without a
    layout yet (the way home, the village, M3) don't accept `move`: travel on the road (distance, river crossing) comes
    with S-081's stops.

    `move` は 1 つの 3D 場面の中を歩いて移ること：2 つの場所が同じ場面のレイアウトにある。まだレイアウトのない場面
    （帰り道、村、M3）は `move` を受け付けない：道中の移動（道のり、川渡り）は S-081 の立ち寄り先と一緒に作る。
    """
    pa, pb = book.places.get(a), book.places.get(b)
    if not (pa and pb and pa.get("sceneRef") is not None and pa.get("sceneRef") == pb.get("sceneRef")):
        return False
    scene = book.scenes.get(str(pa["sceneRef"]))
    return scene is not None and a in scene.places and b in scene.places


def find_affordance(book: Book, state: SimState, req: Mapping[str, Any]) -> Json | None:
    """The actionId the frontend gave (searched among all situational actions; ones whose conditions don't hold are
    left for step 3 to judge); when an eval only gives kind + target, the single situational action holding right now
    whose kind and target match.

    フロントエンドが渡した actionId（すべての状況アクションから探し、条件が成り立たないものは
    第 3 ステップの判定に回す）。
    評価が kind + target だけを渡したときは、いま成り立つ状況アクションのうち kind と target が一致する唯一のもの。
    """
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
    """The target of go: a layout exit (`way.*`) is replaced by the place it leads to; place IDs are accepted too.

    go の対象：レイアウトの出口（`way.*`）はその行き先の場所に置き換える。場所 ID も受け付ける。
    """
    if target is None:
        return None
    place = state["vars"]["var.player.location"]
    scene = book.scenes.get(book.scene_of(place, book.act_of(state["vars"])))
    for ex in scene.exits if scene else ():
        if target in (ex["spot"], ex["place"]):
            return ex["place"]
    return target if target in book.places else None


def next_beat(book: Book, state: SimState, sched: Mapping[str, int]) -> str | None:
    """wait: the next beat at this place (scheduled after now and before this act closes).

    wait：この場所の次のビート（予定時刻がいまより後で、この幕を閉じる前）。
    """
    place = state["vars"]["var.player.location"]
    limit = wait_limit(book, state)
    best: tuple[int, int, str] | None = None
    for b, t in sched.items():
        if book.beats[b]["place"] != place or t <= state["t"] or (limit is not None and t > limit):
            continue
        key = (t, int(book.beats[b]["order"]), b)
        best = key if best is None or key < best else best
    return best[2] if best else None


def wait_limit(book: Book, state: SimState) -> int:
    """In a normal act, wait at most until the act closes; in the final act, at most until the deadline, and the real
    ending flow settles the curtain.

    通常の幕では最長で幕を閉じるまで待つ。最後の幕では最長で期限まで待ち、幕切れは正式なエンディングの流れが精算する。
    """
    act = book.acts[book.act_of(state["vars"])]
    limit = int(act["end"]["atLatest"])
    if not act.get("exits"):
        limit = min(limit, int(book.world["clock"]["deadline"]["t"]))
    return limit


def role_name(book: Book, state: SimState) -> str:
    return str(book.roles[state["role"]]["name"])


# —— Judgment (outside the transaction, calls models) / 判定（トランザクションの外、モデルを呼ぶ） ——


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
        if beat is None:
            # No beats left at this place before the act closes: wait until it closes (atLatest), settling the beats
            # on the way as usual; otherwise time could only be moved on turn by turn through talking.
            # この場所には幕を閉じる前のビートがもうない：幕を閉じるまで（atLatest）待ち、
            # 途中のビートは通常どおり精算する。
            # そうしないと、話して 1 ターンずつ時間を進めるしかなくなる。
            limit = wait_limit(book, state)
            return Decision("wait", kind, None, ok=state["t"] < limit, at=limit)
        return Decision("wait", kind, None, beat=beat, at=sched[beat])
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
            # Contract 1.8: the sentence after it is done, with the target (the role name becomes 「あなた」 when sent).
            # 契約 1.8：やり終えたあとの文で、対象を含む（送るときに役柄名を「あなた」に置き換える）。
            "summary": f"{who}は、{aff['pastLabel']}",
            "causes": [],
            "effects": copy.deepcopy(aff.get("effects", [])),
        }
        if kind in FOR_TARGET and aff.get("target") in book.characters:
            # Done for the target character (contract 2.8's beneficiary; memories and the ending read it).
            # 対象の登場人物のために行ったもの（契約 2.8 の beneficiary。記憶とエンディングが参照する）。
            cand["beneficiary"] = aff["target"]
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
            # If it can't be done, the checks reject it / できないことなら検査が却下する
            "summary": f"{who}は、{to}に{known['name'] if known else '持っていない物'}を渡した",
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


# —— Writing events (inside the transaction, and first once on a copy) ——
# —— イベントの書き込み（トランザクションの中。先にコピーにも一度書く） ——


def write(w: Writer, book: Book, turn_id: str, d: Decision) -> Outcome:
    """Write events per the judgment, settle, and ask for an action-timed set piece. Returns the status, the minutes and
    the set piece played.

    判定に従ってイベントを書き、精算し、アクションのタイミングの演出を問い合わせる。状態、分数、演じた演出を返す。
    """
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
            # Changed place: stand on this place's starting spot (contract 3.1).
            # 場所が変わった：この場所の起点に立つ（契約 3.1）。
            w.run.player_spot = None
        elif d.crossing and d.target in book.places:
            # The way of crossing the river doesn't work (taking the bridge after it was washed away, E5-008; contract
            # 3.8's move has no params, only evals send this): record a rejected move the same way other rejected
            # actions are written (empty effects, dt 0); the player doesn't move.
            # 川の渡り方が通用しない（橋が流されたのに橋を渡ろうとする、E5-008。契約 3.8 の move に params はなく、
            # 評価だけがこう送る）：ほかのアクションが却下されたときと同じ書き方で却下された move を 1 つ記録し
            # （effects は空、dt 0）、プレイヤーは動かない。
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
        if d.ok:
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
    """go, situational actions, give and extracted actions: write the judged candidates in order (rejected ones with
    empty effects, dt 0). The situational action's or go's event carries dt; when an extracted action succeeds, write a
    separate event that only advances the clock (as for dialogue). After writing, settle the beats that came due during
    that time.

    go、状況アクション、give、抽出したアクション：判定済みの候補を順に書く（却下されたものは effects が空、dt 0）。
    状況アクションと go のイベントは dt を持つ。抽出したアクションが成功したら、時計を進めるだけのイベントを別に書く
    （対話のときと同じ）。書き終えたら、その間に時刻が来たビートを精算する。
    """
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
    """Write once on a copy of the state: learn the resulting state and whether a set piece takes over (no model calls,
    no database writes).

    状態のコピーに一度書く：結果の状態と、演出が引き取るかを知る（モデルは呼ばず、データベースにも書かない）。
    """
    w = Writer(book, pid, copy.deepcopy(state), key_base=f"{turn_id}/dry", turn_id=turn_id, ids=ids, now="")
    w.run = copy.deepcopy(run)
    return write(w, book, turn_id, d)


async def narrate(
    n: Narrator, book: Book, state: SimState, d: Decision, out: Outcome, spend: Spend, span: Mapping[str, Any]
) -> str:
    """One line of 地の文 (prompt `narrate`): from the action, the judgment result and the failed rules. If both tries
    fail or the filter rejects it, use the fixed line.

    地の文 1 行（プロンプト `narrate`）：アクション、判定結果、失敗した規則から。2 回ともだめ、またはフィルターを
    通らなければ固定の一文を使う。
    """
    act: Json = {"kind": d.act, "target": d.target}
    if d.affordance is not None:
        # Says what the player tried to do; this is not a result already achieved, and above all a partial must not
        # be written up as a different plot.
        # プレイヤーが何をしようとしたかを伝える。これはすでに成し遂げた結果ではなく、特に partial を別の筋書きとして
        # 書いてはならない。
        act["intendedAction"] = d.affordance.get("label", d.affordance.get("pastLabel", ""))
    completed = [str(c.candidate["summary"]) for c in d.checked if c.passed and c.candidate.get("summary")]
    if completed:
        # Only candidates that passed the checks and were actually committed, never rejected summaries.
        # 検査を通り実際にコミットした候補だけを渡し、却下された要約は含めない。
        act["completedActions"] = completed
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
        # The span's status is this call's status; the action's result is on narrator.action (data-design section 8).
        # Span の status はこの呼び出しの状態。アクションの結果は narrator.action にある（data-design 第 8 節）。
        r = await n.pipeline.call("narrate", request, spend, span=span)
    except CallFailed:
        return narrate_fallback(out.status)
    return clean(str(r.output["text"]), "", frozenset(), limit=60) or narrate_fallback(out.status)


async def run_action(n: Narrator, task: Task) -> Result:
    """One action: read → judge → write once on a copy (to see set pieces) → write a line if there is no set piece →
    commit in a single transaction. If lastSeq changes, start again from judging.

    1 つのアクション：読む → 判定 → コピーに一度書く（演出を見る）→ 演出がなければ 1 行書く → 単一トランザクションで
    コミット。lastSeq が変わったら判定からやり直す。
    """
    from zoujin_backend.narrator.core import MAX_STALE, Stale

    req = dict(task.request or {})
    for _ in range(MAX_STALE):
        pt, state = await n.read(task.pid)
        run = Run.of(pt)
        book = n.library.version(pt["world_model_version"])
        # After the act has closed: 0 minutes, no events, no model calls (B-3 item 4).
        # 幕を閉じたあと：0 分、イベントを書かず、モデルを呼ばない（B-3 第 4 項）。
        if run.act_end is not None:
            return await n._commit(task, pt["last_seq"], lambda w, b: ended(req))
        # Follows the task: retries and uncommitted attempts count too (B-8 item 7).
        # タスクに付いて回る：やり直しやコミットしなかった分も数える（B-8 第 7 項）。
        spend = task.spend
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
            log.info("lastSeq changed; judging %s again / lastSeq が変わったので判定からやり直す", task.turn_id)
    raise RuntimeError(f"{task.turn_id}: lastSeq keeps changing / {task.turn_id}：lastSeq が変わり続けている")


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


def ended(req: Mapping[str, Any]) -> Planned:
    """An action whose turn comes only after the act closed: refused, 0 minutes, no events, one fixed line (the
    frontend clears the pending action by clientMsgId).

    幕を閉じたあとに順番が来たアクション：refused、0 分、イベントなし、固定の一文（フロントエンドは clientMsgId で
    保留中のアクションを片づける）。
    """
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
