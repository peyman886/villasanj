"""Matcher evaluation against the gold set: P/R/F1 with Wilson 95% intervals (ADR-0009).

The gold set is a stratified sample, so each labelled pair carries a weight (1 / its inclusion
probability). Proportions are weighted, and their Wilson interval uses Kish's effective sample
size; with equal weights this is the ordinary Wilson interval.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass

from villasanj.entity_resolution.domain.labels import Label

Z_95 = 1.959963984540054


@dataclass(frozen=True, slots=True)
class Interval:
    estimate: float | None
    low: float
    high: float

    def as_dict(self) -> dict[str, float | None]:
        return {"estimate": self.estimate, "low": self.low, "high": self.high}


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

    def as_dict(self) -> dict[str, object]:
        return {
            "threshold": self.threshold,
            "tp": self.true_positives,
            "fp": self.false_positives,
            "fn": self.false_negatives,
            "tn": self.true_negatives,
            "unsure": self.unsure,
            "precision": self.precision.as_dict(),
            "recall": self.recall.as_dict(),
            "f1": self.f1,
        }


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


@dataclass(frozen=True, slots=True)
class BCubed:
    precision: float
    recall: float
    f1: float
    elements: int


def bcubed(
    predicted: Iterable[frozenset[Hashable]], gold: Iterable[frozenset[Hashable]]
) -> BCubed | None:
    """B-cubed P/R/F1 over the elements both clusterings cover (ADR-0009; M5 criterion 3)."""
    predicted_of = {e: group for group in predicted for e in group}
    gold_of = {e: group for group in gold for e in group}
    shared = predicted_of.keys() & gold_of.keys()
    if not shared:
        return None
    precision = recall = 0.0
    for element in shared:
        both = len(predicted_of[element] & gold_of[element])
        precision += both / len(predicted_of[element])
        recall += both / len(gold_of[element])
    p, r = precision / len(shared), recall / len(shared)
    return BCubed(p, r, 2 * p * r / (p + r) if p + r else 0.0, len(shared))


PHOTO_FEATURES = frozenset({"shared_photos", "no_shared_photo"})


def partial_score(contributions: Iterable[tuple[str, float]], photos: bool) -> float:
    """The score from photo evidence only (``photos``) or from everything else (H5 ablation)."""
    return sum(points for feature, points in contributions if (feature in PHOTO_FEATURES) == photos)
