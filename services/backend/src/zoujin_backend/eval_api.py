"""Eval entry point (api-contract section 7, the minimal version of B-0 item 9): called in-process by data
engineering's runner, no HTTP, absent in production.

    from zoujin_backend import eval_api
    s = eval_api.setup({"role": "role.traveler", "checkpoint": "sc.canon@beat.03"}, mode="text")
    s.say("char.old-man", "…")
    s.state()

- `setup` reads `DATABASE_URL` and `ZJ_MODEL` each time (fake / replay / real; real only on the Mac, see
  `models/vertex.py` for the ledger and caps). A playthrough is a real one in the test DB: a new account, a
  playthrough, the starting events and world_state; later steps go through the same narrator as the gateway
  (`Narrator.run`).
- Done: setup's `role`, `place`, `budgetTier` (only recorded), `scenario`, `checkpoint`, `events`; steps `say` (the
  character answers in text, then the narrator's whole pipeline runs, B-2), `advance`; `act`, `propose`, `choose`
  (B-3: the same path as WebSocket, write a task and call the narrator); `check` (step 3 + step 4 per
  `model_checks`, no rewrite, no commit); queries `state()`, `events()`; B-9: `ending()` (None while the ending has not
  started); a setup whose scenario pushes to the close of the act enters the ending at the start, and the ending task
  runs to completion synchronously inside setup. When the checkpoint stops on this act's closing beat (e.g.
  `sc.canon@beat.07`), after setup the end-of-act choice is pending.
- B-4: `say(hold=True)` only writes this turn and gets the character's answer, returning `held: true` with no events
  (the retract window is still open); at the start of the next call (any step or query) the narrator commits it first,
  and its events count toward that call. `retract(n)` retracts step n while it is still held (`retracted`); once
  committed it is `too_late`; `utterance_cleared(n)`. When this step left an intent-confirmation draft,
  `StepResult.confirm` has a value; the draft waits at most one step: the next step `confirm(answer)` answers it, for
  `say` the narrator judges whether it is an answer, and any other step (or a `say` that is not an answer) closes it
  as a timeout. The eval's commit window is 0.
- B-5 simulated playthroughs: `setup({"role": …, "persona": …, "seed": …})` starts a playthrough the production way
  (the same path as the gateway's `POST /v1/playthroughs`: write the playthrough and the `open` task, and the
  narrator does it), without the `opening()` simulation; `persona` and `seed` are only recorded on the Trace
  (`eval.setup`), and `seed` goes to the fake model. The AI player sees only `view()` (2.3's snapshot and 2.4's
  player-visible events, the same projection as the gateway), `manifest()` (B-7's generator) and the fields of each
  step result the player can hear or see. Each step result carries `elapsedMs` (from entry to return). Ledger entries
  in this playthrough carry `playthroughId` (`zoujin_llm.playthrough`).
- Steps and queries not done, setup events with `memory`, and `move` in scenes without a layout raise
  `EvalNotImplemented("<name>")`;
  a replay not found raises `ReplayMissing`. The ledger reaching its cap raises `BudgetStop`, and a 429 from the model
  raises `RateLimited`: these two must stop the whole run, not skip this case. The runner recognises them by class
  name.
- A playthrough shares one event loop, and the DB uses connections outside the connection pool; when the runner's
  timeout (SIGALRM) interrupts midway, the abandoned playthrough simply stays in the test DB.

評価の入口（api-contract 第 7 節、B-0 第 9 項の最小版）：データエンジニアリングのランナーが Python パッケージ内で
呼ぶもので、HTTP は開かず、本番環境にはない。

- `setup` は毎回 `DATABASE_URL` と `ZJ_MODEL` を読む（fake / replay / real。real は Mac 上だけで、台帳と上限は
  `models/vertex.py` を参照）。1 プレイはテスト DB の本物のプレイ：新しいアカウント、プレイ、開始時点のイベントと
  world_state を作り、以後のステップはゲートウェイと同じナレーター（`Narrator.run`）を通る。
- 実装済み：setup の `role`、`place`、`budgetTier`（記録だけ）、`scenario`、`checkpoint`、`events`。ステップ `say`
  （登場人物がテキストで答え、ナレーターのパイプライン全体を通す、B-2）、`advance`。`act`、`propose`、`choose`
  （B-3：WebSocket と同じ経路で、タスクを書いてナレーターを呼ぶ）。`check`（第 3 段階 + `model_checks` に従って第 4 段階、
  書き換えもコミットもしない）。クエリ `state()`、`events()`。B-9：`ending()`（エンディングに入っていなければ None）。
  シナリオで幕を閉じるところまで進む setup では開始時点でエンディングに入り、エンディングのタスクは setup の中で
  同期的に最後まで実行する。チェックポイントがこの幕の閉幕のビート（例 `sc.canon@beat.07`）で止まっているときは、
  setup の後は幕末の選択待ちになる。
- B-4：`say(hold=True)` はこのターンを書いて登場人物の回答を得るだけで、`held: true` を返し、イベントはない（取り消し
  可能な時間はまだ開いている）。次の呼び出し（どのステップやクエリでも）の最初にナレーターがそれをコミットし、イベントは
  その呼び出しに数える。`retract(n)` はまだ hold 中の n ステップ目を取り消し（`retracted`）、コミット済みなら `too_late`。
  `utterance_cleared(n)`。このステップが意図確認の草稿を残したときは `StepResult.confirm` に値があり、草稿は最大 1
  ステップ待つ：次のステップの `confirm(answer)` がそれに答え、`say` なら回答かどうかをナレーターが判定し、ほかのステップ
  （または回答ではない `say`）ではタイムアウトとして閉じる。評価のコミット待ち時間は 0。
- B-5 のシミュレーションのプレイ：`setup({"role": …, "persona": …, "seed": …})` は本番どおりにプレイを開始し（ゲートウェイの
  `POST /v1/playthroughs` と同じ経路：プレイと `open` タスクを書き、ナレーターが処理する）、`opening()` のシミュレーションは
  使わない。`persona`、`seed` は Trace（`eval.setup`）に記録するだけで、`seed` は偽モデルに渡す。AI プレイヤーが見るのは
  `view()`（2.3 のスナップショットと 2.4 のプレイヤーに見えるイベント。ゲートウェイと同じ射影）、`manifest()`（B-7 の
  ジェネレーター）、各ステップの結果のうちプレイヤーが聞こえる・見えるフィールドだけ。各ステップの結果には `elapsedMs`
  （入ってから返るまで）が付く。このプレイで記録した台帳には `playthroughId`（`zoujin_llm.playthrough`）が付く。
- 未実装のステップとクエリ、`memory` 付きの配置イベント、レイアウトのないシーンでの `move` は
  `EvalNotImplemented("<name>")` を投げる。
  リプレイが見つからなければ `ReplayMissing`。台帳が上限に達したら `BudgetStop`、モデルが 429 を返したら
  `RateLimited`：この 2 つは実行全体を止めるもので、このケースをスキップするのではない。ランナーはクラス名で判別する。
- 1 プレイで 1 つのイベントループを共有し、DB はコネクションプールに入らない接続を使う。ランナーのタイムアウト
  （SIGALRM）で途中で中断されたとき、残されたプレイはテスト DB に残るだけ。
"""

