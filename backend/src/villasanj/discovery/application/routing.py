"""Free-flow drive times from an origin to every listing (ROADMAP M8 criterion 3, ADR-0013).

OSRM routes on a clipped OSM graph without traffic, so every time is labelled free-flow. A
listing's pin is blurred, so the pin and points around its circle are routed and the minimum and
maximum give the range shown ("۲:۴۰ تا ۲:۵۵"). Unroutable points (no road nearby) are left out;
a listing with no routable point has no drive time, never a guessed one.
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


@dataclass(frozen=True, slots=True)
class Leg:
    seconds: float
    meters: float


class RoutingService(Protocol):
    async def legs(self, origin: GeoPoint, destinations: Sequence[GeoPoint]) -> list[Leg | None]:
        """Free-flow car legs from ``origin`` to each destination (``None``: no route)."""
        ...


@dataclass(frozen=True, slots=True)
class Origin:
    slug: str
    name_fa: str
    point: GeoPoint
    source: str


@dataclass(frozen=True, slots=True)
class DriveTime:
    listing_id: ListingId
    origin: str
    dataset: str
    center: Leg | None  # the route to the published pin itself
    low_s: float | None
    high_s: float | None
    routed_points: int
    blur: Blur
    computed_at: datetime


class DriveTimeStore(Protocol):
    async def replace(self, platform: str, origin: str, rows: Sequence[DriveTime]) -> None: ...

    async def of_platform(self, platform: str, origin: str) -> dict[ListingId, DriveTime]: ...

    async def get(self, listing_id: ListingId, origin: str) -> DriveTime | None: ...


@dataclass(frozen=True, slots=True)
class RoutingReport:
    platform: str
    listings: int
    with_location: int
    routed: int  # at least one point of the circle has a route
    center_unroutable: int  # the pin itself has no route, but some point of the circle has


class ComputeDriveTimes:
    def __init__(
        self,
        listings: ListingReader,
        routing: RoutingService,
        store: DriveTimeStore,
        clock: Clock,
        origin: Origin,
        dataset: str,
    ) -> None:
        self._listings = listings
        self._routing = routing
        self._store = store
        self._clock = clock
        self._origin = origin
        self._dataset = dataset

    async def run(self, platform: str) -> RoutingReport:
        listings = await self._listings.listings(platform)
        located = [(x, x.location) for x in listings if x.location is not None]
        blurs = [Blur.of(location.radius_m) for _, location in located]
        samples = [
            blur.samples(location.point) for (_, location), blur in zip(located, blurs, strict=True)
        ]
        flat = [point for points in samples for point in points]
        legs = await self._routing.legs(self._origin.point, flat)
        now = self._clock.now()
        rows: list[DriveTime] = []
        position = 0
        for (listing, _), points, blur in zip(located, samples, blurs, strict=True):
            mine = legs[position : position + len(points)]
            position += len(points)
            routed = [leg.seconds for leg in mine if leg is not None]
            rows.append(
                DriveTime(
                    listing.id,
                    self._origin.slug,
                    self._dataset,
                    mine[0],
                    min(routed) if routed else None,
                    max(routed) if routed else None,
                    len(routed),
                    blur,
                    now,
                )
            )
        await self._store.replace(platform, self._origin.slug, rows)
        return RoutingReport(
            platform,
            len(listings),
            len(located),
            sum(r.routed_points > 0 for r in rows),
            sum(r.center is None and r.routed_points > 0 for r in rows),
        )
