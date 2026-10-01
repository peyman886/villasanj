"""parse_listing on a trimmed real stay page. Expected values were read from the fixture by hand."""

from datetime import date
from pathlib import Path

import pytest

from tests.fakes.llm import NOW
from villasanj.ingestion.application.errors import PageStructureChanged
from villasanj.ingestion.domain.pages import FetchedPage, PageKind, PageRequest
from villasanj.ingestion.domain.parsed import (
    Availability,
    ParsedAmenity,
    ParsedCalendarDay,
    ParsedDistanceClaim,
    ParsedRateCard,
    TravelMode,
)
from villasanj.ingestion.infrastructure.sources.jabama.adapter import (
    LISTING_CODE,
    SLUG,
    JabamaAdapter,
)
from villasanj.shared.domain.geo import GeoPoint
from villasanj.shared.domain.money import Money

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "jabama"
URL = "https://www.jabama.com/stay/villa-800749"
ZWJ = "\N{ZERO WIDTH JOINER}"


def stay_page(
    code: str | None = "800749", name: str = "stay_page.html", url: str = URL
) -> FetchedPage:
    context = ((LISTING_CODE, code),) if code else ()
    request = PageRequest(SLUG, PageKind.LISTING, url, context=context)
    return FetchedPage(
        request=request,
        status=200,
        final_url=url,
        headers=(("content-type", "text/html; charset=utf-8"),),
        body=(FIXTURES / name).read_bytes(),
        fetched_at=NOW,
        fetcher="fixture",
    )


def test_core_fields() -> None:
    listing = JabamaAdapter().parse_listing(stay_page())
    assert listing is not None
    assert (listing.platform, listing.external_id, listing.url) == (SLUG, "800749", URL)
    assert listing.title == "ویلا دوخوابه هونام"
    assert listing.description is not None
    assert listing.description.startswith("توضیحات مصنوعی")
    assert (listing.property_type, listing.city_fa, listing.city_slug) == (
        "villa",
        "رامسر",
        "ramsar",
    )
    assert listing.locality_fa is None  # empty neighbourhood on this listing
    assert listing.location == GeoPoint(36.887585, 50.691742)
    assert listing.location_radius_m == 400
    assert (listing.bedrooms, listing.bathrooms, listing.area_m2) == (2, 1, 100)
    assert (listing.base_capacity, listing.extra_capacity) == (4, 4)
    assert (listing.rating_avg, listing.rating_count) == (4.9, 30)
    assert (listing.check_in_time, listing.check_out_time, listing.min_nights) == (
        "14:00",
        "12:00",
        1,
    )
    assert listing.instant_booking is True
    assert listing.vat_applies is True
    assert listing.host_ref is None  # scrubbed in the fixture
    assert listing.cancellation_policy_text is not None
    assert listing.cancellation_policy_text.startswith("از لحظه رزرو تا 4 روز")


def test_money_is_read_as_rial() -> None:
    listing = JabamaAdapter().parse_listing(stay_page())
    assert listing is not None
    assert listing.rate_card == ParsedRateCard(
        base=Money.from_toman(2_920_000),
        weekend=Money.from_toman(3_220_000),
        holiday=Money.from_toman(3_550_000),
        extra_guest_base=Money.from_toman(340_000),
        extra_guest_weekend=Money.from_toman(340_000),
        extra_guest_holiday=Money.from_toman(340_000),
    )


def test_photos_amenities_and_distance_claims() -> None:
    listing = JabamaAdapter().parse_listing(stay_page())
    assert listing is not None
    assert len(listing.photos) == 8
    assert listing.photos[0].startswith("https://cdn.jabama.com/image/jabama-images/")
    assert listing.amenities[:2] == (
        ParsedAmenity("room-mountain-forest-view", "منظره به کوه/جنگل", present=True),
        ParsedAmenity("parking", "پارکینگ", present=True),
    )
    assert listing.distance_claims[0] == ParsedDistanceClaim(
        "فاصله از دریا", f"زیر {ZWJ}۵ دقیقه", TravelMode.CAR
    )
    assert listing.distance_claims[3] == ParsedDistanceClaim(
        "فاصله از دریا", "15 دقیقه", TravelMode.WALK
    )


def test_calendar_days() -> None:
    listing = JabamaAdapter().parse_listing(stay_page())
    assert listing is not None
    assert len(listing.calendar) == 10
    assert listing.calendar[0] == ParsedCalendarDay(
        date(2026, 10, 1), Availability.UNAVAILABLE, None, None, 1, is_holiday=False
    )
    thursday = next(day for day in listing.calendar if day.night == date(2026, 10, 8))
    assert thursday == ParsedCalendarDay(
        date(2026, 10, 8),
        Availability.AVAILABLE,
        Money.from_toman(2_460_000),
        Money.from_toman(340_000),
        1,
        is_holiday=False,
    )


def test_code_falls_back_to_the_url() -> None:
    listing = JabamaAdapter().parse_listing(stay_page(code=None))
    assert listing is not None
    assert listing.external_id == "800749"


def test_wrong_code_means_structure_changed() -> None:
    with pytest.raises(PageStructureChanged):
        JabamaAdapter().parse_listing(stay_page(code="1"))


def test_non_listing_pages_parse_to_nothing() -> None:
    page = stay_page()
    search = FetchedPage(
        PageRequest(SLUG, PageKind.SEARCH, URL), 200, URL, page.headers, page.body, NOW, "fixture"
    )
    assert JabamaAdapter().parse_listing(search) is None
