"""Measures behind the M3 hypotheses (ROADMAP M3 criterion 4), as pure functions.

- H2: for a matched pair, how the two platforms' totals for the same stay compare.
- H3: "hidden nights": nights free on one platform and taken on the other, counted only when the
  two observations are close in time, because availability is an observation, not a state.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from villasanj.catalog.domain.listing import CalendarObservation
from villasanj.ingestion.domain.parsed import Availability
from villasanj.pricing.domain.quote import Quote, QuoteStatus

_TAKEN = frozenset({Availability.UNAVAILABLE, Availability.BOOKED, Availability.BLOCKED})
P90 = 0.9


@dataclass(frozen=True, slots=True)
class PriceGap:
    """Listed totals of one stay on two platforms (fees are unknown on both: lower bounds)."""

    cheaper_platform: str | None  # None when equal
    ratio: float  # higher / lower, >= 1


def price_gap(first: Quote, second: Quote) -> PriceGap | None:
    """``None`` unless both platforms can be booked for the stay."""
    if first.status is not QuoteStatus.BOOKABLE or second.status is not QuoteStatus.BOOKABLE:
        return None
    if first.total is None or second.total is None:
        return None
    a, b = first.total.low.amount_rial, second.total.low.amount_rial
    if a == 0 or b == 0:
        return None
    if a == b:
        return PriceGap(None, 1.0)
    cheaper = first if a < b else second
    return PriceGap(cheaper.listing_id.platform, max(a, b) / min(a, b))


@dataclass(frozen=True, slots=True)
class GapSummary:
    pairs: int
    median_ratio: float | None
    p90_ratio: float | None
    cheaper: dict[str, int]  # platform -> pairs where it was cheaper (equal totals excluded)


def summarize_gaps(gaps: Sequence[PriceGap]) -> GapSummary:
    ratios = sorted(g.ratio for g in gaps)
    cheaper: dict[str, int] = {}
    for gap in gaps:
        if gap.cheaper_platform is not None:
            cheaper[gap.cheaper_platform] = cheaper.get(gap.cheaper_platform, 0) + 1
    return GapSummary(
        pairs=len(gaps),
        median_ratio=round(statistics.median(ratios), 4) if ratios else None,
        p90_ratio=round(ratios[min(len(ratios) - 1, int(P90 * len(ratios)))], 4)
        if ratios
        else None,
        cheaper=dict(sorted(cheaper.items())),
    )


@dataclass(frozen=True, slots=True)
class NightComparison:
    compared: int  # nights observed on both platforms within the time gap
    hidden: tuple[date, ...]  # free on one platform, taken on the other


def compare_calendars(
    first: Iterable[CalendarObservation],
    second: Iterable[CalendarObservation],
    max_gap: timedelta,
) -> NightComparison:
    a, b = _newest(first), _newest(second)
    compared = 0
    hidden = []
    for night in sorted(a.keys() & b.keys()):
        left, right = a[night], b[night]
        if abs(left.observed_at - right.observed_at) > max_gap:
            continue
        known = {left.availability, right.availability}
        if Availability.UNKNOWN in known:
            continue
        compared += 1
        if Availability.AVAILABLE in known and known & _TAKEN:
            hidden.append(night)
    return NightComparison(compared, tuple(hidden))


def _newest(observations: Iterable[CalendarObservation]) -> dict[date, CalendarObservation]:
    newest: dict[date, CalendarObservation] = {}
    for observation in observations:
        current = newest.get(observation.night)
        if current is None or observation.observed_at > current.observed_at:
            newest[observation.night] = observation
    return newest


@dataclass(frozen=True, slots=True)
class OverlapEstimate:
    """Real cross-platform pairs estimated from the predicted ones (H1).

    Predicted = TP + FP and real = TP + FN, so real ~ predicted x precision / recall. The range
    combines the ends of the two Wilson intervals (conservative; not itself a 95% interval) and
    is capped by the platform with fewer listings, since a listing has at most one partner.
    """

    estimate: float
    low: float
    high: float


def corrected_overlap(
    predicted: int,
    precision: tuple[float, float, float],  # estimate, low, high
    recall: tuple[float, float, float],
    cap: int,
) -> OverlapEstimate | None:
    p, p_low, p_high = precision
    r, r_low, r_high = recall
    if r <= 0 or r_high <= 0:
        return None
    high = predicted * p_high / r_low if r_low > 0 else float(cap)
    return OverlapEstimate(
        min(predicted * p / r, cap), min(predicted * p_low / r_high, cap), min(high, cap)
    )
