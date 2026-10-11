"""B-4: drafts (intent confirmation, one row per open draft, deleted when closed), the commit window on turns,
confirmation counters on playthrough_metrics

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTS = ("confirms_asked", "confirms_yes", "confirms_no", "confirms_timeout", "confirms_rejected")


def upgrade() -> None:
    op.create_table(
        "drafts",
        sa.Column("draft_id", sa.Text(), nullable=False),
        sa.Column("playthrough_id", sa.Text(), nullable=False),
        sa.Column("turn_id", sa.Text(), nullable=False),
        sa.Column("character", sa.Text(), nullable=False),
        sa.Column("candidate", postgresql.JSONB(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("asked", sa.Boolean(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["playthrough_id"], ["playthroughs.playthrough_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.turn_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("draft_id"),
    )
    op.create_index("drafts_playthrough", "drafts", ["playthrough_id"])
    op.add_column("turns", sa.Column("commit_after", postgresql.TIMESTAMP(timezone=True), nullable=True))
    for name in COUNTS:
        op.add_column("playthrough_metrics", sa.Column(name, sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    for name in reversed(COUNTS):
        op.drop_column("playthrough_metrics", name)
    op.drop_column("turns", "commit_after")
    op.drop_index("drafts_playthrough", table_name="drafts")
    op.drop_table("drafts")
