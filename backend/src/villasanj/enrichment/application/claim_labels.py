"""The owner's labels of feature claims in 60 descriptions, and the extraction's score on them
(ROADMAP M9 criterion 1). The labeller never sees what the rules extracted."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.claim_extraction import ReadClaimsWithLLM, with_residue
from villasanj.enrichment.domain.claim_eval import ClaimScore, Stance, stances
from villasanj.enrichment.domain.features import Feature, extract_claims
from villasanj.shared.application.clock import Clock
from villasanj.shared.application.llm.types import JobContext

MIN_DESCRIPTION = 80  # characters: shorter descriptions rarely claim anything


@dataclass(frozen=True, slots=True)
class ClaimItem:
    position: int
    listing_id: ListingId


class ClaimLabelStore(Protocol):
    async def items(self, queue: str) -> list[ClaimItem]: ...

    async def save(self, queue: str, items: Sequence[ClaimItem], at: datetime) -> None: ...

    async def labels(self, queue: str, labeler: str) -> dict[ListingId, dict[Feature, Stance]]: ...

    async def save_labels(
        self,
        queue: str,
        listing_id: ListingId,
        labeler: str,
        labels: Mapping[Feature, Stance],
        at: datetime,
    ) -> None: ...


class ClaimQueueExists(ValueError):
    """Queues are drawn once: a second draw would change what was labelled."""


class BuildClaimLabelQueue:
    def __init__(
        self,
        listings: ListingReader,
        store: ClaimLabelStore,
        clock: Clock,
        platforms: Sequence[str],
    ) -> None:
        self._listings = listings
        self._store = store
        self._clock = clock
        self._platforms = tuple(platforms)

    async def run(self, name: str, n: int) -> list[ClaimItem]:
        if await self._store.items(name):
            raise ClaimQueueExists(name)
        candidates = [
            listing.id
            for platform in self._platforms
            for listing in await self._listings.listings(platform)
            if len(listing.description_norm or "") >= MIN_DESCRIPTION
        ]
        candidates.sort(key=lambda x: hashlib.sha256(f"{name}:{x}".encode()).hexdigest())
        items = [ClaimItem(i, x) for i, x in enumerate(candidates[:n], start=1)]
        await self._store.save(name, items, self._clock.now())
        return items


@dataclass(frozen=True, slots=True)
class ClaimTask:
    item: ClaimItem
    total: int
    labelled: int
    current: dict[Feature, Stance]  # this labeller's labels so far (empty: not labelled)
    done: bool


class ClaimLabeling:
    def __init__(self, store: ClaimLabelStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    async def task(self, queue: str, labeler: str, position: int | None = None) -> ClaimTask | None:
        items = await self._store.items(queue)
        if not items:
            return None
        labels = await self._store.labels(queue, labeler)
        if position is not None:
            item = next((i for i in items if i.position == position), items[0])
        else:
            item = next((i for i in items if i.listing_id not in labels), items[-1])
        labelled = sum(i.listing_id in labels for i in items)
        return ClaimTask(
            item, len(items), labelled, labels.get(item.listing_id, {}), labelled == len(items)
        )

    async def record(
        self, queue: str, listing_id: ListingId, labeler: str, labels: Mapping[Feature, Stance]
    ) -> bool:
        """Every feature is stored (one not given is «none»); ``False``: not in the queue."""
        if listing_id not in {i.listing_id for i in await self._store.items(queue)}:
            return False
        complete = {feature: labels.get(feature, Stance.NONE) for feature in Feature}
        await self._store.save_labels(queue, listing_id, labeler, complete, self._clock.now())
        return True


@dataclass(frozen=True, slots=True)
class ClaimEvaluation:
    queue: str
    total: int
    labelled: int
    score: ClaimScore  # the rules alone
    with_llm: ClaimScore | None = None  # the rules plus the LLM's residue
    llm_dropped: int = 0  # LLM claims whose quote was not in the text
    llm_cost: Decimal = Decimal(0)


class EvaluateClaimExtraction:
    def __init__(
        self,
        listings: ListingReader,
        store: ClaimLabelStore,
        reader: ReadClaimsWithLLM | None = None,
    ) -> None:
        self._listings = listings
        self._store = store
        self._reader = reader

    async def descriptions(self, queue: str, labeler: str) -> list[str]:
        """The labelled descriptions (for a dry run of the LLM pass)."""
        labels = await self._store.labels(queue, labeler)
        found = []
        for item in await self._store.items(queue):
            listing = await self._listings.get(item.listing_id)
            if item.listing_id in labels and listing is not None:
                found.append(listing.description_norm or "")
        return found

    async def run(self, queue: str, labeler: str, ctx: JobContext | None = None) -> ClaimEvaluation:
        items = await self._store.items(queue)
        labels = await self._store.labels(queue, labeler)
        rules_only, merged = ClaimScore(), ClaimScore()
        use_llm = self._reader is not None and ctx is not None
        dropped, cost = 0, Decimal(0)
        for item in items:
            if item.listing_id not in labels:
                continue
            listing = await self._listings.get(item.listing_id)
            if listing is None:
                continue
            description = listing.description_norm or ""
            predicted = stances(extract_claims(description))
            rules_only.add(predicted, labels[item.listing_id])
            if use_llm and self._reader is not None and ctx is not None:
                read = await self._reader.run(description, ctx)
                dropped += read.dropped
                cost += read.cost_usd
                merged.add(with_residue(predicted, read.claims), labels[item.listing_id])
        return ClaimEvaluation(
            queue,
            len(items),
            sum(i.listing_id in labels for i in items),
            rules_only,
            merged if use_llm else None,
            dropped,
            cost,
        )
