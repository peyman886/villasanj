"""Zero-shot photo tags: scoring, a stratified labelling queue, labels and the threshold eval (M9).

Scores are computed once per image, model and prompt version (like the matching embeddings). The
queue samples, for every tag, photos from the top of its ranking, the middle and the rest, so the
owner's ~300 labels contain both positives and hard negatives. Thresholds come only from labels.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Protocol

from villasanj.enrichment.domain.photo_tags import (
    Labelled,
    PhotoTag,
    TagThreshold,
    choose_threshold,
)
from villasanj.ingestion.application.ports import SnapshotRepository
from villasanj.ingestion.domain.pages import PageKind
from villasanj.shared.application.blobs import BlobStore
from villasanj.shared.application.clock import Clock

HTTP_OK = 200
TOP, MIDDLE, REST = 20, 15, 15  # photos per tag drawn from each band of its ranking
MIDDLE_END = 300  # the middle band is ranks TOP..MIDDLE_END


class PhotoTagger(Protocol):
    @property
    def model_id(self) -> str:
        """Model, pinned revision and prompt version: scores of different ids are never mixed."""
        ...

    async def scores(self, images: Sequence[bytes]) -> list[dict[PhotoTag, float] | None]:
        """One score per tag for each image; ``None`` for bytes that are not a readable image."""
        ...


@dataclass(frozen=True, slots=True)
class TagScore:
    sha256: str
    model: str
    tag: PhotoTag
    score: float
    computed_at: datetime


class PhotoTagStore(Protocol):
    async def scored(self, model: str) -> set[str]: ...

    async def save(self, rows: Sequence[TagScore]) -> None: ...

    async def scores(self, model: str) -> dict[str, dict[PhotoTag, float]]: ...


@dataclass(frozen=True, slots=True)
class TagReport:
    model: str
    images: int = 0
    already_scored: int = 0
    scored: int = 0
    unreadable: int = 0


class TagPhotos:
    def __init__(
        self,
        snapshots: SnapshotRepository,
        blobs: BlobStore,
        tagger: PhotoTagger,
        store: PhotoTagStore,
        clock: Clock,
        batch_size: int = 32,
    ) -> None:
        self._snapshots = snapshots
        self._blobs = blobs
        self._tagger = tagger
        self._store = store
        self._clock = clock
        self._batch_size = batch_size

    async def run(self, platforms: Sequence[str]) -> TagReport:
        model = self._tagger.model_id
        keys = {
            snapshot.blob_key
            for platform in platforms
            for snapshot in await self._snapshots.list_for(platform, [PageKind.PHOTO])
            if snapshot.status == HTTP_OK
        }
        done = await self._store.scored(model)
        todo = sorted(keys - done)
        report = TagReport(model, images=len(keys), already_scored=len(keys) - len(todo))
        for start in range(0, len(todo), self._batch_size):
            batch = todo[start : start + self._batch_size]
            results = await self._tagger.scores([await self._blobs.get(key) for key in batch])
            now = self._clock.now()
            rows = [
                TagScore(key, model, tag, score, now)
                for key, scores in zip(batch, results, strict=True)
                if scores is not None
                for tag, score in scores.items()
            ]
            await self._store.save(rows)
            readable = sum(scores is not None for scores in results)
            report = replace(
                report,
                scored=report.scored + readable,
                unreadable=report.unreadable + len(batch) - readable,
            )
        return report


@dataclass(frozen=True, slots=True)
class QueuedPhoto:
    queue: str
    position: int
    sha256: str
    url: str
    stratum: str  # e.g. "pool:top"


class PhotoUrls(Protocol):
    async def urls(self, sha256s: Sequence[str]) -> dict[str, str]:
        """A platform URL for each image (shown hotlinked; the stored bytes were scored)."""
        ...


@dataclass(frozen=True, slots=True)
class PhotoTask:
    item: QueuedPhoto
    total: int
    labelled: int
    present: frozenset[PhotoTag]  # what this labeller already said, if anything
    done: bool  # every photo of the queue is labelled


class PhotoQueueStore(Protocol):
    async def exists(self, queue: str) -> bool: ...

    async def save(self, items: Sequence[QueuedPhoto], created_at: datetime) -> None: ...

    async def items(self, queue: str) -> list[QueuedPhoto]: ...

    async def labels(self, queue: str, labeler: str) -> dict[str, frozenset[PhotoTag]]:
        """For each labelled photo, the tags marked present."""
        ...

    async def save_label(
        self, queue: str, sha256: str, present: frozenset[PhotoTag], labeler: str, at: datetime
    ) -> None: ...


class PhotoQueueExists(ValueError):
    """Queues are drawn once: a second draw would change what was labelled."""


def _rank_key(seed: str, sha256: str) -> str:
    return hashlib.sha256(f"{seed}:{sha256}".encode()).hexdigest()


def draw_queue(name: str, scores: dict[str, dict[PhotoTag, float]]) -> list[tuple[str, str]]:
    """(sha256, stratum) pairs: per tag its top photos, a middle band and a sample of the rest."""
    chosen: dict[str, str] = {}
    for tag in PhotoTag:
        ranked = sorted(scores, key=lambda s: (-scores[s].get(tag, 0.0), s))
        bands = (
            ("top", ranked[:TOP], TOP),
            ("middle", ranked[TOP:MIDDLE_END], MIDDLE),
            ("rest", ranked[MIDDLE_END:], REST),
        )
        for band, members, count in bands:
            sample = sorted(members, key=lambda s: _rank_key(f"{name}:{tag}:{band}", s))
            picked = [s for s in sample if s not in chosen][:count]
            for sha in picked:
                chosen[sha] = f"{tag}:{band}"
    order = sorted(chosen, key=lambda s: _rank_key(name, s))  # shuffle: no strata in a row
    return [(sha, chosen[sha]) for sha in order]


class BuildPhotoTagQueue:
    def __init__(
        self,
        scores: PhotoTagStore,
        urls: PhotoUrls,
        queues: PhotoQueueStore,
        clock: Clock,
        model: str,
    ) -> None:
        self._scores = scores
        self._urls = urls
        self._queues = queues
        self._clock = clock
        self._model = model

    async def run(self, name: str) -> list[QueuedPhoto]:
        if await self._queues.exists(name):
            raise PhotoQueueExists(name)
        scores = await self._scores.scores(self._model)
        urls = await self._urls.urls(sorted(scores))
        drawn = [(sha, stratum) for sha, stratum in draw_queue(name, scores) if sha in urls]
        items = [
            QueuedPhoto(name, position, sha, urls[sha], stratum)
            for position, (sha, stratum) in enumerate(drawn, start=1)
        ]
        await self._queues.save(items, self._clock.now())
        return items


class PhotoLabeling:
    def __init__(self, queues: PhotoQueueStore, clock: Clock) -> None:
        self._queues = queues
        self._clock = clock

    async def task(self, queue: str, labeler: str, position: int | None = None) -> PhotoTask | None:
        """The photo at ``position``, or the first one not labelled yet; ``None``: no such queue."""
        items = await self._queues.items(queue)
        if not items:
            return None
        labels = await self._queues.labels(queue, labeler)
        if position is not None:
            item = next((i for i in items if i.position == position), items[0])
        else:
            item = next((i for i in items if i.sha256 not in labels), items[-1])
        return PhotoTask(
            item,
            len(items),
            len(labels),
            labels.get(item.sha256, frozenset()),
            len(labels) >= len(items),
        )

    async def label(
        self, queue: str, sha256: str, present: frozenset[PhotoTag], labeler: str
    ) -> None:
        await self._queues.save_label(queue, sha256, present, labeler, self._clock.now())


@dataclass(frozen=True, slots=True)
class PhotoTagEvaluation:
    model: str
    labelled_photos: int
    thresholds: list[TagThreshold] = field(default_factory=list)


class EvaluatePhotoTags:
    def __init__(self, scores: PhotoTagStore, queues: PhotoQueueStore, model: str) -> None:
        self._scores = scores
        self._queues = queues
        self._model = model

    async def run(self, queue: str, labeler: str) -> PhotoTagEvaluation:
        labels = await self._queues.labels(queue, labeler)
        scores = await self._scores.scores(self._model)
        labelled = {sha: tags for sha, tags in labels.items() if sha in scores}
        thresholds = [
            choose_threshold(
                tag,
                [
                    Labelled(scores[sha].get(tag, 0.0), tag in tags)
                    for sha, tags in labelled.items()
                ],
            )
            for tag in PhotoTag
        ]
        return PhotoTagEvaluation(self._model, len(labelled), thresholds)
