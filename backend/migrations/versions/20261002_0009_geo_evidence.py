"""Geo evidence: OSM coastline, distance to the coast and free-flow drive times (ADR-0013).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE enrichment.coastline (
            osm_way_id bigint NOT NULL,
            dataset text NOT NULL,
            geom geography(LineString, 4326) NOT NULL,
            CONSTRAINT pk_coastline PRIMARY KEY (dataset, osm_way_id)
        )
        """
    )
    op.execute("CREATE INDEX ix_coastline_geom ON enrichment.coastline USING gist (geom)")
    op.create_table(
        "coast_distance",
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("dataset", sa.Text, nullable=False),
        sa.Column("center_m", sa.Float, nullable=False),
        sa.Column("low_m", sa.Float, nullable=False),  # nearest any point of the circle can be
        sa.Column("high_m", sa.Float, nullable=False),
        sa.Column("radius_m", sa.Integer, nullable=False),
        sa.Column("radius_assumed", sa.Boolean, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("platform", "external_id", name="pk_coast_distance"),
        schema="enrichment",
    )
    op.create_table(
        "drive_time",
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("origin", sa.Text, nullable=False),
        sa.Column("dataset", sa.Text, nullable=False),
        sa.Column("center_s", sa.Float),  # null: the published point could not be routed
        sa.Column("low_s", sa.Float),
        sa.Column("high_s", sa.Float),
        sa.Column("center_m", sa.Float),
        sa.Column("routed_points", sa.Integer, nullable=False),
        sa.Column("radius_m", sa.Integer, nullable=False),
        sa.Column("radius_assumed", sa.Boolean, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("platform", "external_id", "origin", name="pk_drive_time"),
        schema="discovery",
    )


def downgrade() -> None:
    op.drop_table("drive_time", schema="discovery")
    op.drop_table("coast_distance", schema="enrichment")
    op.execute("DROP TABLE enrichment.coastline")
