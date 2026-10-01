"""Entity-resolution domain: pair keys, photo and pair evidence, rule scores, sampling, metrics."""

import pytest

from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from villasanj.catalog.domain.listing import Listing, ListingId
from villasanj.entity_resolution.domain.evaluation import (
    LabelledScore,
    blocking_recall,
    evaluate,
    operating_point,
    weighted_proportion,
    wilson,
)
from villasanj.entity_resolution.domain.evidence import (
    PairEvidence,
    PhotoEvidence,
    PhotoSimilarity,
    pair_evidence,
    photo_evidence,
)
from villasanj.entity_resolution.domain.labels import Label
from villasanj.entity_resolution.domain.pairs import PairKey
from villasanj.entity_resolution.domain.sampling import (
    ScoredPair,
    Stratum,
    build_queue,
    score_bands,
)
from villasanj.entity_resolution.domain.scoring import score
from villasanj.ingestion.domain.parsed import ParsedRateCard
from villasanj.shared.domain.geo import GeoPoint
from villasanj.shared.domain.money import Money

SNAPSHOT = "00000000-0000-0000-0000-000000000701"
A, B, C = ListingId("jabama", "1"), ListingId("shab", "2"), ListingId("shab", "3")

# ---------------------------------------------------------------- pairs


def test_pair_keys_are_canonical_and_round_trip() -> None:
    assert PairKey.of(B, A) == PairKey.of(A, B) == PairKey(A, B)
    assert str(PairKey.of(A, B)) == "jabama:1|shab:2"
    assert PairKey.parse("shab:2|jabama:1") == PairKey(A, B)
    assert PairKey(A, B).cross_platform
    assert not PairKey(B, C).cross_platform


def test_invalid_pairs_are_rejected() -> None:
    with pytest.raises(ValueError, match="itself"):
        PairKey.of(A, A)
    with pytest.raises(ValueError, match="canonical"):
        PairKey(B, A)


# ---------------------------------------------------------------- photo evidence


def sim(
    left: int, right: int, hamming: int | None, cosine: float | None, df: int = 1
) -> PhotoSimilarity:
    return PhotoSimilarity(left, right, hamming, cosine, df)


@pytest.mark.parametrize(
    ("hamming", "cosine", "strength"),
    [
        (4, None, 1.0),
        (None, 0.95, 1.0),
        (9, None, 0.5),
        (None, 0.88, 0.5),
        (20, 0.5, 0.0),
        (None, None, 0.0),
    ],
)
def test_photo_strength(hamming: int | None, cosine: float | None, strength: float) -> None:
    assert sim(0, 0, hamming, cosine).strength == strength


def test_each_photo_counts_once_and_shared_photos_weigh_less() -> None:
    evidence = photo_evidence(
        [
            sim(0, 0, 2, 0.99),  # strong
            sim(0, 1, 3, 0.98),  # same left photo again: ignored
            sim(1, 1, None, 0.87, df=1),  # weak
            sim(2, 2, 5, None, df=4),  # strong but a complex/stock photo
            sim(3, 3, 30, 0.2),  # unrelated
        ],
        left_photos=5,
        right_photos=4,
    )
    assert (evidence.strong_matches, evidence.weak_matches) == (2, 1)
    assert evidence.weighted_matches == 1 + 0.5 + 0.25
    assert evidence.best_cosine == 0.99
    assert evidence.best_hamming == 2


def test_no_photos_means_no_measures() -> None:
    evidence = photo_evidence([], 0, 3)
    assert evidence == PhotoEvidence(0, 3, 0, 0, 0.0, None, None)


# ---------------------------------------------------------------- pair evidence


def listing(external_id: str, **overrides: object) -> Listing:
    return Listing.from_parsed(parsed(external_id=external_id, **overrides), SNAPSHOT, NOW)


NO_PHOTOS = PhotoEvidence(5, 5, 0, 0, 0.0, None, None)


