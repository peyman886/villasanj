"""Feature claims the LLM read, in Postgres (``enrichment.llm_claim``)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Column, DateTime, MetaData, PrimaryKeyConstraint, Table, Text, delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.claim_extraction import CLAIM_PROMPT_VERSION, ReadClaim
from villasanj.enrichment.domain.claim_eval import Stance
from villasanj.enrichment.domain.features import Feature

metadata = MetaData(naming_convention={"pk": "pk_%(table_name)s"})
llm_claim = Table(
    "llm_claim",
    metadata,
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("feature", Text, nullable=False),
    Column("stance", Text, nullable=False),
    Column("quote", Text, nullable=False),
    Column("prompt_version", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("computed_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("platform", "external_id", "feature", "stance"),
    schema="enrichment",
)


class PgReadClaimStore:
    """Only claims read with the current prompt version are returned."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def replace(
        self, listing_id: ListingId, claims: Sequence[ReadClaim], model: str, at: datetime
    ) -> None:
        values = {
            (c.feature, c.stance): {
                "platform": listing_id.platform,
                "external_id": listing_id.external_id,
                "feature": c.feature.value,
                "stance": c.stance.value,
                "quote": c.quote,
                "prompt_version": CLAIM_PROMPT_VERSION,
                "model": model,
                "computed_at": at,
            }
            for c in claims
        }
        async with self._engine.begin() as conn:
            await conn.execute(
                delete(llm_claim).where(
                    (llm_claim.c.platform == listing_id.platform)
                    & (llm_claim.c.external_id == listing_id.external_id)
                )
            )
            if values:
                await conn.execute(insert(llm_claim), list(values.values()))

    async def get(self, listing_id: ListingId) -> list[ReadClaim]:
        query = select(llm_claim).where(
            (llm_claim.c.platform == listing_id.platform)
            & (llm_claim.c.external_id == listing_id.external_id)
            & (llm_claim.c.prompt_version == CLAIM_PROMPT_VERSION)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [ReadClaim(Feature(r.feature), Stance(r.stance), r.quote) for r in rows]

    async def of_platform(self, platform: str) -> dict[ListingId, list[ReadClaim]]:
        query = select(llm_claim).where(
            (llm_claim.c.platform == platform)
            & (llm_claim.c.prompt_version == CLAIM_PROMPT_VERSION)
        )
        found: dict[ListingId, list[ReadClaim]] = defaultdict(list)
        async with self._engine.connect() as conn:
            for r in await conn.execute(query):
                found[ListingId(r.platform, r.external_id)].append(
                    ReadClaim(Feature(r.feature), Stance(r.stance), r.quote)
                )
        return dict(found)
