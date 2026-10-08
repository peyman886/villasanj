"""Villa API: members with conflicts, each listing's own offer, merged nights, labelled reviews."""

from collections.abc import Iterator, Sequence
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient

from tests.fakes.er import CandidateStoreFake, LabelStoreFake
from tests.fakes.ingestion import SteppingClock
from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from tests.unit.pricing.test_quote import night
from tests.unit.test_search_api import Jobs
from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.catalog.domain.photo import ListingPhoto, PerceptualFingerprint
from villasanj.catalog.domain.review import ListingReview
from villasanj.enrichment.application.consistency import CheckVillaConsistency
from villasanj.enrichment.application.features import AmenityMap
from villasanj.enrichment.application.review_summary import CitedPoint, ReviewSummary
from villasanj.enrichment.domain.features import Feature
from villasanj.entity_resolution.application.explain import ExplainMatch
from villasanj.entity_resolution.application.ports import ScoredCandidate
from villasanj.entity_resolution.application.villas import DecisionPolicy, StoredJudgement
from villasanj.entity_resolution.domain.clustering import CanonicalVilla
from villasanj.entity_resolution.domain.evidence import PhotoSimilarity
from villasanj.entity_resolution.domain.labels import Label, PairLabel
from villasanj.entity_resolution.domain.pairs import BlockingSource, PairKey
from villasanj.entity_resolution.domain.scoring import Contribution, Score
from villasanj.entrypoints.api.app import create_app
from villasanj.entrypoints.container import Container
from villasanj.ingestion.domain.parsed import (
    Availability,
    DatePrecision,
    ParsedAmenity,
    ParsedReview,
)
from villasanj.pricing.application.offers import OfferBook
from villasanj.shared.application.llm.types import JobContext
from villasanj.shared.domain.stay import DateRange

SNAPSHOT = "00000000-0000-0000-0000-000000000a12"
POOL = (ParsedAmenity("swim", "استخر", True),)
J = Listing.from_parsed(
    parsed(
        platform="jabama",
        external_id="1",
        bedrooms=2,
        amenities=POOL,
        photos=("https://j.test/0.jpg", "https://j.test/1.jpg"),
    ),
    SNAPSHOT,
    NOW,
)
S = Listing.from_parsed(
    parsed(platform="shab", external_id="1", bedrooms=3, description="ویلا بدون استخر است"),
    SNAPSHOT,
    NOW,
)
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

    jobs = Jobs()

    def review_summaries(self) -> "Summaries":
        return Summaries()

    def villa_consistency(self) -> CheckVillaConsistency:
        return CheckVillaConsistency(AmenityMap({"jabama": {"swim": Feature.POOL}}))

    def offers(self) -> OfferBook:
        return OfferBook(self.listings, {}, SteppingClock(NOW + timedelta(hours=1)))

    def catalog_photos(self) -> "Photos":
        return Photos()

    def explain_match(self) -> ExplainMatch:
        key = PairKey.of(J.id, S.id)
        candidate = ScoredCandidate(
            key,
            frozenset({BlockingSource.GEO_ROOMS}),
            True,
            None,
            Score(1.5, (Contribution("location_overlaps", 1.0),)),
        )
        labels = LabelStoreFake()
        labels.decisions[(key, "owner")] = PairLabel(key, Label.MATCH, "owner", NOW)
        return ExplainMatch(
            CandidateStoreFake([candidate]),
            NoJudge(),
            labels,
            NoPhotos(),
            DecisionPolicy(threshold=-0.25),
        )

    async def aclose(self) -> None:
        return None


class Photos:
    async def photos_of(self, listings: Sequence[ListingId]) -> list[ListingPhoto]:
        fingerprint = PerceptualFingerprint(-1, 0, 800, 600)  # stored signed: all 64 bits set
        return [ListingPhoto(J.id, 0, "https://j.test/0.jpg", SNAPSHOT, "a" * 64, fingerprint, NOW)]


class NoJudge:
    async def of_pair(self, key: PairKey) -> StoredJudgement | None:
        return None


class NoPhotos:
    async def similarities(self, key: PairKey) -> list[PhotoSimilarity]:
        return []

    async def urls(self, listing: ListingId) -> dict[int, str]:
        return {}


class Summaries:
    seen: list[ListingReview] = []  # noqa: RUF012 - one test reads what the use case was given

    async def summarize(
        self, reviews: Sequence[ListingReview], ctx: JobContext
    ) -> ReviewSummary | None:
        Summaries.seen = list(reviews)
        return ReviewSummary(
            pros=(CitedPoint("میزبان خوش\N{ZERO WIDTH NON-JOINER}برخورد بود", tuple(reviews)),),
            cons=(),
            reviews_given=len(reviews),
            retried=False,
            dropped=0,
            models=("m",),
            cost_usd=Decimal("0.001"),
        )


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(lambda: cast(Container, Stub()))) as test_client:
        yield test_client


def test_a_villa_shows_its_members_and_where_they_disagree(client: TestClient) -> None:
    body = client.get("/villas/v-test").json()
    assert [m["platform"] for m in body["members"]] == ["jabama", "shab"]
    assert {"field": "bedrooms", "values": {"jabama": 2, "shab": 3}} in body["conflicts"]
    (pool,) = body["inconsistencies"]
    assert (pool["kind"], pool["subject"]) == ("feature", "pool")
    said = {x["platform"]: (x["says"], x["source"], x["span"]) for x in pool["statements"]}
    assert said == {
        "jabama": ("has", "amenities", "استخر"),  # listed, and its description says so too
        "shab": ("has_not", "description", "استخر"),
    }
    assert all(x["provenance"]["snapshot_id"] == SNAPSHOT for x in pool["statements"])
    assert client.get("/villas/v-none").status_code == 404
    assert client.get("/villas/of/jabama/1").json() == {"villa_id": "v-test", "members": 2}
    assert body["gallery"] == [
        {"url": "https://j.test/0.jpg", "platform": "jabama", "phash": "ffffffffffffffff"},
        {"url": "https://j.test/1.jpg", "platform": "jabama", "phash": None},  # not fingerprinted
    ]


def test_the_match_shows_what_was_recorded_for_the_pair(client: TestClient) -> None:
    (pair,) = client.get("/villas/v-test/match").json()
    assert (pair["left"], pair["right"]) == ("jabama:1", "shab:1")
    assert pair["photo_pairs"] == []
    assert pair["bedrooms"] == [2, 3]
    assert pair["rule_score"] == 1.5
    assert pair["rules_match"] is True
    assert pair["contributions"] == {"location_overlaps": 1.0}
    assert pair["distance_min_m"] is None  # no stored evidence: nothing is made up
    assert pair["judge"] is None
    assert pair["human"] == "match"


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


def test_the_review_summary_covers_every_platform_and_cites_across_them(client: TestClient) -> None:
    body = client.get("/villas/v-test/review-summary").json()
    # both platforms' reviews, most recent stays first (same day: by review id, descending)
    assert [r.listing_id.platform for r in Summaries.seen] == ["shab", "jabama"]
    (point,) = body["pros"]
    assert sorted(point["review_ids"]) == ["jabama:r-jabama", "shab:r-shab"]
    assert not point["single_opinion"]
    assert client.get("/villas/v-none/review-summary").status_code == 404
