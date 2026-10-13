"""Intent confirmation (B-4, api-contract 3.9, backend-design 2.4 step 6): drafts, the counter-question and the answer.

- In a dialogue turn, candidates that extraction marked as needing confirmation and that are irreversible go through
  steps 3-5 as usual; those that pass aren't written to the event log but stored as a draft (a `drafts` row), while the
  turn's other candidates and the 10 minutes are committed as usual. The original turn is settled first (`commit` →
  `turn_settled`), then the gateway has the character ask back and pushes `confirm` (`turns.result.confirm`).
- At most one draft per game at a time, and at most 3 questions per game; extra ones, and new ones proposed in the turn
  that closes the act, are dropped as in B-2 (`candidates_confirm_dropped`). A draft still open when the act closes is
  closed as a timeout, with `confirm_closed` pushed before `act_ended`.
- Every answer (button, voice, timeout) is a task row with `kind: "confirm"` (`store.answer_draft`), which the narrator
  handles serially per game (`run_confirm`): `yes` rechecks from step 3 against the state at that time, committing if
  it passes or writing a rejected event if not, both with `confirmed: true` and attached to the original turn; `no` and
  timeouts are dropped. Closing deletes the draft row.

意図の確認（B-4、api-contract 3.9、backend-design 2.4 第 6 ステップ）：下書き、聞き返し、返答。

- 対話の 1 ターンで、抽出が確認要と印を付けた不可逆な候補は通常どおり第 3〜5 ステップを通す。通ったものはイベントログに
  書かず下書き（`drafts` の 1 行）として保存し、このターンのほかの候補と 10 分は通常どおりコミットする。元のターンを
  先に締め（`commit` → `turn_settled`）、そのあとゲートウェイが登場人物に聞き返させて `confirm` をプッシュする
  （`turns.result.confirm`）。
- 同じゲームで同時に開ける下書きは 1 つまで、1 ゲームで聞くのは 3 回まで。あふれたものと、幕を閉じるターンで新たに
  出たものは B-2 のとおり捨てる（`candidates_confirm_dropped`）。幕を閉じるときにまだ開いているものはタイムアウトとして
  閉じ、`confirm_closed` を `act_ended` の前に置く。
- 返答（ボタン、音声、タイムアウト）はどれも `kind: "confirm"` のタスク 1 行（`store.answer_draft`）で、ナレーターが
  ゲームごとに直列に処理する（`run_confirm`）：`yes` はその時点の状態で第 3 ステップから検査し直し、通ればコミット、
  通らなければ rejected のイベントを書く。どちらも `confirmed: true` を付けて元のターンにぶら下げる。`no` と
  タイムアウトは捨てる。閉じたら下書きの行を削除する。
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
QUESTION_MAX = 30  # max characters in the counter-question (3.9) / 聞き返しの一文の最大文字数（3.9）
TIMEOUT_SEC = 30  # seconds to wait after pushing confirm (3.9 item 3) / confirm を送ってから待つ秒数（3.9 第 3 項）
MAX_ASKS = 3  # max questions per game (S-040) / 1 ゲームで聞く最大回数（S-040）
OPTIONS = ({"optionId": "yes", "label": "本気だ"}, {"optionId": "no", "label": "いや、違う"})
ANSWERS = ("yes", "no")
# Candidate fields stored in the draft (never the player's words) / 下書きに保存する候補のフィールド（発話は入れない）
KEEP = ("actor", "type", "origin", "summary", "causes", "beneficiary")


@dataclass
class Proposal:
    """A candidate in this turn that passed the checks and needs confirmation: stored as a draft, or dropped (a draft
    is already open, the question limit is reached, or this turn closed the act).

    このターンで検査を通り、確認が要る候補：下書きとして保存するか捨てる（すでに下書きが開いている、聞く回数を
    使い切った、このターンで幕を閉じた）。
    """

    checked: Checked
    asked: bool
    question: str
    place: str


def question_of(ask: Mapping[str, Any], said: str | None) -> str:
    """The counter-question is checked like the rule part of step 3's R6 (personal-information patterns, 8 consecutive
    characters identical to the player's words); if it fails, use the fixed line.

    聞き返しの一文は第 3 ステップ R6 の規則部分と同じく検査する（個人情報のパターン、プレイヤーの発話と 8 文字連続で
    一致）。通らなければ固定の一文を使う。
    """
    q = ask.get("question")
    return clean(q if isinstance(q, str) else None, said or "", frozenset(), limit=QUESTION_MAX) or QUESTION_FALLBACK


def proposes(checked: Checked, ask: Mapping[str, Any] | None) -> bool:
    """Ask only for major irreversible things that passed steps 3-5 and are still irreversible after rewriting.

    第 3〜5 ステップを通り、書き換え後も不可逆な大きなことだけを聞く。
    """
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


# —— Inside the narrator's commit transaction (while the game is locked) ——
# —— ナレーターのコミットのトランザクション内（このゲームをロックしている間） ——


async def in_commit(
    n: Narrator, c: AsyncConnection, task: Task, w: Writer, planned: Planned
) -> tuple[list[Json], Json | None]:
    """The draft-related parts of this commit: when the act closes, close the open draft and drop new ones; write a task
    row for a voice answer; store a new proposal as a draft. Returns what must be pushed before act_ended
    (confirm_closed), and the counter-question the gateway should ask (`turns.result.confirm`).

    このコミットのうち下書きに関わる部分：幕を閉じるときは開いている下書きを閉じ、新しく出たものを捨てる。音声の返答は
    タスクを 1 行書く。新しく出たものは下書きとして保存する。act_ended の前にプッシュするもの（confirm_closed）と、
    ゲートウェイが行う聞き返し（`turns.result.confirm`）を返す。
    """
    push: list[Json] = []
    # Closing the act or entering the ending: keep no drafts (data review).
    # 幕を閉じる・エンディングに入る：下書きを残さない（データレビュー）。
    if w.closed or w.ending is not None:
        draft = await store.open_draft(c, task.pid, lock=True)
        if draft is not None:
            await c.execute(delete(drafts).where(drafts.c.draft_id == draft["draft_id"]))
            planned.confirms_timeout += 1
            push.append(closed_msg(draft["draft_id"], None, "timeout"))
            log.info(
                "Act closed; draft %s closed as a timeout / 幕を閉じたので下書きをタイムアウトとして閉じる",
                draft["draft_id"],
            )
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


# —— Answers (tasks with `kind: "confirm"`) / 返答（`kind: "confirm"` のタスク） ——


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
        # Already closed (another answer arrived first, or the act closed): write nothing, push nothing.
        # すでに閉じている（別の返答が先に届いた、幕を閉じた）：何も書かず、プッシュもしない。
        if draft is None:
            log.info(
                "Draft %s already closed; ignoring this answer / 下書きはすでに閉じているので、この返答は無視する",
                draft_id,
            )
            return await n._commit(task, None, lambda w, b: Planned(info={"result": "ignored"}))
        span = {"playthrough_id": task.pid, "turn_id": draft["turn_id"], "world_model_version": book.version}
        # Follows the task: retries and uncommitted attempts count too (B-8 item 7).
        # タスクに付いて回る：やり直しやコミットしなかった分も数える（B-8 第 7 項）。
        spend = task.spend
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
            log.info("lastSeq changed; rechecking %s / lastSeq が変わったので検査し直す", task.turn_id)
    raise RuntimeError(f"{task.turn_id}: lastSeq keeps changing / {task.turn_id}：lastSeq が変わり続けている")


async def deleted(c: AsyncConnection, turn_id: str) -> bool:
    """The original turn's words were deleted in the 記憶帳 (the 記憶帳 card does deletion; the draft is then dropped as
    a "no").

    元のターンの発話が記憶帳で削除された（削除は記憶帳のカードが担当。そのとき下書きは「いいえ」として捨てる）。
    """
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
    """Answered "yes": recheck from step 3 against the current state (steps 3-5, as in B-2), with the place kept as
    the draft candidate's original one. If both tries time out, retry this task (like B-0's failure retries).

    「はい」と答えた：現在の状態で第 3 ステップから検査し直す（第 3〜5 ステップ、B-2 と同じ）。場所は下書きの候補の
    元のものを使う。2 回ともタイムアウトしたらこのタスクをやり直す（B-0 の失敗時のリトライと同じ）。
    """
    lines = await n._lines(draft["turn_id"])
    turn = TurnInput(character=draft["character"], player=lines.get("player"), reply=lines.get("character"))
    cand = {k: v for k, v in draft["candidate"].items() if k != "place"}
    v = await n.pipeline.verify(book, state, [cand], turn, 0, spend, span)
    if v.timed_out or not v.checked:
        raise RuntimeError("Recheck timed out / 再検査がタイムアウト")
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
    """The recheck failed: one line of 地の文 saying it didn't happen (`narrate`, B-3; if both tries fail or the filter
    rejects it, use the fixed line).

    再検査で通らなかった：それが起きなかったと告げる地の文を 1 行（`narrate`、B-3。2 回ともだめ、またはフィルターを
    通らなければ固定の一文）。
    """
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
    """What closing a draft needs: the draft, the answer (yes / no / None = timeout), who answered, the recheck result,
    the narration line when it didn't happen, whether the original turn was deleted, and which close this is in the
    game.

    下書きを閉じるのに要るもの：下書き、返答（yes / no / None = タイムアウト）、誰が答えたか、再検査の結果、起きなかった
    ときの地の文 1 行、元のターンが削除されたか、このゲームで何回目か。
    """

    draft: Json
    option: str | None
    by: str
    checked: Checked | None
    narration: list[str]
    gone: bool
    nth: int


def closed(n: Narrator, w: Writer, task: Task, shut: Shut) -> Planned:
    """Close the draft: on "yes" write that event (`confirmed: true`, `dt: 0`, attached to the original turn, with the
    original place), and push confirm_closed.

    下書きを閉じる：「はい」ならそのイベントを書き（`confirmed: true`、`dt: 0`、元のターンにぶら下げ、場所は元のまま）、
    confirm_closed をプッシュする。
    """
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
        log.info(
            "Draft %s: the original turn was already deleted; dropping / 元のターンは削除済みなので下書きを捨てる",
            draft["draft_id"],
        )
    return planned


__all__ = ["MAX_ASKS", "OPTIONS", "QUESTION_FALLBACK", "TIMEOUT_SEC", "Proposal", "confirm_msg", "run_confirm"]
