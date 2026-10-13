"""Runtime tables (the ones B-0 uses). Columns follow data-design section 3 and the data contract (Playthrough, Event,
Utterance, WorldState); the backend's own tables (turns, sessions, invite_codes, idempotency_keys) follow
backend-design 3.4, 3.5, 5.2.

Tables are created by Alembic (`migrations/versions/`); the definitions here are for queries, and the two must match
(a test compares them). The other tables (promises, run_facts, briefs, approach_log) are created by the M2 cards that
use them; memory_items is B-13 (0007).

ランタイムのテーブル（B-0 が使うもの）。列は data-design 第 3 節とデータ契約（Playthrough、Event、Utterance、
WorldState）に従い、バックエンド独自のテーブル（turns、sessions、invite_codes、idempotency_keys）は backend-design 3.4・
3.5・5.2 に従う。

テーブルの作成は Alembic（`migrations/versions/`）で行い、ここの定義はクエリ用。
両者は一致していなければならない（テストで比較する）。ほかのテーブル（promises、run_facts、briefs、approach_log）
はそれを使う M2 のカードが作る。memory_items は B-13（0007）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

metadata = MetaData()


def _ts(name: str, *, nullable: bool = True, now: bool = False) -> Column[Any]:
    return Column(name, TIMESTAMP(timezone=True), nullable=nullable, server_default=func.now() if now else None)


def _pt_fk() -> Column[str]:
    return Column("playthrough_id", Text, ForeignKey("playthroughs.playthrough_id", ondelete="CASCADE"), nullable=False)


# Invite-code accounts (S-020): userRef is this row's ID; no personal information at all
# 招待コードのアカウント（S-020）：userRef はこの行の ID そのもので、個人情報は一切ない
users = Table(
    "users",
    metadata,
    Column("user_id", Text, primary_key=True),  # usr_ + ULID
    _ts("created_at", nullable=False, now=True),
    _ts("last_login_at"),
)

# Only hashes are stored (backend-design 5.2). One code maps to one account: the account is created at the first
# login, and afterwards the same code returns to the same account (data-design 5.2)
# ハッシュだけを保存する（backend-design 5.2）。1 つのコードに 1 つのアカウント：最初のログインでアカウントを作り、
# 以後同じコードは同じアカウントに戻る（data-design 5.2）
invite_codes = Table(
    "invite_codes",
    metadata,
    Column("code_hash", Text, primary_key=True),  # sha256 of the normalised code / 正規化したコードの sha256
    Column("user_id", Text, ForeignKey("users.user_id", ondelete="SET NULL"), unique=True),
    _ts("created_at", nullable=False, now=True),
    _ts("revoked_at"),  # Revoked after L3 deletion / L3 削除の後に無効化
)

# Session cookie: the DB stores only the token's hash / セッション Cookie：DB にはトークンのハッシュだけを保存する
sessions = Table(
    "sessions",
    metadata,
    Column("token_hash", Text, primary_key=True),
    Column("user_id", Text, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
    _ts("created_at", nullable=False, now=True),
    _ts("expires_at", nullable=False),
    Index("sessions_user", "user_id"),
)

playthroughs = Table(
    "playthroughs",
    metadata,
    Column("playthrough_id", Text, primary_key=True),
    Column("user_ref", Text, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
    Column("book_id", Text, nullable=False),
    Column("world_model_version", Text, nullable=False),
    Column("role_id", Text, nullable=False),
    # active / ended / abandoned (deleted rows are simply removed)
    # active / ended / abandoned（deleted の行はそのまま削除）
    Column("status", Text, nullable=False),
    _ts("started_at", nullable=False, now=True),
    _ts("ended_at"),
    _ts("last_active_at", nullable=False, now=True),
    Column("last_seq", Integer, nullable=False, server_default="0"),
    # B-3 (0003): the bits of this playthrough that are not events and do not go into WorldState (contract 3.1, 2.11,
    # api-contract 3.11); all deleted with the playthrough
    # B-3（0003）：このプレイのうちイベントではなく WorldState にも入らないもの（契約 3.1・2.11、api-contract 3.11）。
    # すべてプレイごと削除する
    # The spot where the player stands; empty = the place's starting spot (startSpots)
    # プレイヤーが立っている位置。空 = いる場所の開始位置（startSpots）
    Column("player_spot", Text),
    # IDs of set pieces already played / 演じ終えた固定演出の ID
    Column("played_pieces", JSONB, nullable=False, server_default=text("'[]'::jsonb")),
    # Act closed but not yet chosen: pending.actEnd (same shape as act_ended, without type)
    # 幕を閉じたがまだ選んでいない：pending.actEnd（act_ended と同じ形で、type は持たない）
    Column("act_end", JSONB),
    # How many times a plan was stated at this end of act / この幕末にプランを何回話したか
    Column("plan_tries", Integer, nullable=False, server_default="0"),
    # Alternative destination offered when the plan is not feasible (cleared at the act change)
    # プランが成り立たないときに出した代わりの行き先（幕の切り替えで消す）
    Column("plan_alternative", JSONB),
    # Landing with an opener, act_landed not yet received: {actId, line, opener}
    # opener 付きで着地し、まだ act_landed を受け取っていない：{actId, line, opener}
    Column("arrival", JSONB),
    # B-12 (0006): this playthrough's safety screening state {paused, hinted, ambiguous} (out-of-character card open,
    # small hint shown, how many ambiguous); only the gateway writes it
    # B-12（0006）：このプレイの安全スクリーニングの状態 {paused, hinted, ambiguous}（物語の外に出るカードが開いている、
    # 小さなヒントを出した、あいまいだった回数）。書くのはゲートウェイだけ
    Column("safety", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    # B-14 (0008): budget tier normal / saving / degraded (backend-design 5.3), only goes up, never down; both the
    # narrator and the gateway follow it
    # B-14（0008）：予算の段階 normal / saving / degraded（backend-design 5.3）。上がるだけで下がらない。
    # ナレーターもゲートウェイもこれに従う
    Column("budget_tier", Text, nullable=False, server_default="normal"),
    # One active playthrough per account at a time (backend-design 5.2)
    # 1 アカウントにつき同時に 1 プレイ（backend-design 5.2）
    Index("playthroughs_one_active", "user_ref", unique=True, postgresql_where=text("status = 'active'")),
)

# The narrator's task table (backend-design 3.4): only IDs, status and leases, never the original words.
# kind: open (start a playthrough), talk (one conversation turn, voice or text), advance (fast-forward, only for tests
# and evals); B-3: action (action), choose (choose a destination at the end of act), plan (state a plan at the end of
# act), arrival (a character speaks first after landing; kept only as a record, the narrator does not process it);
# B-4: confirm (answer an intent confirmation, request carries draftId, optionId, by); B-16: world (world advance,
# request carries reason: key / mid)
# ナレーターのタスクテーブル（backend-design 3.4）：ID、状態、リースだけを保存し、発話の原文は保存しない。kind：
# open（プレイ開始）、talk（会話 1 ターン、音声またはテキスト）、advance（早送り、テストと評価専用）。B-3：
# action（アクション）、choose（幕末に行き先を選ぶ）、plan（幕末にプランを話す）、arrival（着地後に登場人物が先に話す。
# 記録だけ残し、ナレーターは処理しない）。B-4：confirm（意図確認への回答、request に draftId・optionId・by）。B-16：
# world（世界の進行、request に reason：key / mid）
turns = Table(
    "turns",
    metadata,
    Column("turn_id", Text, primary_key=True),
    _pt_fk(),
    Column("kind", Text, nullable=False),
    Column("input_mode", Text),  # talk: voice / text
    Column("character", Text),  # talk: who is spoken to / 誰と話すか
    Column("turn_seq", BigInteger),  # The frontend's turnSeq / フロントエンドの turnSeq
    # advance: how many minutes to fast-forward; when done: how many minutes this turn took (turn_settled.minutes)
    # advance：何分早送りするか。完了後：このターンにかかった分数（turn_settled.minutes）
    Column("minutes", Integer),
    # pending / leased / done / retracted / failed / lost (character had not finished when the connection dropped)
    # pending / leased / done / retracted / failed / lost（接続が切れたとき登場人物が話し終えていなかった）
    Column("status", Text, nullable=False),
    Column("outcome", Text),  # turn_settled.outcome
    _ts("lease_until"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    # The idempotency keys of the events this turn writes all start with it
    # このターンが書くイベントの冪等キーはすべてこれで始まる
    Column("idempotency_key", Text, nullable=False),
    Column("character_text_missing", Boolean, nullable=False, server_default=text("false")),
    # B-3 (0003): the frontend's clientMsgId; the request (an action's kind / target / params / actionId, the end of
    # act's optionId / enRouteChoice, never the original words); the result (messages to push in order after the commit,
    # and the set pieces played this time)
    # B-3（0003）：フロントエンドの clientMsgId。リクエスト（アクションの kind / target / params / actionId、
    # 幕末の optionId / enRouteChoice。発話の原文は入れない）。結果（コミット後に順に送るメッセージと、
    # 今回演じた固定演出）
    Column("client_msg_id", Text),
    Column("request", JSONB),
    Column("result", JSONB),
    _ts("created_at", nullable=False, now=True),
    _ts("settled_at"),
    # B-4 (0004): the earliest time the narrator commits this turn (turn_complete or the plan's final text + 3 seconds,
    # the retract window)
    # B-4（0004）：ナレーターがこのターンを最短でいつコミットするか（turn_complete、プランの確定 + 3 秒、
    # 取り消し可能な時間）
    _ts("commit_after"),
    # B-12 (0006): step-0 safety screening flags for the narrator (injection / pii / harmful / unscreened / ambiguous);
    # the judgement scores are not stored
    # B-12（0006）：第 0 段階の安全スクリーニングがナレーターに渡す
    # フラグ（injection / pii / harmful / unscreened / ambiguous）。判定のスコアは入れない
    Column("flags", JSONB),
    UniqueConstraint("playthrough_id", "idempotency_key", name="turns_idempotency"),
    Index("turns_queue", "playthrough_id", "status", "created_at"),
)

# Original words (data-design 3, 5.2): on retract or delete, text is cleared and the row stays
# 発話の原文（data-design 3・5.2）：取り消し・削除のときは text を空にし、行は残す
utterances = Table(
    "utterances",
    metadata,
    Column("utterance_id", Text, primary_key=True),
    _pt_fk(),
    Column("turn_id", Text, ForeignKey("turns.turn_id", ondelete="CASCADE"), nullable=False),
    Column("speaker", Text, nullable=False),  # player / character ID / 登場人物 ID
    Column("text", Text),
    Column("source", Text),  # Character's words: live / script / fallback / 登場人物の発話：live / script / fallback
    Column("t", Integer, nullable=False),
    _ts("recorded_at", nullable=False, now=True),
    _ts("deleted_at"),
    Index("utterances_turn", "turn_id"),
)

# Event log (data-design 3): append only. Every field of the contract Event has a place: common ones are columns, the
# other optional fields go in extra
# イベントログ（data-design 3）：追記のみ。契約の Event の各フィールドには置き場所がある：よく使うものは列、
# ほかの任意フィールドは extra
events = Table(
    "events",
    metadata,
    Column("event_id", Text, primary_key=True),
    _pt_fk(),
    Column("seq", Integer, nullable=False),
    Column("turn_id", Text),
    Column("idempotency_key", Text, nullable=False),
    Column("schema_version", Text, nullable=False),
    Column("t", Integer, nullable=False),
    Column("dt", Integer, nullable=False),
    Column("actor", Text, nullable=False),
    Column("type", Text, nullable=False),
    Column("origin", Text),
    Column("place", Text, nullable=False),
    Column("summary", Text, nullable=False),
    Column("causes", JSONB, nullable=False),
    Column("effects", JSONB, nullable=False),
    Column("key_moment", Boolean, nullable=False),
    Column("check_result", JSONB, nullable=False),
    Column("supersedes", Text),
    Column("exit_id", Text),
    Column("extra", JSONB, nullable=False, server_default=text("'{}'::jsonb")),  # beneficiary, confirmed, etc.
    _ts("recorded_at", nullable=False),
    UniqueConstraint("playthrough_id", "seq", name="events_seq"),
    UniqueConstraint("playthrough_id", "idempotency_key", name="events_idempotency"),
)

# W-1's SimState (JSON), can be replayed from events (data-design 4.4)
# W-1 の SimState（JSON）。イベントからリプレイできる（data-design 4.4）
world_state = Table(
    "world_state",
    metadata,
    Column("playthrough_id", Text, ForeignKey("playthroughs.playthrough_id", ondelete="CASCADE"), primary_key=True),
    Column("as_of_seq", Integer, nullable=False),
    Column("state", JSONB, nullable=False),
)

# REST Idempotency-Key (api-contract section 0): the same key with the same request returns the previous result
# REST の Idempotency-Key（api-contract 第 0 節）：同じキーで同じリクエストなら前回の結果を返す
idempotency_keys = Table(
    "idempotency_keys",
    metadata,
    Column("user_id", Text, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
    Column("key", Text, nullable=False),
    Column("request_hash", Text, nullable=False),
    Column("status_code", Integer, nullable=False),
    Column("response", JSONB, nullable=False),
    _ts("created_at", nullable=False, now=True),
    PrimaryKeyConstraint("user_id", "key"),
)

# One row per playthrough (backend-design 3.5): for now turn counts and each part's model spend, no text at all
# 1 プレイにつき 1 行（backend-design 3.5）：まずはターン数と各部分のモデル費用。文章は一切含まない
playthrough_metrics = Table(
    "playthrough_metrics",
    metadata,
    Column("playthrough_id", Text, ForeignKey("playthroughs.playthrough_id", ondelete="CASCADE"), primary_key=True),
    Column("turns", Integer, nullable=False, server_default="0"),
    Column("turns_retracted", Integer, nullable=False, server_default="0"),
    Column("cost_extract_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("cost_check_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("cost_reply_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("cost_live_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("voice_in_seconds", Numeric(10, 1), nullable=False, server_default="0"),
    Column("voice_out_seconds", Numeric(10, 1), nullable=False, server_default="0"),
    _ts("degraded_at"),
    # B-14 (0008): when the saving tier was entered; the degradation reason (budget / daily / service, the first one)
    # B-14（0008）：節約段階に入った時刻。降格の理由（budget / daily / service、最初に降格したときのもの）
    _ts("budget_saving_at"),
    Column("degraded_reason", Text),
    # B-21 (0010): spend on suggested utterances / 発話候補の費用
    Column("cost_suggest_usd", Numeric(12, 6), nullable=False, server_default="0"),
    # B-2 (0002): triage and rewrite spend; pipeline counts (turns where triage was skipped or that degraded on timeout;
    # candidates rewritten, downgraded, rejected, or dropped because they needed confirmation)
    # B-2（0002）：振り分けと書き換えの費用。パイプラインの件数（振り分けを飛ばしたターン、
    # タイムアウトで降格したターン、書き換え・降格・却下・確認が必要なため破棄した候補）
    Column("cost_triage_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("cost_rewrite_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("turns_triage_skipped", Integer, nullable=False, server_default="0"),
    Column("turns_timed_out", Integer, nullable=False, server_default="0"),
    Column("candidates_rewritten", Integer, nullable=False, server_default="0"),
    Column("candidates_downgraded", Integer, nullable=False, server_default="0"),
    Column("candidates_rejected", Integer, nullable=False, server_default="0"),
    Column("candidates_confirm_dropped", Integer, nullable=False, server_default="0"),
    # B-3 (0003): spend on one-line 地の文 (narration) and end-of-act plans; action counts (those answered refused from
    # the queue when the act closed are counted separately), counts of feasible and infeasible plans
    # B-3（0003）：一行の地の文と幕末のプランの費用。アクションの回数（幕を閉じたときにキューで refused
    # を返したものは別に数える）、プランが成り立った回数と成り立たなかった回数
    Column("cost_narrate_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("cost_plan_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("actions", Integer, nullable=False, server_default="0"),
    Column("actions_act_ended", Integer, nullable=False, server_default="0"),
    Column("plans_accepted", Integer, nullable=False, server_default="0"),
    Column("plans_refused", Integer, nullable=False, server_default="0"),
    # B-4 (0004): intent confirmations pushed (= yes + no + timeout, at most 1 still open when the playthrough ends),
    # those that failed the re-check after a "yes"
    # B-4（0004）：出した意図確認（= yes + no + timeout、プレイ終了時に開いたままなのは多くても 1 つ）、「はい」
    # の後の再チェックを通らなかったもの
    Column("confirms_asked", Integer, nullable=False, server_default="0"),
    Column("confirms_yes", Integer, nullable=False, server_default="0"),
    Column("confirms_no", Integer, nullable=False, server_default="0"),
    Column("confirms_timeout", Integer, nullable=False, server_default="0"),
    Column("confirms_rejected", Integer, nullable=False, server_default="0"),
    # B-9 (0005): when the ending started playing, the world ending's category, whether the template was used (S-065),
    # how many model calls, how long generation took, the ending's spend
    # B-9（0005）：エンディングの開始時刻、世界のエンディングの分類、テンプレートを使ったか（S-065）、
    # モデルの呼び出し回数、生成にかかった時間、エンディングの費用
    _ts("ending_started_at"),
    Column("ending_outcome", Text),
    Column("ending_template", Boolean),
    Column("ending_calls", Integer),
    Column("ending_ms", Integer),
    Column("cost_ending_usd", Numeric(12, 6), nullable=False, server_default="0"),
    # B-12 (0006): counts only (S-057, S-069 ③); column names follow the table in data review #112. Spend on the
    # safety classifier (including resends) and Model Armor; out-of-character cards (signal and second ambiguous),
    # ambiguous counts (including the one that showed the small hint), small hints, not judged, classifier refusals,
    # turns handed to the narrator with an injection / personal information / harmful flag, Model Armor errors (both
    # input and output);
    # output side: finalised character lines that passed monitoring (the denominator), lines that hit a spoiler, lines
    # judged harmful, sessions rebuilt for spoilers, lines ending in a question, the same character repeating the same
    # question, the too-many-questions note switched on
    # B-12（0006）：回数だけを記録する（S-057、S-069 ③）。列名はデータレビュー #112 の表に従う。安全分類器（再送を含む）
    # と Model Armor の費用。物語の外に出るカード（signal と 2 回目の ambiguous）、
    # ambiguous の回数（小さなヒントを出した回を含む）、小さなヒント、判定なし、分類器の回答拒否、
    # インジェクション / 個人情報 / 有害のフラグ付きでナレーターに渡したターン数、Model Armor のエラー（入力・
    # 出力の両側）。出力側：監視を通った登場人物の確定セリフ数（分母）、ネタバレに当たったセリフ数、
    # 有害と判定したセリフ数、ネタバレによるセッション再構築、疑問文で終わるセリフ数、
    # 同じ登場人物が同じ質問を繰り返した数、質問が多すぎるときの注意を出した数
    Column("cost_safety_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("cost_armor_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("safety_pauses", Integer, nullable=False, server_default="0"),
    Column("safety_ambiguous", Integer, nullable=False, server_default="0"),
    Column("safety_hints", Integer, nullable=False, server_default="0"),
    Column("safety_unscreened", Integer, nullable=False, server_default="0"),
    Column("safety_refused", Integer, nullable=False, server_default="0"),
    Column("safety_injection", Integer, nullable=False, server_default="0"),
    Column("safety_pii", Integer, nullable=False, server_default="0"),
    Column("safety_harmful", Integer, nullable=False, server_default="0"),
    Column("armor_errors", Integer, nullable=False, server_default="0"),
    Column("output_lines", Integer, nullable=False, server_default="0"),
    Column("output_spoilers", Integer, nullable=False, server_default="0"),
    Column("output_harmful", Integer, nullable=False, server_default="0"),
    Column("output_rebuilds", Integer, nullable=False, server_default="0"),
    Column("output_questions", Integer, nullable=False, server_default="0"),
    Column("output_questions_repeated", Integer, nullable=False, server_default="0"),
    Column("output_question_notes", Integer, nullable=False, server_default="0"),
    # B-13 (0007): spend on the memory line and the "consequence that will not be undone" line; memories written,
    # those that failed the three filters, those not written because the model errored or timed out, those deleted in
    # the 記憶帳 (Model Armor's spend and errors are still recorded in cost_armor_usd, armor_errors)
    # B-13（0007）：記憶の一文と「取り消されない結果」の一文の費用。書いた記憶、3 段のフィルターを通らなかったもの、
    # モデルのエラーやタイムアウトで書かなかったもの、記憶帳で削除したもの（Model Armor の費用とエラーはこれまでどおり
    # cost_armor_usd、armor_errors に記録する）
    Column("cost_memory_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("memories_written", Integer, nullable=False, server_default="0"),
    Column("memories_filtered", Integer, nullable=False, server_default="0"),
    Column("memories_failed", Integer, nullable=False, server_default="0"),
    Column("memories_deleted", Integer, nullable=False, server_default="0"),
    # B-15 (0009, S-072 ⑤): review spend; number of reviews (including second ambiguous ones), those downgraded to
    # ambiguous, those that kept signal because the review failed, those not reviewed because a guardrail hit
    # B-15（0009、S-072 ⑤）：再確認の費用。再確認の回数（2 回目の ambiguous を含む）、ambiguous に下げたもの、
    # 再確認に失敗して signal を残したもの、ガードレールに当たったため再確認しなかったもの
    Column("cost_safety_review_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("safety_reviews", Integer, nullable=False, server_default="0"),
    Column("safety_downgrades", Integer, nullable=False, server_default="0"),
    Column("safety_review_failed", Integer, nullable=False, server_default="0"),
    Column("safety_guarded", Integer, nullable=False, server_default="0"),
    # B-16 (0011): world advance spend; character-plan events and director events written (origin plan / director)
    # B-16（0011）：世界の進行の費用。書いた登場人物のプランのイベント、ディレクターのイベント（origin plan / director）
    Column("cost_world_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("world_events", Integer, nullable=False, server_default="0"),
    Column("director_events", Integer, nullable=False, server_default="0"),
)

# Intent-confirmation drafts (B-4, api-contract 3.9): the one candidate the narrator proposed that is not answered yet
# (no original words). The row is deleted when closed, and deleted with the playthrough.
# turn_id is the turn that proposed it (events after confirmation hang off that turn; when the 記憶帳 deletes that
# turn, the draft is dropped as a "no")
# 意図確認の草稿（B-4、api-contract 3.9）：ナレーターが出して、まだ回答のない候補 1 つ（発話の原文は入れない）。
# 閉じたら行を削除し、プレイごと削除する。turn_id はそれを出したターン（確認後のイベントはそのターンにぶら下がる。
# 記憶帳でそのターンを削除すると、草稿は「いいえ」として捨てる）
drafts = Table(
    "drafts",
    metadata,
    Column("draft_id", Text, primary_key=True),  # draft_ + ULID
    _pt_fk(),
    Column("turn_id", Text, ForeignKey("turns.turn_id", ondelete="CASCADE"), nullable=False),
    Column("character", Text, nullable=False),  # The character asking back / 聞き返す登場人物
    # The candidate that passed the check: actor, type, summary, effects, place, etc.
    # チェックを通った候補：actor、type、summary、effects、place など
    Column("candidate", JSONB, nullable=False),
    # The line in which the character asks back (confirm.prompt) / 登場人物が聞き返す一言（confirm.prompt）
    Column("prompt", Text, nullable=False),
    # The character's answer this turn is already the question back (no separate turn)
    # 登場人物のこのターンの回答がすでに聞き返しになっている（別のターンを起こさない）
    Column("asked", Boolean, nullable=False),
    _ts("created_at", nullable=False, now=True),
    _ts("expires_at"),  # Written when confirm is pushed: push + 30 s / confirm を送るときに書く：送信 + 30 秒
    Index("drafts_playthrough", "playthrough_id"),
)

# Endings (B-9, data-design line 84): one row per playthrough; body is the Ending from data contract section 5;
# deleted with the playthrough
# エンディング（B-9、data-design 第 84 行）：1 プレイにつき 1 行。body はデータ契約第 5 節の Ending。プレイごと削除する
endings = Table(
    "endings",
    metadata,
    Column("ending_id", Text, primary_key=True),  # end_ + ULID
    _pt_fk(),
    Column("body", JSONB, nullable=False),
    _ts("decided_at", nullable=False, now=True),
    UniqueConstraint("playthrough_id", name="endings_playthrough"),
)

# Characters' memories of the player (B-13, contract section 4): on deletion text is set to null and deleted_at is
# written, the row stays (audit); deleted with the playthrough.
# keeps: cache of the "consequence that will not be undone" line in the delete confirmation; keeps_done = already
# computed (a null result is cached too)
# 登場人物のプレイヤーについての記憶（B-13、契約第 4 節）：削除すると text を null にして deleted_at を書き、
# 行は残す（監査用）。プレイごと削除する。keeps：削除確認の「取り消されない結果」の一文のキャッシュ。
# keeps_done = 計算済み（null になってもキャッシュする）
memory_items = Table(
    "memory_items",
    metadata,
    Column("memory_id", Text, primary_key=True),  # mem_ + ULID
    _pt_fk(),
    Column("schema_version", Text, nullable=False),
    Column("character", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("text", Text),
    Column("from_events", JSONB, nullable=False),
    Column("t", Integer, nullable=False),
    Column("trust_delta", Integer, nullable=False),
    Column("salience", Numeric(4, 3), nullable=False),
    Column("via", Text),
    Column("promise_id", Text),
    Column("keeps", Text),
    Column("keeps_done", Boolean, nullable=False, server_default=text("false")),
    _ts("created_at", nullable=False, now=True),
    _ts("deleted_at"),
    # Situation briefs and relationship calculation read only undeleted rows (data review)
    # 状況説明と関係の計算は削除されていないものだけを読む（データレビュー）
    Index("memory_items_character", "playthrough_id", "character", postgresql_where=text("deleted_at IS NULL")),
)

# Tables on data-design 5.3's deletion list that are not built yet (situation briefs are not stored; they are assembled
# fresh each time a session opens); eval_api's db_absent answers 0 for them
# data-design 5.3 の削除リストのうち、まだ作っていないテーブル（状況説明は DB に保存せず、
# セッションを開くたびにその場で組み立てる）。eval_api の db_absent はこれらに 0 を返す
NOT_BUILT = ("briefs",)

# B-14 (0008): per account per day (Japan time), how many playthroughs were started and how many seconds of voice were
# spoken (backend-design 5.2). Deleting a playthrough does not refund the count, so it is not counted live from
# playthroughs; numbers only, deleted with the account
# B-14（0008）：アカウントごと・1 日（日本時間）ごとに開始したプレイ数と話した音声の秒数（backend-design 5.2）。
# プレイを削除しても回数は戻らないので、playthroughs からその場で数えない。数字だけで、アカウントごと削除する
account_days = Table(
    "account_days",
    metadata,
    Column("user_id", Text, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
    Column("day", Date, nullable=False),
    Column("runs", Integer, nullable=False, server_default="0"),
    Column("voice_seconds", Numeric(10, 1), nullable=False, server_default="0"),
    PrimaryKeyConstraint("user_id", "day"),
)

# B-14 (0008): operations switches (for now only voice_enabled, backend-design 5.3's global circuit breaker)
# B-14（0008）：運用スイッチ（今は voice_enabled だけ。backend-design 5.3 の全体サーキットブレーカー）
app_settings = Table(
    "app_settings",
    metadata,
    Column("key", Text, primary_key=True),
    Column("value", JSONB, nullable=False),
    _ts("updated_at", nullable=False, now=True),
)

# Tables on data-design 5.3's deletion list that are already built (eval_api's db_absent checks these)
# data-design 5.3 の削除リストのうち、作成済みのテーブル（eval_api の db_absent はこれらを確認する）
PER_PLAYTHROUGH = (
    "playthroughs",
    "turns",
    "utterances",
    "events",
    "world_state",
    "playthrough_metrics",
    "drafts",
    "endings",
    "memory_items",
)
