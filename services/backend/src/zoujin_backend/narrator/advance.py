"""World advancement: plans of characters who are not present, settling promises, and director events (B-16;
backend-design 2.6, contract 3.2, 2.8.1 step 3).

Three timings; one call (prompt `world`) handles plans, promises and the director together:
- Act transition (`act`): after a destination is chosen or a plan goes ahead and before jumping acts; the window is
  from now to the target time. Events and the beats that come due are merged by time (2.8.1 step 3, the player not
  present), and 「その頃」 is taken from them. The model is called outside the commit transaction; inside it, events
  are settled by time and step 3 and the director rules are judged again, dropping those that fail.
- After a key moment (`key`): when a commit has an event with `keyMoment`, a `world` task is queued in the same
  transaction; it happens at the current time (dt 0).
- Mid-act (`mid`): one per 8 judged dialogue turns in this act; the model isn't called when there are no plans left
  to advance and the director has no quota left.

Checks: candidates go through step 3 in time order (R1-R4, R7, `Turn.act.kind = "world"`: the actor counts as able to
reach things even away from the player, and targets count only at the actor's place); those that pass go through one
combined step 4 (R5, R6), then the director rules. Failures are simply dropped: no rewriting, no rejected events (2.6
step 3).

Director rules (deterministic):
- D1, D2: world advancement (the director just like character plans) must not make Melos arrive after sunset: if after
  commit the forecast (the player doing nothing more) misses it and is later than before the commit → drop. Stricter
  than the design draft's D2: the director may delay him a little, but even if the player does nothing he must still
  make it, so there is always a chance to put things right.
- D3: director events in front of the player are only placed in `key` and `mid`, and only when no player turn is
  queued; the actor is the environment (`system`), or a character walking in from elsewhere (the effects relocate them
  to the player's place).
- D4: at most 1 per act in front of the player; at most 3 per act away from the player (「その頃」 reports at most 3).
- D5: `causes` contains at least one event by the player or a character.

Character plans are not written where the player can see them (things face to face go through dialogue). The player is
written as 「あなた」 only when sending (as with other events).

世界の進行：その場にいない登場人物のプラン、約束の精算、ディレクターのイベント（B-16。backend-design 2.6、契約 3.2、
2.8.1 第 3 ステップ）。

3 つのタイミングで、1 回の呼び出し（プロンプト `world`）がプラン、約束、ディレクターをまとめて扱う：
- 幕切り替え（`act`）：行き先を選んだ、またはプランが実行されると決まったあと、幕を飛ぶ前。
  時間帯はいまから目標時刻まで。
  イベントと時刻が来たビートを時刻順に合わせ（2.8.1 第 3 ステップ、プレイヤー不在）、「その頃」はそこから取る。
  モデルはコミットのトランザクションの外で呼び、トランザクションの中で時刻順に精算し、第 3 ステップとディレクターの
  規則をもう一度判定して、通らないものは捨てる。
- 重要な瞬間のあと（`key`）：コミットに `keyMoment` のイベントがあれば、同じトランザクションで `world` タスクを 1 つ
  積む。いま起きる（dt 0）。
- 各幕の中盤（`mid`）：この幕で判定済みの対話ターン 8 回ごとに 1 つ積む。まだ進めていないプランがなく、
  ディレクターの枠もなければモデルは呼ばない。

検査：候補を時刻順に第 3 ステップに通し（R1〜R4、R7、`Turn.act.kind = "world"`：行為者はプレイヤーのそばにいなくても
届くとみなし、対象は行為者と同じ場所にいるときだけ数える）、通ったものをまとめて 1 回第 4 ステップ（R5、R6）に通し、
さらにディレクターの規則に通す。通らないものはそのまま捨て、書き換えも rejected のイベントの書き込みもしない
（2.6 第 3 ステップ）。

ディレクターの規則（決定的）：
- D1、D2：世界の進行（ディレクターも登場人物のプランと同じ）でメロスが日没より後に着くようにしてはならない：コミット後の
  予測（プレイヤーがもう何もしない場合）で間に合わず、しかもコミット前より遅い → 捨てる。設計稿の D2 より厳しい：
  ディレクターが少し遅らせるのはよいが、プレイヤーが何もしなくてもまだ間に合わなければならず、挽回の機会は常に残す。
- D3：プレイヤーの目の前でのディレクターのイベントは `key` と `mid` だけで、積まれたプレイヤーのターンがないときだけ
  出す。行為者は環境（`system`）か、よそから歩いてくる登場人物（効果でその人物をプレイヤーの場所へ relocate する）。
- D4：プレイヤーの目の前では各幕 1 件まで、その場にいないものは各幕 3 件まで（「その頃」が伝えるのは最大 3 件）。
- D5：`causes` にプレイヤーか登場人物のイベントが少なくとも 1 つある。

登場人物のプランはプレイヤーに見える場所では書かない（面と向かってのことは対話で扱う）。プレイヤーを「あなた」と書くのは
送るときだけ（ほかのイベントと同じ）。
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from zoujin_backend.db import store
from zoujin_backend.db.tables import turns
from zoujin_backend.narrator.ending import alias_map
from zoujin_backend.narrator.pipeline import CallFailed, Spend, TurnInput, _Try, normalize, result
from zoujin_backend.narrator.rules import absent, fill_ids, index, judge, trial
from zoujin_backend.narrator.view import state_view
from zoujin_backend.narrator.writer import Writer
from zoujin_backend.projection import as_you, committed
from zoujin_backend.world import Book
from zoujin_worldsim import SimState, activity, same_scene, sees, world_state

if TYPE_CHECKING:
    from zoujin_backend.narrator.core import Narrator, Planned, Result, Task

log = logging.getLogger("zoujin.narrator")

Json = Any

KIND = "world"  # the task and prompt kind / タスクとプロンプトの種類
MID_EVERY = 8  # mid-act: every 8 judged dialogue turns / 各幕の中盤：判定済みの対話ターン 8 回ごと
PRESENT_PER_ACT = 1  # D4: at most 1 per act in front of the player / プレイヤーの目の前では各幕 1 件まで
ABSENT_PER_ACT = 3  # D4: at most 3 absent director events per act / その場にいないディレクターのイベントは各幕 3 件まで
# How many of this act's most recent player-visible events are given to the model.
# モデルに渡す、この幕でプレイヤーに見えた最近のイベントの件数。
RECENT = 12
SUMMARY_MAX = 80
WORLD_ACT = {"kind": "world"}  # step 3's Turn.act: world advancement / 第 3 ステップの Turn.act：世界の進行


@dataclass(frozen=True)
class Window:
    """The window and reason of this advancement (act / key / mid). For key and mid, start == end (now).

    今回の進行の時間帯と理由（act / key / mid）。key と mid では start == end（いま）。
    """

    reason: str
    start: int
    end: int
    # act: which act to jump to (so the model sees the next act's plans).
    # act：どの幕へ飛ぶか（次の幕のプランをモデルに見せるため）。
    to_act: str | None = None


@dataclass
class Item:
    """One candidate that passed the checks (at commit, step 3 and the director rules are judged again against the state
    at that time).

    検査を通った候補 1 つ（コミット時にその時点の状態で第 3 ステップとディレクターの規則をもう一度判定する）。
    """

    cand: Json
    effects: list[Json]
    check: Json
    present: bool = False  # in front of the player (D3, D4) / プレイヤーの目の前（D3、D4）


@dataclass
class Prepared:
    items: list[Item] = field(default_factory=list)
    called: bool = False


# —— This act / この幕 ——


def act_start(log_: Sequence[Mapping[str, Any]]) -> int:
    """The seq after which this act starts: the last system act-transition (0 at the start of the game).

    この幕がどの seq の後から始まるか：最後のシステムの act-transition（ゲーム開始時は 0）。
    """
    return max((int(e["seq"]) for e in log_ if e["type"] == "act-transition" and e["actor"] == "system"), default=0)


def visible_log(book: Book, role_id: str, log_: Sequence[Mapping[str, Any]]) -> set[str]:
    """IDs of the events the player can see (same scope as the timeline: visible per 2.4, plus things the player got
    done that had effects).

    プレイヤーに見えるイベントの ID（時間線と同じ範囲：2.4 で見えるものに、
    プレイヤー自身がやり遂げた効果のあるものを加える）。
    """
    from zoujin_backend.timeline import replay

    return {ev["eventId"] for ev in replay(book, role_id, log_).visible}


def used(log_: Sequence[Mapping[str, Any]], shown: set[str]) -> tuple[int, int]:
    """Director quota already used in this act: (in front of the player, away from the player).

    この幕ですでに使ったディレクターの枠：（プレイヤーの目の前, その場にいない）。
    """
    start = act_start(log_)
    mine = [e for e in log_ if int(e["seq"]) > start and e.get("origin") == "director" and committed(e)]
    present = sum(1 for e in mine if e["eventId"] in shown)
    return present, len(mine) - present


def quota(window: Window, log_: Sequence[Mapping[str, Any]], shown: set[str], *, busy: bool) -> Json:
    p, a = used(log_, shown)
    present = window.reason != "act" and not busy and p < PRESENT_PER_ACT
    return {"present": present, "absent": max(0, ABSENT_PER_ACT - a)}


def plans_for(book: Book, who: str, acts_: Iterable[str]) -> list[str]:
    wanted = set(acts_)
    return [str(p["text"]) for p in book.characters[who].get("plans", []) if p.get("act") in wanted]


def actors(book: Book, state: SimState, window: Window) -> list[Json]:
    """The characters given to the model: those with goals or plans, with where they are now, what they are doing,
    whether they share the player's scene, and their plans for this act (and the next).

    モデルに渡す登場人物：目標かプランのある者について、いまどこにいて何をしているか、プレイヤーと同じ場面か、
    この幕（と次の幕）のプラン。
    """
    acts_ = [book.act_of(state["vars"]), *([window.to_act] if window.to_act else [])]
    player = state["vars"]["var.player.location"]
    out = []
    for c in sorted(book.characters):
        ch = book.characters[c]
        plans = plans_for(book, c, acts_)
        if not plans and not ch.get("goals"):
            continue
        place = state["locations"].get(c)
        out.append(
            {
                "id": c,
                "name": ch["name"],
                "place": place,
                "activity": activity(book.world, state, c),
                "withPlayer": place is not None and same_scene(book.world, place, player),
                "goals": [str(g["text"]) for g in ch.get("goals", [])],
                "plans": plans,
            }
        )
    return out


def has_work(book: Book, state: SimState, window: Window, q: Mapping[str, Any]) -> bool:
    """mid and key: calling the model is only worth it if some character away from the player, not absent, has plans
    for this act, or the director still has quota.

    mid と key：プレイヤーのそばにおらず、absent でもなく、この幕のプランを持つ登場人物がいるか、ディレクターにまだ
    枠があるときだけモデルを呼ぶ価値がある。
    """
    if q["present"] or q["absent"] > 0:
        return True
    ix = index(book.world)
    player = state["vars"]["var.player.location"]
    for c in book.characters:
        place = state["locations"].get(c)
        if place is None or absent(ix, state, c) or same_scene(book.world, place, player):
            continue
        if plans_for(book, c, [book.act_of(state["vars"])]):
            return True
    return False


def request(
    book: Book, state: SimState, log_: Sequence[Mapping[str, Any]], shown: set[str], window: Window, q: Json
) -> Json:
    start = act_start(log_)
    role = state["role"]
    recent = [
        {"eventId": e["eventId"], "t": e["t"], "actor": e["actor"], "summary": as_you(book, role, str(e["summary"]))}
        for e in log_
        if int(e["seq"]) > start and e["eventId"] in shown
    ][-RECENT:]
    view = state_view(book, state)
    promises = [p for p in view.doc["promises"] if p.get("status") == "open"]
    return {
        "worldModelVersion": book.version,
        "state": view.doc,
        "reason": window.reason,
        "window": {
            "from": window.start,
            "to": window.end,
            "fromLabel": book.label(window.start),
            "toLabel": book.label(window.end),
        },
        "player": {"place": state["vars"]["var.player.location"]},
        "characters": actors(book, state, window),
        "promises": promises,
        "recent": recent,
        "director": q,
    }


def swap(x: Json, ids: Mapping[str, str]) -> Json:
    """Replace strings that are exactly an event ID (or alias); leave everything else as is.

    ちょうどイベント ID（または別名）である文字列を置き換え、それ以外はそのままにする。
    """
    if isinstance(x, dict):
        return {k: swap(v, ids) for k, v in x.items()}
    if isinstance(x, list):
        return [swap(v, ids) for v in x]
    return ids.get(x, x) if isinstance(x, str) else x


# —— Candidates and checks / 候補と検査 ——


def candidate(raw: Mapping[str, Any], book: Book, state: SimState, ids: set[str], window: Window) -> Json | None:
    """One item from the model → a candidate; drop it if its time is outside the window, its actor or place is unknown,
    or its summary is too long. causes keeps only this game's events and beats.

    モデルの 1 件 → 候補。時刻が時間帯の外、行為者か場所が不明、要約が長すぎるものは捨てる。causes はこのゲームの
    イベントとビートだけ残す。
    """
    t = int(raw.get("t", window.start))
    actor = str(raw.get("actor") or "")
    origin = raw.get("origin")
    if not window.start <= t <= window.end or origin not in ("plan", "director"):
        return None
    if actor not in book.characters and not (actor == "system" and origin == "director"):
        return None
    if raw.get("place") not in book.places:
        return None
    summary = str(raw.get("summary") or "").strip()
    if not summary or len(summary) > SUMMARY_MAX or not raw.get("effects"):
        return None  # changes nothing, so it is mere narration: not written / 何も変えないのはただの叙述なので書かない
    view = state_view(book, state)
    c = normalize({**raw, "summary": summary}, view, book)
    c.pop("needsConfirm", None)
    c["origin"] = origin
    c["place"] = raw["place"]
    c["t"] = t
    c["causes"] = list(dict.fromkeys(x for x in raw.get("causes") or [] if x in ids or x in book.beats))
    return c


def arrival(book: Book, state: SimState) -> int | None:
    """The forecast time Melos reaches the execution ground (`clock.deadline.watchBeat`): the actual time if it
    happened, the scheduled time if it has no result yet; None if it won't happen.

    メロスが刑場に着く予測時刻（`clock.deadline.watchBeat`）：起きたなら起きた時刻、まだ結果がなければ予定時刻、
    起きないなら None。
    """
    watch = book.world["clock"]["deadline"].get("watchBeat")
    if watch is None:
        return None
    at = state["times"].get(watch)
    if at is None:
        at = world_state(book.world, state, "")["schedule"].get(watch)
    return None if at is None else int(at)


def too_late(book: Book, before: SimState, after: SimState) -> bool:
    """D1, D2: after commit he misses sunset and is later than before the commit (not happening counts as latest).
    World models without a deadline aren't judged.

    D1、D2：コミット後に日没に間に合わず、しかもコミット前より遅い（起きないものは最も遅いとみなす）。
    期限のない世界モデルは判定しない。
    """
    if book.world["clock"]["deadline"].get("watchBeat") is None:
        return False
    deadline = int(book.world["clock"]["deadline"]["t"])
    a, b = arrival(book, before), arrival(book, after)
    late = b is None or b > deadline
    later = (b is None and a is not None) or (a is not None and b is not None and b > a)
    return late and later


def in_sight(book: Book, cand: Mapping[str, Any], effects: Sequence[Mapping[str, Any]], player: str) -> bool:
    """Whether the player can see it (contract 1.12's `sees()`, the same test as pushing commits).

    プレイヤーに見えるか（契約 1.12 の `sees()`、commit のプッシュと同じ判定）。
    """
    return sees(book.world, player, {**cand, "effects": list(effects)})


def entered(cand: Mapping[str, Any], effects: Sequence[Mapping[str, Any]], player: str) -> bool:
    """D3: a director event in front of the player enters through the environment or a character walking in.

    D3：プレイヤーの目の前でのディレクターのイベントは、環境か歩いてくる登場人物から入る。
    """
    if cand["actor"] == "system":
        return True
    return any(
        e.get("op") == "relocate" and e.get("character") == cand["actor"] and e.get("place") == player for e in effects
    )


def fairness(
    book: Book,
    state: SimState,
    cand: Mapping[str, Any],
    effects: Sequence[Json],
    log_by_id: Mapping[str, Mapping[str, Any]],
    q: Mapping[str, Any],
    taken: dict[str, int],
    *,
    away: bool = False,
) -> tuple[str | None, bool]:
    """The director rules and "plans not in front of the player". Returns (the failed rule code, whether it is in front
    of the player). taken: the quota already used by this advancement. In an act transition (`away`) the player is
    always not present.

    ディレクターの規則と「プランはプレイヤーの目の前では起こさない」。（通らなかった規則コード, プレイヤーの目の前か）を
    返す。taken：今回の進行ですでに使った枠。幕切り替え（`away`）ではプレイヤーは常にその場にいない。
    """
    player = state["vars"]["var.player.location"]
    shown = not away and in_sight(book, cand, effects, player)
    try:
        after = trial(book.world, state, dict(cand), list(effects))
    except ValueError:
        return "apply", shown
    if too_late(book, state, after):
        return "D1", shown
    if cand["origin"] == "plan":
        return ("plan-in-sight" if shown else None), shown
    causes = [log_by_id[c] for c in cand.get("causes", []) if c in log_by_id]
    if not any(c["actor"] == "player" or c["actor"] in book.characters for c in causes):
        return "D5", shown
    if shown:
        if not q["present"] or taken["present"] >= 1 or not entered(cand, effects, player):
            return "D3", shown
    elif taken["absent"] >= int(q["absent"]):
        return "D4", shown
    return None, shown


async def prepare(
    n: Narrator,
    book: Book,
    state: SimState,
    log_: Sequence[Mapping[str, Any]],
    window: Window,
    spend: Spend,
    span: Mapping[str, Any],
    *,
    busy: bool = False,
) -> Prepared:
    """Outside the transaction: call the model, run step 3 and the director rules, and run one combined step 4 on those
    that pass. On a model error or timeout return nothing (world advancement never blocks the player).

    トランザクションの外：モデルを呼び、第 3 ステップとディレクターの規則に通し、通ったものをまとめて
    1 回第 4 ステップに通す。モデルのエラーやタイムアウトなら空を返す（世界の進行はプレイヤーを妨げない）。
    """
    if not n.world_advance:
        return Prepared()
    shown = visible_log(book, state["role"], log_)
    q = quota(window, log_, shown, busy=busy)
    if window.reason != "act" and not has_work(book, state, window, q):
        return Prepared()
    # Event IDs in the request use the alias `e<seq>` (the same situation gives the same request: replay, cache).
    # リクエストのイベント ID は別名 `e<seq>` を使う（同じ局面なら同じリクエスト：リプレイ、キャッシュ）。
    to_alias, back = alias_map(log_)
    req = swap(request(book, state, log_, shown, window, q), to_alias)
    try:
        r = await n.pipeline.call(KIND, req, spend, span={**span, "reason": window.reason})
    except CallFailed:
        log.info(
            "World advancement (%s) failed twice; not advancing this time"
            " / 世界の進行が 2 回とも失敗したので今回は進めない",
            window.reason,
        )
        return Prepared(called=True)
    out = swap(r.output, back)
    by_id = {e["eventId"]: e for e in log_ if committed(e)}
    turn = TurnInput(character=None, player=None, act=WORLD_ACT)
    raws = sorted(out["events"], key=lambda x: int(x.get("t", window.start)))
    now = state
    taken = {"present": 0, "absent": 0}
    tries: list[tuple[_Try, bool]] = []
    for raw in raws:
        c = candidate(raw, book, state, set(by_id), window)
        if c is None:
            continue
        # R3: movement finishes within this window; written with dt 0 (settling moves the clock).
        # R3：移動はこの時間帯の中で終える。書き込むときは dt 0（時計は精算で進める）。
        c["dt"] = window.end - c["t"]
        effects = fill_ids(c.get("effects", []), n.ids)
        hits = n.pipeline.step3(book, now, c, effects, turn)
        if hits:
            log.info(
                "World advancement candidate failed step 3: %s / 世界の進行の候補が第 3 ステップを通らない",
                [h.code for h in hits],
            )
            continue
        code, shown_ = fairness(book, now, c, effects, by_id, q, taken, away=window.reason == "act")
        if code is not None:
            log.info("World advancement candidate failed %s / 世界の進行の候補が規則を通らない", code)
            continue
        if c["origin"] == "director":
            taken["present" if shown_ else "absent"] += 1
        tries.append((_Try(c, effects, []), shown_))
        now = trial(book.world, now, c, effects)
    if not tries:
        return Prepared(called=True)
    rows = await n.pipeline.model_check(book, state, [t for t, _ in tries], turn, spend, span)
    items = []
    for (t, shown_), row in zip(tries, rows, strict=True):
        t.model = row
        if not t.ok:
            log.info(
                "World advancement candidate failed step 4: %s / 世界の進行の候補が第 4 ステップを通らない",
                [f for f, _ in t.fails],
            )
            continue
        items.append(Item(t.cand, t.effects, result("passed", 1, [], True), present=shown_))
    return Prepared(items, called=True)


# —— Writing (inside the commit transaction) / 書き込み（コミットのトランザクションの中） ——


def write(
    w: Writer,
    items: Sequence[Item],
    *,
    until: int | None = None,
    away: bool = False,
    log_: Sequence[Mapping[str, Any]] = (),
) -> list[Json]:
    """Write the candidates that passed the checks, by time. away (act transition): first settle to this item's time
    with the player not present. Before writing, judge step 3 and D1 again against the state at that time, dropping
    failures. Returns the events written.

    検査を通った候補を時刻順に書く。away（幕切り替え）：まずプレイヤー不在のままこの件の時刻まで精算する。書く前に
    その時点の状態で第 3 ステップと D1 をもう一度判定し、通らないものは捨てる。書いたイベントを返す。
    """
    book = w.book
    turn = TurnInput(character=None, player=None, act=WORLD_ACT).rules
    by_id = {e["eventId"]: e for e in log_}
    out: list[Json] = []
    for it in sorted(items, key=lambda x: int(x.cand["t"])):
        t = int(it.cand["t"])
        if until is not None and t > until:
            continue
        if away and t > w.state["t"]:
            w.settle(t, guard=False, present=False)
        t = max(t, int(w.state["t"]))
        cand = {**it.cand, "t": t, "dt": (until - t) if until is not None else 0}
        causes = [c for c in cand.get("causes", []) if c in by_id or c in book.beats]
        hits = judge(book.world, w.state, cand, it.effects, turn)
        if hits:
            log.info(
                "World advancement event failed step 3 before writing: %s"
                " / 世界の進行のイベントが書き込み前に第 3 ステップを通らない",
                [h.code for h in hits],
            )
            continue
        try:
            after = trial(book.world, w.state, cand, it.effects)
        except ValueError:
            continue
        if too_late(book, w.state, after):
            continue
        if not away and it.present != in_sight(book, cand, it.effects, w.player_place):
            # Whether it is in front of the player changed since judging (someone left): the quota was counted at
            # judging time, so drop it.
            # プレイヤーの目の前かどうかが判定時と変わった（人が立ち去った）：枠は判定時に数えたので捨てる。
            continue
        extra = {"beneficiary": cand["beneficiary"]} if cand.get("beneficiary") else {}
        out.append(
            w.add(
                w.full(
                    t=t,
                    dt=0,
                    actor=cand["actor"],
                    type=cand["type"],
                    origin=cand["origin"],
                    place=cand["place"],
                    summary=cand["summary"],
                    effects=it.effects,
                    check=it.check,
                    causes=causes,
                    **extra,
                )
            )
        )
    return out


def counts(events: Iterable[Mapping[str, Any]]) -> tuple[int, int]:
    """(number of character plan events, number of director events).

    （登場人物のプランのイベント数, ディレクターのイベント数）。
    """
    evs = list(events)
    return sum(1 for e in evs if e.get("origin") == "plan"), sum(1 for e in evs if e.get("origin") == "director")


# —— Tasks / タスク ——


async def busy(n: Narrator, pid: str, turn_id: str) -> bool:
    """A player turn is queued (D3: don't cut into the turn where the player is talking).

    プレイヤーのターンが積まれている（D3：プレイヤーが話しているターンに割り込まない）。
    """
    async with n.engine.connect() as c:
        got = await c.scalar(
            select(func.count())
            .select_from(turns)
            .where(
                turns.c.playthrough_id == pid,
                turns.c.turn_id != turn_id,
                turns.c.status.in_(("pending", "leased")),
                turns.c.kind.in_(("talk", "action", "plan", "choose", "confirm")),
            )
        )
    return bool(got)


async def run_world(n: Narrator, task: Task) -> Result:
    """The `world` task (key, mid): happens at the current time. If this act has already closed or the game has entered
    the ending, write nothing.

    `world` タスク（key、mid）：いま起きる。この幕がすでに閉じた、またはゲームがエンディングに入ったなら何も書かない。
    """
    from zoujin_backend.narrator.core import MAX_STALE, Planned, Stale

    reason = str((task.request or {}).get("reason") or "mid")
    for _ in range(MAX_STALE):
        pt, state = await n.read(task.pid)
        book = n.library.version(pt["world_model_version"])
        if pt["act_end"] is not None or pt["status"] != "active":
            return await n._commit(task, pt["last_seq"], lambda w, b: Planned())
        async with n.engine.connect() as c:
            log_ = await store.event_log(c, task.pid, book.version)
        window = Window(reason, int(state["t"]), int(state["t"]))
        span = {"playthrough_id": task.pid, "turn_id": task.turn_id, "world_model_version": book.version}
        prepared = await prepare(
            n, book, state, log_, window, task.spend, span, busy=await busy(n, task.pid, task.turn_id)
        )

        def go(w: Writer, b: Book, items: list[Item] = prepared.items, log_: list[Json] = log_) -> Planned:
            written = write(w, items, log_=log_)
            plans, directed = counts(written)
            # Director events in front of the player: the summary becomes a line of 地の文 in commit.narration
            # (api-contract 3.4), with the player written as 「あなた」.
            # プレイヤーの目の前でのディレクターのイベント：要約を commit.narration の地の文 1 行にする
            # （api-contract 3.4）。プレイヤーは「あなた」と書く。
            lines = [
                as_you(b, w.state["role"], str(e["summary"]), period=True)
                for e in written
                if in_sight(b, e, e["effects"], w.player_place)
            ]
            info = {"reason": reason, "events": len(written)}
            extra = {"narration": lines} if lines else {}
            return Planned(info=info, extra=extra, world_events=plans, director_events=directed)

        try:
            return await n._commit(task, pt["last_seq"], go, spend=task.spend)
        except Stale:
            log.info("lastSeq changed; redoing %s / lastSeq が変わったのでやり直す", task.turn_id)
    raise RuntimeError(f"{task.turn_id}: lastSeq keeps changing / {task.turn_id}：lastSeq が変わり続けている")


__all__ = ["KIND", "MID_EVERY", "Item", "Prepared", "Window", "prepare", "run_world", "write"]
