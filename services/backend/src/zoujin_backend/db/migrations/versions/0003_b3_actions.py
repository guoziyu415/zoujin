"""B-3: per-run extras on playthroughs (player spot, played set pieces, act end, plan tries, landing), action and
act-end requests and results on turns, narrate / plan costs and action / plan counters on playthrough_metrics

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COSTS = ("cost_narrate_usd", "cost_plan_usd")
COUNTS = ("actions", "actions_act_ended", "plans_accepted", "plans_refused")


def upgrade() -> None:
    op.add_column("playthroughs", sa.Column("player_spot", sa.Text(), nullable=True))
    op.add_column(
        "playthroughs",
        sa.Column("played_pieces", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
    )
    op.add_column("playthroughs", sa.Column("act_end", postgresql.JSONB(), nullable=True))
    op.add_column("playthroughs", sa.Column("plan_tries", sa.Integer(), server_default="0", nullable=False))
    op.add_column("playthroughs", sa.Column("plan_alternative", postgresql.JSONB(), nullable=True))
    op.add_column("playthroughs", sa.Column("arrival", postgresql.JSONB(), nullable=True))
    op.add_column("turns", sa.Column("client_msg_id", sa.Text(), nullable=True))
    op.add_column("turns", sa.Column("request", postgresql.JSONB(), nullable=True))
    op.add_column("turns", sa.Column("result", postgresql.JSONB(), nullable=True))
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
    for name in ("result", "request", "client_msg_id"):
        op.drop_column("turns", name)
    for name in ("arrival", "plan_alternative", "plan_tries", "act_end", "played_pieces", "player_spot"):
        op.drop_column("playthroughs", name)
