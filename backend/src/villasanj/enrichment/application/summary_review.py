"""The owner's blind review of review summaries (ROADMAP M10 criterion 3).

A queue of listings is drawn once (deterministic, seeded by its name) among listings with enough
reviews with text. For each, the owner reads the summary next to every raw review and says
whether it is faithful. The target is at least 18 of 20; the result is recorded either way.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.review_summary import ListingReviews
from villasanj.shared.application.clock import Clock

MIN_TEXT_REVIEWS = 5  # enough reviews for a summary worth judging
TARGET_FAITHFUL = 18  # of 20 (M10 criterion 3)


@dataclass(frozen=True, slots=True)
class Verdict:
    faithful: bool
    note: str | None


@dataclass(frozen=True, slots=True)
class ReviewItem:
    position: int
    listing_id: ListingId


class SummaryReviewStore(Protocol):
    async def items(self, queue: str) -> list[ReviewItem]: ...

    async def save(self, queue: str, items: Sequence[ReviewItem], at: datetime) -> None: ...

    async def verdicts(self, queue: str, labeler: str) -> dict[ListingId, Verdict]: ...

    async def save_verdict(
        self, queue: str, listing_id: ListingId, labeler: str, verdict: Verdict, at: datetime
    ) -> None: ...


class SummaryQueueExists(ValueError):
    """Queues are drawn once: a second draw would change what was reviewed."""


def draw(name: str, candidates: Sequence[ListingId], n: int) -> list[ListingId]:
    def key(listing_id: ListingId) -> str:
        return hashlib.sha256(f"{name}:{listing_id}".encode()).hexdigest()

    return sorted(candidates, key=key)[:n]


class BuildSummaryReviewQueue:
    def __init__(
        self,
        listings: ListingReader,
        reviews: ListingReviews,
        store: SummaryReviewStore,
        clock: Clock,
        platforms: Sequence[str],
    ) -> None:
        self._listings = listings
        self._reviews = reviews
        self._store = store
        self._clock = clock
        self._platforms = tuple(platforms)

    async def run(self, name: str, n: int) -> list[ReviewItem]:
        if await self._store.items(name):
            raise SummaryQueueExists(name)
        candidates = []
        for platform in self._platforms:
            for listing in await self._listings.listings(platform):
                reviews = await self._reviews.reviews(listing.id)
                if sum(bool(r.text_norm) for r in reviews) >= MIN_TEXT_REVIEWS:
                    candidates.append(listing.id)
        items = [
            ReviewItem(position, listing_id)
            for position, listing_id in enumerate(draw(name, candidates, n), start=1)
        ]
        await self._store.save(name, items, self._clock.now())
        return items


@dataclass(frozen=True, slots=True)
class ReviewTask:
    item: ReviewItem
    total: int
    reviewed: int
    current: Verdict | None
    done: bool


class SummaryReviewing:
    def __init__(self, store: SummaryReviewStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    async def task(
        self, queue: str, labeler: str, position: int | None = None
    ) -> ReviewTask | None:
        """The listing at ``position``, or the first not reviewed yet; ``None``: no such queue."""
        items = await self._store.items(queue)
        if not items:
            return None
        verdicts = await self._store.verdicts(queue, labeler)
        if position is not None:
            item = next((i for i in items if i.position == position), items[0])
        else:
            item = next((i for i in items if i.listing_id not in verdicts), items[-1])
        reviewed = sum(i.listing_id in verdicts for i in items)
        return ReviewTask(
            item, len(items), reviewed, verdicts.get(item.listing_id), reviewed == len(items)
        )

    async def record(
        self, queue: str, listing_id: ListingId, labeler: str, verdict: Verdict
    ) -> bool:
        """``False`` when the listing is not in the queue."""
        if listing_id not in {i.listing_id for i in await self._store.items(queue)}:
            return False
        await self._store.save_verdict(queue, listing_id, labeler, verdict, self._clock.now())
        return True


@dataclass(frozen=True, slots=True)
class SummaryReviewResult:
    queue: str
    total: int
    reviewed: int
    faithful: int
    unfaithful: list[tuple[ListingId, str | None]]

    @property
    def meets_target(self) -> bool | None:
        """``None`` until every summary of the queue is reviewed."""
        if self.reviewed < self.total:
            return None
        return self.faithful >= TARGET_FAITHFUL * self.total / 20


class EvaluateSummaryReviews:
    def __init__(self, store: SummaryReviewStore) -> None:
        self._store = store

    async def run(self, queue: str, labeler: str) -> SummaryReviewResult:
        items = await self._store.items(queue)
        verdicts = await self._store.verdicts(queue, labeler)
        judged = [(i.listing_id, verdicts[i.listing_id]) for i in items if i.listing_id in verdicts]
        return SummaryReviewResult(
            queue,
            len(items),
            len(judged),
            sum(v.faithful for _, v in judged),
            [(listing_id, v.note) for listing_id, v in judged if not v.faithful],
        )
