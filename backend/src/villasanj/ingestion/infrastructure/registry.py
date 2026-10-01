"""Discovery of source adapters (entry-point group ``villasanj.sources``) and region loading."""

from __future__ import annotations

import tomllib
from importlib.metadata import entry_points
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from villasanj.ingestion.application.ports import SourceAdapter
from villasanj.ingestion.domain.region import Place, Region
from villasanj.shared.application.errors import ConfigurationError
from villasanj.shared.domain.geo import GeoPoint

ENTRY_POINT_GROUP = "villasanj.sources"


def load_source_adapters() -> dict[str, SourceAdapter]:
    """Instantiate every registered adapter. Adding a platform = adding one entry point."""
    adapters: dict[str, SourceAdapter] = {}
    for entry in entry_points(group=ENTRY_POINT_GROUP):
        adapter: SourceAdapter = entry.load()()
        if adapter.profile.slug != entry.name:
            raise ConfigurationError(
                f"entry point {entry.name!r} provides adapter {adapter.profile.slug!r}"
            )
        adapters[entry.name] = adapter
    return adapters


class _Point(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lat: float
    lon: float


class _PlaceFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str
    name_fa: str


class _RegionFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str
    name_fa: str
    south_west: _Point
    north_east: _Point
    places: list[_PlaceFile]


def load_region(path: Path) -> Region:
    try:
        with path.open("rb") as handle:
            data = _RegionFile.model_validate(tomllib.load(handle))
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        raise ConfigurationError(f"invalid region file {path}: {error}") from None
    return Region(
        slug=data.slug,
        name_fa=data.name_fa,
        places=tuple(Place(p.slug, p.name_fa) for p in data.places),
        south_west=GeoPoint(data.south_west.lat, data.south_west.lon),
        north_east=GeoPoint(data.north_east.lat, data.north_east.lon),
    )
