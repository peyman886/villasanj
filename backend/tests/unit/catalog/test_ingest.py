"""IngestListingSnapshots: builds the catalog from stored snapshots with zero network access."""

import socket
from datetime import date, timedelta

import pytest

from tests.fakes.catalog import InMemoryListingRepository, listing_request, store_fixture
from tests.fakes.ingestion import InMemoryBlobStore, InMemorySnapshotRepository
from tests.fakes.llm import NOW
from villasanj.catalog.application.ingest import IngestListingSnapshots
from villasanj.catalog.domain.listing import ListingId
from villasanj.ingestion.domain.pages import FetchedPage, PageKind, PageRequest
from villasanj.ingestion.domain.parsed import (
    Availability,
    ParsedCalendar,
    ParsedCalendarDay,
)
from villasanj.ingestion.infrastructure.sources.jabama.adapter import (
    LISTING_CODE,
    SLUG,
    JabamaAdapter,
)
from villasanj.shared.domain.money import Money

URL = "https://www.jabama.com/stay/villa-800749"
CONTEXT = ((LISTING_CODE, "800749"),)


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network access attempted during reparse")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


class World:
    def __init__(self) -> None:
        self.snapshots = InMemorySnapshotRepository()
        self.blobs = InMemoryBlobStore()
        self.listings = InMemoryListingRepository()
        self.ingest = IngestListingSnapshots(
            {SLUG: JabamaAdapter()}, self.snapshots, self.blobs, self.listings
        )


async def test_builds_listing_and_calendar_without_network(no_network: None) -> None:
    world = World()
    await store_fixture(
        world.snapshots, world.blobs, listing_request(SLUG, URL, CONTEXT), "jabama/stay_page.html"
    )
    report = await world.ingest.run(SLUG)
    assert (report.snapshots, report.saved, report.failed) == (1, 1, 0)
    listing = world.listings.listings[ListingId(SLUG, "800749")]
    assert listing.title_norm == "ویلا دوخوابه هونام"
    assert len(world.listings.calendar) == 10


async def test_reparse_is_idempotent(no_network: None) -> None:
    world = World()
    await store_fixture(
        world.snapshots, world.blobs, listing_request(SLUG, URL, CONTEXT), "jabama/stay_page.html"
    )
    await world.ingest.run(SLUG)
    first = (dict(world.listings.listings), dict(world.listings.calendar))
    await world.ingest.run(SLUG)
    assert (world.listings.listings, world.listings.calendar) == first


async def test_newer_observation_wins_whatever_the_order() -> None:
    world = World()
    request = listing_request(SLUG, URL, CONTEXT)
    newer = await store_fixture(
        world.snapshots, world.blobs, request, "jabama/stay_page.html", NOW + timedelta(hours=2)
    )
    await store_fixture(world.snapshots, world.blobs, request, "jabama/stay_page.html", NOW)
    report = await world.ingest.run(SLUG)
    assert (report.saved, report.superseded) == (1, 1)
    assert world.listings.listings[ListingId(SLUG, "800749")].provenance.snapshot_id == newer.id
    assert len(world.listings.calendar) == 20  # both observations are kept as history


async def test_structure_changes_are_quarantined() -> None:
    world = World()
    broken = await store_fixture(
        world.snapshots,
        world.blobs,
        listing_request(SLUG, URL, CONTEXT),
        "jabama/search_without_flight.html",
    )
    report = await world.ingest.run(SLUG)
    assert report.failed == 1
    assert broken.id in world.listings.failures


async def test_non_listing_snapshots_are_ignored() -> None:
    world = World()
    search = PageRequest(SLUG, PageKind.SEARCH, "https://www.jabama.com/city-ramsar")
    await store_fixture(world.snapshots, world.blobs, search, "jabama/search_page.html")
    report = await world.ingest.run(SLUG)
    assert report.snapshots == 0  # only listing snapshots are read


class StandaloneCalendarAdapter(JabamaAdapter):
    """A platform whose calendar lives on its own page (the generic capability under test)."""

    def parse_calendar(self, page: FetchedPage) -> ParsedCalendar | None:
        day = ParsedCalendarDay(
            date(2026, 10, 8), Availability.AVAILABLE, Money.from_toman(1), None, 2, None
        )
        return ParsedCalendar(SLUG, "800749", (day,))


async def test_calendar_pages_append_observations() -> None:
    world = World()
    world.ingest = IngestListingSnapshots(
        {SLUG: StandaloneCalendarAdapter()}, world.snapshots, world.blobs, world.listings
    )
    calendar = PageRequest(SLUG, PageKind.CALENDAR, "https://api.example.test/calendar/800749")
    snapshot = await store_fixture(
        world.snapshots, world.blobs, calendar, "jabama/search_last_page.html"
    )
    report = await world.ingest.run(SLUG)
    assert (report.calendars, report.saved) == (1, 0)
    observation = world.listings.calendar[
        (ListingId(SLUG, "800749"), date(2026, 10, 8), snapshot.id)
    ]
    assert observation.min_nights == 2
