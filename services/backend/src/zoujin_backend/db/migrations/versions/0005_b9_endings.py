"""B-9: endings (one row per playthrough, the data contract's Ending as jsonb, deleted with the playthrough),
ending columns on playthrough_metrics

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "endings",
        sa.Column("ending_id", sa.Text(), nullable=False),
        sa.Column("playthrough_id", sa.Text(), nullable=False),
        sa.Column("body", postgresql.JSONB(), nullable=False),
        sa.Column("decided_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.playthrough_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ending_id"),
        sa.UniqueConstraint("playthrough_id", name="endings_playthrough"),
    )
    m = "playthrough_metrics"
    op.add_column(m, sa.Column("ending_started_at", postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column(m, sa.Column("ending_outcome", sa.Text(), nullable=True))
    op.add_column(m, sa.Column("ending_template", sa.Boolean(), nullable=True))
    op.add_column(m, sa.Column("ending_calls", sa.Integer(), nullable=True))
    op.add_column(m, sa.Column("ending_ms", sa.Integer(), nullable=True))
    op.add_column(m, sa.Column("cost_ending_usd", sa.Numeric(12, 6), server_default="0", nullable=False))


def downgrade() -> None:
    m = "playthrough_metrics"
    for name in (
        "cost_ending_usd",
        "ending_ms",
        "ending_calls",
        "ending_template",
        "ending_outcome",
        "ending_started_at",
    ):
        op.drop_column(m, name)
    op.drop_table("endings")
