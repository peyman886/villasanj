"""Matcher evaluation against the gold set: P/R/F1 with Wilson 95% intervals (ADR-0009).

The gold set is a stratified sample, so each labelled pair carries a weight (1 / its inclusion
probability). Proportions are weighted, and their Wilson interval uses Kish's effective sample
size; with equal weights this is the ordinary Wilson interval.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from villasanj.entity_resolution.domain.labels import Label

Z_95 = 1.959963984540054


@dataclass(frozen=True, slots=True)
class Interval:
    estimate: float | None
    low: float
    high: float


def wilson(successes: float, trials: float, z: float = Z_95) -> Interval:
    """Wilson score interval; with no trials there is no estimate and the interval is [0, 1]."""
    if trials <= 0:
        return Interval(None, 0.0, 1.0)
    p = successes / trials
    denominator = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return Interval(p, max(0.0, centre - half), min(1.0, centre + half))


def weighted_proportion(hits: Sequence[float], misses: Sequence[float]) -> Interval:
    weights = [*hits, *misses]
    total = sum(weights)
    if total <= 0:
        return Interval(None, 0.0, 1.0)
    effective_n = total * total / sum(w * w for w in weights)
    return wilson(sum(hits) / total * effective_n, effective_n)


@dataclass(frozen=True, slots=True)
class LabelledScore:
    score: float
    label: Label
    blocked: bool = True  # found by the production blocking (False: only by the wide net)
    weight: float = 1.0  # 1 / inclusion probability in the stratified sample


@dataclass(frozen=True, slots=True)
class Metrics:
    threshold: float
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    unsure: int
    precision: Interval
    recall: Interval
    f1: float | None


def evaluate(pairs: Sequence[LabelledScore], threshold: float) -> Metrics:
    """A pair is predicted a match when it was blocked and its score is >= threshold."""
    cells: dict[str, list[float]] = {"tp": [], "fp": [], "fn": [], "tn": []}
    unsure = 0
    for pair in pairs:
        if pair.label is Label.UNSURE:
            unsure += 1
            continue
        predicted = pair.blocked and pair.score >= threshold
        actual = pair.label is Label.MATCH
        cell = ("tp" if actual else "fp") if predicted else ("fn" if actual else "tn")
        cells[cell].append(pair.weight)
    precision = weighted_proportion(cells["tp"], cells["fp"])
    recall = weighted_proportion(cells["tp"], cells["fn"])
    f1 = (
        2 * precision.estimate * recall.estimate / (precision.estimate + recall.estimate)
        if precision.estimate and recall.estimate
        else None
    )
    return Metrics(
        threshold,
        len(cells["tp"]),
        len(cells["fp"]),
        len(cells["fn"]),
        len(cells["tn"]),
        unsure,
        precision,
        recall,
        f1,
    )


def operating_point(
    pairs: Sequence[LabelledScore], min_precision: float = 0.95, min_precision_low: float = 0.92
) -> Metrics | None:
    """The lowest threshold whose precision estimate and Wilson lower bound both clear the bars
    (ADR-0009). Lowest threshold = highest recall among acceptable thresholds."""
    for threshold in sorted({p.score for p in pairs if p.label is not Label.UNSURE}):
        metrics = evaluate(pairs, threshold)
        estimate = metrics.precision.estimate
        if (
            estimate is not None
            and estimate >= min_precision
            and metrics.precision.low >= min_precision_low
        ):
            return metrics
    return None


def blocking_recall(pairs: Sequence[LabelledScore]) -> Interval:
    """Share of gold matches the production blocking found (the wide net finds the rest)."""
    matches = [p for p in pairs if p.label is Label.MATCH]
    return weighted_proportion(
        [p.weight for p in matches if p.blocked], [p.weight for p in matches if not p.blocked]
    )
