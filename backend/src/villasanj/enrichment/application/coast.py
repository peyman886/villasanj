"""Distance from every listing to the Caspian coastline (M9 evidence, ADR-0013; zero network).

The coastline is OSM's ``natural=coastline`` from a dated Geofabrik snapshot, stored in PostGIS.
Each listing gets the distance from its published pin and the exact range over its blur circle.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.domain.geo import Blur
from villasanj.shared.application.clock import Clock
from villasanj.shared.domain.geo import GeoPoint

MAX_COAST_M = 100_000.0  # farther than this: not a coastal listing, nothing is stored


class CoastlineIndex(Protocol):
    async def distances_m(self, points: Sequence[GeoPoint], max_m: float) -> list[float | None]:
        """Distance from each point to the nearest coastline, ``None`` beyond ``max_m``."""
        ...


@dataclass(frozen=True, slots=True)
class CoastDistance:
    listing_id: ListingId
    dataset: str  # the OSM snapshot, e.g. "iran-260930"
    center_m: float
    low_m: float
    high_m: float
    blur: Blur
    computed_at: datetime


class CoastDistanceStore(Protocol):
    async def replace(self, platform: str, rows: Sequence[CoastDistance]) -> None: ...

    async def of_platform(self, platform: str) -> dict[ListingId, CoastDistance]: ...


@dataclass(frozen=True, slots=True)
class CoastReport:
    platform: str
    listings: int
    with_location: int
    measured: int
    radius_assumed: int


class MeasureCoastDistances:
    def __init__(
        self,
        listings: ListingReader,
        coast: CoastlineIndex,
        store: CoastDistanceStore,
        clock: Clock,
        dataset: str,
    ) -> None:
        self._listings = listings
        self._coast = coast
        self._store = store
        self._clock = clock
        self._dataset = dataset

    async def run(self, platform: str) -> CoastReport:
        listings = await self._listings.listings(platform)
        located = [(x, x.location) for x in listings if x.location is not None]
        distances = await self._coast.distances_m([loc.point for _, loc in located], MAX_COAST_M)
        now = self._clock.now()
        rows = []
        for (listing, location), center in zip(located, distances, strict=True):
            if center is None:
                continue
            blur = Blur.of(location.radius_m)
            low, high = blur.distance_range(center)
            rows.append(CoastDistance(listing.id, self._dataset, center, low, high, blur, now))
        await self._store.replace(platform, rows)
        return CoastReport(
            platform, len(listings), len(located), len(rows), sum(r.blur.assumed for r in rows)
        )