from __future__ import annotations

import asyncio
import contextvars
import copy
import json
import time
from collections.abc import Callable, Coroutine, Iterable, Mapping, Sequence
from dataclasses import replace
from functools import cache, wraps
from pathlib import Path
from typing import Any, NoReturn

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool
from zoujin_llm import mark_playthrough, playthrough
from zoujin_llm.errors import check_batch_halt
from zoujin_worldsim import Opened, SimState, initial_state, opening, parse_checkpoint, world_state

from zoujin_backend import budget, memory_delete
from zoujin_backend.config import Settings
from zoujin_backend.db import store
from zoujin_backend.db.events import recorded_at, to_row
from zoujin_backend.db.store import Run
from zoujin_backend.db.tables import (
    NOT_BUILT,
    PER_PLAYTHROUGH,
    endings,
    memory_items,
    metadata,
    playthrough_metrics,
    playthroughs,
    users,
    utterances,
)
from zoujin_backend.db.tables import events as events_t
from zoujin_backend.db.tables import turns as turns_t
from zoujin_backend.db.tables import world_state as world_state_t
from zoujin_backend.eval_diagnostics import ObservedPipeline, ending_observations
from zoujin_backend.gateway.monitor import Monitor
from zoujin_backend.gateway.safety import context_of
from zoujin_backend.ids import IdGen
from zoujin_backend.manifest import Manifest, generate
from zoujin_backend.models.armor import Armor, armor
from zoujin_backend.models.text import BudgetStop, RateLimited, ReplayMissing, TextModel, text_model
from zoujin_backend.narrator import acts, ending, memory
from zoujin_backend.narrator.core import Narrator, Result
from zoujin_backend.narrator.pipeline import CallFailed, Pipeline, Spend, TurnInput
from zoujin_backend.narrator.writer import Writer, act_closed
from zoujin_backend.projection import snapshot, visible_events
from zoujin_backend.safety import SafetyState, Screen, Screener, counts_of, decide
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.trace import Tracer
from zoujin_backend.world import Book, Library

__all__ = ["BudgetStop", "CallFailed", "EvalNotImplemented", "RateLimited", "ReplayMissing", "Session", "setup"]

Json = Any