def test_pair_evidence_compares_structure_location_price_and_title() -> None:
    left = listing(
        "1",
        title="ویلا دوبلکس جنگلی رامسر",
        location=GeoPoint(36.9, 50.66),
        location_radius_m=400,
        bedrooms=3,
        bathrooms=2,
        area_m2=200,
        base_capacity=6,
        extra_capacity=2,
        rate_card=ParsedRateCard(base=Money.from_toman(3_000_000)),
    )
    right = listing(
        "2",
        title="ویلا دوبلکس جنگلی در رامسر",
        location=GeoPoint(36.905, 50.66),  # ~556 m north
        location_radius_m=None,
        bedrooms=2,
        bathrooms=2,
        area_m2=100,
        base_capacity=4,
        extra_capacity=0,
        rate_card=ParsedRateCard(base=Money.from_toman(6_000_000)),
    )
    evidence = pair_evidence(left, right, NO_PHOTOS)
    assert evidence.distance_min_m == pytest.approx(156, abs=2)
    assert (evidence.bedrooms_diff, evidence.bathrooms_diff, evidence.capacity_diff) == (1, 0, 4)
    assert evidence.area_ratio == 0.5
    assert evidence.price_ratio == 2.0
    assert evidence.title_similarity > 0.5


def test_unknown_fields_stay_unknown() -> None:
    left = listing("1", location=None, bedrooms=None, area_m2=None, title="ab")
    right = listing("2", area_m2=0, rate_card=ParsedRateCard(), title="ab")
    evidence = pair_evidence(left, right, NO_PHOTOS)
    assert evidence.distance_min_m is None
    assert evidence.bedrooms_diff is None
    assert evidence.area_ratio is None
    assert evidence.price_ratio is None
    assert evidence.title_similarity == 0.0  # too short for a trigram


# ---------------------------------------------------------------- scoring


def evidence(**overrides: object) -> PairEvidence:
    values: dict[str, object] = {
        "photos": NO_PHOTOS,
        "distance_min_m": None,
        "bedrooms_diff": None,
        "bathrooms_diff": None,
        "capacity_diff": None,
        "area_ratio": None,
        "price_ratio": None,
        "title_similarity": 0.0,
    }
    values.update(overrides)
    return PairEvidence(**values)  # type: ignore[arg-type]


def test_shared_photos_dominate_and_are_capped() -> None:
    photos = PhotoEvidence(5, 5, 6, 0, 6.0, 0.99, 0)
    result = score(evidence(photos=photos, distance_min_m=0.0, bedrooms_diff=0))
    assert [c.feature for c in result.contributions] == [
        "shared_photos",
        "location_overlaps",
        "same_bedrooms",
    ]
    assert result.value == 2.5 * 4 + 1.0 + 0.5


@pytest.mark.parametrize(
    ("overrides", "feature", "points"),
    [
        ({}, "no_shared_photo", -2.0),
        ({"distance_min_m": 1500.0}, "far_apart", -3.0),
        ({"distance_min_m": 5000.0}, "very_far_apart", -6.0),
        ({"bedrooms_diff": 1}, "bedrooms_off_by_one", -0.5),
        ({"bedrooms_diff": 3}, "bedrooms_differ", -2.5),
        ({"capacity_diff": 3}, "capacity_differs", -1.0),
        ({"area_ratio": 0.5}, "area_differs", -1.0),
        ({"price_ratio": 2.0}, "price_apart", -1.0),
        ({"price_ratio": 3.0}, "price_far_apart", -2.0),
        ({"title_similarity": 0.7}, "similar_titles", 1.0),
    ],
)
def test_each_rule_is_explained(overrides: dict[str, object], feature: str, points: float) -> None:
    contributions = {c.feature: c.points for c in score(evidence(**overrides)).contributions}
    assert contributions[feature] == points


def test_too_few_photos_say_nothing_and_near_locations_are_neutral() -> None:
    result = score(
        evidence(
            photos=PhotoEvidence(2, 9, 0, 0, 0.0, None, None), distance_min_m=500, price_ratio=1.2
        )
    )
    assert result.contributions == ()
    assert result.value == 0


