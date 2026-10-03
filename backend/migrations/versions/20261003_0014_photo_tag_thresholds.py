"""Photo-tag thresholds chosen from the owner's labels (ROADMAP M9 criterion 2).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "photo_tag_threshold",
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("tag", sa.Text, nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("precision", sa.Float, nullable=False),
        sa.Column("precision_low", sa.Float, nullable=False),
        sa.Column("recall", sa.Float, nullable=False),
        sa.Column("positives", sa.Integer, nullable=False),
        sa.Column("labelled", sa.Integer, nullable=False),
        sa.Column("queue", sa.Text, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("model", "tag", name="pk_photo_tag_threshold"),
        schema="enrichment",
    )


def downgrade() -> None:
    op.drop_table("photo_tag_threshold", schema="enrichment")
