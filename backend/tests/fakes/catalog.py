"""In-memory catalog repository and a helper to store fixture pages as snapshots."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from tests.fakes.ingestion import InMemoryBlobStore, InMemorySnapshotRepository
from tests.fakes.llm import NOW
from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.ingestion.domain.pages import FetchedPage, PageKind, PageRequest, Snapshot

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


class InMemoryListingRepository:
    def __init__(self) -> None:
        self.listings: dict[ListingId, Listing] = {}
        self.calendar: dict[tuple[ListingId, object, str], CalendarObservation] = {}
        self.failures: dict[str, str] = {}

    async def save(self, listing: Listing, calendar: Sequence[CalendarObservation]) -> bool:
        current = self.listings.get(listing.id)
        for observation in calendar:
            key = (observation.listing_id, observation.night, observation.snapshot_id)
            self.calendar.setdefault(key, observation)
        if current and current.provenance.observed_at > listing.provenance.observed_at:
            return False
        self.listings[listing.id] = listing
        return True

    async def record_failure(self, snapshot_id: str, platform: str, reason: str) -> None:
        self.failures[snapshot_id] = reason

    async def count(self, platform: str) -> int:
        return sum(1 for key in self.listings if key.platform == platform)


async def store_fixture(
    snapshots: InMemorySnapshotRepository,
    blobs: InMemoryBlobStore,
    request: PageRequest,
    fixture: str,
    fetched_at: datetime = NOW,
) -> Snapshot:
    body = (FIXTURES / fixture).read_bytes()
    page = FetchedPage(
        request=request,
        status=200,
        final_url=request.url,
        headers=(("content-type", "text/html; charset=utf-8"),),
        body=body,
        fetched_at=fetched_at,
        fetcher="fixture",
    )
    return await snapshots.save(page, await blobs.put(body), None)


def listing_request(platform: str, url: str, context: tuple[tuple[str, str], ...]) -> PageRequest:
    return PageRequest(platform, PageKind.LISTING, url, context=context)
