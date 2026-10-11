"""B-21: suggestion cost on playthrough_metrics

Revision ID: 0010
Revises: 0009
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "playthrough_metrics", sa.Column("cost_suggest_usd", sa.Numeric(12, 6), server_default="0", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("playthrough_metrics", "cost_suggest_usd")
