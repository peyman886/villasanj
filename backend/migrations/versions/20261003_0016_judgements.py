"""LLM judge verdicts on gray-zone candidate pairs (ADR-0009 stage 4, ROADMAP M5). Never gold.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "judgement",
        sa.Column("left_platform", sa.Text, nullable=False),
        sa.Column("left_id", sa.Text, nullable=False),
        sa.Column("right_platform", sa.Text, nullable=False),
        sa.Column("right_id", sa.Text, nullable=False),
        sa.Column("verdict", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("evidence", postgresql.ARRAY(sa.Text), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("prompt_version", sa.Text, nullable=False),
        sa.Column("judged_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "left_platform", "left_id", "right_platform", "right_id", name="pk_judgement"
        ),
        schema="er",
    )


def downgrade() -> None:
    op.drop_table("judgement", schema="er")
