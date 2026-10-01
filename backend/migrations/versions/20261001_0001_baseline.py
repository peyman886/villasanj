"""Baseline: extensions, one schema per bounded context, ops tables (jobs, LLM cache, LLM ledger).

Revision ID: 0001
Revises:
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies: migrations must not change when application constants change.
EXTENSIONS = ("postgis", "vector", "pg_trgm")
SCHEMAS = ("ingestion", "catalog", "er", "pricing", "enrichment", "discovery", "ops")
USD = sa.Numeric(14, 8)


def upgrade() -> None:
    for extension in EXTENSIONS:
        op.execute(f'CREATE EXTENSION IF NOT EXISTS "{extension}"')
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    op.create_table(
        "job",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("params", JSONB, nullable=False),
        sa.Column("budget_usd", USD, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id", name="pk_job"),
        schema="ops",
    )
    op.create_table(
        "llm_cache",
        sa.Column("key", sa.String(64)),
        sa.Column("task", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("response_text", sa.Text, nullable=False),
        sa.Column("usage", JSONB, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("key", name="pk_llm_cache"),
        schema="ops",
    )
    op.create_table(
        "llm_call",
        sa.Column("id", sa.BigInteger, sa.Identity()),
        sa.Column("job_id", sa.Text, nullable=False),
        sa.Column("task", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("prompt_id", sa.Text, nullable=False),
        sa.Column("prompt_version", sa.Text, nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("input_tokens", sa.Integer, nullable=False),
        sa.Column("cached_input_tokens", sa.Integer, nullable=False),
        sa.Column("output_tokens", sa.Integer, nullable=False),
        sa.Column("reasoning_tokens", sa.Integer, nullable=False),
        sa.Column("usage_source", sa.Text, nullable=False),
        sa.Column("cost_usd", USD, nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("error_code", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_llm_call"),
        schema="ops",
    )
    op.create_index("ix_llm_call_job_id", "llm_call", ["job_id"], schema="ops")


def downgrade() -> None:
    op.drop_index("ix_llm_call_job_id", table_name="llm_call", schema="ops")
    for table in ("llm_call", "llm_cache", "job"):
        op.drop_table(table, schema="ops")
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema}")
    for extension in reversed(EXTENSIONS):
        op.execute(f'DROP EXTENSION IF EXISTS "{extension}"')
