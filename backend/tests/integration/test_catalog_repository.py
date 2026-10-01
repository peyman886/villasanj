"""PgListingRepository: newest wins, calendar history is append-only, reparse is stable."""

from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from villasanj.catalog.domain.listing import CalendarObservation, Listing
from villasanj.catalog.infrastructure.repositories import PgListingRepository
from villasanj.ingestion.domain.parsed import Availability, ParsedCalendarDay
from villasanj.shared.domain.money import Money

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
