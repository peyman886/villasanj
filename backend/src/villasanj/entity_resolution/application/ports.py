"""Ports of the entity-resolution context."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from villasanj.catalog.domain.listing import ListingId
from villasanj.entity_resolution.domain.evidence import PairEvidence, PhotoSimilarity
from villasanj.entity_resolution.domain.labels import PairLabel, QueueItem
from villasanj.entity_resolution.domain.pairs import BlockingSource, PairKey
from villasanj.entity_resolution.domain.scoring import Score


class PhotoIndex(Protocol):
    """All fingerprinted photos with their hashes and embeddings, compared in memory."""

    @property
    def image_model(self) -> str | None:
        """Embedding model of the vectors in the index (``None``: hashes only)."""
        ...

    @property
    def digest(self) -> str:
        """Hash of every (listing, position, image) in the index and the image model."""
        ...

    def photo_count(self, listing: ListingId) -> int: ...

    def hash_pairs(self, max_hamming: int) -> dict[PairKey, int]:
        """Listing pairs with a photo pair within ``max_hamming`` bits (best distance)."""
        ...

    def embedding_pairs(self, neighbours: int, min_cosine: float) -> dict[PairKey, float]:
        """Listing pairs where a photo is among another listing's photo's nearest neighbours."""
        ...

    def similarities(self, key: PairKey) -> list[PhotoSimilarity]:
        """Every photo of one listing against every photo of the other."""
        ...


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    key: PairKey
    sources: frozenset[BlockingSource]
    blocked: bool  # False: in the wide net only (always predicted "not the same villa")
    evidence: PairEvidence | None
    score: Score | None


@dataclass(frozen=True, slots=True)
class MatchRun:
    id: str
    dataset_hash: str
    config: dict[str, object]
    counts: dict[str, int]
    created_at: datetime


class CandidateStore(Protocol):
    async def replace(self, run: MatchRun, candidates: Sequence[ScoredCandidate]) -> None:
        """Make this run's candidates the current ones."""
        ...

    async def current(self) -> list[ScoredCandidate]: ...

    async def get(self, key: PairKey) -> ScoredCandidate | None: ...

    async def latest_run(self) -> MatchRun | None: ...


class LabelStore(Protocol):
    async def save_queue(self, queue: str, items: Sequence[QueueItem]) -> None:
        """Create a queue; an existing queue of that name is never overwritten."""
        ...

    async def queue(self, queue: str) -> list[QueueItem]: ...

    async def save_label(self, label: PairLabel) -> None:
        """Upsert: a labeler's latest decision on a pair wins."""
        ...

    async def labels(self, labeler: str) -> list[PairLabel]: ...
