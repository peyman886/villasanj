"""Feature claims an LLM read in descriptions, quoted verbatim (ROADMAP M9: the residue the
rules miss). The rules' claims are not stored: they are a pure function of the text.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_claim",
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("feature", sa.Text, nullable=False),
        sa.Column("stance", sa.Text, nullable=False),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("prompt_version", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "platform", "external_id", "feature", "stance", name="pk_llm_claim"
        ),
        schema="enrichment",
    )


def downgrade() -> None:
    op.drop_table("llm_claim", schema="enrichment")
