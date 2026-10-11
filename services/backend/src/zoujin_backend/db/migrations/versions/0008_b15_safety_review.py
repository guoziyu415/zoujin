"""B-15: safety classifier review counters and cost on playthrough_metrics (S-072 ⑤)

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTS = ("safety_reviews", "safety_downgrades", "safety_review_failed", "safety_guarded")


def upgrade() -> None:
    op.add_column(
        "playthrough_metrics",
        sa.Column("cost_safety_review_usd", sa.Numeric(12, 6), server_default="0", nullable=False),
    )
    for name in COUNTS:
        op.add_column("playthrough_metrics", sa.Column(name, sa.Integer, server_default="0", nullable=False))


def downgrade() -> None:
    for name in reversed(COUNTS):
        op.drop_column("playthrough_metrics", name)
    op.drop_column("playthrough_metrics", "cost_safety_review_usd")
