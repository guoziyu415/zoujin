"""运行时的表（B-0 用到的那几张）。列按 data-design 第 3 节和数据契约（Playthrough、Event、Utterance、WorldState），
后端自己的表（turns、sessions、invite_codes、idempotency_keys）按 backend-design 3.4、3.5、5.2。

建表走 Alembic（`migrations/versions/`），这里的定义给查询用，两边要一致（测试比对）。
其余的表（promises、run_facts、briefs、approach_log）由用到它们的 M2 卡建；memory_items 是 B-13（0007）。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
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


# 邀请码账号（S-020）：userRef 就是这一行的 ID，没有任何个人信息
users = Table(
    "users",
    metadata,
    Column("user_id", Text, primary_key=True),  # usr_ + ULID
    _ts("created_at", nullable=False, now=True),
    _ts("last_login_at"),
)

# 只存哈希（backend-design 5.2）。一个码对应一个账号：第一次登录时建账号，之后同一个码回到同一个账号（data-design 5.2）
invite_codes = Table(
    "invite_codes",
    metadata,
    Column("code_hash", Text, primary_key=True),  # 规范化之后的码的 sha256
    Column("user_id", Text, ForeignKey("users.user_id", ondelete="SET NULL"), unique=True),
    _ts("created_at", nullable=False, now=True),
    _ts("revoked_at"),  # L3 删除后作废
)

# 会话 Cookie：库里只存令牌的哈希
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
    Column("status", Text, nullable=False),  # active / ended / abandoned（deleted 的行直接删掉）
    _ts("started_at", nullable=False, now=True),
    _ts("ended_at"),
    _ts("last_active_at", nullable=False, now=True),
    Column("last_seq", Integer, nullable=False, server_default="0"),
    # B-3（0003）：这一局的几样不是事件、不进 WorldState 的东西（契约 3.1、2.11，api-contract 3.11），都随整局删除
    Column("player_spot", Text),  # 玩家站的位置点；空 = 所在地点的起点（startSpots）
    Column("played_pieces", JSONB, nullable=False, server_default=text("'[]'::jsonb")),  # 演过的固定演出 ID
    Column("act_end", JSONB),  # 收了幕、还没选定：pending.actEnd（和 act_ended 同形，不带 type）
    Column("plan_tries", Integer, nullable=False, server_default="0"),  # 这次幕末说过几次打算
    Column("plan_alternative", JSONB),  # 打算不成行时给的替代去处（幕切换时清掉）
    Column("arrival", JSONB),  # 落地带 opener、还没收到 act_landed：{actId, line, opener}
    # B-12（0006）：安全筛查的这一局状态 {paused, hinted, ambiguous}（出戏卡开着、小提示推过、似是而非几次），只有网关写
    Column("safety", JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    # 每账号同时 1 局（backend-design 5.2）
    Index("playthroughs_one_active", "user_ref", unique=True, postgresql_where=text("status = 'active'")),
)

# 叙事者的任务表（backend-design 3.4）：只存 ID、状态、租约，不存原话。
# kind：open（开局）、talk（一轮对话，语音或文字）、advance（快进，只给测试和评测）；B-3：action（动作）、
# choose（幕末选去处）、plan（幕末说出打算）、arrival（落地后人物先开口，只留记录，叙事者不处理）；
# B-4：confirm（回答意图确认，request 带 draftId、optionId、by）
turns = Table(
    "turns",
    metadata,
    Column("turn_id", Text, primary_key=True),
    _pt_fk(),
    Column("kind", Text, nullable=False),
    Column("input_mode", Text),  # talk：voice / text
    Column("character", Text),  # talk：和谁说
    Column("turn_seq", BigInteger),  # 前端的 turnSeq
    Column("minutes", Integer),  # advance：快进几分钟；完成后：这一轮花了几分钟（turn_settled.minutes）
    Column("status", Text, nullable=False),  # pending / leased / done / retracted / failed / lost（断线时人物没说完）
    Column("outcome", Text),  # turn_settled.outcome
    _ts("lease_until"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("idempotency_key", Text, nullable=False),  # 这一轮写的事件的幂等键都以它开头
    Column("character_text_missing", Boolean, nullable=False, server_default=text("false")),
    # B-3（0003）：前端的 clientMsgId；请求（动作的 kind / target / params / actionId，幕末的 optionId /
    # enRouteChoice，不放原话）；结果（提交以后按顺序要推的消息，和这次演的固定演出）
    Column("client_msg_id", Text),
    Column("request", JSONB),
    Column("result", JSONB),
    _ts("created_at", nullable=False, now=True),
    _ts("settled_at"),
    _ts("commit_after"),  # B-4（0004）：叙事者最早什么时候提交这一轮（turn_complete、打算的定稿 + 3 秒，作废的窗口）
    # B-12（0006）：第 0 步安全筛查给叙事者的标记（injection / pii / harmful / unscreened / ambiguous），不放判定的分数
    Column("flags", JSONB),
    UniqueConstraint("playthrough_id", "idempotency_key", name="turns_idempotency"),
    Index("turns_queue", "playthrough_id", "status", "created_at"),
)

# 原话（data-design 3、5.2）：作废、删除时清空 text，行留着
utterances = Table(
    "utterances",
    metadata,
    Column("utterance_id", Text, primary_key=True),
    _pt_fk(),
    Column("turn_id", Text, ForeignKey("turns.turn_id", ondelete="CASCADE"), nullable=False),
    Column("speaker", Text, nullable=False),  # player / 人物 ID
    Column("text", Text),
    Column("source", Text),  # 人物的话：live / script / fallback
    Column("t", Integer, nullable=False),
    _ts("recorded_at", nullable=False, now=True),
    _ts("deleted_at"),
    Index("utterances_turn", "turn_id"),
)

# 事件日志（data-design 3）：只追加。契约 Event 的每个字段都有地方放：常用的是列，其余可选字段在 extra
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
    Column("extra", JSONB, nullable=False, server_default=text("'{}'::jsonb")),  # beneficiary、confirmed 等
    _ts("recorded_at", nullable=False),
    UniqueConstraint("playthrough_id", "seq", name="events_seq"),
    UniqueConstraint("playthrough_id", "idempotency_key", name="events_idempotency"),
)

# W-1 的 SimState（JSON），可以从事件重放（data-design 4.4）
world_state = Table(
    "world_state",
    metadata,
    Column("playthrough_id", Text, ForeignKey("playthroughs.playthrough_id", ondelete="CASCADE"), primary_key=True),
    Column("as_of_seq", Integer, nullable=False),
    Column("state", JSONB, nullable=False),
)

# REST 的 Idempotency-Key（api-contract 第 0 节）：同一个键、同样的请求回上次的结果
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

# 每局一行（backend-design 3.5）：先放轮数和各部分的模型花费，不含任何文字
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
    # B-2（0002）：分流和改写的花费；流水线的计数（分流跳过、超时降级的轮，改写、降级、拒绝、因要确认而丢弃的候选）
    Column("cost_triage_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("cost_rewrite_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("turns_triage_skipped", Integer, nullable=False, server_default="0"),
    Column("turns_timed_out", Integer, nullable=False, server_default="0"),
    Column("candidates_rewritten", Integer, nullable=False, server_default="0"),
    Column("candidates_downgraded", Integer, nullable=False, server_default="0"),
    Column("candidates_rejected", Integer, nullable=False, server_default="0"),
    Column("candidates_confirm_dropped", Integer, nullable=False, server_default="0"),
    # B-3（0003）：一行地の文和幕末打算的花费；动作的次数（收幕时队列里回 refused 的另数），打算成行、不成行的次数
    Column("cost_narrate_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("cost_plan_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("actions", Integer, nullable=False, server_default="0"),
    Column("actions_act_ended", Integer, nullable=False, server_default="0"),
    Column("plans_accepted", Integer, nullable=False, server_default="0"),
    Column("plans_refused", Integer, nullable=False, server_default="0"),
    # B-4（0004）：推出的意图确认（= yes + no + timeout，局终了时最多还开着 1 个），答「是」以后重查没过的
    Column("confirms_asked", Integer, nullable=False, server_default="0"),
    Column("confirms_yes", Integer, nullable=False, server_default="0"),
    Column("confirms_no", Integer, nullable=False, server_default="0"),
    Column("confirms_timeout", Integer, nullable=False, server_default="0"),
    Column("confirms_rejected", Integer, nullable=False, server_default="0"),
    # B-9（0005）：结局开演的时刻、世界结局的分类、走没走模板（S-065）、调了几次模型、生成用了多久、结局的花费
    _ts("ending_started_at"),
    Column("ending_outcome", Text),
    Column("ending_template", Boolean),
    Column("ending_calls", Integer),
    Column("ending_ms", Integer),
    Column("cost_ending_usd", Numeric(12, 6), nullable=False, server_default="0"),
    # B-12（0006）：只记次数（S-057、S-069 ③），列名按数据评审 #112 的表。安全分类器（含重发）和 Model Armor 的花费；
    # 出戏卡（信号和第二次 ambiguous）、ambiguous 的次数（含出小提示的那次）、小提示、没判定、分类器拒答、
    # 带注入 / 个人信息 / 有害标记交给叙事者的轮数、Model Armor 出错（输入输出两边）；
    # 输出侧：过了监控的人物定稿句数（分母）、命中剧透的句数、判有害的句数、剧透重建会话、以问句结尾的句数、
    # 同一人物重复问同一句、问句过多的提示打开
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
    # B-13（0007）：记忆一句和「不会撤销的后果」一句的花费；写了的记忆、三道过滤没过的、模型出错超时没写的、
    # 在記憶帳删掉的（Model Armor 的花费和出错照旧记在 cost_armor_usd、armor_errors）
    Column("cost_memory_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("memories_written", Integer, nullable=False, server_default="0"),
    Column("memories_filtered", Integer, nullable=False, server_default="0"),
    Column("memories_failed", Integer, nullable=False, server_default="0"),
    Column("memories_deleted", Integer, nullable=False, server_default="0"),
    # B-15（0008，S-072 ⑤）：复核的花费；复核了几次（含第二次 ambiguous 的）、降成 ambiguous 的、
    # 复核失败保留 signal 的、护栏命中不复核的
    Column("cost_safety_review_usd", Numeric(12, 6), nullable=False, server_default="0"),
    Column("safety_reviews", Integer, nullable=False, server_default="0"),
    Column("safety_downgrades", Integer, nullable=False, server_default="0"),
    Column("safety_review_failed", Integer, nullable=False, server_default="0"),
    Column("safety_guarded", Integer, nullable=False, server_default="0"),
)

# 意图确认的草稿（B-4，api-contract 3.9）：叙事者提出、还没答的那一个候选（不放原话）。关掉就删行，随整局删除。
# turn_id 是提出它的那一轮（确认以后的事件挂在那一轮上，记憶帳删那一轮时草稿按「不是」丢掉）
drafts = Table(
    "drafts",
    metadata,
    Column("draft_id", Text, primary_key=True),  # draft_ + ULID
    _pt_fk(),
    Column("turn_id", Text, ForeignKey("turns.turn_id", ondelete="CASCADE"), nullable=False),
    Column("character", Text, nullable=False),  # 反问的人物
    Column("candidate", JSONB, nullable=False),  # 过了检查的候选：actor、type、summary、effects、place 等
    Column("prompt", Text, nullable=False),  # 人物反问的那一句（confirm.prompt）
    Column("asked", Boolean, nullable=False),  # 人物这一轮的回答已经在反问（不另起一轮）
    _ts("created_at", nullable=False, now=True),
    _ts("expires_at"),  # 推出 confirm 时写：推出 + 30 秒
    Index("drafts_playthrough", "playthrough_id"),
)

# 结局（B-9，data-design 第 84 行）：一局一行，body 是数据契约第 5 节的 Ending，随整局删除
endings = Table(
    "endings",
    metadata,
    Column("ending_id", Text, primary_key=True),  # end_ + ULID
    _pt_fk(),
    Column("body", JSONB, nullable=False),
    _ts("decided_at", nullable=False, now=True),
    UniqueConstraint("playthrough_id", name="endings_playthrough"),
)

# 人物对玩家的记忆（B-13，契约第 4 节）：删了 text 置空、写 deleted_at，行留着（审计）；随整局删除。
# keeps：删除确认里「不会撤销的后果」一句的缓存，keeps_done = 算过了（算出 null 也缓存）
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
    # 局势说明和算关系只读没删的（数据评审）
    Index("memory_items_character", "playthrough_id", "character", postgresql_where=text("deleted_at IS NULL")),
)

# data-design 5.3 的删除清单里还没建的表（局势说明不存库，每次开会话现拼），eval_api 的 db_absent 答 0
NOT_BUILT = ("briefs",)
# data-design 5.3 的删除清单里，已经建了的表（eval_api 的 db_absent 查这些）
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
