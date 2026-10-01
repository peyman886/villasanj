"""Catalog photos: perceptual fingerprints per listing photo.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "photo",
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("snapshot_id", sa.Uuid, nullable=False),
        sa.Column("sha256", sa.Text, nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("phash", sa.BigInteger, nullable=False),
        sa.Column("dhash", sa.BigInteger, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("platform", "external_id", "position", name="pk_photo"),
        schema="catalog",
    )
    op.create_index("ix_photo_phash", "photo", ["phash"], schema="catalog")


def downgrade() -> None:
    op.drop_index("ix_photo_phash", table_name="photo", schema="catalog")
    op.drop_table("photo", schema="catalog")
