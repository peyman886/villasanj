from datetime import timedelta

import pytest

from tests.fakes.llm import NOW
from villasanj.catalog.domain.listing import Listing, ListingId, LocationEvidence
from villasanj.ingestion.domain.parsed import (
    ParsedDistanceClaim,
    ParsedListing,
    ParsedRateCard,
    TravelMode,
)
from villasanj.shared.domain.geo import GeoPoint
from villasanj.shared.domain.provenance import ProvenanceMethod
from villasanj.shared.domain.stay import GuestCount

ARABIC_YEH = "\N{ARABIC LETTER YEH}"
ARABIC_KAF = "\N{ARABIC LETTER KAF}"
ZWJ = "\N{ZERO WIDTH JOINER}"
SNAPSHOT = "00000000-0000-0000-0000-0000000000aa"


def parsed(**overrides: object) -> ParsedListing:
    values: dict[str, object] = {
        "platform": "example",
        "external_id": "42",
        "url": "https://www.example.test/stay/42",
        "title": f"و{ARABIC_YEH}لا {ARABIC_KAF}نار در{ARABIC_YEH}ا",
        "description": "  ویلا   با  استخر \n\n\n نزدیک دریا ",
        "property_type": "villa",
        "city_fa": f"رامسر{ZWJ}",
        "city_slug": "ramsar",
        "locality_fa": None,
        "location": GeoPoint(36.9, 50.66),
        "location_radius_m": 400,
        "bedrooms": 2,
        "bathrooms": 1,
        "area_m2": 120,
        "base_capacity": 4,
        "extra_capacity": 2,
        "rating_avg": 4.7,
        "rating_count": 12,
        "check_in_time": "14:00",
        "check_out_time": "12:00",
        "min_nights": 1,
        "instant_booking": True,
        "host_ref": None,
        "cancellation_policy_text": None,
        "vat_applies": None,
        "rate_card": ParsedRateCard(),
        "distance_claims": (
            ParsedDistanceClaim("فاصله از دریا", f"زیر {ZWJ}۵ دقیقه", TravelMode.CAR),
        ),
    }
    values.update(overrides)
    return ParsedListing(**values)  # type: ignore[arg-type]


def test_from_parsed_normalizes_text_and_records_provenance() -> None:
    listing = Listing.from_parsed(parsed(), SNAPSHOT, NOW)
    assert listing.id == ListingId("example", "42")
    assert str(listing.id) == "example:42"
    assert listing.title_norm == "ویلا کنار دریا"
    assert listing.description_norm == "ویلا با استخر\nنزدیک دریا"
    assert listing.city_fa == "رامسر"
    assert listing.distance_claims[0].value_text == "زیر 5 دقیقه"
    assert listing.provenance.method is ProvenanceMethod.OBSERVED
    assert listing.provenance.snapshot_id == SNAPSHOT
    assert listing.provenance.observed_at == NOW


@pytest.mark.parametrize(
    ("guests", "base", "extra", "expected"),
    [(6, 4, 2, True), (7, 4, 2, False), (4, 4, None, True), (3, None, None, None)],
)
def test_capacity(guests: int, base: int | None, extra: int | None, expected: bool | None) -> None:
    listing = Listing.from_parsed(parsed(base_capacity=base, extra_capacity=extra), SNAPSHOT, NOW)
    assert listing.capacity_allows(GuestCount(guests)) is expected


def test_location_uncertainty_becomes_a_distance_range() -> None:
    evidence = LocationEvidence(GeoPoint(36.9, 50.66), radius_m=400)
    near, far = evidence.distance_range_m(GeoPoint(36.9, 50.66))
    assert (near, far) == (0.0, 400.0)
    unknown = LocationEvidence(GeoPoint(36.9, 50.66), radius_m=None)
    assert unknown.distance_range_m(GeoPoint(36.95, 50.66)) == (0.0, None)


def test_staleness() -> None:
    listing = Listing.from_parsed(parsed(), SNAPSHOT, NOW)
    assert not listing.is_stale(NOW + timedelta(hours=23), timedelta(hours=24))
    assert listing.is_stale(NOW + timedelta(hours=25), timedelta(hours=24))


def test_missing_location_stays_missing() -> None:
    listing = Listing.from_parsed(parsed(location=None), SNAPSHOT, NOW)
    assert listing.location is None
