"""Load the curated gazetteer from ``config/gazetteer.toml``."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from villasanj.catalog.domain.gazetteer import Gazetteer, Place, PlaceKind
from villasanj.shared.application.errors import ConfigurationError


class _PlaceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str
    name_fa: str
    kind: PlaceKind
    parent: str | None = None
    aliases: list[str] = []


class _GazetteerFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    places: list[_PlaceEntry]


def load_gazetteer(path: Path) -> Gazetteer:
    try:
        with path.open("rb") as handle:
            data = _GazetteerFile.model_validate(tomllib.load(handle))
        places = [
            Place(e.slug, e.name_fa, e.kind, e.parent, frozenset(e.aliases)) for e in data.places
        ]
        _check_references(places)
        return Gazetteer(places)
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        raise ConfigurationError(f"invalid gazetteer file {path}: {error}") from None


def _check_references(places: list[Place]) -> None:
    kinds: dict[str, PlaceKind] = {}
    for place in places:
        if place.slug in kinds:
            raise ValueError(f"duplicate slug {place.slug!r}")
        kinds[place.slug] = place.kind
    for place in places:
        if place.parent is not None and kinds.get(place.parent) is not PlaceKind.CITY:
            raise ValueError(f"{place.slug!r} has parent {place.parent!r}, which is not a city")
