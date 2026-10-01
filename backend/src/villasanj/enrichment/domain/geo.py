"""Where a listing can be, given its published pin (ADR-0013).

A platform publishes a point and, sometimes, how far the villa may be from it. For evidence we
need the possible range of a measured quantity over that circle. For a distance to a fixed shape
(the coastline) the range is exact: any point within r of the pin is between d - r and d + r away.
When a platform publishes no radius, we assume one (``UNKNOWN_RADIUS_M``) and say so on every value
derived from it, rather than treating the pin as exact.
"""

from __future__ import annotations

from dataclasses import dataclass

from villasanj.shared.domain.geo import GeoPoint

UNKNOWN_RADIUS_M = 500  # jabama publishes 400 m; a pin without a stated radius gets a margin
CIRCLE_POINTS = 8  # sample points on the circle for quantities that are not distances (routing)


@dataclass(frozen=True, slots=True)
class Blur:
    radius_m: int
    assumed: bool  # True: the platform did not publish a radius

    @classmethod
    def of(cls, radius_m: int | None) -> Blur:
        if radius_m is None:
            return cls(UNKNOWN_RADIUS_M, assumed=True)
        return cls(radius_m, assumed=False)

    def distance_range(self, center_m: float) -> tuple[float, float]:
        """Nearest and farthest a point of the circle can be from a shape ``center_m`` away."""
        return max(0.0, center_m - self.radius_m), center_m + self.radius_m

    def samples(self, center: GeoPoint) -> list[GeoPoint]:
        """The pin and points around the circle, for an approximate range of any quantity."""
        if self.radius_m == 0:
            return [center]
        step = 360 / CIRCLE_POINTS
        return [center, *(center.offset(i * step, self.radius_m) for i in range(CIRCLE_POINTS))]
