"""Candidate pairs: two listings that might be the same real villa, and why we looked at them."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from villasanj.catalog.domain.listing import ListingId


class BlockingSource(StrEnum):
    GEO_ROOMS = "geo_rooms"  # published locations close, bedrooms within one
    PHOTO_HASH = "photo_hash"  # a near-identical photo (pHash)
    PHOTO_EMBEDDING = "photo_embedding"  # a visually close photo (image embedding)
    SAME_PLATFORM_PHOTOS = "same_platform_photos"  # complex units / duplicates on one platform
    WIDE = "wide"  # loose net used only to estimate blocking recall


@dataclass(frozen=True, slots=True, order=True)
class PairKey:
    """Unordered pair in canonical order, so (a, b) and (b, a) are the same pair."""

    left: ListingId
    right: ListingId

    def __post_init__(self) -> None:
        if not self.left < self.right:
            raise ValueError(f"pair must be in canonical order: {self.left} < {self.right}")

    @classmethod
    def of(cls, a: ListingId, b: ListingId) -> PairKey:
        if a == b:
            raise ValueError(f"a listing cannot pair with itself: {a}")
        return cls(a, b) if a < b else cls(b, a)

    @property
    def cross_platform(self) -> bool:
        return self.left.platform != self.right.platform

    def __str__(self) -> str:
        return f"{self.left}|{self.right}"

    @classmethod
    def parse(cls, text: str) -> PairKey:
        left, right = (ListingId(*part.split(":", 1)) for part in text.split("|", 1))
        return cls.of(left, right)


@dataclass(frozen=True, slots=True)
class CandidatePair:
    key: PairKey
    sources: frozenset[BlockingSource]
