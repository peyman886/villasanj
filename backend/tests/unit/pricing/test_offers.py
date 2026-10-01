"""Offers: age of the evidence, staleness, and the distribution per platform and scenario."""

from datetime import date, timedelta

from tests.fakes.ingestion import SteppingClock
from tests.fakes.llm import NOW
from tests.unit.pricing.test_quote import FINAL, ID, THU, ask, listing, night
from tests.unit.pricing.test_quotes_application import STAY, StaticReader
from villasanj.catalog.domain.listing import ListingId
from villasanj.ingestion.domain.parsed import Availability
from villasanj.pricing.application.offers import OfferBook
from villasanj.pricing.domain.offer import Offer
from villasanj.pricing.domain.quote import OfferKind, quote_stay
from villasanj.shared.domain.stay import GuestCount, StayScenario

FRI = date(2026, 10, 16)


def test_offer_age_is_the_age_of_its_oldest_observation() -> None:
    quote = quote_stay(listing(), [night(THU, age_hours=30), night(FRI, age_hours=2)], ask(), FINAL)
    fresh = Offer(quote, NOW)
    assert fresh.age == timedelta(hours=30)
    assert fresh.stale  # older than the 24 h default
    assert not Offer(quote, NOW, max_age=timedelta(hours=48)).stale
    assert fresh.kind is OfferKind.EXACT


async def test_offer_book_quotes_one_listing_and_flags_age() -> None:
    reader = StaticReader(listing(), [night(STAY.check_in), night(FRI)])
    clock = SteppingClock(NOW + timedelta(hours=25))
    offer = await OfferBook(reader, {"example": FINAL}, clock).offer(ID, ask())
    assert offer is not None
    assert offer.stale
    assert await OfferBook(reader, {}, clock).offer(ListingId("example", "0"), ask()) is None


async def test_distribution_counts_status_kind_and_staleness_per_group_size() -> None:
    reader = StaticReader(listing(), [night(STAY.check_in), night(FRI)])
    scenario = StayScenario("weekend", "آخر هفته", STAY, (GuestCount(4), GuestCount(8)))
    rows = await OfferBook(reader, {}, SteppingClock()).distribution(["example"], [scenario])
    four, eight = rows
    assert (four.guests, four.listings, four.by_status, four.by_kind) == (
        4,
        1,
        {"bookable": 1},
        {"open": 1},  # fees unknown without a policy
    )
    assert eight.by_status == {"too_many_guests": 1}
    assert eight.by_kind == {}
    assert four.stale == 0


async def test_unavailable_listings_count_as_their_status() -> None:
    reader = StaticReader(
        listing(), [night(STAY.check_in, availability=Availability.BOOKED), night(FRI)]
    )
    scenario = StayScenario("weekend", "آخر هفته", STAY, (GuestCount(4),))
    (row,) = await OfferBook(reader, {}, SteppingClock()).distribution(["example"], [scenario])
    assert row.by_status == {"unavailable": 1}


async def test_offers_quote_every_listing_of_a_platform_in_one_batch() -> None:
    reader = StaticReader(listing(), [night(STAY.check_in), night(FRI)])
    offers = await OfferBook(reader, {"example": FINAL}, SteppingClock()).offers("example", ask())
    assert list(offers) == [ID]
    assert offers[ID].kind is OfferKind.EXACT
