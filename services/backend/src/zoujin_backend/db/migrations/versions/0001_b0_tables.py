"""B-0: users, invite codes, sessions, playthroughs, turns, utterances, events, world state, idempotency keys, metrics

Revision ID: 0001
Revises: (none)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_login_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "key"),
    )
    op.create_table(
        "invite_codes",
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("code_hash"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "playthroughs",
        sa.Column("playthrough_id", sa.Text(), nullable=False),
        sa.Column("user_ref", sa.Text(), nullable=False),
        sa.Column("book_id", sa.Text(), nullable=False),
        sa.Column("world_model_version", sa.Text(), nullable=False),
        sa.Column("role_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ended_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "last_active_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("last_seq", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["user_ref"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("playthrough_id"),
    )
    op.create_index(
        "playthroughs_one_active",
        "playthroughs",
        ["user_ref"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index("sessions_user", "sessions", ["user_id"], unique=False)
    op.create_table(
        "events",
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("playthrough_id", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("turn_id", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("t", sa.Integer(), nullable=False),
        sa.Column("dt", sa.Integer(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=True),
        sa.Column("place", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("causes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("effects", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("key_moment", sa.Boolean(), nullable=False),
        sa.Column("check_result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("supersedes", sa.Text(), nullable=True),
        sa.Column("exit_id", sa.Text(), nullable=True),
        sa.Column(
            "extra", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("recorded_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.playthrough_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("playthrough_id", "idempotency_key", name="events_idempotency"),
        sa.UniqueConstraint("playthrough_id", "seq", name="events_seq"),
    )
    op.create_table(
        "playthrough_metrics",
        sa.Column("playthrough_id", sa.Text(), nullable=False),
        sa.Column("turns", sa.Integer(), server_default="0", nullable=False),
        sa.Column("turns_retracted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_extract_usd", sa.Numeric(precision=12, scale=6), server_default="0", nullable=False),
        sa.Column("cost_check_usd", sa.Numeric(precision=12, scale=6), server_default="0", nullable=False),
        sa.Column("cost_reply_usd", sa.Numeric(precision=12, scale=6), server_default="0", nullable=False),
        sa.Column("cost_live_usd", sa.Numeric(precision=12, scale=6), server_default="0", nullable=False),
        sa.Column("voice_in_seconds", sa.Numeric(precision=10, scale=1), server_default="0", nullable=False),
        sa.Column("voice_out_seconds", sa.Numeric(precision=10, scale=1), server_default="0", nullable=False),
        sa.Column("degraded_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.playthrough_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("playthrough_id"),
    )
    op.create_table(
        "turns",
        sa.Column("turn_id", sa.Text(), nullable=False),
        sa.Column("playthrough_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("input_mode", sa.Text(), nullable=True),
        sa.Column("character", sa.Text(), nullable=True),
        sa.Column("turn_seq", sa.BigInteger(), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("lease_until", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("character_text_missing", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("settled_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.playthrough_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("turn_id"),
        sa.UniqueConstraint("playthrough_id", "idempotency_key", name="turns_idempotency"),
    )
    op.create_index("turns_queue", "turns", ["playthrough_id", "status", "created_at"], unique=False)
    op.create_table(
        "world_state",
        sa.Column("playthrough_id", sa.Text(), nullable=False),
        sa.Column("as_of_seq", sa.Integer(), nullable=False),
        sa.Column("state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.playthrough_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("playthrough_id"),
    )
    op.create_table(
        "utterances",
        sa.Column("utterance_id", sa.Text(), nullable=False),
        sa.Column("playthrough_id", sa.Text(), nullable=False),
        sa.Column("turn_id", sa.Text(), nullable=False),
        sa.Column("speaker", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("t", sa.Integer(), nullable=False),
        sa.Column("recorded_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.playthrough_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.turn_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("utterance_id"),
    )
    op.create_index("utterances_turn", "utterances", ["turn_id"], unique=False)


def downgrade() -> None:
    op.drop_index("utterances_turn", table_name="utterances")
    op.drop_table("utterances")
    op.drop_table("world_state")
    op.drop_index("turns_queue", table_name="turns")
    op.drop_table("turns")
    op.drop_table("playthrough_metrics")
    op.drop_table("events")
    op.drop_index("sessions_user", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("playthroughs_one_active", table_name="playthroughs", postgresql_where=sa.text("status = 'active'"))
    op.drop_table("playthroughs")
    op.drop_table("invite_codes")
    op.drop_table("idempotency_keys")
    op.drop_table("users")
