"""Corrections of human labels, kept beside them (the original decision is never lost).

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "label_revision",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("left_platform", sa.Text, nullable=False),
        sa.Column("left_id", sa.Text, nullable=False),
        sa.Column("right_platform", sa.Text, nullable=False),
        sa.Column("right_id", sa.Text, nullable=False),
        sa.Column("labeler", sa.Text, nullable=False),
        sa.Column("before", sa.Text, nullable=False),
        sa.Column("after", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("revised_by", sa.Text, nullable=False),
        sa.Column("revised_at", sa.DateTime(timezone=True), nullable=False),
        schema="er",
    )


def downgrade() -> None:
    op.drop_table("label_revision", schema="er")
