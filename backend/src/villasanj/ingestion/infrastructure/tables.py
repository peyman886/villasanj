"""SQLAlchemy Core tables for the ``ingestion`` schema."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Identity,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB

SCHEMA = "ingestion"

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "pk": "pk_%(table_name)s",
    }
)

crawl_run = Table(
    "crawl_run",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("platform", Text, nullable=False),
    Column("live", Boolean, nullable=False),
    Column("status", Text, nullable=False),
    Column("report", JSONB),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    schema=SCHEMA,
)

frontier = Table(
    "frontier",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("platform", Text, nullable=False),
    Column("request_key", String(64), nullable=False, unique=True),
    Column("kind", Text, nullable=False),
    Column("method", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("body", LargeBinary),
    Column("headers", JSONB, nullable=False),
    Column("context", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("next_attempt_at", DateTime(timezone=True), nullable=False),
    Column("last_error", Text),
    Column("discovered_from", Uuid),
    Column("snapshot_id", Uuid),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("ix_frontier_claim", "platform", "status", "next_attempt_at"),
    schema=SCHEMA,
)

snapshot = Table(
    "snapshot",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("platform", Text, nullable=False),
    Column("request_key", String(64), nullable=False),
    Column("kind", Text, nullable=False),
    Column("method", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("request_headers", JSONB, nullable=False),
    Column("request_body", LargeBinary),
    Column("context", JSONB, nullable=False),
    Column("status", Integer, nullable=False),
    Column("final_url", Text, nullable=False),
    Column("headers", JSONB, nullable=False),
    Column("blob_key", String(64), nullable=False),
    Column("size", Integer, nullable=False),
    Column("fetcher", Text, nullable=False),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("run_id", Uuid),
    Index("ix_snapshot_request_key_fetched_at", "request_key", "fetched_at"),
    Index("ix_snapshot_platform_kind", "platform", "kind"),
    schema=SCHEMA,
)
