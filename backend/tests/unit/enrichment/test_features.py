"""Feature claims in descriptions, and the listing's own amenity list as evidence."""

from pathlib import Path

import pytest

from tests.fakes.er import ListingsFake
from tests.unit.catalog.test_reports import listing
from villasanj.enrichment.application.features import AmenityMap, MeasureFeatureClaims
from villasanj.enrichment.domain.features import (
    Agreement,
    DescriptionClaim,
    Feature,
    FeatureEvidence,
    Polarity,
    against_amenities,
    extract_claims,
    feature_evidence,
    near_sea_evidence,
)
from villasanj.enrichment.infrastructure.features import load_amenity_map
from villasanj.ingestion.domain.parsed import ParsedAmenity
from villasanj.shared.application.errors import ConfigurationError

ZWNJ = "\N{ZERO WIDTH NON-JOINER}"
HAS, HAS_NOT = Polarity.HAS, Polarity.HAS_NOT


def found(text: str) -> list[tuple[Feature, Polarity, bool]]:
    return [(c.feature, c.polarity, c.shared) for c in extract_claims(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "ویلا دارای استخر روباز و جکوزی است",
            [(Feature.POOL, HAS, False), (Feature.JACUZZI, HAS, False)],
        ),
        ("ویلای بدون استخر در محله آرام", [(Feature.POOL, HAS_NOT, False)]),
        ("این ویلا استخر ندارد", [(Feature.POOL, HAS_NOT, False)]),
        ("استفاده از استخر مشاع شهرک", [(Feature.POOL, HAS, True)]),
        ("در نزدیکی استخر عمومی شهر", []),
        ("ویو ابدی دریا", [(Feature.SEA_VIEW, HAS, False)]),
        (f"چشم{ZWNJ}انداز دریا از تراس", [(Feature.SEA_VIEW, HAS, False)]),
        ("ساحل اختصاصی دارد", [(Feature.NEAR_SEA, HAS, False)]),
        ("در منطقه جنگلی", [(Feature.FOREST, HAS, False)]),
        (f"کباب{ZWNJ}پز و منقل", [(Feature.BARBECUE, HAS, False)]),
        ("شومینه هیزمی", [(Feature.FIREPLACE, HAS, False)]),
        (
            "پارکینگ ندارد. استخر دارد",
            [(Feature.PARKING, HAS_NOT, False), (Feature.POOL, HAS, False)],
        ),
        ("استخر بزرگ. استخر سرپوشیده", [(Feature.POOL, HAS, False)]),  # one claim per feature
        # Found on real listings while checking the first report by hand:
        ("دریا ویلا را بی نیاز از استخر میکند", []),
        ("استخر فعلا قابل استفاده نیست", [(Feature.POOL, HAS_NOT, False)]),
        ("استخر اختصاصی. استخر فعلا قابل استفاده نیست", [(Feature.POOL, HAS_NOT, False)]),
        (
            "استخر مشاع. ویلا استخر ندارد",
            [(Feature.POOL, HAS, True), (Feature.POOL, HAS_NOT, False)],
        ),
        ("استفاده از حیاط و پارکینگ به صورت اشتراکی است", [(Feature.PARKING, HAS, True)]),
    ],
)
def test_claims(text: str, expected: list[tuple[Feature, Polarity, bool]]) -> None:
    assert found(text) == expected


def test_spans_are_verbatim_slices() -> None:
    text = f"ویلای دوبلکس با چشم{ZWNJ}انداز دریا و استخر"
    for claim in extract_claims(text):
        assert claim.span == text[claim.start : claim.end]
        assert claim.span in text


def claim(polarity: Polarity = HAS, shared: bool = False) -> DescriptionClaim:
    return DescriptionClaim(Feature.POOL, polarity, 0, 5, "استخر", shared)


def test_claims_against_the_amenity_list() -> None:
    assert against_amenities(claim(), {Feature.POOL: True}) is Agreement.AGREES
    assert against_amenities(claim(HAS_NOT), {Feature.POOL: False}) is Agreement.AGREES
    assert against_amenities(claim(), {Feature.POOL: False}) is Agreement.AMENITIES_DISAGREE
    assert against_amenities(claim(), {}) is Agreement.AMENITIES_SILENT
    shared = claim(shared=True)
    assert against_amenities(shared, {Feature.POOL: False}) is Agreement.AMENITIES_SILENT


