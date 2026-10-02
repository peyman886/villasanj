"""The gold set: a stratified queue of pairs and the owner's labels (ADR-0009)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import Listing
from villasanj.entity_resolution.application.ports import CandidateStore, LabelStore
from villasanj.entity_resolution.domain.labels import Label, PairLabel, QueueItem
from villasanj.entity_resolution.domain.pairs import BlockingSource, PairKey
from villasanj.entity_resolution.domain.sampling import (
    ScoredPair,
    Stratum,
    build_queue,
    score_bands,
)
from villasanj.shared.application.clock import Clock

PHOTO_SOURCES = frozenset({BlockingSource.PHOTO_HASH, BlockingSource.PHOTO_EMBEDDING})


@dataclass(frozen=True, slots=True)
class QueuePlan:
    """Pairs to draw per score band (lowest band first) and per special stratum.

    The high bands get more pairs because precision is decided there; the bands below still get
    some, so that missed matches (recall) can be found.
    """

    photo_bands: tuple[int, ...] = (6, 6, 6, 6, 6, 10, 12, 20, 35, 70)
    geo_bands: tuple[int, ...] = (4, 4, 4, 4, 4, 4, 6, 10, 18, 32)
    same_platform: int = 45
    wide: int = 50
    seed: int = 20261001


DEFAULT_PLAN = QueuePlan()


class QueueExists(Exception):
    """A queue name is used once; a new design needs a new name, so labels stay comparable."""


class BuildLabelQueue:
    def __init__(self, candidates: CandidateStore, labels: LabelStore) -> None:
        self._candidates = candidates
        self._labels = labels

    async def run(self, queue: str, plan: QueuePlan = DEFAULT_PLAN) -> list[QueueItem]:
        if await self._labels.queue(queue):
            raise QueueExists(queue)
        photo: list[ScoredPair] = []
        geo: list[ScoredPair] = []
        same: list[ScoredPair] = []
        wide: list[ScoredPair] = []
        for candidate in await self._candidates.current():
            value = candidate.score.value if candidate.score else 0.0
            pair = ScoredPair(candidate.key, value)
            if not candidate.blocked:
                wide.append(pair)
            elif not candidate.key.cross_platform:
                same.append(pair)
            elif candidate.sources & PHOTO_SOURCES:
                photo.append(pair)
            else:
                geo.append(pair)
        strata = [
            *score_bands("photo", photo, plan.photo_bands),
            *score_bands("geo", geo, plan.geo_bands),
            Stratum("same_platform", tuple(sorted(same, key=lambda p: p.key)), plan.same_platform),
            Stratum("wide", tuple(sorted(wide, key=lambda p: p.key)), plan.wide),
        ]
        items = build_queue(strata, plan.seed)
        await self._labels.save_queue(queue, items)
        return items


@dataclass(frozen=True, slots=True)
class LabelTask:
    item: QueueItem
    left: Listing
    right: Listing
    labeled: int  # pairs of this queue the labeler has labelled
    total: int
    current: Label | None  # the labeler's existing label on this pair, if any


class LabelingSession:
    def __init__(self, labels: LabelStore, listings: ListingReader, clock: Clock) -> None:
        self._labels = labels
        self._listings = listings
        self._clock = clock

    async def progress(self, queue: str, labeler: str) -> tuple[int, int] | None:
        """(pairs, labelled by ``labeler``); ``None`` when the queue does not exist."""
        items = await self._labels.queue(queue)
        if not items:
            return None
        done = {label.key for label in await self._labels.labels(labeler)}
        return len(items), sum(item.key in done for item in items)

    async def task(self, queue: str, labeler: str, position: int | None = None) -> LabelTask | None:
        """The pair at ``position``, or the first one the labeler has not labelled yet."""
        items = await self._labels.queue(queue)
        done = {label.key: label.label for label in await self._labels.labels(labeler)}
        labeled = sum(item.key in done for item in items)
        if position is not None:
            chosen = next((item for item in items if item.position == position), None)
        else:
            chosen = next((item for item in items if item.key not in done), None)
        if chosen is None:
            return None
        left = await self._listings.get(chosen.key.left)
        right = await self._listings.get(chosen.key.right)
        if left is None or right is None:
            return None
        return LabelTask(chosen, left, right, labeled, len(items), done.get(chosen.key))

    async def record(
        self, key: PairKey, label: Label, labeler: str, seconds: float | None
    ) -> PairLabel:
        decision = PairLabel(key, label, labeler, self._clock.now(), seconds)
        await self._labels.save_label(decision)
        return decision


def labelled_items(items: Sequence[QueueItem], labels: Sequence[PairLabel]) -> dict[str, int]:
    """Pairs labelled per stratum (the denominator of the stratum weights)."""
    keys = {label.key for label in labels}
    counts: dict[str, int] = {}
    for item in items:
        if item.key in keys:
            counts[item.stratum] = counts.get(item.stratum, 0) + 1
    return counts