# ---------------------------------------------------------------- sampling


def pairs(count: int) -> list[ScoredPair]:
    return [
        ScoredPair(
            PairKey(ListingId("jabama", f"{i:03d}"), ListingId("shab", f"{i:03d}")), float(i)
        )
        for i in range(count)
    ]


def test_score_bands_split_evenly_from_the_lowest() -> None:
    bands = score_bands("photo", pairs(10), [1, 1, 5])
    assert [s.name for s in bands] == ["photo:band01", "photo:band02", "photo:band03"]
    assert [len(s.pairs) for s in bands] == [3, 3, 4]
    assert bands[2].pairs[-1].score == 9.0


def test_queue_is_deterministic_interleaved_and_records_stratum_sizes() -> None:
    strata = [
        Stratum("low", tuple(pairs(20)[:10]), 2),
        Stratum("high", tuple(pairs(20)[10:]), 4),
        Stratum("tiny", tuple(pairs(30)[20:21]), 5),  # asks for more than it has
    ]
    queue = build_queue(strata, seed=7)
    assert queue == build_queue(strata, seed=7)
    assert [item.position for item in queue] == list(range(7))
    assert {item.stratum for item in queue[:3]} == {"low", "high", "tiny"}
    sizes = {item.stratum: item.stratum_size for item in queue}
    assert sizes == {"low": 10, "high": 10, "tiny": 1}


def test_overlapping_strata_are_rejected() -> None:
    shared = tuple(pairs(2))
    with pytest.raises(ValueError, match="overlap"):
        build_queue([Stratum("a", shared, 2), Stratum("b", shared, 2)], seed=1)


# ---------------------------------------------------------------- evaluation


def test_wilson_interval() -> None:
    interval = wilson(95, 100)
    assert interval.estimate == 0.95
    assert interval.low == pytest.approx(0.8882, abs=1e-4)
    assert interval.high == pytest.approx(0.9785, abs=1e-4)
    assert wilson(0, 0).estimate is None


def test_weighted_proportion_uses_the_effective_sample_size() -> None:
    assert weighted_proportion([1.0] * 95, [1.0] * 5) == wilson(95, 100)
    heavy = weighted_proportion([1.0], [9.0])
    assert heavy.estimate == pytest.approx(0.1)
    assert weighted_proportion([], []).estimate is None


GOLD = [
    LabelledScore(10, Label.MATCH),
    LabelledScore(8, Label.MATCH),
    LabelledScore(6, Label.NON_MATCH),
    LabelledScore(4, Label.MATCH),
    LabelledScore(1, Label.NON_MATCH),
    LabelledScore(9, Label.UNSURE),
    LabelledScore(0, Label.MATCH, blocked=False),  # only the wide net found it
]


def test_confusion_counts_at_a_threshold() -> None:
    metrics = evaluate(GOLD, threshold=5)
    counts = (
        metrics.true_positives,
        metrics.false_positives,
        metrics.false_negatives,
        metrics.true_negatives,
        metrics.unsure,
    )
    assert counts == (2, 1, 2, 1, 1)
    assert metrics.precision.estimate == pytest.approx(2 / 3)
    assert metrics.recall.estimate == pytest.approx(0.5)
    assert metrics.f1 == pytest.approx(4 / 7)


def test_no_predictions_means_no_f1() -> None:
    assert evaluate(GOLD, threshold=100).f1 is None


def test_operating_point_is_the_lowest_threshold_meeting_both_precision_bars() -> None:
    gold = [LabelledScore(10 + i, Label.MATCH) for i in range(60)] + [
        LabelledScore(5, Label.NON_MATCH),
        LabelledScore(2, Label.MATCH),
    ]
    point = operating_point(gold)
    assert point is not None
    assert point.threshold == 10
    assert operating_point(GOLD) is None


def test_blocking_recall_counts_gold_matches_found_by_blocking() -> None:
    assert blocking_recall(GOLD).estimate == pytest.approx(3 / 4)
