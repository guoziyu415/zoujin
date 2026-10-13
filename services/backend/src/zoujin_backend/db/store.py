"""Reads and writes shared by the gateway, the narrator and the eval entry point: starting a playthrough, queueing a
turn, reading events and state.

The caller opens the transaction (`async with engine.begin() as c`); this module only executes on the given connection.

ゲートウェイ、ナレーター、評価の入口が共有する読み書き：プレイの開始、ターンのキュー投入、イベントと状態の読み出し。

トランザクションは呼び出し側が開く（`async with engine.begin() as c`）。ここでは渡された接続の上で実行するだけ。
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, cast

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection
from zoujin_worldsim import SimState, apply, initial_state

from zoujin_backend.db.events import from_row
from zoujin_backend.db.tables import drafts, events, playthrough_metrics, playthroughs, turns, utterances, world_state
from zoujin_backend.ids import IdGen
from zoujin_backend.narrator import roles
from zoujin_backend.world import Book

Json = Any


async def create_playthrough(c: AsyncConnection, ids: IdGen, *, user_id: str, book: Book, role_id: str) -> str:
    """Start a playthrough: the playthrough row, the metrics row and one open task (the narrator writes the opening
    events). Returns the playthroughId.

    プレイの開始：プレイの行、指標の行、open タスク 1 件（ナレーターが開始イベントを書く）。playthroughId を返す。
    """
    pid = ids.new("pt")
    await c.execute(
        insert(playthroughs).values(
            playthrough_id=pid,
            user_ref=user_id,
            book_id=book.book_id,
            world_model_version=book.version,
            role_id=role_id,
            status="active",
            # B-19: who speaks first at the start (same logic as landing after an act change)
            # B-19：開始時に先に口を開く人（幕の切り替え後の着地と同じ仕組み）
            arrival=roles.start_arrival(book, role_id),
        )
    )
    await c.execute(insert(playthrough_metrics).values(playthrough_id=pid))
    await enqueue(c, ids, pid, kind="open")
    return pid


async def enqueue(
    c: AsyncConnection,
    ids: IdGen,
    pid: str,
    *,
    kind: str,
    turn_id: str | None = None,
    input_mode: str | None = None,
    character: str | None = None,
    turn_seq: int | None = None,
    minutes: int | None = None,
    status: str = "pending",
    client_msg_id: str | None = None,
    request: Json | None = None,
    commit_after: float | None = None,
    created_at: Any = None,
    flags: Iterable[str] | None = None,
) -> str:
    """Queue one narrator task. The idempotency key is the turnId: retries use the same one, and the keys of the events
    written by this turn all start with it.
    created_at uses clock_timestamp(), so several tasks queued in the same transaction still have an order.
    status="lost": a turn where the character had not finished speaking when the connection dropped; only kept as a
    record (welcome's lastTurn), the narrator does not process it.
    request: the action and end-of-act request (B-3), without the original words (those are in utterances).
    commit_after: the earliest number of seconds after which the narrator commits (B-4's retract window, by the DB
    clock); None = commit as soon as judged.
    created_at: the time it is queued (a timeout task for an expired draft is queued at the moment it expired, B-4).
    flags: the step-0 safety screening flags (B-12); the narrator judges by them.

    ナレーターのタスクを 1 件キューに入れる。冪等キーは turnId そのもの：再試行では同じものを使い、
    このターンが書くイベントのキーはすべてそれで始まる。created_at には clock_timestamp() を使うので、
    同じトランザクションで入れた複数件でも前後が区別できる。status="lost"：
    接続が切れたとき登場人物がまだ話し終えていなかったターン。記録だけ残し（welcome の lastTurn）、
    ナレーターは処理しない。request：アクションと幕末のリクエスト（B-3）。
    発話の原文は入れない（原文は utterances にある）。commit_after：
    ナレーターが最短で何秒後にコミットするか（B-4 の取り消し可能な時間、DB の時計で数える）。
    None = 判定が終わったらすぐコミット。created_at：キューに入れた時刻（草稿が期限切れになったときの
    タイムアウトタスクは期限の時刻に入れる、B-4）。flags：第 0 段階の安全スクリーニングのフラグ（B-12）。
    ナレーターはそれに従って判定する。
    """
    turn_id = turn_id or ids.new("turn")
    await c.execute(
        insert(turns).values(
            turn_id=turn_id,
            playthrough_id=pid,
            kind=kind,
            input_mode=input_mode,
            character=character,
            turn_seq=turn_seq,
            minutes=minutes,
            status=status,
            idempotency_key=turn_id,
            client_msg_id=client_msg_id,
            request=request,
            created_at=func.clock_timestamp() if created_at is None else created_at,
            commit_after=None if commit_after is None else func.clock_timestamp() + timedelta(seconds=commit_after),
            flags=sorted(flags) if flags else None,
        )
    )
    return turn_id


# —— Retract (B-4, api-contract 3.6) / 取り消し（B-4、api-contract 3.6）——

RETRACTABLE = ("talk", "plan")


async def retract_queued(c: AsyncConnection, pid: str, turn_id: str) -> str | None:
    """Mark a turn already handed to the narrator but not yet committed (pending / leased) as retracted: clear the
    original words, set deleted_at (the row stays) and add 1 to turns_retracted. Whichever of this and the narrator's
    commit gets the turn's row lock first wins (the narrator only accepts leased). Returns the turn's kind; returns
    None (too_late) if it is already committed, unknown or cannot be retracted.

    ナレーターに渡したがまだコミットしていないターン（pending / leased）を retracted にし、
    発話の原文を消して deleted_at を記録し（行は残す）、turns_retracted に 1 を足す。ナレーターのコミットと、
    このターンの行ロックを先に取った方が有効（ナレーターは leased だけを受け付ける）。このターンの kind を返す。
    すでにコミット済み、不明、取り消せないものは None（too_late）を返す。
    """
    row = (
        await c.execute(
            update(turns)
            .where(
                turns.c.turn_id == turn_id,
                turns.c.playthrough_id == pid,
                turns.c.kind.in_(RETRACTABLE),
                turns.c.status.in_(("pending", "leased")),
            )
            .values(
                status="retracted", outcome="retracted", minutes=0, lease_until=None, settled_at=func.now(), flags=None
            )
            .returning(turns.c.kind)
        )
    ).first()
    if row is None:
        return None
    await c.execute(update(utterances).where(utterances.c.turn_id == turn_id).values(text=None, deleted_at=func.now()))
    await count_retracted(c, pid)
    return str(row.kind)


async def count_retracted(c: AsyncConnection, pid: str) -> None:
    m = playthrough_metrics.c
    await c.execute(
        update(playthrough_metrics).where(m.playthrough_id == pid).values(turns_retracted=m.turns_retracted + 1)
    )


# —— Intent-confirmation drafts (B-4, api-contract 3.9) / 意図確認の草稿（B-4、api-contract 3.9）——


async def count(c: AsyncConnection, pid: str, **by: float) -> None:
    """Add to the counts and spend in playthrough_metrics (B-12's safety and output side; nothing is added if the row
    does not exist, i.e. the playthrough has been deleted).

    playthrough_metrics の件数と費用に加算する（B-12 の安全と出力側。行がなければ加算しない＝プレイは削除済み）。
    """
    if not by:
        return
    await c.execute(
        update(playthrough_metrics)
        .where(playthrough_metrics.c.playthrough_id == pid)
        .values({k: getattr(playthrough_metrics.c, k) + v for k, v in by.items()})
    )


async def safety_state(c: AsyncConnection, pid: str, *, lock: bool = False) -> dict[str, Any]:
    """This playthrough's safety screening state (B-12): {paused, hinted, ambiguous}.

    このプレイの安全スクリーニングの状態（B-12）：{paused, hinted, ambiguous}。
    """
    q = select(playthroughs.c.safety).where(playthroughs.c.playthrough_id == pid)
    if lock:
        q = q.with_for_update()
    got = await c.scalar(q)
    return dict(got or {})


async def set_safety(c: AsyncConnection, pid: str, state: Mapping[str, Any]) -> None:
    await c.execute(update(playthroughs).where(playthroughs.c.playthrough_id == pid).values(safety=dict(state)))


async def open_draft(c: AsyncConnection, pid: str, *, lock: bool = False) -> dict[str, Any] | None:
    """This playthrough's open draft (at most one). lock: lock the row (when writing the answer task or closing the
    draft).

    このプレイで開いている草稿（多くても 1 つ）。lock：その行をロックする（回答のタスクを書くとき、草稿を閉じるとき）。
    """
    q = select(drafts).where(drafts.c.playthrough_id == pid).order_by(drafts.c.created_at).limit(1)
    if lock:
        q = q.with_for_update()
    row = (await c.execute(q)).mappings().first()
    return dict(row) if row is not None else None


async def answered(c: AsyncConnection, pid: str, draft_id: str) -> bool:
    """This draft already has an answer task row (button, voice or timeout; whichever is written first counts). Failed
    ones do not count: the draft is still open and the timeout can still close it.

    この草稿にはすでに回答のタスクの行がある（ボタン、音声、タイムアウトのうち先に書いた方が有効）。
    失敗したものは数えない：草稿はまだ開いていて、タイムアウトで閉じることができる。
    """
    found = await c.scalar(
        select(turns.c.turn_id).where(
            turns.c.playthrough_id == pid,
            turns.c.kind == "confirm",
            turns.c.request["draftId"].astext == draft_id,
            turns.c.status != "failed",
        )
    )
    return found is not None


async def answer_draft(
    c: AsyncConnection, ids: IdGen, pid: str, draft_id: str, option_id: str | None, by: str, *, at: Any = None
) -> str | None:
    """Write a `kind: "confirm"` task for the open draft (the narrator processes them queued per playthrough). If the
    draft is gone or already answered, write nothing and return None. The check runs after locking the draft row, so
    when a button, voice and timeout arrive at the same time only one row is written.

    開いている草稿に `kind: "confirm"` のタスクを 1 行書く（ナレーターはプレイごとにキューで処理する）。草稿がもうない、
    またはすでに回答があれば何も書かず None を返す。草稿の行をロックしてから確認するので、ボタン・音声・
    タイムアウトが同時に来ても 1 行しか書かない。
    """
    row = await c.scalar(
        select(drafts.c.draft_id).where(drafts.c.draft_id == draft_id, drafts.c.playthrough_id == pid).with_for_update()
    )
    if row is None or await answered(c, pid, draft_id):
        return None
    return await enqueue(
        c, ids, pid, kind="confirm", request={"draftId": draft_id, "optionId": option_id, "by": by}, created_at=at
    )


async def expire_drafts(c: AsyncConnection, ids: IdGen, pid: str) -> list[str]:
    """Write timeout tasks for expired, unanswered drafts, queued at the moment they expired (answers that came before
    count first). Returns the IDs of the drafts written.

    期限切れでまだ回答のない草稿にタイムアウトのタスクを書き、期限の時刻に入れる（それより前に来た回答が優先）。
    書いた草稿の ID を返す。
    """
    rows = (
        await c.execute(
            select(drafts.c.draft_id, drafts.c.expires_at)
            .where(drafts.c.playthrough_id == pid, drafts.c.expires_at <= func.now())
            .with_for_update()
        )
    ).all()
    out = []
    for draft_id, at in rows:
        if await answer_draft(c, ids, pid, draft_id, None, "timeout", at=at) is not None:
            out.append(draft_id)
    return out


@dataclass
class Run:
    """The bits of a playthrough that are not events and do not go into WorldState (B-3, migration 0003): the narrator
    reads, changes and writes them back in the commit transaction; the gateway only reads them.

    プレイのうちイベントではなく WorldState にも入らないもの（B-3、マイグレーション 0003）：
    ナレーターがコミットのトランザクション内で読み、変更し、書き戻す。ゲートウェイは読むだけ。
    """

    player_spot: str | None = None
    played: list[str] = field(default_factory=list)
    act_end: Json | None = None
    plan_tries: int = 0
    plan_alternative: Json | None = None
    arrival: Json | None = None

    @classmethod
    def of(cls, row: Mapping[str, Any]) -> Run:
        return cls(
            player_spot=row.get("player_spot"),
            played=list(row.get("played_pieces") or []),
            act_end=row.get("act_end"),
            plan_tries=int(row.get("plan_tries") or 0),
            plan_alternative=row.get("plan_alternative"),
            arrival=row.get("arrival"),
        )

    def values(self) -> dict[str, Any]:
        return {
            "player_spot": self.player_spot,
            "played_pieces": list(self.played),
            "act_end": self.act_end,
            "plan_tries": self.plan_tries,
            "plan_alternative": self.plan_alternative,
            "arrival": self.arrival,
        }


PLAN_TEXT_CLEARED = "cleared"


async def clear_plan_texts(c: AsyncConnection, pid: str, turn_ids: list[str] | None = None) -> int:
    """Clear the retelling of end-of-act plans (label, narration, the alternative destination's label) from
    turns.result (B-3 item 4, data-design 5.2, 5.3): per-turn deletion from the 記憶帳 (L1) passes those turns, after
    the ending pass None (the whole playthrough). plan.label in events is untouched (events are not deleted and were
    filtered before writing). Returns how many turns were cleared.

    幕末のプランの言い換え（label、narration、代わりの行き先の label）を turns.result から消す（B-3 第 4 項、
    data-design 5.2・5.3）：記憶帳のターンごとの削除（L1）ではそのターンを渡し、
    エンディングの後は None（このプレイ全部）を渡す。イベント内の plan.label には触れない（イベントは削除せず、
    書き込む前にフィルター済み）。消したターン数を返す。
    """
    q = select(turns.c.turn_id, turns.c.result).where(turns.c.playthrough_id == pid, turns.c.kind == "plan")
    if turn_ids is not None:
        q = q.where(turns.c.turn_id.in_(turn_ids))
    n = 0
    for turn_id, result in (await c.execute(q)).all():
        if not result or result.get(PLAN_TEXT_CLEARED):
            continue
        kept = []
        for m in result.get("push", []):
            if m.get("type") == "act_plan_result":
                m = {k: v for k, v in m.items() if k != "narration"}
                if m.get("alternative"):
                    m["alternative"] = {k: v for k, v in m["alternative"].items() if k != "label"}
            kept.append(m)
        await c.execute(
            update(turns)
            .where(turns.c.turn_id == turn_id)
            .values(result={**result, "push": kept, PLAN_TEXT_CLEARED: True})
        )
        n += 1
    return n


async def add_utterance(
    c: AsyncConnection,
    ids: IdGen,
    pid: str,
    turn_id: str,
    *,
    speaker: str,
    text: str | None,
    t: int,
    source: str | None = None,
) -> str:
    utterance_id = ids.new("utt")
    await c.execute(
        insert(utterances).values(
            utterance_id=utterance_id,
            playthrough_id=pid,
            turn_id=turn_id,
            speaker=speaker,
            text=text,
            source=source,
            t=t,
            recorded_at=func.clock_timestamp(),
        )
    )
    return utterance_id


async def playthrough(c: AsyncConnection, pid: str) -> dict[str, Any] | None:
    row = (await c.execute(select(playthroughs).where(playthroughs.c.playthrough_id == pid))).mappings().first()
    return dict(row) if row is not None else None


async def sim_state(c: AsyncConnection, pid: str) -> SimState | None:
    """The SimState in the world_state cache (None while the opening task has not finished).

    world_state キャッシュの SimState（開始タスクがまだ終わっていなければ None）。
    """
    st = await c.scalar(select(world_state.c.state).where(world_state.c.playthrough_id == pid))
    return cast(SimState, st) if st is not None else None


async def event_log(
    c: AsyncConnection, pid: str, version: str, *, after_seq: int = 0, upto_seq: int | None = None
) -> list[Json]:
    """Full events in the event log after after_seq (up to upto_seq), in seq order.

    イベントログのうち after_seq より後（upto_seq まで）の完全なイベント。seq 順。
    """
    q = select(events).where(events.c.playthrough_id == pid, events.c.seq > after_seq)
    if upto_seq is not None:
        q = q.where(events.c.seq <= upto_seq)
    rows = (await c.execute(q.order_by(events.c.seq))).mappings().all()
    return [from_row(dict(r), version) for r in rows]


def replay(book: Book, role_id: str, log: list[Json], upto_seq: int | None = None) -> SimState:
    """Initial value + every event applied in seq order (data-design 4.4).

    初期値 + 全イベントを seq 順に適用（data-design 4.4）。
    """
    state = initial_state(book.world, role_id)
    for ev in log:
        if upto_seq is not None and ev["seq"] > upto_seq:
            break
        state = apply(book.world, state, ev)
    return state
