"""Evidence that two listings are the same villa, computed deterministically (ADR-0009 stage 2).

Photos are the strongest signal, but a photo shared by many listings (a complex's marketing shots,
a stock sea view) says little, so each matched photo is weighted by 1 / document frequency.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from villasanj.catalog.domain.listing import Listing

# Photo pair thresholds (pHash Hamming bits / embedding cosine). Calibrated on the M3 benchmark
# (docs/adr/0012) and reviewed against the gold set.
STRONG_HAMMING = 6
WEAK_HAMMING = 10
STRONG_COSINE = 0.92
WEAK_COSINE = 0.85
WEAK_WEIGHT = 0.5
TRIGRAM = 3


@dataclass(frozen=True, slots=True)
class PhotoSimilarity:
    """One photo of each listing, compared. Missing measures are ``None``."""

    left_position: int
    right_position: int
    hamming: int | None
    cosine: float | None
    document_frequency: int  # listings sharing a near-identical photo (>= 1)

    @property
    def strength(self) -> float:
        """1 for a near-identical photo, 0.5 for a close one, 0 otherwise."""
        if (self.hamming is not None and self.hamming <= STRONG_HAMMING) or (
            self.cosine is not None and self.cosine >= STRONG_COSINE
        ):
            return 1.0
        if (self.hamming is not None and self.hamming <= WEAK_HAMMING) or (
            self.cosine is not None and self.cosine >= WEAK_COSINE
        ):
            return WEAK_WEIGHT
        return 0.0


@dataclass(frozen=True, slots=True)
class PhotoEvidence:
    compared_left: int  # photos available on each side
    compared_right: int
    strong_matches: int
    weak_matches: int
    weighted_matches: float  # sum of strength / document frequency over a one-to-one matching
    best_cosine: float | None
    best_hamming: int | None


def photo_evidence(
    similarities: Iterable[PhotoSimilarity], left_photos: int, right_photos: int
) -> PhotoEvidence:
    """Greedy one-to-one matching, strongest first: each photo counts at most once."""
    pairs = list(similarities)
    ranked = sorted(
        (p for p in pairs if p.strength > 0),
        key=lambda p: (-p.strength, -(p.cosine or 0.0), p.hamming if p.hamming is not None else 64),
    )
    used_left: set[int] = set()
    used_right: set[int] = set()
    strong = weak = 0
    weighted = 0.0
    for pair in ranked:
        if pair.left_position in used_left or pair.right_position in used_right:
            continue
        used_left.add(pair.left_position)
        used_right.add(pair.right_position)
        if pair.strength == 1.0:
            strong += 1
        else:
            weak += 1
        weighted += pair.strength / max(1, pair.document_frequency)
    cosines = [p.cosine for p in pairs if p.cosine is not None]
    hammings = [p.hamming for p in pairs if p.hamming is not None]
    return PhotoEvidence(
        compared_left=left_photos,
        compared_right=right_photos,
        strong_matches=strong,
        weak_matches=weak,
        weighted_matches=round(weighted, 4),
        best_cosine=round(max(cosines), 4) if cosines else None,
        best_hamming=min(hammings) if hammings else None,
    )


@dataclass(frozen=True, slots=True)
class PairEvidence:
    photos: PhotoEvidence
    distance_min_m: float | None  # smallest possible distance given published radii
    bedrooms_diff: int | None
    bathrooms_diff: int | None
    capacity_diff: int | None  # maximum capacity
    area_ratio: float | None  # smaller / larger, in (0, 1]
    price_ratio: float | None  # base nightly price, larger / smaller, >= 1
    title_similarity: float  # Jaccard of character trigrams on normalized titles


def pair_evidence(left: Listing, right: Listing, photos: PhotoEvidence) -> PairEvidence:
    return PairEvidence(
        photos=photos,
        distance_min_m=distance_min_m(left, right),
        bedrooms_diff=_diff(left.bedrooms, right.bedrooms),
        bathrooms_diff=_diff(left.bathrooms, right.bathrooms),
        capacity_diff=_diff(left.max_capacity, right.max_capacity),
        area_ratio=_ratio(left.area_m2, right.area_m2, smaller_over_larger=True),
        price_ratio=_ratio(
            left.rate_card.base.amount_rial if left.rate_card.base else None,
            right.rate_card.base.amount_rial if right.rate_card.base else None,
            smaller_over_larger=False,
        ),
        title_similarity=round(
            _jaccard(_trigrams(left.title_norm), _trigrams(right.title_norm)), 4
        ),
    )


def distance_min_m(left: Listing, right: Listing) -> float | None:
    """Lower bound of the true distance. A missing radius is read as an exact pin (shab)."""
    if left.location is None or right.location is None:
        return None
    centre = left.location.point.distance_m(right.location.point)
    slack = (left.location.radius_m or 0) + (right.location.radius_m or 0)
    return round(max(0.0, centre - slack), 1)


def _diff(a: int | None, b: int | None) -> int | None:
    return None if a is None or b is None else abs(a - b)


def _ratio(a: int | None, b: int | None, *, smaller_over_larger: bool) -> float | None:
    if not a or not b:
        return None
    low, high = sorted((a, b))
    return round(low / high if smaller_over_larger else high / low, 4)


def _trigrams(text: str) -> set[str]:
    compact = "".join(text.split())
    return {compact[i : i + TRIGRAM] for i in range(len(compact) - TRIGRAM + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0
