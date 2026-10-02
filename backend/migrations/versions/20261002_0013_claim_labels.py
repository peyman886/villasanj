"""The owner's labels of feature claims in descriptions (ROADMAP M9 criterion 1).

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "claim_label_queue",
        sa.Column("queue", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("queue", "position", name="pk_claim_label_queue"),
        sa.UniqueConstraint(
            "queue", "platform", "external_id", name="uq_claim_label_queue_listing"
        ),
        schema="enrichment",
    )
    op.create_table(
        "claim_label",
        sa.Column("queue", sa.Text, nullable=False),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("labeler", sa.Text, nullable=False),
        sa.Column("feature", sa.Text, nullable=False),
        sa.Column("stance", sa.Text, nullable=False),  # has, has_not, shared, none
        sa.Column("labeled_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "queue", "platform", "external_id", "labeler", "feature", name="pk_claim_label"
        ),
        schema="enrichment",
    )


def downgrade() -> None:
    op.drop_table("claim_label", schema="enrichment")
    op.drop_table("claim_label_queue", schema="enrichment")
