"""B-12: safety screening state on playthroughs (pause card, hint shown, ambiguous count), screening flags on turns,
safety and output-monitor counters on playthrough_metrics

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

COUNTS = (
    "safety_pauses",
    "safety_ambiguous",
    "safety_hints",
    "safety_unscreened",
    "safety_refused",
    "safety_injection",
    "safety_pii",
    "safety_harmful",
    "armor_errors",
    "output_lines",
    "output_spoilers",
    "output_harmful",
    "output_rebuilds",
    "output_questions",
    "output_questions_repeated",
    "output_question_notes",
)
COSTS = ("cost_safety_usd", "cost_armor_usd")


def upgrade() -> None:
    op.add_column(
        "playthroughs",
        sa.Column("safety", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column("turns", sa.Column("flags", postgresql.JSONB(), nullable=True))
    for name in COSTS:
        op.add_column("playthrough_metrics", sa.Column(name, sa.Numeric(12, 6), server_default="0", nullable=False))
    for name in COUNTS:
        op.add_column("playthrough_metrics", sa.Column(name, sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    for name in (*reversed(COUNTS), *reversed(COSTS)):
        op.drop_column("playthrough_metrics", name)
    op.drop_column("turns", "flags")
    op.drop_column("playthroughs", "safety")
