"""B-2: playthrough_metrics gets triage and rewrite costs and the narrator pipeline counters

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COSTS = ("cost_triage_usd", "cost_rewrite_usd")
COUNTS = (
    "turns_triage_skipped",
    "turns_timed_out",
    "candidates_rewritten",
    "candidates_downgraded",
    "candidates_rejected",
    "candidates_confirm_dropped",
)


def upgrade() -> None:
    for name in COSTS:
        op.add_column(
            "playthrough_metrics",
            sa.Column(name, sa.Numeric(precision=12, scale=6), server_default="0", nullable=False),
        )
    for name in COUNTS:
        op.add_column("playthrough_metrics", sa.Column(name, sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    for name in reversed(COSTS + COUNTS):
        op.drop_column("playthrough_metrics", name)
