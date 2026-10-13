"""Event-by-event simulation: the incremental interface used by the narrator (W-1, proposed by backend).

A run's state SimState is derived only from events: initial_state() gives the state before the opening, and after that
every event (the player's, the narrator's, the system events written by settle()) is applied with apply(). settle()
itself also first computes drafts of system events and then apply()s them one by one, so "replaying the event log from
initial_state()" and "computing event by event" give the same state (contract 3.1, eval E7).

The rules are the same as the whole-run simulation (sim.Sim.run); see docs/data/contracts.md 2.4.1, 2.5.1 and the
reference implementation's file header:

- At the same time, beats first (by order), then the deadline, events last. So the caller first settles to the event's
  t, then applies the event; the next settle's t2 is not earlier than this event's t.
- When a beat reaches its scheduled time: if its preconditions hold it happens (with a variant if one applies, or as
  registered if the player registered altered); if they fail it is rechecked after every step until window.latest,
  happening at that moment once they hold, and after latest it is written as prevented (時間切れ).
- A beat with outgoing delays / hastens edges whose preconditions fail when due is prevented on the spot, and its
  minutes are refunded downstream per 2.5.1; a beat scheduled past latest (late) is prevented on the spot with no
  refund.
- Deadline: when the clock reaches clock.deadline.t, onDeadline is judged on the state at that moment, and the rules
  that hold are written as one system event. If no rule holds, a system event with empty effects is still written:
  state is derived only from events, and it records that "the deadline has been settled".

- In one run, a beat without a result yet has only one kind of change (contract section 3, clarified in 1.6): delays
  and hastening add up as signed minutes, and a net of 0 removes the change; prevented replaces earlier changes; any
  other combination is reported as bad-state by check_effects() and raises ValueError in apply() (sim.merge_change).
- origin = "schedule" is used only for due beats (type beat, one beat result) and the deadline (type action, one per
  run, not earlier than the deadline).
- (1.7) If relocate has a spot, it is recorded in spots; without a spot, the spot is removed only when moving to a
  different place and kept within the same place (a beat first moves participants to the beat's place, and someone
  already standing there keeps their spot). Spots enter no judgement; they are for the backend to position people
  (contract 3.1).

Two things that only exist here and not in the whole-run simulation; none of the 24 simulations is affected:
① a change the player registers at t moves the scheduled time of a beat without a result yet to before t; that beat
  is judged at t (the whole-run simulation knows all changes from the start);
② while a downstream beat is already waiting on its preconditions, an upstream beat being prevented pushes its
  scheduled time later; it goes back to "not yet due" and is judged again at the new scheduled time.

イベントごとのシミュレーション：ナレーターが使う増分インターフェース（W-1、バックエンドの提案）。

1 回のプレイの状態 SimState はイベントからのみ導かれる：initial_state() がオープニング前の状態を与え、その後の
すべてのイベント（プレイヤーのもの、ナレーターのもの、settle() が書くシステムイベント）は apply() で適用する。
settle() 自身もまずシステムイベントの下書きを計算し、それを 1 件ずつ apply() するので、「イベントログを
initial_state() からリプレイする」ことと「イベントごとに計算する」ことは同じ状態になる（契約 3.1、評価 E7）。

ルールは一括シミュレーション（sim.Sim.run）と同じ。docs/data/contracts.md 2.4.1、2.5.1 と参照実装のファイル冒頭を
参照：

- 同時刻ではビート（order 順）、期限、イベントの順。したがって呼び出し側はまずイベントの t まで settle してから、
  そのイベントを apply する。次の settle の t2 はこのイベントの t より早くない。
- ビートが予定時刻に達したとき：前提条件が成り立てば起きる（バリアントがあればバリアントで、プレイヤーが
  altered を登録していれば登録どおりに演じる）。成り立たなければ window.latest まで各ステップの後に再確認し、
  成り立った時点で起き、latest を過ぎたら prevented（時間切れ）と書く。
- delays / hastens の出エッジを持つビートは、期限時に前提条件が成り立たなければその場で prevented になり、その
  分数は 2.5.1 に従って下流に戻される。予定時刻が latest を超えたもの（late）はその場で prevented になり、戻さない。
- 期限：時刻が clock.deadline.t に達したら、その時点の状態で onDeadline を判定し、成り立ったルールを 1 件の
  システムイベントとして書く。成り立つルールがなくても effects が空のシステムイベントを書く：状態はイベント
  からのみ導かれるので、これで「期限は精算済み」を記録する。

- 1 回のプレイで、まだ結果の出ていないビートへの変更は 1 種類だけ（契約第 3 節、1.6 で明記）：遅延と前倒しは
  符号付きの分数として足し、正味 0 なら取り除く。prevented はそれまでの変更を上書きする。それ以外の組み合わせは
  check_effects() が bad-state と報告し、apply() は ValueError を送出する（sim.merge_change）。
- origin = "schedule" は期限に達したビート（type beat、beat の結果 1 件）と期限（type action、1 プレイに 1 件、
  期限より早くない）にだけ使う。
- （1.7）relocate に spot があれば spots に記録する。spot がなければ、別の場所に移ったときだけ取り除き、同じ場所
  の中では動かさない（ビートはまず参加人物をビートの場所に移すが、すでにそこに立っている人は元の立ち位置を
  保つ）。立ち位置はどの判定にも入らず、バックエンドが人を配置するために使う（契約 3.1）。

一括シミュレーションにはなく、ここにだけある 2 点。24 回のシミュレーションはどれも影響を受けない：
① プレイヤーが t に登録した変更によって、まだ結果の出ていないビートの予定時刻が t より前に早まると、その
  ビートは t で判定する（一括シミュレーションは最初からすべての変更を知っている）；
② 下流のビートがすでに前提条件を待っているときに、上流が阻止されて予定時刻が後ろにずれると、それは「まだ期限
  前」に戻り、新しい予定時刻に改めて判定する。
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, NotRequired, TypedDict

from .sim import BIG, OCCURRED, Effect, Override, Sim, World, change_conflict, merge_change, role_of
from .visibility import sees

SCHEDULE = "schedule"  # Event.origin: due beats and the deadline / 期限に達したビートと期限
# 1.7: spot name (SpotId in data common.schema.json) / 立ち位置の名前（data common.schema.json の SpotId）
SPOT = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*")


class SimState(TypedDict):
    """A run's state up to some event, storable directly as JSON. Produced only by initial_state() and apply().

    1 回のプレイの、あるイベントまでの状態で、そのまま JSON として保存できる。initial_state() と apply() だけが作る。
    """

    worldModelVersion: str
    role: str
    t: int  # Clock = max(previous clock, each event's t + dt) / 時刻 = max(前の時刻, 各イベントの t + dt)
    cursor: int | None  # t of the last event; None before any event / 最後のイベントの t。まだなければ None
    seq: int  # How many events have been applied (WorldState.asOfSeq) / 適用したイベント数
    vars: dict[str, Any]  # Every stateVar / すべての stateVar
    # Portable items (and items someone holds at the opening) → who holds them now
    # portable なアイテム（とオープニングで誰かが持っているアイテム）→ 今誰が持っているか
    holdings: dict[str, str | None]
    locations: dict[str, str]  # Character → place / 登場人物 → 場所
    # (1.7) Character → assigned spot; state saved before 1.7 does not have this
    # （1.7）登場人物 → 指定された立ち位置。1.7 より前に保存された状態にはこの項目がない
    spots: NotRequired[dict[str, str]]
    # Character → facts learned at runtime (in the order learned, no duplicates)
    # 登場人物 → 実行時に知った事実（知った順、重複なし）
    knowledge: dict[str, list[str]]
    # factId → RunFact (madeBy is None when there is no event ID) / madeBy はイベント ID がなければ None
    runFacts: dict[str, dict[str, Any]]
    promises: dict[str, dict[str, Any]]  # promiseId → StoryPromise (same as above / 同上)
    beats: dict[str, str]  # Beats with a result: happened / altered / prevented / 結果の出たビート
    times: dict[str, int]  # When they happened (happened / altered) / 起きた時刻
    variants: dict[str, str]  # Beat played as a variant → variant ID / バリアントで演じたビート → バリアント ID
    # This run's changes to beats, in order of registration (sc.beats in the reference implementation)
    # このプレイでのビートへの変更、登録順（参照実装の sc.beats）
    overrides: dict[str, Override]
    deadline: bool  # The deadline has been settled / 期限は精算済み


class Draft(TypedDict):
    """A draft system event written by settle(). event is a subset of the contract's Event; B-0 fills in eventId, seq,
    summary and so on before writing it to the database.

    settle() が書くシステムイベントの下書き。event は契約の Event のサブセットで、B-0 が eventId、seq、summary
    などを補ってから DB に書く。
    """

    event: dict[str, Any]
    beat: str | None  # Which beat (B-0 uses it for the summary); None for the deadline / どのビートか。期限は None
    variant: str | None  # Which variant it was played as / どのバリアントで演じたか
    # Why it was prevented, one Japanese sentence; B-0 writes it into check.reason
    # prevented の理由。日本語の一文で、B-0 が check.reason に書く
    reason: str | None
    reasonCode: str | None  # late / overridden / requires / precondition / expired


type Emit = Callable[[Draft], None]
type Bad = Callable[[int, str, str], None]


class Problem(TypedDict):
    """One problem reported by check_effects().

    check_effects() が報告する問題 1 件。
    """

    index: int  # Index of the effect / 何番目の effect か
    code: str
    message: str
    # valueRequires note (Japanese); the narrator uses it for reason / valueRequires の note（日本語）
    note: NotRequired[str]


REASONS = {
    "late": "時間切れ（予定の時刻が刻限を過ぎた）",
    "overridden": "この局の出来事で起きなくなった",
    "requires": "前の出来事が起きなかった",
    "precondition": "その時点で前提が成り立たなかった",
    "expired": "前提が成り立たないまま時間切れになった",
    "expired-requires": "前の出来事が起きないまま時間切れになった",
}


class _Sim(Sim):
    """settle() computes the schedule many times, and the result does not change while the change list does not, so
    cache by content. Callers must not modify the returned dict / set.

    settle() ではスケジュールを何度も計算するが、変更リストが同じなら結果も同じなので、内容でキャッシュする。
    返した dict / set を呼び出し側は変更してはいけない。
    """

    def __init__(self, world: World) -> None:
        super().__init__(world)
        self._cache: dict[tuple[str, bool], tuple[dict[str, int], set[str]]] = {}

    def schedule(self, over: Mapping[str, Override], _floor: bool = True) -> tuple[dict[str, int], set[str]]:
        key = (json.dumps(over, sort_keys=True, ensure_ascii=False), _floor)
        if key not in self._cache:
            self._cache[key] = super().schedule(over, _floor)
        return self._cache[key]


def initial_state(world: World, role_id: str) -> SimState:
    """The state before this role's opening: clock 0, initial variable values (var.player.location = startPlace,
    var.act.current = startAct), characters at initialPlace, items in the hands of whoever has them in
    Character.items and Role.items. The caller then settles to the role's startT.

    このロールのオープニング前の状態：時刻 0、変数の初期値（var.player.location = startPlace、var.act.current =
    startAct）、登場人物は initialPlace に、アイテムは Character.items、Role.items の持ち主の手にある。呼び出し側は
    続けてロールの startT まで settle する。
    """
    role = role_of(world, role_id)
    vars_ = {v["id"]: v["default"] for v in world["stateVars"]}
    vars_["var.player.location"] = role["startPlace"]
    if "startAct" in role and "var.act.current" in vars_:
        vars_["var.act.current"] = role["startAct"]
    holdings: dict[str, str | None] = {it["id"]: None for it in world.get("items", []) if it.get("portable")}
    for c in world["characters"]:
        for it in c.get("items", []):
            holdings[it] = c["id"]
    for it in role.get("items") or []:
        holdings[it] = "player"
    return {
        "worldModelVersion": world["worldModelVersion"],
        "role": role_id,
        "t": 0,
        "cursor": None,
        "seq": 0,
        "vars": vars_,
        "holdings": holdings,
        "locations": {c["id"]: c["initialPlace"] for c in world["characters"]},
        "spots": {},
        "knowledge": {},
        "runFacts": {},
        "promises": {},
        "beats": {},
        "times": {},
        "variants": {},
        "overrides": {},
        "deadline": False,
    }


def flat(state: SimState) -> dict[str, Any]:
    """The view used to evaluate conditions: variables plus item holders (the reference implementation keeps both in
    one dict).

    条件の評価に使うビュー：変数にアイテムの持ち主を加えたもの（参照実装は両者を同じ dict に入れている）。
    """
    return {**state["holdings"], **state["vars"]}


def apply(world: World, state: SimState, event: Mapping[str, Any]) -> SimState:
    """Applies one event and returns the new state (the one passed in is not changed). Uses the event's t, dt,
    origin, type, effects, and eventId, seq if present.

    In a system event with origin = "schedule", a beat effect is the beat's result; in other events it is a change for
    this run (delayed / hastened / prevented / altered, merged with sim.merge_change), and to = "happened" is not
    defined by the contract and raises ValueError.
    Other invalid input also raises ValueError; the narrator should block it first with check_effects():
    - a non-schedule event preceded by beats or a deadline not yet settled (not settled to its t first; after the
      previous event at the same time, settle again too, since it may make a beat waiting on its preconditions hold).
      When replaying an event log, this catches missing system events;
    - an event with seq where seq is not the previous one + 1;
    - a schedule event that is not a due beat or the deadline, or the deadline written a second time or earlier than
      the deadline.

    イベントを 1 件適用し、新しい状態を返す（渡された状態は変えない）。event の t、dt、origin、type、effects、
    あれば eventId、seq を使う。

    origin = "schedule" のシステムイベントでは、beat 効果はビートの結果。それ以外のイベントではこのプレイでの変更
    （delayed / hastened / prevented / altered、sim.merge_change で統合）で、to = "happened" は契約で定義されて
    おらず ValueError を送出する。
    ほかの不正な箇所も ValueError を送出する。ナレーターは先に check_effects() で弾くべき：
    - schedule でないイベントの前に、まだ精算していないビートや期限がある（先にその t まで settle していない。
      同時刻の前のイベントの後にも再び settle が必要で、それによって前提条件待ちのビートが成り立つことがある）。
      イベントログのリプレイ時には、これで書き漏れたシステムイベントを検出できる；
    - seq を持つイベントで、seq が前のもの + 1 でない；
    - schedule イベントが期限に達したビートでも期限でもない、または期限を 2 回書いた、期限より早い。
    """
    _same_world(world, state)
    if event.get("origin") != SCHEDULE and (state["cursor"] is None or event["t"] >= state["cursor"]):
        due = settle(world, state, event["t"])[0]
        if due:
            what = ", ".join(d["beat"] or "deadline" for d in due)
            raise ValueError(
                f"Not yet settled before t={event['t']}: {what}; settle to {event['t']} first, then apply"
                f" / t={event['t']} より前に未精算の {what} がある。先に {event['t']} まで settle してから apply"
            )
    return _apply(_Sim(world), state, event)


def _apply(sim: Sim, state: SimState, event: Mapping[str, Any]) -> SimState:
    t, dt = event["t"], event.get("dt", 0)
    if state["cursor"] is not None and t < state["cursor"]:
        raise ValueError(f"The event's t goes backwards / イベントの t が逆行している: {t} < {state['cursor']}")
    if "seq" in event and event["seq"] != state["seq"] + 1:
        raise ValueError(
            f"seq is not consecutive: {event['seq']}, previous was {state['seq']}"
            f" / seq が連続していない：{event['seq']}、前は {state['seq']}"
        )
    system = event.get("origin") == SCHEDULE
    if system:
        _check_schedule_event(sim, state, event)
    s = copy.deepcopy(state)
    eid = event.get("eventId")
    for e in event["effects"]:
        _apply_effect(sim, s, e, t, system, eid)
    if system and event.get("type") == "action":  # Deadline / 期限
        s["deadline"] = True
    s["t"] = max(s["t"], t + dt)
    s["cursor"] = t
    s["seq"] += 1
    return s


def _check_schedule_event(sim: Sim, state: SimState, event: Mapping[str, Any]) -> None:
    """Contract section 3 (clarified in 1.6): origin = "schedule" is used only for due beats and the deadline; other
    system events do not use it.

    契約第 3 節（1.6 で明記）：origin = "schedule" は期限に達したビートと期限にだけ使い、ほかのシステムイベントは
    使わない。
    """
    ty = event.get("type")
    if ty == "beat":
        n = sum(1 for e in event["effects"] if e["op"] == "beat")
        if n != 1:
            raise ValueError(
                f"A due-beat event must have exactly one beat effect; this one has {n}"
                f" / 期限に達したビートのイベントには beat 効果がちょうど 1 件必要。ここでは {n} 件"
            )
    elif ty == "action":
        dl = sim.world["clock"]["deadline"]["t"]
        if state["deadline"]:
            raise ValueError(
                "The deadline has already been settled: only one deadline event per run"
                " / 期限は精算済み：期限イベントは 1 プレイに 1 件だけ"
            )
        if event["t"] < dl:
            raise ValueError(
                f"The deadline event's t={event['t']} is earlier than the deadline {dl}"
                f" / 期限イベントの t={event['t']} が期限 {dl} より早い"
            )
    else:
        raise ValueError(
            f"origin = schedule is used only for due beats (type beat) and the deadline (type action), not {ty!r}"
            f" / origin = schedule は期限に達したビート（type beat）と期限（type action）にだけ使う。{ty!r} は不可"
        )


def _apply_effect(sim: Sim, s: SimState, e: Effect, t: int, system: bool, eid: str | None) -> None:
    op = e["op"]
    if op == "set":
        s["vars"][e["var"]] = e["value"]
    elif op == "inc":
        v = sim.svars[e["var"]]
        s["vars"][e["var"]] = max(v.get("min", -BIG), min(v.get("max", BIG), s["vars"][e["var"]] + e["by"]))
    # 1.7: with a spot, stand there; without one, remove it only on a change of place, keep it within the same place
    # (contract 3.1)
    # 1.7：spot があればそこに立つ。なければ場所が変わったときだけ取り除き、同じ場所の中では動かさない（契約 3.1）
    elif op == "relocate":
        c, spots = e["character"], s.setdefault("spots", {})
        if "spot" in e:
            spots[c] = e["spot"]
        elif s["locations"].get(c) != e["place"]:
            spots.pop(c, None)
        s["locations"][c] = e["place"]
    elif op == "hold":
        s["holdings"][e["item"]] = e["to"]
    elif op == "learn":
        known = s["knowledge"].setdefault(e["character"], [])
        if e["fact"] not in known:
            known.append(e["fact"])
    elif op == "improv":
        if e["factId"] in s["runFacts"]:
            raise ValueError(f"Duplicate improvised fact / 即興設定の重複: {e['factId']}")
        s["runFacts"][e["factId"]] = {
            "factId": e["factId"],
            "character": e["character"],
            "statement": e["statement"],
            "madeBy": eid,
        }
    elif op == "promise":
        _apply_promise(s, e, eid)
    elif op == "beat":
        if system:
            _apply_beat_result(sim, s, e, t, eid)
        else:
            _apply_beat_change(s, e)
    else:
        raise ValueError(f"Unknown effect / 未知の効果: {op}")


def _apply_promise(s: SimState, e: Effect, eid: str | None) -> None:
    pid = e.get("promiseId")
    if not pid:
        raise ValueError("A submitted promise effect needs a promiseId / 提出する promise 効果には promiseId が必要")
    if e["change"] == "made":
        if pid in s["promises"]:
            raise ValueError(f"Duplicate promise / 約束の重複: {pid}")
        made: dict[str, Any] = {"promiseId": pid, "from": e["from"], "to": e["to"], "text": e["text"]}
        for k in ("due", "template"):
            if k in e:
                made[k] = copy.deepcopy(e[k])
        made["status"], made["madeBy"] = "open", eid
        s["promises"][pid] = made
        return
    p = s["promises"].get(pid)
    if p is None or p["status"] != "open":
        raise ValueError(
            f"Only an open promise can become {e['change']} / open の約束だけが {e['change']} になれる: {pid}"
        )
    p["status"], p["resolvedBy"] = e["change"], eid


def _apply_beat_result(sim: Sim, s: SimState, e: Effect, t: int, eid: str | None) -> None:
    bid, to = e["beat"], e["to"]
    if bid in s["beats"]:
        raise ValueError(f"{bid} already has a result / すでに結果がある ({s['beats'][bid]})")
    if to in OCCURRED:
        s["beats"][bid], s["times"][bid] = to, t
        if to == "altered":
            if e.get("note") in {v["id"] for v in sim.beats[bid].get("variants", [])}:
                s["variants"][bid] = e["note"]
            for x in e.get("outcomes", []):
                _apply_effect(sim, s, x, t, True, eid)
    elif to == "prevented":
        # 2.5.1: a beat with outgoing delays / hastens edges prevented because its preconditions failed when due has
        # its minutes refunded downstream (auto in the reference implementation's run())
        # 2.5.1：delays / hastens の出エッジを持つビートが期限時に前提条件不成立で阻止されたら、その分数を下流に戻す
        # （参照実装 run() の auto）
        late = sim.schedule(s["overrides"])[1]
        if bid in sim.timed and bid not in late and bid not in s["overrides"] and sim.requires_met(bid, s["beats"]):
            s["overrides"][bid] = {"to": "prevented"}
        s["beats"][bid] = "prevented"
    else:
        raise ValueError(
            f"beat in a system event can only be happened / altered / prevented"
            f" / システムイベントの beat は happened / altered / prevented のみ: {to}"
        )


def _apply_beat_change(s: SimState, e: Effect) -> None:
    bid = e["beat"]
    if e["to"] == "happened":
        raise ValueError(
            f"{{op: beat, to: happened}} in a non-system event is not defined by the contract"
            f" / システムイベント以外での {{op: beat, to: happened}} は契約で定義されていない: {bid}"
        )
    if bid in s["beats"]:
        raise ValueError(
            f"{bid} already has a result ({s['beats'][bid]}) and cannot be changed"
            f" / {bid} はすでに結果がある（{s['beats'][bid]}）ので変更できない"
        )
    merge_change(s["overrides"], e)


def settle(
    world: World, state: SimState, t2: int | None, *, player_present: bool = True
) -> tuple[list[Draft], SimState]:
    """Advance the clock to t2: settle, in order, the beats and deadline scheduled at ≤ t2. With t2 = None, settle
    until every beat has a result and the deadline has been settled.

    player_present=False: for this stretch the player always counts as absent, and even a beat that falls on
    `var.player.location` writes no learn for the player (contract 2.1 ②). Used in step 3 of an act switch (2.8.1):
    at that point the player's place has not changed yet, but they are already gone.

    Returns (drafts of system events, the settled state). The settled state = the drafts applied in order to the state
    passed in. The state passed in is not changed.

    時刻を t2 まで進める：予定時刻 ≤ t2 のビートと期限を順に精算する。t2 = None なら、すべてのビートに結果が出て
    期限も精算されるまで精算する。

    player_present=False：この区間ではプレイヤーは常に不在とみなし、ビートが `var.player.location` に落ちても
    プレイヤーに learn を書かない（契約 2.1 ②）。幕切り替えの第 3 段階で使う（2.8.1）：このときプレイヤーの場所は
    まだ変わっていないが、本人はもういない。

    （システムイベントの下書き, 精算後の状態）を返す。精算後の状態 = 下書きを順に、渡された状態へ apply したもの。
    渡された状態は変えない。
    """
    _same_world(world, state)
    sim = _Sim(world)
    s = state
    drafts: list[Draft] = []
    end = BIG * 2 if t2 is None else t2

    def emit(d: Draft) -> None:
        nonlocal s
        s = _apply(sim, s, d["event"])
        drafts.append(d)

    def current() -> SimState:
        return s

    now = s["cursor"] if s["cursor"] is not None else -BIG
    # Beats past their scheduled time without a result are waiting on preconditions (judged by the previous settle;
    # the kinds that get a result from a single judgement are never waiting)
    # 予定時刻を過ぎてまだ結果のないビートは前提条件を待っている（前回の settle で判定済み。1 回の判定で結果が出る
    # 種類のものは待たない）
    seen = {b for b, tb in _schedule(sim, s).items() if tb <= now} - _special(sim, s)
    if s["cursor"] is not None:
        _recheck(sim, now, seen, emit, current, player_present)

    while True:
        sched = _schedule(sim, s)
        # Beats whose scheduled time was pushed later go back to "not yet due"; the kinds that get a result from a
        # single judgement (_special) are never waiting
        # 予定時刻が後ろにずれたものは「まだ期限前」に戻る。1 回の判定で結果が出る種類（_special）は待たない
        seen &= {b for b, tb in sched.items() if tb <= now}
        seen -= _special(sim, s)
        items: list[tuple[int, int, int, str, str | None]] = []
        for b, tb in sched.items():
            order = sim.beats[b]["order"]
            if b not in seen:
                if max(tb, now) <= end:
                    items.append((max(tb, now), 0, order, "beat", b))
            elif b not in sim.timed:
                latest = sim.beats[b]["window"]["latest"]
                if latest < end:
                    items.append((max(latest, now), 3, order, "expire", b))
        dl = world["clock"]["deadline"]["t"]
        if not s["deadline"] and dl <= end:
            items.append((max(dl, now), 1, 0, "deadline", None))
        if not items:
            break
        tt, _, _, kind, bid = min(items)
        now = tt
        if kind == "deadline" or bid is None:
            emit(_deadline_draft(sim, world, s, tt))
        elif kind == "beat":
            seen.add(bid)
            _first_check(sim, s, bid, tt, emit, player_present)
        else:
            code = "expired" if sim.requires_met(bid, s["beats"]) else "expired-requires"
            emit(_prevented(sim, bid, tt, code))
        _recheck(sim, tt, seen, emit, current, player_present)
    return drafts, s


def _schedule(sim: Sim, s: SimState) -> dict[str, int]:
    """This run's scheduled times of the beats without a result yet (2.5.1).

    まだ結果のないビートの、このプレイでの予定時刻（2.5.1）。
    """
    shift = sim.schedule(s["overrides"])[0]
    return {b: x["window"]["canonical"] + shift.get(b, 0) for b, x in sim.beats.items() if b not in s["beats"]}


def _special(sim: Sim, s: SimState) -> set[str]:
    """Beats that always get a result from a single judgement: those with outgoing delays / hastens edges, those
    scheduled past latest, and those the player registered as prevented.

    1 回の判定で必ず結果が出るビート：delays / hastens の出エッジを持つもの、予定時刻が latest を超えたもの、
    プレイヤーが prevented を登録したもの。
    """
    late = sim.schedule(s["overrides"])[1]
    return {
        b
        for b in sim.beats
        if b not in s["beats"] and (b in sim.timed or b in late or s["overrides"].get(b, {}).get("to") == "prevented")
    }


def _first_check(sim: Sim, s: SimState, b: str, t: int, emit: Emit, player_present: bool) -> None:
    """A beat reaches its scheduled time (_step1 in the reference implementation).

    ビートが予定時刻に達した（参照実装の _step1）。
    """
    x = sim.beats[b]
    late = sim.schedule(s["overrides"])[1]
    if b in late:
        emit(_prevented(sim, b, t, "late"))
    elif s["overrides"].get(b, {}).get("to") == "prevented":
        emit(_prevented(sim, b, t, "overridden"))
    elif b not in sim.timed and t > x["window"]["latest"]:
        emit(_prevented(sim, b, t, "expired" if sim.requires_met(b, s["beats"]) else "expired-requires"))
    elif not sim.requires_met(b, s["beats"]):
        # The reference implementation records blocked and stops checking; for the ending it equals prevented
        # 参照実装は blocked と記録して再確認しない。結末の上では prevented と同じ
        if b in sim.timed:
            emit(_prevented(sim, b, t, "requires"))
    elif not sim.holds(x["preconditions"], flat(s)):
        if b in sim.timed:
            emit(_prevented(sim, b, t, "precondition"))
    else:
        emit(_occur_draft(sim, s, b, t, player_present))


def _recheck(
    sim: Sim, t: int, seen: set[str], emit: Emit, current: Callable[[], SimState], player_present: bool
) -> None:
    """After every step, recheck in order the beats waiting on preconditions; those that now hold happen at this time
    t; repeat until nothing changes (_recheck in the reference implementation).

    各ステップの後、前提条件を待っているビートを order 順に再確認し、成り立ったものはこの時刻 t に起きる。変化が
    なくなるまで繰り返す（参照実装の _recheck）。
    """
    changed = True
    while changed:
        changed = False
        s = current()
        sched, special = _schedule(sim, s), _special(sim, s)
        waiting = sorted(
            (
                b
                for b in seen
                if b in sched and sched[b] <= t and b not in special and t <= sim.beats[b]["window"]["latest"]
            ),
            key=lambda b: sim.beats[b]["order"],
        )
        for b in waiting:
            s = current()
            if (
                b not in s["beats"]
                and sim.requires_met(b, s["beats"])
                and sim.holds(sim.beats[b]["preconditions"], flat(s))
            ):
                emit(_occur_draft(sim, s, b, t, player_present))
                changed = True


def _occur_draft(sim: Sim, s: SimState, b: str, t: int, player_present: bool) -> Draft:
    """A beat happens: first move the participants to the beat's place, then write the result (_occur in the
    reference implementation).

    ビートが起きる：まず参加人物をビートの場所に移し、それから結果を書く（参照実装の _occur）。
    """
    x = sim.beats[b]
    effects: list[dict[str, Any]] = [{"op": "relocate", "character": p, "place": x["place"]} for p in x["participants"]]
    o = s["overrides"].get(b, {})
    variant = None
    if o.get("to") == "altered":  # A player's event changed this beat in advance / プレイヤーのイベントが事前に変更
        effects.append({"op": "beat", "beat": b, "to": "altered", "outcomes": copy.deepcopy(o["outcomes"])})
    else:
        v = sim.variant_of(x, flat(s))
        if v is not None:  # 1.4: when due, play it differently per this run's state / 状態に応じて別の演じ方
            variant = v["id"]
            effects.append(
                {"op": "beat", "beat": b, "to": "altered", "outcomes": copy.deepcopy(v["outcomes"]), "note": v["id"]}
            )
        else:
            effects.append({"op": "beat", "beat": b, "to": "happened"})
            effects += copy.deepcopy(list(x["outcomes"]))
    # Player present: the player also learns the public facts (contract 2.1, 2.3, 1.7). Presence follows sees()
    # (1.12: for a beat with no participants, the same scene counts)
    # プレイヤーが在場：public な事実はプレイヤーも知る（契約 2.1、2.3、1.7）。在場かどうかは sees() に従う
    # （1.12：参加人物のないビートは同じシーンならよい）
    if player_present and sees(
        sim.world, s["vars"].get("var.player.location"), _system_event("beat", t, x["place"], effects)
    ):
        known = s["knowledge"].get("player", [])
        effects += [
            {"op": "learn", "character": "player", "fact": f["id"]}
            for f in sim.world["facts"]
            if f["trueFrom"] == b and f["visibility"] == "public" and f["id"] not in known
        ]
    return {
        "event": _system_event("beat", t, x["place"], effects),
        "beat": b,
        "variant": variant,
        "reason": None,
        "reasonCode": None,
    }


def _prevented(sim: Sim, b: str, t: int, code: str) -> Draft:
    x = sim.beats[b]
    return {
        "event": _system_event("beat", t, x["place"], [{"op": "beat", "beat": b, "to": "prevented"}]),
        "beat": b,
        "variant": None,
        "reason": REASONS[code],
        "reasonCode": code.removesuffix("-requires"),
    }


def _deadline_draft(sim: Sim, world: World, s: SimState, t: int) -> Draft:
    """Deadline: the onDeadline rules whose if holds, all judged on the state at the moment of the deadline; written
    even if none holds (empty effects).

    期限：onDeadline のうち if が成り立つルール。すべて期限の時点の状態で判定する。1 件も成り立たなくても書く
    （effects は空）。
    """
    dl = world["clock"]["deadline"]
    pre = flat(s)
    effects = [
        copy.deepcopy(e) for r in world["clock"].get("onDeadline", []) if sim.holds(r["if"], pre) for e in r["then"]
    ]
    wb = dl.get("watchBeat")
    place = str(sim.beats[wb]["place"] if wb in sim.beats else s["vars"]["var.player.location"])
    return {
        "event": _system_event("action", t, place, effects),
        "beat": None,
        "variant": None,
        "reason": None,
        "reasonCode": None,
    }


def _system_event(type_: str, t: int, place: str, effects: list[dict[str, Any]]) -> dict[str, Any]:
    return {"actor": "system", "type": type_, "origin": SCHEDULE, "t": t, "dt": 0, "place": place, "effects": effects}


def world_state(world: World, state: SimState, playthrough_id: str) -> dict[str, Any]:
    """Converts to the contract 3.1 WorldState. Promises or improvised facts without an event ID (a trial computation
    before commit) cannot be converted and raise ValueError.

    契約 3.1 の WorldState に変換する。イベント ID のない約束や即興設定（コミット前の試算）は変換できず、
    ValueError を送出する。
    """
    _same_world(world, state)
    for kind, xs in (("promises", state["promises"]), ("runFacts", state["runFacts"])):
        for k, x in xs.items():
            if x.get("madeBy") is None or ("resolvedBy" in x and x["resolvedBy"] is None):
                raise ValueError(
                    f"{k} in {kind} has no event ID (a trial state cannot be converted to WorldState)"
                    f" / {kind} の {k} にイベント ID がない（試算の状態は WorldState に変換できない）"
                )
    sim = _Sim(world)
    sched = _schedule(sim, state)
    beats: dict[str, str] = {}
    for b in sim.beats:
        if b in state["beats"]:
            beats[b] = state["beats"][b]
        else:
            to = state["overrides"].get(b, {}).get("to")
            beats[b] = to if to in ("delayed", "hastened") else "pending"
    return {
        "playthroughId": playthrough_id,
        "asOfSeq": state["seq"],
        "t": state["t"],
        "vars": copy.deepcopy(state["vars"]),
        "beats": beats,
        "schedule": sched,
        "knowledge": copy.deepcopy(state["knowledge"]),
        "locations": dict(state["locations"]),
        "spots": dict(state.get("spots", {})),
        "promises": copy.deepcopy(state["promises"]),
        "runFacts": copy.deepcopy(state["runFacts"]),
        "holdings": dict(state["holdings"]),
    }


def classify(world: World, state: SimState) -> str | None:
    """2.9: which class of world ending the current state falls into.

    2.9：今の状態がどの種類の世界の結末に当たるか。
    """
    return Sim(world).classify(flat(state))


def signature(world: World, state: SimState) -> dict[str, Any]:
    """2.9.1 ending signature: the final values of `endings.signature.vars`, and whether the `beats` happened as in the
    original story (happened; altered does not count).
    The ending's `world.signature` and the data's diversity statistics both use this one (key moments from the third
    onwards use it too). Empty when the world model defines no signature.

    2.9.1 結末のシグネチャ：`endings.signature.vars` の最終値と、`beats` が原作どおりに起きたか（happened。altered
    は数えない）。
    結末の `world.signature` も、データの多様性の統計もこれを使う（キーモーメントの 3 件目以降も使う）。世界
    モデルにシグネチャがなければ空。
    """
    sig = world.get("endings", {}).get("signature") or {}
    out: dict[str, Any] = {v: copy.deepcopy(state["vars"].get(v)) for v in sig.get("vars", [])}
    out |= {b: state["beats"].get(b) == "happened" for b in sig.get("beats", [])}
    return out


def predict(world: World, state: SimState) -> str | None:
    """Prediction (backend-design 2.5): assuming the player does nothing more, settle a copy of the state to the end,
    then classify.

    予測（backend-design 2.5）：プレイヤーがこれ以上何もしないとして、状態のコピーを最後まで精算してから分類する。
    """
    return classify(world, settle(world, state, None)[1])


def arrival_delta(world: World, state: SimState, effects: Sequence[Effect], t: int) -> dict[str, Any]:
    """S-066 ①, contract 2.10: if effects are submitted at t, how many minutes later (+) or earlier (−) Melos reaches
    the execution ground (watchBeat), and whether he still makes it after doing it.
    The same algorithm as Sim.arrival_delta: minutes are computed in a world with window.latest removed, by settling to
    the end both with and without doing it and comparing the scheduled times.
    state must be settled to t first. Raises ValueError when effects cannot be merged with the registered changes
    (check_effects' bad-state).

    S-066 ①、契約 2.10：t に effects を提出すると、メロスが刑場（watchBeat）に何分遅れる（+）か早まる（−）か、
    実行後もまだ間に合うか。
    Sim.arrival_delta と同じアルゴリズム：分数は window.latest を外した世界で、実行した場合としない場合をそれぞれ
    最後まで精算して予定時刻を比べる。
    state は先に t まで settle しておく。effects が登録済みの変更と統合できない（check_effects の bad-state）ときは
    ValueError を送出する。
    """
    wb = world["clock"]["deadline"].get("watchBeat")
    loose = {**world, "beats": [{**b, "window": {**b["window"], "latest": BIG}} for b in world["beats"]]}
    event = {"t": t, "dt": 0, "origin": "action", "effects": list(effects)}
    after = apply(world, state, event)
    lsim = _Sim(loose)
    a = lsim.schedule(settle(loose, state, None)[1]["overrides"])[0]
    b = lsim.schedule(settle(loose, after, None)[1]["overrides"])[0]
    real = settle(world, after, None)[1]
    return {"minutes": b.get(wb, 0) - a.get(wb, 0), "inTime": real["beats"].get(wb) in OCCURRED}


def check_effects(world: World, state: SimState, effects: Iterable[Effect], origin: str | None) -> list[Problem]:
    """Whether the effects themselves are valid: referenced IDs exist, values match their types, ops are used
    correctly. When origin is not "schedule" (neither the narrator's candidate events nor director events are),
    {op: beat, to: happened} and changing a beat that already has a result are also reported, and
    StateVar.valueRequires (contract 1.6, C-16) is checked. Distinguished by origin, not actor: director events also
    have actor system. Only shape and references are checked; R1〜R7 belong to the narrator.

    効果そのものが妥当か：参照する ID が存在し、値が型に合い、op の使い方が正しいか。origin が "schedule" でない
    とき（ナレーターの候補イベントもディレクターイベントもそうでない）、{op: beat, to: happened} とすでに結果の
    出たビートの変更も報告し、StateVar.valueRequires（契約 1.6、C-16）で判定する。actor ではなく origin で区別
    する：ディレクターイベントの actor も system。調べるのは形と参照だけで、R1〜R7 はナレーターの担当。
    """
    effects = list(effects)
    sim = Sim(world)
    chars = set(sim.chars)
    places = {p["id"] for p in world["places"]}
    facts = {f["id"] for f in world["facts"]}
    items = {it["id"]: it for it in world.get("items", [])}
    templates = {x["id"] for c in world["characters"] for x in c.get("promiseTemplates", [])}
    run_facts = set(state["runFacts"])
    promises = {k: p["status"] for k, p in state["promises"].items()}
    # Earlier changes in the same batch count too (merge_change) / 同じバッチ内の前の変更も数える（merge_change）
    over = copy.deepcopy(state["overrides"])
    system = origin == SCHEDULE
    out: list[Problem] = []

    def bad(i: int, code: str, msg: str) -> None:
        out.append({"index": i, "code": code, "message": msg})

    def who(x: Any) -> bool:
        return x == "player" or x in chars

    for i, e in enumerate(effects):
        op = e.get("op")
        if op == "set":
            msg = _check_value(sim, places, e.get("var"), e.get("value"))
            if msg:
                bad(i, "bad-value", msg)
        elif op == "inc":
            v = sim.svars.get(e.get("var", ""))
            if v is None or v["type"] not in ("int", "minutes"):
                bad(
                    i,
                    "bad-op",
                    f"inc only works on int and minutes variables / inc は int、minutes の変数専用: {e.get('var')}",
                )
            elif not isinstance(e.get("by"), int) or isinstance(e.get("by"), bool):
                bad(
                    i, "bad-value", f"inc's by must be an integer / inc の by は整数でなければならない: {e.get('by')!r}"
                )
        elif op == "relocate":
            if e.get("character") not in chars or e.get("place") not in places:
                bad(
                    i,
                    "unknown-id",
                    f"relocate references something that does not exist / relocate の参照先が存在しない:"
                    f" {e.get('character')} → {e.get('place')}",
                )
            if "spot" in e and not (isinstance(e["spot"], str) and SPOT.fullmatch(e["spot"])):
                bad(
                    i,
                    "bad-value",
                    f"relocate's spot must be a spot name from the layout (lowercase slug)"
                    f" / relocate の spot はレイアウトの立ち位置名（小文字の slug）でなければならない: {e['spot']!r}",
                )
        elif op == "hold":
            it = items.get(e.get("item", ""))
            if not it or not it.get("portable"):
                bad(
                    i, "bad-op", f"hold only works on portable items / hold は portable なアイテム専用: {e.get('item')}"
                )
            for k in ("to", "from"):
                if k in e and e[k] is not None and not who(e[k]):
                    bad(
                        i,
                        "unknown-id",
                        f"hold.{k} must be player, a character ID or null"
                        f" / hold.{k} は player、登場人物 ID、null のいずれか: {e[k]!r}",
                    )
            if "to" not in e:
                bad(
                    i,
                    "bad-op",
                    "hold needs to (null = taken away, used up) / hold には to が必要（null = 取られた、使い切った）",
                )
        elif op == "learn":
            if not who(e.get("character")):  # 1.7: the player can learn too (contract 2.1) / プレイヤーも知れる
                bad(
                    i,
                    "unknown-id",
                    f"learn's character does not exist / learn の登場人物が存在しない: {e.get('character')}",
                )
            if e.get("fact") not in facts and e.get("fact") not in run_facts:
                bad(i, "unknown-id", f"learn's fact does not exist / learn の事実が存在しない: {e.get('fact')}")
        elif op == "improv":
            if e.get("character") not in chars:
                bad(
                    i,
                    "unknown-id",
                    f"improv's character does not exist / improv の登場人物が存在しない: {e.get('character')}",
                )
            if e.get("factId") in run_facts:
                bad(i, "duplicate-id", f"Duplicate improvised fact / 即興設定の重複: {e.get('factId')}")
            run_facts.add(e.get("factId", ""))
        elif op == "promise":
            _check_promise(i, e, who, sim, templates, promises, bad)
        elif op == "beat":
            _check_beat(i, e, sim, state, over, system, bad)
        else:
            bad(i, "bad-op", f"Unknown effect / 未知の効果: {op}")
    # Once every shape is right, check valueRequires, following Sim.value_requires (state before each effect)
    # 形がすべて正しければ valueRequires で判定する。規則は Sim.value_requires どおり（各 effect の前の状態で）
    if not system and not out:
        cur = flat(state)
        for i, e in enumerate(effects):
            for x in sim.value_requires([e], cur, origin):
                msg = f"{x['var']} = {x['value']!r} requires / には次が必要: {x['when']}"
                out.append({"index": i, "code": "value-requires", "message": msg, "note": x["note"]})
            sim.apply([e], cur)
    return out


def _check_value(sim: Sim, places: set[str], var: Any, value: Any) -> str | None:
    v = sim.svars.get(var)
    if v is None:
        return f"Undefined state variable / 未定義の状態変数: {var}"
    ty = v["type"]
    if ty == "enum" and value not in v["values"]:
        return f"{var}: value {value!r} is not in the enum / 値が列挙にない: {v['values']}"
    if ty == "bool" and not isinstance(value, bool):
        return f"{var} needs a bool, got / bool が必要だが次を受け取った: {value!r}"
    if ty in ("int", "minutes"):
        if not isinstance(value, int) or isinstance(value, bool):
            return f"{var} needs an integer, got / 整数が必要だが次を受け取った: {value!r}"
        if not v.get("min", -BIG) <= value <= v.get("max", BIG):
            return f"{var}: value {value} is out of range / 値が範囲外: {v.get('min')}〜{v.get('max')}"
    if ty == "place" and value not in places:
        return f"{var} needs a place ID, got / 場所 ID が必要だが次を受け取った: {value!r}"
    return None


def _check_promise(
    i: int, e: Effect, who: Callable[[Any], bool], sim: Sim, templates: set[str], promises: dict[str, str], bad: Bad
) -> None:
    change, pid = e.get("change"), e.get("promiseId")
    if change == "made":
        for k in ("from", "to"):
            if not who(e.get(k)):
                bad(
                    i,
                    "unknown-id",
                    f"promise.{k} must be player or a character ID"
                    f" / promise.{k} は player か登場人物 ID でなければならない: {e.get(k)!r}",
                )
        if not e.get("text"):
            bad(i, "bad-value", "promise made needs text / promise made には text が必要")
        if e.get("template") and e["template"] not in templates:
            bad(i, "unknown-id", f"promise.template does not exist / promise.template が存在しない: {e['template']}")
        if e.get("due", {}).get("beat") and e["due"]["beat"] not in sim.beats:
            bad(i, "unknown-id", f"promise.due.beat does not exist / promise.due.beat が存在しない: {e['due']['beat']}")
        if pid and pid in promises:
            bad(i, "duplicate-id", f"Duplicate promise / 約束の重複: {pid}")
        if pid:
            promises[pid] = "open"
    elif change in ("kept", "broken", "voided"):
        if not pid or promises.get(pid) != "open":
            bad(
                i, "bad-state", f"Only an open promise can become {change} / open の約束だけが {change} になれる: {pid}"
            )
        else:
            promises[pid] = change
    else:
        bad(i, "bad-value", f"Unrecognized promise.change / 不明な promise.change: {change!r}")


def _check_beat(
    i: int, e: Effect, sim: Sim, state: SimState, over: dict[str, Override], system: bool, bad: Bad
) -> None:
    bid, to = e.get("beat"), e.get("to")
    if bid not in sim.beats:
        bad(i, "unknown-id", f"Beat does not exist / ビートが存在しない: {bid}")
        return
    if to not in ("happened", "prevented", "delayed", "hastened", "altered"):
        bad(i, "bad-value", f"Unrecognized beat.to / 不明な beat.to: {to!r}")
        return
    ok = True
    if to in ("delayed", "hastened"):
        m = e.get("minutes")
        if not isinstance(m, int) or isinstance(m, bool) or m < 0:
            bad(i, "bad-value", f"{to} needs minutes (an integer ≥ 0) / {to} には minutes（0 以上の整数）が必要: {m!r}")
            ok = False
    if to == "altered" and not system and not isinstance(e.get("outcomes"), list):
        bad(i, "bad-value", "altered needs outcomes (the changed result) / altered には outcomes（変更後の結果）が必要")
        ok = False
    if bid in state["beats"]:
        bad(i, "beat-has-result", f"{bid} already has a result / すでに結果がある ({state['beats'][bid]})")
    elif not system and to == "happened":
        bad(
            i,
            "beat-happened",
            f"A candidate event cannot make {bid} happen directly (due beats are settled by the system)"
            f" / 候補イベントは {bid} を直接起こせない（期限に達したビートはシステムが精算する）",
        )
    elif system and to in ("delayed", "hastened"):
        bad(
            i,
            "bad-value",
            f"beat in a system event can only be happened / altered / prevented"
            f" / システムイベントの beat は happened / altered / prevented のみ: {to}",
        )
    elif not system and ok:
        why = change_conflict(over.get(bid), e)
        if why:
            bad(i, "bad-state", f"{bid}: {why}")
        else:
            merge_change(over, e)


def _same_world(world: World, state: SimState) -> None:
    if world["worldModelVersion"] != state["worldModelVersion"]:
        raise ValueError(
            f"The state is for {state['worldModelVersion']} but the world model is {world['worldModelVersion']}"
            f" / 状態は {state['worldModelVersion']} のもので、世界モデルは {world['worldModelVersion']}"
        )
