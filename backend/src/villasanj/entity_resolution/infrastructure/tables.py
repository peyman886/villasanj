"""SQLAlchemy Core tables for the ``er`` schema."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

SCHEMA = "er"
PAIR = ("left_platform", "left_id", "right_platform", "right_id")

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "pk": "pk_%(table_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
    }
)


def _pair() -> list[Column[str]]:
    return [Column(name, Text, nullable=False) for name in PAIR]


run = Table(
    "run",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("dataset_hash", Text, nullable=False),
    Column("config", JSONB, nullable=False),
    Column("counts", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    schema=SCHEMA,
)

candidate = Table(
    "candidate",
    metadata,
    *_pair(),
    Column("run_id", Uuid, nullable=False),
    Column("sources", ARRAY(Text), nullable=False),
    Column("blocked", Boolean, nullable=False),
    Column("score", Float),
    Column("evidence", JSONB),
    Column("contributions", JSONB),
    PrimaryKeyConstraint(*PAIR, name="pk_candidate"),
    schema=SCHEMA,
)

queue_item = Table(
    "queue_item",
    metadata,
    Column("queue", Text, nullable=False),
    Column("position", Integer, nullable=False),
    *_pair(),
    Column("stratum", Text, nullable=False),
    Column("stratum_size", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("queue", "position", name="pk_queue_item"),
    UniqueConstraint("queue", *PAIR, name="uq_queue_item_pair"),
    schema=SCHEMA,
)

label = Table(
    "label",
    metadata,
    *_pair(),
    Column("labeler", Text, nullable=False),
    Column("label", Text, nullable=False),
    Column("labeled_at", DateTime(timezone=True), nullable=False),
    Column("seconds", Float),
    PrimaryKeyConstraint(*PAIR, "labeler", name="pk_label"),
    schema=SCHEMA,
)
