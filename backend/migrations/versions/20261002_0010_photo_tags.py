"""Photo tags: zero-shot scores per image, a labelling queue and the owner's labels (M9).

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "photo_tag_score",
        sa.Column("sha256", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),  # model id + pinned revision + prompt version
        sa.Column("tag", sa.Text, nullable=False),
        sa.Column("score", sa.Float, nullable=False),  # sigmoid probability; only its rank is used
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("sha256", "model", "tag", name="pk_photo_tag_score"),
        schema="enrichment",
    )
    op.create_index(
        "ix_photo_tag_score_model_tag", "photo_tag_score", ["model", "tag"], schema="enrichment"
    )
    op.create_table(
        "photo_tag_queue",
        sa.Column("queue", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("sha256", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),  # shown hotlinked; the bytes were scored
        sa.Column("stratum", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("queue", "position", name="pk_photo_tag_queue"),
        sa.UniqueConstraint("queue", "sha256", name="uq_photo_tag_queue_photo"),
        schema="enrichment",
    )
    op.create_table(
        "photo_tag_label",
        sa.Column("queue", sa.Text, nullable=False),
        sa.Column("sha256", sa.Text, nullable=False),
        sa.Column("tag", sa.Text, nullable=False),
        sa.Column("present", sa.Boolean, nullable=False),
        sa.Column("labeler", sa.Text, nullable=False),
        sa.Column("labeled_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("queue", "sha256", "tag", "labeler", name="pk_photo_tag_label"),
        schema="enrichment",
    )


def downgrade() -> None:
    op.drop_table("photo_tag_label", schema="enrichment")
    op.drop_table("photo_tag_queue", schema="enrichment")
    op.drop_index("ix_photo_tag_score_model_tag", table_name="photo_tag_score", schema="enrichment")
    op.drop_table("photo_tag_score", schema="enrichment")
