"""Search filters and the map area: the shared cases the filter panel's live count also runs."""

import json
from pathlib import Path
from typing import Any

import pytest

from villasanj.discovery.domain.area import InvalidArea, MapArea
from villasanj.discovery.domain.filters import FacetRow, SearchFilters, passes, villas_passing
from villasanj.shared.domain.geo import GeoPoint

CASES = json.loads((Path(__file__).parents[2] / "fixtures" / "filter_cases.json").read_text())
ROWS = [FacetRow(**{**r, "features": frozenset(r["features"])}) for r in CASES["rows"]]


def filters_of(raw: dict[str, Any]) -> SearchFilters:
    sets = {"features", "property_types", "platforms"}
    values: dict[str, Any] = {k: frozenset(v) if k in sets else v for k, v in raw.items()}
    return SearchFilters(**values)


@pytest.mark.parametrize("case", CASES["cases"], ids=[c["name"] for c in CASES["cases"]])
def test_shared_filter_cases(case: dict[str, Any]) -> None:
    f = filters_of(case["filters"])
    assert [r.listing for r in ROWS if passes(r, f)] == case["listings"]
    assert villas_passing(ROWS, f) == case["villas"]


def test_no_filter_is_empty() -> None:
    assert SearchFilters().empty
    assert not SearchFilters(instant=True).empty


def test_a_map_area_keeps_published_points_inside_it() -> None:
    area = MapArea(west=50.5, south=36.8, east=50.8, north=37.0)
    assert area.contains(GeoPoint(36.9, 50.66))
    assert not area.contains(GeoPoint(36.7, 50.66))
    with pytest.raises(InvalidArea):
        MapArea(west=50.8, south=36.8, east=50.5, north=37.0)
