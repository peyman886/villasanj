"""Contract tests for the shab adapter on trimmed real responses (tests/fixtures/shab).

Expected values were read from the fixtures by hand.
"""

from datetime import date
from pathlib import Path

import pytest

from tests.fakes.ingestion import REGION
from tests.fakes.llm import NOW
from villasanj.ingestion.application.errors import PageStructureChanged
from villasanj.ingestion.domain.pages import FetchedPage, PageKind, PageRequest
from villasanj.ingestion.domain.parsed import (
    Availability,
    ParsedCalendarDay,
    ParsedDistanceClaim,
    ParsedRateCard,
    TravelMode,
)
from villasanj.ingestion.domain.region import Place, Region
from villasanj.ingestion.infrastructure.sources.shab.adapter import HOUSE_ID, SLUG, ShabAdapter
from villasanj.shared.domain.geo import GeoPoint
from villasanj.shared.domain.money import Money

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "shab"
HOUSE_URL = "https://www.shab.ir/houses/show/2085"
CONTEXT = ((HOUSE_ID, "2085"),)


def fetched(
    name: str, kind: PageKind, url: str, context: tuple[tuple[str, str], ...] = ()
) -> FetchedPage:
    request = PageRequest(SLUG, kind, url, context=context)
    return FetchedPage(request, 200, url, (), (FIXTURES / name).read_bytes(), NOW, "fixture")


def house(name: str = "house_page.html") -> FetchedPage:
    return fetched(name, PageKind.LISTING, HOUSE_URL, CONTEXT)


def test_seeds_are_city_sitemaps_with_encoded_persian_names() -> None:
    region = Region(
        "r",
        "منطقه",
        (Place("ramsar", "رامسر"), Place("tonekabon", "تنکابن")),
        REGION.south_west,
        REGION.north_east,
    )
    assert [r.url for r in ShabAdapter().seed_requests(region)] == [
        "https://www.shab.ir/sitemaps/sitemap-%D8%B1%D8%A7%D9%85%D8%B3%D8%B1.xml",
        "https://www.shab.ir/sitemaps/sitemap-%D8%AA%D9%86%DA%A9%D8%A7%D8%A8%D9%86.xml",
    ]


def test_sitemap_yields_house_pages_only() -> None:
    sitemap = fetched("sitemap_ramsar.xml", PageKind.SITEMAP, "https://www.shab.ir/sitemaps/x.xml")
    assert ShabAdapter().discover(sitemap, REGION) == [
        PageRequest(
            SLUG, PageKind.LISTING, f"https://www.shab.ir/houses/show/{i}", context=((HOUSE_ID, i),)
        )
        for i in ("431", "438", "2085")
    ]


def test_in_region_house_page_requests_three_jalali_months_of_calendar() -> None:
    (calendar,) = ShabAdapter().discover(house(), REGION)  # NOW = 2026-10-01 = 1405/07/09
    assert calendar == PageRequest(
        SLUG,
        PageKind.CALENDAR,
        "https://api.shab.ir/api/fa/sandbox/v_1_4/house/2085/calendar"
        "?from_date=1405-07-01&to_date=1405-10-01",
        headers=(("Accept", "application/json"),),
        context=CONTEXT,
    )


def test_out_of_region_house_gets_no_calendar_request() -> None:
    assert ShabAdapter().discover(house("house_outside_region.html"), REGION) == []


def test_parse_listing() -> None:
    listing = ShabAdapter().parse_listing(house())
    assert listing is not None
    assert (listing.platform, listing.external_id, listing.url) == (SLUG, "2085", HOUSE_URL)
    assert listing.title == "ویلای ساحلی با استخر آبگرم و کلبه چوبی"
    assert (listing.property_type, listing.city_fa, listing.city_slug) == (
        "cottage",
        "رامسر",
        "ramsar",
    )
    assert listing.location == GeoPoint(36.873366, 50.772264)
    assert listing.location_radius_m is None
    assert (listing.bedrooms, listing.area_m2) == (4, 400)
    assert (listing.base_capacity, listing.extra_capacity) == (8, 2)
    assert (listing.rating_avg, listing.rating_count) == (4.6, 2)
    assert (listing.check_in_time, listing.check_out_time) == ("15:00", "12:00")
    assert listing.instant_booking is False
    assert listing.host_ref == "jqE"  # an opaque id, never the host's name
    assert listing.cancellation_policy_text is None  # a bare plan code is not text
    assert listing.calendar == ()  # served on its own endpoint


def test_money_is_read_as_toman() -> None:
    listing = ShabAdapter().parse_listing(house())
    assert listing is not None
    assert listing.rate_card == ParsedRateCard(
        base=Money.from_toman(35_000_000),
        weekend=Money.from_toman(40_000_000),
        holiday=Money.from_toman(40_000_000),
        extra_guest_base=Money.from_toman(2_500_000),
        extra_guest_weekend=Money.from_toman(2_500_000),
        extra_guest_holiday=Money.from_toman(2_500_000),
    )
    assert len(listing.photos) == 3
    assert listing.distance_claims == (
        ParsedDistanceClaim("سوپرمارکت", "5 دقیقه", TravelMode.WALK),
        ParsedDistanceClaim("نانوایی", "5 دقیقه", TravelMode.WALK),
    )


def test_calendar_direct_shape() -> None:
    page = fetched("calendar_direct.json", PageKind.CALENDAR, "https://api.shab.ir/c", CONTEXT)
    calendar = ShabAdapter().parse_calendar(page)
    assert calendar is not None
    assert (calendar.platform, calendar.external_id, len(calendar.days)) == (SLUG, "2085", 5)
    assert calendar.days[0] == ParsedCalendarDay(
        date(2026, 9, 30), Availability.AVAILABLE, Money.from_toman(40_000_000), None, 2, False
    )
    assert calendar.days[-1].night == date(2026, 10, 4)  # 1405/07/12


def test_calendar_nested_shape() -> None:
    page = fetched("calendar_nested.json", PageKind.CALENDAR, "https://api.shab.ir/c", CONTEXT)
    calendar = ShabAdapter().parse_calendar(page)
    assert calendar is not None
    assert [(d.night, d.nightly_price) for d in calendar.days] == [
        (date(2026, 11, 12), Money.from_toman(40_000_000)),  # 1405/08/21
        (date(2026, 11, 13), Money.from_toman(35_000_000)),  # 1405/08/22, not marked peak on shab
        (date(2026, 11, 14), Money.from_toman(35_000_000)),
    ]
    assert all(day.is_holiday is False for day in calendar.days)


def test_structure_changes_are_reported() -> None:
    with pytest.raises(PageStructureChanged):
        ShabAdapter().parse_listing(house("house_without_data.html"))
    broken = fetched("sitemap_ramsar.xml", PageKind.CALENDAR, "https://api.shab.ir/c", CONTEXT)
    with pytest.raises(PageStructureChanged):
        ShabAdapter().parse_calendar(broken)
