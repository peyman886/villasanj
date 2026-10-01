"""Catalog listing: locality (village or neighbourhood).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("listing", sa.Column("locality_fa", sa.Text), schema="catalog")


def downgrade() -> None:
    op.drop_column("listing", "locality_fa", schema="catalog")
