"""幕末选去处和说出打算（B-3 第 4 条；api-contract 3.11，契约 2.8.1）。

- 选去处（`choose`）：这次 `act_ended` 的去处，或上一次打算不成行时给的替代去处；不在里面、`enRouteChoice` 不对的回
  `invalid_choice`、不写事件。过场二选一选了不是最后一项的，那一项的效果过第 3、4 步。
- 说出打算（`plan`）：提示 `plan` 判能不能成行。这一幕有 `Act.plan` 时，打算自己的效果过第 3〜5 步（在
  `Act.plan.effects` 试算之后的状态上判），过了就跳；没有 `Act.plan` 的幕本卡一律不成行。不成行不写事件，试次加一，
  替代去处记在局上。
- 打算的转述（label、narration、替代去处的 label）都从玩家的话来：写入前过和事件摘要一样的过滤（个人信息的模式、
  和玩家原话连续 8 字相同、第 0 步的标记、长度），不过的换成固定的、不转述的说法（`clean`）。
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

LABEL_MAX = 30
LINE_MAX = 60
LABEL_FALLBACK = "自分で決めた道を行く"
REFUSAL_FALLBACK = "その考えは、いまは形にならなかった。"
# 声音说打算没转写出字：不算试次（文案 UX 定的，10-10）
NOT_HEARD = "声が届かなかったようです。もう一度、聞かせてください。"
INVALID_CHOICE = "その行き先は選べません。"
INVALID_REQUEST = "うまく送れませんでした。"
FLAGS = frozenset(
    {"injection", "pii", "harmful", "unscreened", "ambiguous"}
)  # 第 0 步（B-12 安全筛查）的标记，有就不转述
NARRATE_FALLBACK = {  # narrate 两次都不行、或过滤不过时的一句（和假模型的默认一样）
    "done": "あなたは、そうした。",
    "partial": "思ったようには、いかなかった。",
    "refused": "それは、いまはかなわなかった。",
}


def narrate_fallback(status: str) -> str:
    return NARRATE_FALLBACK.get(status, NARRATE_FALLBACK["done"])


def clean(text: str | None, said: str, flags: frozenset[str], *, limit: int) -> str | None:
    """模型从玩家的话转述出来的一句，能不能写进去（data-design 5.1，同事件的 summary）：不空、不超过 limit 字、
    没有个人信息的模式、没有和玩家原话连续 8 字相同、第 0 步没有标记。不过返回 None，调用方换固定的说法。"""
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


# —— 选去处 ——


def choice_of(book: Book, state: SimState, run: Run, req: Mapping[str, Any]) -> tuple[str, Json] | None:
    """这次能选的：("exit", 去处) 或 ("plan", 替代的打算)。不在这次的去处和替代去处里、或 enRouteChoice 不对 → None。"""
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
    """过场二选一：选了不是最后一项（不带 = 最后一项）时的候选事件。"""
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
    """「その頃」要的玩家见过的人物（读这一局的全部事件和对话过的人物）。"""
    from zoujin_backend.db import store
    from zoujin_backend.narrator.acts import seen_characters

    async with n.engine.connect() as c:
        log_ = await store.event_log(c, pid, book.version)
    start = initial_state(book.world, role_id)["vars"]["var.player.location"]
    return seen_characters(book, start, log_, await talked(n, pid))


async def run_choose(n: Narrator, task: Task) -> Result:
    from zoujin_backend.narrator.core import MAX_STALE, Stale

    req = dict(task.request or {})
    for _ in range(MAX_STALE):
        pt, state = await n.read(task.pid)
        run = Run.of(pt)
        book = n.library.version(pt["world_model_version"])
        got = choice_of(book, state, run, req)
        if got is None:
            return await n._commit(task, pt["last_seq"], lambda w, b: invalid(INVALID_CHOICE, "invalid_choice"))
        spend = task.spend  # 跟着任务走：重来的、没提交的也算（B-8 第 7 条）
        span = {"playthrough_id": task.pid, "turn_id": task.turn_id, "world_model_version": book.version}
        who = await seen(n, book, task.pid, pt["role_id"])
        if got[0] == "plan":
            alt = got[1]
            accepted = await verify_plan(n, book, state, alt.get("effects", []), "", spend, span)
            if accepted is None:
                return await n._commit(task, pt["last_seq"], lambda w, b: invalid(INVALID_CHOICE, "invalid_choice"))
            label = str(alt["label"])
            plan = (label, [c for c in alt.get("with", []) if c in book.characters], accepted)

            def go_plan(w: Writer, b: Book, who: set[str] = who, plan: Any = plan) -> Planned:
                return transition(n, w, b, task, req, who, plan=plan)

            write: Callable[[Writer, Book], Planned] = go_plan
        else:
            ex = got[1]
            cand = en_route_candidate(book, state, ex, req.get("enRouteChoice"))
            checked = None
            if cand is not None:
                turn = TurnInput(character=None, player=None, act={"kind": "en-route", "exit": ex["id"]})
                checked = await n.pipeline.check_only(book, state, cand, turn, "scoped", spend, span)

            def go_exit(
                w: Writer, b: Book, who: set[str] = who, ex: Json = ex, checked: Checked | None = checked
            ) -> Planned:
                return transition(n, w, b, task, req, who, ex=ex, step1=checked)

            write = go_exit
        try:
            return await n._commit(task, pt["last_seq"], write, spend=spend)
        except Stale:
            log.info("lastSeq 变了，%s 重来", task.turn_id)
    raise RuntimeError(f"{task.turn_id}：lastSeq 一直在变")


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
) -> Planned:
    """幕切换（契约 2.8.1）：给定去处（ex）或成行的打算（plan = (label, with, 打算自己的效果的判定)）。"""
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
    moved = acts.jump(w, landing, t, task.turn_id)
    items = acts.recap(book, w.state["role"], moved.skipped, who, acts.player_promises(w.state))
    msg: Json = {
        "type": "act_transition",
        "fromActId": moved.from_act,
        "toActId": moved.to_act,
        "recap": items,
        "snapshot": None,  # 提交前按落地以后的状态补（core._commit）
    }
    if moved.arrival:
        msg["arrival"] = moved.arrival
    info: Json = {"toAct": moved.to_act, "t": t}
    return Planned(push=[*head, msg], info=info, extra={"playerSpot": landing.spot}, snapshot=True)


# —— 说出打算 ——


def option_ref(book: Book, run: Run, option_id: str) -> Json | None:
    """act_ended 里的一个去处 → PlanAlternative 的形状。"""
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
    """打算自己的效果过第 3〜5 步：在 `Act.plan.effects` 试算之后的状态上判（例：去处让玩家知道了约定，
    才能把约定告诉别人），时长 = 跳过的这段。没有效果的不用判（返回 None 以外的结果由调用方当作过了）。
    被否决返回 None。"""
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
        log.info("Act.plan.effects 试算不了，在原状态上判")
    cand = {
        "actor": "player",
        "type": "action",  # 只用来判效果（改写的输出不收 act-transition）；写进去的是玩家的 act-transition
        "origin": "act",
        "summary": "幕末の打算",
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
        spend = task.spend  # 跟着任务走：重来的、没提交的也算（B-8 第 7 条）
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
            who = await seen(n, book, task.pid, pt["role_id"])
            plan = (label, with_, checked if checked and checked.effects else None)

            def go_plan(w: Writer, b: Book, who: set[str] = who, plan: Any = plan, head: Json = head) -> Planned:
                p = transition(n, w, b, task, req, who, plan=plan, head=[head])
                p.info |= {"accepted": True, "triesLeft": head["triesLeft"], "narration": head["narration"]}
                p.plans_accepted = 1
                return p

            write: Callable[[Writer, Book], Planned] = go_plan
        else:
            lines = [x for x in (clean(s, text, frozenset(), limit=LINE_MAX) for s in out.get("narration", [])) if x]
            lines = lines[:2] or [REFUSAL_FALLBACK]
            if bool(out["accepted"]) and request["hasPlan"]:  # 判过不过：不转述模型的成行说法
                lines = [REFUSAL_FALLBACK]
            alt = alternative(n, book, state, run, out.get("alternative"), text, request)

            def refuse(w: Writer, b: Book, lines: list[str] = lines, alt: Json = alt) -> Planned:
                return refused(w, task, req, lines, alt)

            write = refuse

        await n.wait_window(task)  # 用声音说的打算：定稿推出 3 秒以内可以作废（B-4）
        try:
            return await n._commit(task, pt["last_seq"], write, spend=spend)
        except Stale:
            log.info("lastSeq 变了，%s 重来", task.turn_id)
    raise RuntimeError(f"{task.turn_id}：lastSeq 一直在变")


def reply_to(task: Task, req: Mapping[str, Any]) -> Json:
    """act_plan_result 带 clientMsgId（文字）或 turnId（声音）。"""
    return (
        {"turnId": task.turn_id}
        if req.get("mode") == "voice"
        else {"clientMsgId": req.get("clientMsgId") or task.turn_id}
    )


def alternative(
    n: Narrator, book: Book, state: SimState, run: Run, raw: Json | None, said: str, request: Mapping[str, Any]
) -> Json:
    """替代去处（局上记的形状：PlanAlternative 的四个字段 + kind，打算的还带 with 和 effects）。
    给定去处用去处 ID；另一个打算用 plan_ 加 ULID，label 过滤不过就改给第一个给定去处。"""
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


PUBLIC = ("optionId", "label", "sceneId", "toActId", "tLabel")  # toActId：v1.0.14，局上记的老替代去处没有


def refused(w: Writer, task: Task, req: Mapping[str, Any], lines: list[str], alt: Json) -> Planned:
    """不成行：不写事件，试次加一，替代去处记在局上，幕末页的 freeform 跟着变。"""
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
