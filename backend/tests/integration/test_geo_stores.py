"""PostGIS coastline distances and the geo evidence stores against a real Postgres."""

import json

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fakes.llm import NOW
from villasanj.catalog.domain.listing import ListingId
from villasanj.discovery.application.routing import DriveTime, Leg
from villasanj.discovery.infrastructure.routing import PgDriveTimeStore
from villasanj.enrichment.application.coast import CoastDistance
from villasanj.enrichment.domain.geo import Blur
from villasanj.enrichment.infrastructure.coast import PgCoastDistanceStore, PgCoastline
from villasanj.shared.domain.geo import GeoPoint

pytestmark = pytest.mark.integration

# An east-west "coast" along latitude 37.0. Dense vertices, like real coastline ways: between two
# far-apart vertices a geography line is a great-circle arc and bulges away from the parallel.
LINE: dict[str, object] = {
    "type": "LineString",
    "coordinates": [[50.0 + i / 100, 37.0] for i in range(101)],
}


def feature(way: str, geometry: dict[str, object]) -> str:
    return "\x1e" + json.dumps(
        {"type": "Feature", "id": way, "geometry": geometry, "properties": {}}
    )


async def test_coast_distances_come_from_the_loaded_lines(engine: AsyncEngine) -> None:
    coast = PgCoastline(engine, f"test-{id(engine)}")
    loaded = await coast.load(
        [
            feature("w1", LINE),
            feature("n2", {"type": "Point", "coordinates": [50.5, 37.0]}),  # not a way: skipped
            "",
        ]
    )
    assert loaded == 1
    near, far = await coast.distances_m([GeoPoint(36.99, 50.5), GeoPoint(35.7, 51.4)], 50_000)
    assert near is not None
    assert near == pytest.approx(1110, rel=0.01)  # 0.01 degree of latitude
    assert far is None  # beyond the window
    assert await PgCoastline(engine, "other-dataset").distances_m(
        [GeoPoint(36.99, 50.5)], 50_000
    ) == [None]


async def test_coast_distances_and_drive_times_are_replaced_per_platform(
    engine: AsyncEngine,
) -> None:
    platform = f"geo-{id(engine)}"
    listing = ListingId(platform, "1")
    coast = PgCoastDistanceStore(engine)
    row = CoastDistance(listing, "osm-1", 1000.0, 600.0, 1400.0, Blur(400, False), NOW)
    await coast.replace(platform, [row])
    await coast.replace(platform, [row])  # replacing twice keeps one row
    assert await coast.of_platform(platform) == {listing: row}
    drives = PgDriveTimeStore(engine)
    routed = DriveTime(
        listing,
        "tehran",
        "osm-1",
        Leg(15600.0, 217000.0),
        15500.0,
        15800.0,
        9,
        Blur(500, True),
        NOW,
    )
    unroutable = DriveTime(
        ListingId(platform, "2"), "tehran", "osm-1", None, None, None, 0, Blur(400, False), NOW
    )
    await drives.replace(platform, "tehran", [routed, unroutable])
    stored = await drives.of_platform(platform, "tehran")
    assert stored == {listing: routed, unroutable.listing_id: unroutable}
    assert await drives.of_platform(platform, "elsewhere") == {}
