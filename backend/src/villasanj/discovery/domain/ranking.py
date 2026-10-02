"""Filtering and transparent ranking of candidates for a search (ROADMAP M8; provisional).

Built ahead of M8 at listing level; after M5 the candidates are canonical villas. Every exclusion
has a reason and every score is a sum of named contributions, so "why is this first?" always has
an answer built from facts (M10 turns them into slot-based text). There is no commission or
promotion factor.

Uncertainty is kept visible, never hidden: an unknown capacity, an open price that may exceed the
budget, or a requested feature nobody confirmed keeps the candidate, with a warning, and the
feature earns no points. Only stated facts exclude.

Order: first by how many requested features are confirmed (a user who asks for a pool sees the
villas with a confirmed pool first; a cheap one without evidence never jumps ahead), then by the
score. The score's weights are provisional (M8's ranking eval tunes them): price per person and
night 0.6, rating 0.4.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum

from villasanj.enrichment.domain.features import Feature, FeatureEvidence
from villasanj.shared.domain.money import MoneyRange

RATING_FLOOR = 1.0  # platform scales are 1..5
RATING_SPAN = 4.0
WEIGHTS = {"price": 0.6, "rating": 0.4}


class BudgetBasis(StrEnum):
    PER_NIGHT = "per_night"
    WHOLE_STAY = "whole_stay"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Candidate:
    id: str
    total: MoneyRange | None  # the all-in offer for the stay and group; None: no price known
    bookable: bool  # the newest observations show every night available
    max_capacity: int | None
    bedrooms: int | None
    rating: float | None  # Bayesian-shrunk, on the 1..5 scale
    features: Mapping[Feature, FeatureEvidence] = field(default_factory=dict)
    drive_minutes: tuple[float, float] | None = None  # free-flow, over the blur circle
    contradicted_claims: int = 0  # published distances the map contradicts even at best


@dataclass(frozen=True, slots=True)
class Requirements:
    nights: int
    guests: int | None = None
    bedrooms_min: int | None = None
    budget_toman: int | None = None
    budget_basis: BudgetBasis = BudgetBasis.UNKNOWN
    features: tuple[Feature, ...] = ()
    max_drive_minutes: float | None = None


class Exclusion(StrEnum):
    NOT_BOOKABLE = "not_bookable"
    TOO_SMALL = "too_small"
    FEW_BEDROOMS = "few_bedrooms"
    OVER_BUDGET = "over_budget"
    FEATURE_DENIED = "feature_denied"
    TOO_FAR = "too_far"  # even the quickest possible route is over the drive limit


class Caution(StrEnum):
    CAPACITY_UNKNOWN = "capacity_unknown"
    BEDROOMS_UNKNOWN = "bedrooms_unknown"
    PRICE_UNKNOWN = "price_unknown"
    MAY_EXCEED_BUDGET = "may_exceed_budget"  # an open or ranged price straddles the budget
    FEATURE_UNCONFIRMED = "feature_unconfirmed"
    FEATURE_ONLY_DESCRIBED = "feature_only_described"
    DRIVE_UNKNOWN = "drive_unknown"
    MAY_EXCEED_DRIVE = "may_exceed_drive"  # the blurred location's range straddles the limit
    CLAIM_CONTRADICTED = "claim_contradicted"  # a published distance the map contradicts


@dataclass(frozen=True, slots=True)
class Contribution:
    component: str  # "price", "rating", "features"
    normalized: float  # 0..1 within this search
    weight: float

    @property
    def points(self) -> float:
        return self.normalized * self.weight


@dataclass(frozen=True, slots=True)
class Ranked:
    candidate: Candidate
    confirmed: int  # requested features confirmed (listed or described): the first sort key
    score: float
    contributions: tuple[Contribution, ...]
    warnings: frozenset[Caution]
    price_per_person_night_toman: float | None


@dataclass(frozen=True, slots=True)
class Ranking:
    results: tuple[Ranked, ...]  # best first
    excluded: Mapping[Exclusion, int]
    # When the budget basis is unknown and the two readings keep different candidates, the
    # counts per reading, so the user can be asked with the numbers that change.
    budget_readings: Mapping[BudgetBasis, int] | None = None


def rank(candidates: Sequence[Candidate], wants: Requirements) -> Ranking:
    if wants.budget_toman is not None and wants.budget_basis is BudgetBasis.UNKNOWN:
        per_night = _filter(candidates, wants, BudgetBasis.PER_NIGHT)
        whole = _filter(candidates, wants, BudgetBasis.WHOLE_STAY)
        if {c.id for c, _ in per_night[0]} != {c.id for c, _ in whole[0]}:
            readings = {
                BudgetBasis.PER_NIGHT: len(per_night[0]),
                BudgetBasis.WHOLE_STAY: len(whole[0]),
            }
            kept, excluded = whole  # the stricter reading until the user answers
            return Ranking(_score(kept, wants), excluded, readings)
        kept, excluded = whole
    else:
        kept, excluded = _filter(candidates, wants, wants.budget_basis)
    return Ranking(_score(kept, wants), excluded)


def _filter(
    candidates: Sequence[Candidate], wants: Requirements, basis: BudgetBasis
) -> tuple[list[tuple[Candidate, frozenset[Caution]]], dict[Exclusion, int]]:
    budget = _budget_total(wants, basis)
    kept: list[tuple[Candidate, frozenset[Caution]]] = []
    excluded: dict[Exclusion, int] = {}
    for candidate in candidates:
        reason, warnings = _check(candidate, wants, budget)
        if reason is None:
            kept.append((candidate, warnings))
        else:
            excluded[reason] = excluded.get(reason, 0) + 1
    return kept, excluded


def _budget_total(wants: Requirements, basis: BudgetBasis) -> int | None:
    if wants.budget_toman is None:
        return None
    if basis is BudgetBasis.PER_NIGHT:
        return wants.budget_toman * wants.nights
    return wants.budget_toman


def _check(
    candidate: Candidate, wants: Requirements, budget: int | None
) -> tuple[Exclusion | None, frozenset[Caution]]:
    warnings: set[Caution] = set()
    if not candidate.bookable:
        return Exclusion.NOT_BOOKABLE, frozenset()
    if wants.guests is not None:
        if candidate.max_capacity is None:
            warnings.add(Caution.CAPACITY_UNKNOWN)
        elif candidate.max_capacity < wants.guests:
            return Exclusion.TOO_SMALL, frozenset()
    if wants.bedrooms_min is not None:
        if candidate.bedrooms is None:
            warnings.add(Caution.BEDROOMS_UNKNOWN)
        elif candidate.bedrooms < wants.bedrooms_min:
            return Exclusion.FEW_BEDROOMS, frozenset()
    if candidate.total is None:
        warnings.add(Caution.PRICE_UNKNOWN)
    elif budget is not None:
        low, high = candidate.total.low.toman, candidate.total.high
        if low > budget:
            return Exclusion.OVER_BUDGET, frozenset()
        if high is None or high.toman > budget:
            warnings.add(Caution.MAY_EXCEED_BUDGET)
    if wants.max_drive_minutes is not None:
        if candidate.drive_minutes is None:
            warnings.add(Caution.DRIVE_UNKNOWN)
        elif candidate.drive_minutes[0] > wants.max_drive_minutes:
            return Exclusion.TOO_FAR, frozenset()
        elif candidate.drive_minutes[1] > wants.max_drive_minutes:
            warnings.add(Caution.MAY_EXCEED_DRIVE)
    for feature in wants.features:
        evidence = candidate.features.get(feature, FeatureEvidence.UNKNOWN)
        if evidence is FeatureEvidence.DENIED:
            return Exclusion.FEATURE_DENIED, frozenset()
        if evidence is FeatureEvidence.UNKNOWN:
            warnings.add(Caution.FEATURE_UNCONFIRMED)
        elif evidence is FeatureEvidence.DESCRIBED:
            warnings.add(Caution.FEATURE_ONLY_DESCRIBED)
    if candidate.contradicted_claims:
        warnings.add(Caution.CLAIM_CONTRADICTED)  # said, never a reason to exclude (rule 5)
    return None, frozenset(warnings)


def _per_person_night(candidate: Candidate, wants: Requirements) -> float | None:
    if candidate.total is None:
        return None
    people = wants.guests or 1
    return float(candidate.total.low.toman) / people / wants.nights


def _score(
    kept: list[tuple[Candidate, frozenset[Caution]]], wants: Requirements
) -> tuple[Ranked, ...]:
    prices = [p for c, _ in kept if (p := _per_person_night(c, wants)) is not None]
    cheapest, dearest = (min(prices), max(prices)) if prices else (0.0, 0.0)
    ranked = []
    for candidate, warnings in kept:
        price = _per_person_night(candidate, wants)
        parts = {
            "price": 0.0 if price is None else _closeness(price, cheapest, dearest),
            "rating": 0.0
            if candidate.rating is None
            else min(1.0, max(0.0, (candidate.rating - RATING_FLOOR) / RATING_SPAN)),
        }
        confirmed = sum(
            candidate.features.get(f)
            in (FeatureEvidence.LISTED, FeatureEvidence.MEASURED, FeatureEvidence.DESCRIBED)
            for f in wants.features
        )
        contributions = tuple(Contribution(name, parts[name], w) for name, w in WEIGHTS.items())
        score = sum(c.points for c in contributions)
        ranked.append(Ranked(candidate, confirmed, score, contributions, warnings, price))
    ranked.sort(key=lambda r: (-r.confirmed, -r.score, r.candidate.id))
    return tuple(ranked)


def _closeness(price: float, cheapest: float, dearest: float) -> float:
    """1 for the cheapest per person and night in this search, 0 for the dearest."""
    if dearest == cheapest:
        return 1.0
    return (dearest - price) / (dearest - cheapest)


DRIVE_COVERAGE_HOURS = (3, 4, 5, 6)


def drive_coverage(
    candidates: Sequence[Candidate],
    wants: Requirements,
    hours: Sequence[int] = DRIVE_COVERAGE_HOURS,
) -> dict[int, int]:
    """How many results the same search has with each drive limit (M8 criterion 3's note).

    Every other filter is applied as asked; a candidate without a drive time is not counted.
    """
    coverage = {}
    for limit in hours:
        limited = replace(wants, max_drive_minutes=float(limit * 60))
        budget = _budget_total(limited, limited.budget_basis)
        coverage[limit] = sum(
            c.drive_minutes is not None and _check(c, limited, budget)[0] is None
            for c in candidates
        )
    return coverage
