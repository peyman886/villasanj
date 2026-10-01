"""Coast distances: the pin's distance and its exact range over the blur circle."""

from collections.abc import Sequence

from tests.fakes.er import ListingsFake
from tests.fakes.llm import FixedClock
from tests.unit.catalog.test_reports import listing
from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.coast import CoastDistance, MeasureCoastDistances
from villasanj.enrichment.domain.geo import UNKNOWN_RADIUS_M
from villasanj.shared.domain.geo import GeoPoint


class Coast:
    async def distances_m(self, points: Sequence[GeoPoint], max_m: float) -> list[float | None]:
        return [None if p.lat < 36 else (37.0 - p.lat) * 100_000 for p in points]


class Store:
    def __init__(self) -> None:
        self.rows: list[CoastDistance] = []

    async def replace(self, platform: str, rows: Sequence[CoastDistance]) -> None:
        self.rows = list(rows)

    async def of_platform(self, platform: str) -> dict[ListingId, CoastDistance]:
        return {r.listing_id: r for r in self.rows}


async def test_distances_get_their_circle_range_and_an_unknown_radius_is_flagged() -> None:
    listings = ListingsFake(
        [
            listing("blurred", location=GeoPoint(36.99, 50.7), location_radius_m=400),
            listing("no-radius", location=GeoPoint(36.98, 50.7), location_radius_m=None),
            listing("far", location=GeoPoint(35.7, 51.4), location_radius_m=400),
        ]
    )
    store = Store()
    report = await MeasureCoastDistances(listings, Coast(), store, FixedClock(), "osm-1").run("p")
    assert (report.with_location, report.measured, report.radius_assumed) == (3, 2, 1)
    by_id = {r.listing_id.external_id: r for r in store.rows}
    blurred = by_id["blurred"]
    assert round(blurred.center_m) == 1000
    assert (round(blurred.low_m), round(blurred.high_m)) == (600, 1400)
    assumed = by_id["no-radius"]
    assert assumed.blur.assumed
    assert round(assumed.high_m - assumed.center_m) == UNKNOWN_RADIUS_M
    assert "far" not in by_id  # beyond the coast window: nothing is stored
