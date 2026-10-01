"""Filtering with reasons, visible uncertainty, budget readings, and a transparent score."""

import pytest

from villasanj.discovery.domain.ranking import (
    BudgetBasis,
    Candidate,
    Caution,
    Exclusion,
    Requirements,
    rank,
)
from villasanj.enrichment.domain.features import Feature, FeatureEvidence
from villasanj.shared.domain.money import Money, MoneyRange


def toman(low: int, high: int | None = -1) -> MoneyRange:
    if high is None:
        return MoneyRange.at_least(Money.from_toman(low))
    if high == -1:
        return MoneyRange.exact(Money.from_toman(low))
    return MoneyRange.between(Money.from_toman(low), Money.from_toman(high))


DEFAULT_TOTAL = toman(10_000_000)


def candidate(id_: str, total: MoneyRange | None = DEFAULT_TOTAL, **overrides: object) -> Candidate:
    values: dict[str, object] = {
        "id": id_,
        "total": total,
        "bookable": True,
        "max_capacity": 6,
        "bedrooms": 2,
        "rating": 4.5,
        "features": {},
    }
    values.update(overrides)
    return Candidate(**values)  # type: ignore[arg-type]


TWO_NIGHTS = Requirements(nights=2, guests=4)


def test_stated_facts_exclude_with_a_reason() -> None:
    ranking = rank(
        [
            candidate("ok"),
            candidate("closed", bookable=False),
            candidate("small", max_capacity=3),
            candidate("one-bed", bedrooms=1),
            candidate("dear", toman(30_000_000)),
            candidate("no-pool", features={Feature.POOL: FeatureEvidence.DENIED}),
        ],
        Requirements(
            nights=2,
            guests=4,
            bedrooms_min=2,
            budget_toman=20_000_000,
            budget_basis=BudgetBasis.WHOLE_STAY,
            features=(Feature.POOL,),
        ),
    )
    assert [r.candidate.id for r in ranking.results] == ["ok"]
    assert ranking.excluded == {
        Exclusion.NOT_BOOKABLE: 1,
        Exclusion.TOO_SMALL: 1,
        Exclusion.FEW_BEDROOMS: 1,
        Exclusion.OVER_BUDGET: 1,
        Exclusion.FEATURE_DENIED: 1,
    }
    assert ranking.budget_readings is None


def test_unknowns_stay_in_with_a_caution_and_earn_nothing() -> None:
    wants = Requirements(
        nights=2,
        guests=4,
        bedrooms_min=2,
        budget_toman=12_000_000,
        budget_basis=BudgetBasis.WHOLE_STAY,
        features=(Feature.POOL,),
    )
    ranking = rank(
        [
            candidate("listed", features={Feature.POOL: FeatureEvidence.LISTED}),
            candidate("described", features={Feature.POOL: FeatureEvidence.DESCRIBED}),
            candidate("unknowns", toman(11_000_000, None), max_capacity=None, bedrooms=None),
            candidate("no-price", None, rating=None),
        ],
        wants,
    )
    by_id = {r.candidate.id: r for r in ranking.results}
    assert by_id["listed"].warnings == frozenset()
    assert by_id["described"].warnings == {Caution.FEATURE_ONLY_DESCRIBED}
    assert by_id["unknowns"].warnings == {
        Caution.CAPACITY_UNKNOWN,
        Caution.BEDROOMS_UNKNOWN,
        Caution.MAY_EXCEED_BUDGET,
        Caution.FEATURE_UNCONFIRMED,
    }
    assert Caution.PRICE_UNKNOWN in by_id["no-price"].warnings
    confirmed = {r.candidate.id: r.confirmed for r in ranking.results}
    assert confirmed == {"listed": 1, "described": 1, "unknowns": 0, "no-price": 0}
    assert by_id["no-price"].contributions[0].normalized == 0.0  # no price: no price points


def test_an_ambiguous_budget_is_reported_with_the_counts_that_change() -> None:
    candidates = [candidate("a", toman(8_000_000)), candidate("b", toman(18_000_000))]
    wants = Requirements(nights=2, guests=4, budget_toman=10_000_000)  # basis unknown
    ranking = rank(candidates, wants)
    assert ranking.budget_readings == {BudgetBasis.PER_NIGHT: 2, BudgetBasis.WHOLE_STAY: 1}
    assert [r.candidate.id for r in ranking.results] == ["a"]  # the stricter reading meanwhile
    same = rank(candidates, Requirements(nights=2, guests=4, budget_toman=30_000_000))
    assert same.budget_readings is None
    assert len(same.results) == 2


def test_the_score_is_the_sum_of_named_contributions() -> None:
    ranking = rank(
        [
            candidate("cheap", toman(8_000_000), rating=4.0),
            candidate("dear", toman(16_000_000), rating=5.0),
            candidate("mid", toman(12_000_000), rating=4.5),
        ],
        TWO_NIGHTS,
    )
    cheap = next(r for r in ranking.results if r.candidate.id == "cheap")
    assert [c.component for c in cheap.contributions] == ["price", "rating"]
    assert [c.weight for c in cheap.contributions] == [0.6, 0.4]
    assert cheap.contributions[0].normalized == 1.0
    assert cheap.contributions[1].normalized == pytest.approx(0.75)
    assert cheap.score == pytest.approx(0.6 + 0.4 * 0.75)
    assert cheap.price_per_person_night_toman == 1_000_000  # 8M / 4 people / 2 nights
    assert [r.candidate.id for r in ranking.results] == ["cheap", "mid", "dear"]
    assert sum(c.points for c in cheap.contributions) == pytest.approx(cheap.score)


def test_a_single_candidate_and_ties_are_deterministic() -> None:
    (only,) = rank([candidate("x")], TWO_NIGHTS).results
    assert only.contributions[0].normalized == 1.0
    tied = rank([candidate("b"), candidate("a")], TWO_NIGHTS)
    assert [r.candidate.id for r in tied.results] == ["a", "b"]


def test_without_a_group_size_the_price_is_per_night() -> None:
    (only,) = rank([candidate("x", max_capacity=None)], Requirements(nights=2)).results
    assert only.price_per_person_night_toman == 5_000_000
    assert only.warnings == frozenset()  # no group size asked: capacity does not matter


def test_confirmed_requested_features_come_before_a_better_score() -> None:
    wants = Requirements(nights=2, guests=4, features=(Feature.POOL,))
    ranking = rank(
        [
            candidate("cheap-unconfirmed", toman(4_000_000), rating=5.0),
            candidate(
                "dear-with-pool",
                toman(16_000_000),
                rating=3.0,
                features={Feature.POOL: FeatureEvidence.LISTED},
            ),
        ],
        wants,
    )
    first, second = ranking.results
    assert first.candidate.id == "dear-with-pool"
    assert first.score < second.score  # the score alone would have put it last
