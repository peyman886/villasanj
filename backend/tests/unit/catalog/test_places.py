"""Measuring how many listings the gazetteer places."""

from villasanj.catalog.application.places import MeasurePlaceResolution, PlaceNames
from villasanj.catalog.domain.gazetteer import Gazetteer, Place, PlaceKind

GAZETTEER = Gazetteer(
    [
        Place("ramsar", "رامسر", PlaceKind.CITY),
        Place("shirud", "شیرود", PlaceKind.CITY),
        Place("sefid-tameshk", "سفیدتمشک", PlaceKind.LOCALITY, parent="ramsar"),
    ]
)


class StaticNames:
    def __init__(self, rows: list[PlaceNames]) -> None:
        self.rows = rows

    async def names(self, platform: str) -> list[PlaceNames]:
        return self.rows


async def test_counts_locality_city_and_unresolved_listings() -> None:
    query = StaticNames(
        [
            PlaceNames("رامسر", "سفید تمشک", 5),
            PlaceNames("رامسر", "شیرود", 2),  # locality text that names a city
            PlaceNames("رامسر", "بلوار معلم", 3),  # street: city level only
            PlaceNames("رامسر", None, 4),
            PlaceNames(None, "میدان شهید رجایی", 1),  # nothing known
        ]
    )
    result = await MeasurePlaceResolution(query, GAZETTEER, top=2).run("p")
    assert (result.listings, result.with_locality_text) == (15, 11)
    assert (result.locality_resolved, result.city_resolved, result.unresolved) == (5, 9, 1)
    assert result.top_unresolved == (("بلوار معلم", 3), ("میدان شهید رجایی", 1))