BOOK = "hashire-merosu"
CHECKER = "eval-setup"
SETUP_PASSED: Json = {"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER}


class EvalNotImplemented(Exception):
    """A step or query B-0 did not implement (the runner recognises it by class name and records "skipped: not
    implemented in the backend").

    B-0 で未実装のステップまたはクエリ（ランナーはクラス名で判別し、「スキップ：バックエンド未実装」と記録する）。
    """


@cache
def _library(worlds: Path, scenes: Path, current: Path) -> Library:
    return Library(worlds, scenes, current)


@cache
def _schemas(root: Path) -> SchemaBook:
    return SchemaBook(root)


@cache
def _scenarios(world_dir: Path) -> dict[str, Json]:
    """`sc.canon` = the original novel's path (not in scenarios.json).

    `sc.canon` = 原作どおりの経路（scenarios.json にはない）。
    """
    path = world_dir / "scenarios.json"
    listed = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    return {"sc.canon": {"id": "sc.canon"}, **{s["id"]: s for s in listed}}


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    """Standalone DB operations kept for tests; Session's model calls use the instance's persistent loop.

    テストとの互換のための単独の DB 操作。Session のモデル呼び出しはインスタンスが持ち続けるループを使う。
    """
    return asyncio.run(coro)


def _timed(step: Callable[..., Json]) -> Callable[..., Json]:
    """Add `elapsedMs` to each step result: from entering the call to returning, including the narrator's model calls
    and commit (B-5).

    各ステップの結果に `elapsedMs` を付ける：呼び出しに入ってから返るまでで、ナレーターの各モデル呼び出しとコミットを含む
    （B-5）。
    """

    @wraps(step)
    def timed(*args: Any, **kwargs: Any) -> Json:
        check_batch_halt()
        start = time.perf_counter()
        out = step(*args, **kwargs)
        out["elapsedMs"] = round((time.perf_counter() - start) * 1000)
        return out

    return timed


# A simulated playthrough with persona plays from the production start, so it is not given together with these
# persona 付きのシミュレーションのプレイは本番の開始から遊ぶので、これらと一緒には渡さない
NOT_WITH_PERSONA = ("checkpoint", "scenario", "events")


def setup(setup: Mapping[str, Json], *, mode: str = "text") -> Session:
    """Start a playthrough. setup is the case's setup as is; mode is text / voice (in B-0 both go through the text
    narrator flow).

    プレイを開始する。setup はケースの setup そのまま、mode は text / voice（B-0 ではどちらもテキストのナレーターの流れを通る）。
    """
    if "persona" in setup:
        mixed = [k for k in NOT_WITH_PERSONA if k in setup]
        if mixed:
            raise ValueError(
                f"persona is not given together with {', '.join(mixed)}: a simulated playthrough plays from the "
                f"production start / persona は {'、'.join(mixed)} と一緒には渡さない：シミュレーションのプレイは"
                "本番の開始から遊ぶ"
            )
    settings = Settings.from_env()
    library = _library(settings.worlds, settings.scenes, settings.world)  # ZJ_WORLD is read on every setup() / 毎回読む
    book = library.book(setup.get("book", BOOK))
    if book is None:
        raise ValueError(f"No such book / その本がない: {setup.get('book', BOOK)}")
    if setup["role"] not in book.roles:
        raise ValueError(f"No such role / その役がない: {setup['role']}")
    s = Session(settings, library, book, setup, mode)
    try:
        s._run(s._open() if s.persona is not None else s._setup())
    except BaseException:
        s.close()
        raise
    return s


class Session:
    def __init__(self, settings: Settings, library: Library, book: Book, setup: Mapping[str, Json], mode: str) -> None:
        self.settings = settings
        self.library = library
        self.book = book
        self.setup_doc = copy.deepcopy(dict(setup))
        self.mode = mode
        self.role: str = setup["role"]
        # B-14: set to this tier at the start (E6) / B-14：開始時にこの段階にする（E6）
        self.budget_tier: str = setup.get("budgetTier", "normal")
        # Persona ID of a simulated playthrough, only goes into the Trace (B-5)
        # シミュレーションのプレイのペルソナ ID。Trace にだけ入れる（B-5）
        self.persona: str | None = setup.get("persona")
        self.seed: int | None = setup.get("seed")
        self.ids = IdGen()
        self.text: TextModel = text_model(
            settings.model, fake_rules=settings.fake_text, replays=settings.replays, settings=settings, seed=self.seed
        )
        self.schemas = _schemas(settings.schemas)
        self.tracer = Tracer()
        # Attributes the runner adds to this step's Span (e.g. S-2's trace_id)
        # ランナーがこのステップの Span に付ける属性（例：S-2 の trace_id）
        self.span: dict[str, Any] = {}
        self.pid = ""
        self.user_id = ""
        # B-13: the playthrough deleted by delete_playthrough (db_absent checks it)
        # B-13：delete_playthrough で削除したプレイ（db_absent がこれを確認する）
        self.deleted: str | None = None
        self.steps = 0
        # Step number → that turn's turnId (say; used by retract, utterance_cleared)
        # ステップ番号 → そのターンの turnId（say。retract、utterance_cleared が使う）
        self.turns: dict[int, str] = {}
        # The step of say(hold=True) not yet committed / say(hold=True) でまだコミットしていないステップ
        self.held: tuple[int, str] | None = None
        # The still-open draft and the step that left it / 開いたままの草稿と、それを残したステップ
        self.draft: tuple[int, str] | None = None
        # B-12: safety screening of every player line and monitoring of character output, the same as the gateway
        # (Model Armor per ZJ_MODEL; a replay not found still raises)
        # B-12：プレイヤーの発言ごとの安全スクリーニングと登場人物の出力の監視。ゲートウェイと同じ仕組み
        # （Model Armor は ZJ_MODEL に従う。リプレイが見つからなければそのまま投げる）
        self.armor: Armor = armor(settings.model, replays=settings.replays)
        self.safety = SafetyState()
        # B-15: each character's previous line (context for safety screening)
        # B-15：登場人物ごとの直前のセリフ（安全スクリーニングの文脈）
        self.last_reply: dict[str, str] = {}
        self.monitor = Monitor(library)
        self.monitor.attach(book)
        self._manifest: Manifest | None = None
        # The real clients' connection pools are reused across steps; the whole playthrough must share one event loop.
        # 本物のクライアントのコネクションプールはステップをまたいで再利用する。プレイ全体で 1 つのイベントループを共有する。
        self._runner = asyncio.Runner()
        self.call_observations: list[dict[str, Any]] = []

    def _run[T](self, coro: Coroutine[Any, Any, T]) -> T:
        """A playthrough shares one event loop; ledger entries made meanwhile carry this playthrough's playthroughId.

        1 プレイで 1 つのイベントループを共有する。その間に記録した台帳にはこのプレイの playthroughId が付く。
        """
        with playthrough(self.pid or None):
            return self._runner.run(coro, context=contextvars.copy_context())

    def close(self) -> None:
        """The eval runner closes this playthrough's event loop after success, failure or a budget stop.

        評価のランナーは、成功・失敗・予算による停止のいずれの後もこのプレイのイベントループを閉じる。
        """
        self._runner.close()

    # —— Connections and narrator: created anew on each call (each with its own event loop) ——
    # —— 接続とナレーター：呼び出しごとに新しく作る（それぞれのイベントループ） ——

    def _engine(self) -> AsyncEngine:
        return create_async_engine(self.settings.database_url, poolclass=NullPool)

    def _narrator(self, engine: AsyncEngine) -> Narrator:
        narrator = Narrator(
            engine=engine,
            library=self.library,
            text=self.text,
            schemas=self.schemas,
            ids=self.ids,
            tracer=self.tracer,
            deadlines=self.settings.deadlines,
            armor=self.armor,
        )
        narrator.pipeline = self.pipeline
        return narrator

    @property
    def screener(self) -> Screener:
        """`text` may be swapped by tests, so build from the current one each time. In evals, the ledger cap and 429
        still stop the whole run.

        `text` はテストで差し替えられることがあるので、毎回その時点のもので作る。評価でも台帳の上限と 429 では実行全体を止める。
        """
        return Screener(self.text, self.armor, self.tracer, raise_stops=True)

    @property
    def pipeline(self) -> Pipeline:
        """`text` may be swapped by tests, so build from the current one each time.

        `text` はテストで差し替えられることがあるので、毎回その時点のもので作る。
        """
        return ObservedPipeline(
            self.text,
            self.schemas,
            self.ids,
            self.tracer,
            self.settings.deadlines,
            observations=self.call_observations,
        )

    # —— Starting point / 開始時点 ——

    async def _setup(self) -> None:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                user_id = await self._user(c)
                self.pid = self.ids.new("pt")
                await c.execute(
                    insert(playthroughs).values(
                        playthrough_id=self.pid,
                        user_ref=user_id,
                        book_id=self.book.book_id,
                        world_model_version=self.book.version,
                        role_id=self.role,
                        status="active",
                    )
                )
                await c.execute(insert(playthrough_metrics).values(playthrough_id=self.pid))
                if self.budget_tier != "normal":
                    await budget.set_tier(c, self.pid, self.budget_tier)
                w = Writer(
                    self.book,
                    self.pid,
                    initial_state(self.book.world, self.role),
                    key_base=f"{self.pid}/setup",
                    turn_id=None,
                    ids=self.ids,
                    now=recorded_at(),
                )
                play_setup(w, _scenarios(self._world_dir()), self.setup_doc)
                # Events laid out by the eval come last / 評価が配置したイベントは最後にある
                laid = w.events[len(w.events) - len(self.setup_doc.get("events", [])) :]
                # The scenario pushed straight to the close of the act (B-9 item 11): enter the ending at the start, as
                # when the narrator commits. Only whether the last act closed counts; a checkpoint stopped after
                # beat.24 but still in an earlier act does not enter (data review #124)
                # シナリオが一気に幕を閉じるところまで進んだ（B-9 第 11 項）：ナレーターのコミット時と同じく開始時点で
                # エンディングに入る。最後の幕が閉じたかだけを見て、beat.24 以降で止まっていてもまだ前の幕にいる
                # チェックポイントは入らない（データレビュー #124）
                trigger = ending.closed(self.book, w.state) if ending.curtain_fell(self.book, w.state) else None
                if trigger is not None:
                    w.ending = ending.enter(w, self.book, trigger)
                for ev in w.events:
                    self.schemas.event(ev)
                if w.events:
                    await c.execute(insert(events_t), [to_row(e) for e in w.events])
                await self._seed_memories(c, laid)
                await c.execute(
                    insert(world_state_t).values(playthrough_id=self.pid, as_of_seq=w.state["seq"], state=w.state)
                )
                await c.execute(
                    update(playthroughs)
                    .where(playthroughs.c.playthrough_id == self.pid)
                    .values(last_seq=w.state["seq"], act_end=setup_act_end(self.book, w, self.setup_doc))
                )
                if w.ending is not None:
                    await c.execute(
                        update(playthroughs)
                        .where(playthroughs.c.playthrough_id == self.pid)
                        .values(status="ended", ended_at=func.now())
                    )
                    await c.execute(
                        update(playthrough_metrics)
                        .where(playthrough_metrics.c.playthrough_id == self.pid)
                        .values(ending_started_at=func.now())
                    )
                    await store.enqueue(c, self.ids, self.pid, kind=ending.KIND, request=w.ending["request"])
            # The ending task runs to completion synchronously inside setup
            # エンディングのタスクは setup の中で同期的に最後まで実行する
            if w.ending is not None:
                await self._narrator(engine).run(self.pid)
        finally:
            await engine.dispose()

    async def _open(self) -> None:
        """Simulated playthrough (B-5): start the production way, the same path as the gateway's
        `POST /v1/playthroughs` (`store.create_playthrough` writes the playthrough, the metrics row and the `open` task,
        and the narrator does it: startT, startAct, the beats that are due).

        シミュレーションのプレイ（B-5）：本番どおりに開始し、ゲートウェイの `POST /v1/playthroughs` と同じ経路を通る
        （`store.create_playthrough` がプレイ、指標の行、`open` タスクを書き、ナレーターが処理する：startT、startAct、
        時刻が来たビート）。
        """
        engine = self._engine()
        try:
            async with engine.begin() as c:
                user_id = await self._user(c)
                self.pid = await store.create_playthrough(
                    c, self.ids, user_id=user_id, book=self.book, role_id=self.role
                )
                if self.budget_tier != "normal":
                    await budget.set_tier(c, self.pid, self.budget_tier)
            mark_playthrough(self.pid)
            attrs = {"eval.persona": self.persona, "eval.seed": self.seed}
            with self.tracer.span("eval.setup", playthrough_id=self.pid, mode=self.mode, **attrs):
                await self._narrator(engine).run(self.pid)
        finally:
            await engine.dispose()

    async def _user(self, c: Any) -> str:
        """This playthrough's account: created the first time; `new_playthrough` uses the same one (E6-008: the same
        account switches to a new playthrough).

        このプレイのアカウント：最初に作り、`new_playthrough` は同じものを使う（E6-008：同じアカウントで別のプレイにする）。
        """
        if not self.user_id:
            self.user_id = self.ids.new("usr")
            await c.execute(insert(users).values(user_id=self.user_id))
        return self.user_id

    async def _seed_memories(self, c: Any, laid: Sequence[Json]) -> None:
        """A setup event with `memory: {character, kind, text}`: seed a memory directly (no model call, through the same
        three filters).

        `memory: {character, kind, text}` 付きの setup のイベント：記憶を直接 1 件植える（モデルは呼ばず、同じ 3 段の
        フィルターを通す）。
        """
        todo = [
            (ev, d["memory"]) for ev, d in zip(laid, self.setup_doc.get("events", []), strict=True) if "memory" in d
        ]
        if not todo:
            return
        m = memory.Memorizer(self.text, self.armor, self.ids, self.tracer)
        rows = []
        for ev, spec in todo:
            text = str(spec["text"]).strip()
            if not (memory.rule_ok(text) and await m._armor_ok(text, memory.Written())):
                raise ValueError(
                    f"A memory seeded by setup fails the filters / setup で植えた記憶がフィルターを通らない: "
                    f"{spec['character']}"
                )
            rows.append(memory.seeded(self.ids, self.pid, ev, spec["character"], spec["kind"], text))
        await c.execute(insert(memory_items), rows)

    def _world_dir(self) -> Path:
        """The scenarios file `scenarios.json` is in the same directory as the world.json used for new playthroughs
        (setup only uses `Library.current`).

        シナリオの `scenarios.json` は開始に使う world.json と同じディレクトリにある（setup は `Library.current` だけを使う）。
        """
        return self.settings.world.parent

    # —— Steps / ステップ ——

    @_timed
    def say(self, to: str, text: str, hold: bool = False) -> Json:
        """Text instead of voice: the character answers in text (`reply`), the original words and this turn are
        written, and the narrator's whole pipeline runs. hold: do not commit yet (B-4).

        音声の代わりにテキスト：登場人物がテキストで答え（`reply`）、発話の原文とこのターンを書き込み、ナレーターの
        パイプライン全体を通す。hold：まだコミットしない（B-4）。
        """
        self.steps += 1
        return self._run(self._say(to, text, hold))

    # —— B-4: the held turn, the draft awaiting an answer / B-4：hold 中のターン、回答待ちの草稿 ——

    async def _prelude(self, engine: AsyncEngine, kind: str, retract: int | None = None) -> list[Result]:
        """At the start of each call: commit the held turn first (unless it is the one being retracted); a draft that
        has waited one step, when this step is neither confirm nor say, is closed as a timeout. Returns what the
        narrator committed meanwhile.

        各呼び出しの最初に：hold 中のターンを先にコミットする（retract の対象がそれならコミットしない）。草稿が 1 ステップ
        待ったうえで、このステップが confirm でも say でもなければタイムアウトとして閉じる。その間にナレーターがコミット
        したものを返す。
        """
        done: list[Result] = []
        if self.held is not None and self.held[0] != retract:
            self.held = None
            done += await self._narrator(engine).run(self.pid)
        if self.draft is not None and (self.steps > self.draft[0] + 1 or kind not in ("say", "confirm")):
            done += await self._close_draft(engine, None, "timeout")
        return done

    async def _close_draft(self, engine: AsyncEngine, option: str | None, by: str) -> list[Result]:
        assert self.draft is not None
        _, draft_id = self.draft
        self.draft = None
        async with engine.begin() as c:
            written = await store.answer_draft(c, self.ids, self.pid, draft_id, option, by)
        return await self._narrator(engine).run(self.pid) if written is not None else []

    async def _flush(self) -> None:
        """Before a query: commit the held turn first (the draft is untouched; a query does not count as a step).

        クエリの前に：hold 中のターンを先にコミットする（草稿には触れず、クエリは 1 ステップと数えない）。
        """
        if self.held is None:
            return
        engine = self._engine()
        try:
            self.held = None
            await self._narrator(engine).run(self.pid)
        finally:
            await engine.dispose()

    def _events_of(self, done: Sequence[Result]) -> list[Json]:
        return [e for r in done for e in self._step_events(r)]

    @staticmethod
    def _set_pieces(done: Sequence[Result]) -> list[Json]:
        """Only the set pieces the player actually received; future lines are never read from the manifest or the
        world model.

        プレイヤーが実際に受け取った固定演出だけを返す。manifest や世界モデルから先のセリフを読むことはしない。
        """
        return [copy.deepcopy(m) for r in done for m in r.push if m.get("type") == "set_piece"]

    async def _say(self, to: str, text: str, hold: bool = False) -> Json:
        engine = self._engine()
        try:
            pre = await self._prelude(engine, "say")
            async with engine.connect() as c:
                st = await store.sim_state(c, self.pid)
            assert st is not None
            spend = Spend()
            ctx = context_of(self.book, st["vars"]["var.player.location"], to, self.last_reply.get(to))
            screen = await self.screener.screen(text, ctx, **self.span)
            if self.safety.ambiguous >= 1:  # B-15: a second ambiguous is reviewed first / 2 回目の ambiguous は先に再確認
                screen = await self.screener.second_look(screen, text, ctx, **self.span)
            decision = decide(screen, self.safety)
            # Out-of-character card (3.12): no character answer, the turn does not go to the narrator, no time
            # passes, the original words are not stored
            # 物語の外に出るカード（3.12）：登場人物の回答は出さず、このターンはナレーターに渡さず、時間を進めず、
            # 発話の原文は保存しない
            if decision == "pause":
                return await self._paused(engine, to, pre, screen)
            if decision == "hint":
                self.monitor.calm()
            notes = self.monitor.notes(to)
            turn_in = TurnInput(character=to, player=text)
            reply = await self.pipeline.reply(self.book, st, turn_in, spend, notes=notes)
            watched = self.monitor.observe(to, reply, st, said=text)
            if reply:
                self.last_reply[to] = reply
            async with engine.begin() as c:
                await c.execute(
                    update(playthrough_metrics)
                    .where(playthrough_metrics.c.playthrough_id == self.pid)
                    .values(cost_reply_usd=playthrough_metrics.c.cost_reply_usd + spend.usd.get("reply", 0.0))
                )
                await store.count(c, self.pid, **counts_of(screen, decision), **(watched.counts() if reply else {}))
                turn_id = await store.enqueue(
                    c, self.ids, self.pid, kind="talk", input_mode="text", character=to, flags=screen.flags
                )
                await c.execute(
                    update(turns_t).where(turns_t.c.turn_id == turn_id).values(character_text_missing=reply is None)
                )
                await store.add_utterance(
                    c, self.ids, self.pid, turn_id, speaker="player", text=screen.masked, t=st["t"]
                )
                await store.add_utterance(
                    c, self.ids, self.pid, turn_id, speaker=to, text=reply, t=st["t"], source="live"
                )
            self.turns[self.steps] = turn_id
            card = {"shown": False, "paused": False, "canReturn": True}
            monitor = {"spoilers": [h.fact for h in watched.spoilers], "notes": notes}
            if hold:
                self.held = (self.steps, turn_id)
                return {
                    "safetyCard": card,
                    "safety": screen.self_harm,
                    "safetyHint": decision == "hint",
                    "monitor": monitor,
                    "reply": reply,
                    "characterTextMissing": reply is None,
                    "events": self._events_of(pre),
                    "setPieces": self._set_pieces(pre),
                    "clockMinutes": sum(r.minutes for r in pre),
                    "traceId": turn_id,
                    "held": True,
                }
            done = await self._narrator(engine).run(self.pid)
            self._only(done, turn_id)
            # A draft awaiting an answer: this line is not an answer, so close it as a timeout
            # 回答待ちの草稿：この発言は回答ではないので、タイムアウトとして閉じる
            if self.draft is not None:
                done += await self._close_draft(engine, None, "timeout")
            asking = await self._draft_of(engine, turn_id)
        finally:
            await engine.dispose()
        out: Json = {
            "safetyCard": card,
            "safety": screen.self_harm,
            "safetyHint": decision == "hint",
            "monitor": monitor,
            "reply": reply,
            "characterTextMissing": reply is None,
            "events": self._events_of([*pre, *done]),
            "setPieces": self._set_pieces([*pre, *done]),
            "clockMinutes": sum(r.minutes for r in [*pre, *done]),
            "traceId": turn_id,
        }
        if asking is not None:
            self.draft = (self.steps, asking["draftId"])
            out["confirm"] = asking
        return out

    async def _paused(self, engine: AsyncEngine, to: str, pre: Sequence[Result], screen: Screen) -> Json:
        """A turn stopped by the out-of-character card (B-12, 3.12): write a row with outcome = paused, 0 minutes, no
        original words, and do not call the narrator. In evals the player's next step counts as choosing 「物語に戻る」
        (canReturn), and the pause is lifted at once.

        物語の外に出るカードで止まったターン（B-12、3.12）：outcome = paused、0 分の行を書き、発話の原文はなく、
        ナレーターは呼ばない。評価ではプレイヤーの次のステップを「物語に戻る」（canReturn）を選んだものとみなし、
        一時停止はすぐに解除する。
        """
        async with engine.begin() as c:
            turn_id = await store.enqueue(
                c, self.ids, self.pid, kind="talk", input_mode="text", character=to, status="done"
            )
            await c.execute(
                update(turns_t)
                .where(turns_t.c.turn_id == turn_id)
                .values(outcome="paused", minutes=0, settled_at=func.now())
            )
            await store.count(c, self.pid, **counts_of(screen, "pause"))
        self.turns[self.steps] = turn_id
        self.safety.paused = False  # The eval's next step = the player returned to the story / プレイヤーが物語に戻った
        return {
            "safetyCard": {"shown": True, "paused": True, "canReturn": True},
            "safety": screen.self_harm,
            "outcome": "paused",
            "reply": None,
            "characterTextMissing": False,
            "events": self._events_of(pre),
            "clockMinutes": sum(r.minutes for r in pre),
            "traceId": turn_id,
        }

    async def _count(self, **by: float) -> None:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                await store.count(c, self.pid, **by)
        finally:
            await engine.dispose()

    async def _draft_of(self, engine: AsyncEngine, turn_id: str) -> Json | None:
        """The draft this turn left (StepResult.confirm).

        このターンが残した草稿（StepResult.confirm）。
        """
        async with engine.connect() as c:
            draft = await store.open_draft(c, self.pid)
        if draft is None or draft["turn_id"] != turn_id:
            return None
        return {"draftId": draft["draft_id"], "character": draft["character"], "prompt": draft["prompt"]}

    @_timed
    def confirm(self, answer: str | None) -> Json:
        """Answer the intent confirmation left by the previous step: yes / no / None (no answer, timeout). With no
        draft waiting, `error: "no_draft"`.

        前のステップが残した意図確認に答える：yes / no / None（未回答、タイムアウト）。待っている草稿がなければ
        `error: "no_draft"`。
        """
        if answer not in ("yes", "no", None):
            raise ValueError(
                f"answer must be yes / no / None, got {answer!r} / answer は yes / no / None のいずれか、指定は {answer!r}"
            )
        self.steps += 1
        return self._run(self._confirm(answer))

    async def _confirm(self, answer: str | None) -> Json:
        engine = self._engine()
        try:
            pre = await self._prelude(engine, "confirm")
            if self.draft is None:
                return {"events": self._events_of(pre), "clockMinutes": 0, "error": "no_draft"}
            done = await self._close_draft(engine, answer, "button" if answer is not None else "timeout")
        finally:
            await engine.dispose()
        out: Json = {
            "events": self._events_of([*pre, *done]),
            "setPieces": self._set_pieces([*pre, *done]),
            "clockMinutes": sum(r.minutes for r in [*pre, *done]),
        }
        mine = [r for r in done if r.task.kind == "confirm"]
        if mine:
            out["traceId"] = mine[-1].task.turn_id
            out["result"] = mine[-1].info.get("result")
            if mine[-1].info.get("narration"):
                out["narration"] = mine[-1].info["narration"]
        return out

    @_timed
    def act(self, kind: str, target: str | None, params: Mapping[str, Json], *, action_id: str | None = None) -> Json:
        """动作（api-contract 3.8）：和 `action` 消息一样写一行任务，叙事者判定。还没有 3D 布局的场景里的 `move`
        （归途、村子：路程和过河跟 S-081 的停靠点一起做，M3）抛 `EvalNotImplemented`，用例记成跳过。`move` 的
        `params.crossing`（过河的走法，E5-008）是评测专用参数：契约 3.8 的 `move` 没有 params，正式客户端不发；走不通时
        记一条被否决的 move（R2-precondition）。"""
        if kind == "move":
            here = self._run(self._state())["vars"]["var.player.location"]
            if self.book.places.get(here, {}).get("sceneRef") not in self.book.scenes:
                raise EvalNotImplemented("move（没有布局的场景）")
        self.steps += 1
        request: Json = {"clientMsgId": f"eval-{self.steps}", "kind": kind, "params": dict(params or {})}
        if action_id is not None:
            request["actionId"] = action_id
        if target is not None:
            request["target"] = target
        r, t0 = self._run(self._task("action", request))
        self.turns[self.steps] = r.task.turn_id  # B-13：delete_memory 按这一步的事件找记忆
        info = r.info
        out: Json = {
            "events": self._step_events(r),
            "clockMinutes": r.minutes,
            "traceId": r.task.turn_id,
            "status": info.get("status"),
            "pieces": list(r.pieces),
            "setPieces": self._set_pieces([r]),
            "aid": info.get("aid"),
        }
        for k in ("narration", "setPiece"):
            if k in info:
                out[k] = info[k]
        return out

    async def _screen_plan(self, text: str) -> Screen:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                st = await store.sim_state(c, self.pid)
        finally:
            await engine.dispose()
        ctx = context_of(self.book, st["vars"]["var.player.location"] if st else None, None, None)
        screen = await self.screener.screen(text, ctx, **self.span)
        if self.safety.ambiguous >= 1:
            screen = await self.screener.second_look(screen, text, ctx, **self.span)
        return screen

    @_timed
    def propose(self, text: str) -> Json:
        """幕末用文字说出打算（3.11）：原话存进 utterances，叙事者的 plan 判能不能成行。收幕以前、试过 2 次以后
        返回 `error: "invalid_request"`、没有事件（网关这时回 invalid_request，不写任务）。"""
        self.steps += 1
        screen = self._run(self._screen_plan(text))  # 幕末的打算也筛（UX 在 #112 的评审）
        decision = decide(screen, self.safety)
        if decision == "pause":  # 不交给叙事者、不算试次；回到故事以后幕末页照原样
            self.safety.paused = False
            self._run(self._count(**counts_of(screen, decision)))
            return {
                "safetyCard": {"shown": True, "paused": True, "canReturn": True},
                "safety": screen.self_harm,
                "outcome": "paused",
                "events": [],
                "clockMinutes": 0,
                "accepted": False,
            }
        if decision == "hint":
            self.monitor.calm()
        self._run(self._count(**counts_of(screen, decision)))
        request = {"clientMsgId": f"eval-{self.steps}", "mode": "text"}
        r, t0 = self._run(self._task("plan", request, said=screen.masked, flags=screen.flags))
        info = r.info
        moved = [e for e in r.events if e["type"] == "act-transition" and e["actor"] == "player"]
        alt = info.get("alternative")
        out: Json = {
            "events": self._step_events(r),
            "clockMinutes": r.state["t"] - t0,
            "traceId": r.task.turn_id,
            "accepted": bool(info.get("accepted")),
            "plan": moved[-1].get("plan") if moved else None,
            "alternative": alt,
            "alternatives": [alt] if alt else [],
            "triesLeft": info.get("triesLeft"),
            "narration": info.get("narration", []),
            "pieces": list(r.pieces),
            "setPieces": self._set_pieces([r]),
        }
        if "error" in info:
            out["error"] = info["error"]
        return out

    @_timed
    def choose(self, exit: str, en_route: int | None = None) -> Json:
        """幕末选去处（3.11）：给定去处，或打算不成行时的替代去处（`plan_…`）。不在选项里返回
        `error: "invalid_choice"`、没有事件（E4-103）。"""
        self.steps += 1
        request: Json = {"clientMsgId": f"eval-{self.steps}", "optionId": exit}
        if en_route is not None:
            request["enRouteChoice"] = en_route
        r, t0 = self._run(self._task("choose", request))
        out: Json = {
            "events": self._step_events(r),
            "clockMinutes": r.state["t"] - t0,
            "traceId": r.task.turn_id,
            "pieces": list(r.pieces),
            "setPieces": self._set_pieces([r]),
        }
        if "error" in r.info:
            out["error"] = r.info["error"]
        else:
            out["toAct"] = r.info.get("toAct")
            self.monitor.act_ended()  # 似是而非之后的提示带到这一幕结束
        return out

    async def _task(
        self, kind: str, request: Json, said: str | None = None, flags: Iterable[str] | None = None
    ) -> tuple[Result, int]:
        """写一行任务（打算还存原话），叫叙事者做完。返回这一步的结果和之前的故事时刻。hold 着的那一轮先提交、
        等回答的草稿按超时关掉，它们的事件放在这一步的前面（B-4）。"""
        engine = self._engine()
        try:
            async with engine.connect() as c:
                before = await store.sim_state(c, self.pid)
            assert before is not None
            pre = await self._prelude(engine, kind)
            async with engine.begin() as c:
                st = await store.sim_state(c, self.pid)
                assert st is not None
                turn_id = await store.enqueue(
                    c,
                    self.ids,
                    self.pid,
                    kind=kind,
                    input_mode="text" if kind == "plan" else None,
                    client_msg_id=request.get("clientMsgId"),
                    request=request,
                    flags=flags,
                )
                if said is not None:
                    await store.add_utterance(c, self.ids, self.pid, turn_id, speaker="player", text=said, t=st["t"])
            done = await self._narrator(engine).run(self.pid)
        finally:
            await engine.dispose()
        return self._merged(pre, self._only(done, turn_id)), int(before["t"])

    @staticmethod
    def _merged(pre: Sequence[Result], r: Result) -> Result:
        """这一步之前提交的（hold 着的那一轮、超时关掉的草稿）的事件并进这一步的结果。"""
        if not pre:
            return r
        return replace(
            r,
            events=[e for p in pre for e in p.events] + r.events,
            push=[m for p in pre for m in p.push] + r.push,
            checked=[c for p in pre for c in p.checked] + r.checked,
            minutes=sum(p.minutes for p in pre) + r.minutes,
        )

    @_timed
    def advance(self, minutes: int) -> Json:
        self.steps += 1
        return self._run(self._advance(minutes))

    async def _advance(self, minutes: int) -> Json:
        engine = self._engine()
        try:
            pre = await self._prelude(engine, "advance")
            async with engine.begin() as c:
                turn_id = await store.enqueue(c, self.ids, self.pid, kind="advance", minutes=minutes)
            done = await self._narrator(engine).run(self.pid)
        finally:
            await engine.dispose()
        result = self._merged(pre, self._only(done, turn_id))
        return {"events": self._step_events(result), "clockMinutes": result.minutes, "traceId": turn_id}

    @staticmethod
    def _only(done: Sequence[Result], turn_id: str) -> Result:
        for r in done:
            if r.task.turn_id == turn_id:
                return r
        raise RuntimeError(f"叙事者没有提交这一步（{turn_id}）")

    @staticmethod
    def _step_events(result: Result) -> list[Json]:
        """这一步写的全部事件；被否决的给候选原本的 effects（日志里那条 effects 是空的，契约第 3 节）。"""
        original = {c.candidate.get("eventId"): c.effects for c in result.checked if not c.passed}
        out = []
        for ev in result.events:
            ev = copy.deepcopy(ev)
            if ev["eventId"] in original:
                ev["effects"] = copy.deepcopy(original[ev["eventId"]])
            out.append(ev)
        return out

    def check(self, candidate: Mapping[str, Json], turn: Mapping[str, Json], model_checks: str = "scoped") -> Json:
        """S-2：候选事件交给第 3 步，再按 `model_checks` 跑第 4 步（`scoped` = 正式范围：过了第 3 步、`effects`
        不为空的；`all` = 都跑），不改写、不提交。没跑第 4 步的 R5 和 R6 其余部分记 skipped。"""
        if model_checks not in ("scoped", "all"):
            raise ValueError(f"model_checks 只能是 scoped / all，得到 {model_checks!r}")
        st = self._run(self._state())
        t = TurnInput(
            character=turn.get("to"),
            player=turn.get("player"),
            reply=turn.get("reply"),
            act=turn.get("act"),
        )
        checked = self._run(
            self.pipeline.check_only(self.book, st, dict(candidate), t, model_checks, Spend(), self.span)
        )
        return {"check": checked.check, "rules": checked.rules}

    # —— 查询 ——

    async def _state(self) -> SimState:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                st = await store.sim_state(c, self.pid)
        finally:
            await engine.dispose()
        assert st is not None
        return st

    def diagnostics(self) -> Json:
        """评测专用：只给统计器，不进 AI 玩家的公开观察。旧批次缺字段保持未知。"""
        return self._run(self._diagnostics())

    async def _diagnostics(self) -> Json:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                row = await store.playthrough(c, self.pid)
                metrics = (
                    (
                        await c.execute(
                            select(playthrough_metrics).where(playthrough_metrics.c.playthrough_id == self.pid)
                        )
                    )
                    .mappings()
                    .one()
                )
                missing = (
                    await c.execute(
                        select(func.count())
                        .select_from(turns_t)
                        .where(turns_t.c.playthrough_id == self.pid, turns_t.c.character_text_missing.is_(True))
                    )
                ).scalar_one()
        finally:
            await engine.dispose()
        return {
            "version": 1,
            "budgetTier": row["budget_tier"] if row else None,
            "metrics": {
                k: metrics[k]
                for k in (
                    "degraded_reason",
                    "turns_timed_out",
                    "ending_template",
                    "memories_failed",
                    "safety_unscreened",
                )
            },
            "characterTextMissing": missing,
            "pipelineCalls": copy.deepcopy(self.call_observations),
            "endingCalls": ending_observations(self.tracer),
            "scope": "text-eval; pipeline terminal states and persisted metrics; live transport not measured",
        }

    def state(self) -> Json:
        """契约 3.1 的 WorldState（W-1 的 world_state()）。"""
        self._run(self._flush())
        return world_state(self.book.world, self._run(self._state()), self.pid)

    def events(self) -> list[Json]:
        """这一局的全部事件（含评测布置的、被否决的），按 seq。"""
        self._run(self._flush())
        return self._run(self._events())

    def view(self, after_seq: int = 0) -> Json:
        """AI 玩家看的（B-5）：2.3 的快照和 2.4 的玩家可见事件（seq 大于 after_seq 的），和网关 `GET …/snapshot`、
        `GET …/events` 同一个投影。没有变量、节拍结果、不可见的事件。"""
        self._run(self._flush())
        return self._run(self._view(after_seq))

    async def _view(self, after_seq: int) -> Json:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                row = await store.playthrough(c, self.pid)
                st = await store.sim_state(c, self.pid)
                log_ = await store.event_log(c, self.pid, self.book.version)
                draft = await store.open_draft(c, self.pid)
        finally:
            await engine.dispose()
        assert row is not None and st is not None
        snap = snapshot(self.book, self.pid, self.role, row["status"], st, st["seq"], Run.of(row))
        if draft is not None:
            snap["pending"]["confirm"] = {
                "draftId": draft["draft_id"],
                "character": draft["character"],
                "prompt": draft["prompt"],
            }
        return {"snapshot": snap, "events": visible_events(self.book, self.role, log_, after_seq)}

    def manifest(self) -> Json:
        """2.1 的 manifest（B-7 的生成器），和正式网关 `GET /v1/books/{id}/manifest` 一样：身份的说明、人物的名字
        和读法。"""
        if self._manifest is None:
            s = self.settings
            self._manifest = generate(self.book, self.schemas, packs=s.packs, voices=s.voice_dir, release=s.release)
        return copy.deepcopy(self._manifest.doc)

    @_timed
    def retract(self, step: int) -> Json:
        """作废第 step 步那一轮（B-4）：还 hold 着就作废（原话清空、不产生事件），已经提交了 `too_late`。"""
        self.steps += 1
        return self._run(self._retract(step))

    async def _retract(self, step: int) -> Json:
        engine = self._engine()
        try:
            held = self.held
            pre = await self._prelude(engine, "retract", retract=step)
            kind = None
            if held is not None and held[0] == step:
                self.held = None
                async with engine.begin() as c:
                    kind = await store.retract_queued(c, self.pid, held[1])
        finally:
            await engine.dispose()
        out: Json = {
            "retract": "retracted" if kind is not None else "too_late",
            "events": self._events_of(pre),
            "clockMinutes": sum(r.minutes for r in pre),
        }
        if step in self.turns:
            out["traceId"] = self.turns[step]
        return out

    def utterance_cleared(self, step: int) -> bool:
        """第 step 步那一轮玩家和人物的原话都清空了（B-4：作废的一轮当场清空）。"""
        self._run(self._flush())
        turn_id = self.turns.get(step)
        if turn_id is None:
            raise ValueError(f"第 {step} 步不是对话")
        return self._run(self._cleared(turn_id))

    async def _cleared(self, turn_id: str) -> bool:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                texts = (await c.execute(select(utterances.c.text).where(utterances.c.turn_id == turn_id))).scalars()
                return all(t is None for t in texts)
        finally:
            await engine.dispose()

    async def _events(self) -> list[Json]:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                return await store.event_log(c, self.pid, self.book.version)
        finally:
            await engine.dispose()

    # —— 记忆和删除（B-13） ——

    def memory_book(self) -> Json:
        """模拟玩家只读正式記憶帳投影，不读检查用的 memories() 内部字段。"""
        self._run(self._flush())
        return self._run(self._memory_book())

    async def _memory_book(self) -> Json:
        from zoujin_backend.gateway import memory_book

        engine = self._engine()
        try:
            async with engine.connect() as c:
                return await memory_book.view(c, self.book, self.pid, self.role)
        finally:
            await engine.dispose()

    def delete_memory_id(self, memory_id: str) -> Json:
        """玩家按記憶帳给的 ID 删除；和正式 REST 共用删除事务，不能跨局删除。"""
        self._run(self._flush())
        self.steps += 1
        return self._run(self._delete_memory_id(memory_id))

    async def _delete_memory_id(self, memory_id: str) -> Json:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                d = await memory_delete.delete_memory(c, self.library, self.ids, self.schemas, self.pid, memory_id)
                evs = await store.event_log(c, self.pid, self.book.version, after_seq=(d.seq or 1) - 1)
        finally:
            await engine.dispose()
        self.last_reply.pop(d.character, None)
        return {
            "events": evs if d.seq is not None else [],
            "clockMinutes": 0,
            "deleted": d.memory_id,
            "promiseVoided": d.promise_voided,
        }

    def delete_memory(self, character: str, from_step: int) -> Json:
        """删这个人物来源于第 from_step 步提交的事件的那条记忆（和 REST 同一个函数；一个人物一轮最多一条，所以唯一）。
        没有这样的记忆 → ValueError（评测报错，不静默成功）。"""
        self._run(self._flush())
        self.steps += 1
        turn_id = self.turns.get(from_step)
        if turn_id is None:
            raise ValueError(f"第 {from_step} 步没有提交的一轮")
        return self._run(self._delete_memory(character, turn_id))

    async def _delete_memory(self, character: str, turn_id: str) -> Json:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                ids = set(
                    (
                        await c.scalars(
                            select(events_t.c.event_id).where(
                                events_t.c.playthrough_id == self.pid, events_t.c.turn_id == turn_id
                            )
                        )
                    ).all()
                )
                target = next(
                    (r["memory_id"] for r in await memory.alive(c, self.pid, character) if ids & set(r["from_events"])),
                    None,
                )
                if target is None:  # 不静默成功（数据评审）：评测报错
                    raise ValueError(f"{character} 没有来源于这一步的记忆")
                d = await memory_delete.delete_memory(c, self.library, self.ids, self.schemas, self.pid, target)
                evs = await store.event_log(c, self.pid, self.book.version, after_seq=(d.seq or 1) - 1)
        finally:
            await engine.dispose()
        return {
            "events": evs if d.seq is not None else [],
            "clockMinutes": 0,
            "deleted": d.memory_id,
            "promiseVoided": d.promise_voided,
        }

    def delete_playthrough(self) -> Json:
        """L2：这一局全删（和 REST 同一个函数）。之后 `db_absent` 查的就是这一局。"""
        self._run(self._flush())
        self.steps += 1
        self._run(self._delete_playthrough())
        return {"events": [], "clockMinutes": 0}

    async def _delete_playthrough(self) -> None:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                await memory_delete.delete_playthrough(c, self.pid)
        finally:
            await engine.dispose()
        self.deleted = self.pid

    def new_playthrough(self) -> Json:
        """同一个账号、同一个起点再开一局；这一局放弃（`abandoned`）。之后的步骤和查询都对新的一局。"""
        self._run(self._flush())
        self.steps += 1
        self._run(self._new_playthrough())
        return {"events": [], "clockMinutes": 0}

    async def _new_playthrough(self) -> None:
        engine = self._engine()
        try:
            async with engine.begin() as c:
                await c.execute(
                    update(playthroughs).where(playthroughs.c.playthrough_id == self.pid).values(status="abandoned")
                )
        finally:
            await engine.dispose()
        self.safety = SafetyState()
        self.monitor = Monitor(self.library)
        self.monitor.attach(self.book)
        self.draft = None
        if self.persona is not None:
            await self._open()
        else:
            await self._setup()

    def memories(self, character: str) -> list[Json]:
        """契约第 4 节的 MemoryItem，删了的也在（带 deletedAt，text 是空的）。"""
        self._run(self._flush())
        return self._run(self._memories(character))

    async def _memories(self, character: str) -> list[Json]:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                rows = (
                    await c.execute(
                        select(memory_items)
                        .where(memory_items.c.playthrough_id == self.pid, memory_items.c.character == character)
                        .order_by(memory_items.c.t, memory_items.c.created_at)
                    )
                ).mappings()
                return [memory.item_json(dict(r)) for r in rows]
        finally:
            await engine.dispose()

    def trust(self, character: str) -> int:
        self._run(self._flush())
        return self._run(self._trust(character))

    async def _trust(self, character: str) -> int:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                return await memory.trust_of(c, self.book, self.pid, self.role, character)
        finally:
            await engine.dispose()

    def db_absent(self, tables: Sequence[str]) -> Mapping[str, int]:
        """每张表里还剩这一局（删了的那一局，没删过就是现在这一局）几行。data-design 5.3 里还没建的表
        （`NOT_BUILT`，局势说明不存库）答 0；名单外不认识的表名不答（评测报「后端没回这张表」，数据评审）。"""
        return self._run(self._db_absent(tables))

    async def _db_absent(self, tables: Sequence[str]) -> Mapping[str, int]:
        pid = self.deleted or self.pid
        engine = self._engine()
        out: dict[str, int] = {}
        try:
            async with engine.connect() as c:
                for name in tables:
                    if name in NOT_BUILT:
                        out[name] = 0
                    if name not in PER_PLAYTHROUGH:
                        continue
                    t = metadata.tables[name]
                    n = await c.scalar(select(func.count()).select_from(t).where(t.c.playthrough_id == pid))
                    out[name] = int(n or 0)
        finally:
            await engine.dispose()
        return out

    # —— 还没做的 ——

    def _no(self, name: str) -> NoReturn:
        raise EvalNotImplemented(name)

    def silence(self, seconds: int) -> Json:
        self._no("silence")

    def ending(self) -> Json:
        """B-9：存的 Ending（数据契约第 5 节的完整形状，含 `signature`）；还没进结局（或结局任务还没做完）返回 None。
        结局任务和别的任务一样，在触发它的那一步里同步跑完。"""
        self._run(self._flush())
        return self._run(self._ending())

    async def _ending(self) -> Json:
        engine = self._engine()
        try:
            async with engine.connect() as c:
                body = await c.scalar(select(endings.c.body).where(endings.c.playthrough_id == self.pid))
        finally:
            await engine.dispose()
        return copy.deepcopy(body) if body is not None else None


def play_setup(w: Writer, scenarios: Mapping[str, Json], setup: Mapping[str, Json]) -> None:
    """起点：用 W-1 的 `opening()` 推演（和评测运行器同一套），结果写成这一局的初始事件（B-0 第 9 条）。

    `place`、情景的节拍改动、情景的事件、到点的节拍和期限、只推进时钟的事件都由 `opening()` 给，这里只补成完整的
    事件（eventId、summary、check）再按 seq 应用；之后在起点时刻追加 `events`（评测布置，api-contract 第 7 节）。
    """
    if "scenario" in setup:
        sc_id, until = str(setup["scenario"]), None
    else:
        sc_id, until = parse_checkpoint(str(setup["checkpoint"]))
    opened, _ = opening(w.book.world, w.state["role"], scenarios[sc_id], until, place=setup.get("place"))
    for d in opened:
        w.add(w.from_draft(d) if d["source"] == "schedule" else _setup_event(w, d))
    for e in setup.get("events", []):
        w.add(
            w.full(
                t=w.state["t"],
                dt=0,
                actor="system",
                type="action",
                place=w.player_place,
                summary=e.get("note") or "評価の設定",
                effects=e["effects"],
                check=SETUP_PASSED,
            )
        )


def setup_act_end(book: Book, w: Writer, setup: Mapping[str, Json]) -> Json | None:
    """检查点停在这一幕的收幕节拍上（例 `sc.canon@beat.07`）：setup 之后就是幕末待选（B-3 第 5 条），幕末的去处
    记在局上。只认收幕节拍本身：停在更后面的节拍上的老用例（`opening()` 不换幕）照旧可以对话。"""
    if "checkpoint" not in setup:
        return None
    _, until = parse_checkpoint(str(setup["checkpoint"]))
    act = acts.current_act(book, w.state)
    if not act.get("exits") or until is None or until[0] != "beat" or until[1] not in act["end"]["onBeats"]:
        return None
    if not act_closed(book, w.state):
        return None
    return acts.act_end(book, w.state, 0, w.events)


def _setup_event(w: Writer, d: Opened) -> Json:
    """开局地点、情景、只推进时钟的事件：summary 用 `opening()` 给的 note。"""
    e = d["event"]
    return w.full(
        t=e["t"],
        dt=e["dt"],
        actor=e["actor"],
        type=e["type"],
        origin=e.get("origin"),
        place=e["place"],
        summary=d.get("note") or "評価の設定",
        effects=e["effects"],
        check=SETUP_PASSED,
    )
