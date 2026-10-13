"""Live sessions on one connection (B-10, backend-design 3.2): warm-up, switching, periodic rebuilds, GoAway, dropping
mid-way, mid-session situation updates, idle closing, cost. `ws.py` only calls into here; sessions live in
`Conn.sessions` (B-4's retraction, intent confirmation and landing look at it too).

- `near`: warm up after a 2-second debounce (no message pushed). At most 1 focused + 1 warmed session per connection;
  warming someone else closes the old warmed one.
- `far`: cancel a warm-up that hasn't started.
- `focus`: session present and alive: ready as before; being opened or missing: `session_preparing { switch }`, then
  `session_ready` once open.
- Periodic rebuild: after the Nth turn (`ZJ_LIVE_REBUILD_TURNS`, 7〜10, default 8), open a new session in the
  background at a pause, swap it in and close the old one. No message pushed.
- GoAway: same as above, started immediately.
- Dropped mid-way: that turn is closed out as interrupted (`ws.py`); then reopen with `session_preparing { rebuild }`
  (not pushed if the player isn't looking at that character).
- Fails to open: 2 times in a row (or quota, or the ledger at its cap): `degraded { voice: false }`; this connection
  keeps voice off for now and tries again on the next `focus`.
- Budget, daily, switch (B-14): `degraded { budget / daily / service }`; `focus` opens no session and characters answer
  in text.
- 5 minutes left (B-14): push `limits` once when today's voice time has 5 minutes left (once per connection).
- Narrator committed: if the situation changed in an open session, `note()` sends the changed entries; not during a
  turn in which someone is speaking, but after that turn is handed over.
- Idle: close 2 minutes after leaving the character (shortened by `ZJ_SPEED`; not closed at speed 0; tests set it
  separately).
- Disconnect (B-11): sessions, recent conversation and the monitor are parked in `Gateway.parked`; a character cut off
  mid-sentence is closed. Sessions are dropped after 30 seconds and the rest after 10 minutes if no one takes them over.
- Reconnecting `hello`: takes over what was parked: sessions are put back (a new `focus` is ready immediately), recent
  conversation and the monitor carry on; if the situation changed, a description is sent.

"Pause" = the character has no turn not yet handed over (`Turn.submitted`). Swapping sessions always waits for a pause;
if another turn is spoken while the new session is opening, the new session lacks that turn, so it is dropped and
reopened.

1 本の接続上の Live セッション（B-10、backend-design 3.2）：ウォームアップ、切り替え、定期的な作り直し、GoAway、
途中の切断、途中の状況更新、アイドル時のクローズ、費用。`ws.py` はここを呼ぶだけ。セッションは `Conn.sessions`
に置く（B-4 の取り消し、意図の確認、着地もこれを見る）。

- `near`：2 秒のデバウンス後にウォームアップ（メッセージは送らない）。1 本の接続で focus 中 1 つ＋
  ウォームアップ 1 つまで。別の人をウォームアップするときは古いウォームアップを閉じる。
- `far`：まだ始まっていないウォームアップを取り消す。
- `focus`：セッションがあって生きている：そのまま準備完了。開いている最中かない：`session_preparing { switch }`、
  開いたら `session_ready` を送る。
- 定期的な作り直し：第 N ターン（`ZJ_LIVE_REBUILD_TURNS`、7〜10、既定 8）を終えたら、間（ま）のところで裏で新しい
  セッションを開き、入れ替えて古いものを閉じる。メッセージは送らない。
- GoAway：同上、すぐに始める。
- 途中で切れた：そのターンは割り込まれたものとして締める（`ws.py`）。それから `session_preparing { rebuild }`
  で開き直す（プレイヤーがその人を見ていなければ送らない）。
- 開けない：2 回続けて（またはクォータ、台帳が上限）：`degraded { voice: false }`。この接続ではひとまず音声を使わず、
  次の `focus` でもう一度試す。
- 予算、1 日の上限、スイッチ（B-14）：`degraded { budget / daily / service }`。`focus` はセッションを開かず、
  登場人物は文字で答える。
- 残り 5 分（B-14）：今日の音声時間が残り 5 分になったら `limits` を 1 回送る（接続ごとに 1 回）。
- ナレーターが commit した：開いているセッションで状況が変わったら `note()` で変わった項目を送る。
  話している最中のターンでは送らず、そのターンが渡されるのを待つ。
- アイドル：登場人物から離れて 2 分で閉じる（`ZJ_SPEED` で短縮。速度 0 なら閉じない。テストは別に設定）。
- 切断（B-11）：セッション、直近の会話、モニターを `Gateway.parked` に預ける。話の途中の登場人物は閉じる。
  誰も引き継がなければセッションは 30 秒、そのほかは 10 分で捨てる。
- 再接続の `hello`：預けたものを引き継ぐ：セッションを戻し（あらためて `focus` すればすぐ準備完了）、
  直近の会話とモニターはそのまま使う。状況が変わっていれば説明を送る。

「間（ま）」= その登場人物にまだ渡していないターン（`Turn.submitted`）がないこと。セッションの入れ替えは常に間を待つ。
新しいセッションを開いている間にまた 1 ターン話されたら、新しいセッションにはそのターンがないので、捨てて開き直す。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sqlalchemy import update

from zoujin_backend import audio, budget
from zoujin_backend.db import store
from zoujin_backend.db.tables import playthrough_metrics
from zoujin_backend.gateway import brief
from zoujin_backend.models.gemini_live import LiveLostQuota
from zoujin_backend.models.live import LiveEvent, LiveLost, LiveSession, Recent
from zoujin_backend.narrator import memory
from zoujin_backend.voice.models import live_cost_parts

if TYPE_CHECKING:
    from zoujin_backend.gateway.monitor import Monitor
    from zoujin_backend.gateway.ws import Conn, Turn

log = logging.getLogger("zoujin.gateway")

Json = Any

# Warm-up, switching characters, rebuilding a session (the example in api-contract 3.5).
# ウォームアップ、登場人物の切り替え、セッションの作り直し（api-contract 3.5 の例）。
SESSION_ETA_MS = 800
WARM_DEBOUNCE_S = 2.0  # server-side debounce for near (3.2) / near のサーバー側デバウンス（3.2）
IDLE_S = 120.0  # close 2 minutes after leaving the character (ux-design 7.2) / 離れて 2 分で閉じる（ux-design 7.2）
MAX_OPEN_FAILS = 2
# Another turn was spoken while a new session was opening: drop and reopen, at most this many times.
# 新しいセッションを開いている間にまた 1 ターン話された：捨てて開き直す。その最大回数。
SWAP_RETRIES = 3
# Estimate for the next turn (for the ledger-cap check, on the high side: about $0.029 per turn at 30 turns, S-073 ⑤).
# 次のターンの見込み（台帳の上限の判定用、高めに：30 ターンで 1 ターン約 0.029 ドル、S-073 ⑤）。
NEXT_TURN_USD = 0.03
# B-11: how long a session parked after a disconnect is kept (the frontend reconnects with 1, 2, 4, 8 s backoff,
# 15 s in total).
# B-11：切断後に預けたセッションを残す秒数（フロントエンドは 1、2、4、8 秒のバックオフで再接続、計 15 秒）。
RESUME_HOLD_S = 30.0
# B-11: how long recent conversation is kept after a disconnect (same as the lifetime of a single Live connection).
# B-11：切断後に直近の会話を残す秒数（Live の 1 接続の寿命と同じ）。
RECENT_HOLD_S = 600.0


@dataclass
class Parked:
    """Voice state parked after a disconnect (B-11), only in the gateway's memory. `recent` is the same object as the
    old connection's: the turn cut off by the disconnect still lands in it once handed over. `monitor` is also the
    old connection's (B-12: terms let slip, the consecutive-spoiler count, questions, the calming after an ambiguous
    line), kept 10 minutes like the recent conversation: after reconnecting, the new session's recent conversation
    still leaves out the lines that let something slip, and the corrective hints are still included.

    切断後に預けた音声まわりのもの（B-11）。ゲートウェイのメモリ内だけにある。`recent` は古い接続と同じもので、
    切断時のターンも渡し終えればいつもどおりここに入る。`monitor` も古い接続のもの（B-12：うっかり口にした語、
    続いたネタバレの回数、質問、どちらとも取れる発言のあとの和らげ）で、直近の会話と同じく 10 分残す：
    再接続後も新しいセッションの直近の会話からうっかり口にした発言を除き、訂正のヒントも付ける。
    """

    sessions: dict[str, LiveSession]
    recent: dict[str, list[tuple[str, Recent]]]
    facts: dict[str, tuple[str, ...]]
    at: float
    monitor: Monitor | None = None
    timer: asyncio.Task[None] | None = None

    async def close_sessions(self) -> None:
        sessions = list(self.sessions.values())
        self.sessions.clear()
        for s in sessions:
            await s.close()

    async def drop(self) -> None:
        if self.timer is not None and self.timer is not asyncio.current_task():
            self.timer.cancel()
        await self.close_sessions()
        self.recent.clear()
        self.facts.clear()
        self.monitor = None


@dataclass
class Voices:
    conn: Conn
    opening: dict[str, asyncio.Task[LiveSession]] = field(default_factory=dict)
    swapping: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    # Situation entries last sent into this character's session. / この登場人物のセッションに前回送った状況の項目。
    facts: dict[str, tuple[str, ...]] = field(default_factory=dict)
    # The situation changed but hasn't been sent yet (during a speaking turn).
    # 状況が変わったがまだ送っていない（話している最中のターン）。
    stale: set[str] = field(default_factory=set)
    warm_task: asyncio.Task[None] | None = None
    warm_for: str | None = None
    idle: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    fails: int = 0
    # B-11: time of the hello; the first ready after focusing again records gateway.resume_ready.
    # B-11：hello の時刻。あらためて focus した後の最初の準備完了で gateway.resume_ready を記録する。
    resumed_at: float | None = None
    # B-11: this connection has already parked (on 4009 it parks first and doesn't park again on disconnect).
    # B-11：この接続はすでに預けた（4009 のときは先に預け、切断時にはもう預けない）。
    parked_once: bool = False
    # Reason for degrading (service / budget / daily); if Live fails to open, the next focus tries again.
    # 縮退の理由（service / budget / daily）。Live が開けなかった場合は次の focus でもう一度試す。
    off: str | None = None
    # B-14: this connection has pushed the "5 minutes left today" limits.
    # B-14：この接続で「今日は残り 5 分」の limits を送った。
    warned: bool = False
    # B-14: the playthrough's budget tier when the session was last opened (economy tier has a shorter situation).
    # B-14：前回セッションを開いたときのこのプレイの予算モード（節約モードでは状況説明が短い）。
    tier: str = "normal"
    # None: computed from ZJ_SPEED; tests set it directly. / None：ZJ_SPEED から計算する。テストでは直接設定する。
    idle_s: float | None = None

    # —— Small helpers / 小道具 ——

    @property
    def sessions(self) -> dict[str, LiveSession]:
        return self.conn.sessions

    @property
    def speed(self) -> float:
        return self.conn.gw.settings.speed

    @property
    def rebuild_turns(self) -> int:
        return self.conn.gw.settings.live_rebuild_turns

    def busy(self, character: str) -> bool:
        """The character has a turn not yet handed over (pause = not busy).

        この登場人物にまだ渡していないターンがある（間 = busy でない）。
        """
        t = self.conn.turn
        return t is not None and t.character == character and not t.submitted.is_set()

    def _spawn(self, coro: Any) -> asyncio.Task[Any]:
        return self.conn.gw.spawn(coro)

    async def _brief(self, character: str) -> brief.Brief:
        gw, pid = self.conn.gw, self.conn.pid
        async with gw.engine.connect() as c:
            pt = await gw.pt(c, pid)
            st = await store.sim_state(c, pid)
            self.tier = await budget.tier_of(c, pid)
            # Memories 8 → 4 in economy tier (B-14). / 節約モードでは記憶 8 → 4（B-14）。
            limit = budget.policy(self.tier).memory_inject
            remembered = await memory.memories_for_brief(c, pid, character, limit)
            if pt is None or st is None:
                raise LiveLost("The playthrough has no state / このプレイには状態がない")
            forgotten = await memory.forgotten_facts(c, pt.book, pid, character)
        pol = budget.policy(self.tier)
        return brief.build(
            pt.book,
            st,
            character,
            self._recent(character),
            self.conn.monitor.notes(character),
            remembered,
            forgotten,
            samples=pol.brief_samples,
        )

    def _recent(self, character: str) -> list[Recent]:
        """Recent conversation carried into the session: lines that let a spoiler slip are left out (B-12, UX's #112
        review: otherwise the new session would see the term again right at the start).

        セッションに持ち込む直近の会話：ネタバレをうっかり口にした発言は入れない（B-12、UX の #112 のレビュー：
        新しいセッションの冒頭でまたその語を目にしてしまう）。
        """
        terms = self.conn.monitor.terms(character)
        kept = [r for _, r in self.conn.recent.get(character, []) if not any(x in (r.reply or "") for x in terms)]
        # Fewer turns in economy tier (B-14). / 節約モードでは持ち込むターンを減らす（B-14）。
        return kept[-budget.policy(self.tier).recent_turns :]

    # —— Opening sessions / セッションを開く ——

    async def _open(self, character: str, reason: str) -> LiveSession:
        """Assemble the system instructions, open the session and attach the change callback. Trace: live.session
        (without the instruction text).

        システム指示を組み立て、セッションを開き、変化のコールバックを付ける。Trace：live.session（指示の文は含めな
        い）。
        """
        b = await self._brief(character)
        recent = self._recent(character)
        with self.conn.gw.tracer.span(
            "live.session",
            playthrough_id=self.conn.pid,
            character=character,
            reason=reason,
            prompt_version=brief.version(),
            prompt_chars=len(b.system),
        ) as sp:
            try:
                s = await self.conn.gw.live.open(character, recent, b.system)
            except Exception:
                sp.set(status="failed")
                raise
            sp.set(status="ok")
        self.facts[character] = b.facts
        self.stale.discard(character)
        s.on_change = lambda: self._changed(character, s)
        return s

    def _ensure(self, character: str, reason: str) -> asyncio.Task[LiveSession]:
        """Use the one being opened if there is one; otherwise open one. Once open it goes into sessions (the old
        session it replaces is closed).

        開いている最中のものがあればそれを使い、なければ開く。開いたら sessions に入れる（入れ替えた古いセッションは閉じ
        る）。
        """
        task = self.opening.get(character)
        if task is not None and not task.done():
            return task

        async def run() -> LiveSession:
            s = await self._open(character, reason)
            # The connection dropped while opening: leave no orphaned session (before B-11 everything was closed on
            # disconnect).
            # 開いている間に接続が切れた：誰も管理しないセッションを残さない（B-11 以前は切断ですべて閉じていた）。
            if self.conn.closed.is_set():
                await s.close()
                raise LiveLost("The connection is already closed / 接続はすでに切れている")
            old = self.sessions.get(character)
            self.sessions[character] = s
            if old is not None and old is not s:
                await old.close()
            return s

        task = asyncio.ensure_future(run())
        self.opening[character] = task

        def forget(done: asyncio.Task[LiveSession]) -> None:
            if self.opening.get(character) is done:
                self.opening.pop(character, None)

        task.add_done_callback(forget)
        return task

    async def prepare(self, character: str, reason: str, *, announce: bool = True) -> None:
        """Open a session and push preparing and ready (switching characters, rebuilding after a retraction, dropped
        mid-way). A new turn waits for `ready` before being sent in (ws._stream).

        セッションを開き、準備中と準備完了を送る（登場人物の切り替え、取り消し後の作り直し、途中の切断）。
        新しいターンは `ready` を待ってから送り込む（ws._stream）。
        """
        conn = self.conn
        if announce:
            await conn.send(
                {"type": "session_preparing", "character": character, "reason": reason, "etaMs": SESSION_ETA_MS}
            )
        start = time.monotonic()
        conn.ready_at[character] = start + SESSION_ETA_MS / 1000 * self.speed
        ev = conn.ready[character] = asyncio.Event()

        async def ready() -> None:
            try:
                ok = await self._try_open(character, reason)
                await asyncio.sleep(max(0.0, conn.ready_at[character] - time.monotonic()))
                if ok and conn.focused == character and (announce or reason in ("switch", "reconnect")):
                    await conn.send({"type": "session_ready", "character": character, "voiceAvailable": True})
                    self._resume_ready(reused=False)
                    # The session just became ready: also give suggested lines once (B-21).
                    # セッションが準備完了になったところ：候補のセリフも 1 回出す（B-21）。
                    if reason in ("switch", "reconnect"):
                        conn.suggest_later(character)
            finally:
                ev.set()

        self._spawn(ready())

    async def _try_open(self, character: str, reason: str) -> bool:
        """Open once, and try once more on failure; degrade on reaching the consecutive-failure limit or the quota.

        1 回開き、失敗したらもう 1 回試す。連続失敗が上限に達するかクォータなら縮退する。
        """
        for _ in range(MAX_OPEN_FAILS):
            try:
                await self._ensure(character, reason)
            except LiveLostQuota:
                await self.degrade("service")
                return False
            except (LiveLost, OSError) as e:
                self.fails += 1
                log.info(
                    "Opening %s's session failed (attempt %d, %s) / セッションを開けなかった",
                    character,
                    self.fails,
                    type(e).__name__,
                )
                if self.fails >= MAX_OPEN_FAILS:
                    await self.degrade("service")
                    return False
                continue
            self.fails = 0
            return True
        return False

    async def degrade(self, why: str) -> None:
        """Push `degraded` (only once per reason); after that characters answer in text (`ws.py`). The playthrough's
        first degrade is recorded in `playthrough_metrics` (B-14). Degrading for budget, daily or the switch (which
        won't recover on its own) closes the sessions that aren't speaking.

        `degraded` を送る（同じ理由では 1 回だけ）。以後、登場人物は文字で答える（`ws.py`）。このプレイで最初の縮退は
        `playthrough_metrics` に記録する（B-14）。予算、1 日の上限、スイッチによる縮退（自然には戻らない）では、
        話していないセッションを閉じる。
        """
        if self.off == why:
            return
        self.off = why
        conn = self.conn
        async with conn.gw.engine.begin() as c:
            await budget.mark_degraded(c, conn.pid, why)
        with conn.gw.tracer.span("gateway.degraded", playthrough_id=conn.pid, reason=why):
            pass
        await conn.send({"type": "degraded", "voice": False, "reason": why})
        if conn.focused is not None:
            await conn.send({"type": "session_ready", "character": conn.focused, "voiceAvailable": False})
        if why != "service" or not await conn.gw.voice_on():
            for who, sess in list(self.sessions.items()):
                if not self.busy(who):
                    self.sessions.pop(who, None)
                    await sess.close()

    async def settle(self) -> None:
        """On hello: if voice is already unavailable (B-14), record the reason without pushing `degraded`
        (`welcome.voice.degraded` already says so).

        hello のとき：すでに音声が使えない場合（B-14）は理由を記録し、`degraded` は送らない（`welcome.voice.degraded`
        がすでに伝えている）。
        """
        why = await self.blocked()
        if why is not None:
            self.off = why
            async with self.conn.gw.engine.begin() as c:
                await budget.mark_degraded(c, self.conn.pid, why)

    async def blocked(self) -> str | None:
        """Budget, daily, the global switch (B-14): why voice can't be opened now; see `Gateway.voice_block`.

        予算、1 日の上限、全体のスイッチ（B-14）：いま音声を開けない理由。`Gateway.voice_block` を参照。
        """
        return await self.conn.gw.voice_block(self.conn.pid, self.conn.user_id)

    async def open_now(self, character: str, reason: str) -> LiveSession | None:
        """Speaking first on landing (B-3): no preparing pushed, just open it.

        着地で先に話し出す（B-3）：準備中は送らず、そのまま開く。
        """
        if not await self._try_open(character, reason):
            return None
        self.conn.ready_at[character] = time.monotonic()
        return self.sessions.get(character)

    # —— near / far / focus from the frontend / フロントエンドの near / far / focus ——

    def near(self, character: str) -> None:
        conn = self.conn
        if not conn.characters.get(character, {}).get("talkable") or self.off:
            return
        s = self.sessions.get(character)
        if (s is not None and s.alive) or character in self.opening:
            return
        if self.warm_task is not None and not self.warm_task.done():
            self.warm_task.cancel()
        self.warm_for = character

        async def warm() -> None:
            await asyncio.sleep(WARM_DEBOUNCE_S * self.speed)
            # Warming someone else: close the old warm-up (not focused and not speaking); at most 1 focused + 1 warmed.
            # 別の人のウォームアップ：古いウォームアップ（focus 中でも話し中でもないもの）を閉じる。focus 1
            # つ＋ウォームアップ 1 つまで。
            for other, sess in list(self.sessions.items()):
                if other not in (character, conn.focused) and not self.busy(other):
                    self.sessions.pop(other, None)
                    await sess.close()
            s = self.sessions.get(character)
            # Already opened during the debounce (it was focused). / デバウンス中にすでに開いた（focus された）。
            if (s is not None and s.alive) or character in self.opening:
                return
            conn.ready_at[character] = time.monotonic() + SESSION_ETA_MS / 1000 * self.speed
            with contextlib.suppress(LiveLost, OSError):
                await self._ensure(character, "warm")

        self.warm_task = self._spawn(warm())

    def far(self, character: str) -> None:
        if self.warm_for == character and self.warm_task is not None and not self.warm_task.done():
            self.warm_task.cancel()
            self.warm_for = None

    async def focus(self, character: str) -> None:
        conn = self.conn
        prev = conn.focused
        conn.focused = character
        self._cancel_idle(character)
        if prev is not None and prev != character:
            self._schedule_idle(prev)
        why = await self.blocked()
        # Won't recover on its own: no session; characters answer in text (B-14).
        # 自然には戻らない：セッションを開かず、登場人物は文字で答える（B-14）。
        if why is not None:
            if self.off == why:
                await conn.send({"type": "session_ready", "character": character, "voiceAvailable": False})
            else:
                await self.degrade(why)
            return
        if self.off is not None:
            self.off = None  # try again / もう一度試す
            self.fails = 0
        if self.warm_for == character and self.warm_task is not None and not self.warm_task.done():
            # The character was tapped before the debounce ended: don't wait, open it below right away (#111 frontend
            # review).
            # デバウンスが終わる前に登場人物を押した：待たずに下ですぐ開く（#111 フロントエンドのレビュー）。
            self.warm_task.cancel()
            self.warm_for = None
        s = self.sessions.get(character)
        if s is not None and s.alive and character not in self.opening:

            async def ready() -> None:
                await asyncio.sleep(max(0.0, conn.ready_at.get(character, 0.0) - time.monotonic()))
                if conn.focused == character:
                    await conn.send({"type": "session_ready", "character": character, "voiceAvailable": True})
                    self._resume_ready(reused=True)
                    # Warm-up hit or resumed play: also give suggested lines once (B-21).
                    # ウォームアップが当たった、続きから遊ぶ：候補のセリフも 1 回出す（B-21）。
                    conn.suggest_later(character)

            self._spawn(ready())
            return
        # First focus after reconnecting with the session already gone: reason is reconnect (contract 3.3).
        # 再接続後の最初の focus でセッションがすでにない：reason は reconnect（契約 3.3）。
        await self.prepare(character, "reconnect" if self.resumed_at is not None else "switch")

    def unfocus(self) -> None:
        if self.conn.focused is not None:
            self._schedule_idle(self.conn.focused)
        self.conn.focused = None

    # —— Idle / アイドル ——

    def _idle_seconds(self) -> float | None:
        if self.idle_s is not None:
            return self.idle_s
        return IDLE_S * self.speed if self.speed > 0 else None

    def _schedule_idle(self, character: str) -> None:
        secs = self._idle_seconds()
        if secs is None:
            return
        self._cancel_idle(character)

        async def close_later() -> None:
            await asyncio.sleep(secs)
            if self.conn.focused == character or self.busy(character) or self.warm_for == character:
                return
            s = self.sessions.pop(character, None)
            if s is not None:
                log.info("%s idle, closing the session / アイドルのためセッションを閉じる", character)
                await s.close()

        self.idle[character] = self._spawn(close_later())

    def _cancel_idle(self, character: str) -> None:
        task = self.idle.pop(character, None)
        if task is not None:
            task.cancel()

    # —— Rebuild after retraction (B-4), periodic rebuild, GoAway, dropped mid-way ——
    # —— 取り消し後の作り直し（B-4）、定期的な作り直し、GoAway、途中の切断 ——

    async def rebuild(self, character: str) -> None:
        """After a retraction: close the old one, open a new one (without that turn), push preparing and ready.

        取り消しの後：古いものを閉じ、新しいもの（そのターンを含まない）を開き、準備中と準備完了を送る。
        """
        task = self.swapping.pop(character, None)
        if task is not None:
            task.cancel()
        old = self.sessions.pop(character, None)
        if old is not None:
            await old.close()
        await self.prepare(character, "rebuild")

    def _changed(self, character: str, s: LiveSession) -> None:
        """Called by the session: GoAway or dropped. During a speaking turn do nothing yet; wait until the turn is
        handed over (after_turn).

        セッションから呼ばれた：GoAway または切断。話している最中のターンではまだ何もせず、そのターンが渡されるのを待つ
        （after_turn）。
        """
        if self.sessions.get(character) is not s or self.busy(character):
            return
        self.after_turn(character)

    def after_turn(self, character: str) -> None:
        """The character's turn was handed over (a pause): send the pending situation update; reopen if the session
        dropped, swap if the turn count is reached or on GoAway.

        この登場人物のターンが渡された（間）：ためていた状況の更新を送る。セッションが切れていれば開き直し、
        ターン数に達したか GoAway なら入れ替える。
        """
        s = self.sessions.get(character)
        if s is None or character in self.opening or self.conn.closed.is_set():
            return
        if not s.alive:
            self.sessions.pop(character, None)
            self._spawn(self.prepare(character, "rebuild", announce=self.conn.focused == character))
            return
        if character in self.stale:
            self._spawn(self._note(character))
        if (s.going_away or s.turns >= self.rebuild_turns) and character not in self.swapping:
            self.swapping[character] = self._spawn(self._swap(character, "goaway" if s.going_away else "turns"))

    async def _swap(self, character: str, reason: str) -> None:
        """Open the new session first, then close the old one, without the player noticing (no message pushed). If
        another turn is spoken while opening, the new session lacks that turn: drop it and reopen.

        先に新しいセッションを開いてから古いものを閉じ、プレイヤーに気づかせない（メッセージは送らない）。
        開いている間にまた 1 ターン話されたら、新しいセッションにはそのターンがないので、捨てて開き直す。
        """
        try:
            for _ in range(SWAP_RETRIES):
                old = self.sessions.get(character)
                if old is None:
                    return
                before = old.turns
                try:
                    new = await self._open(character, f"rebuild_{reason}")
                except (LiveLost, OSError) as e:
                    log.info(
                        "Swapping %s's session failed to open (%s); retrying at the next pause / 次の間で再試行",
                        character,
                        type(e).__name__,
                    )
                    return
                while self.busy(character):
                    t = self.conn.turn
                    assert t is not None
                    await t.submitted.wait()
                # Meanwhile it was rebuilt after a retraction, or disconnected. / その間に取り消しで作り直された、
                # または切断された。
                if self.sessions.get(character) is not old or self.conn.closed.is_set():
                    await new.close()
                    return
                if old.turns != before and old.alive:
                    await new.close()
                    continue
                self.sessions[character] = new
                self.conn.ready_at[character] = time.monotonic()
                await old.close()
                return
        finally:
            if self.swapping.get(character) is asyncio.current_task():
                self.swapping.pop(character, None)

    # —— Mid-session situation updates / 途中の状況更新 ——

    async def refresh(self) -> None:
        """The narrator committed: for every open session whose situation changed, send the changed entries; a speaking
        one can't take it, so note it and wait until that turn is handed over.

        ナレーターが commit した：開いているセッションごとに、状況が変わっていれば変わった項目を送る。
        話している最中のものには送れないので、記録してそのターンが渡されるのを待つ。
        """
        for character, s in list(self.sessions.items()):
            if not s.alive:
                continue
            if self.busy(character):
                self.stale.add(character)
                continue
            await self._note(character)

    async def _note(self, character: str) -> None:
        s = self.sessions.get(character)
        if s is None or not s.alive:
            return
        try:
            b = await self._brief(character)
        except LiveLost:
            return
        self.stale.discard(character)
        msg = brief.changes(self.facts.get(character, ()), b.facts)
        self.facts[character] = b.facts
        if msg is None:
            return
        await s.note(msg)
        with self.conn.gw.tracer.span(
            "live.note", playthrough_id=self.conn.pid, character=character, notes=msg.count("\n")
        ):
            pass

    # —— Cost / 費用 ——

    async def can_speak(self) -> bool:
        """Whether this turn can use voice: degrade when the ledger is at its cap (during development), the playthrough
        hit its spending cap, today's voice time is used up or the global switch is off (B-14), and this turn
        doesn't use Live (a text turn gets a text answer, `ws.py`).

        このターンで音声を使えるか：台帳が上限（開発中）、プレイの支出が上限、今日の音声時間を使い切った、
        全体のスイッチがオフ（B-14）のどれかなら縮退し、このターンは Live を使わない（文字のターンは文字で答える、
        `ws.py`）。
        """
        ledger = self.conn.gw.live_ledger
        if ledger is not None:
            try:
                ledger.before(NEXT_TURN_USD)
            except Exception:  # noqa: BLE001 - BudgetStop
                await self.degrade("budget")
                return False
        why = await self.blocked()
        if why is not None:
            await self.degrade(why)
            return False
        return self.off is None

    async def account(self, t: Turn, ev: LiveEvent, session: LiveSession, before_s: float) -> None:
        """A turn's cost: the ledger (with real Live), `cost_live_usd`, and Trace's live.turn (without the words said).
        The ledger's usage also carries the input and output micro-dollars and "usage missing, recorded as an
        estimate" (S-090 reconciliation compares only input, and skips estimates).

        1 ターンの費用：台帳（本物の Live のとき）、`cost_live_usd`、Trace の live.turn（発言そのものは含めない）。
        台帳の usage には入力・出力それぞれのマイクロドルと「使用量が届かず推計で記録」も付ける（S-090
        の照合は入力だけを比べ、推計のものは比べない）。
        """
        conn = self.conn
        usage = dict(ev.usage or {})
        estimated = not usage
        in_usd, out_usd = live_cost_parts(usage)
        first_ms = -1 if t.first_audio is None or t.released is None else round((t.first_audio - t.released) * 1000)
        reply_s = max(0.0, session.audio_seconds - before_s)
        if conn.gw.live_ledger is not None:
            extra = {
                "sessionTurn": session.turns,
                "sessionAudioMsBefore": round(before_s * 1000),
                "replyAudioMs": round(reply_s * 1000),
                "firstAudioMs": first_ms,
                "inputMicroUsd": round(in_usd * 1_000_000),
                "outputMicroUsd": round(out_usd * 1_000_000),
                "usageEstimated": int(estimated),
            }
            conn.gw.live_ledger.add(
                kind=f"live.turn/{conn.pid}", model=conn.gw.live_model_name, usage=usage | extra, cost=ev.usd
            )
        if ev.usd:
            async with conn.gw.engine.begin() as c:
                m = playthrough_metrics.c
                await c.execute(
                    update(playthrough_metrics)
                    .where(m.playthrough_id == conn.pid)
                    .values(cost_live_usd=m.cost_live_usd + ev.usd)
                )
        out_s = min(reply_s, len(t.pcm_out) / 2 / audio.RATE)
        # Doesn't block the turn's wrap-up (the timing of retraction and the commit window stays the same).
        # このターンの締めくくりを妨げない（取り消しと提出の時間枠のタイミングは変わらない）。
        self._spawn(self._voice_seconds(reply_s, out_s))
        with conn.gw.tracer.span(
            "live.turn",
            playthrough_id=conn.pid,
            turn_id=t.turn_id,
            character=t.character,
            mode=t.mode,
            first_audio_ms=first_ms,
            audio_s=round(reply_s, 2),
            session_audio_s=round(before_s, 2),
            session_turn=session.turns,
            cost_usd=round(ev.usd, 6),
            tokens_in=usage.get("inputTokens", 0),
            tokens_out=usage.get("outputTokens", 0),
            usage_estimated=estimated,
            interrupted=t.stream is not None and t.stream.cancelled(),
            transcript_source=t.source,
        ):
            pass

    async def _voice_seconds(self, total_s: float, out_s: float) -> None:
        """Audio seconds in and out for this turn: the playthrough's voice_in/out_seconds and the account's voice time
        today (B-14, 60 minutes a day).

        このターンの入出力の音声秒数：このプレイの voice_in/out_seconds と、アカウントの今日の音声時間（B-14、1 日 60
        分）。
        """
        conn = self.conn
        async with conn.gw.engine.begin() as c:
            m = playthrough_metrics.c
            await c.execute(
                update(playthrough_metrics)
                .where(m.playthrough_id == conn.pid)
                .values(
                    voice_in_seconds=m.voice_in_seconds + round(total_s - out_s, 1),
                    voice_out_seconds=m.voice_out_seconds + round(out_s, 1),
                )
            )
            await budget.add_voice(c, conn.user_id, total_s)
            used = await budget.voice_seconds_today(c, conn.user_id)
        await self._warn(budget.minutes_left(used))

    async def _warn(self, left: int) -> None:
        """Push `limits` once when today's voice time has 5 minutes left (once per connection). Once used up, degrade
        before the next turn starts (`can_speak`).

        今日の音声時間が残り 5 分になったら `limits` を 1 回送る（接続ごとに 1 回）。使い切ったら次のターンが始まる前に
        縮退する（`can_speak`）。
        """
        if self.warned or left > budget.WARN_MINUTES or left <= 0:
            return
        self.warned = True
        await self.conn.send({"type": "limits", "voiceMinutesLeft": left})

    # —— Disconnect and reconnect (B-11) / 切断と再接続 ——

    def _hold(self, full: float) -> float:
        return full * self.speed if self.speed > 0 else full

    async def park(self) -> None:
        """The connection dropped (or was kicked out by a new connection to the same playthrough): park the live
        sessions, recent conversation and situation entries without closing the sessions. The session of the
        character cut off mid-sentence (`lost`) is closed: the character heard a turn the narrator never processed
        (like a retraction).

        接続が切れた（または同じプレイの新しい接続に追い出された）：生きているセッション、直近の会話、状況の項目を預け、
        セッションは閉じない。話の途中で切れた（`lost`）登場人物のセッションは閉じる：ナレーターが処理していないターンを
        登場人物が聞いてしまったため（取り消しと同じ）。
        """
        if self.parked_once:
            return
        self.parked_once = True
        conn, gw = self.conn, self.conn.gw
        self._cancel_tasks()
        t = conn.turn
        lost = {t.character} if t is not None and t.lost and t.character is not None else set()
        keep: dict[str, LiveSession] = {}
        shut: list[LiveSession] = []
        for character, s in self.sessions.items():
            if s.alive and character not in lost and not gw.draining:
                s.on_change = _ignore
                keep[character] = s
            else:
                shut.append(s)
        self.sessions.clear()
        # No await while parking: a new connection's hello can't slip in between and miss it.
        # 預ける処理では await しない：新しい接続の hello が途中に割り込んで取りそこねることがない。
        # What was parked last time was never taken over (shouldn't happen): drop it.
        # 前回預けたものを誰も引き継がなかった（本来ないはず）：捨てる。
        stale = gw.parked.pop(conn.pid, None)
        watched = bool(conn.monitor.chars) or conn.monitor.calming
        if not gw.draining and (keep or any(conn.recent.values()) or watched):
            p = Parked(keep, conn.recent, dict(self.facts), time.monotonic(), conn.monitor)
            gw.parked[conn.pid] = p
            p.timer = self._spawn(self._expire(p))
        for s in shut:
            await s.close()
        if stale is not None:
            await stale.drop()

    async def _expire(self, p: Parked) -> None:
        """Parked sessions are dropped after 30 seconds and recent conversation after 10 minutes if no one takes them
        over (shortened by ZJ_SPEED).

        預けたセッションは 30 秒、直近の会話は 10 分、誰も引き継がなければ捨てる（ZJ_SPEED で短縮）。
        """
        gw, pid = self.conn.gw, self.conn.pid
        hold = self._hold(RESUME_HOLD_S)
        await asyncio.sleep(hold)
        if gw.parked.get(pid) is not p:
            return
        await p.close_sessions()
        await asyncio.sleep(max(0.0, self._hold(RECENT_HOLD_S) - hold))
        if gw.parked.get(pid) is p:
            del gw.parked[pid]
            await p.drop()

    async def adopt(self) -> Parked | None:
        """Reconnecting hello: take over what this playthrough parked. Live sessions are put back (a new focus is ready
        immediately) and managed by the idle rules; if the situation changed during the disconnect, a description is
        sent. Returns what was taken over (for Trace), or None.

        再接続の hello：このプレイが預けたものを引き継ぐ。生きているセッションは戻し（あらためて focus
        すればすぐ準備完了）、アイドルの規則で管理する。切断中に状況が変わっていれば説明を送る。引き継いだもの（Trace
        用）を返し、なければ None。
        """
        conn, gw = self.conn, self.conn.gw
        p = gw.parked.pop(conn.pid, None)
        if p is None:
            return None
        if p.timer is not None:
            p.timer.cancel()
        conn.recent = p.recent
        self.facts.update(p.facts)
        if p.monitor is not None:
            conn.monitor = p.monitor
        now = time.monotonic()
        for character, s in list(p.sessions.items()):
            if not s.alive:
                p.sessions.pop(character)
                await s.close()
                continue
            conn.sessions[character] = s
            s.on_change = lambda c=character, s=s: self._changed(c, s)
            conn.ready_at[character] = now
            self._schedule_idle(character)
            if s.going_away:
                self.after_turn(character)
            else:
                self._spawn(self._note(character))
        return p

    def _resume_ready(self, *, reused: bool) -> None:
        """First ready after reconnecting: milliseconds from hello to session_ready (the server-side part, B-11).

        再接続後の最初の準備完了：hello から session_ready までのミリ秒（サーバー側の区間、B-11）。
        """
        if self.resumed_at is None:
            return
        ms = round((time.monotonic() - self.resumed_at) * 1000)
        self.resumed_at = None
        with self.conn.gw.tracer.span(
            "gateway.resume_ready", playthrough_id=self.conn.pid, duration_ms=ms, reused=reused
        ):
            pass

    def _cancel_tasks(self) -> None:
        for task in [*self.opening.values(), *self.swapping.values(), *self.idle.values()]:
            task.cancel()
        if self.warm_task is not None:
            self.warm_task.cancel()

    async def close_all(self) -> None:
        self._cancel_tasks()
        for s in list(self.sessions.values()):
            await s.close()
        self.sessions.clear()


def _ignore() -> None:
    """Called by a session while parked (GoAway, dropped): ignored; only sessions still alive at takeover are used.

    預けている間にセッションから呼ばれた（GoAway、切断）：何もしない。引き継ぐときに生きているものだけを使う。
    """
