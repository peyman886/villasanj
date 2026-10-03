"""Listing API: provenance is part of every DTO that carries a number or a claim (ADR-0007)."""

import asyncio
from collections.abc import Iterator
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from tests.fakes.ingestion import SteppingClock
from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from tests.unit.discovery.test_routing import Store as DriveStore
from tests.unit.enrichment.test_coast import Store as CoastStore
from tests.unit.pricing.test_quote import SNAPSHOT as CALENDAR_SNAPSHOT
from tests.unit.pricing.test_quote import night
from tests.unit.test_search_api import Jobs
from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.catalog.domain.review import ListingReview
from villasanj.discovery.application.routing import Origin
from villasanj.enrichment.application.coast import CoastDistance
from villasanj.enrichment.application.features import AmenityMap
from villasanj.enrichment.application.review_summary import CitedPoint, ReviewSummary
from villasanj.enrichment.application.truth import CheckListingClaims
from villasanj.enrichment.domain.features import Feature
from villasanj.enrichment.domain.geo import Blur
from villasanj.entrypoints.api import listings as api
from villasanj.entrypoints.api.app import create_app
from villasanj.entrypoints.container import Container
from villasanj.ingestion.domain.parsed import (
    DatePrecision,
    ParsedAmenity,
    ParsedDistanceClaim,
    ParsedReview,
    TravelMode,
)
from villasanj.pricing.application.offers import OfferBook
from villasanj.shared.application.llm.types import JobContext
from villasanj.shared.domain.geo import GeoPoint
from villasanj.shared.domain.stay import DateRange

CONFIG = Path(__file__).resolve().parents[3] / "config"
SNAPSHOT = "00000000-0000-0000-0000-000000000a11"
LISTING = Listing.from_parsed(parsed(), SNAPSHOT, NOW)
THU, FRI = date(2026, 10, 15), date(2026, 10, 16)


ZWNJ = "\N{ZERO WIDTH NON-JOINER}"


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
        profile = SimpleNamespace(display_name="example")
        self.crawl = SimpleNamespace(adapters={"example": SimpleNamespace(profile=profile)})

    def offers(self) -> OfferBook:
        return OfferBook(self.listings, {}, SteppingClock(NOW + timedelta(hours=2)))

    def routing_origin(self) -> Origin:
        return Origin("tehran", "میدان آزادی تهران", GeoPoint(35.7, 51.34), "test")

    def coast_store(self) -> CoastStore:
        store = CoastStore()
        store.rows = [
            CoastDistance(LISTING.id, "osm-1", 900.0, 500.0, 1300.0, Blur(400, False), NOW)
        ]
        return store

    def drive_store(self) -> DriveStore:
        return DriveStore()  # not routed

    def listing_claims(self) -> CheckListingClaims:
        return CheckListingClaims(AmenityMap({}), self.coast_store())

    jobs = Jobs()
    summary: ReviewSummary | None = None

    def review_summaries(self) -> "Summaries":
        return Summaries(self.summary)

    async def aclose(self) -> None:
        return None


class Summaries:
    def __init__(self, summary: ReviewSummary | None) -> None:
        self.summary = summary

    async def for_listing(self, listing_id: ListingId, ctx: JobContext) -> ReviewSummary | None:
        return self.summary


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(lambda: cast(Container, Stub()))) as test_client:
        yield test_client


def test_a_sample_is_deterministic_and_bounded(client: TestClient) -> None:
    first = client.get("/listings/sample", params={"n": 5}).json()
    assert first == client.get("/listings/sample", params={"n": 5}).json()
    assert first == [{"platform": "example", "external_id": "42", "title": LISTING.title_norm}]
    assert client.get("/listings/sample", params={"n": 0}).status_code == 422


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
    assert body["per_person"]["low_toman"] == 500_000  # 4 guests share it
    assert body["per_person"]["high_toman"] is None  # an open total stays open per person
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


def test_geo_comes_with_ranges_text_and_provenance(client: TestClient) -> None:
    response = client.get(f"/listings/{LISTING.id.platform}/{LISTING.id.external_id}/geo")
    assert response.status_code == 200
    body = response.json()
    coast = body["coast_m"]
    assert (coast["low"], coast["high"]) == (500.0, 1300.0)
    assert coast["text"] == "۰٫۵ تا ۱٫۳ کیلومتر تا ساحل در خط مستقیم"
    assert coast["provenance"]["method"] == "derived"
    assert "OpenStreetMap (osm-1)" in coast["provenance"]["note"]
    assert body["drive_s"] is None  # not routed: no time, never a guess
    assert body["origin"] == "میدان آزادی تهران"


