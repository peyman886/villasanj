"""Evaluate the current matcher against the owner's labels (ROADMAP M3 criterion 2)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from villasanj.entity_resolution.application.labeling import labelled_items
from villasanj.entity_resolution.application.ports import CandidateStore, LabelStore, MatchRun
from villasanj.entity_resolution.domain.evaluation import (
    Interval,
    LabelledScore,
    Metrics,
    blocking_recall,
    evaluate,
    operating_point,
    wilson,
)
from villasanj.entity_resolution.domain.labels import Label

CURVE_POINTS = (0.0, 2.0, 4.0, 6.0, 8.0, 10.0)


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    queue: str
    labeler: str
    run: MatchRun | None
    queued: int
    labelled: int
    unsure: Interval  # share of labelled pairs marked unsure
    operating_point: Metrics | None
    curve: tuple[Metrics, ...]
    blocking_recall: Interval
    labels_by_stratum: dict[str, dict[str, int]] = field(default_factory=dict)
    same_platform: dict[str, int] = field(default_factory=dict)


class EvaluateMatcher:
    def __init__(self, candidates: CandidateStore, labels: LabelStore) -> None:
        self._candidates = candidates
        self._labels = labels

    async def run(self, queue: str, labeler: str) -> EvaluationReport:
        items = await self._labels.queue(queue)
        labels = {label.key: label for label in await self._labels.labels(labeler)}
        in_queue = [item for item in items if item.key in labels]
        per_stratum = labelled_items(items, list(labels.values()))
        current = {c.key: c for c in await self._candidates.current()}

        by_stratum: dict[str, Counter[str]] = {}
        same_platform: Counter[str] = Counter()
        gold: list[LabelledScore] = []
        for item in in_queue:
            label = labels[item.key].label
            by_stratum.setdefault(item.stratum, Counter())[label.value] += 1
            if not item.key.cross_platform:
                same_platform[label.value] += 1
                continue
            candidate = current.get(item.key)
            weight = item.stratum_size / per_stratum[item.stratum]
            if candidate is None:  # labelled under an older run and no longer a candidate
                gold.append(LabelledScore(float("-inf"), label, blocked=False, weight=weight))
                continue
            value = candidate.score.value if candidate.score else float("-inf")
            gold.append(LabelledScore(value, label, candidate.blocked, weight))

        unsure = sum(1 for item in in_queue if labels[item.key].label is Label.UNSURE)
        return EvaluationReport(
            queue=queue,
            labeler=labeler,
            run=await self._candidates.latest_run(),
            queued=len(items),
            labelled=len(in_queue),
            unsure=wilson(unsure, len(in_queue)),
            operating_point=operating_point(gold),
            curve=tuple(evaluate(gold, threshold) for threshold in CURVE_POINTS),
            blocking_recall=blocking_recall(gold),
            labels_by_stratum={k: dict(v) for k, v in sorted(by_stratum.items())},
            same_platform=dict(same_platform),
        )
