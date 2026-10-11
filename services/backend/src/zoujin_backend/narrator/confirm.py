"""意图确认（B-4，api-contract 3.9，backend-design 2.4 第 6 步）：草稿、反问和回答。

- 对话的一轮里，提取标了要确认、又不可逆的候选照常过第 3〜5 步；过了的不写进事件日志，存成草稿（`drafts` 一行），
  这一轮别的候选和 10 分钟照常提交。原来那一轮先结掉（`commit` → `turn_settled`），网关再让人物反问、推 `confirm`
  （`turns.result.confirm`）。
- 同一局同时最多一个草稿，一局最多问 3 次；多出来的、收幕那一轮新提出的按 B-2 丢掉（`candidates_confirm_dropped`）。
  收幕时还开着的按超时关掉，`confirm_closed` 排在 `act_ended` 前面。
- 回答（按钮、声音、超时）都是一行 `kind: "confirm"` 的任务（`store.answer_draft`），叙事者按局串行处理
  （`run_confirm`）：`yes` 按当时的状态从第 3 步重查，过了提交、没过写一条 rejected 的事件，两种都带
  `confirmed: true`、挂在原来那一轮上；`no` 和超时丢掉。关掉就删草稿那一行。
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection
from zoujin_backend.db import store
from zoujin_backend.db.tables import drafts, playthrough_metrics, utterances
from zoujin_backend.narrator.pipeline import Spend, TurnInput, irreversible
from zoujin_backend.narrator.plans import clean, narrate_fallback
from zoujin_backend.narrator.rules import Checked
from zoujin_backend.narrator.view import state_view
from zoujin_backend.narrator.writer import Writer
from zoujin_backend.world import Book

if TYPE_CHECKING:
    from zoujin_backend.narrator.core import Narrator, Planned, Result, Task

log = logging.getLogger("zoujin.narrator")

Json = Any

QUESTION_FALLBACK = "……本気で言っているのか。"
QUESTION_MAX = 30  # 反问的一句最多几个字（3.9）
TIMEOUT_SEC = 30  # 推出 confirm 以后等几秒（3.9 第 3 条）
MAX_ASKS = 3  # 一局最多问几次（S-040）
OPTIONS = ({"optionId": "yes", "label": "本気だ"}, {"optionId": "no", "label": "いや、違う"})
ANSWERS = ("yes", "no")
KEEP = ("actor", "type", "origin", "summary", "causes", "beneficiary")  # 草稿里存的候选字段（不放原话）


@dataclass
class Proposal:
    """这一轮里过了检查、要确认的候选：存成草稿，或者丢掉（已经有草稿开着、问满了、这一轮收了幕）。"""

    checked: Checked
    asked: bool
    question: str
    place: str


def question_of(ask: Mapping[str, Any], said: str | None) -> str:
    """反问的一句照第 3 步 R6 的规则部分查（个人信息的模式、和玩家原话连续 8 字相同），不过用固定的一句。"""
    q = ask.get("question")
    return clean(q if isinstance(q, str) else None, said or "", frozenset(), limit=QUESTION_MAX) or QUESTION_FALLBACK


def proposes(checked: Checked, ask: Mapping[str, Any] | None) -> bool:
    """过了第 3〜5 步、改写以后还是不可逆的大事，才问。"""
    return ask is not None and checked.passed and irreversible({"effects": checked.effects})


def confirm_msg(draft_id: str, character: str, prompt: str) -> Json:
    return {
        "type": "confirm",
        "draftId": draft_id,
        "character": character,
        "prompt": prompt,
        "options": [dict(o) for o in OPTIONS],
        "timeoutSec": TIMEOUT_SEC,
    }


def closed_msg(draft_id: str, option_id: str | None, by: str) -> Json:
    return {"type": "confirm_closed", "draftId": draft_id, "optionId": option_id, "by": by}


# —— 在叙事者提交的事务里（锁着这一局时）——


async def in_commit(
    n: Narrator, c: AsyncConnection, task: Task, w: Writer, planned: Planned
) -> tuple[list[Json], Json | None]:
    """这次提交里和草稿有关的：收幕时关掉开着的、丢掉新提出的；声音的回答写一行任务；新提出的存成草稿。
    返回要排在 act_ended 前面推的（confirm_closed），和网关要做的反问（`turns.result.confirm`）。"""
    push: list[Json] = []
    if w.closed:  # 收幕：不留草稿（数据评审）
        draft = await store.open_draft(c, task.pid, lock=True)
        if draft is not None:
            await c.execute(delete(drafts).where(drafts.c.draft_id == draft["draft_id"]))
            planned.confirms_timeout += 1
            push.append(closed_msg(draft["draft_id"], None, "timeout"))
            log.info("收幕，草稿 %s 按超时关掉", draft["draft_id"])
        planned.dropped += len(planned.proposals)
        return push, None
    if planned.answer is not None:
        draft_id, option_id = planned.answer
        await store.answer_draft(c, n.ids, task.pid, draft_id, option_id, "voice")
    if not planned.proposals:
        return push, None
    first, *rest = planned.proposals
    planned.dropped += len(rest)
    asked = int(
        await c.scalar(
            select(playthrough_metrics.c.confirms_asked).where(playthrough_metrics.c.playthrough_id == task.pid)
        )
        or 0
    )
    if await store.open_draft(c, task.pid) is not None or asked >= MAX_ASKS:
        planned.dropped += 1
        return push, None
    draft_id = n.ids.new("draft")
    cand = first.checked.candidate
    kept = {**{k: cand[k] for k in KEEP if k in cand}, "effects": first.checked.effects, "place": first.place}
    await c.execute(
        insert(drafts).values(
            draft_id=draft_id,
            playthrough_id=task.pid,
            turn_id=task.turn_id,
            character=task.character,
            candidate=kept,
            prompt=first.question,
            asked=first.asked,
        )
    )
    planned.confirms_asked += 1
    return push, {"draftId": draft_id, "character": task.character, "prompt": first.question, "asked": first.asked}


# —— 回答（`kind: "confirm"` 的任务）——


async def run_confirm(n: Narrator, task: Task) -> Result:
    from zoujin_backend.narrator.core import MAX_STALE, Planned, Stale

    req = dict(task.request or {})
    draft_id = str(req.get("draftId"))
    option = req.get("optionId") if req.get("optionId") in ANSWERS else None
    by = str(req.get("by") or "button")
    for _ in range(MAX_STALE):
        pt, state = await n.read(task.pid)
        book = n.library.version(pt["world_model_version"])
        async with n.engine.connect() as c:
            q = select(drafts).where(drafts.c.draft_id == draft_id, drafts.c.playthrough_id == task.pid)
            draft = (await c.execute(q)).mappings().first()
            gone = draft is not None and await deleted(c, draft["turn_id"])
            nth = await closed_count(c, task.pid) + 1
        if draft is None:  # 已经关掉了（别的回答先到、收幕）：什么都不写，不推
            log.info("草稿 %s 已经关掉，忽略这次回答", draft_id)
            return await n._commit(task, None, lambda w, b: Planned(info={"result": "ignored"}))
        span = {"playthrough_id": task.pid, "turn_id": draft["turn_id"], "world_model_version": book.version}
        spend = task.spend  # 跟着任务走：重来的、没提交的也算（B-8 第 7 条）
        checked: Checked | None = None
        narration: list[str] = []
        if option == "yes" and not gone:
            checked = await recheck(n, book, state, dict(draft), spend, span)
            if not checked.passed:
                narration = [await narrate_rejected(n, book, state, dict(draft), checked, spend, span)]
        if n.before_commit is not None:
            await n.before_commit(task)

        shut = Shut(dict(draft), option, by, checked, narration, gone, nth)

        def write(w: Writer, b: Book, shut: Shut = shut) -> Planned:
            return closed(n, w, task, shut)

        try:
            return await n._commit(task, pt["last_seq"], write, spend=spend)
        except Stale:
            log.info("lastSeq 变了，%s 重查", task.turn_id)
    raise RuntimeError(f"{task.turn_id}：lastSeq 一直在变")


async def deleted(c: AsyncConnection, turn_id: str) -> bool:
    """原来那一轮的原话在記憶帳里删掉了（記憶帳的卡做删除；那时草稿按「不是」丢掉）。"""
    found = await c.scalar(
        select(utterances.c.utterance_id).where(utterances.c.turn_id == turn_id, utterances.c.deleted_at.is_not(None))
    )
    return found is not None


async def closed_count(c: AsyncConnection, pid: str) -> int:
    m = playthrough_metrics.c
    row = (
        await c.execute(select(m.confirms_yes, m.confirms_no, m.confirms_timeout).where(m.playthrough_id == pid))
    ).first()
    return sum(int(x or 0) for x in row) if row is not None else 0


async def recheck(
    n: Narrator, book: Book, state: Any, draft: Mapping[str, Any], spend: Spend, span: Mapping[str, Any]
) -> Checked:
    """答了「是」：按此刻的状态从第 3 步重新检查（第 3〜5 步，同 B-2），地点照草稿里候选原来的。两次都超时就重试
    这个任务（同 B-0 的失败重试）。"""
    lines = await n._lines(draft["turn_id"])
    turn = TurnInput(character=draft["character"], player=lines.get("player"), reply=lines.get("character"))
    cand = {k: v for k, v in draft["candidate"].items() if k != "place"}
    v = await n.pipeline.verify(book, state, [cand], turn, 0, spend, span)
    if v.timed_out or not v.checked:
        raise RuntimeError("重查超时")
    return v.checked[0]


async def narrate_rejected(
    n: Narrator,
    book: Book,
    state: Any,
    draft: Mapping[str, Any],
    checked: Checked,
    spend: Spend,
    span: Mapping[str, Any],
) -> str:
    """重查没过：一行地の文说这件事没成（`narrate`，B-3；两次都不行、或过滤不过用固定的一句）。"""
    from zoujin_backend.narrator.pipeline import CallFailed

    request = {
        "worldModelVersion": book.version,
        "state": state_view(book, state).doc,
        "act": {"kind": "confirm", "target": draft["character"]},
        "status": "refused",
        "failedRules": checked.check.get("failedRules", []),
    }
    try:
        r = await n.pipeline.call("narrate", request, spend, span={**span, "status": "refused"})
    except CallFailed:
        return narrate_fallback("refused")
    return clean(str(r.output["text"]), "", frozenset(), limit=60) or narrate_fallback("refused")


@dataclass
class Shut:
    """关掉一个草稿要的：草稿、回答（yes / no / None = 超时）、谁答的、重查的结果、没成时的一行叙事、
    原来那一轮删了没有、这一局第几次。"""

    draft: Json
    option: str | None
    by: str
    checked: Checked | None
    narration: list[str]
    gone: bool
    nth: int


def closed(n: Narrator, w: Writer, task: Task, shut: Shut) -> Planned:
    """关掉草稿：答「是」写那一条事件（`confirmed: true`、`dt: 0`、挂在原来那一轮、地点照原来的），
    推 confirm_closed。"""
    from zoujin_backend.narrator.core import Planned

    draft, option, by, checked, narration = shut.draft, shut.option, shut.by, shut.checked, shut.narration

    planned = Planned(close_draft=draft["draft_id"])
    planned.push.append(closed_msg(draft["draft_id"], option, by))
    answer = option or "timeout"
    if option == "yes":
        planned.confirms_yes = 1
    elif option == "no":
        planned.confirms_no = 1
    else:
        planned.confirms_timeout = 1
    result = "discarded"
    if checked is not None:
        cand = draft["candidate"]
        w.settle(w.state["t"])
        extra = {"beneficiary": cand["beneficiary"]} if "beneficiary" in cand else {}
        ev = w.add(
            w.full(
                t=w.state["t"],
                dt=0,
                actor=cand.get("actor", "player"),
                type=cand.get("type", "say"),
                origin=cand.get("origin", "turn"),
                place=cand.get("place", w.player_place),
                summary=cand["summary"],
                effects=checked.effects if checked.passed else [],
                causes=cand.get("causes", []),
                check=checked.check,
                turn_id=draft["turn_id"],
                confirmed=True,
                **extra,
            )
        )
        checked.candidate = {**checked.candidate, "eventId": ev["eventId"]}
        planned.checked = [checked]
        result = "committed" if checked.passed else "rejected"
        planned.confirms_rejected = 0 if checked.passed else 1
        planned.extra["turnId"] = draft["turn_id"]
        if narration:
            planned.extra["narration"] = narration
    planned.info = {"result": result, "answer": answer, "by": by}
    if narration and checked is not None:
        planned.info["narration"] = narration
    with n.tracer.span(
        "narrator.confirm",
        playthrough_id=task.pid,
        turn_id=draft["turn_id"],
        answer=answer,
        by=by,
        result=result,
        nth=shut.nth,
    ):
        pass
    if shut.gone:
        log.info("草稿 %s 原来那一轮已经删了，丢掉", draft["draft_id"])
    return planned


__all__ = ["MAX_ASKS", "OPTIONS", "QUESTION_FALLBACK", "TIMEOUT_SEC", "Proposal", "confirm_msg", "run_confirm"]
