"""The sea truth check over stored listings and measured coast distances."""

from collections.abc import Sequence

from tests.fakes.er import ListingsFake
from tests.fakes.llm import NOW
from tests.unit.catalog.test_reports import listing
from tests.unit.enrichment.test_coast import Store
from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.coast import CoastDistance
from villasanj.enrichment.application.features import AmenityMap
from villasanj.enrichment.application.places import PlaceDistance
from villasanj.enrichment.application.truth import (
    CheckDistanceClaims,
    CheckListingClaims,
    CheckSeaClaims,
    SeaTruthReport,
)
from villasanj.enrichment.domain.distance_claims import Verdict
from villasanj.enrichment.domain.features import Agreement, Feature, FeatureEvidence, Polarity
from villasanj.enrichment.domain.geo import Blur
from villasanj.enrichment.domain.places import PlaceKind
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


class Places:
    def __init__(self, rows: list[PlaceDistance]) -> None:
        self.rows = rows

    async def replace(self, platform: str, rows: Sequence[PlaceDistance]) -> None:
        self.rows = list(rows)

    async def get(self, listing_id: ListingId) -> dict[PlaceKind, PlaceDistance]:
        return {r.kind: r for r in self.rows if r.listing_id == listing_id}

    async def of_platform(self, platform: str) -> dict[ListingId, dict[PlaceKind, PlaceDistance]]:
        found: dict[ListingId, dict[PlaceKind, PlaceDistance]] = {}
        for r in self.rows:
            found.setdefault(r.listing_id, {})[r.kind] = r
        return found


def place(listing_id: ListingId, kind: PlaceKind, low: float, high: float) -> PlaceDistance:
    return PlaceDistance(
        listing_id, kind, "osm", (low + high) / 2, low, high, Blur(400, False), "رامسر", NOW
    )


CENTRE_AND_BAKERY = (
    ParsedDistanceClaim("فاصله از مرکز شهر", "زیر 5 دقیقه", TravelMode.WALK),
    ParsedDistanceClaim("فاصله از نانوایی", "زیر 5 دقیقه", TravelMode.WALK),
    ParsedDistanceClaim("فاصله از مراکز تفریحی", "زیر 5 دقیقه", TravelMode.WALK),
)


async def test_places_judge_their_claims_and_a_partial_map_never_contradicts() -> None:
    home = listing("home", distance_claims=CENTRE_AND_BAKERY)
    far = [
        place(home.id, PlaceKind.CITY_CENTER, 4000.0, 4800.0),  # 2.5 km even from the centre's edge
        place(home.id, PlaceKind.BAKERY, 4000.0, 4800.0),
    ]
    truth = await CheckListingClaims(AmenityMap({}), Store(), Places(far)).run(home)
    centre, bakery, recreation = truth.distances
    assert centre.assessment is not None
    assert centre.assessment.verdict is Verdict.CONTRADICTED
    assert bakery.assessment is not None
    assert bakery.assessment.verdict is Verdict.NOT_CONFIRMED  # an unmapped bakery may be near
    assert bakery.place is not None
    assert bakery.place.kind is PlaceKind.BAKERY
    assert recreation.assessment is None  # no kind of place for it: not checked


async def test_the_platform_report_counts_verdicts_per_target_and_h4() -> None:
    near_home = listing("near", distance_claims=CENTRE_AND_BAKERY)
    far_home = listing("far", distance_claims=CENTRE_AND_BAKERY)
    rows = [
        place(near_home.id, PlaceKind.CITY_CENTER, 0.0, 800.0),
        place(near_home.id, PlaceKind.BAKERY, 0.0, 400.0),
        place(far_home.id, PlaceKind.CITY_CENTER, 4000.0, 4800.0),
    ]
    report = await CheckDistanceClaims(
        ListingsFake([near_home, far_home]), Store(), Places(rows)
    ).run("p")
    assert report.verdicts["city_center:supported"] == 1
    assert report.verdicts["city_center:contradicted"] == 1
    assert report.verdicts["bakery:supported"] == 1
    assert report.verdicts["bakery:not_checked"] == 1  # no mapped bakery within 30 km
    assert report.verdicts["recreation:not_checked"] == 2
    assert (report.listings_judged, report.listings_contradicted) == (2, 1)