AMENITIES = AmenityMap(
    {"p": {"pool-code": Feature.POOL, "pool-2": Feature.POOL, "park": Feature.PARKING}}
)


def test_the_amenity_map_reads_only_mapped_codes_and_yes_wins() -> None:
    item = listing(
        "1",
        amenities=(
            ParsedAmenity("pool-code", "استخر", False),
            ParsedAmenity("pool-2", "استخر", True),
            ParsedAmenity("park", "پارکینگ", False),
            ParsedAmenity("tv", "تلویزیون", True),
        ),
    )
    assert AMENITIES.features_of(item) == {Feature.POOL: True, Feature.PARKING: False}
    assert AmenityMap({}).features_of(item) == {}


async def test_report_counts_claims_and_shows_disagreements() -> None:
    listings = ListingsFake(
        [
            listing(
                "1", description="ویلا با استخر", amenities=(ParsedAmenity("pool-code", "", False),)
            ),
            listing(
                "2", description="بدون استخر", amenities=(ParsedAmenity("pool-code", "", False),)
            ),
            listing("3", description="استخر مشاع", amenities=()),
            listing("4", description=None, amenities=(ParsedAmenity("pool-code", "", True),)),
        ]
    )
    report = await MeasureFeatureClaims(listings, AMENITIES).run("p")
    assert (report.listings, report.with_description) == (4, 3)
    (pool,) = [r for r in report.rows if r.feature is Feature.POOL]
    assert (pool.amenity_yes, pool.amenity_no) == (1, 2)
    assert pool.claims == {"has": 1, "has_not": 1, "shared": 1}
    assert pool.agreement == {"amenities_disagree": 1, "agrees": 1, "amenities_silent": 1}
    (disagreement,) = pool.disagreements
    assert disagreement.listing == "p:1"
    assert "استخر" in disagreement.context


def test_the_project_config_loads_and_a_broken_one_fails(tmp_path: Path) -> None:
    amenity_map = load_amenity_map(Path(__file__).parents[4] / "config" / "features.toml")
    assert amenity_map.codes
    broken = tmp_path / "features.toml"
    broken.write_text('[p]\ncode = "not-a-feature"\n', encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_amenity_map(broken)


@pytest.mark.parametrize(
    ("amenity", "polarities", "evidence"),
    [
        (True, [], FeatureEvidence.LISTED),
        (False, [], FeatureEvidence.DENIED),
        (None, [HAS], FeatureEvidence.DESCRIBED),
        (None, [HAS_NOT], FeatureEvidence.DENIED),
        (None, [], FeatureEvidence.UNKNOWN),
        (True, [HAS_NOT], FeatureEvidence.UNKNOWN),  # the two sources contradict each other
        (False, [HAS], FeatureEvidence.UNKNOWN),
        (True, [HAS], FeatureEvidence.LISTED),
    ],
)
def test_feature_evidence(
    amenity: bool | None, polarities: list[Polarity], evidence: FeatureEvidence
) -> None:
    claims = [claim(p) for p in polarities]
    assert feature_evidence(amenity, claims) is evidence


def test_a_shared_facility_is_no_evidence_about_the_villa() -> None:
    assert feature_evidence(None, [claim(shared=True)]) is FeatureEvidence.UNKNOWN
    assert feature_evidence(False, [claim(shared=True)]) is FeatureEvidence.DENIED


@pytest.mark.parametrize(
    ("low", "high", "evidence"),
    [
        (0.0, 800.0, FeatureEvidence.MEASURED),
        (1200.0, 2000.0, FeatureEvidence.DENIED),
        (600.0, 1400.0, FeatureEvidence.UNKNOWN),  # the blur circle straddles the threshold
        (None, None, FeatureEvidence.UNKNOWN),
    ],
)
def test_near_sea_from_the_map(
    low: float | None, high: float | None, evidence: FeatureEvidence
) -> None:
    assert near_sea_evidence(low, high) is evidence
