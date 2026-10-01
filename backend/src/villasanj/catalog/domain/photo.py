"""Photos as matching evidence: perceptual fingerprints and their distance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from villasanj.catalog.domain.listing import ListingId

HASH_BITS = 64
_MASK = (1 << HASH_BITS) - 1


def hamming(a: int, b: int) -> int:
    """Number of differing bits between two 64-bit hashes (signed or unsigned)."""
    return ((a ^ b) & _MASK).bit_count()


@dataclass(frozen=True, slots=True)
class PerceptualFingerprint:
    phash: int  # 64-bit DCT hash: robust to resizing and recompression
    dhash: int  # 64-bit gradient hash: cheap second opinion
    width: int
    height: int

    def distance(self, other: PerceptualFingerprint) -> int:
        return hamming(self.phash, other.phash)


@dataclass(frozen=True, slots=True)
class ListingPhoto:
    listing_id: ListingId
    position: int
    url: str
    snapshot_id: str
    sha256: str
    fingerprint: PerceptualFingerprint
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class PhotoEmbedding:
    """An image's vector under one model. Keyed by image content, so identical photos on several
    listings are embedded once and never recomputed."""

    sha256: str
    model_id: str
    vector: tuple[float, ...]
