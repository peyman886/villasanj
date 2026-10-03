"""Villa API: members with conflicts, each listing's own offer, merged nights, labelled reviews."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import date, timedelta
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient

from tests.fakes.ingestion import SteppingClock
from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from tests.unit.pricing.test_quote import night
from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.catalog.domain.review import ListingReview
from villasanj.entity_resolution.domain.clustering import CanonicalVilla
from villasanj.entrypoints.api.app import create_app
from villasanj.entrypoints.container import Container
from villasanj.ingestion.domain.parsed import Availability, DatePrecision, ParsedReview
from villasanj.pricing.application.offers import OfferBook
from villasanj.shared.domain.stay import DateRange

SNAPSHOT = "00000000-0000-0000-0000-000000000a12"
J = Listing.from_parsed(parsed(platform="jabama", external_id="1", bedrooms=2), SNAPSHOT, NOW)
S = Listing.from_parsed(parsed(platform="shab", external_id="1", bedrooms=3), SNAPSHOT, NOW)
DAY = date(2026, 10, 15)
VILLA = CanonicalVilla("v-test", frozenset({J.id, S.id}))


class Listings:
    async def get(self, listing_id: ListingId) -> Listing | None:
        return {J.id: J, S.id: S}.get(listing_id)

    async def listings(self, platform: str) -> list[Listing]:
        return [x for x in (J, S) if x.id.platform == platform]

    async def calendar(self, listing_id: ListingId, stay: DateRange) -> list[CalendarObservation]:
        free = replace(night(DAY), listing_id=listing_id)
        taken = replace(night(DAY, availability=Availability.UNAVAILABLE), listing_id=listing_id)
        return [free if listing_id == J.id else taken]

    async def calendars(
        self, platform: str, stay: DateRange
    ) -> dict[ListingId, list[CalendarObservation]]:
        return {}

    async def reviews(self, listing_id: ListingId) -> list[ListingReview]:
        owner = J if listing_id == J.id else S
        review = ParsedReview(f"r-{listing_id.platform}", 5.0, "خوب", DAY, DatePrecision.DAY, False)
        return [ListingReview.from_parsed(owner, review, SNAPSHOT, NOW)]


class Villas:
    async def multi_platform(self) -> list[str]:
        return [VILLA.id]

    async def get(self, villa_id: str) -> CanonicalVilla | None:
        return VILLA if villa_id == VILLA.id else None

    async def villa_of(self, listing: ListingId) -> CanonicalVilla | None:
        return VILLA if listing in VILLA.members else None


class Stub:
    def __init__(self) -> None:
        self.listings = Listings()
        profile = SimpleNamespace(display_name="p")
        self.crawl = SimpleNamespace(adapters={"jabama": SimpleNamespace(profile=profile)})

    def villa_store(self) -> Villas:
        return Villas()

    def offers(self) -> OfferBook:
        return OfferBook(self.listings, {}, SteppingClock(NOW + timedelta(hours=1)))

    async def aclose(self) -> None:
        return None


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(lambda: cast(Container, Stub()))) as test_client:
        yield test_client


def test_a_villa_shows_its_members_and_where_they_disagree(client: TestClient) -> None:
    body = client.get("/villas/v-test").json()
    assert [m["platform"] for m in body["members"]] == ["jabama", "shab"]
    assert {"field": "bedrooms", "values": {"jabama": 2, "shab": 3}} in body["conflicts"]
    assert client.get("/villas/v-none").status_code == 404
    assert client.get("/villas/of/jabama/1").json() == {"villa_id": "v-test", "members": 2}


def test_offers_stay_per_listing_and_nights_keep_each_platform(client: TestClient) -> None:
    offers = client.get(
        "/villas/v-test/offers",
        params={"check_in": str(DAY), "check_out": str(DAY + timedelta(days=1)), "guests": 4},
    ).json()
    assert sorted(o["listing_id"] for o in offers) == ["jabama:1", "shab:1"]  # never merged
    nights = client.get(
        "/villas/v-test/calendar", params={"start": str(DAY), "end": str(DAY + timedelta(days=1))}
    ).json()
    (only,) = nights
    assert set(only["by_platform"]) == {"jabama", "shab"}
    assert only["hidden"]


def test_reviews_of_every_listing_carry_their_platform(client: TestClient) -> None:
    reviews = client.get("/villas/v-test/reviews").json()
    assert sorted(r["platform"] for r in reviews) == ["jabama", "shab"]


def test_a_sample_of_villas_on_more_than_one_platform(client: TestClient) -> None:
    assert client.get("/villas/sample", params={"n": 5}).json() == [{"villa_id": "v-test"}]
