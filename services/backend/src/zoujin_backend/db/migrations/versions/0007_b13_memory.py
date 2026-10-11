"""B-13: memory_items (character memories of the player, deletable from the memory book), memory counters and cost
on playthrough_metrics

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTS = ("memories_written", "memories_filtered", "memories_failed", "memories_deleted")


def upgrade() -> None:
    op.create_table(
        "memory_items",
        sa.Column("memory_id", sa.Text(), primary_key=True),
        sa.Column(
            "playthrough_id",
            sa.Text(),
            sa.ForeignKey("playthroughs.playthrough_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("character", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("from_events", postgresql.JSONB(), nullable=False),
        sa.Column("t", sa.Integer(), nullable=False),
        sa.Column("trust_delta", sa.Integer(), nullable=False),
        sa.Column("salience", sa.Numeric(4, 3), nullable=False),
        sa.Column("via", sa.Text(), nullable=True),
        sa.Column("promise_id", sa.Text(), nullable=True),
        sa.Column("keeps", sa.Text(), nullable=True),
        sa.Column("keeps_done", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("memory_items_character", "memory_items", ["playthrough_id", "character"])
    op.add_column(
        "playthrough_metrics", sa.Column("cost_memory_usd", sa.Numeric(12, 6), server_default="0", nullable=False)
    )
    for name in COUNTS:
        op.add_column("playthrough_metrics", sa.Column(name, sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    for name in reversed(COUNTS):
        op.drop_column("playthrough_metrics", name)
    op.drop_column("playthrough_metrics", "cost_memory_usd")
    op.drop_index("memory_items_character", table_name="memory_items")
    op.drop_table("memory_items")
