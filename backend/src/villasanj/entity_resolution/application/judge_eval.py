"""The judge bake-off on the gold set (ROADMAP M5 criterion 4).

The gold pairs whose rule score falls in a band are judged by the configured model, and the
verdicts are compared with the owner's labels. Precision of "match" and recall of the labelled
matches are weighted by stratum, like the matcher's evaluation, so they estimate the band's
population. Unsure verdicts go to the human queue in production: their rate is a cost, not an
error. Judge verdicts are never gold labels.
"""

from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from villasanj.entity_resolution.application.judge import JudgeInput, Judgement, JudgePairs
from villasanj.entity_resolution.application.labeling import labelled_items
from villasanj.entity_resolution.application.ports import CandidateStore, LabelStore
from villasanj.entity_resolution.domain.evaluation import Interval, weighted_proportion
from villasanj.entity_resolution.domain.labels import Label
from villasanj.entity_resolution.domain.pairs import PairKey
from villasanj.shared.application.errors import LLMError
from villasanj.shared.application.llm.types import JobContext


@dataclass(frozen=True, slots=True)
class JudgedPair:
    key: PairKey
    label: Label
    score: float
    weight: float
    judgement: Judgement | None
    failure: str | None = None


@dataclass(frozen=True, slots=True)
class JudgeReport:
    pairs: list[JudgedPair]
    confusion: dict[str, dict[str, int]] = field(default_factory=dict)  # label -> verdict -> n

    @property
    def judged(self) -> list[JudgedPair]:
        return [p for p in self.pairs if p.judgement is not None]

    def match_precision(self, min_confidence: float = 0.0) -> Interval:
        said = [p for p in self.judged if _says_match(p, min_confidence)]
        return weighted_proportion(
            [p.weight for p in said if p.label is Label.MATCH],
            [p.weight for p in said if p.label is not Label.MATCH],
        )

    def match_recall(self, min_confidence: float = 0.0) -> Interval:
        matches = [p for p in self.judged if p.label is Label.MATCH]
        return weighted_proportion(
            [p.weight for p in matches if _says_match(p, min_confidence)],
            [p.weight for p in matches if not _says_match(p, min_confidence)],
        )

    @property
    def unsure_rate(self) -> float:
        judged = self.judged
        if not judged:
            return 0.0
        unsure = sum(
            p.judgement is not None and p.judgement.verdict.verdict == "unsure" for p in judged
        )
        return unsure / len(judged)

    @property
    def cost_usd(self) -> Decimal:
        return sum((p.judgement.cost_usd for p in self.judged if p.judgement), Decimal(0))

    def latency_ms(self) -> dict[str, list[int]]:
        by_model: dict[str, list[int]] = defaultdict(list)
        for p in self.judged:
            if p.judgement and not p.judgement.cache_hit:
                by_model[p.judgement.model].append(p.judgement.latency_ms)
        return dict(by_model)


def _says_match(pair: JudgedPair, min_confidence: float) -> bool:
    j = pair.judgement
    return j is not None and j.verdict.verdict == "match" and j.verdict.confidence >= min_confidence


class EvaluateJudge:
    def __init__(self, candidates: CandidateStore, labels: LabelStore, judge: JudgePairs) -> None:
        self._candidates = candidates
        self._labels = labels
        self._judge = judge

    async def gold_in_band(
        self, queue: str, labeler: str, low: float, high: float
    ) -> list[tuple[JudgeInput, Label, float, float]]:
        """(input, label, score, weight) for the cross-platform gold pairs in the band."""
        items = await self._labels.queue(queue)
        labels = {label.key: label for label in await self._labels.labels(labeler)}
        per_stratum = labelled_items(items, list(labels.values()))
        current = {c.key: c for c in await self._candidates.current()}
        found: list[tuple[JudgeInput, Label, float, float]] = []
        for item in items:
            label = labels.get(item.key)
            if label is None or label.label is Label.UNSURE or not item.key.cross_platform:
                continue
            candidate = current.get(item.key)
            if candidate is None or candidate.score is None or candidate.evidence is None:
                continue
            score = candidate.score.value
            if low <= score <= high:
                weight = item.stratum_size / per_stratum[item.stratum]
                found.append((JudgeInput(item.key, candidate.evidence), label.label, score, weight))
        return found

    async def run(
        self,
        queue: str,
        labeler: str,
        low: float,
        high: float,
        ctx: JobContext,
        concurrency: int = 4,
    ) -> JudgeReport:
        gold = await self.gold_in_band(queue, labeler, low, high)
        gate = asyncio.Semaphore(concurrency)

        async def one(
            judge_input: JudgeInput, label: Label, score: float, weight: float
        ) -> JudgedPair:
            async with gate:
                try:
                    judged = await self._judge.run([judge_input], ctx)
                except LLMError as error:
                    failure = type(error).__name__
                    return JudgedPair(judge_input.key, label, score, weight, None, failure)
            judgement = judged[0] if judged else None
            return JudgedPair(judge_input.key, label, score, weight, judgement)

        pairs = list(await asyncio.gather(*(one(*g) for g in gold)))
        confusion: dict[str, Counter[str]] = defaultdict(Counter)
        for pair in pairs:
            if pair.failure is not None:
                verdict = "failed"
            elif pair.judgement is None:
                verdict = "skipped"
            else:
                verdict = pair.judgement.verdict.verdict
            confusion[pair.label.value][verdict] += 1
        return JudgeReport(pairs, {k: dict(v) for k, v in confusion.items()})
