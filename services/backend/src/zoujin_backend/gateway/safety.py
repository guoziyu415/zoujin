"""Safety screening in the gateway (B-12, api-contract 3.12, backend-design 5.5). `gateway/ws.py` calls into here in
only a few places.

- Screening starts as soon as the final of the player's line arrives (`text` for a text turn, Live's `input_final`
  for a voice turn) (`Guard.start`); the character answers as usual.
- Judged signal, or ambiguous for the second time in a playthrough: `Guard.pause`: stop forwarding the character's
  answer (no `interrupted`, no character final), push `turn_settled { outcome: "paused" }` and `safety_pause`; the
  turn is written as one row with `outcome: "paused"`, without the words said and without calling the narrator; a new
  turn the player is holding the talk button for is dropped entirely; every character session on this connection is
  closed; the playthrough records `paused` (`welcome.pending.safetyPause`).
- First ambiguous in a playthrough: push `safety_hint` (at most once per playthrough); the turn goes to the narrator
  as usual with the `ambiguous` flag (no events extracted).
- While paused, conversation, actions and end-of-act all get `invalid_request`; `focus` opens no session and returns no
  error; `safety_resume` → `safety_resumed`.
- The screening result is awaited before handing to the narrator (`Guard.result`), so nothing is committed and then
  paused.
- Verdicts are neither stored nor logged (S-057); `playthrough_metrics` records only counts.
- B-15: screening carries context (this turn's character, the player's location, the character's previous line in
  memory); the second ambiguous in a playthrough is first reviewed again (`Screener.second_look`), and if the review
  says it's in-story talk it isn't escalated. During the review, the character's audio and subtitles not yet sent are
  held back (`Turn.flowing`): dropped on pause, released otherwise.

ゲートウェイ内の安全チェック（B-12、api-contract 3.12、backend-design 5.5）。`gateway/ws.py` はわずかな箇所で
ここを呼ぶだけ。

- プレイヤーの発言の確定文が届いたらすぐ（文字のターンなら `text`、音声のターンなら Live の `input_final`）
  チェックを始め（`Guard.start`）、登場人物はいつもどおり答える。
- signal と判定、または同じプレイで 2 回目の ambiguous：`Guard.pause`：登場人物の答えの転送を止め（`interrupted`
  も登場人物の確定文も送らない）、`turn_settled { outcome: "paused" }` と `safety_pause` を送る。このターンは
  `outcome: "paused"` の 1 行として書き、発言そのものは書かず、ナレーターも呼ばない。プレイヤーがそのとき話すボタンを
  押している新しいターンは丸ごと捨てる。この接続上のすべての登場人物のセッションを閉じる。プレイには `paused` を
  記録する（`welcome.pending.safetyPause`）。
- プレイで 1 回目の ambiguous：`safety_hint` を送り（1 プレイに最大 1 回）、このターンは `ambiguous` の印を付けて
  いつもどおりナレーターに渡す（イベントは抽出しない）。
- 一時停止中は会話、アクション、幕末のどれにも `invalid_request` を返す。`focus` はセッションを開かず、エラーも
  返さない。`safety_resume` → `safety_resumed`。
- ナレーターに渡す前にチェックの結果を待つ（`Guard.result`）ので、commit してから一時停止することはない。
- 判定結果は保存もログもしない（S-057）。`playthrough_metrics` には回数だけを記録する。
- B-15：チェックには文脈を付ける（このターンの登場人物、プレイヤーのいる場所、その登場人物のメモリ上の直前の
  発言）。同じプレイで 2 回目の ambiguous はまず見直し（`Screener.second_look`）、物語の中の話だと判断されたら
  引き上げない。見直しの間、登場人物のまだ送っていない音声と字幕は止めておく（`Turn.flowing`）：一時停止なら捨て、
  そうでなければ流す。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update

from zoujin_backend.config import Settings
from zoujin_backend.db import store
from zoujin_backend.db.tables import turns
from zoujin_backend.models.armor import armor
from zoujin_backend.models.text import text_model
from zoujin_backend.safety import NOT_SCREENED, Context, SafetyState, Screen, Screener, counts_of, decide
from zoujin_backend.trace import Tracer
from zoujin_backend.world import Book

if TYPE_CHECKING:
    from zoujin_backend.gateway.ws import Conn, Turn

log = logging.getLogger("zoujin.gateway")

Json = Any

PAUSED_REFUSED = ("text", "activity_start", "action", "act_choose", "act_propose", "act_landed")
# focus while paused (the frontend sends it automatically on reconnect): no session opened, no error returned; after
# safety_resume the frontend focuses again (UX's #112 review).
# 一時停止中の focus（再接続時にフロントエンドが自動で送る）：セッションを開かず、エラーも返さない。safety_resume の
# あとフロントエンドがもう一度 focus する（UX の #112 のレビュー）。


def build_screener(settings: Settings, tracer: Tracer | None = None) -> Screener:
    """The gateway's screener: text model and Model Armor per `ZJ_MODEL` (fake in CI and containers; real only on
    the Mac).

    ゲートウェイ用の安全チェック：テキストモデルと Model Armor は `ZJ_MODEL` に従う（CI とコンテナでは偽物、本物は
    Mac 上だけ）。
    """
    return Screener(
        text=text_model(settings.model, fake_rules=settings.fake_text, replays=settings.replays, settings=settings),
        armor=armor(settings.model, replays=settings.replays),
        tracer=tracer or Tracer(),
    )


class Guard:
    """Safety state on one connection. The state itself lives in the database (`playthroughs.safety`); here it is
    read, changed and written back after each verdict.

    1 本の接続上の安全の状態。状態そのものは DB（`playthroughs.safety`）にあり、ここでは判定のたびに読んで、変えて、
    書き戻す。
    """

    def __init__(self, conn: Conn) -> None:
        self.conn = conn
        self.paused = False  # in-memory copy: handle() checks it first / メモリ上の写し：handle() が先に見る
        self.lock = asyncio.Lock()

    @property
    def screener(self) -> Screener:
        return self.conn.gw.screener

    async def load(self) -> None:
        async with self.conn.gw.engine.connect() as c:
            self.paused = SafetyState.of(await store.safety_state(c, self.conn.pid)).paused

    def start(self, t: Turn, said: str | None) -> None:
        """The player's final for this turn arrived: start screening (only once per turn).

        このターンのプレイヤーの確定文が届いた：チェックを始める（1 ターンに 1 回だけ）。
        """
        if t.screen is not None or not said:
            return
        t.screen = asyncio.ensure_future(self._run(t, said))

    async def result(self, t: Turn) -> Screen:
        """Wait for the screening result before handing to the narrator; a turn with no player words (not heard, or
        the character spoke first) = not screened.

        ナレーターに渡す前にチェックの結果を待つ。このターンにプレイヤーの言葉がない（聞き取れなかった、登場人物が先に
        話した）= チェックしていない。
        """
        if t.screen is None:
            return NOT_SCREENED
        try:
            return await t.screen
        except Exception:
            log.exception("Safety screening failed (%s) / 安全チェックでエラー", t.turn_id)
            return NOT_SCREENED

    async def context(self, character: str | None) -> Context:
        """B-15: the context the classifier and the review see. Items that can't be read are left out.

        B-15：分類器と見直しが見る文脈。読めない項目は渡さない。
        """
        conn = self.conn
        async with conn.gw.engine.connect() as c:
            pt = await conn.gw.pt(c, conn.pid)
            st = await store.sim_state(c, conn.pid)
        if pt is None or st is None:
            return Context()
        return context_of(pt.book, st["vars"]["var.player.location"], character, self._previous(character))

    def _previous(self, character: str | None) -> str | None:
        said = [r.reply for _, r in self.conn.recent.get(character or "", []) if r.reply]
        return said[-1] if said else None

    async def _second_look(self, s: Screen, said: str, ctx: Context, t: Turn | None = None, **span: object) -> Screen:
        """This line is ambiguous and the playthrough already had one (so this one would escalate): review it first
        (C in section 6 of the card).

        この発言が ambiguous で、このプレイですでに 1 回あった（今回は引き上げになる）：まず見直す
        （カード第 6 節の C）。
        """
        if s.self_harm != "ambiguous" or s.reviewed is not None:
            return s
        async with self.conn.gw.engine.connect() as c:
            st = SafetyState.of(await store.safety_state(c, self.conn.pid))
        if st.ambiguous < 1 or st.paused:
            return s
        if t is not None:
            # This would escalate: hold the character during the review too.
            # 引き上げになるので、見直しの間は登場人物も止めておく。
            t.flowing.clear()
        return await self.screener.second_look(s, said, ctx, **span)

    async def _run(self, t: Turn, said: str) -> Screen:
        conn = self.conn
        ctx = await self.context(t.character)
        span = {"playthrough_id": conn.pid, "turn_id": t.turn_id}
        try:
            s = await self.screener.screen(said, ctx, t.flowing.clear, **span)
            s = await self._second_look(s, said, ctx, t, **span)
            decision = await self._decide(s)
            if decision == "pause":
                await self.pause(t)  # what was held back is dropped with the turn / 止めていた分はターンごと捨てる
                return s
        finally:
            if not t.paused:
                # The review lowered it, or it was kept but the playthrough had already paused: release what was held.
                # 見直しで下がった、または維持されたがこのプレイはすでに一時停止済み：止めていた分を流す。
                t.flowing.set()
        if decision == "hint":
            conn.monitor.calm()
            await conn.send({"type": "safety_hint"})
        return s

    async def _decide(self, s: Screen) -> str:
        conn = self.conn
        async with self.lock, conn.gw.engine.begin() as c:
            st = SafetyState.of(await store.safety_state(c, conn.pid, lock=True))
            # Already paused (by an earlier line): this line no longer counts; only record the cost.
            # すでに一時停止済み（前の発言で）：この発言はもう数えず、費用だけを記録する。
            if st.paused:
                costs = {k: v for k, v in counts_of(s, "pass").items() if k.startswith("cost_")}
                await store.count(c, conn.pid, **costs)
                return "pass"
            decision = decide(s, st)
            await store.set_safety(c, conn.pid, st.to_json())
            await store.count(c, conn.pid, **counts_of(s, decision))
        if decision == "pause":
            self.paused = True
        return decision

    async def screen_plan(self, said: str | None) -> Screen:
        """Plans said at the end of an act are screened too (every player line): signal → pause, and the plan isn't
        handed to the narrator. No character is speaking, so there's no answer to wait for.

        幕末に言うプランもチェックする（プレイヤーのすべての発言）：signal → 一時停止し、プランはナレーターに渡さない。
        話している登場人物はいないので、答えを待つ必要はない。
        """
        if not said:
            return NOT_SCREENED
        ctx = await self.context(None)
        s = await self.screener.screen(said, ctx, playthrough_id=self.conn.pid)
        s = await self._second_look(s, said, ctx, playthrough_id=self.conn.pid)
        decision = await self._decide(s)
        if decision == "pause":
            await self.pause(None)
        elif decision == "hint":
            self.conn.monitor.calm()
            await self.conn.send({"type": "safety_hint"})
        return s

    async def pause(self, t: Turn | None) -> None:
        """Stop this turn (and later turns not yet handed over), drop the new turn whose talk button is held, close the
        sessions, and push turn_settled and safety_pause.

        このターン（とその後のまだ渡していないターン）を止め、話すボタンを押している新しいターンを捨て、セッションを
        閉じて、turn_settled と safety_pause を送る。
        """
        conn = self.conn
        stopped = []
        cur = conn.turn
        for x in (t, cur):
            if x is None or x.paused or x in stopped:
                continue
            # The player is still holding the talk button: drop it entirely and ignore later audio and activity_end
            # (3.12).
            # プレイヤーがまだ話すボタンを押している：丸ごと捨て、その後の音声と activity_end は無視する（3.12）。
            if not x.ended:
                conn.memory.pop(x.turn_id, None)
                if conn.turn is x:
                    conn.turn = None
                continue
            # Already being written to the database (handed to the narrator): too late to stop; the narrator judges
            # as usual.
            # すでに DB に書き込み中（ナレーターに渡した）：止めるには遅いので、ナレーターがいつもどおり判定する。
            if x.handing:
                continue
            x.paused = True
            stopped.append(x)
            if x.stream is not None and not x.stream.done():
                x.stream.cancel()
        # Saying a plan at the end of an act with the talk button held: drop it as well.
        # 幕末に話すボタンを押してプランを言っている：同じく捨てる。
        if conn.plan is not None:
            conn.plan.retracted = True
            conn.plan = None
        for x in stopped:
            conn.settled.add(x.turn_id)
            await conn.send(
                {"type": "turn_settled", "turnId": x.turn_id, "outcome": "paused", "eventIds": [], "minutes": 0}
            )
        await conn.send({"type": "safety_pause"})
        await conn.close_sessions()

    async def write_paused(self, t: Turn) -> None:
        """A paused turn: write one row with outcome = paused and 0 minutes, without the words said and without calling
        the narrator (3.12).

        一時停止したターン：outcome = paused、0 分の 1 行を書く。発言そのものは書かず、ナレーターも呼ばない（3.12）。
        """
        conn = self.conn
        async with conn.gw.engine.begin() as c:
            exists = await c.scalar(select(turns.c.turn_id).where(turns.c.turn_id == t.turn_id))
            if exists is not None:
                return
            await store.enqueue(
                c,
                conn.gw.ids,
                conn.pid,
                kind="talk",
                turn_id=t.turn_id,
                input_mode=t.mode,
                character=t.character,
                turn_seq=t.turn_seq,
                status="done",
            )
            await c.execute(
                update(turns)
                .where(turns.c.turn_id == t.turn_id)
                .values(outcome="paused", minutes=0, settled_at=func.now())
            )

    async def resume(self) -> None:
        conn = self.conn
        async with self.lock, conn.gw.engine.begin() as c:
            st = SafetyState.of(await store.safety_state(c, conn.pid, lock=True))
            st.paused = False
            await store.set_safety(c, conn.pid, st.to_json())
        self.paused = False
        await conn.send({"type": "safety_resumed"})


def context_of(book: Book, place: str | None, character: str | None, previous: str | None) -> Context:
    """B-15: replace character and place with display names (shared by the gateway and the eval entry point).

    B-15：登場人物と場所を表示名に置き換える（ゲートウェイと評価の入口で共用）。
    """
    places = {p["id"]: p["name"] for p in book.world["places"]}
    who = book.characters.get(character or "", {}).get("name")
    return Context(character=who, place=places.get(place or ""), previous=previous)
