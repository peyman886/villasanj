"""The sea truth check over stored listings and measured coast distances."""

from tests.fakes.er import ListingsFake
from tests.fakes.llm import NOW
from tests.unit.catalog.test_reports import listing
from tests.unit.enrichment.test_coast import Store
from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.coast import CoastDistance
from villasanj.enrichment.application.features import AmenityMap
from villasanj.enrichment.application.truth import (
    CheckListingClaims,
    CheckSeaClaims,
    SeaTruthReport,
)
from villasanj.enrichment.domain.distance_claims import Verdict
from villasanj.enrichment.domain.features import Agreement, Feature, FeatureEvidence, Polarity
from villasanj.enrichment.domain.geo import Blur
from villasanj.ingestion.domain.parsed import ParsedAmenity, ParsedDistanceClaim, TravelMode


def sea(value: str, mode: TravelMode = TravelMode.WALK) -> tuple[ParsedDistanceClaim, ...]:
    return (ParsedDistanceClaim("فاصله از دریا", value, mode),)


async def test_verdicts_are_counted_per_listing_and_mode() -> None:
    listings = ListingsFake(
        [
            listing("near", distance_claims=sea("زیر 5 دقیقه")),
            listing("far", distance_claims=sea("زیر 5 دقیقه")),
            listing("unmeasured", distance_claims=sea("10 دقیقه", TravelMode.CAR)),
            listing("no-claim", distance_claims=()),
        ]
    )
    store = Store()
    store.rows = [
        CoastDistance(ListingId("p", "near"), "osm", 200.0, 0.0, 600.0, Blur(400, False), NOW),
        CoastDistance(ListingId("p", "far"), "osm", 5000.0, 4600.0, 5400.0, Blur(400, True), NOW),
    ]
    report = await CheckSeaClaims(listings, store).run("p")
    assert (report.listings_with_claim, report.without_distance) == (3, 1)
    assert report.listings_contradicted == 1
    assert report.verdicts == {"not_confirmed": 1, "contradicted": 1}  # 600 m may exceed 500 m
    assert report.verdicts_with_assumed_radius == {"contradicted": 1}
    assert report.by_mode == {"walk:not_confirmed": 1, "walk:contradicted": 1}
    (example,) = report.contradicted
    assert example.listing_id == ListingId("p", "far")


def test_h4_share_counts_only_listings_with_a_measured_distance() -> None:
    report = SeaTruthReport(
        "p", listings_with_claim=12, listings_contradicted=2, without_distance=2
    )
    share = report.contradicted_share()
    assert share.estimate == 0.2
    assert 0.0 < share.low < 0.2 < share.high < 1.0
    assert SeaTruthReport("p").contradicted_share().estimate is None


async def test_one_listing_gets_every_claim_with_its_evidence_or_none() -> None:
    claims = (
        *sea("زیر 5 دقیقه"),
        ParsedDistanceClaim("فاصله از جنگل", "زیر 5 دقیقه", TravelMode.WALK),  # no evidence yet
        ParsedDistanceClaim("فاصله از دریا", "نزدیک", TravelMode.WALK),  # not understood
    )
    described = "ویلا با استخر و شومینه، بدون پارکینگ، کنار دریا"
    amenities = (
        ParsedAmenity("swim", "استخر", True),
        ParsedAmenity("fire", "شومینه", False),
    )
    home = listing("home", distance_claims=claims, description=described, amenities=amenities)
    store = Store()
    store.rows = [
        CoastDistance(home.id, "osm", 2000.0, 1600.0, 2400.0, Blur(400, True), NOW),
    ]
    codes = {"p": {"swim": Feature.POOL, "fire": Feature.FIREPLACE}}
    truth = await CheckListingClaims(AmenityMap(codes), store).run(home)

    sea_check, forest, vague = truth.distances
    assert sea_check.assessment is not None
    assert sea_check.assessment.verdict is Verdict.CONTRADICTED  # 1.6 km even at best: > 500 m
    assert sea_check.radius_assumed
    assert forest.claim is not None
    assert forest.assessment is None
    assert vague.claim is None
    assert vague.assessment is None

    by_feature = {c.claim.feature: c for c in truth.features}
    assert by_feature[Feature.POOL].agreement is Agreement.AGREES
    assert by_feature[Feature.FIREPLACE].agreement is Agreement.AMENITIES_DISAGREE
    assert by_feature[Feature.PARKING].claim.polarity is Polarity.HAS_NOT
    assert by_feature[Feature.PARKING].agreement is Agreement.AMENITIES_SILENT
    near = by_feature[Feature.NEAR_SEA]
    assert near.map_evidence is FeatureEvidence.DENIED  # shown as a fact, never a contradiction
    assert near.claim.span == "کنار دریا"


async def test_a_listing_without_a_measured_distance_has_no_sea_verdicts() -> None:
    home = listing("home", distance_claims=sea("زیر 5 دقیقه"), description="لب دریا")
    truth = await CheckListingClaims(AmenityMap({}), Store()).run(home)
    (check,) = truth.distances
    assert check.claim is not None
    assert check.assessment is None
    (feature,) = truth.features
    assert feature.map_evidence is None
    assert truth.coast is None
