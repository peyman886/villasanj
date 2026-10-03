"""One villa across its listings: conflicts are shown per platform, nights are never merged."""

from dataclasses import replace
from datetime import date, timedelta

from tests.unit.catalog.test_reports import listing
from tests.unit.pricing.test_quote import night
from villasanj.catalog.domain.listing import ListingId
from villasanj.discovery.domain.villa import conflicts, merge_calendars
from villasanj.ingestion.domain.parsed import Availability

DAY = date(2026, 10, 15)


def test_conflicts_name_each_platforms_value_and_ignore_rounding_and_gaps() -> None:
    jabama = listing("1", platform="jabama", bedrooms=2, area_m2=100, base_capacity=4)
    shab = listing("1", platform="shab", bedrooms=3, area_m2=110, base_capacity=None)
    found = {c.field: c.values for c in conflicts([jabama, shab])}
    assert found == {"bedrooms": {"jabama": 2, "shab": 3}}  # 100 vs 110 m2 is one measurement
    assert conflicts([jabama, replace(shab, area_m2=200)])[-1].field == "area_m2"


def test_a_night_free_on_one_platform_and_taken_on_the_other_is_hidden() -> None:
    free = replace(night(DAY), listing_id=ListingId("jabama", "1"))
    taken = replace(
        night(DAY, availability=Availability.UNAVAILABLE, age_hours=2),
        listing_id=ListingId("shab", "1"),
    )
    stale = replace(
        night(DAY + timedelta(days=1), availability=Availability.UNAVAILABLE, age_hours=30),
        listing_id=ListingId("shab", "1"),
    )
    later = replace(night(DAY + timedelta(days=1)), listing_id=ListingId("jabama", "1"))
    merged = merge_calendars(
        {"jabama": [free, later], "shab": [taken, stale]}, max_gap=timedelta(hours=6)
    )
    first, second = merged
    assert first.hidden
    assert set(first.by_platform) == {"jabama", "shab"}
    assert not second.hidden  # observed 30 h apart: not comparable