def test_claims_come_with_a_verdict_evidence_and_both_provenances(client: TestClient) -> None:
    body = client.get(f"/listings/{LISTING.id.platform}/{LISTING.id.external_id}/claims").json()
    (sea,) = body["distances"]
    assert sea["text"] == "فاصله از دریا: زیر ۵ دقیقه با ماشین"
    assert sea["verdict"] == "supported"  # 0.5-1.3 km: within any reading of five minutes by car
    assert sea["evidence"].startswith("نقشه: ۰٫۵ تا ۱٫۳ کیلومتر تا ساحل")
    assert sea["provenance"]["method"] == "observed"
    assert sea["evidence_provenance"]["method"] == "derived"
    (pool,) = body["features"]
    assert (pool["feature"], pool["span"], pool["polarity"]) == ("pool", "استخر", "has")
    assert pool["verdict"] == "not_confirmed"  # the amenity list is silent: «تأیید نشد»
    assert pool["evidence_provenance"] is None
    assert client.get("/listings/example/0/claims").status_code == 404


def test_claim_texts_never_accuse() -> None:
    walk = (ParsedDistanceClaim("فاصله از دریا", "زیر 5 دقیقه", TravelMode.WALK),)
    listing = Listing.from_parsed(
        parsed(description="استخر ندارد، لب دریا", distance_claims=walk), SNAPSHOT, NOW
    )  # the amenity list says it has a pool, the map says 3 km
    far = CoastDistance(listing.id, "osm-1", 3000.0, 2600.0, 3400.0, Blur(400, False), NOW)
    store = CoastStore()
    store.rows = [far]
    truth = asyncio.run(
        CheckListingClaims(AmenityMap({"example": {"pool": Feature.POOL}}), store).run(
            replace(listing, amenities=(ParsedAmenity("pool", "استخر", True),))
        )
    )
    out = api.claims_out(listing, truth)
    verdicts = {c.verdict for c in out.distances} | {c.verdict for c in out.features}
    assert verdicts == {"contradicted", "inconsistent", "not_confirmed"}
    near = next(c for c in out.features if c.feature == "near_sea")
    assert near.verdict == "not_confirmed"  # a vague word is never contradicted by the map
    texts = " ".join([*(c.evidence for c in out.distances), *(c.evidence for c in out.features)])
    for word in ("دروغ", "تقلب", "نادرست", "غلط"):
        assert word not in texts


def test_place_claims_say_what_the_map_can_and_cannot_tell() -> None:
    from tests.unit.enrichment.test_truth import Places, place
    from villasanj.enrichment.domain.places import PlaceKind

    claims = (
        ParsedDistanceClaim("فاصله از نانوایی", "زیر 5 دقیقه", TravelMode.WALK),
        ParsedDistanceClaim("فاصله از مرکز شهر", "زیر 5 دقیقه", TravelMode.WALK),
    )
    listing = Listing.from_parsed(parsed(distance_claims=claims), SNAPSHOT, NOW)
    rows = [
        place(listing.id, PlaceKind.BAKERY, 4000.0, 4800.0),
        place(listing.id, PlaceKind.CITY_CENTER, 4000.0, 4800.0),
    ]
    truth = asyncio.run(CheckListingClaims(AmenityMap({}), CoastStore(), Places(rows)).run(listing))
    bakery, centre = api.claims_out(listing, truth).distances
    assert bakery.verdict == "not_confirmed"
    assert "OpenStreetMap" in bakery.evidence
    assert f"رد نمی{ZWNJ}کند" in bakery.evidence  # a partial map never contradicts
    assert centre.verdict == "contradicted"
    assert "رامسر" in centre.evidence  # the nearest centre is named
    assert centre.evidence_provenance is not None
    assert centre.evidence_provenance.method == "derived"


def test_a_claim_the_photos_show_is_supported_with_its_source() -> None:
    from tests.unit.enrichment.test_truth import Photos

    listing = Listing.from_parsed(parsed(description="ویلا با استخر"), SNAPSHOT, NOW)
    photos = Photos({listing.id: frozenset({Feature.POOL})})
    truth = asyncio.run(CheckListingClaims(AmenityMap({}), CoastStore(), None, photos).run(listing))
    (pool,) = api.claims_out(listing, truth).features
    assert pool.verdict == "supported"
    assert "عکس" in pool.evidence
    assert pool.evidence_provenance is not None
    assert pool.evidence_provenance.note is not None
    assert "SigLIP" in pool.evidence_provenance.note


def test_review_summary_cites_reviews_and_is_null_with_too_few(client: TestClient) -> None:
    path = f"/listings/{LISTING.id.platform}/{LISTING.id.external_id}/review-summary"
    assert client.get(path).json() is None  # too few reviews with text: no summary
    review = ListingReview.from_parsed(
        LISTING, ParsedReview("R1", 5.0, "تمیز", None, None, False), SNAPSHOT, NOW
    )
    Stub.summary = ReviewSummary(
        pros=(CitedPoint(f"مهمان{ZWNJ}ها از تمیزی راضی بودند", (review,)),),
        cons=(),
        reviews_given=3,
        retried=False,
        dropped=0,
        models=("m",),
        cost_usd=Decimal("0.001"),
    )
    try:
        body = client.get(path).json()
    finally:
        Stub.summary = None
    assert body["pros"] == [
        {"text": f"مهمان{ZWNJ}ها از تمیزی راضی بودند", "review_ids": ["R1"], "single_opinion": True}
    ]
    assert (body["cons"], body["reviews_given"]) == ([], 3)
