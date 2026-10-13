"""The events of one commit: assign eventId, seq and idempotency keys, and apply them in seq order with W-1's apply
(B-0 item 7, step 4).

Beats and the deadline that come due are settled with W-1's settle, and the drafts are filled out into full events
before apply, so the world_state cache is field-for-field identical to the replay "initial values + apply every event in
seq order" (data-design 4.4). At the same moment: beats first, then the deadline, then the event; the caller settles up
to the event's t first.

B-3:
- Closing the act (api-contract 3.11): while the act is still open, settling only goes as far as the closing beat (an
  `end.onBeats` beat has a result) or `end.atLatest`; the rest waits for step 3 of the act transition. The last act (no
  exits) isn't held back; closing it into the ending is the ending card's job.
- Set pieces (contract 2.11): after each beat's system event is applied, ask W-1's `pick_set_piece`; pieces that played
  are recorded on the run (`run.played`), ones with `learns` are written as a learn event right after (once all beats at
  that moment are settled), and the `set_piece` message is left for the gateway to push.
- Step 3 of an act transition: the player always counts as not present (`present=False`), doesn't learn the beats'
  public facts, and set pieces aren't asked for.

1 回のコミットのイベント：eventId、seq、冪等キーを割り当て、W-1 の apply で seq 順に適用する
（B-0 第 7 項第 4 ステップ）。

時刻が来たビートと期限は W-1 の settle で精算し、下書きを完全なイベントに仕上げてから apply する。そのため
world_state のキャッシュは「初期値 + seq 順にすべてのイベントを適用」したリプレイとフィールド単位で一致する
（data-design 4.4）。同じ時刻ならビート、期限、イベントの順：呼び出し側はまずイベントの t まで settle する。

B-3：
- 幕を閉じる（api-contract 3.11）：この幕がまだ開いている間、精算は幕を閉じるビート（`end.onBeats` に結果が出た）か
  `end.atLatest` までにとどめ、その先は幕切り替えの第 3 ステップに回す。最後の幕（exits なし）は止めない。
  幕を閉じてエンディングに入るのはエンディングのカードの担当。
- 演出（固定演出、契約 2.11）：各ビートのシステムイベントを適用したあと W-1 の `pick_set_piece` に問い合わせる。
  演じたものはゲームに記録し（`run.played`）、`learns` を持つものは直後の learn イベントとして書き
  （同じ時刻のビートをすべて精算してから）、`set_piece` メッセージはゲートウェイがプッシュするよう残す。
- 幕切り替えの第 3 ステップ：プレイヤーは常にその場にいないとみなし（`present=False`）、ビートの public な事実を
  learn せず、演出も問い合わせない。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from zoujin_backend.db.store import Run
from zoujin_backend.ids import IdGen
from zoujin_backend.projection import Away, is_visible
from zoujin_backend.world import Book
from zoujin_worldsim import OCCURRED, SimState, apply, pick_set_piece, settle

Json = Any

# The data contract version written into events: the newest in the contract's `SchemaVersion` (test_world guards it).
# 書き込むときのデータ契約バージョン：契約の `SchemaVersion` の最新のもの（test_world が見張る）。
SCHEMA_VERSION = "1.15"
CHECKER_SYSTEM = "w1-settle"
CHECKER_PIECE = "set-piece"


def act_closed(book: Book, state: SimState) -> bool:
    """Whether this act has closed: one of `end.onBeats` has a result (happened, altered or prevented; past
    window.latest also counts as prevented), or the clock has reached `end.atLatest` (api-contract 3.11).

    この幕が閉じたか：`end.onBeats` のどれかに結果が出た（起きた・変わった・阻止された。window.latest を過ぎたものも
    阻止）、または時計が `end.atLatest` に達した（api-contract 3.11）。
    """
    act = book.acts[book.act_of(state["vars"])]
    end = act["end"]
    return any(b in state["beats"] for b in end["onBeats"]) or state["t"] >= end["atLatest"]


def has_exits(book: Book, state: SimState) -> bool:
    return bool(book.acts[book.act_of(state["vars"])].get("exits"))


class Writer:
    def __init__(
        self,
        book: Book,
        pid: str,
        state: SimState,
        *,
        key_base: str,
        turn_id: str | None,
        ids: IdGen,
        now: str,
    ) -> None:
        self.book = book
        self.pid = pid
        self.state = state
        self.key_base = key_base
        self.turn_id = turn_id
        self.ids = ids
        self.now = now
        self.events: list[Json] = []
        # System events written by settle (for StepResult and Trace).
        # settle が書いたシステムイベント（StepResult と Trace 用）。
        self.system: list[Json] = []
        # What is recorded on the run (read in the commit transaction and written back).
        # ゲームに記録するもの（コミットのトランザクションで読み込み、書き戻す）。
        self.run = Run()
        # Set pieces played at beat timing in this commit (set_piece messages).
        # このコミットでビートのタイミングに演じた演出（set_piece メッセージ）。
        self.pieces: list[Json] = []
        # Event IDs visible to the player (turn_settled.eventIds, api-contract 2.4).
        # プレイヤーに見えるイベント ID（turn_settled.eventIds、api-contract 2.4）。
        self.seen: list[str] = []
        # Events settled in step 3 of an act transition don't count as seen by the player (the same rule as the
        # gateway's commit push and catch-up push).
        # 幕切り替えの第 3 ステップで精算したものはプレイヤーが見たとみなさない（ゲートウェイの commit プッシュ・
        # 追いつきプッシュと同じ規則）。
        self.away = Away()
        # The act is still open at the start of this commit (an act with somewhere to go): settling stops at its close.
        # この幕はこのコミットの開始時にまだ開いている（行き先のある幕）：精算は幕を閉じるところで止める。
        self.guard = has_exits(book, state) and not act_closed(book, state)
        # B-9: this commit entered the ending (the result of `ending.enter`).
        # B-9：このコミットでエンディングに入った（`ending.enter` の結果）。
        self.ending: Json | None = None

    @property
    def player_place(self) -> str:
        p: str = self.state["vars"]["var.player.location"]
        return p

    def full(
        self,
        *,
        t: int,
        dt: int,
        actor: str,
        type: str,
        place: str,
        summary: str,
        effects: Sequence[Json],
        check: Mapping[str, Any],
        origin: str | None = None,
        causes: Sequence[str] = (),
        key_moment: bool = False,
        turn_id: str | None = None,
        **extra: Any,
    ) -> Json:
        ev: Json = {
            "schemaVersion": SCHEMA_VERSION,
            "eventId": self.ids.new("ev"),
            "playthroughId": self.pid,
            "seq": self.state["seq"] + 1,
            "idempotencyKey": f"{self.key_base}/{len(self.events) + 1:03d}",
            "worldModelVersion": self.book.version,
            "t": t,
            "dt": dt,
            "recordedAt": self.now,
            "actor": actor,
            "type": type,
            "place": place,
            "summary": summary,
            "causes": list(causes),
            "effects": [dict(e) for e in effects],
            "keyMoment": key_moment,
            "check": dict(check),
        }
        if origin is not None:
            ev["origin"] = origin
        if turn_id is not None:
            ev["turnId"] = turn_id
        ev.update(extra)
        return ev

    def add(self, ev: Json) -> Json:
        """Apply in seq order and record it. ev comes from full(); if W-1's apply rejects it, raise ValueError (the
        whole turn rolls back).

        seq 順に適用して記録する。ev は full() が作る。W-1 の apply が受け付けなければ ValueError を投げる
        （ターン全体をロールバック）。
        """
        if ev["seq"] != self.state["seq"] + 1:
            raise ValueError(
                f"Non-consecutive seq: {ev['seq']}, previous is {self.state['seq']}"
                f" / seq が連続していない：{ev['seq']}、直前は {self.state['seq']}"
            )
        if not self.away(ev) and is_visible(self.book, ev, self.player_place):
            self.seen.append(ev["eventId"])
        self.state = apply(self.book.world, self.state, ev)
        self.events.append(ev)
        return ev

    @property
    def closed(self) -> bool:
        """This act (open at the start) closed during this commit.

        この幕（開始時に開いていたもの）がこのコミットの中で閉じた。
        """
        return self.guard and act_closed(self.book, self.state)

    def settle(
        self,
        t2: int | None,
        *,
        stop_after: str | None = None,
        present: bool = True,
        guard: bool = True,
        anywhere: bool = False,
    ) -> list[Json]:
        """Settle up to t2 (None = to the end). When stop_after names a beat, stop right after writing its system event
        (the eval checkpoint "just after it happened").

        guard: if this act was open at the start, settle only up to its close (everything at the moment of the closing
        beat is settled); once the act has closed, settle nothing more.
        present=False: step 3 of an act transition; the player isn't present (W-1 settle's player_present), and set
        pieces aren't asked for.
        anywhere: beat set pieces don't depend on whether the player is at the beat's place (B-9: when entering the
        ending, the closing parts count as the ending set piece, with the camera at the execution ground).

        t2 まで精算する（None = 最後まで）。stop_after にビートを渡すと、そのシステムイベントを書いたところで止める
        （評価のチェックポイント「起きた直後」）。

        guard：この幕が開始時に開いていれば、幕を閉じるところまでだけ精算する（幕を閉じるビートの時刻のものは
        すべて精算する）。幕がもう閉じていれば何も精算しない。
        present=False：幕切り替えの第 3 ステップ。プレイヤーはその場にいない（W-1 settle の player_present）。
        演出は問い合わせない。
        anywhere：ビートの演出は、プレイヤーがビートの場所にいるかを見ない（B-9：エンディングに入るとき、
        幕を閉じる部分はエンディングの演出に含め、カメラは刑場にある）。
        """
        if guard and self.guard:
            if self.closed:
                return []
            at_latest = int(self.book.acts[self.book.act_of(self.state["vars"])]["end"]["atLatest"])
            t2 = at_latest if t2 is None else min(t2, at_latest)
        drafts, _ = settle(self.book.world, self.state, t2, player_present=present)
        out: list[Json] = []
        # learns carried by beat-timed set pieces, written once everything at that moment is settled.
        # ビートのタイミングの演出が持つ learns。同じ時刻のものをすべて精算してから書く。
        learns: list[Json] = []
        closed_at: int | None = None
        for d in drafts:
            t = d["event"]["t"]
            if closed_at is not None and t > closed_at:
                break
            if learns and t > learns[0]["t"]:
                self._learns(learns)
            out.append(self.add(self.from_draft(d)))
            if present and d["beat"] is not None:
                self._beat_piece(d["beat"], t, learns, anywhere=anywhere)
            if stop_after is not None and d["beat"] == stop_after:
                break
            if guard and self.closed and closed_at is None:
                closed_at = t
        self._learns(learns)
        self.system.extend(out)
        return out

    def curtain(self, beat: str) -> bool:
        """The beat the deadline watches in the last act, and the beats after it (B-9: the closing set pieces count as
        the ending set piece, wherever the player is).

        最後の幕で期限が見張るビートと、それ以降のビート（B-9：幕を閉じる演出はエンディングの演出に含め、
        プレイヤーの居場所を問わない）。
        """
        watch = self.book.world["clock"]["deadline"].get("watchBeat")
        if watch is None or has_exits(self.book, self.state):
            return False
        return float(self.book.beats[beat]["order"]) >= float(self.book.beats[watch]["order"])

    def _beat_piece(self, beat: str, t: int, learns: list[Json], *, anywhere: bool = False) -> None:
        state = self.state
        # W-1 only gives one when the player is at the beat's place: ask as if the player stood there.
        # W-1 はプレイヤーがビートの場所にいるときだけ返す：問い合わせるときはプレイヤーがそこに立っているとみなす。
        if anywhere or self.curtain(beat):
            vars_ = {**state["vars"], "var.player.location": self.book.beats[beat]["place"]}
            state = cast(SimState, {**state, "vars": vars_})
        piece = pick_set_piece(self.book.world, state, {"beat": beat}, self.run.played)
        if piece is None:
            return
        self.play(piece)
        if piece.get("learns"):
            learns.append({"t": t, "piece": piece})

    def play(self, piece: Mapping[str, Any]) -> Json:
        """Play one set piece: record it on the run (once pieces don't play again) and return the set_piece message.

        演出を 1 つ演じる：ゲームに記録し（once のものは二度と演じない）、set_piece メッセージを返す。
        """
        self.run.played.append(piece["id"])
        msg = {"type": "set_piece", "pieceId": piece["id"], "lines": [dict(x) for x in piece["lines"]]}
        if "beat" in piece["on"]:
            self.pieces.append(msg)
        return msg

    def _learns(self, learns: list[Json]) -> None:
        for x in learns:
            self.piece_learn(x["piece"], x["t"], origin=None)
        learns.clear()

    def piece_learn(self, piece: Mapping[str, Any], t: int, *, origin: str | None) -> Json | None:
        """Write a set piece's learns as one learn event (contract 2.11): the actor is the first character who
        speaks, or system when there is only 地の文; at action timing origin is action, at beat timing it is left out
        (schedule is only for beats and the deadline). Facts already known aren't written again.

        演出の learns を 1 つの learn イベントとして書く（契約 2.11）：actor は最初に話す登場人物で、地の文だけのときは
        system。アクションのタイミングなら origin は action、ビートのタイミングなら書かない（schedule はビートと期限
        専用）。すでに知っているものは書かない。
        """
        effects = [
            {"op": "learn", "character": k["character"], "fact": k["fact"]}
            for k in piece.get("learns", [])
            if k["fact"] not in self.state["knowledge"].get(k["character"], [])
        ]
        if not effects:
            return None
        speaker = next((x["speaker"] for x in piece["lines"] if x.get("speaker")), None)
        name = self.book.characters[speaker]["name"] if speaker else None
        return self.add(
            self.full(
                t=t,
                dt=0,
                actor=speaker or "system",
                type="learn",
                origin=origin,
                place=self.player_place,
                summary=f"{name}が、そのことを口にした" if name else "そのことが、知らされた",
                effects=effects,
                check={"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER_PIECE},
                turn_id=self.turn_id if origin is not None else None,
            )
        )

    def occurred(self, beat: str) -> bool:
        return self.state["beats"].get(beat) in OCCURRED

    def from_draft(self, d: Json) -> Json:
        """Fill out a W-1 settle draft (or the ones in `opening()` with source = schedule) into a full system event.

        W-1 の settle の下書き（または `opening()` のうち source = schedule のもの）を完全なシステムイベントに仕上げる。
        """
        e = d["event"]
        check: Json = {"status": "passed", "attempts": 1, "failedRules": [], "checker": CHECKER_SYSTEM}
        if d.get("reason"):
            check["reason"] = d["reason"]
        if d["beat"] is not None:
            beat = self.book.beats[d["beat"]]
            summary = beat["summary"]
            for v in beat.get("variants", []):
                if v["id"] == d.get("variant") and v.get("summary"):
                    summary = v["summary"]
        else:
            deadline = self.book.world["clock"]["deadline"]
            summary = f"{deadline['label']}の刻限が来た"
        return self.full(
            t=e["t"],
            dt=e["dt"],
            actor=e["actor"],
            type=e["type"],
            origin=e["origin"],
            place=e["place"],
            summary=summary,
            effects=e["effects"],
            check=check,
        )
