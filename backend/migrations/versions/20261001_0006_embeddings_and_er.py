"""Photo embeddings (content-addressed) and entity-resolution tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, REAL

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAIR = ("left_platform", "left_id", "right_platform", "right_id")


def _pair_columns() -> list[sa.Column[str]]:
    return [sa.Column(name, sa.Text, nullable=False) for name in PAIR]


def upgrade() -> None:
    # One row per distinct image and model: the same photo on two listings is embedded once.
    op.create_table(
        "photo_embedding",
        sa.Column("sha256", sa.Text, nullable=False),
        sa.Column("model_id", sa.Text, nullable=False),
        sa.Column("vector", ARRAY(REAL), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("sha256", "model_id", name="pk_photo_embedding"),
        schema="catalog",
    )
    op.create_table(
        "run",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("dataset_hash", sa.Text, nullable=False),
        sa.Column("config", JSONB, nullable=False),
        sa.Column("counts", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="er",
    )
    op.create_table(
        "candidate",
        *_pair_columns(),
        sa.Column("run_id", sa.Uuid, nullable=False),
        sa.Column("sources", ARRAY(sa.Text), nullable=False),
        sa.Column("blocked", sa.Boolean, nullable=False),
        sa.Column("score", sa.Float),
        sa.Column("evidence", JSONB),
        sa.Column("contributions", JSONB),
        sa.PrimaryKeyConstraint(*PAIR, name="pk_candidate"),
        schema="er",
    )
    op.create_index("ix_candidate_score", "candidate", ["score"], schema="er")
    op.create_table(
        "queue_item",
        sa.Column("queue", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        *_pair_columns(),
        sa.Column("stratum", sa.Text, nullable=False),
        sa.Column("stratum_size", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("queue", "position", name="pk_queue_item"),
        sa.UniqueConstraint("queue", *PAIR, name="uq_queue_item_pair"),
        schema="er",
    )
    op.create_table(
        "label",
        *_pair_columns(),
        sa.Column("labeler", sa.Text, nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("labeled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("seconds", sa.Float),
        sa.PrimaryKeyConstraint(*PAIR, "labeler", name="pk_label"),
        schema="er",
    )


def downgrade() -> None:
    op.drop_table("label", schema="er")
    op.drop_table("queue_item", schema="er")
    op.drop_index("ix_candidate_score", table_name="candidate", schema="er")
    op.drop_table("candidate", schema="er")
    op.drop_table("run", schema="er")
    op.drop_table("photo_embedding", schema="catalog")
