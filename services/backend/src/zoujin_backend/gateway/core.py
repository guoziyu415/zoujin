"""The gateway's overall state: the database, world model, Schema, narrator calls and open connections. REST
(rest.py) and WebSocket (ws.py) both take what they need from here.

Everything pushed to the frontend is computed on the fly from the events in the database (projection.py):
- snapshot = the projection of the SimState cached in world_state, plus the location points and pending items
  recorded on the playthrough (B-3, `store.Run`);
- commit = the run of events written by one commit (same idempotency-key prefix, `commit_key`); patch is the diff
  between the snapshots before and after that run.
  The commit that enters the ending (B-9): `ending_started` from `turns.result.before` goes before its commit.
  The commit for answering yes to an intent confirmation (B-4): `turnId` is the original turn, and if the recheck
  fails `narration` carries one line (`turns.result`).
  The player's location point is not in WorldState (contract 3.1): `patch.player.spot` after a situational action or
  an act-change landing comes from that commit's result (`turns.result.playerSpot`); movement actions (`move`, `go`)
  don't carry it (B-3 item 1).
  Memory changes (B-13): `turns.result.memories` records which memories this commit wrote or deleted and the
  relationship at that time; the text comes from `memory_items`, and ones later deleted in the 記憶帳 are no longer
  included (deleted text doesn't appear in resent commits either). Promise changes follow the promise effects of the
  run's events and the state after it.

ゲートウェイ全体の状態：データベース、世界モデル、Schema、ナレーターの呼び出し、開いている接続。REST（rest.py）と
WebSocket（ws.py）はどちらもここから取る。

フロントエンドに送るものはすべてデータベースのイベントからその場で計算する（projection.py）：
- スナップショット = world_state にキャッシュされた SimState の投影に、プレイに記録された位置点と保留中のものを
  加えたもの（B-3、`store.Run`）；
- commit = 1 回の commit で書かれた一続きのイベント（冪等キーの前半が同じ、`commit_key`）。patch はその前後の
  スナップショットの差分。
  エンディングに入る commit（B-9）：`turns.result.before` の `ending_started` をその commit の前に置く。
  意図の確認に「はい」と答えた commit（B-4）：`turnId` は元のターンで、再チェックで通らなければ `narration` に
  1 行付く（`turns.result`）。
  プレイヤーの位置点は WorldState に入らない（契約 3.1）：状況アクションや幕の切り替わりの着地のあとの
  `patch.player.spot` はその commit の結果（`turns.result.playerSpot`）から渡し、移動のアクション（`move`、`go`）
  には付けない（B-3 第 1 項）。
  記憶の変化（B-13）：`turns.result.memories` にこの commit で書いた・削除した記憶とそのときの関係を記録し、文は
  `memory_items` から取る。あとで記憶帳で削除されたものはもう含めない（再送する commit にも削除された文は出ない）。
  約束の変化は、この一続きのイベントの promise の効果とその後の状態から渡す。
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from zoujin_worldsim import SimState, apply, initial_state

from zoujin_backend import budget
from zoujin_backend.config import Settings
from zoujin_backend.db import store
from zoujin_backend.db.events import commit_key, recorded_at
from zoujin_backend.db.store import Run
from zoujin_backend.db.tables import memory_items, turns
from zoujin_backend.gateway.fallback import AudioTranscriber, FakeAudioTranscriber
from zoujin_backend.ids import IdGen
from zoujin_backend.manifest import Manifest
from zoujin_backend.models.ledger import Ledger
from zoujin_backend.models.live import LiveModel
from zoujin_backend.projection import Away, is_visible, patch, snapshot, visible_event, visible_events, with_locations
from zoujin_backend.safety import Screener
from zoujin_backend.schemas import SchemaBook
from zoujin_backend.trace import Tracer
from zoujin_backend.world import Book, Library

if TYPE_CHECKING:
    from zoujin_backend.gateway.voice import Parked
    from zoujin_backend.gateway.ws import Conn
    from zoujin_backend.narrator.pipeline import Pipeline

log = logging.getLogger("zoujin.gateway")

Json = Any

# B-14: how often to read the global voice switch from the database. / B-14：全体の音声スイッチを DB から読む間隔。
VOICE_SWITCH_TTL_S = 30.0
# How many seconds at most a reconnecting hello waits for the old connection to finish writing the turn cut off by the
# disconnect (normally milliseconds).
# 再接続の hello が、古い接続が切断時のターンを書き終えるのを待つ最大秒数（通常はミリ秒単位）。
HANDOFF_WAIT_S = 5.0


def memory_changes(result: Json, texts: dict[str, str | None]) -> list[Json]:
    """commit.memories (api-contract 3.4, B-13): added carries the text and kind; one whose text is already deleted
    isn't pushed. deleted carries no text.

    commit.memories（api-contract 3.4、B-13）：added は文と kind を持つ。文がすでに削除されたものは送らない。deleted は
    文を持たない。
    """
    out = []
    for m in result.get("memories", []):
        if m["change"] == "deleted":
            out.append({k: m[k] for k in ("character", "change", "memoryId", "relationLabel", "relationLevel")})
        elif texts.get(m["memoryId"]):
            out.append({**m, "text": texts[m["memoryId"]]})
    return out


def promise_changes(seg: Sequence[Json], after: SimState) -> list[Json]:
    """commit.promises: promises involving the player that this run of events touched, as of the state after the run
    (direction from contract 3.1).

    commit.promises：この一続きのイベントが動かした、プレイヤーに関わる約束。その後の状態に従う（契約 3.1 の
    direction）。
    """
    out: list[Json] = []
    seen: set[str] = set()
    for ev in seg:
        for e in ev["effects"]:
            pid = e.get("promiseId") if e.get("op") == "promise" else None
            p = (after.get("promises") or {}).get(pid or "")
            if pid is None or pid in seen or p is None:
                continue
            if p["from"] == "player":
                character, direction = p["to"], "playerToCharacter"
            elif p["to"] == "player":
                character, direction = p["from"], "characterToPlayer"
            else:
                continue
            seen.add(pid)
            out.append(
                {
                    "promiseId": pid,
                    "character": character,
                    "text": p["text"],
                    "direction": direction,
                    "status": p["status"],
                }
            )
    return out


class NarratorClient(Protocol):
    async def run(self, pid: str) -> int: ...


class IdToken:
    """OIDC token for calling the narrator on Cloud Run (B-23): the audience is the narrator's address; the gateway
    service account's token is fetched from the metadata server and refreshed every 50 minutes.

    Cloud Run 上でナレーターを呼ぶための OIDC トークン（B-23）：audience はナレーターのアドレス。ゲートウェイの
    サービスアカウントのトークンをメタデータサーバーから取得し、50 分ごとに更新する。
    """

    REFRESH_S = 50 * 60

    def __init__(self, audience: str, fetch: Callable[[str], str] | None = None) -> None:
        self.audience = audience
        self.fetch = fetch or _fetch_id_token
        self._token = ""
        self._at = 0.0
        self._lock = asyncio.Lock()

    async def __call__(self) -> str:
        async with self._lock:
            now = time.monotonic()
            if not self._token or now - self._at > self.REFRESH_S:
                self._token = await asyncio.to_thread(self.fetch, self.audience)
                self._at = now
            return self._token


def _fetch_id_token(audience: str) -> str:  # pragma: no cover - Cloud Run only / Cloud Run 上のみ
    import google.auth.transport.requests
    import google.oauth2.id_token

    token: str = google.oauth2.id_token.fetch_id_token(google.auth.transport.requests.Request(), audience)  # type: ignore[no-untyped-call]
    return token


class HttpNarrator:
    """Locally this is HTTP (two processes); when deployed it is a Cloud Run service-to-service call (token supplies
    the OIDC token). transport lets tests plug in an in-process narrator.

    ローカルでは HTTP（2 つのプロセス）、デプロイ時は Cloud Run のサービス間呼び出し（token が OIDC トークンを渡す）。
    transport はテストでプロセス内のナレーターをつなぐためのもの。
    """

    def __init__(
        self,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
        token: Callable[[], Awaitable[str]] | None = None,
    ) -> None:
        self.client = httpx.AsyncClient(base_url=base_url, timeout=30.0, transport=transport)
        self.token = token

    async def run(self, pid: str) -> int:
        headers = {"Authorization": f"Bearer {await self.token()}"} if self.token is not None else None
        r = await self.client.post(f"/internal/v1/playthroughs/{pid}/run", headers=headers)
        r.raise_for_status()
        return int(r.json()["processed"])

    async def close(self) -> None:
        await self.client.aclose()


@dataclass
class Pt:
    """A playthrough as the gateway sees it. / ゲートウェイから見た 1 つのプレイ。"""

    pid: str
    user_id: str
    book: Book
    role_id: str
    status: str
    last_seq: int
    last_active_at: Any
    run: Run = field(default_factory=Run)


@dataclass
class Gateway:
    settings: Settings
    engine: AsyncEngine
    library: Library
    schemas: SchemaBook
    live: LiveModel
    narrator: NarratorClient
    # 2.1: generated once from `Library.current` at process start (B-7); 404 if missing.
    # 2.1：プロセス起動時に `Library.current` から 1 回生成する（B-7）。なければ 404。
    manifest: Manifest | None = None
    # Opened resources looked up by book; manifest keeps the old interface.
    # 本ごとに公開済みのリソースを引く。manifest は旧インターフェースのために残す。
    manifests: dict[str, Manifest] = field(default_factory=dict)
    # Old world versions authorized for resuming. / 再開が許可された古い世界のバージョン。
    history_manifests: dict[str, Manifest] = field(default_factory=dict)
    ids: IdGen = field(default_factory=IdGen)
    # One connection per playthrough (section 4, 4009). / 1 プレイにつき接続 1 本（第 4 節、4009）。
    conns: dict[str, Conn] = field(default_factory=dict)
    draining: bool = False
    tasks: set[asyncio.Task[Any]] = field(default_factory=set)
    # Conversation turns per playthrough still being handed to the narrator (`_finish`): a reconnecting hello first
    # waits for the old connection's ones to be written, so lastTurn is accurate (section 4).
    # プレイごとにまだナレーターに渡している最中の会話ターン（`_finish`）：再接続の hello はまず古い接続のこれらが
    # 書き終わるのを待ち、それで lastTurn が正確になる（第 4 節）。
    handing: dict[str, set[asyncio.Task[Any]]] = field(default_factory=dict)
    tracer: Tracer = field(default_factory=Tracer)  # B-4：gateway.retract
    # B-11: Live sessions and recent conversation parked after a disconnect (memory only), taken over by a
    # reconnecting hello (`gateway/voice.py`).
    # B-11：切断後に預けておく Live セッションと直近の会話（メモリ内のみ）。再接続の hello が引き継ぐ
    # （`gateway/voice.py`）。
    parked: dict[str, Parked] = field(default_factory=dict)
    # B-10: fallback transcription (when the character has audio but no text), the Live ledger (with real Live) and
    # the model name used for bookkeeping.
    # B-10：補完の文字起こし（登場人物に音声はあるが文字がないとき）、Live の台帳（本物の Live のとき）、記帳用の
    # モデル名。
    transcriber: AudioTranscriber = field(default_factory=FakeAudioTranscriber)
    live_ledger: Ledger | None = None
    live_model_name: str = "fake-live"
    # B-12: safety screening of every player line (text model and Model Armor per ZJ_MODEL; built from settings when
    # not given; tests can swap it).
    # B-12：プレイヤーの発言ごとの安全チェック（テキストモデルと Model Armor は ZJ_MODEL に従う。渡されなければ
    # settings から作る。テストで差し替えられる）。
    screener: Screener = field(default=None)  # type: ignore[assignment]
    # B-14: after degrading, characters answer in text (the narrator's `reply`).
    # B-14：縮退後は登場人物が文字で答える（ナレーターの `reply`）。
    replier: Pipeline = field(default=None)  # type: ignore[assignment]
    # B-14: cache of the global voice switch (when it was read, whether it's on); tests set voice_ttl_s = 0.
    # B-14：全体の音声スイッチのキャッシュ（読んだ時刻、オンかどうか）。テストでは voice_ttl_s = 0 にする。
    voice_cache: tuple[float, bool] | None = None
    voice_ttl_s: float = VOICE_SWITCH_TTL_S
    # For tests: every server message sent (already validated against the Schema).
    # テスト用：送信したサーバーメッセージすべて（Schema の検証済み）。
    on_send: Callable[[Json], None] | None = None

    def __post_init__(self) -> None:
        if self.manifest is not None:
            self.manifests.setdefault(self.manifest.book_id, self.manifest)
        if self.screener is None:
            from zoujin_backend.gateway.safety import build_screener

            self.screener = build_screener(self.settings, self.tracer)
        # Characters' text answers after degrading (B-14): the same text model as the screening.
        # 縮退後の登場人物の文字の答え（B-14）：安全チェックと同じテキストモデル。
        if self.replier is None:
            from zoujin_backend.narrator.pipeline import Pipeline

            self.replier = Pipeline(
                text=self.screener.text, schemas=self.schemas, ids=self.ids, tracer=self.tracer, on_rate_limit="degrade"
            )

    # —— Budget and degrading (B-14, `zoujin_backend/budget.py`) / 予算と縮退 ——

    async def voice_on(self) -> bool:
        """The global voice switch, read from the database at most every `voice_ttl_s` seconds (no redeploy needed after
        ops change it).

        全体の音声スイッチ。DB からは最大で `voice_ttl_s` 秒ごとに 1 回読む（運用で変えても再デプロイ不要）。
        """
        now = time.monotonic()
        if self.voice_cache is not None and now - self.voice_cache[0] < self.voice_ttl_s:
            return self.voice_cache[1]
        async with self.engine.connect() as c:
            on = await budget.voice_enabled(c)
        self.voice_cache = (now, on)
        return on

    async def voice_block(self, pid: str, user_id: str) -> str | None:
        """Why this playthrough can't use voice now (`degraded.reason`): service if the global switch is off; budget if
        spending hit the cap; daily if today's voice time is used up. None if none apply.

        このプレイがいま音声を使えない理由（`degraded.reason`）：全体のスイッチがオフなら service、支出が上限に
        達したら budget、今日の音声時間を使い切ったら daily。どれでもなければ None。
        """
        if not await self.voice_on():
            return "service"
        async with self.engine.begin() as c:
            tier = await budget.refresh(c, pid, self.tracer)
            used = await budget.voice_seconds_today(c, user_id)
        if tier == "degraded":
            return "budget"
        if budget.minutes_left(used) <= 0:
            return "daily"
        return None

    async def voice_state(self, c: AsyncConnection, pid: str, user_id: str) -> Json:
        """`welcome.voice` and the snapshot's `voice` (contract 3.x): enabled = the global switch; degraded = this
        playthrough has switched to text.

        `welcome.voice` とスナップショットの `voice`（契約 3.x）：enabled = 全体のスイッチ、degraded = このプレイは
        すでに文字に切り替わった。
        """
        on = await self.voice_on()
        left = budget.minutes_left(await budget.voice_seconds_today(c, user_id))
        tier = await budget.tier_of(c, pid)
        return {"enabled": on, "degraded": not on or tier == "degraded" or left <= 0, "minutesLeftToday": left}

    # —— Playthroughs / プレイ ——

    async def pt(self, c: AsyncConnection, pid: str) -> Pt | None:
        row = await store.playthrough(c, pid)
        if row is None:
            return None
        return Pt(
            pid=pid,
            user_id=row["user_ref"],
            book=self.library.version(row["world_model_version"]),
            role_id=row["role_id"],
            status=row["status"],
            last_seq=row["last_seq"],
            last_active_at=row["last_active_at"],
            run=Run.of(row),
        )

    async def snapshot(self, pid: str) -> Json | None:
        """The 2.3 snapshot; if the opening task isn't done yet, have the narrator do it first.

        2.3 のスナップショット。開始のタスクがまだ終わっていなければ、先にナレーターにやらせる。
        """
        for attempt in range(2):
            async with self.engine.connect() as c:
                pt = await self.pt(c, pid)
                st = await store.sim_state(c, pid)
            if pt is None:
                return None
            if st is not None:
                snap = snapshot(pt.book, pid, pt.role_id, pt.status, st, st["seq"], pt.run)
                async with self.engine.connect() as c:
                    snap["voice"] = await self.voice_state(c, pid, pt.user_id)
                return snap
            if attempt == 0:
                await self.narrator.run(pid)
        raise RuntimeError(f"{pid}: the narrator didn't write the opening / ナレーターが開始を書かなかった")

    async def active_ref(self, c: AsyncConnection, pt: Pt) -> Json:
        st = await store.sim_state(c, pt.pid)
        t = st["t"] if st is not None else int(pt.book.roles[pt.role_id]["startT"])
        act = pt.book.act_of(st["vars"]) if st is not None else pt.book.act_of({})
        return {
            "playthroughId": pt.pid,
            "roleId": pt.role_id,
            "roleName": pt.book.roles[pt.role_id]["name"],
            "actId": act,
            "tLabel": pt.book.label(t),
            "updatedAt": recorded_at(pt.last_active_at),
        }

    # —— Pushing / プッシュ ——

    async def commits(self, pid: str, after_seq: int, upto_seq: int | None = None) -> tuple[list[Json], int]:
        """The commit messages (3.4) after after_seq, and the seq pushed up to. Split by commit, one message per run;
        a run of only invisible events still gets one.

        after_seq より後の commit メッセージ（3.4）と、送った先の seq。commit ごとに区切り、一続きごとに 1 件。見えない
        イベントだけの一続きでも 1 件送る。
        """
        async with self.engine.connect() as c:
            pt = await self.pt(c, pid)
            if pt is None:
                return [], after_seq
            log_ = await store.event_log(c, pid, pt.book.version)
            keys = {commit_key(e["idempotencyKey"]) for e in log_ if e["seq"] > after_seq}
            rows = (
                await c.execute(select(turns.c.turn_id, turns.c.kind, turns.c.result).where(turns.c.turn_id.in_(keys)))
            ).all()
            ids = [m["memoryId"] for r in rows for m in (r.result or {}).get("memories", [])]
            texts = dict(
                (
                    await c.execute(
                        select(memory_items.c.memory_id, memory_items.c.text).where(memory_items.c.memory_id.in_(ids))
                    )
                ).all()
            )
        kinds = {r.turn_id: r.kind for r in rows}
        results = {r.turn_id: r.result or {} for r in rows}
        book = pt.book
        state = initial_state(book.world, pt.role_id)
        segments: list[list[Json]] = []
        for ev in log_:
            if upto_seq is not None and ev["seq"] > upto_seq:
                break
            if ev["seq"] <= after_seq:
                state = apply(book.world, state, ev)
                continue
            if segments and commit_key(segments[-1][-1]["idempotencyKey"]) == commit_key(ev["idempotencyKey"]):
                segments[-1].append(ev)
            else:
                segments.append([ev])
        out = []
        sent = after_seq
        for seg in segments:
            msg, state = self._commit(book, pt, state, seg, kinds, results, texts)
            out.extend(results.get(commit_key(seg[0]["idempotencyKey"]), {}).get("before", []))  # B-9: ending_started
            out.append(msg)
            sent = seg[-1]["seq"]
        return out, sent

    def _commit(
        self,
        book: Book,
        pt: Pt,
        before: SimState,
        seg: Sequence[Json],
        kinds: dict[str, str],
        results: dict[str, Json],
        texts: dict[str, str | None] | None = None,
    ) -> tuple[Json, SimState]:
        state = before
        visible = []
        # An act change is written in one turn; steps 2〜4 are in the same run.
        # 幕の切り替わりは 1 ターンで書かれ、第 2〜4 段階は同じ一続きに入る。
        away = Away()
        for ev in seg:
            if not away(ev) and is_visible(book, ev, state["vars"]["var.player.location"]):
                visible.append(visible_event(book, ev, pt.role_id))
            state = apply(book.world, state, ev)
        from_seq = seg[0]["seq"]
        key = commit_key(seg[0]["idempotencyKey"])
        # Characters are placed by the location points currently recorded on the playthrough; for the player's spot
        # see the module docstring.
        # 登場人物の立ち位置はプレイにいま記録されている位置点で決める。プレイヤーの spot はモジュールの説明を参照。
        snap_before = with_locations(
            snapshot(book, pt.pid, pt.role_id, pt.status, before, from_seq - 1, pt.run), before
        )
        snap_after = with_locations(snapshot(book, pt.pid, pt.role_id, pt.status, state, seg[-1]["seq"], pt.run), state)
        diff = patch(snap_before, snap_after)
        player = diff.pop("player", {})
        # move and go carry no spot (on receiving a spot the frontend places the player there directly).
        # move、go には spot を付けない（spot を受け取るとフロントエンドはプレイヤーをそこへ直接置く）。
        if kinds.get(key) == "action":
            player.pop("spot", None)
        spot = results.get(key, {}).get("playerSpot")
        if spot is not None:
            player["spot"] = spot
        if player:
            diff["player"] = player
        msg: Json = {
            "type": "commit",
            "fromSeq": from_seq,
            "seq": seg[-1]["seq"],
            "events": visible,
            "patch": diff,
            "memories": memory_changes(results.get(key, {}), texts or {}),
            "promises": promise_changes(seg, state),
            "narration": [],
            "cue": None,
            "reveal": None,
        }
        if kinds.get(key) == "talk":
            msg["turnId"] = key
        # B-16: a director event in front of the player, one line of 地の文.
        # B-16：プレイヤーの前での演出イベント、地の文 1 行。
        if kinds.get(key) == "world":
            msg["narration"] = list(results.get(key, {}).get("narration", []))
        if kinds.get(key) == "confirm":
            done = results.get(key, {})
            if done.get("turnId"):
                msg["turnId"] = done["turnId"]
            msg["narration"] = list(done.get("narration", []))
        return msg, state

    async def visible_events(self, pid: str, after_seq: int, limit: int) -> list[Json]:
        """2.4: events visible to the player. Ones that only change the time, happen without the player or were vetoed
        take a seq but aren't here.

        2.4：プレイヤーに見えるイベント。時刻だけを変えるもの、プレイヤーがその場にいないもの、却下されたものは seq を
        占めるがここには入らない。
        """
        async with self.engine.connect() as c:
            pt = await self.pt(c, pid)
            if pt is None:
                return []
            log_ = await store.event_log(c, pid, pt.book.version)
        return visible_events(pt.book, pt.role_id, log_, after_seq, limit)

    async def log(self, pid: str) -> tuple[Any, list[Json]] | None:
        """This playthrough (`pt`) and its event log; the timeline and 「なぜ」 are computed from the log on the fly
        (2.5, 2.6).

        このプレイ（`pt`）とそのイベントログ。タイムラインと「なぜ」はログからその場で計算する（2.5、2.6）。
        """
        async with self.engine.connect() as c:
            pt = await self.pt(c, pid)
            if pt is None:
                return None
            return pt, await store.event_log(c, pid, pt.book.version)

    async def on_commit(self, payload: Json) -> None:
        """The NOTIFY after a narrator commit (forwarded by hub.py): push if this playthrough has an open connection.

        ナレーターの commit 後の NOTIFY（hub.py から転送）：このプレイに開いている接続があればプッシュする。
        """
        conn = self.conns.get(payload["pid"])
        if conn is not None:
            await conn.on_commit(payload)

    # —— Narrator / ナレーター ——

    def kick(self, pid: str) -> None:
        """Ask the narrator to process this playthrough's queued tasks (without waiting). Failed tasks stay queued and
        are retried on the next call.

        このプレイの待ち行列のタスクをナレーターに処理させる（待たない）。失敗したタスクは待ち行列に残り、次の呼び出しで
        再試行される。
        """
        self.spawn(self._kick(pid))

    async def _kick(self, pid: str) -> None:
        try:
            await self.narrator.run(pid)
        except Exception:
            log.exception("Calling the narrator failed (%s) / ナレーターの呼び出しに失敗", pid)

    def spawn(self, coro: Awaitable[Any]) -> asyncio.Task[Any]:
        task: asyncio.Task[Any] = asyncio.ensure_future(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    def hand(self, pid: str, coro: Awaitable[Any]) -> asyncio.Task[Any]:
        """Hand a turn to the narrator (`_finish`), tracked per playthrough and removed once written.

        ターンをナレーターに渡し（`_finish`）、プレイごとに記録して、書き終えたら外す。
        """
        task = self.spawn(coro)
        mine = self.handing.setdefault(pid, set())
        mine.add(task)

        def done(t: asyncio.Task[Any]) -> None:
            mine.discard(t)
            if not mine and self.handing.get(pid) is mine:
                del self.handing[pid]

        task.add_done_callback(done)
        return task

    async def handed(self, pid: str) -> None:
        """Wait up to `HANDOFF_WAIT_S` seconds for this playthrough's turns still being handed over to be written.
        On a quick reconnect the turn cut off on the old connection may not be written yet, so the lastTurn that hello
        computes would be one turn behind, the frontend would resend by the rules and the character would answer twice
        (#100 review).

        このプレイでまだ渡している最中のターンが書き終わるのを最大 `HANDOFF_WAIT_S` 秒待つ。素早く再接続すると古い接続で
        切れたターンがまだ書かれておらず、hello が計算する lastTurn が 1 ターン遅れ、フロントエンドが規則どおり再送して
        登場人物が 2 回答えてしまう（#100 のレビュー）。
        """
        pending = self.handing.get(pid)
        if pending:
            _, late = await asyncio.wait(set(pending), timeout=HANDOFF_WAIT_S)
            if late:
                log.warning(
                    "%d turn(s) still not handed over at reconnect (%s) / 再接続時に未提出のターンあり", len(late), pid
                )

    # —— Shutdown / シャットダウン ——

    async def goaway(self, reconnect_after_ms: int = 1000) -> None:
        """On SIGTERM: push goaway to every connection first, then close it with 1012 (section 4).

        SIGTERM を受けたら：各接続にまず goaway を送り、それから 1012 で閉じる（第 4 節）。
        """
        self.draining = True
        conns = list(self.conns.values())
        for conn in conns:
            await conn.send({"type": "goaway", "reason": "deploy", "reconnectAfterMs": reconnect_after_ms})
        for conn in conns:
            await conn.close(1012, "service restart")
        # After moving to another instance, sessions are rebuilt from the situation description (B-11).
        # 別のインスタンスに移ったら状況の説明から作り直す（B-11）。
        for pid in list(self.parked):
            await self.forget(pid)

    async def forget(self, pid: str) -> None:
        """Drop this playthrough's parked session and recent conversation (B-11): called on deleting the playthrough,
        on a 記憶帳 deletion (B-13) and at shutdown.

        このプレイの預けたセッションと直近の会話を捨てる（B-11）：プレイの削除、記憶帳での削除（B-13）、シャットダウンの
        ときに呼ぶ。
        """
        p = self.parked.pop(pid, None)
        if p is not None:
            await p.drop()
