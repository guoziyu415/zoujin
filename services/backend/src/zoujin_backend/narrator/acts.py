"""End of act and act transitions (B-3 item 4; api-contract 3.11, contract 2.8, 2.8.1).

- `act_ended`, pushed after the act closes (`pending.actEnd` after a disconnect): destinations filtered by role and
  `requires`, with subtitle, time, companions and the en-route either/or choice; 「この幕であなたが動かしたこと」; and
  how many more plans the player may state.
- The four steps of an act transition (2.8.1): the en-route choice event → the player's act-transition → settling to
  the target time with the player not present → the system's act-transition. Shared by choosing a given destination
  and by a plan that goes ahead; called inside the commit transaction while the game is locked (`Writer`).
- 「その頃」 (2.8.1 step 5): taken from the events settled in step 3, at most 3.

Only the world model and events are used here, never the player's own words. The plan paraphrase (`label`) is already
filtered before the call (`narrator/plans.py`).

幕末と幕切り替え（B-3 第 4 項。api-contract 3.11、契約 2.8、2.8.1）。

- 幕を閉じたあとにプッシュする `act_ended`（切断時は `pending.actEnd`）：行き先を役柄と `requires` で絞り込み、
  副題、時刻、同行者、道中の二択を付ける。「この幕であなたが動かしたこと」。プランをあと何回言えるか。
- 幕切り替えの 4 ステップ（2.8.1）：道中の二択のイベント → プレイヤーの act-transition → プレイヤー不在のまま
  目標時刻まで精算 → システムの act-transition。決まった行き先を選んだときと、プランが実行されるときで共用し、
  コミットのトランザクションの中、このゲームをロックしている間に呼ぶ（`Writer`）。
- 「その頃」（2.8.1 第 5 ステップ）：第 3 ステップで精算したイベントから取り、最大 3 件。

ここでは世界モデルとイベントだけを使い、プレイヤーの発話には触れない。プランの言い換え（`label`）は呼び出し前に
フィルター済み（`narrator/plans.py`）。
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from zoujin_backend.narrator.rules import Checked
from zoujin_backend.narrator.writer import Writer
from zoujin_backend.projection import as_you, committed
from zoujin_backend.world import Book
from zoujin_worldsim import SimState, arrival_delta, flat, world_state

log = logging.getLogger("zoujin.narrator")

Json = Any

PLAN_TRIES = 2  # at most 2 plans per end of act (api-contract 3.11 Freeform) / 1 回の幕末でプランは最大 2 回
RECAP_LINES = 4
RECAP_ITEMS = 3
# Destination effects hard-coded in the world model: statically checked by the data validation tool, so no model check.
# 世界モデルに固定で書かれた行き先の効果：データの検証ツールが静的に確認済みなので、モデルの検査は通さない。
CHECKER_EXIT = "world-exit"
PASSED_EXIT = {"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER_EXIT}


# —— Time and subtitle / 時刻と副題 ——


def schedule(book: Book, state: SimState) -> dict[str, int]:
    """The scheduled times in this game of beats that have no result yet (W-1 world_state's schedule).

    まだ結果の出ていないビートの、このゲームでの予定時刻（W-1 world_state の schedule）。
    """
    sched: dict[str, int] = world_state(book.world, state, "")["schedule"]
    return sched


def target_t(book: Book, state: SimState, t: int, align_to: str | None) -> int:
    """A destination's target time: `t` plus the minutes by which the alignTo beat was delayed or brought forward in
    this game (its scheduled or actual time minus the original time), never earlier than now.

    行き先の目標時刻：`t` に、alignTo のビートがこのゲームで遅れた・早まった分数（予定または発生の時刻 − 原作の時刻）を
    足したもの。いまより前にはしない。
    """
    if align_to and align_to in book.beats:
        canon = int(book.beats[align_to]["window"]["canonical"])
        at = state["times"].get(align_to)
        if at is None:
            at = schedule(book, state).get(align_to, canon)
        t += int(at) - canon
    return max(t, int(state["t"]))


def where(book: Book, place: str, t: int) -> str:
    """The first half of the subtitle, 「{place}・{day}の{band}」 (api-contract 3.11 ActOption.where): clock.labels
    wording, without applying format.

    副題の前半「{場所}・{日}の{時間帯}」（api-contract 3.11 ActOption.where）：clock.labels の呼び方で、
    format は使わない。
    """
    labels = book.labels
    day, minute = divmod(t, 1440)
    band = [b for m, b in labels.bands if m <= minute][-1]
    return f"{book.places[place]['name']}・{labels.days[min(day, len(labels.days) - 1)]}の{band}"


def companions(book: Book, effects: Iterable[Mapping[str, Any]], arrival: Mapping[str, Any] | None) -> list[str]:
    """Companions: the characters set by `set var.player.companionOf` in the effects, plus whoever speaks first on
    landing, without duplicates.

    同行者：効果の `set var.player.companionOf` の登場人物に、着地して最初に話しかける人物を加え、重複を除いたもの。
    """
    out = [
        str(e["value"])
        for e in effects
        if e.get("op") == "set" and e.get("var") == "var.player.companionOf" and e.get("value") in book.characters
    ]
    if arrival and arrival.get("opener"):
        out.append(str(arrival["opener"]))
    return list(dict.fromkeys(out))


# —— Destinations / 行き先 ——


def current_act(book: Book, state: SimState) -> Json:
    return book.acts[book.act_of(state["vars"])]


def open_exits(book: Book, state: SimState) -> list[Json]:
    """The destinations of this act that this role may choose and whose `requires` holds in the current state
    (api-contract 3.11).

    この幕の行き先のうち、この役柄が選べて、`requires` が現在の状態で成り立つもの（api-contract 3.11）。
    """
    values = flat(state)
    out = []
    for ex in current_act(book, state).get("exits", []):
        if ex.get("roles") and state["role"] not in ex["roles"]:
            continue
        if ex.get("requires") and not book.sim.holds(ex["requires"], values):
            continue
        out.append(ex)
    return out


def en_route(book: Book, state: SimState, ex: Mapping[str, Any], t: int) -> Json | None:
    """The en-route either/or choice (contract 1.4): given only while the beat has no result yet and its scheduled time
    in this game lies between now and the target time. melosMinutes is computed from now with W-1's arrival_delta, and
    the last option (as in the original) is null; when it can't be computed (can't be combined with the changes
    already registered), use the minutes written in the world model.

    道中の二択（契約 1.4）：ビートにまだ結果がなく、このゲームでの予定時刻がいまと目標時刻の間にあるときだけ出す。
    melosMinutes はいまの状態から W-1 の arrival_delta で計算し、最後の選択肢（原作どおり）は null。計算できない
    （登録済みの変更と合わせられない）ときは世界モデルに書かれた分数を使う。
    """
    er = ex.get("enRoute")
    if not er or er["beat"] in state["beats"]:
        return None
    at = schedule(book, state).get(er["beat"])
    if at is None or not state["t"] <= at <= t:
        return None
    choices = []
    last = len(er["choices"]) - 1
    for i, c in enumerate(er["choices"]):
        minutes: int | None = None
        if i < last:
            try:
                minutes = int(arrival_delta(book.world, state, c.get("effects", []), state["t"])["minutes"])
            except ValueError:
                minutes = int(c.get("melosMinutes", 0))
        choices.append({"index": i, "label": c["label"], "melosMinutes": minutes, "afterLine": c.get("after")})
    return {"line": er["line"], "choices": choices}


def option(book: Book, state: SimState, ex: Mapping[str, Any]) -> Json:
    """One destination (ActOption).

    行き先 1 つ（ActOption）。
    """
    t = target_t(book, state, int(ex["t"]), ex.get("alignTo"))
    out: Json = {
        "optionId": ex["id"],
        "label": ex["label"],
        "sceneId": book.scene_of(ex["place"], ex["toAct"]),
        "toActId": ex["toAct"],
        "tLabel": book.label(t),
        "where": where(book, ex["place"], t),
    }
    if ex.get("sub"):
        out["sub"] = ex["sub"]
    out["with"] = companions(book, ex.get("effects", []), ex.get("arrival"))
    out["because"] = None
    er = en_route(book, state, ex, t)
    if er is not None:
        out["enRoute"] = er
    return out


def recap_lines(book: Book, role_id: str, act_events: Iterable[Mapping[str, Any]]) -> list[str]:
    """「この幕であなたが動かしたこと」: summaries of this act's committed events that the player did (or a character
    did for the player) and that changed something, the last 4 by seq; empty when there are none (the frontend shows
    actEnd.summary.empty). The player is written as 「あなた」, and 「。」 is added at the end.

    「この幕であなたが動かしたこと」：この幕でプレイヤーがした（または登場人物がプレイヤーのためにした）、コミット済みで
    何かを変えたイベントの要約を、seq 順に最後の 4 件。1 件もなければ空（フロントエンドは actEnd.summary.empty を
    表示）。プレイヤーは「あなた」と書き、文末に「。」を補う。
    """
    lines = [
        as_you(book, role_id, str(e["summary"]), period=True)
        for e in act_events
        if committed(e)
        and e["effects"]
        and (e["actor"] == "player" or e.get("beneficiary") == "player")
        and e["type"] != "act-transition"
    ]
    return lines[-RECAP_LINES:]


def act_end(book: Book, state: SimState, tries: int, act_events: Iterable[Mapping[str, Any]]) -> Json:
    """ActEnd (same shape as act_ended and pending.actEnd, without type).

    ActEnd（act_ended と pending.actEnd と同じ形で、type は付けない）。
    """
    exits = open_exits(book, state)
    # The world model always has one destination without conditions; if none holds anyway, give them all rather than
    # leave the end-of-act page empty.
    # 世界モデルには条件のない行き先が必ず 1 つある。万一どれも成り立たなければ、幕末ページを空にせず全部出す。
    if not exits:
        log.warning(
            "No destination of %s holds; offering them all / どの行き先も成り立たないので全部出す",
            book.act_of(state["vars"]),
        )
        exits = list(current_act(book, state).get("exits", []))
    left = max(0, PLAN_TRIES - tries)
    return {
        "actId": book.act_of(state["vars"]),
        "recapLines": recap_lines(book, state["role"], act_events),
        "options": [option(book, state, ex) for ex in exits],
        "freeform": {"allowed": left > 0, "triesLeft": left},
    }


def exit_of(book: Book, state: SimState, exit_id: str) -> Json | None:
    return next((ex for ex in current_act(book, state).get("exits", []) if ex["id"] == exit_id), None)


# —— Act transition (2.8.1) / 幕切り替え（2.8.1） ——


@dataclass
class Landing:
    """Where to jump: the next act, the place, the planned time (the target time is computed from alignTo after step
    1), the spot, and the landing.

    どこへ飛ぶか：次の幕、場所、予定時刻（目標時刻は第 1 ステップのあと alignTo で計算する）、立ち位置、着地。
    """

    to_act: str
    place: str
    t: int
    align_to: str | None = None
    spot: str | None = None
    arrival: Json | None = None

    @classmethod
    def of_exit(cls, ex: Mapping[str, Any]) -> Landing:
        return cls(ex["toAct"], ex["place"], int(ex["t"]), ex.get("alignTo"), ex.get("spot"), ex.get("arrival"))

    @classmethod
    def of_plan(cls, plan: Mapping[str, Any]) -> Landing:
        return cls(plan["toAct"], plan["place"], int(plan["t"]), None, plan.get("spot"), plan.get("arrival"))


@dataclass
class Moved:
    """What the act transition wrote: the events settled in step 3 (「その頃」 is taken from here), the target time,
    and what to push after landing.

    幕切り替えが書いたもの：第 3 ステップで精算したイベント（「その頃」はここから取る）、目標時刻、
    着地後にプッシュするもの。
    """

    from_act: str
    to_act: str
    t: int
    skipped: list[Json] = field(default_factory=list)
    arrival: Json | None = None
    # B-16: events written by world advancement in step 3 (also in skipped).
    # B-16：第 3 ステップで世界の進行が書いたイベント（skipped にも入る）。
    world: list[Json] = field(default_factory=list)


def catch_up(w: Writer) -> None:
    """When the act has closed and the clock has gone past the closing moment (the minutes of dialogue or an action
    crossed the closing beat), settle the beats that came due in between first, so later events can be written at the
    current time (W-1 apply needs settle first). The player spent this stretch talking and was present: beats at their
    place still give learn and set pieces (data #158); "not present" applies only to step 3 (contract 2.8.1).

    幕がすでに閉じ、時計が幕を閉じた時点を過ぎているとき（対話やアクションの分数が幕を閉じるビートをまたいだ）、
    間に時刻が来たビートを先に精算してから、以降のイベントを現在時刻で書けるようにする（W-1 の apply は先に settle が
    必要）。この間プレイヤーは話しながら過ごしていてその場にいる：プレイヤーのいる場所のビートは従来どおり learn と
    演出を出す（データ #158）。不在扱いは第 3 ステップだけ（契約 2.8.1）。
    """
    w.settle(w.state["t"], guard=False)


def en_route_event(w: Writer, ex: Mapping[str, Any], checked: Checked | None, turn_id: str) -> None:
    """Step 1: if an option other than the last was chosen in the en-route choice, the player's action event (origin
    act, exitId), with the result of steps 3 and 4.

    第 1 ステップ：道中の二択で最後以外の選択肢を選んだとき、プレイヤーの action イベント（origin act、exitId）。
    第 3・4 ステップを通した結果を使う。
    """
    if checked is None:
        return
    cand = checked.candidate
    w.add(
        w.full(
            t=w.state["t"],
            dt=0,
            actor="player",
            type="action",
            origin="act",
            place=w.player_place,
            summary=cand["summary"],
            effects=checked.effects if checked.passed else [],
            check=checked.check,
            turn_id=turn_id,
            exitId=ex["id"],
        )
    )


def player_transition(
    w: Writer,
    *,
    turn_id: str,
    summary: str,
    effects: Sequence[Mapping[str, Any]],
    check: Mapping[str, Any],
    exit_id: str | None = None,
    plan: Mapping[str, Any] | None = None,
) -> Json:
    """Step 2: the player's act-transition, at the current time, dt 0, origin act. A given destination carries exitId,
    a plan carries plan.

    第 2 ステップ：プレイヤーの act-transition。現在時刻、dt 0、origin act。決まった行き先なら exitId、
    プランなら plan を付ける。
    """
    extra: dict[str, Any] = {}
    if exit_id is not None:
        extra["exitId"] = exit_id
    if plan is not None:
        extra["plan"] = dict(plan)
    return w.add(
        w.full(
            t=w.state["t"],
            dt=0,
            actor="player",
            type="act-transition",
            origin="act",
            place=w.player_place,
            summary=summary,
            effects=effects,
            check=check,
            turn_id=turn_id,
            **extra,
        )
    )


def jump(
    w: Writer,
    landing: Landing,
    t: int,
    turn_id: str,
    world: Sequence[Any] = (),
    log_: Sequence[Mapping[str, Any]] = (),
) -> Moved:
    """Steps 3 and 4: settle to the target time with the player not present (no learning of beats' public facts, no
    set pieces), then write the system's act-transition (new act, new place). world: the world advancement candidates
    that passed the checks (B-16, `advance.Item`), merged by time with the beats that come due and judged again before
    writing; log_ is this game's events before this commit (causes keep only those found there).

    第 3・4 ステップ：プレイヤー不在のまま目標時刻まで精算し（ビートの public な事実は learn せず、演出も演じない）、
    それからシステムの act-transition（幕と場所を替える）を書く。world：世界の進行のうち検査を通った候補
    （B-16、`advance.Item`）。時刻が来たビートと時刻順に合わせ、書く前にもう一度判定する。log_ はこのコミットより前の
    このゲームのイベント（causes はそこにあるものだけ残す）。
    """
    from zoujin_backend.narrator import advance

    from_act = w.book.act_of(w.state["vars"])
    before = len(w.events)
    written = advance.write(w, world, until=t, away=True, log_=[*log_, *w.events]) if world else []
    w.settle(t, guard=False, present=False)
    skipped = list(w.events[before:])
    w.add(
        w.full(
            t=t,
            dt=0,
            actor="system",
            type="act-transition",
            origin="act",
            place=landing.place,
            summary=f"{w.book.acts[landing.to_act]['title']}へ",
            effects=[
                {"op": "set", "var": "var.act.current", "value": landing.to_act},
                {"op": "set", "var": "var.player.location", "value": landing.place},
            ],
            check=PASSED_EXIT,
            turn_id=turn_id,
        )
    )
    run = w.run
    run.player_spot = landing.spot
    run.act_end = None
    run.plan_tries = 0
    run.plan_alternative = None
    arrival = dict(landing.arrival) if landing.arrival else None
    run.arrival = {"actId": landing.to_act, **arrival} if arrival and arrival.get("opener") else None
    return Moved(from_act, landing.to_act, t, skipped, arrival, written)


# —— 「その頃」 ——


def _who(e: Mapping[str, Any]) -> set[str]:
    """The characters appearing in an event: the actor and the targets of its effects.

    イベントに登場する人物：行為者と効果の対象。
    """
    out = {str(e["actor"])}
    for x in e.get("effects", []):
        for k in ("character", "to", "from"):
            v = x.get(k)
            if isinstance(v, str):
                out.add(v)
    return out


def seen_characters(
    book: Book, start_place: str, log: Iterable[Mapping[str, Any]], talked: Collection[str]
) -> set[str]:
    """Characters the player has seen (approximate; WorldState doesn't record who has seen whom): those who talked with
    the player, plus those who were the actor or a target in events committed while the player was present. log is
    all of this game's events in seq order; the player's place starts at the starting place and follows the
    `set var.player.location` in the events.

    プレイヤーが会った登場人物（近似。WorldState は誰が誰に会ったかを記録しない）：プレイヤーと話した人物に、
    プレイヤーがその場にいたときにコミットされたイベントで行為者か対象になった人物を加える。log はこのゲームの
    seq 順の全イベント。プレイヤーの場所は開始時の場所から始め、イベントの `set var.player.location` に従って追う。
    """
    seen = set(talked)
    loc = start_place
    for e in log:
        if committed(e) and (e["actor"] == "player" or e["place"] == loc):
            seen |= _who(e)
        for x in e.get("effects", []):
            if x.get("op") == "set" and x.get("var") == "var.player.location":
                loc = str(x["value"])
    return {c for c in seen if c in book.characters}


def recap(
    book: Book,
    role_id: str,
    skipped: Iterable[Mapping[str, Any]],
    seen: Collection[str],
    player_promises: Collection[str],
) -> list[Json]:
    """「その頃」 (contract 2.8.1 step 5): promises involving the player kept or broken → keyMoment → things done on
    their own by characters the player has seen (origin plan) and director events (origin director). Voided promises
    and forget are left out; line uses summary (the player written as 「あなた」, 「。」 added at the end). At most 3.

    「その頃」（契約 2.8.1 第 5 ステップ）：プレイヤーに関わる約束が守られた・破られた → keyMoment → プレイヤーが
    会った登場人物が自分でしたこと（origin plan）とディレクターのイベント（origin director）。voided の約束と forget は
    書かない。line は summary を使う（プレイヤーは「あなた」と書き、文末に「。」を補う）。最大 3 件。
    """
    promised: list[Json] = []
    key: list[Json] = []
    others: list[Json] = []
    for e in skipped:
        if not committed(e) or e["type"] == "forget":
            continue
        change = next(
            (
                x
                for x in e.get("effects", [])
                if x.get("op") == "promise"
                and x.get("change") in ("kept", "broken")
                and x.get("promiseId") in player_promises
            ),
            None,
        )
        item = {"eventId": e["eventId"], "line": as_you(book, role_id, str(e["summary"]), period=True)}
        if change is not None:
            promised.append({**item, "promise": change["change"]})
        elif e.get("keyMoment"):
            key.append(item)
        elif e.get("origin") == "director" or (e.get("origin") == "plan" and e["actor"] in seen):
            others.append(item)
    return (promised + key + others)[:RECAP_ITEMS]


def player_promises(state: SimState) -> set[str]:
    return {p for p, x in state["promises"].items() if "player" in (x.get("from"), x.get("to"))}
