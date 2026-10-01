"""SQLAlchemy Core tables for the ``catalog`` schema (geography column is generated in SQL)."""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, BIGINT, JSONB, REAL

SCHEMA = "catalog"

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "pk": "pk_%(table_name)s",
    }
)

listing = Table(
    "listing",
    metadata,
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("title_norm", Text, nullable=False),
    Column("description", Text),
    Column("description_norm", Text),
    Column("property_type", Text),
    Column("city_fa", Text),
    Column("city_slug", Text),
    Column("locality_fa", Text),
    Column("lat", Float),
    Column("lon", Float),
    Column("location_radius_m", Integer),
    Column("bedrooms", Integer),
    Column("bathrooms", Integer),
    Column("area_m2", Integer),
    Column("base_capacity", Integer),
    Column("extra_capacity", Integer),
    Column("rating_avg", Float),
    Column("rating_count", Integer),
    Column("check_in_time", Text),
    Column("check_out_time", Text),
    Column("min_nights", Integer),
    Column("instant_booking", Boolean),
    Column("host_ref", Text),
    Column("cancellation_policy_text", Text),
    Column("vat_applies", Boolean),
    Column("rate_base_rial", BIGINT),
    Column("rate_weekend_rial", BIGINT),
    Column("rate_holiday_rial", BIGINT),
    Column("extra_guest_base_rial", BIGINT),
    Column("extra_guest_weekend_rial", BIGINT),
    Column("extra_guest_holiday_rial", BIGINT),
    Column("photos", JSONB, nullable=False),
    Column("amenities", JSONB, nullable=False),
    Column("distance_claims", JSONB, nullable=False),
    Column("snapshot_id", Uuid, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("platform", "external_id", name="pk_listing"),
    schema=SCHEMA,
)

calendar_observation = Table(
    "calendar_observation",
    metadata,
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("night", Date, nullable=False),
    Column("snapshot_id", Uuid, nullable=False),
    Column("availability", Text, nullable=False),
    Column("nightly_rial", BIGINT),
    Column("extra_guest_rial", BIGINT),
    Column("min_nights", Integer),
    Column("is_holiday", Boolean),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint(
        "platform", "external_id", "night", "snapshot_id", name="pk_calendar_observation"
    ),
    schema=SCHEMA,
)

parse_failure = Table(
    "parse_failure",
    metadata,
    Column("snapshot_id", Uuid, primary_key=True),
    Column("platform", Text, nullable=False),
    Column("reason", Text, nullable=False),
    schema=SCHEMA,
)

photo = Table(
    "photo",
    metadata,
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("position", Integer, nullable=False),
    Column("url", Text, nullable=False),
    Column("snapshot_id", Uuid, nullable=False),
    Column("sha256", Text, nullable=False),
    Column("width", Integer, nullable=False),
    Column("height", Integer, nullable=False),
    Column("phash", BIGINT, nullable=False),
    Column("dhash", BIGINT, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("platform", "external_id", "position", name="pk_photo"),
    schema=SCHEMA,
)

photo_embedding = Table(
    "photo_embedding",
    metadata,
    Column("sha256", Text, nullable=False),
    Column("model_id", Text, nullable=False),
    Column("vector", ARRAY(REAL), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("sha256", "model_id", name="pk_photo_embedding"),
    schema=SCHEMA,
)
