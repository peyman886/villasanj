"""Parser coverage over stored listings."""

from tests.fakes.er import ListingsFake
from tests.unit.catalog.test_reports import listing
from villasanj.enrichment.application.claims import MeasureClaimParsing
from villasanj.ingestion.domain.parsed import ParsedDistanceClaim, TravelMode


def claims(*items: tuple[str, str]) -> tuple[ParsedDistanceClaim, ...]:
    return tuple(ParsedDistanceClaim(t, v, TravelMode.WALK) for t, v in items)


async def test_coverage_counts_parsed_claims_and_lists_what_was_not_understood() -> None:
    listings = ListingsFake(
        [
            listing(
                "1", distance_claims=claims(("دریا", "زیر 5 دقیقه"), ("تله کابین", "۱۰ دقیقه"))
            ),
            listing("2", distance_claims=claims(("جنگل", "نزدیک"), ("دریا", "نزدیک"))),
            listing("3", distance_claims=()),
        ]
    )
    report = await MeasureClaimParsing(listings).run("p")
    assert (report.listings, report.with_claims, report.claims, report.parsed) == (3, 2, 4, 2)
    assert report.coverage == 0.5
    assert report.by_target == {"sea": 1, "other": 1}
    assert report.by_mode == {"walk": 2}
    assert report.top_unparsed == [("نزدیک", 2)]
    assert report.top_other_targets == [("تله کابین", 1)]


async def test_a_platform_without_listings_has_zero_coverage() -> None:
    report = await MeasureClaimParsing(ListingsFake([])).run("p")
    assert (report.claims, report.coverage) == (0, 0.0)
