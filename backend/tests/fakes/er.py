"""In-memory fakes for the entity-resolution ports."""

from __future__ import annotations

from collections.abc import Sequence

from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.entity_resolution.application.ports import MatchRun, ScoredCandidate
from villasanj.entity_resolution.domain.evidence import PhotoSimilarity
from villasanj.entity_resolution.domain.labels import PairLabel, QueueItem
from villasanj.entity_resolution.domain.pairs import PairKey
from villasanj.shared.domain.stay import DateRange


class ListingsFake:
    def __init__(self, listings: Sequence[Listing]) -> None:
        self.by_id = {listing.id: listing for listing in listings}

    async def get(self, listing_id: ListingId) -> Listing | None:
        return self.by_id.get(listing_id)

    async def listings(self, platform: str) -> list[Listing]:
        return sorted(
            (x for x in self.by_id.values() if x.id.platform == platform), key=lambda x: x.id
        )

    async def calendar(self, listing_id: ListingId, stay: DateRange) -> list[CalendarObservation]:
        return []

    async def calendars(
        self, platform: str, stay: DateRange
    ) -> dict[ListingId, list[CalendarObservation]]:
        return {}


class PhotoIndexFake:
    """Scripted photo comparisons: hash and embedding pairs, per-pair similarities."""

    def __init__(
        self,
        counts: dict[ListingId, int] | None = None,
        hash_pairs: dict[PairKey, int] | None = None,
        embedding_pairs: dict[PairKey, float] | None = None,
        similarities: dict[PairKey, list[PhotoSimilarity]] | None = None,
    ) -> None:
        self.counts = counts or {}
        self._hash = hash_pairs or {}
        self._embedding = embedding_pairs or {}
        self._similarities = similarities or {}

    @property
    def image_model(self) -> str | None:
        return "fake-model"

    @property
    def digest(self) -> str:
        return "fake-digest"

    def photo_count(self, listing: ListingId) -> int:
        return self.counts.get(listing, 0)

    def hash_pairs(self, max_hamming: int) -> dict[PairKey, int]:
        return {k: v for k, v in self._hash.items() if v <= max_hamming}

    def embedding_pairs(self, neighbours: int, min_cosine: float) -> dict[PairKey, float]:
        return dict(self._embedding)

    def similarities(self, key: PairKey) -> list[PhotoSimilarity]:
        return self._similarities.get(key, [])


class CandidateStoreFake:
    def __init__(self, candidates: Sequence[ScoredCandidate] = ()) -> None:
        self.runs: list[MatchRun] = []
        self.candidates = list(candidates)

    async def replace(self, run: MatchRun, candidates: Sequence[ScoredCandidate]) -> None:
        self.runs.append(run)
        self.candidates = list(candidates)

    async def current(self) -> list[ScoredCandidate]:
        return list(self.candidates)

    async def get(self, key: PairKey) -> ScoredCandidate | None:
        return next((c for c in self.candidates if c.key == key), None)

    async def latest_run(self) -> MatchRun | None:
        return self.runs[-1] if self.runs else None


class LabelStoreFake:
    def __init__(self) -> None:
        self.queues: dict[str, list[QueueItem]] = {}
        self.decisions: dict[tuple[PairKey, str], PairLabel] = {}

    async def save_queue(self, queue: str, items: Sequence[QueueItem]) -> None:
        self.queues.setdefault(queue, list(items))

    async def queue(self, queue: str) -> list[QueueItem]:
        return list(self.queues.get(queue, []))

    async def save_label(self, label: PairLabel) -> None:
        self.decisions[(label.key, label.labeler)] = label

    async def labels(self, labeler: str) -> list[PairLabel]:
        return [d for (_, who), d in self.decisions.items() if who == labeler]
