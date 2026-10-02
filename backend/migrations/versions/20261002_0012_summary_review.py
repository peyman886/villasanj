"""The owner's blind review of review summaries against the raw reviews (ROADMAP M10 crit. 3).

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "summary_review_queue",
        sa.Column("queue", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("queue", "position", name="pk_summary_review_queue"),
        sa.UniqueConstraint(
            "queue", "platform", "external_id", name="uq_summary_review_queue_listing"
        ),
        schema="enrichment",
    )
    op.create_table(
        "summary_review_label",
        sa.Column("queue", sa.Text, nullable=False),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("labeler", sa.Text, nullable=False),
        sa.Column("faithful", sa.Boolean, nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("labeled_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "queue", "platform", "external_id", "labeler", name="pk_summary_review_label"
        ),
        schema="enrichment",
    )


def downgrade() -> None:
    op.drop_table("summary_review_label", schema="enrichment")
    op.drop_table("summary_review_queue", schema="enrichment")
