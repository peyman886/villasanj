"""Listing API: provenance is part of every DTO that carries a number or a claim (ADR-0007)."""

from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from tests.fakes.ingestion import SteppingClock
from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from tests.unit.pricing.test_quote import SNAPSHOT as CALENDAR_SNAPSHOT
from tests.unit.pricing.test_quote import night
from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.catalog.domain.review import ListingReview
from villasanj.entrypoints.api import listings as api
from villasanj.entrypoints.api.app import create_app
from villasanj.entrypoints.container import Container
from villasanj.ingestion.domain.parsed import DatePrecision, ParsedReview
from villasanj.pricing.application.offers import OfferBook
from villasanj.shared.domain.stay import DateRange

CONFIG = Path(__file__).resolve().parents[3] / "config"
SNAPSHOT = "00000000-0000-0000-0000-000000000a11"
LISTING = Listing.from_parsed(parsed(), SNAPSHOT, NOW)
THU, FRI = date(2026, 10, 15), date(2026, 10, 16)


class Listings:
    def __init__(self) -> None:
        self.calendar_rows = [
            night(THU, 1_000_000, age_hours=3),
            night(THU, 900_000, age_hours=30),
            night(FRI),
        ]

    async def get(self, listing_id: ListingId) -> Listing | None:
        return LISTING if listing_id == LISTING.id else None

    async def listings(self, platform: str) -> list[Listing]:
        return [LISTING]

    async def calendar(self, listing_id: ListingId, stay: DateRange) -> list[CalendarObservation]:
        return [o for o in self.calendar_rows if stay.contains_night(o.night)]

    async def calendars(
        self, platform: str, stay: DateRange
    ) -> dict[ListingId, list[CalendarObservation]]:
        return {LISTING.id: await self.calendar(LISTING.id, stay)}

    async def reviews(self, listing_id: ListingId) -> list[ListingReview]:
        review = ParsedReview("R1", 4.5, "خوب", date(2026, 8, 1), DatePrecision.DAY, True)
        return [ListingReview.from_parsed(LISTING, review, SNAPSHOT, NOW)]


class Stub:
    def __init__(self) -> None:
        self.listings = Listings()
        self.settings = SimpleNamespace(scenarios_path=CONFIG / "scenarios.toml")
        self.crawl = SimpleNamespace(adapters={})

    def offers(self) -> OfferBook:
        return OfferBook(self.listings, {}, SteppingClock(NOW + timedelta(hours=2)))

    async def aclose(self) -> None:
        return None


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(lambda: cast(Container, Stub()))) as test_client:
        yield test_client


def test_listing_carries_its_source_snapshot(client: TestClient) -> None:
    body = client.get("/listings/example/42").json()
    assert body["provenance"]["method"] == "observed"
    assert body["provenance"]["snapshot_id"] == SNAPSHOT
    assert body["provenance"]["source"]["url"] == LISTING.url
    assert body["platform_name"] == "example"
    assert body["location"]["radius_m"] == 400
    assert client.get("/listings/example/0").status_code == 404


def test_offer_is_per_listing_with_its_components_and_age(client: TestClient) -> None:
    body = client.get(
        "/listings/example/42/offer",
        params={"check_in": str(THU), "check_out": str(FRI + timedelta(days=1)), "guests": 4},
    ).json()
    assert (body["status"], body["kind"], body["caveats"]) == ("bookable", "open", ["fees_unknown"])
    assert body["total"]["low_toman"] == 2_000_000
    assert body["total"]["high_toman"] is None  # fees unknown: ">= X"
    assert body["provenance"]["method"] == "derived"
    assert [n["price_provenance"]["method"] for n in body["nights"]] == ["observed", "observed"]
    assert (
        body["age_hours"] == 5.0
    )  # the newest Thursday observation is 3 h old, at a clock 2 h later
    assert body["stale"] is False


@pytest.mark.parametrize(
    "params",
    [
        {"check_in": "2026-10-17", "check_out": "2026-10-15", "guests": 4},
        {"check_in": "2026-10-15", "check_out": "2026-10-17", "guests": 0},
    ],
)
def test_bad_offer_requests_are_422(client: TestClient, params: dict[str, str | int]) -> None:
    assert client.get("/listings/example/42/offer", params=params).status_code == 422


def test_unknown_listing_has_no_offer(client: TestClient) -> None:
    params: dict[str, str | int] = {
        "check_in": "2026-10-15",
        "check_out": "2026-10-17",
        "guests": 4,
    }
    assert client.get("/listings/example/0/offer", params=params).status_code == 404


def test_calendar_shows_the_newest_observation_per_night(client: TestClient) -> None:
    nights = client.get(
        "/listings/example/42/calendar",
        params={"start": str(THU), "end": str(FRI + timedelta(days=1))},
    ).json()
    assert [n["night"] for n in nights] == ["2026-10-15", "2026-10-16"]
    assert nights[0]["price"]["low_toman"] == 1_000_000  # not the older 900,000 observation
    assert (
        nights[0]["provenance"]["snapshot_id"] == CALENDAR_SNAPSHOT
    )  # the calendar's own snapshot
    too_long = {"start": "2026-10-01", "end": "2027-10-01"}
    assert client.get("/listings/example/42/calendar", params=too_long).status_code == 422


def test_reviews_and_scenarios(client: TestClient) -> None:
    (review,) = client.get("/listings/example/42/reviews").json()
    assert (review["rating"], review["stayed_precision"], review["host_replied"]) == (
        4.5,
        "day",
        True,
    )
    assert review["provenance"]["method"] == "observed"
    scenarios = client.get("/scenarios").json()
    assert [s["slug"] for s in scenarios] == ["weekend", "midweek", "holiday"]


SOURCED = [api.ListingOut, api.OfferOut, api.CalendarNightOut, api.ReviewOut, api.NightOut]


@pytest.mark.parametrize("model", SOURCED)
def test_sourced_dtos_cannot_be_built_without_provenance(model: type[BaseModel]) -> None:
    provenance_fields = [name for name in model.model_fields if name.endswith("provenance")]
    assert provenance_fields
    assert all(model.model_fields[name].is_required() for name in provenance_fields)
    with pytest.raises(ValidationError, match="provenance"):
        model()
