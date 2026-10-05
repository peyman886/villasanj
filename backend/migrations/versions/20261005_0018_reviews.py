"""The owner's reviews for M8: expected intents of the query set, and search relevance.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review_case",
        sa.Column("queue", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("queue", "position", name="pk_review_case"),
        schema="discovery",
    )
    op.create_table(
        "review_label",
        sa.Column("queue", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("item", sa.Text, nullable=False),
        sa.Column("labeler", sa.Text, nullable=False),
        sa.Column("value", JSONB, nullable=False),
        sa.Column("labeled_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("queue", "position", "item", "labeler", name="pk_review_label"),
        schema="discovery",
    )


def downgrade() -> None:
    op.drop_table("review_label", schema="discovery")
    op.drop_table("review_case", schema="discovery")
