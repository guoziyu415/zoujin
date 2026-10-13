"""Narrator skeleton (B-0 item 7): take tasks per game → extraction and checks outside the transaction →
single-transaction commit → NOTIFY.

A task is a row of the turns table (backend-design 3.4):
- open: start a game. W-1's initial_state, settled to the role's startT, with beats due before the start written as
  system events.
- talk: one dialogue turn. The pipeline (`narrator/pipeline.py`: triage → extraction → step 3 rules → step 4 model
  check → rewrite, downgrade or reject) → commit the candidate events (rejected ones too, with empty effects), the
  turn's time (a say event that only advances the clock), and the beats that come due in that time. If extraction or
  check times out twice: commit only the clock event, drop the candidates, and record one in `playthrough_metrics`.
- advance: fast-forward (only for tests and evals).
- B-3: action (`narrator/actions.py`), choose (choosing a destination at the end of an act), plan (stating a plan at
  the end of an act, `narrator/plans.py`). After each commit, check whether the act has closed (`Writer.closed`): if
  so, record the end-of-act destinations on the run and push `act_ended`. Dialogue and actions whose turn comes after
  the act closes and before a choice is made take 0 minutes, write no events and call no models. Messages to push after
  commit (set pieces, turn_settled, action_result, act_plan_result, act_transition, act_ended) are recorded in order in
  `turns.result`, and the gateway pushes them in that order after pushing the commit.
- B-4: confirm (answering an intent confirmation, `narrator/confirm.py`); candidates in dialogue needing confirmation
  are stored as drafts. Dialogue and plans spoken by voice have a commit window (`turns.commit_after`): once judged,
  wait if it isn't time yet (without holding a transaction); meanwhile the gateway may retract the turn
  (`status = retracted`), and if commit finds it is no longer leased, the result is dropped and no message is pushed.
  Before taking a task, write timeout tasks for drafts that have expired.
- B-13: if the committed events call for memories (`narrator/memory.py`), the commit transaction doesn't NOTIFY yet;
  after the transaction the model writes the memories in parallel (no transaction held, no resend), and a second
  transaction stores them, records the counts, writes this commit's memory changes into `turns.result.memories`, and
  then NOTIFYs. Whatever goes wrong while writing memories, NOTIFY still happens, and the turn's result is unaffected.

Strictly serial per game: taking a task locks the game's row, and nothing is taken while an unexpired lease exists.
Commit locks again and verifies lastSeq hasn't changed; if it has, the result is dropped and redone from step 3 with
the new state (without re-extracting). Any failed step rolls back the whole turn, the task goes back on the queue and
is retried with the same idempotency key; after three failures it is recorded as no_response. The ledger hitting its
limit (`BudgetStop`), the first 429 (`RateLimited`) and a missing replay (`ReplayMissing`) aren't retried: the task
goes back on the queue and the exception is raised.

ナレーターの骨組み（B-0 第 7 項）：ゲームごとにタスクを取る → トランザクションの外で抽出と検査 →
単一トランザクションでコミット → NOTIFY。

タスクは turns テーブルの 1 行（backend-design 3.4）：
- open：ゲーム開始。W-1 の initial_state から役柄の startT まで settle し、開始前に時刻が来たビートは
  システムイベントとして書く。
- talk：対話 1 ターン。パイプライン（`narrator/pipeline.py`：振り分け → 抽出 → 第 3 ステップの規則 → 第 4 ステップの
  モデルの検査 → 書き換え、格下げ、または却下）→ 候補イベント（却下されたものも effects を空にして書く）、このターンの
  時間（時計を進めるだけの say イベント 1 つ）、その間に時刻が来たビートをコミットする。抽出か検査が 2 回とも
  タイムアウトしたら、時計のイベントだけをコミットし、候補は捨て、`playthrough_metrics` に 1 回記録する。
- advance：早送り（テストと評価専用）。
- B-3：action（アクション、`narrator/actions.py`）、choose（幕末の行き先の選択）、plan（幕末のプランの表明、
  `narrator/plans.py`）。コミットのたびにこの幕が閉じたかを見る（`Writer.closed`）：閉じたら幕末の行き先を
  ゲームに記録し、`act_ended` をプッシュする。幕を閉じたあと、選ぶ前に順番が来た対話とアクションは 0 分で、
  イベントを書かず、モデルも呼ばない。コミット後にプッシュするメッセージ（演出、turn_settled、action_result、
  act_plan_result、act_transition、act_ended）は順に `turns.result` に記録し、ゲートウェイは commit を
  プッシュしたあとその順にプッシュする。
- B-4：confirm（意図の確認への返答、`narrator/confirm.py`）。対話で確認が要る候補は下書きとして保存する。対話と音声で
  言ったプランにはコミットの猶予（`turns.commit_after`）がある：判定が済んでも時間前なら待ち（トランザクションは
  保持しない）、その間ゲートウェイはこのターンを取り消せる（`status = retracted`）。コミット時に leased でなくなって
  いれば結果を捨て、メッセージは何もプッシュしない。タスクを取る前に、期限の来た下書きにタイムアウトのタスクを書く。
- B-13：コミットしたイベントに記憶を書くべきものがあれば（`narrator/memory.py`）、コミットのトランザクションではまだ
  NOTIFY しない。トランザクションのあとモデルを並行に呼んで記憶を書き（トランザクションは保持せず、再送もしない）、
  2 つ目のトランザクションで記憶を保存し、件数を記録し、今回の記憶の変化を `turns.result.memories` に書いてから
  NOTIFY する。記憶の書き込みで何が起きても NOTIFY はし、このターンの結果には影響しない。

同じゲームは厳密に直列：タスクを取るときにこのゲームの行をロックし、期限切れでないリースがあれば取らない。コミット時に
もう一度ロックして lastSeq が変わっていないか確かめる。変わっていれば結果を捨て、新しい状態で第 3 ステップから
やり直す（抽出はやり直さない）。どのステップで失敗してもターン全体をロールバックし、タスクをキューに戻して同じ冪等キーで
再試行する。3 回とも失敗したら no_response を記録する。台帳が上限に達した（`BudgetStop`）、最初の 429
（`RateLimited`）、リプレイがない（`ReplayMissing`）ときは再試行しない：タスクをキューに戻し、例外を上に投げる。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, cast

from sqlalchemy import and_, delete, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from zoujin_backend.config import DEADLINES
from zoujin_backend.db import store
from zoujin_backend.db.events import recorded_at, to_row
from zoujin_backend.db.store import Run
from zoujin_backend.db.tables import (
    drafts,
    playthrough_metrics,
    playthroughs,
    turns,
    utterances,
    world_state,
)
from zoujin_backend.db.tables import events as events_t
from zoujin_backend.ids import IdGen
from zoujin_backend.models.armor import Armor
from zoujin_backend.models.text import ReplayMissing, Stop, TextModel
from zoujin_backend.narrator import acts, advance, confirm, ending, memory
from zoujin_backend.narrator.pipeline import Counts, Extracted, Pipeline, Spend, TurnInput, Verified
from zoujin_backend.narrator.rules import Checked
from zoujin_backend.narrator.writer import Writer
from zoujin_backend.projection import is_visible, snapshot
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.trace import Tracer
from zoujin_backend.world import Book, Library
from zoujin_worldsim import SimState, initial_state, role_of

log = logging.getLogger("zoujin.narrator")

Json = Any

# NOTIFY after commit; the gateway LISTENs / コミット後に NOTIFY し、ゲートウェイが LISTEN する
CHANNEL = "zoujin_commit"
LEASE = timedelta(seconds=30)
MAX_ATTEMPTS = 3
MAX_STALE = 5
CHECKER_CLOCK = "b0:clock"
PASSED = {"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER_CLOCK}


class Stale(Exception):
    """lastSeq changed after reading (something else was committed in between): this result is void; redo from step 3.

    読み込んだあと lastSeq が変わった（間に別のものがコミットされた）：今回の結果は無効にし、第 3 ステップからやり直す。
    """


class Gone(Exception):
    """The task no longer belongs to this run (already settled, retracted, or the game was deleted).

    タスクはもう今回の処理の担当ではない（判定済み、取り消された、ゲームが削除された）。
    """


@dataclass(frozen=True)
class Task:
    turn_id: str
    pid: str
    kind: str
    input_mode: str | None
    character: str | None
    minutes: int | None
    key: str
    attempts: int
    client_msg_id: str | None = None  # B-3: clientMsgId of actions and end of act / アクションと幕末の clientMsgId
    request: Json | None = None  # B-3: action and end-of-act request (turns.request) / アクションと幕末のリクエスト
    # B-4: when the commit window ends (time.monotonic()); None = no window.
    # B-4：コミットの猶予がいつまでか（time.monotonic()）。None = 猶予なし。
    window_until: float | None = None
    flags: frozenset[str] = frozenset()  # B-12: step 0 safety screening flags (turns.flags) / 第 0 ステップの印
    # Money already spent on this task (B-8 item 7): the passes redone from the check (Stale) added together; when
    # committed it goes into playthrough_metrics with the commit, and when not (retracted, failed, stopped)
    # `Narrator.charge` records it, so each game's spend matches the ledger.
    # この処理ですでに使ったお金（B-8 第 7 項）：検査からやり直した（Stale）分をまとめたもの。コミットしたら
    # コミットと一緒に playthrough_metrics に書き、コミットしなかった（取り消し、エラー、停止）ら
    # `Narrator.charge` が補って記録する。こうしてゲームごとの支出が台帳と一致する。
    spend: Spend = field(default_factory=Spend, compare=False)


# Tasks whose narrator events carry turnId (contract Event.turnId: this turn, this action, this end of act).
# ナレーターのイベントに turnId を付けるタスク（契約 Event.turnId：このターン、このアクション、この幕末）。
TURN_KINDS = ("talk", "action", "choose", "plan")
# Tasks that must give the frontend a result even when they fail (the gateway catches up from turns).
# 失敗してもフロントエンドに結果を返す必要のあるタスク（ゲートウェイが turns から補ってプッシュする）。
ANSWERED = ("talk", "action", "choose", "plan")


@dataclass
class Planned:
    """The conclusions of a task beyond what it wrote in the commit transaction.

    タスクがコミットのトランザクションで書いたもの以外の結論。
    """

    outcome: str | None = None  # talk: turn_settled.outcome
    minutes: int = 0  # minutes this turn took / このターンにかかった分数
    checked: list[Checked] = field(default_factory=list)
    # Messages to push in order after commit (after beat-timed set pieces).
    # コミット後に順にプッシュするメッセージ（ビートのタイミングの演出のあと）。
    push: list[Json] = field(default_factory=list)
    # What the eval entry point needs (status, narration, accepted...).
    # 評価の入口が要るもの（status、narration、accepted…）。
    info: dict[str, Any] = field(default_factory=dict)
    # What goes into turns.result (playerSpot, reason) / turns.result に記録するもの（playerSpot、reason）
    extra: dict[str, Any] = field(default_factory=dict)
    # The act_transition in push needs the snapshot after landing filled in.
    # push の act_transition に着地後のスナップショットを補う必要がある。
    snapshot: bool = False
    actions: int = 0
    actions_ended: int = 0
    plans_accepted: int = 0
    plans_refused: int = 0
    # B-4: this turn's candidates needing confirmation (the first is stored as a draft, the rest dropped), a voice
    # answer to the open draft (draftId, yes / no), the draft closed this time, confirmation counts, and dropped
    # candidates that needed confirmation.
    # B-4：このターンの確認が要る候補（最初のものを下書きに保存し、残りは捨てる）、開いている下書きへの音声の返答
    # （draftId, yes / no）、今回閉じた下書き、確認の件数、捨てた確認が要る候補。
    proposals: list[confirm.Proposal] = field(default_factory=list)
    answer: tuple[str, str] | None = None
    close_draft: str | None = None
    confirms_asked: int = 0
    confirms_yes: int = 0
    confirms_no: int = 0
    confirms_timeout: int = 0
    confirms_rejected: int = 0
    dropped: int = 0
    # B-16: character plan events and director events written by world advancement.
    # B-16：世界の進行が書いた登場人物のプランのイベントとディレクターのイベント。
    world_events: int = 0
    director_events: int = 0


@dataclass
class Result:
    """What one commit wrote (for the eval's StepResult and tests).

    1 回のコミットで書いたもの（評価の StepResult とテスト用）。
    """

    task: Task
    events: list[Json]
    state: SimState
    outcome: str | None = None
    minutes: int = 0
    checked: list[Checked] = field(default_factory=list)
    # What the gateway should push (set pieces, results, end of act, act transition).
    # ゲートウェイがプッシュするもの（演出、結果、幕末、幕切り替え）。
    push: list[Json] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)
    pieces: list[str] = field(default_factory=list)  # set piece IDs played this time / 今回演じた演出の ID
    # B-13: memories written this time (memory_items rows) / B-13：今回書いた記憶（memory_items の行）
    memories: list[Json] = field(default_factory=list)


def talk_minutes(book: Book, state: SimState) -> int:
    """Story time for one exchange: 10 minutes in acts 1-3, 15 minutes in act 4 (api-contract 3.7).

    1 往復の物語の時間：第一〜三幕は 10 分、第四幕は 15 分（api-contract 3.7）。
    """
    act4 = max(book.world["acts"], key=lambda a: a["order"])["start"]["t"]
    key = "talkTurnMinutesAct4" if state["t"] >= act4 else "talkTurnMinutes"
    return int(book.world["pacing"][key])


@dataclass
class Narrator:
    engine: AsyncEngine
    library: Library
    text: TextModel
    schemas: SchemaBook
    ids: IdGen = field(default_factory=IdGen)
    # For tests: called before each commit step (with the step name); raising fails that step.
    # テスト用：コミットの各ステップの前に呼ぶ（ステップ名を渡す）。例外を投げるとそのステップで失敗する。
    fault: Callable[[str], None] = field(default=lambda step: None)
    # For tests: called after checking and before commit (simulates another commit in between).
    # テスト用：検査のあと、コミットの前に呼ぶ（間に別のコミットがあった状況を再現する）。
    before_commit: Callable[[Task], Awaitable[None]] | None = None
    tracer: Tracer = field(default_factory=Tracer)
    deadlines: Mapping[str, float] = field(default_factory=lambda: dict(DEADLINES))
    # The player-facing narrator (narrator/app.py) uses "degrade"; see Pipeline.
    # プレイヤー向けのナレーター（narrator/app.py）は "degrade"。Pipeline を参照。
    on_rate_limit: str = "stop"
    # B-13: the second filter for memory lines (None = skip it; tests only).
    # B-13：記憶の一文に対する 2 段目のフィルター（None = このフィルターを通さない。テスト専用）。
    armor: Armor | None = None
    # B-16: world advancement (act transitions, after key moments, mid-act); False = no model calls, no tasks queued.
    # B-16：世界の進行（幕切り替え、重要な瞬間のあと、各幕の中盤）。False = モデルを呼ばず、タスクも積まない。
    world_advance: bool = True

    def __post_init__(self) -> None:
        self.pipeline = Pipeline(self.text, self.schemas, self.ids, self.tracer, self.deadlines, self.on_rate_limit)
        self.memorizer = memory.Memorizer(
            self.text,
            self.armor,
            self.ids,
            self.tracer,
            deadline=self.deadlines.get("memory"),
            raise_stops=self.on_rate_limit == "stop",
        )

    # —— Taking tasks / タスクを取る ——

    async def run(self, pid: str) -> list[Result]:
        """Work through this game's queued tasks in order; return right away if another process is working on it.

        このゲームに積まれたタスクを順に片づける。別のプロセスがこのゲームを処理中ならすぐ戻る。
        """
        done: list[Result] = []
        while True:
            await self.expire(pid)
            task = await self.claim(pid)
            if task is None:
                return done
            try:
                done.append(await self.process(task))
            except Gone:
                log.info("Task %s no longer needs doing / タスクはもう不要", task.turn_id)
                await self.charge(task)
            # Not retried: back on the queue, and the whole run stops / 再試行しない：キューに戻し、全体を止める
            except (Stop, ReplayMissing) as e:
                log.warning("Task %s stopped: %s / タスクを停止", task.turn_id, type(e).__name__)
                await self.charge(task)
                await self.release(task, failed=False)
                raise
            except Exception:
                log.exception("Task %s failed (attempt %d) / タスクが失敗", task.turn_id, task.attempts)
                await self.charge(task)
                await self.release(task, failed=task.attempts >= MAX_ATTEMPTS)

    async def charge(self, task: Task) -> None:
        """This run didn't commit (the turn was retracted, the game deleted, an error retried, or a stop), but the money
        already spent still goes into the game's `playthrough_metrics` (B-8 item 7: what a retracted turn spent in its
        window, and the retries after failures). If the game is already deleted there is nowhere to record it (0 rows).

        今回の処理はコミットしなかった（ターンの取り消し、ゲームの削除、エラーでのやり直し、停止）が、すでに使ったお金は
        このゲームの `playthrough_metrics` に記録する（B-8 第 7 項：取り消されたターンが猶予中に使った分、失敗後に
        やり直した分）。ゲームがすでに削除されていれば記録先がない（0 行）。
        """
        if not any(task.spend.usd.values()):
            return
        async with self.engine.begin() as c:
            await c.execute(
                update(playthrough_metrics)
                .where(playthrough_metrics.c.playthrough_id == task.pid)
                .values(cost_values(task.spend))
            )
        task.spend.usd.clear()

    async def expire(self, pid: str) -> None:
        """Write timeout tasks for expired drafts (B-4: so they close even if the gateway's 30-second timer went away
        with its connection).

        期限の来た下書きにタイムアウトのタスクを書く（B-4：
        ゲートウェイの 30 秒のタイマーが接続とともに消えても閉じられる）。
        """
        async with self.engine.begin() as c:
            for draft_id in await store.expire_drafts(c, self.ids, pid):
                log.info(
                    "Draft %s expired; writing a timeout task / 下書きの期限切れ、タイムアウトのタスクを書く", draft_id
                )

    async def claim(self, pid: str) -> Task | None:
        async with self.engine.begin() as c:
            live = await c.execute(
                select(playthroughs.c.playthrough_id).where(playthroughs.c.playthrough_id == pid).with_for_update()
            )
            if live.first() is None:
                return None
            now = func.now()
            busy = await c.execute(
                select(turns.c.turn_id).where(
                    turns.c.playthrough_id == pid, turns.c.status == "leased", turns.c.lease_until > now
                )
            )
            if busy.first() is not None:
                return None
            window = func.extract("epoch", turns.c.commit_after - func.clock_timestamp()).label("window")
            row = (
                (
                    await c.execute(
                        select(turns, window)
                        .where(
                            turns.c.playthrough_id == pid,
                            or_(
                                turns.c.status == "pending",
                                and_(turns.c.status == "leased", turns.c.lease_until <= now),
                            ),
                        )
                        .order_by(turns.c.created_at, turns.c.turn_id)
                        .limit(1)
                        .with_for_update(skip_locked=True)
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            await c.execute(
                update(turns)
                .where(turns.c.turn_id == row["turn_id"])
                .values(status="leased", lease_until=now + LEASE, attempts=turns.c.attempts + 1)
            )
            left = float(row["window"]) if row["window"] is not None else 0.0
            return Task(
                turn_id=row["turn_id"],
                pid=pid,
                kind=row["kind"],
                input_mode=row["input_mode"],
                character=row["character"],
                minutes=row["minutes"],
                key=row["idempotency_key"],
                attempts=row["attempts"] + 1,
                client_msg_id=row["client_msg_id"],
                request=row["request"],
                window_until=time.monotonic() + left if left > 0 else None,
                flags=frozenset(row["flags"] or ()),
            )

    async def wait_window(self, task: Task) -> None:
        """The commit window (B-4): once judged, wait until commit_after without holding a transaction. The turn may be
        retracted meanwhile; commit will notice.

        コミットの猶予（B-4）：判定が済んでも commit_after 前なら待ち、トランザクションは保持しない。その間にターンが
        取り消されることがあり、コミット時に分かる。
        """
        if task.window_until is not None:
            await asyncio.sleep(max(0.0, task.window_until - time.monotonic()))

    async def release(self, task: Task, *, failed: bool) -> None:
        async with self.engine.begin() as c:
            if not failed:
                await c.execute(
                    update(turns)
                    .where(turns.c.turn_id == task.turn_id, turns.c.status == "leased")
                    .values(status="pending", lease_until=None)
                )
                return
            res = await c.execute(
                update(turns)
                .where(turns.c.turn_id == task.turn_id, turns.c.status == "leased")
                .values(
                    status="failed",
                    outcome="no_response",
                    minutes=0,
                    lease_until=None,
                    settled_at=func.now(),
                    flags=None,
                )
                .returning(turns.c.turn_id)
            )
            if res.first() is not None and task.kind in ANSWERED:
                last = await c.scalar(select(playthroughs.c.last_seq).where(playthroughs.c.playthrough_id == task.pid))
                await self._notify(c, task, seq=int(last or 0), outcome="no_response")

    # —— Processing / 処理 ——

    async def process(self, task: Task) -> Result:
        if task.kind == ending.KIND:
            return await ending.run_ending(self, task)
        # Its turn came only after the ending started: no events, no model calls (B-9).
        # エンディングに入ってから順番が来たもの：イベントを書かず、モデルも呼ばない（B-9）。
        if await self._ended(task.pid):
            return await self._commit(task, None, lambda w, book: self._after_end(task))
        if task.kind == "open":
            return await self._commit(task, None, lambda w, book: self._open(w, book))
        if task.kind == "advance":
            minutes = int(task.minutes or 0)
            return await self._commit(task, None, lambda w, book: self._advance(w, minutes))
        if task.kind == "talk":
            return await self._talk(task)
        if task.kind == "action":
            from zoujin_backend.narrator.actions import run_action

            return await run_action(self, task)
        if task.kind == "choose":
            from zoujin_backend.narrator.plans import run_choose

            return await run_choose(self, task)
        if task.kind == "plan":
            from zoujin_backend.narrator.plans import run_plan

            return await run_plan(self, task, (await self._lines(task.turn_id)).get("player"))
        if task.kind == "confirm":
            return await confirm.run_confirm(self, task)
        if task.kind == advance.KIND:
            return await advance.run_world(self, task)
        raise ValueError(f"Unknown task {task.kind} / 不明なタスク {task.kind}")

    async def _ended(self, pid: str) -> bool:
        async with self.engine.connect() as c:
            status = await c.scalar(select(playthroughs.c.status).where(playthroughs.c.playthrough_id == pid))
        if status is None:
            raise Gone(pid)
        return bool(status != "active")

    def _after_end(self, task: Task) -> Planned:
        """Tasks whose turn comes only after the ending started: dialogue gets no_response, actions refused, end of act
        invalid_request; nothing is pushed for the rest.

        エンディング開始後に順番が来たタスク：対話は no_response、アクションは refused、幕末は invalid_request、
        それ以外は何もプッシュしない。
        """
        from zoujin_backend.narrator.actions import ended
        from zoujin_backend.narrator.plans import INVALID_REQUEST, invalid

        if task.kind == "talk":
            return self._ended_talk(task)
        if task.kind == "action":
            return ended(dict(task.request or {}))
        if task.kind in ("choose", "plan"):
            return invalid(INVALID_REQUEST, "invalid_request")
        return Planned()

    async def read(self, pid: str) -> tuple[dict[str, Any], SimState]:
        async with self.engine.connect() as c:
            pt = (await c.execute(select(playthroughs).where(playthroughs.c.playthrough_id == pid))).mappings().one()
            st = await c.scalar(select(world_state.c.state).where(world_state.c.playthrough_id == pid))
        if st is None:
            raise Gone(pid)
        return dict(pt), cast(SimState, st)

    async def _talk(self, task: Task) -> Result:
        pt, state = await self.read(task.pid)
        # Its turn came after the act closed: no_response, 0 minutes, no model calls.
        # 幕を閉じたあとに順番が来た：no_response、0 分、モデルを呼ばない。
        if pt["act_end"] is not None:
            await self.wait_window(task)
            return await self._commit(task, pt["last_seq"], lambda w, book: self._ended_talk(task))
        book = self.library.version(pt["world_model_version"])
        lines = await self._lines(task.turn_id)
        turn = TurnInput(
            character=task.character,
            player=lines.get("player"),
            reply=lines.get("character"),
            mode=task.input_mode or "voice",
            flags=task.flags,
        )
        # Follows the task: retries and uncommitted attempts count too (B-8 item 7).
        # タスクに付いて回る：やり直しやコミットしなかった分も数える（B-8 第 7 項）。
        spend = task.spend
        span = {"playthrough_id": task.pid, "turn_id": task.turn_id}
        draft = await self._waiting(task)
        asking = {"prompt": draft["prompt"], "summary": draft["candidate"]["summary"]} if draft else None
        # S-069: an ambiguous line extracts no events, only records time (B-12).
        # S-069：どちらとも取れる一言からはイベントを抽出せず、時間だけを記録する（B-12）。
        if "ambiguous" in turn.flags and asking is None:
            extracted = Extracted([], Counts())
        else:
            extracted = await self.pipeline.extract(book, state, turn, spend, span, drafts=True, confirm=asking)
        answer = (draft["draft_id"], extracted.answer) if draft and extracted.answer in confirm.ANSWERS else None
        for _ in range(MAX_STALE):
            if extracted.timed_out:
                verified = Verified([], Counts())
            else:
                minutes = talk_minutes(book, state)
                verified = await self.pipeline.verify(book, state, extracted.candidates, turn, minutes, spend, span)
            await self.wait_window(task)
            if self.before_commit is not None:
                await self.before_commit(task)
            try:
                plan = self._talk_plan(task, verified.checked, extracted.confirm, answer, turn.player)
                counts = extracted.counts + verified.counts
                return await self._commit(task, pt["last_seq"], plan, spend=spend, counts=counts)
            except Stale:
                log.info("lastSeq changed; checking %s again / lastSeq が変わったので検査からやり直す", task.turn_id)
                pt, state = await self.read(task.pid)
        raise RuntimeError(f"{task.turn_id}: lastSeq keeps changing / {task.turn_id}：lastSeq が変わり続けている")

    async def _lines(self, turn_id: str) -> dict[str, str | None]:
        """This turn's words from the player and the character. For the character take the first line: the intent
        confirmation's counter-question (B-4) is also attached to the original turn, after the reply.

        このターンのプレイヤーと登場人物の発話。登場人物は最初の一言を取る：意図の確認の聞き返し（B-4）も
        元のターンの下にぶら下がり、返答のあとに並ぶ。
        """
        async with self.engine.connect() as c:
            rows = (
                await c.execute(
                    select(utterances.c.speaker, utterances.c.text)
                    .where(utterances.c.turn_id == turn_id)
                    .order_by(utterances.c.recorded_at)
                )
            ).all()
        out: dict[str, str | None] = {}
        for speaker, text in rows:
            out.setdefault("player" if speaker == "player" else "character", text)
        return out

    async def _waiting(self, task: Task) -> dict[str, Any] | None:
        """This turn is addressed to the character who asked back, and the draft is still open (not expired, not yet
        answered): extraction must judge whether the line is an answer (B-4).

        このターンは聞き返した登場人物に向けたもので、下書きがまだ開いている（期限前で、まだ返答がない）：抽出は
        その一言が返答かどうかを判定する（B-4）。
        """
        async with self.engine.connect() as c:
            draft = await store.open_draft(c, task.pid)
            if draft is None or draft["character"] != task.character:
                return None
            if draft["expires_at"] is not None and draft["expires_at"] <= await c.scalar(select(func.now())):
                return None
            if await store.answered(c, task.pid, draft["draft_id"]):
                return None
        return draft

    # —— Which events each task kind writes (called inside the commit transaction while the game is locked) ——
    # —— タスクの種類ごとに書くイベント（コミットのトランザクションの中、このゲームをロックしている間に呼ぶ） ——

    def _open(self, w: Writer, book: Book) -> Planned:
        role = role_of(book.world, w.state["role"])
        start = int(role["startT"])
        w.settle(start)
        if w.state["t"] < start:
            act = book.acts[role.get("startAct") or book.act_of(w.state["vars"])]
            w.add(
                w.full(
                    t=start,
                    dt=0,
                    actor="system",
                    type="action",
                    origin="act",
                    place=w.player_place,
                    summary=f"{act['title']}、物語が始まった",
                    effects=[],
                    check=PASSED,
                )
            )
        return Planned()

    def _advance(self, w: Writer, minutes: int) -> Planned:
        """Settle to t0 + minutes, then write an event that only advances the clock (contract: the clock is only moved
        by events). If the act closes during that time, stop at the moment it closes; after it has closed and before a
        choice is made, don't move.

        t0 + minutes まで精算し、時計を進めるだけのイベントを 1 つ書く（契約：時計はイベントだけで進める）。その間に
        この幕が閉じたら閉じた時点で止める。幕を閉じたあと、まだ選んでいないときは動かさない。
        """
        if w.run.act_end is not None:
            return Planned()
        t0 = w.state["t"]
        t2 = t0 + minutes
        if w.guard:
            t2 = min(t2, int(acts.current_act(w.book, w.state)["end"]["atLatest"]))
        w.settle(t2)
        if not w.closed and w.state["t"] < t2:
            w.add(
                w.full(
                    t=t2,
                    dt=0,
                    actor="system",
                    type="action",
                    place=w.player_place,
                    summary="時が過ぎた",
                    effects=[],
                    check=PASSED,
                )
            )
        return Planned(minutes=w.state["t"] - t0)

    def _talk_plan(
        self,
        task: Task,
        checked: list[Checked],
        asks: list[Json | None],
        answer: tuple[str, str] | None,
        said: str | None,
    ) -> Callable[[Writer, Book], Planned]:
        def plan(w: Writer, book: Book) -> Planned:
            p = self._talk_events(w, book, task, checked, asks, said)
            p.answer = answer
            return p

        return plan

    def _talk_events(
        self,
        w: Writer,
        book: Book,
        task: Task,
        checked: list[Checked],
        asks: list[Json | None] | None = None,
        said: str | None = None,
    ) -> Planned:
        w.settle(w.state["t"])
        t0 = w.state["t"]
        place = w.player_place
        proposals: list[confirm.Proposal] = []
        for i, c in enumerate(checked):
            cand = c.candidate
            ask = asks[i] if asks is not None and i < len(asks) else None
            # Needs confirmation: not written to the log; stored as a draft at commit (B-4).
            # 確認が要る：ログには書かず、コミット時に下書きとして保存する（B-4）。
            if confirm.proposes(c, ask):
                assert ask is not None
                question = confirm.question_of(ask, said)
                proposals.append(confirm.Proposal(c, bool(ask.get("asked")), question, cand.get("place", place)))
                continue
            extra = {k: cand[k] for k in ("beneficiary", "confirmed") if k in cand}
            ev = w.add(
                w.full(
                    t=t0,
                    dt=0,
                    actor=cand.get("actor", "player"),
                    type=cand.get("type", "say"),
                    origin=cand.get("origin", "turn"),
                    place=cand.get("place", place),
                    summary=cand["summary"],
                    effects=c.effects if c.passed else [],
                    causes=cand.get("causes", []),
                    check=c.check,
                    turn_id=task.turn_id,
                    **extra,
                )
            )
            c.candidate = {**cand, "eventId": ev["eventId"]}
        minutes = talk_minutes(book, w.state)
        role = book.roles[w.state["role"]]["name"]
        who = book.characters.get(task.character or "", {}).get("name", "誰か")
        w.add(
            w.full(
                t=t0,
                dt=minutes,
                actor="player",
                type="say",
                origin="turn",
                place=place,
                summary=f"{role}が{who}と話した",
                effects=[],
                check=PASSED,
                turn_id=task.turn_id,
            )
        )
        w.settle(w.state["t"])
        visible = [e for e in w.events if e.get("turnId") == task.turn_id and is_visible(book, e, place)]
        outcome = "committed" if visible else "rejected" if any(not c.passed for c in checked) else "no_change"
        seen = set(w.seen)
        settled = {
            "type": "turn_settled",
            "turnId": task.turn_id,
            "outcome": outcome,
            "eventIds": [e["eventId"] for e in w.events if e.get("turnId") == task.turn_id and e["eventId"] in seen],
            "minutes": minutes,
        }
        return Planned(outcome=outcome, minutes=minutes, checked=checked, push=[settled], proposals=proposals)

    def _ended_talk(self, task: Task) -> Planned:
        settled = {
            "type": "turn_settled",
            "turnId": task.turn_id,
            "outcome": "no_response",
            "eventIds": [],
            "minutes": 0,
        }
        return Planned(outcome="no_response", push=[settled])

    # —— Single-transaction commit / 単一トランザクションのコミット ——

    async def _commit(
        self,
        task: Task,
        read_seq: int | None,
        plan: Callable[[Writer, Book], Planned],
        *,
        spend: Spend | None = None,
        counts: Counts | None = None,
    ) -> Result:
        async with self.engine.begin() as c:
            self.fault("lock")
            pt = (
                (
                    await c.execute(
                        select(playthroughs).where(playthroughs.c.playthrough_id == task.pid).with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            if pt is None:
                raise Gone(task.pid)
            if read_seq is not None and pt["last_seq"] != read_seq:
                raise Stale(task.turn_id)
            status = await c.scalar(select(turns.c.status).where(turns.c.turn_id == task.turn_id).with_for_update())
            if status != "leased":
                raise Gone(task.turn_id)
            book = self.library.version(pt["world_model_version"])
            row = (
                await c.execute(
                    select(world_state.c.state, world_state.c.as_of_seq).where(world_state.c.playthrough_id == task.pid)
                )
            ).first()
            state: SimState = cast(SimState, row[0]) if row else initial_state(book.world, pt["role_id"])
            if state["seq"] != pt["last_seq"]:
                raise RuntimeError(
                    f"{task.pid}: world_state seq {state['seq']} doesn't match lastSeq {pt['last_seq']}"
                    f" / {task.pid}：world_state の seq {state['seq']} と lastSeq {pt['last_seq']} が一致しない"
                )

            self.fault("apply")
            w = Writer(
                book,
                task.pid,
                state,
                key_base=task.key,
                turn_id=task.turn_id if task.kind in TURN_KINDS else None,
                ids=self.ids,
                now=recorded_at(),
            )
            w.run = Run.of(dict(pt))
            planned = plan(w, book)
            # An answered draft is deleted when closed (B-4) / 返答済みの下書きは閉じたら削除する（B-4）
            if planned.close_draft is not None:
                await c.execute(delete(drafts).where(drafts.c.draft_id == planned.close_draft))
            trigger = ending.due(book, w.state) if pt["status"] == "active" else None
            # Entering the ending (B-9): settle to the close, classify, and place people.
            # エンディングに入る（B-9）：幕を閉じるところまで精算し、分類し、立ち位置を決める。
            if trigger is not None:
                w.ending = ending.enter(w, book, trigger)
            closing, asking = await confirm.in_commit(self, c, task, w, planned)
            push = list(w.pieces) + list(planned.push)
            # What the gateway pushes before this commit's commit message (B-9: ending_started).
            # ゲートウェイがこのコミットの commit より前にプッシュするもの（B-9：ending_started）。
            before: list[Json] = []
            if w.ending is not None:
                push.extend(closing)
                if w.events:
                    before.append(w.ending["message"])
                else:
                    push.insert(0, w.ending["message"])
                await store.enqueue(c, self.ids, task.pid, kind=ending.KIND, request=w.ending["request"])
            # The act closed in this commit: record the end-of-act destinations on the run and push act_ended
            # (api-contract 3.11).
            # この幕がこのコミットで閉じた：幕末の行き先をゲームに記録し、
            # act_ended をプッシュする（api-contract 3.11）。
            if w.closed:
                start = await c.scalar(
                    select(func.max(events_t.c.seq)).where(
                        events_t.c.playthrough_id == task.pid,
                        events_t.c.type == "act-transition",
                        events_t.c.actor == "system",
                    )
                )
                earlier = await store.event_log(c, task.pid, book.version, after_seq=int(start or 0))
                w.run.act_end = acts.act_end(book, w.state, 0, [*earlier, *w.events])
                w.run.plan_tries = 0
                w.run.plan_alternative = None
                # The open draft is closed as a timeout, before act_ended (B-4).
                # 開いている下書きはタイムアウトとして閉じ、act_ended の前に置く（B-4）。
                push.extend(closing)
                push.append({"type": "act_ended", **w.run.act_end})
            if planned.snapshot:
                for m in push:
                    if m["type"] == "act_transition":
                        m["snapshot"] = snapshot(
                            book, task.pid, pt["role_id"], pt["status"], w.state, w.state["seq"], w.run
                        )
            pieces = [m["pieceId"] for m in push if m["type"] == "set_piece"]
            # B-13: memories to write (the model writes the text after the transaction).
            # B-13：書く記憶（文章はトランザクションのあとモデルが書く）。
            todo = memory.seeds(book, state, w.events, task.character)
            role_id = str(pt["role_id"])
            result = Result(
                task,
                w.events,
                w.state,
                planned.outcome,
                planned.minutes,
                planned.checked,
                # Evals and tests see the same order the gateway pushes in (ending_started → what follows commit).
                # 評価とテストが見る順はゲートウェイがプッシュする順と同じ（ending_started → commit のあとのもの）。
                [*before, *push],
                planned.info,
                pieces,
            )

            self.fault("validate")
            for ev in w.events:
                # Not matching the data contract raises SchemaError and rolls back the whole turn.
                # データ契約に合わなければ SchemaError を投げ、ターン全体をロールバックする。
                self.schemas.event(ev)

            self.fault("events")
            if w.events:
                await c.execute(insert(events_t), [to_row(e) for e in w.events])
            await self._schedule_world(c, task, dict(pt), w)
            self.fault("world_state")
            if row is None:
                await c.execute(
                    insert(world_state).values(playthrough_id=task.pid, as_of_seq=w.state["seq"], state=w.state)
                )
            else:
                await c.execute(
                    update(world_state)
                    .where(world_state.c.playthrough_id == task.pid)
                    .values(as_of_seq=w.state["seq"], state=w.state)
                )
            self.fault("playthrough")
            ended: dict[str, Any] = {"status": "ended", "ended_at": func.now()} if w.ending is not None else {}
            await c.execute(
                update(playthroughs)
                .where(playthroughs.c.playthrough_id == task.pid)
                .values(last_seq=w.state["seq"], last_active_at=func.now(), **w.run.values(), **ended)
            )
            self.fault("turn")
            stored = {"push": push, "pieces": pieces, "seq": w.state["seq"], **planned.extra}
            if before:
                stored["before"] = before
            # After pushing this turn's result, the gateway has the character ask back and pushes confirm (B-4).
            # このターンの結果をプッシュしたあと、ゲートウェイが登場人物に聞き返させ confirm をプッシュする（B-4）。
            if asking is not None:
                stored["confirm"] = asking
            await c.execute(
                update(turns)
                .where(turns.c.turn_id == task.turn_id)
                .values(
                    status="done",
                    outcome=result.outcome,
                    minutes=result.minutes,
                    lease_until=None,
                    settled_at=func.now(),
                    result=stored,
                    # B-12: screening flags are only for the narrator; cleared in the same commit transaction
                    # (S-057, S-069 ③).
                    # B-12：スクリーニングの印はナレーターに渡すためだけのもので、同じコミットのトランザクションで
                    # 消す（S-057、S-069 ③）。
                    flags=None,
                )
            )
            self.fault("metrics")
            counts = (counts or Counts()) + Counts(confirm_dropped=planned.dropped)
            values = metrics(task, spend or Spend(), counts, planned)
            if w.ending is not None:
                values["ending_started_at"] = func.now()
            await c.execute(
                update(playthrough_metrics).where(playthrough_metrics.c.playthrough_id == task.pid).values(values)
            )
            # When memories are to be written, NOTIFY comes after writing them (`_remember`); the fault-injection
            # point stays in the commit transaction.
            # 記憶を書くときは NOTIFY を書き終えたあとに行う（`_remember`）。障害注入の位置は従来どおりコミットの
            # トランザクションの中。
            self.fault("notify")
            if not todo:
                await self._notify(c, task, seq=w.state["seq"], outcome=result.outcome)
            self.fault("commit")
        log.info(
            "Committed %s %s: seq %d-%d, %d events / コミット",
            task.kind,
            task.turn_id,
            state["seq"] + 1,
            w.state["seq"],
            len(w.events),
        )
        if todo:
            result.memories = await self._remember(task, book, role_id, todo, result)
        return result

    async def _schedule_world(self, c: AsyncConnection, task: Task, pt: Mapping[str, Any], w: Writer) -> None:
        """B-16: queue world advancement after dialogue, action and confirmation commits (after this commit's events
        are written, in the same transaction): an event with keyMoment → `key`; the act's judged dialogue turns reach a
        multiple of 8 → `mid`. Nothing is queued if the act has closed, the ending has started, or the game isn't
        active.

        B-16：対話、アクション、確認のコミットのあとに世界の進行を積む（今回のイベントを書き込んだあと、同じ
        トランザクションの中で）：keyMoment のイベントがある → `key`。この幕で判定済みの対話ターンが 8 の倍数に達した →
        `mid`。幕が閉じた、エンディングに入った、ゲームが進行中でないときは積まない。
        """
        if not self.world_advance or task.kind not in ("talk", "action", "confirm"):
            return
        if pt["status"] != "active" or w.ending is not None or w.closed or w.run.act_end is not None:
            return
        reason = None
        if any(e.get("keyMoment") and e["check"]["status"] != "rejected" for e in w.events):
            reason = "key"
        elif task.kind == "talk":
            start = await c.scalar(
                select(func.max(events_t.c.seq)).where(
                    events_t.c.playthrough_id == task.pid,
                    events_t.c.type == "act-transition",
                    events_t.c.actor == "system",
                )
            )
            talks = await c.scalar(
                select(func.count(func.distinct(events_t.c.turn_id)))
                .select_from(events_t.join(turns, turns.c.turn_id == events_t.c.turn_id))
                .where(events_t.c.playthrough_id == task.pid, events_t.c.seq > int(start or 0), turns.c.kind == "talk")
            )
            if talks and int(talks) % advance.MID_EVERY == 0:
                reason = "mid"
        if reason is not None:
            await store.enqueue(c, self.ids, task.pid, kind=advance.KIND, request={"reason": reason})

    async def _remember(
        self, task: Task, book: Book, role_id: str, todo: list[memory.Seed], result: Result
    ) -> list[Json]:
        """B-13: write memories after commit, store them, then NOTIFY. Whatever goes wrong, NOTIFY anyway (the turn's
        result is still pushed); `Stop` is raised after the push.

        B-13：コミットのあとで記憶を書き、保存してから NOTIFY する。何が起きても NOTIFY はし（このターンの結果は
        そのままプッシュする）、`Stop` はプッシュのあとで上に投げる。
        """
        rows: list[Json] = []
        stop: Stop | None = None
        try:
            got = await self.memorizer.write(
                book, task.pid, role_id, todo, playthrough_id=task.pid, turn_id=task.turn_id
            )
            async with self.engine.begin() as c:
                rows = await self._store_memories(c, task, book, role_id, got)
                await self._notify(c, task, seq=result.state["seq"], outcome=result.outcome)
            return rows
        except Stop as e:
            stop = e
        except Exception:
            log.exception(
                "Writing memories failed (%s); pushing the turn as usual"
                " / 記憶の書き込みに失敗、ターンは通常どおりプッシュする",
                task.turn_id,
            )
        async with self.engine.begin() as c:
            await self._notify(c, task, seq=result.state["seq"], outcome=result.outcome)
        if stop is not None:
            raise stop
        return []

    async def _store_memories(
        self, c: AsyncConnection, task: Task, book: Book, role_id: str, got: memory.Written
    ) -> list[Json]:
        """Store the memories and record counts and cost; this commit's memory changes (without text) go into
        turns.result.memories, and the gateway fetches the text when building the commit. If the game was deleted
        meanwhile, not a single row is written (foreign key); only this turn's counts have nowhere to go.

        記憶を保存し、件数と費用を記録する。今回の記憶の変化（文章なし）は turns.result.memories に書き、ゲートウェイが
        commit を組み立てるときに文章を取る。その間にゲームが削除されていたら 1 行も書かず（外部キー）、
        このターンの件数を記録する先がないだけ。
        """
        exists = await c.scalar(
            select(playthroughs.c.playthrough_id).where(playthroughs.c.playthrough_id == task.pid).with_for_update()
        )
        if exists is None:
            return []
        stored_rows = await memory.save(c, book, task.pid, got.rows)
        changes = []
        for who in dict.fromkeys(r["character"] for r, _ in stored_rows):
            label, level = await memory.relation_of(c, book, task.pid, role_id, who)
            changes += [
                {
                    "character": who,
                    "change": change,
                    "memoryId": r["memory_id"],
                    "kind": r["kind"],
                    "relationLabel": label,
                    "relationLevel": level,
                }
                for r, change in stored_rows
                if r["character"] == who
            ]
        if changes:
            stored = await c.scalar(select(turns.c.result).where(turns.c.turn_id == task.turn_id))
            await c.execute(
                update(turns)
                .where(turns.c.turn_id == task.turn_id)
                .values(result={**(stored or {}), "memories": changes})
            )
        m = playthrough_metrics.c
        values: dict[str, Any] = {
            "cost_memory_usd": m.cost_memory_usd + got.cost_usd,
            "memories_written": m.memories_written + len(got.rows),
            "memories_filtered": m.memories_filtered + got.filtered,
            "memories_failed": m.memories_failed + got.failed,
            "armor_errors": m.armor_errors + got.armor_errors,
            "cost_armor_usd": m.cost_armor_usd + got.armor_usd,
        }
        await c.execute(update(playthrough_metrics).where(m.playthrough_id == task.pid).values(values))
        return got.rows

    async def _notify(self, c: AsyncConnection, task: Task, *, seq: int, outcome: str | None) -> None:
        payload = {"pid": task.pid, "seq": seq, "kind": task.kind, "turnId": task.turn_id, "outcome": outcome}
        await c.execute(select(func.pg_notify(CHANNEL, json.dumps(payload))))


# What one turn writes into playthrough_metrics: turn count, cost per prompt kind (data-design section 3: cost per game
# = the sum of all cost_*_usd), and counts.
# 1 ターンで playthrough_metrics に書くもの：ターン数、プロンプトの種類ごとの費用（data-design 第 3 節：
# ゲームごとの費用 = すべての cost_*_usd の合計）、件数。
COST_COLUMNS = {
    "triage": "cost_triage_usd",
    "extract": "cost_extract_usd",
    "check": "cost_check_usd",
    "rewrite": "cost_rewrite_usd",
    "reply": "cost_reply_usd",
    "narrate": "cost_narrate_usd",
    "plan": "cost_plan_usd",
    "ending": "cost_ending_usd",
    # B-17: the ending model check counts in the ending column / エンディングのモデルの検査はエンディングの列に入れる
    "ending-check": "cost_ending_usd",
    "world": "cost_world_usd",  # B-16
}
COUNT_COLUMNS = {
    "triage_skipped": "turns_triage_skipped",
    "timeouts": "turns_timed_out",
    "rewritten": "candidates_rewritten",
    "downgraded": "candidates_downgraded",
    "rejected": "candidates_rejected",
    "confirm_dropped": "candidates_confirm_dropped",
}


# B-3: action counts (those refused from the queue at the close of an act counted separately), plans accepted and
# refused; B-4: intent confirmation.
# B-3：アクションの回数（幕を閉じたときキューで refused を返したものは別に数える）、
# プランが実行された・されなかった回数。
# B-4：意図の確認。
PLANNED_COLUMNS = {
    "actions": "actions",
    "actions_ended": "actions_act_ended",
    "plans_accepted": "plans_accepted",
    "plans_refused": "plans_refused",
    "confirms_asked": "confirms_asked",
    "confirms_yes": "confirms_yes",
    "confirms_no": "confirms_no",
    "confirms_timeout": "confirms_timeout",
    "confirms_rejected": "confirms_rejected",
    "world_events": "world_events",  # B-16
    "director_events": "director_events",
}


def cost_values(spend: Spend) -> dict[str, Any]:
    """Add each prompt kind's cost to the game's existing totals (data-design section 3: cost per game = the sum of all
    cost_*_usd).

    プロンプトの種類ごとの費用をこのゲームの既存の数に足す（data-design 第 3 節：ゲームごとの費用 = すべての cost_*_usd
    の合計）。
    """
    m = playthrough_metrics.c
    by_col: dict[str, float] = {}
    for kind, usd in spend.usd.items():
        by_col[COST_COLUMNS[kind]] = by_col.get(COST_COLUMNS[kind], 0.0) + usd
    return {col: m[col] + usd for col, usd in by_col.items()}


def metrics(task: Task, spend: Spend, counts: Counts, planned: Planned | None = None) -> dict[str, Any]:
    m = playthrough_metrics.c
    out: dict[str, Any] = {"turns": m.turns + (1 if task.kind == "talk" else 0)}
    for k, col in PLANNED_COLUMNS.items():
        n = getattr(planned, k) if planned is not None else 0
        if n:
            out[col] = m[col] + n
    out |= cost_values(spend)
    for k, col in COUNT_COLUMNS.items():
        n = getattr(counts, k)
        if n:
            out[col] = m[col] + n
    return out
