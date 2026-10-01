"""Build the catalog from stored snapshots. Takes no Fetcher: it cannot touch the network."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from typing import Protocol

import structlog

from villasanj.catalog.domain.listing import CalendarObservation, Listing
from villasanj.ingestion.application.errors import PageStructureChanged
from villasanj.ingestion.application.ports import SnapshotRepository, SourceAdapter
from villasanj.ingestion.domain.pages import FetchedPage, PageKind, Snapshot
from villasanj.shared.application.blobs import BlobStore

log = structlog.get_logger(__name__)


class ListingRepository(Protocol):
    async def save(self, listing: Listing, calendar: Sequence[CalendarObservation]) -> bool:
        """Upsert idempotently. Returns False when a newer observation is already stored."""
        ...

    async def record_failure(self, snapshot_id: str, platform: str, reason: str) -> None: ...

    async def count(self, platform: str) -> int: ...


@dataclass(frozen=True, slots=True)
class IngestReport:
    platform: str
    snapshots: int = 0
    saved: int = 0
    superseded: int = 0
    not_listing: int = 0
    failed: int = 0


class IngestListingSnapshots:
    def __init__(
        self,
        adapters: Mapping[str, SourceAdapter],
        snapshots: SnapshotRepository,
        blobs: BlobStore,
        listings: ListingRepository,
    ) -> None:
        self._adapters = adapters
        self._snapshots = snapshots
        self._blobs = blobs
        self._listings = listings

    async def run(self, platform: str) -> IngestReport:
        adapter = self._adapters[platform]
        report = IngestReport(platform=platform)
        for snapshot in await self._snapshots.list_for(platform, [PageKind.LISTING]):
            report = await self._ingest_one(adapter, snapshot, report)
        log.info("catalog.ingested", **asdict(report))
        return report

    async def _ingest_one(
        self, adapter: SourceAdapter, snapshot: Snapshot, report: IngestReport
    ) -> IngestReport:
        report = replace(report, snapshots=report.snapshots + 1)
        page = await self._page(snapshot)
        try:
            parsed = adapter.parse_listing(page)
        except PageStructureChanged as error:
            await self._listings.record_failure(snapshot.id, snapshot.request.platform, str(error))
            return replace(report, failed=report.failed + 1)
        if parsed is None:
            return replace(report, not_listing=report.not_listing + 1)
        listing = Listing.from_parsed(parsed, snapshot.id, snapshot.fetched_at)
        calendar = [
            CalendarObservation.from_parsed(listing.id, day, snapshot.id, snapshot.fetched_at)
            for day in parsed.calendar
        ]
        if await self._listings.save(listing, calendar):
            return replace(report, saved=report.saved + 1)
        return replace(report, superseded=report.superseded + 1)

    async def _page(self, snapshot: Snapshot) -> FetchedPage:
        return FetchedPage(
            request=snapshot.request,
            status=snapshot.status,
            final_url=snapshot.final_url,
            headers=snapshot.headers,
            body=await self._blobs.get(snapshot.blob_key),
            fetched_at=snapshot.fetched_at,
            fetcher=snapshot.fetcher,
        )
