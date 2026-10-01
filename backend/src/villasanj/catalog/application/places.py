"""How many listings the gazetteer can place (the input to locality-based ER blocking)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Protocol

from villasanj.catalog.domain.gazetteer import Gazetteer, PlaceKind


@dataclass(frozen=True, slots=True)
class PlaceNames:
    """One distinct (city, locality) text pair as a platform published it."""

    city_fa: str | None
    locality_fa: str | None
    listings: int


class PlaceNameQuery(Protocol):
    async def names(self, platform: str) -> list[PlaceNames]: ...


@dataclass(frozen=True, slots=True)
class PlaceResolution:
    platform: str
    listings: int
    with_locality_text: int
    locality_resolved: int  # the locality text names a known locality
    city_resolved: int  # placed at city level only (no locality text, or it names a city)
    unresolved: int
    top_unresolved: tuple[tuple[str, int], ...]


class MeasurePlaceResolution:
    def __init__(self, query: PlaceNameQuery, gazetteer: Gazetteer, top: int = 10) -> None:
        self._query = query
        self._gazetteer = gazetteer
        self._top = top

    async def run(self, platform: str) -> PlaceResolution:
        counts: Counter[str] = Counter()
        unresolved: Counter[str] = Counter()
        for row in await self._query.names(platform):
            counts["listings"] += row.listings
            if row.locality_fa:
                counts["with_locality_text"] += row.listings
            locality = self._gazetteer.resolve(row.locality_fa)
            if locality is not None and locality.kind is PlaceKind.LOCALITY:
                counts["locality"] += row.listings
            elif locality is not None or self._gazetteer.resolve(row.city_fa) is not None:
                counts["city"] += row.listings
            else:
                counts["unresolved"] += row.listings
            if row.locality_fa and locality is None:
                unresolved[row.locality_fa] += row.listings
        return PlaceResolution(
            platform=platform,
            listings=counts["listings"],
            with_locality_text=counts["with_locality_text"],
            locality_resolved=counts["locality"],
            city_resolved=counts["city"],
            unresolved=counts["unresolved"],
            top_unresolved=tuple(unresolved.most_common(self._top)),
        )
