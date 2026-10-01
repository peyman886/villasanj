"""Ranges over a published pin's circle."""

import pytest

from villasanj.enrichment.domain.geo import CIRCLE_POINTS, UNKNOWN_RADIUS_M, Blur
from villasanj.shared.domain.geo import GeoPoint

RAMSAR = GeoPoint(36.9030, 50.6583)


def test_a_missing_radius_is_assumed_and_flagged() -> None:
    assert Blur.of(None) == Blur(UNKNOWN_RADIUS_M, assumed=True)
    assert Blur.of(400) == Blur(400, assumed=False)


def test_distance_ranges_are_exact_bounds_and_never_negative() -> None:
    assert Blur(400, False).distance_range(1000.0) == (600.0, 1400.0)
    assert Blur(400, False).distance_range(150.0) == (0.0, 550.0)


def test_samples_lie_on_the_circle() -> None:
    points = Blur(400, False).samples(RAMSAR)
    assert points[0] == RAMSAR
    assert len(points) == CIRCLE_POINTS + 1
    for point in points[1:]:
        assert RAMSAR.distance_m(point) == pytest.approx(400, abs=0.5)
    north = points[1]
    assert north.lat > RAMSAR.lat
    assert north.lon == pytest.approx(RAMSAR.lon)
    assert Blur(0, False).samples(RAMSAR) == [RAMSAR]


def test_offset_wraps_around_the_antimeridian() -> None:
    east = GeoPoint(0.0, 179.9999).offset(90, 1000)
    assert -180 <= east.lon < -179.99
