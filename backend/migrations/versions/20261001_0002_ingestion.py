"""Ingestion: crawl runs, frontier queue and immutable snapshots.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "ingestion"


def upgrade() -> None:
    op.create_table(
        "crawl_run",
        sa.Column("id", sa.Uuid),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("live", sa.Boolean, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("report", JSONB),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id", name="pk_crawl_run"),
        schema=SCHEMA,
    )
    op.create_table(
        "frontier",
        sa.Column("id", sa.BigInteger, sa.Identity()),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("method", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("body", sa.LargeBinary),
        sa.Column("headers", JSONB, nullable=False),
        sa.Column("context", JSONB, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.Text),
        sa.Column("discovered_from", sa.Uuid),
        sa.Column("snapshot_id", sa.Uuid),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_frontier"),
        sa.UniqueConstraint("request_key", name="uq_frontier_request_key"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_frontier_claim", "frontier", ["platform", "status", "next_attempt_at"], schema=SCHEMA
    )
    op.create_table(
        "snapshot",
        sa.Column("id", sa.Uuid),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("request_key", sa.String(64), nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("method", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("request_headers", JSONB, nullable=False),
        sa.Column("request_body", sa.LargeBinary),
        sa.Column("context", JSONB, nullable=False),
        sa.Column("status", sa.Integer, nullable=False),
        sa.Column("final_url", sa.Text, nullable=False),
        sa.Column("headers", JSONB, nullable=False),
        sa.Column("blob_key", sa.String(64), nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("fetcher", sa.Text, nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_id", sa.Uuid),
        sa.PrimaryKeyConstraint("id", name="pk_snapshot"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_snapshot_request_key_fetched_at",
        "snapshot",
        ["request_key", "fetched_at"],
        schema=SCHEMA,
    )
    op.create_index("ix_snapshot_platform_kind", "snapshot", ["platform", "kind"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_snapshot_platform_kind", table_name="snapshot", schema=SCHEMA)
    op.drop_index("ix_snapshot_request_key_fetched_at", table_name="snapshot", schema=SCHEMA)
    op.drop_table("snapshot", schema=SCHEMA)
    op.drop_index("ix_frontier_claim", table_name="frontier", schema=SCHEMA)
    op.drop_table("frontier", schema=SCHEMA)
    op.drop_table("crawl_run", schema=SCHEMA)
