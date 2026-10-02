"""Distance from every listing to the nearest mapped place of each kind (M9 evidence; zero
network). Places come from the same dated OSM snapshot as the coastline (ADR-0013); each listing
gets the distance from its pin and the range over its blur circle, as for the coast.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.domain.geo import Blur
from villasanj.enrichment.domain.places import PlaceKind
from villasanj.shared.application.clock import Clock
from villasanj.shared.domain.geo import GeoPoint

MAX_PLACE_M = 30_000.0  # farther than this, nothing is stored: no claim names a place that far


@dataclass(frozen=True, slots=True)
class Nearest:
    distance_m: float
    name: str | None  # e.g. the town whose centre it is


class PlaceIndex(Protocol):
    async def nearest(
        self, points: Sequence[GeoPoint], kind: PlaceKind, max_m: float
    ) -> list[Nearest | None]:
        """The nearest mapped place of ``kind`` to each point, ``None`` beyond ``max_m``."""
        ...


@dataclass(frozen=True, slots=True)
class PlaceDistance:
    listing_id: ListingId
    kind: PlaceKind
    dataset: str
    center_m: float
    low_m: float
    high_m: float
    blur: Blur
    nearest_name: str | None
    computed_at: datetime


class PlaceDistanceStore(Protocol):
    async def replace(self, platform: str, rows: Sequence[PlaceDistance]) -> None: ...

    async def get(self, listing_id: ListingId) -> dict[PlaceKind, PlaceDistance]: ...

    async def of_platform(
        self, platform: str
    ) -> dict[ListingId, dict[PlaceKind, PlaceDistance]]: ...


@dataclass(slots=True)
class PlaceReport:
    platform: str
    with_location: int = 0
    measured: Counter[str] = field(default_factory=Counter)  # kind -> listings with a distance


class MeasurePlaceDistances:
    def __init__(
        self,
        listings: ListingReader,
        places: PlaceIndex,
        store: PlaceDistanceStore,
        clock: Clock,
        dataset: str,
    ) -> None:
        self._listings = listings
        self._places = places
        self._store = store
        self._clock = clock
        self._dataset = dataset

    async def run(self, platform: str) -> PlaceReport:
        located = [(x, x.location) for x in await self._listings.listings(platform) if x.location]
        points = [location.point for _, location in located]
        report = PlaceReport(platform, len(located))
        now = self._clock.now()
        rows = []
        for kind in PlaceKind:
            found = await self._places.nearest(points, kind, MAX_PLACE_M)
            for (listing, location), nearest in zip(located, found, strict=True):
                if nearest is None:
                    continue
                blur = Blur.of(location.radius_m)
                low, high = blur.distance_range(nearest.distance_m)
                rows.append(
                    PlaceDistance(
                        listing.id,
                        kind,
                        self._dataset,
                        nearest.distance_m,
                        low,
                        high,
                        blur,
                        nearest.name,
                        now,
                    )
                )
                report.measured[kind.value] += 1
        await self._store.replace(platform, rows)
        return report
