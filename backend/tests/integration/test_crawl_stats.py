"""Crawl metrics and photo counts against a real Postgres."""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fakes.ingestion import SteppingClock
from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from villasanj.catalog.domain.listing import Listing, ListingId
from villasanj.catalog.domain.photo import ListingPhoto, PerceptualFingerprint, PhotoEmbedding
from villasanj.catalog.infrastructure.repositories import (
    PgEmbeddingStore,
    PgListingRepository,
    PgPhotoRepository,
    PgPhotoStatsQuery,
)
from villasanj.ingestion.application.ports import CrawlReport
from villasanj.ingestion.domain.pages import FetchedPage, PageKind, PageRequest
from villasanj.ingestion.infrastructure.repositories import (
    PgCrawlRunRepository,
    PgFrontierRepository,
    PgSnapshotRepository,
)
from villasanj.ingestion.infrastructure.stats import PgCrawlStatsQuery
from villasanj.shared.application.blobs import BlobRef

pytestmark = pytest.mark.integration

SNAPSHOT = "00000000-0000-0000-0000-000000000e01"


async def test_traffic_progress_responses_and_runs(engine: AsyncEngine) -> None:
    platform = f"stats-{id(engine)}"
    host = f"cdn{id(engine)}.stats.test"
    run_id = str(uuid.uuid4())
    snapshots = PgSnapshotRepository(engine)
    at = NOW
    for i, (status, gap) in enumerate([(200, 0.0), (200, 3.2), (404, 4.0), (200, 3.6)]):
        at += timedelta(seconds=gap)
        request = PageRequest(platform, PageKind.PHOTO, f"https://{host}/{i}.jpg")
        page = FetchedPage(request, status, request.url, (), b"x", at, "httpx")
        await snapshots.save(page, BlobRef(f"{i:064x}", 100 + i), run_id)

    stats = PgCrawlStatsQuery(engine)
    (traffic,) = [t for t in await stats.traffic() if t.platform == platform]
    assert traffic.host == host
    assert (traffic.responses, traffic.statuses) == (4, {200: 3, 404: 1})
    assert traffic.stored_bytes == 100 + 101 + 102 + 103
    assert (traffic.min_interval_s, traffic.median_interval_s) == (3.2, 3.6)

    (responses,) = [r for r in await stats.responses(["photo"]) if r.platform == platform]
    assert responses.requests_by_status == {200: 3, 404: 1}

    frontier = PgFrontierRepository(engine, SteppingClock())
    await frontier.enqueue([PageRequest(platform, PageKind.PHOTO, f"https://{host}/q.jpg")], None)
    item = await frontier.claim(platform, NOW)
    assert item is not None
    await frontier.give_up(item, "http-404")
    (progress,) = [p for p in await stats.progress() if p.platform == platform]
    assert progress.statuses == {"failed": 1}
    assert progress.reasons == {"http-404": 1}

    runs = PgCrawlRunRepository(engine, SteppingClock())
    started = await runs.start(platform, live=True)
    await runs.finish(CrawlReport(started, platform, True, fetched=4))
    (latest,) = [r for r in await stats.runs(100) if r.platform == platform]
    assert (latest.status, latest.fetched, latest.stop_reason) == ("finished", 4, "frontier-empty")


async def test_photo_counts_per_platform(engine: AsyncEngine) -> None:
    platform = f"photocount-{id(engine)}"
    listings = PgListingRepository(engine)
    photo_urls = ("https://c.test/1.jpg", "https://c.test/2.jpg")
    for external_id in ("1", "2"):
        listing = Listing.from_parsed(
            parsed(platform=platform, external_id=external_id, photos=photo_urls), SNAPSHOT, NOW
        )
        await listings.save(listing, [])
    photos = PgPhotoRepository(engine)
    for external_id, sha in (("1", "a" * 64), ("2", "a" * 64), ("2", "b" * 64)):
        position = 1 if sha == "b" * 64 else 0
        fingerprint = PerceptualFingerprint(1, 2, 3, 4)
        await photos.save(
            ListingPhoto(
                ListingId(platform, external_id), position, "u", SNAPSHOT, sha, fingerprint, NOW
            )
        )
    await PgEmbeddingStore(engine, SteppingClock()).save(
        [PhotoEmbedding("a" * 64, "m@count", (1.0,))]
    )
    (counts,) = [
        c for c in await PgPhotoStatsQuery(engine).counts("m@count") if c.platform == platform
    ]
    assert (counts.listings, counts.referenced) == (2, 4)
    assert (counts.fingerprinted, counts.distinct_images, counts.embedded) == (3, 2, 1)
