"""Search filters (M12): narrow the ranked results by what each listing states or was measured.

Filters never change a score or the order; they only keep or drop ranked listings, before one
listing per villa is chosen. Each filter reads one stored fact of the listing (its own offer's
lower bound, rooms, capacity, type, instant booking, rating, the features its amenity list,
description, photos or the map back, the measured distance to the sea, its platform, and whether
its villa is on more than one platform). Where a fact is a range (the distance to the sea over the
blur circle), the best case decides, as in the truth check: a filter never drops a listing that
could satisfy it. An unknown fact fails a filter that asks for it.

The same rules are implemented for the filter panel's live count in
``frontend/src/lib/filters.ts``; both run the shared cases in ``tests/fixtures/filter_cases.json``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class FacetRow:
    """One ranked listing as the filters see it."""

    listing: str  # "platform:id"
    villa: str  # the canonical villa id, or the listing id when the villa has one listing
    platform: str
    multi_platform: bool
    total_toman: int | None  # the offer's lower bound for the whole stay
    nights: int
    bedrooms: int | None
    max_capacity: int | None
    property_type: str | None
    instant: bool | None
    rating: float | None  # the platform's own average
    coast_low_m: float | None  # the best case over the blur circle
    features: frozenset[str] = frozenset()  # stated or measured as present


@dataclass(frozen=True, slots=True)
class SearchFilters:
    price_min: int | None = None  # toman, for ``basis``
    price_max: int | None = None
    per_night: bool = False  # the price bounds are per night, not for the whole stay
    bedrooms_min: int | None = None
    capacity_min: int | None = None
    features: frozenset[str] = field(default_factory=frozenset)
    property_types: frozenset[str] = field(default_factory=frozenset)
    platforms: frozenset[str] = field(default_factory=frozenset)
    multi_platform: bool = False
    instant: bool = False
    rating_min: float | None = None
    coast_max_m: float | None = None

    @property
    def empty(self) -> bool:
        return self == SearchFilters()


def _price(row: FacetRow, per_night: bool) -> float | None:
    if row.total_toman is None:
        return None
    return row.total_toman / max(1, row.nights) if per_night else float(row.total_toman)


def passes(row: FacetRow, f: SearchFilters) -> bool:
    """Whether a ranked listing stays under these filters."""
    price = _price(row, f.per_night)
    checks = (
        f.price_min is None or (price is not None and price >= f.price_min),
        f.price_max is None or (price is not None and price <= f.price_max),
        f.bedrooms_min is None or (row.bedrooms is not None and row.bedrooms >= f.bedrooms_min),
        f.capacity_min is None
        or (row.max_capacity is not None and row.max_capacity >= f.capacity_min),
        f.features <= row.features,
        not f.property_types or row.property_type in f.property_types,
        not f.platforms or row.platform in f.platforms,
        not f.multi_platform or row.multi_platform,
        not f.instant or row.instant is True,
        f.rating_min is None or (row.rating is not None and row.rating >= f.rating_min),
        f.coast_max_m is None or (row.coast_low_m is not None and row.coast_low_m <= f.coast_max_m),
    )
    return all(checks)


def villas_passing(rows: Iterable[FacetRow], f: SearchFilters) -> int:
    """How many villas would show (one card per villa)."""
    return len({row.villa for row in rows if passes(row, f)})
