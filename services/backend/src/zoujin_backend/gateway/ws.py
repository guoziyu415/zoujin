"""The WebSocket of api-contract sections 3 and 4 (the messages done in B-0 item 5).

A voice turn: `activity_start` → upstream audio → `activity_end` → the fake Live returns the player's subtitles, the
character's audio and subtitles, `turn_complete` → write the words said and the turn's task → call the narrator →
NOTIFY after the narrator commits → push `commit` and `turn_settled`. A text turn replaces the first half with `text`.

Interruption (3.2): when a new turn arrives while the character is still speaking, the old turn stops (`interrupted`, a
final up to where it got) and is handed to the narrator as usual; if the character has already sent `turn_complete` and
the final hasn't arrived, it isn't an interruption: the turn is handed over as usual once the final arrives. A turn the
character hadn't finished at disconnect is recorded as `lost` (section 4 `lastTurn.status`) and not handed to the
narrator; finished ones are handed over as usual.

B-3 added actions and end of act (3.8, 3.11): `action`, `act_choose` and `act_propose` each write one task row
(`turns.kind` = action / choose / plan) and then call the narrator; saying a plan by voice (`activity_start purpose:
"act_plan"`) is only transcribed, with no character answer, and writes a plan task likewise after release. When the
narrator has judged, it records the messages to push in order in `turns.result.push`; here, after pushing that commit's
`commit`, they are pushed accordingly (`_results`). After the act closes and before a choice is made, `text`,
`activity_start` (except `act_plan`) and `action` get `invalid_request` (section 5). For a landing with an `opener`,
the character speaks first only on receiving `act_landed` (`turn_started reason: "arrival"`), and that line isn't
handed to the narrator.

B-4 added retraction, recognition correction and intent confirmation (3.6, 3.9):
- `turn_retract`: if the turn is still in the connection's memory (the player still talking, the character not
  finished, not yet handed to the narrator), stop it and write a `retracted` row; if it was handed to the narrator but
  not yet committed, change it to `retracted` in the database and clear the words said (whichever of this and the
  narrator's commit gets the row lock first wins); otherwise `too_late`. After a conversation turn is retracted, the
  character's session is rebuilt (`session_preparing reason: "rebuild"` → `session_ready`), and the new session only
  carries the text of the last few turns with them on this connection, skipping retracted ones (`recent`, memory only).
  A
  new turn waits until the session is ready (`ready`).
- Conversation turns and plans said by voice are handed to the narrator with a commit window (`turn_complete` or final
  + 3 seconds, shortened by `ZJ_SPEED`).
- `text { via: "correction" }`: the frontend sends `turn_retract` first; when the old turn is retracted successfully
  the session is already being rebuilt, and the new turn waits for ready as usual.
- Intent confirmation: the narrator records what to ask in `turns.result.confirm`; here, after pushing that turn's
  result, if the character hasn't asked back yet, a new turn is started to say the question (`turn_started reason:
  "confirm"`, its words attached under the original turn), then `confirm` is pushed and a 30-second timer started
  (shortened by `ZJ_SPEED`; 30 seconds at speed 0). The buttons and the timer running out each write a `kind: "confirm"`
  task. On reconnect, `welcome.pending.confirm` carries the remaining seconds; expired ones are closed first.

Reconnect (section 4): resend the `commit`s after `hello.lastSeq`; turn results already settled before this connection
are not resent, with one exception (v1.0.12): when the last commit is an act change the client hasn't confirmed
receiving (`lastSeq` no later than its `seq`), that `act_transition` (together with `act_plan_result` if a plan worked
out) is pushed again after the resent `commit`, otherwise an end-of-act page that chose a destination during the
disconnect would never get the act change (`again`).

B-9 added the ending (3.13):
- For the commit that enters the ending, `ending_started` goes before its commit (`Gateway.commits`). Once pushed, this
  connection takes no more input: audio frames are dropped, and `text`, `activity_start`, `action` and `act_choose` get
  `invalid_request`; if the character is still saying a line, forwarding continues until it finishes or for at most 3
  seconds, and then the playthrough's Live sessions are closed (`_wind_down`, including ones being opened or warmed);
  after that `focus` and `near` open no sessions. Turns not yet handed to the narrator are recorded as `lost` and not
  handed over.
- After the ending task commits, `ending_ready` is pushed (`turns.result.push`). If the playthrough is already `ended`
  on reconnect: after `welcome`, `ending_started` is pushed once more (the stored `staging`), and `ending_ready` once
  the
  ending is ready.

B-10 connected real Live (`models/gemini_live.py`, `ZJ_LIVE=real`); opening, swapping and closing sessions all live in
`gateway/voice.py`: `near` / `far` warm-up, `focus`, rebuilding after retraction, the seamless rebuild every N turns
and on Live's goAway, Live dropping mid-way (a turn that made sound with `turn_complete { audio: true }` is handed over
as usual, a silent one gets `no_response`, then `rebuild`), mid-session situation updates after narrator commits, idle
closing, and each turn's cost. When the character has audio but no text, fallback transcription runs
(`gateway/fallback.py`, final `source: "fallback"`). B-11: on disconnect, sessions and recent conversation are parked
and the reconnecting `hello` takes them over. Whether or not `hello.fakeVoice` is given, the gateway's setting applies.
Messages not yet implemented are ignored, logging only the type name.

api-contract 第 3・4 節の WebSocket（B-0 第 5 項で作ったメッセージ）。

音声の 1 ターン：`activity_start` → 上り音声 → `activity_end` → 偽 Live がプレイヤーの字幕、登場人物の音声と字幕、
`turn_complete` を返す → 発言そのものとこのターンのタスクを書く → ナレーターを呼ぶ → ナレーターの commit 後に NOTIFY →
`commit` と `turn_settled` を送る。文字のターンは前半を `text` に置き換える。

割り込み（3.2）：登場人物がまだ話している間に新しいターンが来たら、古いターンを止め（`interrupted`、途中までの確定文）、
いつもどおりナレーターに渡す。登場人物がすでに `turn_complete` を送り確定文がまだ届いていないものは割り込みではなく、
確定文が届いたらいつもどおり渡す。切断時に登場人物が話し終えていなかったターンは `lost` と記録し（第 4 節
`lastTurn.status`）、ナレーターには渡さない。話し終えたものはいつもどおり渡す。

B-3 でアクションと幕末を加えた（3.8、3.11）：`action`、`act_choose`、`act_propose` はそれぞれタスクを 1 行書いて
（`turns.kind` = action / choose / plan）からナレーターを呼ぶ。声でプランを言う（`activity_start purpose: "act_plan"`）
のは文字起こしだけで登場人物は答えず、離したあと同じく plan のタスクを書く。ナレーターは判定し終えると送るべきメッセージ
を順に `turns.result.push` に記録し、ここではその commit の `commit` を送ったあとそれに従って送る（`_results`）。
幕を閉じてまだ選んでいない間は、`text`、`activity_start`（`act_plan` を除く）、`action` に `invalid_request`
を返す（第 5 節）。着地に `opener` があるものは、`act_landed` を受け取ってから登場人物が先に話し出し（`turn_started
reason: "arrival"`）、その発言はナレーターに渡さない。

B-4 で取り消し、認識の訂正、意図の確認を加えた（3.6、3.9）：
- `turn_retract`：そのターンがまだ接続のメモリにある（プレイヤーが話している、登場人物が話し終えていない、
  ナレーターにまだ渡していない）なら止めて `retracted` の行を書く。ナレーターに渡したがまだ commit していないものは DB
  で
  `retracted` に変え、発言そのものを消す（ナレーターの commit とどちらが先に行ロックを取るかで決まる）。
  それ以外は `too_late`。会話のターンを取り消したら、その登場人物のセッションを作り直し（`session_preparing reason:
  "rebuild"` → `session_ready`）、新しいセッションにはこの接続上でのその人との直近数ターンの文字だけを、
  取り消したものを飛ばして持たせる（`recent`、メモリ内のみ）。セッションの準備ができるまで新しいターンは待つ
  （`ready`）。
- 会話や声で言ったプランは、提出の時間枠を付けてナレーターに渡す（`turn_complete` または確定文 + 3 秒、
  `ZJ_SPEED` で短縮）。
- `text { via: "correction" }`：フロントエンドは先に `turn_retract` を送る。古いターンの取り消しに成功した時点で
  セッションはすでに作り直し中で、新しいターンはいつもどおり準備完了を待つ。
- 意図の確認：ナレーターは尋ねることを `turns.result.confirm` に記録する。ここではそのターンの結果を送ったあと、
  登場人物がまだ聞き返していなければ新しいターンを起こして聞き返しを言わせ（`turn_started reason: "confirm"`、
  発言は元のターンの下にぶら下げる）、`confirm` を送って 30 秒のタイマーを始める（`ZJ_SPEED` で短縮。
  速度 0 なら 30 秒のまま）。ボタンもタイマー切れも `kind: "confirm"` のタスクを 1 行書く。再接続時は
  `welcome.pending.confirm` に残り秒数を付け、期限切れのものは先に閉じる。

再接続（第 4 節）：`hello.lastSeq` 以降の `commit` を再送する。この接続より前に判定済みのターンの結果は再送しないが、
例外が 1 つある（v1.0.12）：最後の commit が幕の切り替わりで、クライアントがまだ受け取りを確認していない（`lastSeq`
がその `seq` より後でない）ときは、再送した `commit` のあとにその `act_transition`（プランが成立した場合は
`act_plan_result` も）をもう一度送る。そうしないと、切断中に行き先を選んだ幕末ページが幕の切り替わりをいつまでも受け取れ
ない（`again`）。

B-9 でエンディングを加えた（3.13）：
- エンディングに入る commit では、`ending_started` をその commit の前に置く（`Gateway.commits`）。送ったあと、
  この接続は入力を受け付けない：音声フレームは捨て、`text`、`activity_start`、`action`、`act_choose` には
  `invalid_request` を返す。登場人物がまだ話していれば、話し終えるか最大 3 秒まで転送を続け、それからこのプレイの Live
  セッションを閉じる（`_wind_down`、開いている最中やウォームアップ中のものも）。その後の `focus`、
  `near` ではセッションを開かない。ナレーターにまだ渡していないターンは `lost` と記録し、渡さない。
- エンディングのタスクが commit したら `ending_ready` を送る（`turns.result.push`）。再接続時にプレイがすでに `ended`
  なら、`welcome` のあと `ending_started`（保存した `staging`）をもう一度送り、エンディングができたら `ending_ready`
  を送る。

B-10 で本物の Live（`models/gemini_live.py`、`ZJ_LIVE=real`）をつないだ。セッションを開く・入れ替える・
閉じるのはすべて `gateway/voice.py`：`near` / `far` のウォームアップ、`focus`、取り消し後の作り直し、
N ターンごとと Live の goAway での気づかれない作り直し、Live の途中の切断（声を出した `turn_complete { audio: true }`
はいつもどおり渡し、声を出していないものは `no_response`、それから `rebuild`）、ナレーターの commit 後の途中の状況更新、
アイドル時のクローズ、ターンごとの費用。登場人物に音声はあるが文字がないときは補完の文字起こしをする
（`gateway/fallback.py`、確定文は `source: "fallback"`）。B-11：切断時にセッションと直近の会話を預け、
再接続の `hello` が引き継ぐ。`hello.fakeVoice` があってもなくてもゲートウェイの設定に従う。まだ実装していないメッセージ
は無視し、ログに type 名だけを記録する。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, cast

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import func, select, update
from starlette.websockets import WebSocketState

from zoujin_backend import audio, budget
from zoujin_backend.config import COOKIE
from zoujin_backend.db import store
from zoujin_backend.db.store import Run
from zoujin_backend.db.tables import drafts, endings, playthrough_metrics, playthroughs, turns, utterances
from zoujin_backend.gateway import auth
from zoujin_backend.gateway.core import Gateway
from zoujin_backend.gateway.fallback import fallback_text
from zoujin_backend.gateway.monitor import Monitor
from zoujin_backend.gateway.safety import PAUSED_REFUSED, Guard
from zoujin_backend.gateway.voice import Voices
from zoujin_backend.models.armor import cost_usd
from zoujin_backend.models.live import LiveLost, LiveSession, Recent, Transcriber
from zoujin_backend.narrator import confirm
from zoujin_backend.narrator.acts import PLAN_TRIES
from zoujin_backend.narrator.pipeline import Spend, TurnInput
from zoujin_backend.narrator.plans import INVALID_REQUEST, NOT_HEARD, REFUSAL_FALLBACK, narrate_fallback
from zoujin_backend.origin import origin_allowed
from zoujin_backend.projection import open_affordances, pending
from zoujin_backend.safety import Screen
from zoujin_backend.schemas import SchemaError

log = logging.getLogger("zoujin.gateway")

Json = Any

FRAME_MIC = 0x01
# Tasks that must give the frontend a result once judged (same name in narrator/core.py), plus answers to intent
# confirmations (confirm_closed, B-4).
# 判定後にフロントエンドへ結果を返すタスク（narrator/core.py の同名のもの）に、意図の確認への答え（confirm_closed、B-4）
# を加えたもの。
ANSWERED = ("talk", "action", "choose", "plan", "confirm", "ending")
# turnSeq of server-initiated turns starts here, with the top bit set (3.1).
# サーバーが起こすターンの turnSeq はここから始まり、最上位ビットが 1（3.1）。
SERVER_SEQ = 0x80000001
# Retraction window: the narrator commits at the earliest this many seconds after turn_complete (the final, for plans)
# (B-4).
# 取り消しの時間枠：ナレーターが commit するのは早くても turn_complete（プランなら確定文）からこの秒数の後（B-4）。
COMMIT_WINDOW_S = 3.0
RECENT_TURNS = 6  # recent turns carried into a rebuilt session / 作り直したセッションに持ち込む直近のターン数
# When entering the ending while the character is still saying a line, forward for at most this many more seconds (B-9,
# shortened by ZJ_SPEED).
# エンディングに入ったとき登場人物がまだ話していれば、最大でこの秒数だけ転送を続ける（B-9、ZJ_SPEED で短縮）。
ENDING_DRAIN_S = 3.0


def again(results: list[Json], client_seq: int, last_seq: int) -> list[Json]:
    """The act change to push again on reconnect (section 4, v1.0.12). results: `turns.result` of judged turns, in the
    order judged. When the latest act change is the last commit (no other commit after it) and the client's
    `lastSeq` is no later than it: that commit's `act_plan_result` (only when a plan worked out) and
    `act_transition`, in the original order. The frontend uses them only while the end-of-act page is still waiting
    for the act change, and ignores them otherwise.

    再接続時にもう一度送る幕の切り替わり（第 4 節、v1.0.12）。results：判定済みのターンの `turns.result`、判定した順。
    直近の幕の切り替わりが最後の commit で（その後に別の commit がない）、クライアントの `lastSeq`
    がそれより後でないとき：そのときの `act_plan_result`（プランが成立したときだけある）と `act_transition`
    を元の順で返す。フロントエンドは幕末ページがまだ幕の切り替わりを待っているときだけ使い、それ以外は無視する。
    """
    for r in reversed(results):
        push = (r or {}).get("push") or []
        if any(m["type"] == "act_transition" for m in push):
            seq = r.get("seq")
            if seq != last_seq or client_seq > seq:
                return []
            return [m for m in push if m["type"] in ("act_plan_result", "act_transition")]
    return []


def error_msg(code: str, message: str) -> Json:
    return {"type": "error", "error": {"code": code, "message": message, "retryable": False, "retryAfterSeconds": None}}


def _open() -> asyncio.Event:
    e = asyncio.Event()
    e.set()
    return e


@dataclass
class Turn:
    """The turn in progress on the connection (not yet handed to the narrator).

    接続上で進行中のターン（まだナレーターに渡していない）。
    """

    turn_id: str
    turn_seq: int
    character: str
    # voice / text / arrival (the character speaks first on landing, B-3) / confirm (the question of an intent
    # confirmation, B-4)
    # voice / text / arrival（着地で登場人物が先に話す、B-3）/ confirm（意図の確認の聞き返し、B-4）
    mode: str
    # None while the session is still opening (switch, rebuild): upstream audio is buffered and sent in once ready
    # (B-10).
    # セッションがまだ開いている最中（切り替え、作り直し）は None：上り音声はためておき、準備完了後に送り込む（B-10）。
    session: LiveSession | None
    # The words of a text turn; confirm: the question the character is to say.
    # 文字のターンの発言。confirm：登場人物が言う聞き返し。
    text: str | None = None
    ended: bool = False  # activity_end or text received / activity_end か text を受け取った
    # Player subtitles: the latest partial, or the final.
    # プレイヤーの字幕：最新の途中の文か確定文。
    heard: str | None = None
    # Character subtitles: the latest partial, or the final.
    # 登場人物の字幕：最新の途中の文か確定文。
    said: str | None = None
    first_audio: float | None = None
    complete: bool = False  # turn_complete sent (the character finished) / turn_complete を送った（話し終えた）
    final: bool = False  # the character's final sent / 登場人物の確定文を送った
    lost: bool = False  # the character hadn't finished at disconnect / 切断時に登場人物が話し終えていなかった
    # Forwards Live's answer; cancelled on interruption or disconnect.
    # Live の答えを転送する。割り込み・切断で取り消す。
    stream: asyncio.Task[None] | None = None
    # This turn won't send any more subtitles or audio.
    # このターンはもう字幕も音声も送らない。
    quiet: asyncio.Event = field(default_factory=asyncio.Event)
    # The previous turn on the same connection: this turn is handed over only after it, so the narrator judges in the
    # order the player spoke.
    # 同じ接続上の前のターン：それが渡されてからこのターンを渡すので、ナレーターはプレイヤーが話した順に判定する。
    prev: Turn | None = None
    submitted: asyncio.Event = field(default_factory=asyncio.Event)
    # When the character finished (turn_complete) or was interrupted: the commit window counts from here (B-4).
    # 登場人物が話し終えた（turn_complete）か割り込まれた時刻：提出の時間枠はここから数える（B-4）。
    done_at: float | None = None
    retracted: bool = False  # retracted while still in memory (B-4) / メモリにある間に取り消された（B-4）
    # Being written to the database (handed to the narrator): later retractions take the database path.
    # DB に書き込み中（ナレーターに渡している）：以後の取り消しは DB 側の経路を通る。
    handing: bool = False
    # confirm: the original turn (the question's words hang under it).
    # confirm：元のターン（聞き返しの発言はその下にぶら下げる）。
    owner: str | None = None
    # confirm: the confirm to push after speaking (turns.result.confirm).
    # confirm：話し終えたら送る confirm（turns.result.confirm）。
    asking: Json | None = None
    # Upstream audio before the session is ready (B-10).
    # セッションの準備ができる前の上り音声（B-10）。
    early: list[bytes] = field(default_factory=list)
    # When it was sent into Live (release, text, speaking first).
    # Live に送り込んだ時刻（離したとき、文字、先に話し出すとき）。
    released: float | None = None
    # The character's audio for this turn (for fallback transcription, memory only).
    # このターンの登場人物の声（補完の文字起こし用、メモリ内のみ）。
    pcm_out: bytearray = field(default_factory=bytearray)
    # Source of the character's final: live / fallback (fallback transcription).
    # 登場人物の確定文の出どころ：live / fallback（補完の文字起こし）。
    source: str = "live"
    # Live dropped mid-way (closed out as interrupted).
    # Live が途中で切れた（割り込みとして締める）。
    dropped: bool = False
    # B-12: safety screening of the player's line (starts as soon as the final arrives).
    # B-12：プレイヤーの発言の安全チェック（確定文が届いたらすぐ始める）。
    screen: asyncio.Future[Screen] | None = None
    # B-15: during the review, hold back the character's audio and subtitles not yet sent (cleared = held; what was
    # already sent isn't taken back). Dropped on pause, released when the review lowers it.
    # B-15：見直しの間、登場人物のまだ送っていない音声と字幕を止める（クリア = 止める。すでに送ったものは取り戻さな
    # い）。一時停止なら捨て、見直しで下がれば流す。
    flowing: asyncio.Event = field(default_factory=lambda: _open())
    # B-12: stopped by the out-of-story card (no character final pushed, not handed to the narrator).
    # B-12：物語の外のカードで止められた（登場人物の確定文を送らず、ナレーターにも渡さない）。
    paused: bool = False

    @property
    def retractable(self) -> bool:
        return self.mode in ("voice", "text")

    @property
    def speaking(self) -> bool:
        return self.stream is not None and not self.stream.done() and not self.complete


@dataclass
class PlanTurn:
    """A turn of saying a plan by voice at the end of an act (3.11): transcription only, no character answer; handed to
    the narrator as a plan after release.

    幕末に声でプランを言うターン（3.11）：文字起こしだけで登場人物は答えず、離したあとナレーターに plan として渡す。
    """

    turn_id: str
    turn_seq: int
    listener: Transcriber
    # Partials pushed out: the final must come after them.
    # 送り出した途中の文：確定文はそれらの後に並べる。
    partials: list[asyncio.Task[Any]] = field(default_factory=list)
    # Retracted while still being said (B-4): dropped; no final pushed, no task written.
    # 話している最中に取り消された（B-4）：捨てる。確定文を送らず、タスクも書かない。
    retracted: bool = False


@dataclass
class Conn:
    gw: Gateway
    ws: WebSocket
    pid: str
    user_id: str
    sent_seq: int = -1  # seq pushed up to; nothing is pushed before hello / 送った先の seq。hello 前は送らない
    # The playthrough's characters (read on hello). / このプレイの登場人物（hello のときに読む）。
    characters: dict[str, Json] = field(default_factory=dict)
    focused: str | None = None
    sessions: dict[str, LiveSession] = field(default_factory=dict)
    ready_at: dict[str, float] = field(default_factory=dict)
    # The session is ready (session_ready pushed); a new turn waits for it.
    # セッションの準備ができた（session_ready を送った）。新しいターンはこれを待つ。
    ready: dict[str, asyncio.Event] = field(default_factory=dict)
    # Each character's last few turns (memory only). / 登場人物ごとの直近数ターン（メモリ内のみ）。
    recent: dict[str, list[tuple[str, Recent]]] = field(default_factory=dict)
    # Turns not yet handed to the narrator (looked up on retraction). / まだナレーターに渡していないターン（取り消し時に
    # 引く）。
    memory: dict[str, Turn] = field(default_factory=dict)
    # 30-second timers of intent confirmations, by draftId. / 意図の確認の 30 秒タイマー、draftId ごと。
    timers: dict[str, asyncio.Task[Any]] = field(default_factory=dict)
    turn: Turn | None = None
    plan: PlanTurn | None = None
    # Server-initiated turns on this connection (for turnSeq). / この接続でサーバーが起こしたターン数（turnSeq 用）。
    served: int = 0
    # Who a retracted turn was said to (for rebuilding the session). / 取り消したターンの相手（セッションの作り直し
    # 用）。
    retracted_with: dict[str, str] = field(default_factory=dict)
    # Turns whose results were already pushed (or were judged before this connection).
    # 結果をすでに送った（またはこの接続より前に判定済みの）ターン。
    settled: set[str] = field(default_factory=set)
    # B-9: this connection already pushed ending_started (no more input after it).
    # B-9：この接続はすでに ending_started を送った（以後は入力を受け付けない）。
    ending: bool = False
    closed: asyncio.Event = field(default_factory=asyncio.Event)
    push_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    voices: Voices = field(init=False)
    # B-12: safety screening (gateway/safety.py). / B-12：安全チェック（gateway/safety.py）。
    guard: Guard = field(init=False)
    # B-12: monitoring of character output (gateway/monitor.py).
    # B-12：登場人物の出力のモニター（gateway/monitor.py）。
    monitor: Monitor = field(init=False)

    def __post_init__(self) -> None:
        self.voices = Voices(self)
        self.guard = Guard(self)
        self.monitor = Monitor(self.gw.library)

    async def close_sessions(self) -> None:
        """Out-of-story card: close every character session on this connection (3.12), and stop warm-ups and sessions
        being opened or swapped; after returning to the story the frontend focuses again and new sessions are opened.

        物語の外のカード：この接続上のすべての登場人物のセッションを閉じ（3.12）、ウォームアップ中、開いている最中、
        入れ替え中のものも止める。物語に戻ったらフロントエンドがあらためて focus し、新しいセッションを開く。
        """
        await self.voices.close_all()
        self.ready.clear()
        self.ready_at.clear()
        self.focused = None

    # —— Sending / 送信 ——

    async def send(self, msg: Json) -> None:
        """Build with the generated types and validate against the Schema before sending; anything that breaks the
        contract is not sent but logged.

        生成した型で組み立て、Schema で検証してから送る。契約に合わないものは送らず、ログに記録する。
        """
        try:
            out = self.gw.schemas.server_message(msg)
        except SchemaError:
            log.exception("Not sending %s: breaks the contract / 契約に合わない", msg.get("type"))
            return
        if self.gw.on_send is not None:
            self.gw.on_send(out)
        if msg.get("type") == "act_ended":
            self.monitor.act_ended()
        async with self.send_lock:
            if self.closed.is_set():
                return
            try:
                await self.ws.send_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
            except (RuntimeError, WebSocketDisconnect):
                self.closed.set()

    async def send_bytes(self, data: bytes) -> None:
        async with self.send_lock:
            if self.closed.is_set():
                return
            try:
                await self.ws.send_bytes(data)
            except (RuntimeError, WebSocketDisconnect):
                self.closed.set()

    async def close(self, code: int, reason: str = "") -> None:
        async with self.send_lock:
            if self.closed.is_set():
                return
            self.closed.set()
            with contextlib.suppress(RuntimeError, WebSocketDisconnect):
                if self.ws.application_state == WebSocketState.CONNECTED:
                    await self.ws.close(code, reason)

    # —— Pushing commits and each turn's result / commit と各ターンの結果を送る ——

    async def push(self) -> None:
        """Push everything committed after sent_seq (both the hello resend and NOTIFY go through here), then push the
        results of judged turns.

        sent_seq 以降に commit されたものをすべて送り（hello の再送も NOTIFY もここを通る）、それから判定済みのターンの
        結果を送る。
        """
        async with self.push_lock:
            if self.sent_seq < 0:
                return
            msgs, self.sent_seq = await self.gw.commits(self.pid, self.sent_seq)
            for m in msgs:
                if m["type"] == "ending_started":
                    if self.ending:  # already resent on reconnect / 再接続時にすでに送った
                        continue
                    self.start_ending()
                await self.send(m)
            await self._results()

    # —— Ending (B-9) / エンディング ——

    def start_ending(self) -> None:
        self.ending = True
        self.gw.spawn(self._wind_down())

    async def _wind_down(self) -> None:
        """Entered the ending: if the character is still saying a line, keep forwarding until it finishes or for 3
        seconds (`ENDING_DRAIN_S`), then close the playthrough's Live sessions.

        エンディングに入った：登場人物がまだ話していれば、話し終えるか 3 秒（`ENDING_DRAIN_S`）まで転送を続け、
        それからこのプレイの Live セッションを閉じる。
        """
        t = self.turn
        if t is not None and t.speaking:
            assert t.stream is not None
            await asyncio.wait({t.stream}, timeout=ENDING_DRAIN_S * self.gw.settings.speed)
            if t.speaking:
                t.lost = True
                t.stream.cancel()
            await t.quiet.wait()
        await self.voices.close_all()
        self.focused = None

    async def _ending_row(self) -> tuple[Json | None, str | None]:
        """The request of the playthrough's ending task (trigger, staging), and the stored ending ID (None if not ready
        yet).

        このプレイのエンディングのタスクの request（trigger、staging）と、保存したエンディングの ID（まだなら None）。
        """
        async with self.gw.engine.connect() as c:
            request = await c.scalar(
                select(turns.c.request)
                .where(turns.c.playthrough_id == self.pid, turns.c.kind == "ending")
                .order_by(turns.c.created_at)
                .limit(1)
            )
            ending_id = await c.scalar(select(endings.c.ending_id).where(endings.c.playthrough_id == self.pid))
        return request, ending_id

    async def _results(self) -> None:
        """Push the results of judged turns: the messages the narrator recorded in `turns.result.push` (set pieces,
        turn_settled, action_result, act_plan_result, act_transition, act_ended), in the order judged.
        `turns.result.seq` is the last seq of that turn's commit: if commits haven't been pushed that far (the
        narrator committed right between reading commits and reading turns), it is left for next time, so the result
        always comes after its own commit (3.4, 3.8, 3.14), even when the turn has no events of its own (`wait` only
        settles beats). Tasks that failed all three times get a stand-in by kind (`_fallback`).

        判定済みのターンの結果を送る：ナレーターが `turns.result.push` に記録したメッセージ（固定演出、turn_settled、
        action_result、act_plan_result、act_transition、act_ended）を判定した順に。`turns.result.seq` はそのターンの
        commit の最後の seq：commit をまだそこまで送っていない（ナレーターがちょうど commit を読んでからターンを読むまで
        の間に commit した）なら次回に回し、結果が必ず自分の commit の後になるようにする（3.4、3.8、3.14）。
        そのターン自体にイベントがない（`wait` がビートを精算するだけ）場合も同じ。3 回ともうまくいかなかったタスクには
        種類ごとに代わりを 1 つ送る（`_fallback`）。
        """
        async with self.gw.engine.connect() as c:
            rows = (
                await c.execute(
                    select(
                        turns.c.turn_id,
                        turns.c.kind,
                        turns.c.outcome,
                        turns.c.minutes,
                        turns.c.client_msg_id,
                        turns.c.request,
                        turns.c.result,
                    )
                    .where(
                        turns.c.playthrough_id == self.pid,
                        turns.c.kind.in_(ANSWERED),
                        turns.c.status.in_(("done", "failed")),
                        turns.c.settled_at.is_not(None),
                    )
                    .order_by(turns.c.settled_at)
                )
            ).all()
        for r in rows:
            upto = (r.result or {}).get("seq")
            if r.turn_id in self.settled or (upto is not None and upto > self.sent_seq):
                continue
            self.settled.add(r.turn_id)
            if r.result is not None and "push" in r.result:
                for m in r.result["push"]:
                    await self.send(m)
                # The turn left a draft: ask back after pushing the results (B-4).
                # このターンは下書きを残した：結果を送ってから聞き返す（B-4）。
                if r.result.get("confirm"):
                    await self._ask(r.turn_id, r.result["confirm"])
            else:
                await self._fallback(r)

    async def _fallback(self, r: Any) -> None:
        """The narrator failed all three times (`turns.status = "failed"`): the frontend is still waiting for the turn,
        so give a result by kind that doesn't change the world.

        ナレーターが 3 回ともうまくいかなかった（`turns.status = "failed"`）：フロントエンドはまだこのターンを待っている
        ので、種類ごとに世界を変えない結果を返す。
        """
        if r.kind == "talk":
            await self.send(
                {
                    "type": "turn_settled",
                    "turnId": r.turn_id,
                    "outcome": r.outcome or "no_response",
                    "eventIds": await self._visible_ids(r.turn_id),
                    "minutes": int(r.minutes or 0),
                }
            )
        elif r.kind == "action":
            await self.send(
                {
                    "type": "action_result",
                    "clientMsgId": r.client_msg_id or r.turn_id,
                    "status": "refused",
                    "eventIds": [],
                    "minutes": 0,
                    "narration": narrate_fallback("refused"),
                }
            )
        # The answer failed all three times: the draft is still open, and the narrator writes the timeout task once it
        # expires.
        # 答えを 3 回とも処理できなかった：下書きはまだ開いており、期限が来たらナレーターがタイムアウトのタスクを書く。
        elif r.kind in ("confirm", "ending"):
            return
        elif r.kind == "plan":
            run = await self._run()
            left = max(0, PLAN_TRIES - run.plan_tries)
            to = {"turnId": r.turn_id} if (r.request or {}).get("mode") == "voice" else {"clientMsgId": r.client_msg_id}
            await self.send(
                {"type": "act_plan_result", **to, "accepted": False, "narration": [REFUSAL_FALLBACK], "triesLeft": left}
            )
        else:
            err = error_msg("internal", "エラーが起きました。")
            err["error"]["retryable"] = True
            await self.send(err)

    async def _visible_ids(self, turn_id: str) -> list[str]:
        evs = await self.gw.visible_events(self.pid, 0, 10_000)
        return [e["eventId"] for e in evs if e.get("turnId") == turn_id]

    async def _observe(self, turn_id: str, character: str, text: str | None, said: str | None = None) -> None:
        """Run a character's final through the output-side monitor (B-12, 2.11): spoilers, Model Armor, question ratio;
        two spoiler lines in a row rebuild the session. said = the player's final for this turn (a term the player
        said themselves isn't a spoiler when the character repeats it). The Span holds only the playthrough, turn,
        character, fact IDs and RAI category, never the words said or the matched term (data-design section 8).

        登場人物の確定文を出力側モニターにかける（B-12、2.11）：ネタバレ、Model Armor、質問の割合。
        ネタバレが 2 文続いたらセッションを作り直す。said = このターンのプレイヤーの確定文（プレイヤー自身が言った語を登
        場人物が続けて言ってもネタバレにならない）。Span にはプレイ、ターン、登場人物、事実 ID、RAI の分類だけを入れ、
        発言そのものやヒットした語は入れない（data-design 第 8 節）。
        """
        if not text:
            return
        async with self.gw.engine.connect() as c:
            st = await store.sim_state(c, self.pid)
        o = self.monitor.observe(character, text, st, said=said)
        armor = self.gw.screener.armor
        harmful = False
        failed = False
        categories: list[str] = []
        try:
            got = await asyncio.wait_for(armor.screen_response(text), self.gw.screener.armor_deadline)
            harmful = got.harmful
            categories = [k for k, v in got.rai.items() if v == "HIGH"]
        # Second layer: errors and timeouts count as no hit.
        # 第 2 層：エラーやタイムアウトはヒットなし。
        except Exception:
            failed = True
            log.info("No Model Armor result for character output (%s) / Model Armor の結果なし", character)
        by = o.counts()
        if armor_usd := cost_usd(armor, text):
            by["cost_armor_usd"] = armor_usd
        if failed:
            by["armor_errors"] = 1
        rebuild = o.rebuild and character in self.sessions and not self.guard.paused
        if rebuild:
            by["output_rebuilds"] = 1
        hit = {"playthrough_id": self.pid, "turn_id": turn_id, "character": character, "rebuild": rebuild}
        if o.spoilers:
            with self.gw.tracer.span("monitor.hit", **hit, kind="spoiler", fact_ids=[h.fact for h in o.spoilers]):
                pass
        if harmful:
            by["output_harmful"] = 1
            with self.gw.tracer.span("monitor.hit", **hit, kind="harmful", category=sorted(categories)):
                pass
        async with self.gw.engine.begin() as c:
            await store.count(c, self.pid, **by)
        if rebuild:
            self.monitor.rebuilt(character)
            await self._rebuild(character)

    async def on_commit(self, payload: Json) -> None:
        await self.push()
        await self.voices.refresh()

    # —— Receiving / 受信 ——

    async def hello(self, msg: Json) -> None:
        # First let the turn cut off on the old connection be written, so lastTurn is that turn (lost, or handed over
        # as usual).
        # 古い接続で切れたターンを先に書かせる。そうすれば lastTurn はそのターンになる（lost、またはいつもどおり渡され
        # た）。
        await self.gw.handed(self.pid)
        async with self.gw.engine.connect() as c:
            last_seq = int(
                await c.scalar(select(playthroughs.c.last_seq).where(playthroughs.c.playthrough_id == self.pid)) or 0
            )
            done = (
                await c.execute(
                    select(turns.c.turn_id, turns.c.result)
                    .where(
                        turns.c.playthrough_id == self.pid,
                        turns.c.kind.in_(ANSWERED),
                        turns.c.status.in_(("done", "failed")),
                    )
                    .order_by(turns.c.settled_at)
                )
            ).all()
            # Results judged before this connection are not pushed again: set pieces are not resent (3.14); end of act
            # and landing are covered by welcome.pending (section 4).
            # この接続より前に判定済みのものは結果を送り直さない：固定演出は再送せず（3.14）、幕末と着地は
            # welcome.pending で補う（第 4 節）。
            self.settled = {r.turn_id for r in done}
            last_turn = await self._last_turn(c)
            pt = await self.gw.pt(c, self.pid)
            voice_now = await self.gw.voice_state(c, self.pid, self.user_id)
        # B-14: if already degraded (spending cap hit, today used up, switch off), don't push degraded again; welcome
        # carries it.
        # B-14：すでに縮退している（支出が上限、今日の分を使い切った、スイッチがオフ）なら degraded は送り直さない。
        # welcome に入っている。
        await self.voices.settle()
        asking = await self._pending_confirm()
        await self.guard.load()
        if pt is not None:
            self.characters = pt.book.characters
            self.monitor.attach(pt.book)
        await self._resume(last_turn is not None)
        await self.send(
            {
                "type": "welcome",
                "lastSeq": last_seq,
                "voice": voice_now,
                "lastTurn": last_turn,
                "pending": pending(pt.run if pt is not None else None, asking, safety_pause=self.guard.paused),
            }
        )
        ending_id: str | None = None
        # Already in the ending on reconnect: push ending_started again (B-9).
        # 再接続時にすでにエンディングに入っている：ending_started をもう一度送る（B-9）。
        if pt is not None and pt.status == "ended":
            request, ending_id = await self._ending_row()
            if request is not None:
                await self.send(
                    {"type": "ending_started", "trigger": request["trigger"], "staging": request["staging"]}
                )
                self.start_ending()
        async with self.push_lock:
            self.sent_seq = min(int(msg["lastSeq"]), last_seq)
        resend = again([r.result for r in done], self.sent_seq, last_seq)
        await self.push()
        if resend:
            async with self.push_lock:
                for m in resend:
                    await self.send(m)
        if ending_id is not None:
            await self.send({"type": "ending_ready", "endingId": ending_id})

    async def _resume(self, reconnect: bool) -> None:
        """Take over the Live sessions and recent conversation parked before the disconnect (B-11, `Voices.adopt`).
        Trace: gateway.resume (without the words said). reconnect: the playthrough has already had conversation
        (there is a lastTurn), so this isn't the first connection after the opening.

        切断前に預けた Live セッションと直近の会話を引き継ぐ（B-11、`Voices.adopt`）。Trace：gateway.resume（発言そのも
        のは含めない）。reconnect：このプレイですでに会話している（lastTurn がある）、つまり開始後の最初の接続ではない。
        """
        p = await self.voices.adopt()
        carried = len(p.sessions) if p is not None else 0
        recent = sum(len(x) for x in p.recent.values()) if p is not None else 0
        with self.gw.tracer.span(
            "gateway.resume",
            playthrough_id=self.pid,
            reconnect=reconnect,
            gap_ms=round((time.monotonic() - p.at) * 1000) if p is not None else -1,
            carried=carried,
            recent_turns=recent,
            resume_kind="carried" if carried else "recent" if recent else "cold",
        ):
            pass
        # The first connection after the opening isn't resumed play.
        # 開始後の最初の接続は続きからのプレイとみなさない。
        if reconnect or p is not None:
            self.voices.resumed_at = time.monotonic()

    async def _last_turn(self, c: Any) -> Json | None:
        """The last turn before the disconnect (section 4). A retracted turn is settled with both texts null (the words
        were cleared, B-4); for the character's words the first line is taken (an intent confirmation's question
        also hangs under the original turn).

        切断前の最後のターン（第 4 節）。取り消したターンは settled で、2 つの文はどちらも null（発言は消去済み、B-4）。
        登場人物の言葉は最初の 1 文を取る（意図の確認の聞き返しも元のターンの下にぶら下がる）。
        """
        row = (
            await c.execute(
                select(turns.c.turn_id, turns.c.character, turns.c.status)
                .where(turns.c.playthrough_id == self.pid, turns.c.kind.in_(("talk", "plan")))
                .order_by(turns.c.created_at.desc())
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        texts: dict[str, str | None] = {}
        for speaker, text in (
            await c.execute(
                select(utterances.c.speaker, utterances.c.text)
                .where(utterances.c.turn_id == row.turn_id)
                .order_by(utterances.c.recorded_at)
            )
        ).all():
            texts.setdefault(speaker, text)
        if row.status == "retracted":
            texts = {}
        return {
            "turnId": row.turn_id,
            "character": row.character,
            "status": "settled"
            if row.status in ("done", "failed", "retracted")
            else "lost"
            if row.status == "lost"
            else "pending",
            "playerText": texts.get("player"),
            "characterText": texts.get(row.character),
        }

    async def focus(self, character: str) -> None:
        if not self.characters.get(character, {}).get("talkable"):
            log.info("The focused character doesn't exist or can't talk / focus の登場人物がいないか話せない")
            await self.send(error_msg("invalid_request", "この人とは話せません。"))
            return
        await self.voices.focus(character)

    async def forgot(self, turn_ids: tuple[str, ...], character: str) -> bool:
        """An entry was deleted in the 記憶帳 (B-13): drop the recent conversation of those turns; if the character's
        session is open, rebuild it with a new situation description (pushing `session_preparing { reason: "rebuild"
        }`). Returns whether it was rebuilt.

        記憶帳で 1 件削除した（B-13）：そのターンの直近の会話を捨てる。この登場人物のセッションが開いていれば新しい状況
        説明で作り直す（`session_preparing { reason: "rebuild" }` を送る）。作り直したかどうかを返す。
        """
        gone = set(turn_ids)
        for kept in self.recent.values():
            kept[:] = [(x, r) for x, r in kept if x not in gone]
        if character not in self.sessions:
            return False
        await self._rebuild(character)
        return True

    async def _rebuild(self, character: str) -> None:
        """Rebuild the character's session after a retraction (backend-design 3.2): the new session carries only the
        non-retracted recent turns, so the character truly never heard that turn.

        取り消しの後でこの登場人物のセッションを作り直す（backend-design 3.2）：新しいセッションには直近のターンのうち取
        り消していないものだけを持たせ、登場人物は本当にそのターンを聞かなかったことになる。
        """
        await self.voices.rebuild(character)

    async def _start(self, msg: Json, mode: str) -> Turn | None:
        if self.focused is None:
            log.info("%s with no focused character / focus の登場人物がいない", msg["type"])
            await self.send(error_msg("invalid_request", "話す相手を選んでください。"))
            return None
        # After degrading, text turns go on as usual and the character answers in text (B-14).
        # 縮退後も文字のターンはいつもどおりで、登場人物は文字で答える（B-14）。
        if not await self.voices.can_speak() and mode != "text":
            await self.send(error_msg("voice_unavailable", "いまは声で話せません。"))
            return None
        await self._cut()
        prev = self.turn if self.turn is not None and self.turn.ended else None
        session = self.sessions.get(self.focused)
        self.turn = Turn(msg["turnId"], msg["turnSeq"], self.focused, mode, session, prev=prev)
        self.memory[self.turn.turn_id] = self.turn
        return self.turn

    async def _cut(self) -> None:
        """A new turn interrupts a character still speaking (3.2 activity_start): stop forwarding the old turn's
        chunks, finish sending the old turn's interrupted and its partial final, then start the new turn. The old
        turn is still handed to the narrator.

        新しいターンがまだ話している登場人物に割り込む（3.2 activity_start）：古いターンの断片の転送をやめ、
        古いターンの interrupted と途中までの確定文を送り終えてから新しいターンを始める。古いターンもいつもどおり
        ナレーターに渡す。
        """
        old = self.turn
        if old is not None and old.speaking:
            assert old.stream is not None
            old.stream.cancel()
            await old.quiet.wait()

    def drop(self) -> None:
        """The connection dropped: a turn the character hadn't finished is recorded as lost; one already finished and
        waiting for its final is handed over as usual. A turn cut off while the player was still holding the talk
        button (no activity_end, the character hadn't spoken) is lost too, otherwise lastTurn would be the previous
        turn and the frontend couldn't say 「もう一度」 (#109 review).

        接続が切れた：登場人物が話し終えていないターンは lost と記録し、話し終えて確定文を待っているものはいつもどおり渡
        す。プレイヤーがまだ話すボタンを押したまま切れたターン（activity_end がなく、登場人物もまだ話していない）
        も lost にする。そうしないと lastTurn が前のターンになり、フロントエンドが「もう一度」と言えない（#109 の
        レビュー）。
        """
        old = self.turn
        if old is None:
            return
        if old.speaking:
            assert old.stream is not None
            old.lost = True
            old.stream.cancel()
        elif not old.ended and old.mode == "voice" and old.turn_id in self.memory:
            old.ended = old.lost = True
            # No answer to wait for; _finish writes the lost row directly. / 待つ答えはないので、
            # _finish が lost の行をそのまま書く。
            old.stream = asyncio.ensure_future(asyncio.sleep(0))
            self.gw.hand(self.pid, self._finish(old))

    def audio_in(self, frame: bytes) -> None:
        if self.ending:  # in the ending: drop upstream audio / エンディング中：上り音声は捨てる
            return
        if self.plan is not None and len(frame) >= 5 and int.from_bytes(frame[1:5], "big") == self.plan.turn_seq:
            self._plan_audio(self.plan, frame)
            return
        t = self.turn
        if len(frame) < 5 or frame[0] != FRAME_MIC or t is None or t.ended or t.mode != "voice":
            return
        if int.from_bytes(frame[1:5], "big") != t.turn_seq:
            return  # drop upstream chunks of an ended turn (3.1) / 終わったターンの上りの断片は捨てる（3.1）
        # The session is still opening: buffer first (B-10). / セッションを開いている最中：先にためておく（B-10）。
        if t.session is None or not t.session.alive:
            t.early.append(frame[5:])
            return
        for ev in t.session.audio_in(frame[5:]):
            if ev.kind == "input_partial":
                t.heard = ev.text
                self.gw.spawn(
                    self.send(
                        {
                            "type": "transcript",
                            "turnId": t.turn_id,
                            "speaker": "player",
                            "text": ev.text,
                            "final": False,
                        }
                    )
                )

    def respond(self, t: Turn) -> None:
        t.ended = True
        if t.mode == "text":
            t.heard = t.text
            self.guard.start(t, t.text)
        if t.mode == "text" and self.voices.off is not None:
            t.stream = asyncio.ensure_future(self._reply_text(t))
        else:
            t.stream = asyncio.ensure_future(self._stream(t))
        self.gw.hand(self.pid, self._finish(t))

    def suggest_later(self, character: str, t: Turn | None = None) -> None:
        """Suggested lines (B-21, ux-design 7.8, contract 3.5): when the character finishes a turn or a session has
        just become ready, generate 2〜3 in the background and push them.

        候補のセリフ（B-21、ux-design 7.8、契約 3.5）：登場人物がターンを話し終えたとき、またはセッションの準備ができた
        ところで、裏で 2〜3 個生成して送る。
        """
        if self.ending or self.guard.paused or self.closed.is_set():
            return
        self.gw.spawn(self._suggest(character, t))

    async def _suggest(self, character: str, t: Turn | None) -> None:
        """Generated from this turn's two lines (or only the situation when there are none) and the actions available
        right now; not generated automatically in economy tier or when degraded (backend-design 5.3). If the player
        starts talking again or switches characters during generation, nothing is pushed (it's stale). Not stored;
        only the cost is recorded (`cost_suggest_usd`).

        このターンの 2 つの発言（なければ状況だけ）といまできるアクションから生成する。節約モードや縮退中は自動では生成
        しない（backend-design 5.3）。生成中にプレイヤーがまた話し始めたり登場人物を替えたりしたら送らない（古くなっ
        た）。DB には保存せず、費用だけを記録する（`cost_suggest_usd`）。
        """
        async with self.gw.engine.connect() as c:
            pt = await self.gw.pt(c, self.pid)
            st = await store.sim_state(c, self.pid)
            tier = await budget.tier_of(c, self.pid)
        if pt is None or st is None or budget.policy(tier).candidates_on_demand:
            return
        spend = Spend()
        items = await self.gw.replier.suggest(
            pt.book,
            st,
            character,
            spend,
            player=t.heard if t is not None else None,
            reply=t.said if t is not None else None,
            actions=[a["label"] for a in open_affordances(pt.book, st)],
        )
        usd = spend.usd.get("suggest", 0.0)
        if usd:
            async with self.gw.engine.begin() as c:
                m = playthrough_metrics.c
                await c.execute(
                    update(playthrough_metrics)
                    .where(m.playthrough_id == self.pid)
                    .values(cost_suggest_usd=m.cost_suggest_usd + usd)
                )
        now = self.turn
        # A new turn started.
        # 新しいターンが始まった。
        busy = now is not None and now is not t and not now.submitted.is_set()
        if items is None or busy or self.focused != character or self.ending or self.guard.paused:
            return
        msg: Json = {"type": "suggestions", "character": character, "items": items}
        if t is not None:
            msg["turnId"] = t.turn_id
        await self.send(msg)

    async def _reply_text(self, t: Turn) -> None:
        """A text turn after degrading (B-14, backend-design 3.2 "degrading to text only"): the character answers with
        the text model (the narrator's `reply`, with the same persona and situation), first pushing the final
        (`source: "live"`), then `turn_complete { audio: false }` (contract 3.3). After that it is handed to the
        narrator as usual. If both attempts fail: no final, the same as the character not answering. The cost goes
        into `cost_reply_usd`.

        縮退後の文字のターン（B-14、backend-design 3.2「文字のみへの縮退」）：登場人物はテキストモデルで答え（ナレーター
        の `reply`。人物設定と状況は同じもの）、まず確定文（`source: "live"`）を送り、次に `turn_complete { audio:
        false }` を送る（契約 3.3）。そのあといつもどおりナレーターに渡す。2 回ともだめなら確定文はなく、
        登場人物が答えなかったのと同じ。費用は `cost_reply_usd` に入れる。
        """
        t.released = time.monotonic()
        async with self.gw.engine.connect() as c:
            pt = await self.gw.pt(c, self.pid)
            st = await store.sim_state(c, self.pid)
        if pt is not None and st is not None and t.text:
            spend = Spend()
            reply = await self.gw.replier.reply(
                pt.book,
                st,
                TurnInput(character=t.character, player=t.text),
                spend,
                notes=self.monitor.notes(t.character),
            )
            usd = spend.usd.get("reply", 0.0)
            if usd:
                async with self.gw.engine.begin() as c:
                    m = playthrough_metrics.c
                    await c.execute(
                        update(playthrough_metrics)
                        .where(m.playthrough_id == self.pid)
                        .values(cost_reply_usd=m.cost_reply_usd + usd)
                    )
            if reply is not None:
                t.said = reply
                await self._final(t)
        await self._complete(t)

    async def _stream(self, t: Turn) -> None:
        """Turn the (fake) Live answer into downstream messages. On interruption or disconnect this task is cancelled
        and stops wherever it is.

        （偽）Live の答えを下りのメッセージにする。割り込みや切断でこのタスクは取り消され、その場で止まる。
        """
        wait = self.ready.get(t.character)
        # The session is still being prepared (rebuild): wait until ready before sending in (B-4).
        # セッションはまだ準備中（作り直し）：準備ができてから送り込む（B-4）。
        if wait is not None and not wait.is_set():
            await wait.wait()
        if t.session is None or not t.session.alive:
            t.session = self.sessions.get(t.character)
        session = t.session
        if session is None or not session.alive:
            raise LiveLost("No usable session / 使えるセッションがない")
        early, t.early = t.early, []
        # Upstream audio buffered before ready (partial subtitles aren't pushed now; the final is as usual).
        # 準備前にためた上り音声（途中の字幕はここでは送らず、確定文はいつもどおり）。
        for pcm in early:
            session.audio_in(pcm)
        t.released = time.monotonic()
        before_s = session.audio_seconds
        if t.mode == "arrival":
            said = session.speak_first()
        elif t.mode == "confirm":
            said = session.speak_first(t.text)
        else:
            said = session.respond(t.text)
        async for ev in said:
            if ev.kind == "input_final":
                t.heard = ev.text
                self.guard.start(t, ev.text)
                await self.send(
                    {"type": "transcript", "turnId": t.turn_id, "speaker": "player", "text": ev.text, "final": True}
                )
                continue
            await t.flowing.wait()  # B-15: hold the character during the review / 見直しの間は登場人物を止める
            if ev.kind == "audio":
                if t.first_audio is None:
                    t.first_audio = time.monotonic()
                t.pcm_out.extend(ev.pcm)
                await self.send_bytes(audio.frame(t.turn_seq, ev.pcm))
            elif ev.kind == "output_partial":
                t.said = ev.text
                await self.send(
                    {"type": "transcript", "turnId": t.turn_id, "speaker": t.character, "text": ev.text, "final": False}
                )
            elif ev.kind == "turn_complete":
                await self._complete(t)
            elif ev.kind == "output_final":
                # Audio but not a single character of text: fallback transcription (S-071).
                # 音声はあるが文字が 1 文字もない：補完の文字起こし（S-071）。
                if ev.text is None and t.pcm_out:
                    await self._fallback_final(t)
                elif ev.text is not None:
                    t.said = ev.text
                    await self._final(t)
            elif ev.kind == "usage":
                await self.voices.account(t, ev, session, before_s)

    async def _complete(self, t: Turn) -> None:
        """turn_complete: the character's side of the turn is finished (or Live dropped, and it ends here).

        turn_complete：登場人物の側でこのターンを話し終えた（または Live が切れて、ここで終わり）。
        """
        ms = None if t.first_audio is None or t.released is None else round((t.first_audio - t.released) * 1000)
        t.complete = True
        t.done_at = time.monotonic()
        await self.send(
            {
                "type": "turn_complete",
                "turnId": t.turn_id,
                "audio": t.first_audio is not None,
                "metrics": {"serverReleaseToFirstAudioMs": ms},
            }
        )

    async def _fallback_final(self, t: Turn) -> None:
        """Fallback transcription (backend-design 3.1): 3-second deadline, no retry; on failure a final with `text:
        null` is still pushed.

        補完の文字起こし（backend-design 3.1）：締め切り 3 秒、再試行なし。失敗しても `text: null` の確定文を送る。
        """
        # A turn stopped by the out-of-story card has no character final (the 3.3 exception, B-12).
        # 物語の外のカードで止めたターンには登場人物の確定文がない（3.3 の例外、B-12）。
        if t.paused:
            return
        t.source = "fallback"
        heard = await fallback_text(self.gw.transcriber, bytes(t.pcm_out))
        t.pcm_out = bytearray()
        if heard is not None:
            t.said = heard.text
            if self.gw.live_ledger is not None:
                self.gw.live_ledger.add(
                    kind=f"live.fallback/{self.pid}", model="transcribe", usage=heard.usage, cost=heard.cost
                )
        t.final = True
        await self.send(
            {
                "type": "transcript",
                "turnId": t.turn_id,
                "speaker": t.character,
                "text": t.said if heard is not None else None,
                "final": True,
                "source": "fallback",
            }
        )
        if heard is not None:
            self._watch(t)

    async def _final(self, t: Turn) -> None:
        # A turn stopped by the out-of-story card has no character final (the 3.3 exception).
        # 物語の外のカードで止めたターンには登場人物の確定文がない（3.3 の例外）。
        if t.paused:
            return
        t.final = True
        await self.send(
            {
                "type": "transcript",
                "turnId": t.turn_id,
                "speaker": t.character,
                "text": t.said,
                "final": True,
                "source": "live",
            }
        )
        self._watch(t)

    def _watch(self, t: Turn) -> None:
        """Every character final (from Live, from fallback transcription, or partial on interruption) goes through the
        output-side monitor (B-12); not awaited.

        登場人物の確定文（Live のもの、補完の文字起こしのもの、割り込まれて途中までのもの）はすべて出力側モニターにかけ
        る（B-12）。待たない。
        """
        if t.said:
            self.gw.spawn(self._observe(t.turn_id, t.character, t.said, t.heard))

    async def _finish(self, t: Turn) -> None:
        """Wait for the character to finish (or be interrupted, or disconnect), then hand the turn to the narrator. An
        interrupted turn gets interrupted and its partial final (3.3); one not finished at disconnect is recorded as
        lost.

        登場人物が話し終える（または割り込まれる、切断される）のを待ってから、このターンをナレーターに渡す。
        割り込まれたものには interrupted と途中までの確定文を送り（3.3）、切断時に話し終えていなかったものは lost
        と記録する。
        """
        assert t.stream is not None
        await asyncio.wait({t.stream})
        failed = not t.stream.cancelled() and t.stream.exception() is not None
        if failed:
            exc = t.stream.exception()
            # Live dropped mid-way: close it out as interrupted, hand it to the narrator, then reopen the session
            # (B-10).
            # Live が途中で切れた：割り込みとして締め、ナレーターに渡し、セッションを開き直す（B-10）。
            if isinstance(exc, LiveLost):
                log.info("Live dropped mid-way (%s, %s) / Live が途中で切れた", t.turn_id, exc)
                t.dropped = True
            else:
                log.error("Live's answer failed mid-way (%s) / Live の答えが途中でエラー", t.turn_id, exc_info=exc)
        if t.done_at is None:
            t.done_at = time.monotonic()
        # A retracted turn gets no interrupted and no partial final (B-4).
        # 取り消したターンには interrupted も途中までの確定文も送らない（B-4）。
        if not t.lost and not t.retracted and not t.paused:
            # Live dropped: the character's side of the turn ends here (not a player interruption, #111 frontend
            # review).
            # Live が切れた：登場人物の側のターンはここで終わり（プレイヤーの割り込みではない、#111 フロントエンドの
            # レビュー）。
            if t.dropped and not t.complete:
                await self._complete(t)
                with self.gw.tracer.span(
                    "live.turn",
                    playthrough_id=self.pid,
                    turn_id=t.turn_id,
                    character=t.character,
                    mode=t.mode,
                    status="lost",
                    first_audio_ms=-1
                    if t.first_audio is None or t.released is None
                    else round((t.first_audio - t.released) * 1000),
                ):
                    pass
                if t.first_audio is not None and not t.final and t.said is None and t.pcm_out:
                    await self._fallback_final(t)
            elif t.stream.cancelled() and not t.complete:
                await self.send({"type": "interrupted", "turnId": t.turn_id})
            # Interrupted before the character produced any text: no final (like a turn with no answer).
            # 登場人物が文字を出す前に割り込まれたものには確定文がない（答えのないターンと同じ）。
            if not t.final and t.said is not None:
                await self._final(t)
        t.quiet.set()
        # Wait for safety screening before handing to the narrator (B-12): never commit and then pause.
        # ナレーターに渡す前に安全チェックを待つ（B-12）：commit してから一時停止することはない。
        screen = await self.guard.result(t)
        if t.prev is not None and not t.retracted:
            await t.prev.submitted.wait()
            t.prev = None
        try:
            if t.paused:
                await self.guard.write_paused(t)
            elif t.retracted:
                await self._write_retracted(t)
            else:
                # From here on, retraction takes the database path. / ここから先の取り消しは DB 側の経路を通る。
                t.handing = True
                await self._submit(t, screen)
                if t.said and not t.lost and not self._silent(t) and t.mode in ("voice", "text", "arrival"):
                    self.suggest_later(t.character, t)
        finally:
            self.memory.pop(t.turn_id, None)
            t.submitted.set()
            self.voices.after_turn(t.character)

    async def _submit(self, t: Turn, screen: Screen | None = None) -> None:
        """Write the words said and the turn's task in one transaction, then call the narrator (after turn_complete). A
        lost turn only keeps the record and doesn't call the narrator. The line a character speaks first on landing
        only stores the words (its task row was already written on act_landed) and isn't handed to the narrator
        (3.11).

        発言そのものとこのターンのタスクを同じトランザクションで書き、それからナレーターを呼ぶ（turn_complete の後）。
        lost のものは記録だけ残し、ナレーターは呼ばない。着地で登場人物が先に話す発言は発言そのものだけを保存し（タスク
        の行は act_landed を受け取ったときに書き済み）、ナレーターには渡さない（3.11）。
        """
        async with self.gw.engine.begin() as c:
            st = await store.sim_state(c, self.pid)
            now_t = st["t"] if st is not None else 0
            # The question hangs under the original turn (B-4). / 聞き返しは元のターンの下にぶら下げる（B-4）。
            if t.mode in ("arrival", "confirm"):
                await store.add_utterance(
                    c,
                    self.gw.ids,
                    self.pid,
                    t.owner or t.turn_id,
                    speaker=t.character,
                    text=t.said,
                    t=now_t,
                    source="live",
                )
            else:
                exists = await c.scalar(select(turns.c.turn_id).where(turns.c.turn_id == t.turn_id))
                if exists is not None:
                    log.info("Turn already handed over (%s) / このターンはすでに渡した", t.turn_id)
                    return
                await store.enqueue(
                    c,
                    self.gw.ids,
                    self.pid,
                    kind="talk",
                    turn_id=t.turn_id,
                    input_mode=t.mode,
                    character=t.character,
                    turn_seq=t.turn_seq,
                    status="lost" if t.lost or self.ending else "failed" if self._silent(t) else "pending",
                    commit_after=self._window(t.done_at),
                    # lost turns aren't handed to the narrator / lost のものはナレーターに渡さない
                    flags=sorted(screen.flags) if screen is not None and not t.lost else None,
                )
                # Live dropped before the first audio: no answer, not handed to the narrator (turn_settled no_response).
                # Live が最初の音声より前に切れた：答えはなく、ナレーターに渡さない（turn_settled no_response）。
                if self._silent(t):
                    await c.execute(
                        update(turns)
                        .where(turns.c.turn_id == t.turn_id)
                        .values(outcome="no_response", minutes=0, settled_at=func.now())
                    )
                heard = screen.masked if screen is not None and screen.masked is not None else t.heard
                await store.add_utterance(c, self.gw.ids, self.pid, t.turn_id, speaker="player", text=heard, t=now_t)
                await store.add_utterance(
                    c, self.gw.ids, self.pid, t.turn_id, speaker=t.character, text=t.said, t=now_t, source=t.source
                )
                # Audio, but no text at all (including fallback transcription) (3.1).
                # 音声はあるが、文字（補完の文字起こしを含む）がまったくない（3.1）。
                if t.said is None and t.first_audio is not None:
                    await c.execute(
                        update(turns).where(turns.c.turn_id == t.turn_id).values(character_text_missing=True)
                    )
        if t.mode == "confirm":
            if t.asking is not None:
                await self._push_confirm(t.asking)
            return
        if t.mode == "arrival":
            return
        if self._silent(t):
            await self.push()
            return
        if not t.lost and not self.ending:
            kept = self.recent.setdefault(t.character, [])
            kept.append((t.turn_id, Recent(t.heard, t.said)))
            del kept[:-RECENT_TURNS]
            self.gw.kick(self.pid)

    @staticmethod
    def _silent(t: Turn) -> bool:
        return t.dropped and t.first_audio is None and not t.lost

    def _window(self, since: float | None) -> float | None:
        """Seconds left in the commit window (turn_complete or final + 3 seconds, shortened by ZJ_SPEED); no window at
        speed 0.

        提出の時間枠の残り秒数（turn_complete または確定文 + 3 秒、ZJ_SPEED で短縮）。速度 0 なら時間枠はない。
        """
        full = COMMIT_WINDOW_S * self.gw.settings.speed
        if full <= 0:
            return None
        return max(0.0, full - (time.monotonic() - since)) if since is not None else full

    async def _write_retracted(self, t: Turn) -> None:
        """A turn retracted while still in memory: write a retracted row, without the words said, not handed to the
        narrator (3.6).

        メモリにある間に取り消したターン：retracted の行を書き、発言そのものは書かず、ナレーターにも渡さない（3.6）。
        """
        async with self.gw.engine.begin() as c:
            exists = await c.scalar(select(turns.c.turn_id).where(turns.c.turn_id == t.turn_id))
            if exists is not None:
                return
            await store.enqueue(
                c,
                self.gw.ids,
                self.pid,
                kind="talk",
                turn_id=t.turn_id,
                input_mode=t.mode,
                character=t.character,
                turn_seq=t.turn_seq,
                status="retracted",
            )
            await c.execute(
                update(turns)
                .where(turns.c.turn_id == t.turn_id)
                .values(outcome="retracted", minutes=0, settled_at=func.now())
            )
            await store.count_retracted(c, self.pid)

    async def handle(self, msg: Json) -> None:
        t = msg["type"]
        if t == "hello":
            await self.hello(msg)
        elif t == "ping":
            await self.send({"type": "pong"})
        elif self.sent_seq < 0:
            log.info("%s before hello / hello より前", t)
            await self.send(error_msg("invalid_request", "うまく送れませんでした。"))
        elif t == "safety_resume":
            await self.guard.resume()
        # The out-of-story card is open: the story is paused and nothing is accepted until returning to it (B-12).
        # 物語の外のカードが開いている：物語は止まっており、物語に戻るまで受け付けない（B-12）。
        elif self.guard.paused and t in PAUSED_REFUSED:
            log.info("%s while paused / 一時停止中", t)
            await self.send(error_msg("invalid_request", INVALID_REQUEST))
        elif t == "focus" and self.guard.paused:
            log.info("focus while paused: no session opened / 一時停止中の focus：セッションを開かない")
        # In the ending: no more sessions opened, no warm-ups (B-9).
        # エンディング中：もうセッションを開かず、ウォームアップもしない（B-9）。
        elif t in ("focus", "near") and self.ending:
            log.info("%s ignored in the ending / エンディング中は処理しない", t)
        elif t == "focus":
            await self.focus(msg["character"])
        elif t == "unfocus":
            self.voices.unfocus()
        elif t == "near":
            self.voices.near(msg["character"])
        elif t == "far":
            self.voices.far(msg["character"])
        elif t == "activity_start":
            if msg.get("purpose") == "act_plan":
                await self.plan_start(msg)
            elif await self._refuse_if_ended():
                return
            else:
                await self._start(msg, "voice")
        elif t == "activity_end":
            if self.plan is not None and self.plan.turn_id == msg["turnId"]:
                plan, self.plan = self.plan, None
                await self.plan_end(plan)
                return
            turn = self.turn
            if turn is not None and turn.turn_id == msg["turnId"] and not turn.ended:
                self.respond(turn)
        elif t == "text":
            if await self._refuse_if_ended():
                return
            turn = await self._start(msg, "text")
            if turn is not None:
                turn.text = msg["text"]
                self.respond(turn)
        elif t == "action":
            await self.action(msg)
        elif t == "act_choose":
            await self.choose(msg)
        elif t == "act_propose":
            await self.propose(msg)
        elif t == "act_landed":
            await self.landed(msg)
        elif t == "turn_retract":
            await self.retract(msg["turnId"])
        elif t == "confirm_answer":
            await self.confirm_answer(msg)
        else:
            log.info("%s not handled yet, ignored / まだ処理しないので無視", t)

    # —— Retraction (B-4, 3.6) / 取り消し ——

    async def retract(self, turn_id: str) -> None:
        """Retract a turn according to how far it got (the table in the card). After a conversation turn is retracted,
        push turn_settled (retracted) and rebuild the session; a plan said by voice gets neither act_plan_result nor
        turn_settled and doesn't count as a try.

        ターンを取り消す：どの段階まで進んだかに従う（カードの表）。会話のターンを取り消したら turn_settled（retracted）
        を送ってセッションを作り直す。声で言ったプランには act_plan_result も turn_settled も送らず、
        試行回数にも数えない。
        """
        with self.gw.tracer.span("gateway.retract", playthrough_id=self.pid, turn_id=turn_id) as sp:
            status, kind, stage = await self._retract(turn_id)
            sp.set(status=status)
            if kind is not None:
                sp.set(turn_kind=kind, stage=stage)
        await self.send({"type": "turn_retract_result", "turnId": turn_id, "status": status})
        if status != "retracted" or kind != "talk":
            return
        self.settled.add(turn_id)
        await self.send(
            {"type": "turn_settled", "turnId": turn_id, "outcome": "retracted", "eventIds": [], "minutes": 0}
        )
        for kept in self.recent.values():
            kept[:] = [(x, r) for x, r in kept if x != turn_id]
        character = self.retracted_with.pop(turn_id, None)
        if character is not None and character in self.sessions:
            await self._rebuild(character)

    async def _retract(self, turn_id: str) -> tuple[str, str | None, str | None]:
        """Returns (retracted / too_late, talk / plan, memory / queued).

        （retracted / too_late、talk / plan、memory / queued）を返す。
        """
        plan = self.plan
        # The plan is still being said: drop it; no final pushed, no task written.
        # プランをまだ話している：捨てる。確定文を送らず、タスクも書かない。
        if plan is not None and plan.turn_id == turn_id:
            plan.retracted = True
            self.plan = None
            async with self.gw.engine.begin() as c:
                await store.count_retracted(c, self.pid)
            return "retracted", "plan", "memory"
        t = self.memory.get(turn_id)
        if t is not None and t.retractable and not t.handing:
            t.retracted = True
            self.retracted_with[turn_id] = t.character
            if t.stream is not None and not t.stream.done():
                t.stream.cancel()  # stop forwarding the turn's downstream audio / 下り音声の転送をやめる
            # The player is still talking: there's no _finish, so write the row here.
            # プレイヤーがまだ話している：_finish がないので、ここで行を書く。
            if not t.ended:
                t.ended = True
                t.quiet.set()
                try:
                    await self._write_retracted(t)
                finally:
                    self.memory.pop(turn_id, None)
                    t.submitted.set()
            else:
                # _finish sees the retraction and writes the row. / _finish が取り消しを見て行を書く。
                await t.submitted.wait()
            return "retracted", "talk", "memory"
        if t is not None and t.handing:
            # Being written to the database: wait until done, then take the database path.
            # DB に書き込み中：書き終わるのを待ち、DB 側の経路を通る。
            await t.submitted.wait()
        async with self.gw.engine.begin() as c:
            row = await c.scalar(select(turns.c.character).where(turns.c.turn_id == turn_id))
            kind = await store.retract_queued(c, self.pid, turn_id)
        if kind is None:
            return "too_late", None, None
        if row is not None:
            self.retracted_with[turn_id] = row
        return "retracted", kind, "queued"

    # —— Intent confirmation (B-4, 3.9) / 意図の確認 ——

    async def _ask(self, turn_id: str, asking: Json) -> None:
        """After the original turn's result is pushed: if the character hasn't asked back yet, the server starts a turn
        to say the question and pushes confirm once it's said; if the character is already asking, the player is no
        longer looking at them, or the player is talking, push confirm directly.

        元のターンの結果を送ったあと：登場人物がまだ聞き返していなければ、サーバーがターンを起こして聞き返しを言わせ、
        言い終えたら confirm を送る。すでに聞き返している、プレイヤーがもうその人を見ていない、プレイヤーが話している最
        中のときは、そのまま confirm を送る。
        """
        who = asking["character"]
        t = self.turn
        busy = t is not None and (not t.ended or t.speaking)
        # Degraded: no spoken question, push confirm directly (the text carries the question, B-14).
        # 縮退中：声で聞き返さず、そのまま confirm を送る（文字に聞き返しが入っている、B-14）。
        off = self.voices.off is not None
        if asking.get("asked") or self.focused != who or busy or who not in self.sessions or off:
            await self._push_confirm(asking)
            return
        turn_seq = SERVER_SEQ + self.served
        self.served += 1
        qid = self.gw.ids.new("turn")
        self.settled.add(qid)
        await self.send(
            {"type": "turn_started", "turnId": qid, "turnSeq": turn_seq, "speaker": who, "reason": "confirm"}
        )
        prev = t if t is not None and t.ended else None
        self.turn = Turn(qid, turn_seq, who, "confirm", self.sessions.get(who), text=asking["prompt"], prev=prev)
        self.turn.owner = turn_id
        self.turn.asking = asking
        self.respond(self.turn)

    def _timeout_s(self) -> float:
        """The confirmation timer: 30 seconds shortened by ZJ_SPEED; 30 seconds at speed 0 (where characters don't wait
        in tests).

        確認のタイマー：30 秒を ZJ_SPEED で短縮する。速度 0（テストで登場人物が待たないとき）は 30 秒のまま。
        """
        return confirm.TIMEOUT_SEC * (self.gw.settings.speed or 1.0)

    async def _push_confirm(self, asking: Json) -> None:
        """Push confirm, record the expiry time on the draft and start the timer. If the draft is already closed (the
        act closed, or another answer arrived first), nothing is pushed.

        confirm を送り、下書きに期限の時刻を記録してタイマーを始める。下書きがすでに閉じている（幕を閉じた、
        別の答えが先に届いた）なら送らない。
        """
        draft_id = asking["draftId"]
        seconds = self._timeout_s()
        async with self.gw.engine.begin() as c:
            found = await c.scalar(
                select(drafts.c.draft_id)
                .where(drafts.c.draft_id == draft_id, drafts.c.playthrough_id == self.pid)
                .with_for_update()
            )
            if found is None or await store.answered(c, self.pid, draft_id):
                log.info("Draft %s already closed, not pushing confirm / 下書きは閉じ済み", draft_id)
                return
            await c.execute(
                update(drafts)
                .where(drafts.c.draft_id == draft_id)
                .values(expires_at=func.clock_timestamp() + timedelta(seconds=seconds))
            )
        await self.send(confirm.confirm_msg(draft_id, asking["character"], asking["prompt"]))
        self._start_timer(draft_id, seconds)

    def _start_timer(self, draft_id: str, seconds: float) -> None:
        old = self.timers.pop(draft_id, None)
        if old is not None:
            old.cancel()

        async def expire() -> None:
            await asyncio.sleep(seconds)
            async with self.gw.engine.begin() as c:
                written = await store.answer_draft(c, self.gw.ids, self.pid, draft_id, None, "timeout")
            if written is not None:
                self.gw.kick(self.pid)

        self.timers[draft_id] = self.gw.spawn(expire())

    async def confirm_answer(self, msg: Json) -> None:
        """A button answer: if it isn't an open draft of this playthrough (timed out, already answered, closed with the
        act), ignore it and only log.

        ボタンでの答え：このプレイの開いている下書きでなければ（タイムアウト済み、回答済み、幕を閉じて閉じた）無視し、
        ログだけ残す。
        """
        draft_id, option = msg["draftId"], msg["optionId"]
        if option not in confirm.ANSWERS:
            log.info("Unknown optionId in confirm_answer, ignored / 不明な optionId を無視")
            return
        async with self.gw.engine.begin() as c:
            row = (
                (
                    await c.execute(
                        select(drafts.c.expires_at, func.now().label("now"))
                        .where(drafts.c.draft_id == draft_id, drafts.c.playthrough_id == self.pid)
                        .with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            expired = row is not None and row["expires_at"] is not None and row["expires_at"] <= row["now"]
            written = None
            if row is not None and not expired:
                written = await store.answer_draft(c, self.gw.ids, self.pid, draft_id, option, "button")
        if written is None:
            log.info("confirm_answer is not for an open draft, ignored / 開いている下書きではないので無視")
            return
        timer = self.timers.pop(draft_id, None)
        if timer is not None:
            timer.cancel()
        self.gw.kick(self.pid)

    async def _pending_confirm(self) -> Json | None:
        """An unanswered confirmation on reconnect (section 4 pending.confirm, with remainingSec). An expired one is
        closed first (writing the timeout task) and null is returned; one never pushed (its turn hadn't come at
        disconnect) gets 30 seconds from now.

        再接続時にまだ答えていない確認（第 4 節 pending.confirm、remainingSec 付き）。期限切れのものは先に閉じ
        （タイムアウトのタスクを書く）、null を返す。まだ送っていないもの（切断時にまだ順番が来ていなかった）
        は今から 30 秒を数える。
        """
        seconds = self._timeout_s()
        async with self.gw.engine.begin() as c:
            draft = await store.open_draft(c, self.pid, lock=True)
            if draft is None or await store.answered(c, self.pid, draft["draft_id"]):
                return None
            now = cast(datetime, await c.scalar(select(func.clock_timestamp())))
            expires: datetime = draft["expires_at"] or now + timedelta(seconds=seconds)
            expired = expires <= now
            if expired:
                await store.answer_draft(c, self.gw.ids, self.pid, draft["draft_id"], None, "timeout")
            elif draft["expires_at"] is None:
                await c.execute(update(drafts).where(drafts.c.draft_id == draft["draft_id"]).values(expires_at=expires))
        if expired:
            self.gw.kick(self.pid)
            return None
        left = (expires - now).total_seconds()
        self._start_timer(draft["draft_id"], left)
        msg = confirm.confirm_msg(draft["draft_id"], draft["character"], draft["prompt"])
        return {k: msg[k] for k in ("draftId", "character", "prompt", "options", "timeoutSec")} | {
            "remainingSec": max(0, math.ceil(left))
        }

    # —— Actions and end of act (B-3) / アクションと幕末 ——

    async def _run(self) -> Run:
        async with self.gw.engine.connect() as c:
            row = await store.playthrough(c, self.pid)
        return Run.of(row or {})

    async def _refuse_if_ended(self) -> bool:
        """The act is closed and no choice is made yet, or the ending has started (B-9): conversation and actions get
        invalid_request, without a turnId (section 5).

        幕を閉じてまだ選んでいない、またはエンディングに入った（B-9）：会話とアクションには turnId なしで
        invalid_request を返す（第 5 節）。
        """
        if not self.ending and (await self._run()).act_end is None:
            return False
        await self.send(error_msg("invalid_request", INVALID_REQUEST))
        return True

    async def action(self, msg: Json) -> None:
        """Action (3.8): write a task row and call the narrator, without waiting. The verdict, commit and action_result
        are all pushed after the narrator commits.

        アクション（3.8）：タスクを 1 行書いてナレーターを呼び、待たない。判定、commit、action_result
        はすべてナレーターの commit 後に送る。
        """
        request = {k: msg[k] for k in ("clientMsgId", "kind", "target", "params", "actionId") if k in msg}
        async with self.gw.engine.begin() as c:
            row = await store.playthrough(c, self.pid)
            ended = self.ending or row is None or row["act_end"] is not None or row["status"] != "active"
            if not ended:
                await store.enqueue(
                    c, self.gw.ids, self.pid, kind="action", client_msg_id=msg["clientMsgId"], request=request
                )
        if ended:
            await self.send(error_msg("invalid_request", INVALID_REQUEST))
            return
        self.gw.kick(self.pid)

    async def choose(self, msg: Json) -> None:
        """Choosing a destination (3.11): the narrator checks that it is among this time's destinations; if not, it
        answers invalid_choice and writes no events.

        行き先を選ぶ（3.11）：ナレーターは今回の行き先に含まれるかを確かめ、含まれなければ invalid_choice を返し、
        イベントは書かない。
        """
        request = {k: msg[k] for k in ("clientMsgId", "optionId", "enRouteChoice") if k in msg}
        if self.ending:
            await self.send(error_msg("invalid_request", INVALID_REQUEST))
            return
        async with self.gw.engine.begin() as c:
            await store.enqueue(
                c, self.gw.ids, self.pid, kind="choose", client_msg_id=msg["clientMsgId"], request=request
            )
        self.gw.kick(self.pid)

    async def _plan_open(self) -> bool:
        """Whether a plan is accepted: the act is closed and tries remain (3.11).

        プランを受け付けるか：幕を閉じていて、試行回数が残っている（3.11）。
        """
        run = await self._run()
        return run.act_end is not None and run.plan_tries < PLAN_TRIES

    async def propose(self, msg: Json) -> None:
        """Saying a plan in text: the words are stored in utterances as usual (only the player speaks this turn), and a
        plan task is written.

        文字でプランを言う：発言そのものはいつもどおり utterances に保存し（このターンはプレイヤーだけが話す）、
        plan のタスクを書く。
        """
        if not await self._plan_open():
            await self.send(error_msg("invalid_request", INVALID_REQUEST))
            return
        screen = await self.guard.screen_plan(msg["text"])
        if self.guard.paused:
            return
        await self._submit_plan(
            None, screen.masked or msg["text"], client_msg_id=msg["clientMsgId"], flags=screen.flags
        )

    async def plan_start(self, msg: Json) -> None:
        if not await self._plan_open():
            await self.send(error_msg("invalid_request", INVALID_REQUEST))
            return
        await self._cut()
        self.plan = PlanTurn(msg["turnId"], msg["turnSeq"], self.gw.live.transcriber())

    def _plan_audio(self, plan: PlanTurn, frame: bytes) -> None:
        if frame[0] != FRAME_MIC:
            return
        for ev in plan.listener.audio_in(frame[5:]):
            if ev.kind == "input_partial":
                task = self.gw.spawn(
                    self.send(
                        {
                            "type": "transcript",
                            "turnId": plan.turn_id,
                            "speaker": "player",
                            "text": ev.text,
                            "final": False,
                        }
                    )
                )
                plan.partials.append(task)

    async def plan_end(self, plan: PlanTurn) -> None:
        """Saying a plan by voice: push the transcribed final to the frontend, then write the plan task; the result
        (act_plan_result) carries this turn's turnId. The commit window counts from when the final is pushed (B-4:
        if the player sees it was misrecognized, there's time to 「言い直す」).

        声でプランを言う：文字起こしの確定文をフロントエンドに送ってから plan のタスクを書く。結果（act_plan_result）
        にはこのターンの turnId を付ける。提出の時間枠は確定文を送ったときから数える（B-4：プレイヤーが誤認識に気づいて
        も「言い直す」のに間に合う）。
        """
        heard = await plan.listener.finish()
        # Partials arrive first so the final isn't overwritten by a partial.
        # 途中の文を先に届け、確定文が途中の文で上書きされないようにする。
        await asyncio.gather(*plan.partials, return_exceptions=True)
        if plan.retracted:
            return
        # Pressed by mistake, nothing said: no task written, not counted as a try (3.11).
        # 誤って押した、声を出さなかった：タスクを書かず、試行回数にも数えない（3.11）。
        if not (heard or "").strip():
            left = max(0, PLAN_TRIES - (await self._run()).plan_tries)
            await self.send(
                {
                    "type": "act_plan_result",
                    "turnId": plan.turn_id,
                    "accepted": False,
                    "narration": [NOT_HEARD],
                    "triesLeft": left,
                }
            )
            return
        await self.send(
            {"type": "transcript", "turnId": plan.turn_id, "speaker": "player", "text": heard, "final": True}
        )
        screen = await self.guard.screen_plan(heard)
        # The plan line was judged a signal: not handed to the narrator (B-12).
        # プランの発言が signal と判定された：ナレーターに渡さない（B-12）。
        if self.guard.paused:
            return
        await self._submit_plan(plan, screen.masked or heard, flags=screen.flags)

    async def _submit_plan(
        self,
        plan: PlanTurn | None,
        text: str | None,
        *,
        client_msg_id: str | None = None,
        flags: frozenset[str] = frozenset(),
    ) -> None:
        mode = "text" if plan is None else "voice"
        request: Json = {"mode": mode}
        if client_msg_id is not None:
            request["clientMsgId"] = client_msg_id
        async with self.gw.engine.begin() as c:
            st = await store.sim_state(c, self.pid)
            turn_id = await store.enqueue(
                c,
                self.gw.ids,
                self.pid,
                kind="plan",
                turn_id=plan.turn_id if plan is not None else None,
                input_mode=mode,
                turn_seq=plan.turn_seq if plan is not None else None,
                client_msg_id=client_msg_id,
                request=request,
                commit_after=self._window(time.monotonic()) if plan is not None else None,
                flags=sorted(flags) or None,
            )
            await store.add_utterance(
                c, self.gw.ids, self.pid, turn_id, speaker="player", text=text, t=st["t"] if st is not None else 0
            )
        self.gw.kick(self.pid)

    async def landed(self, msg: Json) -> None:
        """Landing (3.11): when this act's arrival has an opener and hasn't landed yet, let that character speak first.
        Other actIds, or a second time in the same act, are ignored.

        着地（3.11）：この幕の arrival に opener があり、まだ着地していなければ、その登場人物に先に話させる。
        ほかの actId や同じ幕での 2 回目は無視する。
        """
        async with self.gw.engine.begin() as c:
            row = (
                (
                    await c.execute(
                        select(playthroughs.c.arrival)
                        .where(playthroughs.c.playthrough_id == self.pid)
                        .with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            arrival = row["arrival"] if row is not None else None
            if not arrival or arrival.get("actId") != msg["actId"] or not arrival.get("opener"):
                log.info("act_landed is not for this act's pending landing, ignored / 着地待ちではないので無視")
                return
            opener = str(arrival["opener"])
            turn_seq = SERVER_SEQ + self.served
            self.served += 1
            turn_id = await store.enqueue(
                c, self.gw.ids, self.pid, kind="arrival", character=opener, turn_seq=turn_seq, status="done"
            )
            await c.execute(update(playthroughs).where(playthroughs.c.playthrough_id == self.pid).values(arrival=None))
        self.settled.add(turn_id)
        await self._cut()
        s = self.sessions.get(opener)
        if s is None or not s.alive:
            await self.voices.open_now(opener, "arrival")
        # For an arrival turn the server treats the speaker as the focused character (3.3).
        # arrival のターンでは、サーバーは speaker を focus 中の登場人物として扱う（3.3）。
        self.focused = opener
        await self.send(
            {"type": "turn_started", "turnId": turn_id, "turnSeq": turn_seq, "speaker": opener, "reason": "arrival"}
        )
        prev = self.turn if self.turn is not None and self.turn.ended else None
        self.turn = Turn(turn_id, turn_seq, opener, "arrival", self.sessions.get(opener), prev=prev)
        self.respond(self.turn)


async def gate(gw: Gateway, ws: WebSocket, pid: str) -> tuple[int, str | None]:
    """Handshake: Cookie (4001), Origin (4003), whether the playthrough exists (4004), whether it's yours (4003).

    ハンドシェイク：Cookie（4001）、Origin（4003）、プレイが存在するか（4004）、あなたのものか（4003）。
    """
    async with gw.engine.begin() as c:
        found = await auth.session_user(c, ws.cookies.get(COOKIE))
        if found is None:
            return 4001, None
        if not origin_allowed(ws.headers, ws.url.scheme, gw.settings.allow_origins):
            return 4003, None
        if gw.schemas.request_errors("snapshot", "params", {"id": pid}):
            return 4004, None
        owner = await c.scalar(select(playthroughs.c.user_ref).where(playthroughs.c.playthrough_id == pid))
    if owner is None:
        return 4004, None
    if owner != found[0]:
        return 4003, None
    return 0, found[0]


async def endpoint(ws: WebSocket, pid: str) -> None:
    gw: Gateway = ws.app.state.gw
    await ws.accept()
    code, user_id = await gate(gw, ws, pid)
    if user_id is None or gw.draining:
        await ws.close(code or 1012)
        return
    conn = Conn(gw, ws, pid, user_id)
    old = gw.conns.get(pid)
    gw.conns[pid] = conn
    if old is not None:
        # First hand over the unfinished or still-held turn on the old connection, so hello's handed() below can wait
        # for it.
        # 古い接続で話し終えていない、または押したままのターンを先に渡す。そうすれば下の hello の handed()
        # がそれを待てる。
        old.drop()
        # The new connection's hello takes over the old connection's sessions and recent conversation (B-11).
        # 新しい接続の hello が古い接続のセッションと直近の会話を引き継ぐ（B-11）。
        await old.voices.park()
        # The same playthrough opened in another tab: the new connection kicks out the old one.
        # 同じプレイを別のタブで開いた：新しい接続が古い接続を追い出す。
        await old.close(4009, "opened elsewhere")
    reader = asyncio.ensure_future(read_loop(conn))
    closed = asyncio.ensure_future(conn.closed.wait())
    try:
        await asyncio.wait({reader, closed}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        reader.cancel()
        closed.cancel()
        conn.drop()
        # Timers are gone on disconnect: the reconnecting hello, or the narrator before taking tasks, closes expired
        # ones.
        # 切断するとタイマーはなくなる：再接続の hello、またはナレーターがタスクを取る前に、期限切れのものを閉じる。
        for timer in conn.timers.values():
            timer.cancel()
        if gw.conns.get(pid) is conn:
            del gw.conns[pid]
        # B-11: park and wait for a reconnect (the same session is reused within 30 seconds).
        # B-11：預けて再接続を待つ（30 秒以内なら同じセッションを使い続ける）。
        await conn.voices.park()


async def read_loop(conn: Conn) -> None:
    ws = conn.ws
    while True:
        try:
            frame = await ws.receive()
        except (RuntimeError, WebSocketDisconnect):
            break
        if frame["type"] == "websocket.disconnect":
            break
        if frame.get("bytes") is not None:
            conn.audio_in(frame["bytes"])
            continue
        try:
            msg = json.loads(frame.get("text") or "")
        except json.JSONDecodeError:
            msg = None
        errs = ["not JSON / JSON ではない"] if msg is None else conn.gw.schemas.client_errors(msg)
        if errs:
            log.info("Client message doesn't match the Schema / Schema に合わない: %s", "; ".join(errs[:3]))
            await conn.send(error_msg("invalid_request", "うまく送れませんでした。"))
            continue
        try:
            await conn.handle(msg)
        except Exception:
            log.exception("Handling %s failed / 処理でエラー", msg["type"])
            err = error_msg("internal", "エラーが起きました。")
            err["error"]["retryable"] = True
            await conn.send(err)
