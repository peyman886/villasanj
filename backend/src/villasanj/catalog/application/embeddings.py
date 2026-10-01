"""Image embeddings for photo matching (ADR-0012): computed once per image and model."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from villasanj.catalog.domain.photo import PhotoEmbedding
from villasanj.ingestion.application.ports import SnapshotRepository
from villasanj.ingestion.domain.pages import PageKind
from villasanj.shared.application.blobs import BlobStore

HTTP_OK = 200


class ImageEmbedder(Protocol):
    @property
    def model_id(self) -> str:
        """Model name plus pinned revision: vectors of different ids are never compared."""
        ...

    async def embed(self, images: Sequence[bytes]) -> list[tuple[float, ...] | None]:
        """One unit-length vector per image; ``None`` for bytes that are not a readable image."""
        ...


class EmbeddingStore(Protocol):
    async def embedded(self, model_id: str) -> set[str]:
        """Content hashes already embedded with this model."""
        ...

    async def save(self, embeddings: Sequence[PhotoEmbedding]) -> None: ...

    async def vectors(self, model_id: str) -> dict[str, tuple[float, ...]]: ...


@dataclass(frozen=True, slots=True)
class EmbedReport:
    model_id: str
    images: int = 0  # distinct photo images available
    already_embedded: int = 0
    embedded: int = 0
    unreadable: int = 0


class EmbedPhotos:
    def __init__(
        self,
        snapshots: SnapshotRepository,
        blobs: BlobStore,
        embedder: ImageEmbedder,
        store: EmbeddingStore,
        batch_size: int = 32,
    ) -> None:
        self._snapshots = snapshots
        self._blobs = blobs
        self._embedder = embedder
        self._store = store
        self._batch_size = batch_size

    async def run(self, platforms: Sequence[str]) -> EmbedReport:
        model_id = self._embedder.model_id
        keys: list[str] = []
        for platform in platforms:
            for snapshot in await self._snapshots.list_for(platform, [PageKind.PHOTO]):
                if snapshot.status == HTTP_OK:
                    keys.append(snapshot.blob_key)
        distinct = sorted(set(keys))
        done = await self._store.embedded(model_id)
        todo = [key for key in distinct if key not in done]
        report = EmbedReport(
            model_id, images=len(distinct), already_embedded=len(distinct) - len(todo)
        )
        for start in range(0, len(todo), self._batch_size):
            batch = todo[start : start + self._batch_size]
            vectors = await self._embedder.embed([await self._blobs.get(key) for key in batch])
            rows = [
                PhotoEmbedding(key, model_id, vector)
                for key, vector in zip(batch, vectors, strict=True)
                if vector is not None
            ]
            await self._store.save(rows)
            report = replace(
                report,
                embedded=report.embedded + len(rows),
                unreadable=report.unreadable + len(batch) - len(rows),
            )
        return report
