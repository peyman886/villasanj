"""Places from OSM as truth-check evidence: an incomplete map supports, never contradicts."""

import pytest

from villasanj.catalog.domain.gazetteer import place_key
from villasanj.enrichment.domain.distance_claims import ClaimTarget, DistanceClaim, Unit, Verdict
from villasanj.enrichment.domain.places import PlaceKind, assess_place, kind_of
from villasanj.ingestion.domain.parsed import TravelMode

CITIES = {place_key("جواهرده")}


@pytest.mark.parametrize(
    ("tags", "kind"),
    [
        ({"shop": "supermarket"}, PlaceKind.SUPERMARKET),
        ({"shop": "convenience"}, PlaceKind.SUPERMARKET),
        ({"shop": "bakery"}, PlaceKind.BAKERY),
        ({"amenity": "fast_food"}, PlaceKind.RESTAURANT),
        ({"amenity": "clinic"}, PlaceKind.MEDICAL),
        ({"place": "town", "name": "رامسر"}, PlaceKind.CITY_CENTER),
        ({"place": "village", "name": "جواهرده"}, PlaceKind.CITY_CENTER),  # a platform's city
        ({"place": "village", "name": "لمتر"}, None),
        ({"natural": "wood"}, PlaceKind.FOREST),
        ({"shop": "clothes"}, None),
    ],
)
def test_osm_tags_map_to_the_kinds_claims_name(tags: dict[str, str], kind: PlaceKind) -> None:
    assert kind_of(tags, CITIES) is kind


def five_minutes_walk() -> DistanceClaim:
    # «۵ دقیقه پیاده» as parsed: up to 5 + 5 minutes (A15)
    return DistanceClaim(ClaimTarget.BAKERY, "نانوایی", TravelMode.WALK, Unit.MINUTES, 0, 10)


def test_a_partial_map_supports_but_never_contradicts() -> None:
    claim = five_minutes_walk()  # up to 10 min x 100 m/min = 1,000 m
    assert assess_place(claim, PlaceKind.BAKERY, (100.0, 900.0)).verdict is Verdict.SUPPORTED
    far = assess_place(claim, PlaceKind.BAKERY, (5_000.0, 5_800.0))
    assert far.verdict is Verdict.NOT_CONFIRMED  # an unmapped bakery may be next door
    more_than = DistanceClaim(ClaimTarget.BAKERY, "نانوایی", TravelMode.CAR, Unit.MINUTES, 30, None)
    assert assess_place(more_than, PlaceKind.BAKERY, (100.0, 900.0)).verdict is (
        Verdict.NOT_CONFIRMED
    )


def test_city_centres_are_complete_so_the_best_case_can_contradict() -> None:
    claim = DistanceClaim(ClaimTarget.CITY_CENTER, "مرکز شهر", TravelMode.WALK, Unit.MINUTES, 0, 10)
    far = assess_place(claim, PlaceKind.CITY_CENTER, (5_000.0, 5_800.0))
    assert far.verdict is Verdict.CONTRADICTED  # even 1.5 km nearer than the point: 3.5 km
    near = assess_place(claim, PlaceKind.CITY_CENTER, (1_600.0, 2_400.0))
    assert near.verdict is Verdict.SUPPORTED  # the centre reaches to within 900 m
    assert near.measured_m == (100.0, 900.0)


def test_names_compare_with_joiners_and_spaces_alike() -> None:
    assert place_key("کتالم و سادات\N{ZERO WIDTH NON-JOINER}شهر") == place_key("کتالم و سادات شهر")


async def test_every_located_listing_gets_its_nearest_place_of_each_kind() -> None:
    from collections.abc import Sequence

    from tests.fakes.er import ListingsFake
    from tests.fakes.llm import NOW, FixedClock
    from tests.unit.catalog.test_reports import listing
    from tests.unit.enrichment.test_truth import Places
    from villasanj.enrichment.application.places import MeasurePlaceDistances, Nearest
    from villasanj.shared.domain.geo import GeoPoint

    class Index:
        async def nearest(
            self, points: Sequence[GeoPoint], kind: PlaceKind, max_m: float
        ) -> list[Nearest | None]:
            if kind is PlaceKind.BAKERY:
                return [Nearest(1000.0, None) for _ in points]
            return [None for _ in points]  # nothing of that kind within max_m

    store = Places([])
    listings = ListingsFake([listing("1", location_radius_m=400), listing("2", location=None)])
    report = await MeasurePlaceDistances(listings, Index(), store, FixedClock(), "osm").run("p")
    assert (report.with_location, dict(report.measured)) == (1, {"bakery": 1})
    (row,) = store.rows
    assert (row.kind, row.low_m, row.high_m, row.computed_at) == (
        PlaceKind.BAKERY,
        600.0,
        1400.0,
        NOW,
    )
