"""Photo pipeline and regional inventory reports over scripted stats."""

from collections.abc import Sequence

from tests.fakes.er import ListingsFake
from tests.fakes.ingestion import REGION
from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from villasanj.catalog.application.reports import (
    PhotoCounts,
    PhotoPipelineReport,
    RegionalInventory,
)
from villasanj.catalog.domain.listing import Listing
from villasanj.ingestion.application.stats import (
    HostTraffic,
    KindProgress,
    ResponseTotals,
    RunSummary,
)
from villasanj.shared.domain.geo import GeoPoint


class Stats:
    async def traffic(self) -> list[HostTraffic]:
        return []

    async def progress(self) -> list[KindProgress]:
        return [
            KindProgress("p", "photo", {"done": 7, "pending": 2, "failed": 1}, {"http-404": 1}),
            KindProgress("p", "listing", {"done": 3}),
        ]

    async def responses(self, kinds: Sequence[str]) -> list[ResponseTotals]:
        rows = {
            "photo": ResponseTotals("p", "photo", {200: 6, 404: 1}, 4_000_000),
            "listing": ResponseTotals("p", "listing", {200: 2, 404: 1}, 900),
        }
        return [rows[k] for k in kinds]

    async def runs(self, limit: int) -> list[RunSummary]:
        return []


class Counts:
    async def counts(self, model_id: str) -> list[PhotoCounts]:
        return [PhotoCounts("p", 3, 40, 6, 5, 5)]


async def test_photo_report_explains_every_selected_photo() -> None:
    (row,) = await PhotoPipelineReport(Stats(), Counts()).run("model@1")
    assert (row.selected, row.downloaded, row.unfinished, row.failed_or_skipped) == (10, 6, 2, 1)
    assert row.failed_responses == {404: 1}
    assert row.coverage == (6 + 1 + 1) / 10  # downloaded, a logged 404, one given up
    assert row.reasons == {"http-404": 1}
    assert row.stored_bytes == 4_000_000


def listing(external_id: str, **overrides: object) -> Listing:
    values: dict[str, object] = {"platform": "p", "external_id": external_id}
    values.update(overrides)
    return Listing.from_parsed(parsed(**values), "00000000-0000-0000-0000-000000000d01", NOW)


async def test_inventory_counts_discovered_fetched_parsed_and_in_region() -> None:
    listings = ListingsFake(
        [
            listing("1"),
            listing("2", location=GeoPoint(35.7, 51.4)),  # Tehran: outside the region
            listing("3", location=None, base_capacity=None),
        ]
    )
    (row,) = await RegionalInventory(Stats(), listings, REGION).run(["p"])
    assert (row.discovered, row.parsed, row.in_region) == (3, 3, 1)
    assert row.responses == {200: 2, 404: 1}
    assert (row.with_location, row.with_capacity, row.with_base_price) == (2, 2, 0)


async def test_platforms_without_any_crawl_have_empty_rows() -> None:
    class Nothing(Stats):
        async def progress(self) -> list[KindProgress]:
            return []

        async def responses(self, kinds: Sequence[str]) -> list[ResponseTotals]:
            return []

    (row,) = await RegionalInventory(Nothing(), ListingsFake([]), REGION).run(["p"])
    assert (row.discovered, row.parsed, row.responses) == (0, 0, {})
    (photos,) = await PhotoPipelineReport(Nothing(), Counts()).run("m")
    assert (photos.selected, photos.coverage, photos.stored_bytes) == (0, 0.0, 0)
