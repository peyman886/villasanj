"""Catalog reviews: the guest reviews shown on listing pages (names are not stored).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "review",
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("review_id", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("rating", sa.Float),
        sa.Column("text", sa.Text),
        sa.Column("text_norm", sa.Text),
        sa.Column("stayed_on", sa.Date),
        sa.Column("stayed_precision", sa.Text),
        sa.Column("host_replied", sa.Boolean, nullable=False),
        sa.Column("snapshot_id", sa.Uuid, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("platform", "review_id", name="pk_review"),
        schema="catalog",
    )
    op.create_index("ix_review_listing", "review", ["platform", "external_id"], schema="catalog")


def downgrade() -> None:
    op.drop_index("ix_review_listing", table_name="review", schema="catalog")
    op.drop_table("review", schema="catalog")
