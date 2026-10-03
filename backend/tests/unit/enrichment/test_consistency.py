"""Claims the listings of one villa state differently (INCONSISTENT_ACROSS_PLATFORMS), and H4."""

from tests.fakes.er import ListingsFake
from tests.fakes.llm import NOW
from tests.unit.catalog.test_reports import listing
from tests.unit.enrichment.test_coast import Store
from tests.unit.enrichment.test_truth import Places
from tests.unit.enrichment.test_truth import sea as sea_claim
from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.coast import CoastDistance
from villasanj.enrichment.application.consistency import (
    CheckVillaConsistency,
    MeasureH4,
    render_h4_markdown,
)
from villasanj.enrichment.application.features import AmenityMap
from villasanj.enrichment.domain.consistency import (
    FeatureStatement,
    MemberClaims,
    compare,
    feature_statements,
)
from villasanj.enrichment.domain.distance_claims import ClaimTarget, DistanceClaim, Unit
from villasanj.enrichment.domain.features import (
    DescriptionClaim,
    Feature,
    Polarity,
    extract_claims,
)
from villasanj.enrichment.domain.geo import Blur
from villasanj.ingestion.domain.parsed import ParsedAmenity, TravelMode

POOL_YES = FeatureStatement(True, True, None)
POOL_NO = FeatureStatement(False, False, "بدون استخر")


def sea(low: float, high: float | None, unit: Unit = Unit.MINUTES) -> DistanceClaim:
    return DistanceClaim(ClaimTarget.SEA, "دریا", TravelMode.UNKNOWN, unit, low, high)


def test_a_listing_states_a_feature_only_when_it_is_not_contested() -> None:
    no_pool = extract_claims("ویلا بدون استخر است")
    assert feature_statements({}, no_pool)[Feature.POOL] == FeatureStatement(False, False, "استخر")
    assert feature_statements({Feature.POOL: True}, [])[Feature.POOL] == POOL_YES
    assert Feature.POOL not in feature_statements({Feature.POOL: True}, no_pool)  # contested
    shared = [DescriptionClaim(Feature.POOL, Polarity.HAS, 0, 5, "استخر", shared=True)]
    assert Feature.POOL not in feature_statements({}, shared)  # the complex's pool


def test_a_feature_one_platform_has_and_another_has_not_is_inconsistent() -> None:
    found = compare(
        [
            MemberClaims("jabama", {Feature.POOL: POOL_YES}, ()),
            MemberClaims("shab", {Feature.POOL: POOL_NO}, ()),
        ]
    )
    assert [(f.feature, f.by_platform["shab"].span) for f in found.features] == [
        (Feature.POOL, "بدون استخر")
    ]
    assert found.inconsistent_platforms() == {"jabama", "shab"}
    same = compare(
        [
            MemberClaims("jabama", {Feature.POOL: POOL_YES}, ()),
            MemberClaims("shab", {Feature.POOL: POOL_YES, Feature.JACUZZI: POOL_NO}, ()),
        ]
    )
    assert same.features == ()
    assert same.compared == frozenset({"jabama", "shab"})
    alone = compare([MemberClaims("jabama", {}, ()), MemberClaims("shab", {}, ())])
    assert alone.compared == frozenset()  # nothing stated twice: nothing compared


def test_distances_disagree_only_when_no_reading_reconciles_them() -> None:
    far = sea(30, None)  # "more than 30 minutes": at least 1.2 km on foot
    near = sea(0.0, 100.0, Unit.METRES)
    found = compare([MemberClaims("jabama", {}, (far,)), MemberClaims("shab", {}, (near,))])
    assert [d.target for d in found.distances] == [ClaimTarget.SEA]
    assert found.distances[0].metres["shab"] == (0.0, 100.0)
    five, ten = sea(0, 10), sea(0, 15)  # "5 minutes" and "10 minutes" with rounding margins
    close = compare([MemberClaims("jabama", {}, (five,)), MemberClaims("shab", {}, (ten,))])
    assert close.distances == ()
    assert close.compared == frozenset({"jabama", "shab"})
    either = compare(
        [MemberClaims("jabama", {}, (far, sea(0, 10))), MemberClaims("shab", {}, (near,))]
    )
    assert either.distances == ()  # the platform's own claims together allow the other's
    other = DistanceClaim(ClaimTarget.OTHER, "پارک", TravelMode.WALK, Unit.METRES, 5000, None)
    unnamed = compare(
        [
            MemberClaims("jabama", {}, (other,)),
            MemberClaims(
                "shab",
                {},
                (DistanceClaim(ClaimTarget.OTHER, "x", TravelMode.WALK, Unit.METRES, 0, 10),),
            ),
        ]
    )
    assert unnamed.distances == ()  # unnamed targets may be different places


class Villas:
    def __init__(self, villas: dict[str, frozenset[ListingId]]) -> None:
        self.villas = villas

    async def current(self) -> dict[str, frozenset[ListingId]]:
        return dict(self.villas)


async def test_h4_counts_contradicted_or_inconsistent_listings_per_platform() -> None:
    pool = (ParsedAmenity("swim", "استخر", True),)
    j1 = listing("j1", platform="jabama", amenities=pool, distance_claims=sea_claim("زیر 5 دقیقه"))
    s1 = listing("s1", platform="shab", description="ویلا بدون استخر است")
    j2 = listing("j2", platform="jabama", amenities=pool)
    s2 = listing("s2", platform="shab", amenities=pool)
    j3 = listing("j3", platform="jabama")
    coast = Store()
    coast.rows = [CoastDistance(j1.id, "osm", 5000.0, 4600.0, 5400.0, Blur(400, False), NOW)]
    villas = Villas({"v1": frozenset({j1.id, s1.id}), "v2": frozenset({j2.id, s2.id})})
    codes = {"jabama": {"swim": Feature.POOL}, "shab": {"swim": Feature.POOL}}
    check = CheckVillaConsistency(AmenityMap(codes))
    rows = await MeasureH4(
        ListingsFake([j1, s1, j2, s2, j3]), villas, check, coast, Places([])
    ).run(["jabama", "shab"])
    jabama, shab = rows
    assert (jabama.listings, jabama.in_multi_platform_villas, jabama.judged) == (3, 2, 2)
    assert (jabama.contradicted, jabama.compared, jabama.inconsistent, jabama.either) == (
        1,
        2,
        1,
        1,
    )
    assert jabama.kinds == {"feature:pool": 1}
    assert (shab.judged, shab.inconsistent, shab.either) == (2, 1, 1)
    assert shab.share.estimate == 0.5
    assert jabama.inconsistent_share.estimate == 0.5
    text = render_h4_markdown(rows, NOW)
    assert "| jabama | 3 | 2 | 1 | 1 | 1 | 50.0%" in text
    assert "feature:pool 1" in text
