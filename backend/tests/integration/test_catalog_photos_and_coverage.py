"""Photo fingerprints, photo URL source and scenario coverage against a real Postgres."""

from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.catalog.domain.photo import ListingPhoto, PerceptualFingerprint
from villasanj.catalog.infrastructure.repositories import (
    PgCoverageQuery,
    PgListingRepository,
    PgPhotoRepository,
)
from villasanj.ingestion.domain.parsed import Availability, ParsedCalendarDay

pytestmark = pytest.mark.integration

SNAPSHOT = "00000000-0000-0000-0000-000000000301"
NIGHTS = [date(2026, 10, 15), date(2026, 10, 16)]


async def test_photo_urls_and_fingerprints(engine: AsyncEngine) -> None:
    platform = f"photo-{id(engine)}"
    listings = PgListingRepository(engine)
    listing = Listing.from_parsed(
        parsed(
            platform=platform,
            photos=("https://c.test/a.jpg", "https://c.test/b.jpg", "https://c.test/c.jpg"),
        ),
        SNAPSHOT,
        NOW,
    )
    await listings.save(listing, [])
    urls = await listings.photo_urls(platform, per_listing=2, listing_limit=None)
    assert urls == [
        (ListingId(platform, "42"), 0, "https://c.test/a.jpg"),
        (ListingId(platform, "42"), 1, "https://c.test/b.jpg"),
    ]
    photos = PgPhotoRepository(engine)
    fingerprint = PerceptualFingerprint(phash=-(2**63), dhash=2**63 - 1, width=749, height=562)
    photo = ListingPhoto(
        ListingId(platform, "42"), 0, urls[0][2], SNAPSHOT, "a" * 64, fingerprint, NOW
    )
    await photos.save(photo)
    await photos.save(photo)  # idempotent


async def test_coverage_counts_listings_with_every_scenario_night(engine: AsyncEngine) -> None:
    platform = f"cov-{id(engine)}"
    repo = PgListingRepository(engine)
    for external_id, nights in (("1", NIGHTS), ("2", NIGHTS[:1])):
        listing = Listing.from_parsed(
            parsed(platform=platform, external_id=external_id), SNAPSHOT, NOW
        )
        days = [
            ParsedCalendarDay(n, Availability.AVAILABLE, None, None, None, None) for n in nights
        ]
        await repo.save(
            listing,
            [
                CalendarObservation.from_parsed(
                    listing.id, d, SNAPSHOT, NOW + timedelta(hours=int(external_id))
                )
                for d in days
            ],
        )
    counts = await PgCoverageQuery(engine).counts(platform, NIGHTS)
    assert (counts.listings, counts.covered) == (2, 1)
    assert counts.earliest == counts.latest == NOW + timedelta(hours=1)
