"""Geographic value objects."""

from __future__ import annotations

import math
from dataclasses import dataclass

from villasanj.shared.domain.errors import InvalidGeoPoint

EARTH_RADIUS_M = 6_371_008.8  # mean Earth radius (IUGG)
MAX_LATITUDE = 90.0
MAX_LONGITUDE = 180.0


@dataclass(frozen=True, slots=True)
class GeoPoint:
    """A WGS84 coordinate."""

    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not (math.isfinite(self.lat) and math.isfinite(self.lon)):
            raise InvalidGeoPoint("coordinates must be finite numbers")
        if abs(self.lat) > MAX_LATITUDE or abs(self.lon) > MAX_LONGITUDE:
            raise InvalidGeoPoint(f"coordinates out of range: ({self.lat}, {self.lon})")

    def distance_m(self, other: GeoPoint) -> float:
        """Great-circle (haversine) distance in metres."""
        lat1, lat2 = math.radians(self.lat), math.radians(other.lat)
        d_lat = lat2 - lat1
        d_lon = math.radians(other.lon - self.lon)
        h = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
        return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))

    def offset(self, bearing_deg: float, distance_m: float) -> GeoPoint:
        """The point ``distance_m`` away along ``bearing_deg`` (0 = north, 90 = east)."""
        angular = distance_m / EARTH_RADIUS_M
        bearing = math.radians(bearing_deg)
        lat1, lon1 = math.radians(self.lat), math.radians(self.lon)
        lat2 = math.asin(
            math.sin(lat1) * math.cos(angular)
            + math.cos(lat1) * math.sin(angular) * math.cos(bearing)
        )
        lon2 = lon1 + math.atan2(
            math.sin(bearing) * math.sin(angular) * math.cos(lat1),
            math.cos(angular) - math.sin(lat1) * math.sin(lat2),
        )
        return GeoPoint(math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180)
