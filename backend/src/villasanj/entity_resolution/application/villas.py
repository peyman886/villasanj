"""Canonical villas from the match decisions (ROADMAP M5 criteria 5 and 7).

Decisions come from three deciders: the rule score at the operating threshold, the judge's
"match" verdicts above a confidence floor, and the owner's labels (a "match" label is a must-link,
a "not the same villa" label a cannot-link that no other decider overrides). Clustering is greedy,
strongest first, and never puts two listings of one platform in a villa (product rule 4); a
merge it refuses is reported with its reason. Canonical ids are reconciled with the previous run,
so a villa keeps its id while its members stay. ``use_labels=False`` builds the villas from the
deciders alone, which is what the gold set evaluates (B-cubed).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import ListingId
from villasanj.entity_resolution.application.labeling import labelled_items
from villasanj.entity_resolution.application.ports import CandidateStore, LabelStore, VillaStore
from villasanj.entity_resolution.domain.clustering import (
    Clustering,
    Decider,
    MatchDecision,
    cluster,
    reconcile,
)
from villasanj.entity_resolution.domain.evaluation import (
    BCubed,
    LabelledScore,
    Metrics,
    bcubed,
    evaluate,
)
from villasanj.entity_resolution.domain.labels import Label
from villasanj.entity_resolution.domain.pairs import PairKey

HUMAN_WEIGHT = 1e9  # a human must-link is applied before any machine decision


@dataclass(frozen=True, slots=True)
class StoredJudgement:
    key: PairKey
    verdict: str  # match / non_match / unsure
    confidence: float
    model: str


class JudgementStore(Protocol):
    async def all(self) -> list[StoredJudgement]: ...


@dataclass(frozen=True, slots=True)
class DecisionPolicy:
    """Who decides a candidate pair, by its rule score (ADR-0009 stages 3-4, ADR-0014).

    At or above ``judge_high`` the rules merge. In [``judge_low``, ``judge_high``) the judge's
    verdict decides when there is one: "match" at ``judge_min_confidence`` or more merges,
    "non_match" vetoes even a rule match, "unsure" or low confidence waits for a human. A pair
    in the zone the judge has not seen, and every pair outside it, follows the rule threshold.
    ``judge_low == judge_high`` turns the judge off.
    """

    threshold: float  # rule score of a match (from the gold set)
    judge_low: float = 0.0
    judge_high: float = 0.0
    judge_min_confidence: float = 0.8


@dataclass(slots=True)
class VillaReport:
    run_id: str | None
    listings: int = 0
    villas: int = 0
    multi_platform: int = 0
    applied: Counter[str] = field(default_factory=Counter)  # decider -> merges applied
    blocked: Counter[str] = field(default_factory=Counter)  # reason -> merges refused
    events: Counter[str] = field(default_factory=Counter)  # id history: created, merged, ...
    waiting_for_human: int = 0  # unsure or low-confidence judge verdicts in the zone


@dataclass(frozen=True, slots=True)
class Decisions:
    matches: list[MatchDecision]
    waiting: list[PairKey]  # for the human review queue


def decide(
    candidates: Sequence[tuple[PairKey, float, bool]],  # key, rule score, blocked
    judgements: Sequence[StoredJudgement],
    policy: DecisionPolicy,
) -> Decisions:
    judged = {j.key: j for j in judgements}
    matches: list[MatchDecision] = []
    waiting: list[PairKey] = []
    for key, score, blocked in candidates:
        if not (blocked and key.cross_platform):
            continue
        in_zone = policy.judge_low <= score < policy.judge_high
        verdict = judged.get(key) if in_zone else None
        if verdict is None:
            if score >= policy.threshold:
                matches.append(MatchDecision(key, score, Decider.RULE))
            continue
        if verdict.verdict == "match" and verdict.confidence >= policy.judge_min_confidence:
            # Below every rule match outside the zone: rules stay the strongest evidence.
            weight = policy.judge_low - 1 + verdict.confidence
            matches.append(MatchDecision(key, weight, Decider.JUDGE))
        elif verdict.verdict != "non_match":
            waiting.append(key)
    return Decisions(matches, waiting)


def decisions(
    candidates: Sequence[tuple[PairKey, float, bool]],
    judgements: Sequence[StoredJudgement],
    policy: DecisionPolicy,
) -> list[MatchDecision]:
    return decide(candidates, judgements, policy).matches


class BuildVillas:
    def __init__(
        self,
        candidates: CandidateStore,
        labels: LabelStore,
        villas: VillaStore,
        listings: ListingReader,
        platforms: Sequence[str],
        judgements: JudgementStore | None = None,
    ) -> None:
        self._candidates = candidates
        self._labels = labels
        self._villas = villas
        self._listings = listings
        self._platforms = tuple(platforms)
        self._judgements = judgements

    async def clustering(
        self, policy: DecisionPolicy, labeler: str | None
    ) -> tuple[list[ListingId], Clustering, list[PairKey]]:
        listing_ids = [
            x.id for platform in self._platforms for x in await self._listings.listings(platform)
        ]
        current = await self._candidates.current()
        rows = [(c.key, c.score.value, c.blocked) for c in current if c.score is not None]
        judged = await self._judgements.all() if self._judgements else []
        decided = decide(rows, judged, policy)
        machine = decided.matches
        cannot: list[PairKey] = []
        human: list[MatchDecision] = []
        if labeler is not None:
            for label in await self._labels.labels(labeler):
                if not label.key.cross_platform:
                    continue  # rule 4: one listing per platform; same-platform labels never merge
                if label.label is Label.MATCH:
                    human.append(MatchDecision(label.key, HUMAN_WEIGHT, Decider.HUMAN))
                elif label.label is Label.NON_MATCH:
                    cannot.append(label.key)
        labelled = {lb.key for lb in await self._labels.labels(labeler)} if labeler else set()
        waiting = [k for k in decided.waiting if k not in labelled]
        return listing_ids, cluster(listing_ids, [*human, *machine], cannot), waiting

    async def run(self, policy: DecisionPolicy, labeler: str | None = "owner") -> VillaReport:
        run = await self._candidates.latest_run()
        listing_ids, clustering, waiting = await self.clustering(policy, labeler)
        reconciliation = reconcile(await self._villas.current(), clustering.clusters)
        if run is not None:
            await self._villas.replace(run.id, reconciliation.villas, reconciliation.events)
        report = VillaReport(run.id if run else None, len(listing_ids))
        report.villas = len(reconciliation.villas)
        report.multi_platform = sum(len(v.members) > 1 for v in reconciliation.villas)
        report.applied.update(d.decided_by.value for d in clustering.applied)
        report.blocked.update(b.reason.value for b in clustering.blocked)
        report.events.update(e.kind.value for e in reconciliation.events)
        report.waiting_for_human = len(waiting)
        return report


@dataclass(frozen=True, slots=True)
class ClusterEvaluation:
    bcubed: BCubed | None
    gold_clusters: int
    gold_elements: int


class EvaluateVillas:
    """B-cubed (M5 criterion 3) of the machine clustering against clusters the owner's labels
    imply: listings joined by "same villa" labels, over the labelled cross-platform pairs."""

    def __init__(self, build: BuildVillas, labels: LabelStore) -> None:
        self._build = build
        self._labels = labels

    async def run(self, policy: DecisionPolicy, queue: str, labeler: str) -> ClusterEvaluation:
        _, clustering, _ = await self._build.clustering(policy, labeler=None)
        in_queue = {item.key for item in await self._labels.queue(queue)}
        labelled = [
            label
            for label in await self._labels.labels(labeler)
            if label.key in in_queue
            and label.key.cross_platform
            and label.label is not Label.UNSURE
        ]
        elements = {m for label in labelled for m in (label.key.left, label.key.right)}
        gold = _components(elements, [lb.key for lb in labelled if lb.label is Label.MATCH])
        predicted = [frozenset(g & elements) for g in clustering.clusters if g & elements]
        hashable_predicted: list[frozenset[Hashable]] = [frozenset(g) for g in predicted]
        hashable_gold: list[frozenset[Hashable]] = [frozenset(g) for g in gold]
        return ClusterEvaluation(
            bcubed(hashable_predicted, hashable_gold), len(gold), len(elements)
        )


def _components(elements: set[ListingId], links: Sequence[PairKey]) -> list[frozenset[ListingId]]:
    parent = {e: e for e in elements}

    def root(e: ListingId) -> ListingId:
        while parent[e] != e:
            parent[e] = parent[parent[e]]
            e = parent[e]
        return e

    for key in links:
        a, b = root(key.left), root(key.right)
        if a != b:
            parent[b] = a
    groups: dict[ListingId, set[ListingId]] = {}
    for e in elements:
        groups.setdefault(root(e), set()).add(e)
    return [frozenset(g) for g in groups.values()]


@dataclass(frozen=True, slots=True)
class DecisionEvaluation:
    metrics: Metrics  # weighted pairwise, at the policy (labels not applied)
    waiting: int  # labelled pairs the policy would send to a human


class EvaluateDecisions:
    """End-to-end pairwise precision and recall of a decision policy on the gold set (M5
    criterion 2): rules, judge vetoes and judge merges together, the owner's labels unused."""

    def __init__(
        self, candidates: CandidateStore, labels: LabelStore, judgements: JudgementStore
    ) -> None:
        self._candidates = candidates
        self._labels = labels
        self._judgements = judgements

    async def run(self, policy: DecisionPolicy, queue: str, labeler: str) -> DecisionEvaluation:
        items = await self._labels.queue(queue)
        labels = {label.key: label for label in await self._labels.labels(labeler)}
        per_stratum = labelled_items(items, list(labels.values()))
        current = {c.key: c for c in await self._candidates.current()}
        rows = [(c.key, c.score.value, c.blocked) for c in current.values() if c.score is not None]
        decided = decide(rows, await self._judgements.all(), policy)
        merged = {d.key for d in decided.matches}
        waiting = set(decided.waiting)
        gold = []
        for item in items:
            label = labels.get(item.key)
            if label is None or not item.key.cross_platform:
                continue
            weight = item.stratum_size / per_stratum[item.stratum]
            # A merged pair scores 1, everything else 0: evaluate() at threshold 1.
            gold.append(
                LabelledScore(1.0 if item.key in merged else 0.0, label.label, True, weight)
            )
        return DecisionEvaluation(
            evaluate(gold, 1.0),
            sum(1 for item in items if item.key in waiting and item.key in labels),
        )
