"""The map area a search is narrowed to (the map's "search this area", M12 3.2)."""

from __future__ import annotations

from dataclasses import dataclass

from villasanj.shared.domain.errors import DomainError
from villasanj.shared.domain.geo import GeoPoint

MAX_LON, MAX_LAT = 180.0, 90.0


class InvalidArea(DomainError):
    pass


@dataclass(frozen=True, slots=True)
class MapArea:
    """A latitude/longitude box, as the map's visible bounds."""

    west: float
    south: float
    east: float
    north: float

    def __post_init__(self) -> None:
        lon_ok = -MAX_LON <= self.west < self.east <= MAX_LON
        if not (lon_ok and -MAX_LAT <= self.south < self.north <= MAX_LAT):
            raise InvalidArea("need west < east and south < north, in degrees")

    def contains(self, point: GeoPoint) -> bool:
        """Whether the listing's published point is inside (the point is all we know)."""
        return self.west <= point.lon <= self.east and self.south <= point.lat <= self.north
