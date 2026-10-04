"""SQLAlchemy Core tables for the ``er`` schema."""

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Identity,
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

label_revision = Table(
    "label_revision",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    *_pair(),
    Column("labeler", Text, nullable=False),
    Column("before", Text, nullable=False),
    Column("after", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("revised_by", Text, nullable=False),
    Column("revised_at", DateTime(timezone=True), nullable=False),
    schema=SCHEMA,
)

villa = Table(
    "villa",
    metadata,
    Column("id", Text, primary_key=True),
    Column("run_id", Uuid, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    schema=SCHEMA,
)

villa_member = Table(
    "villa_member",
    metadata,
    Column("villa_id", Text, ForeignKey("er.villa.id", ondelete="CASCADE"), nullable=False),
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    PrimaryKeyConstraint("platform", "external_id", name="pk_villa_member"),
    UniqueConstraint("villa_id", "platform", name="uq_villa_member_one_per_platform"),
    schema=SCHEMA,
)

villa_event = Table(
    "villa_event",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("run_id", Uuid, nullable=False),
    Column("kind", Text, nullable=False),
    Column("villa_id", Text, nullable=False),
    Column("previous_ids", ARRAY(Text), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    schema=SCHEMA,
)


judgement = Table(
    "judgement",
    metadata,
    Column("left_platform", Text, nullable=False),
    Column("left_id", Text, nullable=False),
    Column("right_platform", Text, nullable=False),
    Column("right_id", Text, nullable=False),
    Column("verdict", Text, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("evidence", ARRAY(Text), nullable=False),
    Column("rationale", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("prompt_version", Text, nullable=False),
    Column("judged_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("left_platform", "left_id", "right_platform", "right_id"),
    schema="er",
)
