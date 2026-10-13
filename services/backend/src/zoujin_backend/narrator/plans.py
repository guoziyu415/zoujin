"""Choosing a destination and stating a plan at the end of an act (B-3 item 4; api-contract 3.11, contract 2.8.1).

- Choosing a destination (`choose`): a destination from this `act_ended`, or the alternative offered when the previous
  plan didn't go ahead; anything not among them, or a bad `enRouteChoice`, gets `invalid_choice` and no event. If an
  option other than the last was chosen in the en-route choice, that option's effects go through steps 3 and 4.
- Stating a plan (`plan`): the `plan` prompt judges whether it can go ahead. When this act has `Act.plan`, the plan's
  own effects go through steps 3-5 (judged on the state after trial-applying `Act.plan.effects`), and if they pass we
  jump; in acts without `Act.plan`, this card never lets a plan go ahead. A plan that doesn't go ahead writes no event,
  adds one to the try count, and records the alternative destination on the run.
- Plan paraphrases (label, narration, the alternative destination's label) all come from the player's words: before
  being written they go through the same filter as event summaries (personal-information patterns, 8 consecutive
  characters identical to the player's words, step 0 flags, length), and failures are replaced with a fixed wording that
  doesn't paraphrase (`clean`).

幕末の行き先の選択とプランの表明（B-3 第 4 項。api-contract 3.11、契約 2.8.1）。

- 行き先の選択（`choose`）：今回の `act_ended` の行き先か、前回プランが実行されなかったときに示した代わりの行き先。
  そのどれでもない、または `enRouteChoice` が誤っていれば `invalid_choice` を返し、イベントは書かない。道中の二択で
  最後以外の選択肢を選んだら、その選択肢の効果を第 3・4 ステップに通す。
- プランの表明（`plan`）：プロンプト `plan` が実行できるかを判定する。この幕に `Act.plan` があれば、プラン自身の効果を
  第 3〜5 ステップに通し（`Act.plan.effects` を試算したあとの状態で判定）、通れば幕を飛ぶ。`Act.plan` のない幕では、
  このカードでは常に実行しない。実行しないときはイベントを書かず、試行回数を 1 増やし、
  代わりの行き先をゲームに記録する。
- プランの言い換え（label、narration、代わりの行き先の label）はどれもプレイヤーの言葉から来る：書き込む前にイベントの
  要約と同じフィルター（個人情報のパターン、プレイヤーの発話と 8 文字連続で一致、第 0 ステップの印、長さ）に通し、
  通らなければ言い換えない固定の言い方に替える（`clean`）。
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from zoujin_backend.db.store import Run
from zoujin_backend.db.tables import turns
from zoujin_backend.narrator.pipeline import CallFailed, Spend, TurnInput, normalize
from zoujin_backend.narrator.rules import VERBATIM, Checked, has_pii, lcs_len
from zoujin_backend.narrator.view import state_view
from zoujin_backend.narrator.writer import Writer
from zoujin_backend.world import Book
from zoujin_worldsim import SimState, apply, initial_state

if TYPE_CHECKING:
    from zoujin_backend.narrator.core import Narrator, Planned, Result, Task

log = logging.getLogger("zoujin.narrator")

Json = Any
# B-16: world advancement candidates that passed the checks (advance.Item) and the event log that was read.
# B-16：世界の進行のうち検査を通った候補（advance.Item）と、読み込んだイベントログ。
World = tuple[list[Any], list[Json]]

LABEL_MAX = 30
LINE_MAX = 60
LABEL_FALLBACK = "自分で決めた道を行く"
REFUSAL_FALLBACK = "その考えは、いまは形にならなかった。"
# A plan spoken by voice produced no transcript: doesn't count as a try (copy decided by UX, 10-10).
# 音声で言ったプランが文字起こしされなかった：試行回数に数えない（文言は UX が決めた、10-10）。
NOT_HEARD = "声が届かなかったようです。もう一度、聞かせてください。"
INVALID_CHOICE = "その行き先は選べません。"
INVALID_REQUEST = "うまく送れませんでした。"
# Step 0 (B-12 safety screening) flags; if any is set, don't paraphrase.
# 第 0 ステップ（B-12 の安全スクリーニング）の印。あれば言い換えない。
FLAGS = frozenset({"injection", "pii", "harmful", "unscreened", "ambiguous"})
# The line used when narrate fails twice or doesn't pass the filter (same as the fake model's default).
# narrate が 2 回ともだめ、またはフィルターを通らないときの一文（偽モデルの既定と同じ）。
NARRATE_FALLBACK = {
    "done": "あなたは、そうした。",
    "partial": "思ったようには、いかなかった。",
    "refused": "それは、いまはかなわなかった。",
}


def narrate_fallback(status: str) -> str:
    return NARRATE_FALLBACK.get(status, NARRATE_FALLBACK["done"])


def clean(text: str | None, said: str, flags: frozenset[str], *, limit: int) -> str | None:
    """Whether a sentence the model paraphrased from the player's words may be written (data-design 5.1, same as an
    event summary): not empty, at most limit characters, no personal-information patterns, no 8 consecutive characters
    identical to the player's words, and no step 0 flags. If it fails, return None and the caller uses a fixed wording.

    モデルがプレイヤーの言葉から言い換えた一文を書き込んでよいか（data-design 5.1、イベントの summary と同じ）：
    空でない、limit 文字以内、個人情報のパターンがない、プレイヤーの発話と 8 文字連続で一致しない、第 0 ステップの印が
    ない。通らなければ None を返し、呼び出し側が固定の言い方に替える。
    """
    if text is None:
        return None
    text = text.strip()
    if not text or len(text) > limit or has_pii(text) or flags & FLAGS:
        return None
    if said and lcs_len(said, text) >= VERBATIM:
        return None
    return text


def error_msg(code: str, message: str) -> Json:
    return {"type": "error", "error": {"code": code, "message": message, "retryable": False, "retryAfterSeconds": None}}


# —— Choosing a destination / 行き先の選択 ——


def choice_of(book: Book, state: SimState, run: Run, req: Mapping[str, Any]) -> tuple[str, Json] | None:
    """What can be chosen this time: ("exit", destination) or ("plan", the alternative plan). Not among this time's
    destinations and alternative, or a bad enRouteChoice → None.

    今回選べるもの：("exit", 行き先) または ("plan", 代わりのプラン)。今回の行き先と代わりの行き先にない、
    または enRouteChoice が誤り → None。
    """
    from zoujin_backend.narrator.acts import exit_of

    if run.act_end is None:
        return None
    oid = req.get("optionId")
    alt = run.plan_alternative
    choice = req.get("enRouteChoice")
    if alt is not None and alt.get("optionId") == oid and alt.get("kind") == "plan":
        return None if choice is not None else ("plan", alt)
    listed = {o["optionId"]: o for o in run.act_end.get("options", [])}
    if oid not in listed and not (alt is not None and alt.get("optionId") == oid):
        return None
    ex = exit_of(book, state, str(oid))
    if ex is None:
        return None
    if choice is not None:
        er = listed.get(str(oid), {}).get("enRoute")
        if er is None or not 0 <= int(choice) < len(er["choices"]):
            return None
    return ("exit", ex)


def en_route_candidate(book: Book, state: SimState, ex: Mapping[str, Any], choice: int | None) -> Json | None:
    """The en-route choice: the candidate event when an option other than the last was chosen (none given = the last).

    道中の二択：最後以外の選択肢を選んだとき（渡さなければ最後の選択肢）の候補イベント。
    """
    er = ex.get("enRoute")
    if er is None or choice is None or choice >= len(er["choices"]) - 1:
        return None
    c = er["choices"][choice]
    return {
        "actor": "player",
        "type": "action",
        "origin": "act",
        "summary": f"道中で「{c['label']}」を選んだ",
        "causes": [],
        "effects": copy.deepcopy(c.get("effects", [])),
    }


async def talked(n: Narrator, pid: str) -> list[str]:
    async with n.engine.connect() as c:
        rows = await c.execute(
            select(turns.c.character).where(
                turns.c.playthrough_id == pid, turns.c.kind == "talk", turns.c.status == "done"
            )
        )
        return [r for r in rows.scalars() if r]


async def seen(n: Narrator, book: Book, pid: str, role_id: str) -> set[str]:
    """The characters the player has seen, for 「その頃」 (reads all of this game's events and the characters talked
    to).

    「その頃」に使う、プレイヤーが会った登場人物（このゲームの全イベントと話した登場人物を読む）。
    """
    return (await seen_and_log(n, book, pid, role_id))[0]


async def seen_and_log(n: Narrator, book: Book, pid: str, role_id: str) -> tuple[set[str], list[Json]]:
    """The characters the player has seen, and this game's event log (world advancement needs it too, B-16).

    プレイヤーが会った登場人物と、このゲームのイベントログ（世界の進行にも要る、B-16）。
    """
    from zoujin_backend.db import store
    from zoujin_backend.narrator.acts import seen_characters

    async with n.engine.connect() as c:
        log_ = await store.event_log(c, pid, book.version)
    start = initial_state(book.world, role_id)["vars"]["var.player.location"]
    return seen_characters(book, start, log_, await talked(n, pid)), log_


async def world_ahead(
    n: Narrator,
    book: Book,
    state: SimState,
    log_: list[Json],
    to_act: str,
    t: int,
    spend: Spend,
    span: Mapping[str, Any],
) -> World:
    """B-16: world advancement for an act transition, from now to the target time (the model is called outside the
    transaction; inside it the results are written merged with the beats).

    B-16：幕切り替えの世界の進行。いまから目標時刻まで（モデルはトランザクションの外で呼び、中でビートと合わせて書く）。
    """
    from zoujin_backend.narrator import advance

    window = advance.Window("act", int(state["t"]), max(int(state["t"]), t), to_act)
    prepared = await advance.prepare(n, book, state, log_, window, spend, span)
    return (prepared.items, log_)


async def run_choose(n: Narrator, task: Task) -> Result:
    from zoujin_backend.narrator.acts import current_act, target_t
    from zoujin_backend.narrator.core import MAX_STALE, Stale

    req = dict(task.request or {})
    for _ in range(MAX_STALE):
        pt, state = await n.read(task.pid)
        run = Run.of(pt)
        book = n.library.version(pt["world_model_version"])
        got = choice_of(book, state, run, req)
        if got is None:
            return await n._commit(task, pt["last_seq"], lambda w, b: invalid(INVALID_CHOICE, "invalid_choice"))
        # Follows the task: retries and uncommitted attempts count too (B-8 item 7).
        # タスクに付いて回る：やり直しやコミットしなかった分も数える（B-8 第 7 項）。
        spend = task.spend
        span = {"playthrough_id": task.pid, "turn_id": task.turn_id, "world_model_version": book.version}
        who, log_ = await seen_and_log(n, book, task.pid, pt["role_id"])
        if got[0] == "plan":
            alt = got[1]
            accepted = await verify_plan(n, book, state, alt.get("effects", []), "", spend, span)
            if accepted is None:
                return await n._commit(task, pt["last_seq"], lambda w, b: invalid(INVALID_CHOICE, "invalid_choice"))
            label = str(alt["label"])
            plan = (label, [c for c in alt.get("with", []) if c in book.characters], accepted)
            p = current_act(book, state)["plan"]
            world = await world_ahead(
                n, book, state, log_, p["toAct"], target_t(book, state, int(p["t"]), None), spend, span
            )

            def go_plan(w: Writer, b: Book, who: set[str] = who, plan: Any = plan, world: World = world) -> Planned:
                return transition(n, w, b, task, req, who, plan=plan, world=world)

            write: Callable[[Writer, Book], Planned] = go_plan
        else:
            ex = got[1]
            cand = en_route_candidate(book, state, ex, req.get("enRouteChoice"))
            checked = None
            if cand is not None:
                turn = TurnInput(character=None, player=None, act={"kind": "en-route", "exit": ex["id"]})
                checked = await n.pipeline.check_only(book, state, cand, turn, "scoped", spend, span)
            t = target_t(book, state, int(ex["t"]), ex.get("alignTo"))
            world = await world_ahead(n, book, state, log_, ex["toAct"], t, spend, span)

            def go_exit(
                w: Writer,
                b: Book,
                who: set[str] = who,
                ex: Json = ex,
                checked: Checked | None = checked,
                world: World = world,
            ) -> Planned:
                return transition(n, w, b, task, req, who, ex=ex, step1=checked, world=world)

            write = go_exit
        try:
            return await n._commit(task, pt["last_seq"], write, spend=spend)
        except Stale:
            log.info("lastSeq changed; redoing %s / lastSeq が変わったのでやり直す", task.turn_id)
    raise RuntimeError(f"{task.turn_id}: lastSeq keeps changing / {task.turn_id}：lastSeq が変わり続けている")


def invalid(message: str, code: str) -> Planned:
    from zoujin_backend.narrator.core import Planned

    return Planned(push=[error_msg(code, message)], info={"error": code})


def transition(
    n: Narrator,
    w: Writer,
    book: Book,
    task: Task,
    req: Mapping[str, Any],
    who: set[str],
    *,
    ex: Json | None = None,
    step1: Checked | None = None,
    plan: tuple[str, list[str], Checked | None] | None = None,
    head: Sequence[Json] = (),
    world: World | None = None,
) -> Planned:
    """Act transition (contract 2.8.1): a given destination (ex) or a plan that goes ahead (plan = (label, with, the
    judgment of the plan's own effects)). world: the world advancement candidates that passed the checks and the event
    log that was read (B-16), written in step 3 merged with the beats.

    幕切り替え（契約 2.8.1）：決まった行き先（ex）か、実行されるプラン（plan = (label, with, プラン自身の効果の判定)）。
    world：世界の進行のうち検査を通った候補と読み込んだイベントログ（B-16）。第 3 ステップでビートと合わせて書く。
    """
    from zoujin_backend.narrator import acts
    from zoujin_backend.narrator.core import Planned

    acts.catch_up(w)
    role = book.roles[w.state["role"]]["name"]
    act = acts.current_act(book, w.state)
    if ex is not None:
        acts.en_route_event(w, ex, step1, task.turn_id)
        landing = acts.Landing.of_exit(ex)
        t = acts.target_t(book, w.state, landing.t, landing.align_to)
        acts.player_transition(
            w,
            turn_id=task.turn_id,
            summary=f"{role}は、{ex['label']}ことにした",
            effects=ex.get("effects", []),
            check=acts.PASSED_EXIT,
            exit_id=ex["id"],
        )
    else:
        assert plan is not None
        label, with_, checked = plan
        landing = acts.Landing.of_plan(act["plan"])
        t = acts.target_t(book, w.state, landing.t, None)
        doc: Json = {"label": label, "toAct": landing.to_act, "place": landing.place, "t": t}
        if with_:
            doc["with"] = with_
        effects = list(act["plan"].get("effects", [])) + (list(checked.effects) if checked else [])
        acts.player_transition(
            w,
            turn_id=task.turn_id,
            summary=f"{role}は、{label}ことにした",
            effects=effects,
            check=checked.check if checked else acts.PASSED_EXIT,
            plan=doc,
        )
    items, log_ = world if world is not None else ([], [])
    moved = acts.jump(w, landing, t, task.turn_id, items, log_)
    items = acts.recap(book, w.state["role"], moved.skipped, who, acts.player_promises(w.state))
    msg: Json = {
        "type": "act_transition",
        "fromActId": moved.from_act,
        "toActId": moved.to_act,
        "recap": items,
        # Filled in before commit from the state after landing (core._commit).
        # コミット前に着地後の状態から補う（core._commit）。
        "snapshot": None,
    }
    if moved.arrival:
        msg["arrival"] = moved.arrival
    info: Json = {"toAct": moved.to_act, "t": t}
    plans_n = sum(1 for e in moved.world if e.get("origin") == "plan")
    return Planned(
        push=[*head, msg],
        info=info,
        extra={"playerSpot": landing.spot},
        snapshot=True,
        world_events=plans_n,
        director_events=len(moved.world) - plans_n,
    )


# —— Stating a plan / プランの表明 ——


def option_ref(book: Book, run: Run, option_id: str) -> Json | None:
    """A destination from act_ended → the shape of PlanAlternative.

    act_ended の行き先 1 つ → PlanAlternative の形。
    """
    o = next((x for x in (run.act_end or {}).get("options", []) if x["optionId"] == option_id), None)
    if o is None:
        return None
    return {k: o[k] for k in PUBLIC if k in o}


def plan_request(book: Book, state: SimState, run: Run, said: str, mode: str) -> Json:
    from zoujin_backend.narrator.acts import current_act, target_t

    act = current_act(book, state)
    options = [
        {k: o[k] for k in ("optionId", "label", "where", "sub") if k in o}
        for o in (run.act_end or {}).get("options", [])
    ]
    req: Json = {
        "worldModelVersion": book.version,
        "state": state_view(book, state).doc,
        "turn": {"character": None, "mode": mode, "player": said},
        "options": options,
        "hasPlan": "plan" in act,
    }
    if "plan" in act:
        p = act["plan"]
        req["landing"] = {"toAct": p["toAct"], "place": p["place"], "t": target_t(book, state, int(p["t"]), None)}
    return req


async def verify_plan(
    n: Narrator,
    book: Book,
    state: SimState,
    effects: Sequence[Mapping[str, Any]],
    said: str,
    spend: Spend,
    span: Mapping[str, Any],
) -> Checked | None:
    """Run the plan's own effects through steps 3-5: judged on the state after trial-applying `Act.plan.effects` (e.g.
    the destination lets the player learn about the promise, which is what makes it possible to tell others about it),
    with the duration = the skipped stretch. Without effects there is nothing to judge (any result other than None is
    treated as passing by the caller). Returns None when rejected.

    プラン自身の効果を第 3〜5 ステップに通す：`Act.plan.effects` を試算したあとの状態で判定する（例：行き先で
    プレイヤーが約束を知るので、その約束をほかの人に話せる）。所要時間 = 飛ばす区間。効果がなければ判定しない
    （None 以外の結果は呼び出し側が通ったものとみなす）。却下されたら None を返す。
    """
    from zoujin_backend.narrator.acts import PASSED_EXIT, current_act, target_t

    act = current_act(book, state)
    p = act.get("plan") or {}
    t = target_t(book, state, int(p.get("t", state["t"])), None)
    if not effects:
        return Checked({"summary": ""}, [], dict(PASSED_EXIT))
    trial = state
    try:
        trial = apply(book.world, state, {"t": state["t"], "dt": 0, "origin": "act", "effects": p.get("effects", [])})
    except ValueError:
        log.info(
            "Act.plan.effects can't be trial-applied; judging on the original state"
            " / Act.plan.effects を試算できないので元の状態で判定する"
        )
    cand = {
        "actor": "player",
        # Only used to judge the effects (rewrite output doesn't accept act-transition); what gets written is the
        # player's act-transition.
        # 効果の判定だけに使う（書き換えの出力は act-transition を受け付けない）。
        # 書き込むのはプレイヤーの act-transition。
        "type": "action",
        "origin": "act",
        "summary": "幕末のプラン",
        "causes": [],
        "effects": [dict(e) for e in effects],
    }
    turn = TurnInput(character=None, player=said or None, act={"kind": "plan"})
    v = await n.pipeline.verify(book, trial, [cand], turn, t - int(state["t"]), spend, span)
    if v.timed_out or not v.checked or not v.checked[0].passed:
        return None
    return v.checked[0]


async def run_plan(n: Narrator, task: Task, said: str | None) -> Result:
    from zoujin_backend.narrator.core import MAX_STALE, Stale

    req = dict(task.request or {})
    for _ in range(MAX_STALE):
        pt, state = await n.read(task.pid)
        run = Run.of(pt)
        book = n.library.version(pt["world_model_version"])
        if run.act_end is None or run.plan_tries >= 2:
            return await n._commit(task, pt["last_seq"], lambda w, b: invalid(INVALID_REQUEST, "invalid_request"))
        # Follows the task: retries and uncommitted attempts count too (B-8 item 7).
        # タスクに付いて回る：やり直しやコミットしなかった分も数える（B-8 第 7 項）。
        spend = task.spend
        span = {"playthrough_id": task.pid, "turn_id": task.turn_id, "world_model_version": book.version}
        text = said or ""
        request = plan_request(book, state, run, text, req.get("mode", "text"))
        tries = run.plan_tries + 1
        try:
            r = await n.pipeline.call(
                "plan", request, spend, span={**span, "tries": tries}, extra=lambda o: {"accepted": bool(o["accepted"])}
            )
            out = r.output
        except CallFailed:
            out = {"accepted": False, "label": None, "with": [], "effects": [], "narration": [], "alternative": None}
        view = state_view(book, state)
        accepted = bool(out["accepted"]) and request["hasPlan"]
        checked: Checked | None = None
        label = LABEL_FALLBACK
        if accepted:
            label = clean(out.get("label"), text, frozenset(), limit=LABEL_MAX) or LABEL_FALLBACK
            effects = normalize({"effects": out.get("effects", [])}, view, book)["effects"]
            checked = await verify_plan(n, book, state, effects, text, spend, span)
            accepted = checked is not None
        with_ = [c for c in out.get("with", []) if c in book.characters]
        if accepted:
            head = {
                "type": "act_plan_result",
                **reply_to(task, req),
                "accepted": True,
                "narration": [f"あなたは、{label}ことにした。"],
                "triesLeft": max(0, 2 - run.plan_tries),
            }
            who, log_ = await seen_and_log(n, book, task.pid, pt["role_id"])
            plan = (label, with_, checked if checked and checked.effects else None)
            land = request["landing"]
            world = await world_ahead(n, book, state, log_, land["toAct"], int(land["t"]), spend, span)

            def go_plan(
                w: Writer, b: Book, who: set[str] = who, plan: Any = plan, head: Json = head, world: World = world
            ) -> Planned:
                p = transition(n, w, b, task, req, who, plan=plan, head=[head], world=world)
                p.info |= {"accepted": True, "triesLeft": head["triesLeft"], "narration": head["narration"]}
                p.plans_accepted = 1
                return p

            write: Callable[[Writer, Book], Planned] = go_plan
        else:
            lines = [x for x in (clean(s, text, frozenset(), limit=LINE_MAX) for s in out.get("narration", [])) if x]
            lines = lines[:2] or [REFUSAL_FALLBACK]
            # Accepted, then failed the checks: don't paraphrase the model's go-ahead wording.
            # 受け入れたが検査を通らなかった：モデルの実行する旨の言い方は言い換えない。
            if bool(out["accepted"]) and request["hasPlan"]:
                lines = [REFUSAL_FALLBACK]
            alt = alternative(n, book, state, run, out.get("alternative"), text, request)

            def refuse(w: Writer, b: Book, lines: list[str] = lines, alt: Json = alt) -> Planned:
                return refused(w, task, req, lines, alt)

            write = refuse

        # A plan spoken by voice can be cancelled within 3 seconds of the final transcript being pushed (B-4).
        # 音声で言ったプランは、確定した文字起こしを送ってから 3 秒以内なら取り消せる（B-4）。
        await n.wait_window(task)
        try:
            return await n._commit(task, pt["last_seq"], write, spend=spend)
        except Stale:
            log.info("lastSeq changed; redoing %s / lastSeq が変わったのでやり直す", task.turn_id)
    raise RuntimeError(f"{task.turn_id}: lastSeq keeps changing / {task.turn_id}：lastSeq が変わり続けている")


def reply_to(task: Task, req: Mapping[str, Any]) -> Json:
    """act_plan_result carries clientMsgId (text) or turnId (voice).

    act_plan_result は clientMsgId（テキスト）か turnId（音声）を持つ。
    """
    return (
        {"turnId": task.turn_id}
        if req.get("mode") == "voice"
        else {"clientMsgId": req.get("clientMsgId") or task.turn_id}
    )


def alternative(
    n: Narrator, book: Book, state: SimState, run: Run, raw: Json | None, said: str, request: Mapping[str, Any]
) -> Json:
    """The alternative destination (the shape recorded on the run: PlanAlternative's four fields + kind, and for a plan
    also with and effects). A given destination uses its destination ID; another plan uses plan_ plus a ULID, and if
    its label fails the filter, offer the first given destination instead.

    代わりの行き先（ゲームに記録する形：PlanAlternative の 4 つのフィールド + kind。プランなら with と effects も
    持つ）。決まった行き先なら行き先 ID を使う。別のプランなら plan_ に ULID を付け、label がフィルターを通らなければ
    最初の決まった行き先に替える。
    """
    first = (run.act_end or {}).get("options", [{}])[0].get("optionId")
    if isinstance(raw, Mapping) and raw.get("exit"):
        ref = option_ref(book, run, str(raw["exit"]))
        if ref is not None:
            return {**ref, "kind": "exit"}
    if isinstance(raw, Mapping) and raw.get("label") and request.get("hasPlan"):
        label = clean(str(raw["label"]), said, frozenset(), limit=LABEL_MAX)
        if label is not None:
            land = request["landing"]
            view = state_view(book, state)
            return {
                "optionId": n.ids.new("plan"),
                "label": label,
                "sceneId": book.scene_of(land["place"], land["toAct"]),
                "toActId": land["toAct"],
                "tLabel": book.label(int(land["t"])),
                "kind": "plan",
                "with": [c for c in raw.get("with", []) if c in book.characters],
                "effects": normalize({"effects": raw.get("effects", [])}, view, book)["effects"],
            }
    ref = option_ref(book, run, str(first))
    assert ref is not None
    return {**ref, "kind": "exit"}


# toActId: v1.0.14; older alternatives recorded on runs don't have it.
# toActId：v1.0.14。ゲームに記録された古い代わりの行き先にはない。
PUBLIC = ("optionId", "label", "sceneId", "toActId", "tLabel")


def refused(w: Writer, task: Task, req: Mapping[str, Any], lines: list[str], alt: Json) -> Planned:
    """The plan doesn't go ahead: no event, the try count goes up by one, the alternative destination is recorded on the
    run, and the end-of-act page's freeform changes accordingly.

    実行しない：イベントは書かず、試行回数を 1 増やし、代わりの行き先をゲームに記録し、幕末ページの freeform もそれに
    合わせて変える。
    """
    from zoujin_backend.narrator.core import Planned

    run = w.run
    run.plan_tries += 1
    run.plan_alternative = alt
    left = max(0, 2 - run.plan_tries)
    if run.act_end is not None:
        run.act_end = {**run.act_end, "freeform": {"allowed": left > 0, "triesLeft": left}}
    public = {k: alt[k] for k in PUBLIC if k in alt}
    msg = {
        "type": "act_plan_result",
        **reply_to(task, req),
        "accepted": False,
        "narration": lines,
        "alternative": public,
        "triesLeft": left,
    }
    info = {"accepted": False, "narration": lines, "alternative": public, "triesLeft": left}
    return Planned(push=[msg], info=info, plans_refused=1)


__all__ = ["clean", "narrate_fallback", "run_choose", "run_plan"]
