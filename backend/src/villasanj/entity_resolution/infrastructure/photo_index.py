"""In-memory photo index (numpy): exact pHash and embedding comparisons, no ANN approximation.

At ~20k photos an exact search takes seconds and gives the same answer every run, which matters
more for a reproducible gold set than the speed of an approximate index.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Mapping, Sequence

import numpy as np

from villasanj.catalog.domain.listing import ListingId
from villasanj.catalog.domain.photo import ListingPhoto
from villasanj.entity_resolution.domain.evidence import (
    STRONG_COSINE,
    STRONG_HAMMING,
    PhotoSimilarity,
)
from villasanj.entity_resolution.domain.pairs import PairKey

_CHUNK = 512  # rows per block: bounds memory at ~20k photos
_MASK64 = (1 << 64) - 1


class NumpyPhotoIndex:
    def __init__(
        self,
        photos: Sequence[ListingPhoto],
        vectors: Mapping[str, tuple[float, ...]],
        image_model: str | None,
    ) -> None:
        ordered = sorted(photos, key=lambda p: (p.listing_id, p.position))
        self._photos = ordered
        self._image_model = image_model
        self._listing_of = [p.listing_id for p in ordered]
        self._rows: dict[ListingId, list[int]] = defaultdict(list)
        for row, photo in enumerate(ordered):
            self._rows[photo.listing_id].append(row)
        self._hashes = np.array([p.fingerprint.phash & _MASK64 for p in ordered], dtype=np.uint64)
        dims = len(next(iter(vectors.values()))) if vectors else 0
        self._has_vector = np.array([p.sha256 in vectors for p in ordered], dtype=bool)
        matrix = np.zeros((len(ordered), dims), dtype=np.float32)
        for row, photo in enumerate(ordered):
            if photo.sha256 in vectors:
                matrix[row] = vectors[photo.sha256]
        self._vectors = matrix
        listing_codes = {listing: code for code, listing in enumerate(sorted(self._rows))}
        self._listing_code = np.array([listing_codes[x] for x in self._listing_of], dtype=np.int64)
        self._frequency = self._document_frequencies()

    # ---------------------------------------------------------------- PhotoIndex

    @property
    def image_model(self) -> str | None:
        return self._image_model if self._vectors.shape[1] else None

    @property
    def digest(self) -> str:
        digest = hashlib.sha256(str(self.image_model).encode())
        for photo in self._photos:
            digest.update(f"{photo.listing_id}:{photo.position}:{photo.sha256}\n".encode())
        digest.update(np.ascontiguousarray(self._has_vector).tobytes())
        return digest.hexdigest()

    def photo_count(self, listing: ListingId) -> int:
        return len(self._rows.get(listing, ()))

    def hash_pairs(self, max_hamming: int) -> dict[PairKey, int]:
        best: dict[PairKey, int] = {}
        for start in range(0, len(self._photos), _CHUNK):
            block = self._hashes[start : start + _CHUNK]
            distances = np.bitwise_count(block[:, None] ^ self._hashes[None, :])
            rows, cols = np.nonzero(distances <= max_hamming)
            for row, col in zip(rows + start, cols, strict=True):
                key = self._pair(int(row), int(col))
                if key is not None:
                    distance = int(distances[row - start, col])
                    best[key] = min(best.get(key, distance), distance)
        return best

    def embedding_pairs(self, neighbours: int, min_cosine: float) -> dict[PairKey, float]:
        best: dict[PairKey, float] = {}
        if not self._vectors.shape[1]:
            return best
        for start in range(0, len(self._photos), _CHUNK):
            sims = self._vectors[start : start + _CHUNK] @ self._vectors.T
            block_codes = self._listing_code[start : start + _CHUNK]
            sims[block_codes[:, None] == self._listing_code[None, :]] = -1.0  # own listing
            sims[:, ~self._has_vector] = -1.0
            sims[~self._has_vector[start : start + _CHUNK], :] = -1.0
            k = min(neighbours, sims.shape[1])
            top = np.argpartition(-sims, k - 1, axis=1)[:, :k]
            for offset, columns in enumerate(top):
                row = start + offset
                for col in columns:
                    value = round(float(sims[offset, col]), 4)
                    key = self._pair(row, int(col))
                    if value >= min_cosine and key is not None:
                        best[key] = max(best.get(key, value), value)
        return best

    def similarities(self, key: PairKey) -> list[PhotoSimilarity]:
        left_rows = self._rows.get(key.left, [])
        right_rows = self._rows.get(key.right, [])
        result = []
        for left in left_rows:
            for right in right_rows:
                both = bool(self._has_vector[left] and self._has_vector[right])
                result.append(
                    PhotoSimilarity(
                        left_position=self._photos[left].position,
                        right_position=self._photos[right].position,
                        hamming=int(np.bitwise_count(self._hashes[left] ^ self._hashes[right])),
                        cosine=round(float(self._vectors[left] @ self._vectors[right]), 4)
                        if both
                        else None,
                        document_frequency=max(self._frequency[left], self._frequency[right]),
                    )
                )
        return result

    # ---------------------------------------------------------------- helpers

    def _pair(self, row: int, col: int) -> PairKey | None:
        a, b = self._listing_of[row], self._listing_of[col]
        return None if a == b else PairKey.of(a, b)

    def _document_frequencies(self) -> list[int]:
        """How many listings show a near-identical copy of each photo (union-find over copies)."""
        parent = list(range(len(self._photos)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(a: int, b: int) -> None:
            parent[find(a)] = find(b)

        for start in range(0, len(self._photos), _CHUNK):
            block = self._hashes[start : start + _CHUNK]
            rows, cols = np.nonzero(
                np.bitwise_count(block[:, None] ^ self._hashes[None, :]) <= STRONG_HAMMING
            )
            for row, col in zip(rows + start, cols, strict=True):
                union(int(row), int(col))
            if self._vectors.shape[1]:
                sims = self._vectors[start : start + _CHUNK] @ self._vectors.T
                rows, cols = np.nonzero(sims >= STRONG_COSINE)
                for row, col in zip(rows + start, cols, strict=True):
                    if self._has_vector[row] and self._has_vector[col]:
                        union(int(row), int(col))
        listings_per_group: dict[int, set[ListingId]] = defaultdict(set)
        for index, listing in enumerate(self._listing_of):
            listings_per_group[find(index)].add(listing)
        return [len(listings_per_group[find(index)]) for index in range(len(self._photos))]
