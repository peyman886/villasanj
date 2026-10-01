"""SQLAlchemy Core table metadata for the ``ops`` schema (jobs, LLM cache, LLM ledger)."""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

OPS_SCHEMA = "ops"
CONTEXT_SCHEMAS = ("ingestion", "catalog", "er", "pricing", "enrichment", "discovery", OPS_SCHEMA)
REQUIRED_EXTENSIONS = ("postgis", "vector", "pg_trgm")
USD = Numeric(14, 8)

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "pk": "pk_%(table_name)s",
    }
)

job = Table(
    "job",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("kind", Text, nullable=False),
    Column("params", JSONB, nullable=False),
    Column("budget_usd", USD, nullable=False),
    Column("status", Text, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    schema=OPS_SCHEMA,
)

llm_cache = Table(
    "llm_cache",
    metadata,
    Column("key", String(64), primary_key=True),
    Column("task", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("response_text", Text, nullable=False),
    Column("usage", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    schema=OPS_SCHEMA,
)

llm_call = Table(
    "llm_call",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("job_id", Text, nullable=False),
    Column("task", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("prompt_id", Text, nullable=False),
    Column("prompt_version", Text, nullable=False),
    Column("attempt", Integer, nullable=False),
    Column("status", Text, nullable=False),
    Column("input_tokens", Integer, nullable=False),
    Column("cached_input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("reasoning_tokens", Integer, nullable=False),
    Column("usage_source", Text, nullable=False),
    Column("cost_usd", USD, nullable=False),
    Column("latency_ms", Integer, nullable=False),
    Column("error_code", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index("ix_llm_call_job_id", "job_id"),
    schema=OPS_SCHEMA,
)
