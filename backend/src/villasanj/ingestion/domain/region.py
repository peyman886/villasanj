"""The geographic scope of a crawl."""

from __future__ import annotations

from dataclasses import dataclass

from villasanj.shared.domain.geo import GeoPoint


@dataclass(frozen=True, slots=True)
class Place:
    slug: str  # transliterated, stable (e.g. "ramsar")
    name_fa: str


@dataclass(frozen=True, slots=True)
class Region:
    slug: str
    name_fa: str
    places: tuple[Place, ...]
    south_west: GeoPoint
    north_east: GeoPoint

    def contains(self, point: GeoPoint) -> bool:
        return (
            self.south_west.lat <= point.lat <= self.north_east.lat
            and self.south_west.lon <= point.lon <= self.north_east.lon
        )

    def place(self, slug: str) -> Place | None:
        return next((p for p in self.places if p.slug == slug), None)
