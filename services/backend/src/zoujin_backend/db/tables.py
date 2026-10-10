"""运行时的表（B-0 用到的那几张）。列按 data-design 第 3 节和数据契约（Playthrough、Event、Utterance、WorldState），
后端自己的表（turns、sessions、invite_codes、idempotency_keys）按 backend-design 3.4、3.5、5.2。

建表走 Alembic（`migrations/versions/`），这里的定义给查询用，两边要一致（测试比对）。
其余的表（memory_items、promises、run_facts、briefs、drafts、approach_log、endings）由用到它们的 M2 卡建。
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
    # 每账号同时 1 局（backend-design 5.2）
    Index("playthroughs_one_active", "user_ref", unique=True, postgresql_where=text("status = 'active'")),
)

# 叙事者的任务表（backend-design 3.4）：只存 ID、状态、租约，不存原话。
# kind：open（开局）、talk（一轮对话，语音或文字）、advance（快进，只给测试和评测）
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
    _ts("created_at", nullable=False, now=True),
    _ts("settled_at"),
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
)

# data-design 5.3 的删除清单里，B-0 建了的表（eval_api 的 db_absent 查这些）
PER_PLAYTHROUGH = ("playthroughs", "turns", "utterances", "events", "world_state", "playthrough_metrics")
