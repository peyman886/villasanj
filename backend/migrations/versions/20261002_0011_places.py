"""Places from OSM (shops, bakeries, restaurants, medical, city centres, forests) and the
distance from every listing to the nearest of each kind (M9 truth check, ADR-0013 amendment).

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE enrichment.place (
            dataset text NOT NULL,
            osm_id text NOT NULL,
            kind text NOT NULL,
            name text,
            geom geography(Geometry, 4326) NOT NULL,
            CONSTRAINT pk_place PRIMARY KEY (dataset, osm_id, kind)
        )
        """
    )
    op.execute("CREATE INDEX ix_place_geom ON enrichment.place USING gist (geom)")
    op.create_table(
        "place_distance",
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("dataset", sa.Text, nullable=False),
        sa.Column("center_m", sa.Float, nullable=False),
        sa.Column("low_m", sa.Float, nullable=False),
        sa.Column("high_m", sa.Float, nullable=False),
        sa.Column("radius_m", sa.Integer, nullable=False),
        sa.Column("radius_assumed", sa.Boolean, nullable=False),
        sa.Column("nearest_name", sa.Text),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("platform", "external_id", "kind", name="pk_place_distance"),
        schema="enrichment",
    )


def downgrade() -> None:
    op.drop_table("place_distance", schema="enrichment")
    op.execute("DROP TABLE enrichment.place")
