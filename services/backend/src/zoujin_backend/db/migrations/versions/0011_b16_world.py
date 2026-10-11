"""B-16: world advance cost and counters on playthrough_metrics (characters' plan events, director events)

Revision ID: 0011
Revises: 0010
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTS = ("world_events", "director_events")


def upgrade() -> None:
    op.add_column(
        "playthrough_metrics", sa.Column("cost_world_usd", sa.Numeric(12, 6), server_default="0", nullable=False)
    )
    for name in COUNTS:
        op.add_column("playthrough_metrics", sa.Column(name, sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    for name in reversed(COUNTS):
        op.drop_column("playthrough_metrics", name)
    op.drop_column("playthrough_metrics", "cost_world_usd")
