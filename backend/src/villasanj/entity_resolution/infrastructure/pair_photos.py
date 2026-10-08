"""One pair's photos, compared by the matcher's own in-memory index (M12 match evidence)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence

from villasanj.catalog.domain.listing import ListingId
from villasanj.catalog.domain.photo import ListingPhoto
from villasanj.entity_resolution.domain.evidence import PhotoSimilarity
from villasanj.entity_resolution.domain.pairs import PairKey
from villasanj.entity_resolution.infrastructure.photo_index import NumpyPhotoIndex

PhotosOf = Callable[[Sequence[ListingId]], Awaitable[list[ListingPhoto]]]
VectorsOf = Callable[[Sequence[str]], Awaitable[Mapping[str, tuple[float, ...]]]]


class IndexedPairPhotos:
    """Loads only the two listings' photos and vectors; the comparison is ``NumpyPhotoIndex``'s."""

    def __init__(self, photos_of: PhotosOf, vectors_of: VectorsOf, image_model: str) -> None:
        self._photos_of = photos_of
        self._vectors_of = vectors_of
        self._image_model = image_model

    async def similarities(self, key: PairKey) -> list[PhotoSimilarity]:
        photos = await self._photos_of([key.left, key.right])
        vectors = await self._vectors_of(sorted({p.sha256 for p in photos}))
        return NumpyPhotoIndex(photos, vectors, self._image_model).similarities(key)

    async def urls(self, listing: ListingId) -> dict[int, str]:
        return {p.position: p.url for p in await self._photos_of([listing])}
