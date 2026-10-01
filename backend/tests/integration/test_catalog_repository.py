"""PgListingRepository: newest wins, calendar history is append-only, reparse is stable."""

from datetime import date, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.catalog.infrastructure.repositories import PgListingRepository
from villasanj.ingestion.domain.parsed import Availability, ParsedCalendarDay, ParsedRateCard
from villasanj.shared.domain.money import Money
from villasanj.shared.domain.stay import DateRange

pytestmark = pytest.mark.integration

FIRST = "00000000-0000-0000-0000-000000000101"
SECOND = "00000000-0000-0000-0000-000000000102"


def observations(listing: Listing, snapshot: str) -> list[CalendarObservation]:
    day = ParsedCalendarDay(
        NOW.date(), Availability.AVAILABLE, Money.from_toman(2_000_000), None, 1, False
    )
    return [CalendarObservation.from_parsed(listing.id, day, snapshot, NOW)]


async def _table_hash(engine: AsyncEngine, platform: str) -> tuple[str, str]:
    async with engine.connect() as conn:
        listing_hash: str = (
            await conn.execute(
                text(
                    "SELECT md5(string_agg(t::text, '|' ORDER BY external_id)) "
                    "FROM catalog.listing t WHERE platform = :p"
                ),
                {"p": platform},
            )
        ).scalar_one()
        calendar_hash: str = (
            await conn.execute(
                text(
                    "SELECT md5(string_agg(t::text, '|' ORDER BY external_id, night, snapshot_id)) "
                    "FROM catalog.calendar_observation t WHERE platform = :p"
                ),
                {"p": platform},
            )
        ).scalar_one()
    return listing_hash, calendar_hash


async def test_newest_wins_and_saving_twice_changes_nothing(engine: AsyncEngine) -> None:
    repo = PgListingRepository(engine)
    platform = f"cat-{id(engine)}"
    old = Listing.from_parsed(parsed(platform=platform, title="عنوان قدیمی"), FIRST, NOW)
    new = Listing.from_parsed(
        parsed(platform=platform, title="عنوان جدید"), SECOND, NOW + timedelta(hours=1)
    )

    assert await repo.save(new, observations(new, SECOND))
    assert not await repo.save(old, observations(old, FIRST))  # older: listing untouched
    before = await _table_hash(engine, platform)
    assert await repo.save(new, observations(new, SECOND))  # same observation again
    assert await _table_hash(engine, platform) == before
    assert await repo.count(platform) == 1

    async with engine.connect() as conn:
        title, geog = (
            await conn.execute(
                text(
                    "SELECT title, ST_AsText(geog::geometry) FROM catalog.listing "
                    "WHERE platform = :p"
                ),
                {"p": platform},
            )
        ).one()
        nights: int = (
            await conn.execute(
                text("SELECT count(*) FROM catalog.calendar_observation WHERE platform = :p"),
                {"p": platform},
            )
        ).scalar_one()
    assert title == "عنوان جدید"
    assert geog == "POINT(50.66 36.9)"
    assert nights == 2  # both observations kept as history


async def test_failures_are_recorded_once(engine: AsyncEngine) -> None:
    repo = PgListingRepository(engine)
    snapshot = "00000000-0000-0000-0000-000000000199"
    await repo.record_failure(snapshot, "example", "no flight data")
    await repo.record_failure(snapshot, "example", "no flight data")
    async with engine.connect() as conn:
        count: int = (
            await conn.execute(
                text("SELECT count(*) FROM catalog.parse_failure WHERE snapshot_id = :s"),
                {"s": snapshot},
            )
        ).scalar_one()
    assert count == 1


async def test_listings_and_calendars_read_back_as_stored(engine: AsyncEngine) -> None:
    platform = f"read-{id(engine)}"
    repo = PgListingRepository(engine)
    card = ParsedRateCard(base=Money.from_toman(1_000_000), extra_guest_holiday=Money.from_rial(7))
    stored = Listing.from_parsed(
        parsed(platform=platform, rate_card=card, photos=("https://c.test/a.jpg",)),
        "00000000-0000-0000-0000-000000000601",
        NOW,
    )
    nights = [date(2026, 10, 15), date(2026, 10, 16), date(2026, 10, 17)]
    calendar = [
        CalendarObservation.from_parsed(
            stored.id,
            ParsedCalendarDay(n, Availability.AVAILABLE, Money.from_toman(9), None, 2, False),
            "00000000-0000-0000-0000-000000000601",
            NOW,
        )
        for n in nights
    ]
    await repo.save(stored, calendar)
    assert await repo.get(stored.id) == stored
    assert await repo.get(ListingId(platform, "missing")) is None
    assert await repo.listings(platform) == [stored]
    two_nights = await repo.calendar(stored.id, DateRange(nights[0], nights[2]))
    assert two_nights == calendar[:2]
