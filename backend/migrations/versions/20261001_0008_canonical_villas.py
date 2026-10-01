"""Canonical villas: members (<= 1 listing per platform, enforced here too) and id history.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "villa",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("run_id", sa.Uuid, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="er",
    )
    op.create_table(
        "villa_member",
        sa.Column(
            "villa_id", sa.Text, sa.ForeignKey("er.villa.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        # A listing belongs to one villa, and a villa has at most one listing per platform.
        sa.PrimaryKeyConstraint("platform", "external_id", name="pk_villa_member"),
        sa.UniqueConstraint("villa_id", "platform", name="uq_villa_member_one_per_platform"),
        schema="er",
    )
    op.create_table(
        "villa_event",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("run_id", sa.Uuid, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("villa_id", sa.Text, nullable=False),
        sa.Column("previous_ids", ARRAY(sa.Text), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="er",
    )


def downgrade() -> None:
    op.drop_table("villa_event", schema="er")
    op.drop_table("villa_member", schema="er")
    op.drop_table("villa", schema="er")
