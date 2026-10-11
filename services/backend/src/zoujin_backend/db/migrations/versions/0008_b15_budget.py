"""B-15: budget tier on playthroughs, saving-tier time and degrade reason on playthrough_metrics, per-account daily
counters (runs, voice seconds), operational settings (voice_enabled)

Revision ID: 0008
Revises: 0006
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("playthroughs", sa.Column("budget_tier", sa.Text(), server_default="normal", nullable=False))
    op.add_column("playthrough_metrics", sa.Column("budget_saving_at", sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column("playthrough_metrics", sa.Column("degraded_reason", sa.Text(), nullable=True))
    op.create_table(
        "account_days",
        sa.Column("user_id", sa.Text(), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("runs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("voice_seconds", sa.Numeric(10, 1), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("user_id", "day"),
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_table("account_days")
    op.drop_column("playthrough_metrics", "degraded_reason")
    op.drop_column("playthrough_metrics", "budget_saving_at")
    op.drop_column("playthroughs", "budget_tier")
