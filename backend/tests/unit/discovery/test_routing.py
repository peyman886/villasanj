"""Drive times: the pin and its circle are routed, the range is min..max, no route is no time."""

import json
from collections.abc import Sequence
from pathlib import Path

import httpx
import pytest

from tests.fakes.er import ListingsFake
from tests.fakes.llm import FixedClock
from tests.unit.catalog.test_reports import listing
from villasanj.catalog.domain.listing import ListingId
from villasanj.discovery.application.routing import (
    ComputeDriveTimes,
    DriveTime,
    Leg,
    Origin,
)
from villasanj.discovery.infrastructure.routing import TABLE_BATCH, OsrmRoutingService, load_origin
from villasanj.enrichment.domain.geo import CIRCLE_POINTS
from villasanj.shared.application.errors import ConfigurationError
from villasanj.shared.domain.geo import GeoPoint

ORIGIN = Origin("tehran", "تهران", GeoPoint(35.7, 51.34), "test")


class Routing:
    """Routes everything east of 50.6 in proportion to longitude; nothing west of it."""

    async def legs(self, origin: GeoPoint, destinations: Sequence[GeoPoint]) -> list[Leg | None]:
        return [Leg(p.lon * 100, p.lon * 1000) if p.lon > 50.6 else None for p in destinations]


class Store:
    def __init__(self) -> None:
        self.rows: list[DriveTime] = []

    async def replace(self, platform: str, origin: str, rows: Sequence[DriveTime]) -> None:
        self.rows = list(rows)

    async def of_platform(self, platform: str, origin: str) -> dict[ListingId, DriveTime]:
        return {r.listing_id: r for r in self.rows}


async def test_the_range_covers_the_circle_and_unroutable_listings_get_no_time() -> None:
    listings = ListingsFake(
        [
            listing("east", location=GeoPoint(36.9, 50.7), location_radius_m=400),
            listing("west", location=GeoPoint(36.9, 50.4), location_radius_m=400),
            listing("nowhere", location=None),
        ]
    )
    store = Store()
    report = await ComputeDriveTimes(listings, Routing(), store, FixedClock(), ORIGIN, "osm-1").run(
        "p"
    )
    assert (report.listings, report.with_location, report.routed) == (3, 2, 1)
    east, west = sorted(store.rows, key=lambda r: r.listing_id.external_id)
    assert east.routed_points == CIRCLE_POINTS + 1
    assert east.center == Leg(50.7 * 100, 50.7 * 1000)
    assert east.low_s is not None
    assert east.high_s is not None
    assert east.low_s < east.center.seconds < east.high_s  # points west and east of the pin
    assert (west.center, west.low_s, west.high_s, west.routed_points) == (None, None, None, 0)
    assert not east.blur.assumed


async def test_osrm_table_requests_are_batched_and_nulls_become_no_route() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        assert request.url.params["sources"] == "0"
        count = request.url.path.rsplit("/", 1)[-1].count(";")
        durations = [[0.0, *([None] + [60.0] * (count - 1))]]
        distances = [[0.0, *([None] + [900.0] * (count - 1))]]
        return httpx.Response(
            200, json={"code": "Ok", "durations": durations, "distances": distances}
        )

    service = OsrmRoutingService("http://osrm.test", transport=httpx.MockTransport(handler))
    points = [GeoPoint(36.9, 50.7)] * (TABLE_BATCH + 2)
    legs = await service.legs(ORIGIN.point, points)
    assert len(seen) == 2
    assert len(legs) == len(points)
    assert legs[0] is None
    assert legs[1] == Leg(60.0, 900.0)
    assert seen[0].startswith("/table/v1/driving/51.340000,35.700000;50.700000,36.900000")


async def test_an_osrm_error_is_raised_not_hidden() -> None:
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, json={"code": "InvalidQuery", "message": "x"})
    )
    service = OsrmRoutingService("http://osrm.test", transport=transport)
    with pytest.raises(RuntimeError, match="InvalidQuery"):
        await service.legs(ORIGIN.point, [GeoPoint(36.9, 50.7)])


def test_the_project_origin_loads(tmp_path: Path) -> None:
    origin = load_origin(Path(__file__).parents[4] / "config" / "routing.toml")
    assert origin.slug == "tehran-azadi"
    broken = tmp_path / "routing.toml"
    broken.write_text(json.dumps({}), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_origin(broken)
