"""The claim-labelling queue and the owner's labels in Postgres (``enrichment`` schema)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    delete,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.claim_labels import ClaimItem
from villasanj.enrichment.domain.claim_eval import Stance
from villasanj.enrichment.domain.features import Feature

SCHEMA = "enrichment"
metadata = MetaData(
    naming_convention={"pk": "pk_%(table_name)s", "uq": "uq_%(table_name)s_listing"}
)

claim_label_queue = Table(
    "claim_label_queue",
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
claim_label = Table(
    "claim_label",
    metadata,
    Column("queue", Text, nullable=False),
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("labeler", Text, nullable=False),
    Column("feature", Text, nullable=False),
    Column("stance", Text, nullable=False),
    Column("labeled_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("queue", "platform", "external_id", "labeler", "feature"),
    schema=SCHEMA,
)


class PgClaimLabelStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def items(self, queue: str) -> list[ClaimItem]:
        query = (
            select(claim_label_queue)
            .where(claim_label_queue.c.queue == queue)
            .order_by(claim_label_queue.c.position)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [ClaimItem(r.position, ListingId(r.platform, r.external_id)) for r in rows]

    async def save(self, queue: str, items: Sequence[ClaimItem], at: datetime) -> None:
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
                await conn.execute(insert(claim_label_queue), values)

    async def labels(self, queue: str, labeler: str) -> dict[ListingId, dict[Feature, Stance]]:
        query = select(claim_label).where(
            (claim_label.c.queue == queue) & (claim_label.c.labeler == labeler)
        )
        found: dict[ListingId, dict[Feature, Stance]] = {}
        async with self._engine.connect() as conn:
            for r in await conn.execute(query):
                found.setdefault(ListingId(r.platform, r.external_id), {})[Feature(r.feature)] = (
                    Stance(r.stance)
                )
        return found

    async def save_labels(
        self,
        queue: str,
        listing_id: ListingId,
        labeler: str,
        labels: Mapping[Feature, Stance],
        at: datetime,
    ) -> None:
        values = [
            {
                "queue": queue,
                "platform": listing_id.platform,
                "external_id": listing_id.external_id,
                "labeler": labeler,
                "feature": feature.value,
                "stance": stance.value,
                "labeled_at": at,
            }
            for feature, stance in labels.items()
        ]
        async with self._engine.begin() as conn:
            await conn.execute(
                delete(claim_label).where(
                    (claim_label.c.queue == queue)
                    & (claim_label.c.platform == listing_id.platform)
                    & (claim_label.c.external_id == listing_id.external_id)
                    & (claim_label.c.labeler == labeler)
                )
            )
            if values:
                await conn.execute(insert(claim_label), values)
