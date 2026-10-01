"""The sea truth check over stored listings and measured coast distances."""

from tests.fakes.er import ListingsFake
from tests.fakes.llm import NOW
from tests.unit.catalog.test_reports import listing
from tests.unit.enrichment.test_coast import Store
from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.coast import CoastDistance
from villasanj.enrichment.application.truth import CheckSeaClaims
from villasanj.enrichment.domain.geo import Blur
from villasanj.ingestion.domain.parsed import ParsedDistanceClaim, TravelMode


def sea(value: str, mode: TravelMode = TravelMode.WALK) -> tuple[ParsedDistanceClaim, ...]:
    return (ParsedDistanceClaim("فاصله از دریا", value, mode),)


async def test_verdicts_are_counted_per_listing_and_mode() -> None:
    listings = ListingsFake(
        [
            listing("near", distance_claims=sea("زیر 5 دقیقه")),
            listing("far", distance_claims=sea("زیر 5 دقیقه")),
            listing("unmeasured", distance_claims=sea("10 دقیقه", TravelMode.CAR)),
            listing("no-claim", distance_claims=()),
        ]
    )
    store = Store()
    store.rows = [
        CoastDistance(ListingId("p", "near"), "osm", 200.0, 0.0, 600.0, Blur(400, False), NOW),
        CoastDistance(ListingId("p", "far"), "osm", 5000.0, 4600.0, 5400.0, Blur(400, True), NOW),
    ]
    report = await CheckSeaClaims(listings, store).run("p")
    assert (report.listings_with_claim, report.without_distance) == (3, 1)
    assert report.listings_contradicted == 1
    assert report.verdicts == {"not_confirmed": 1, "contradicted": 1}  # 600 m may exceed 500 m
    assert report.verdicts_with_assumed_radius == {"contradicted": 1}
    assert report.by_mode == {"walk:not_confirmed": 1, "walk:contradicted": 1}
    (example,) = report.contradicted
    assert example.listing_id == ListingId("p", "far")
