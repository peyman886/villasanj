"""The summary review queue and the owner's verdicts in Postgres (``enrichment`` schema)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.summary_review import ReviewItem, Verdict

SCHEMA = "enrichment"
metadata = MetaData(
    naming_convention={"pk": "pk_%(table_name)s", "uq": "uq_%(table_name)s_listing"}
)

summary_review_queue = Table(
    "summary_review_queue",
    metadata,
    Column("queue", Text, nullable=False),
    Column("position", Integer, nullable=False),
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("queue", "position"),
    UniqueConstraint("queue", "platform", "external_id"),
    schema=SCHEMA,
)
summary_review_label = Table(
    "summary_review_label",
    metadata,
    Column("queue", Text, nullable=False),
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("labeler", Text, nullable=False),
    Column("faithful", Boolean, nullable=False),
    Column("note", Text),
    Column("labeled_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("queue", "platform", "external_id", "labeler"),
    schema=SCHEMA,
)


class PgSummaryReviewStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def items(self, queue: str) -> list[ReviewItem]:
        query = (
            select(summary_review_queue)
            .where(summary_review_queue.c.queue == queue)
            .order_by(summary_review_queue.c.position)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [ReviewItem(r.position, ListingId(r.platform, r.external_id)) for r in rows]

    async def save(self, queue: str, items: Sequence[ReviewItem], at: datetime) -> None:
        values = [
            {
                "queue": queue,
                "position": i.position,
                "platform": i.listing_id.platform,
                "external_id": i.listing_id.external_id,
                "created_at": at,
            }
            for i in items
        ]
        if values:
            async with self._engine.begin() as conn:
                await conn.execute(insert(summary_review_queue), values)

    async def verdicts(self, queue: str, labeler: str) -> dict[ListingId, Verdict]:
        query = select(summary_review_label).where(
            (summary_review_label.c.queue == queue) & (summary_review_label.c.labeler == labeler)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return {ListingId(r.platform, r.external_id): Verdict(r.faithful, r.note) for r in rows}

    async def save_verdict(
        self, queue: str, listing_id: ListingId, labeler: str, verdict: Verdict, at: datetime
    ) -> None:
        statement = insert(summary_review_label).values(
            queue=queue,
            platform=listing_id.platform,
            external_id=listing_id.external_id,
            labeler=labeler,
            faithful=verdict.faithful,
            note=verdict.note,
            labeled_at=at,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["queue", "platform", "external_id", "labeler"],
            set_={"faithful": verdict.faithful, "note": verdict.note, "labeled_at": at},
        )
        async with self._engine.begin() as conn:
            await conn.execute(statement)
