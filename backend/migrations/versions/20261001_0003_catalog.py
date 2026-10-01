"""Catalog: listings (with a generated PostGIS geography), calendar observations, parse failures.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "catalog"


def upgrade() -> None:
    op.create_table(
        "listing",
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("title_norm", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("description_norm", sa.Text),
        sa.Column("property_type", sa.Text),
        sa.Column("city_fa", sa.Text),
        sa.Column("city_slug", sa.Text),
        sa.Column("lat", sa.Float),
        sa.Column("lon", sa.Float),
        sa.Column("location_radius_m", sa.Integer),
        sa.Column("bedrooms", sa.Integer),
        sa.Column("bathrooms", sa.Integer),
        sa.Column("area_m2", sa.Integer),
        sa.Column("base_capacity", sa.Integer),
        sa.Column("extra_capacity", sa.Integer),
        sa.Column("rating_avg", sa.Float),
        sa.Column("rating_count", sa.Integer),
        sa.Column("check_in_time", sa.Text),
        sa.Column("check_out_time", sa.Text),
        sa.Column("min_nights", sa.Integer),
        sa.Column("instant_booking", sa.Boolean),
        sa.Column("host_ref", sa.Text),
        sa.Column("cancellation_policy_text", sa.Text),
        sa.Column("vat_applies", sa.Boolean),
        sa.Column("rate_base_rial", sa.BigInteger),
        sa.Column("rate_weekend_rial", sa.BigInteger),
        sa.Column("rate_holiday_rial", sa.BigInteger),
        sa.Column("extra_guest_base_rial", sa.BigInteger),
        sa.Column("extra_guest_weekend_rial", sa.BigInteger),
        sa.Column("extra_guest_holiday_rial", sa.BigInteger),
        sa.Column("photos", JSONB, nullable=False),
        sa.Column("amenities", JSONB, nullable=False),
        sa.Column("distance_claims", JSONB, nullable=False),
        sa.Column("snapshot_id", sa.Uuid, nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("platform", "external_id", name="pk_listing"),
        schema=SCHEMA,
    )
    op.execute(
        "ALTER TABLE catalog.listing ADD COLUMN geog geography(Point, 4326) "
        "GENERATED ALWAYS AS (CASE WHEN lat IS NULL OR lon IS NULL THEN NULL "
        "ELSE ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography END) STORED"
    )
    op.execute("CREATE INDEX ix_listing_geog ON catalog.listing USING gist (geog)")
    op.create_table(
        "calendar_observation",
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("night", sa.Date, nullable=False),
        sa.Column("snapshot_id", sa.Uuid, nullable=False),
        sa.Column("availability", sa.Text, nullable=False),
        sa.Column("nightly_rial", sa.BigInteger),
        sa.Column("extra_guest_rial", sa.BigInteger),
        sa.Column("min_nights", sa.Integer),
        sa.Column("is_holiday", sa.Boolean),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "platform", "external_id", "night", "snapshot_id", name="pk_calendar_observation"
        ),
        schema=SCHEMA,
    )
    op.create_table(
        "parse_failure",
        sa.Column("snapshot_id", sa.Uuid),
        sa.Column("platform", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.PrimaryKeyConstraint("snapshot_id", name="pk_parse_failure"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("parse_failure", schema=SCHEMA)
    op.drop_table("calendar_observation", schema=SCHEMA)
    op.execute("DROP INDEX IF EXISTS catalog.ix_listing_geog")
    op.drop_table("listing", schema=SCHEMA)
