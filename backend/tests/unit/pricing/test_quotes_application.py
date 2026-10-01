"""QuoteStays: reading the catalog and choosing the fee policy."""

from datetime import date
from pathlib import Path

import pytest

from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from tests.unit.pricing.test_quote import SNAPSHOT, night
from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.pricing.application.quotes import QuoteStays
from villasanj.pricing.domain.quote import Caveat, FeePolicy, QuoteStatus, StayRequest
from villasanj.pricing.infrastructure.fees_file import load_fee_policies
from villasanj.shared.application.errors import ConfigurationError
from villasanj.shared.domain.money import Money, MoneyRange
from villasanj.shared.domain.stay import DateRange, GuestCount, StayScenario

CONFIG = Path(__file__).resolve().parents[4] / "config" / "fees.toml"
STAY = DateRange(date(2026, 10, 15), date(2026, 10, 17))


class StaticReader:
    def __init__(self, listing: Listing, calendar: list[CalendarObservation]) -> None:
        self.listing = listing
        self.calendar_rows = calendar

    async def get(self, listing_id: ListingId) -> Listing | None:
        return self.listing if listing_id == self.listing.id else None

    async def listings(self, platform: str) -> list[Listing]:
        return [self.listing]

    async def calendar(self, listing_id: ListingId, stay: DateRange) -> list[CalendarObservation]:
        return [o for o in self.calendar_rows if stay.contains_night(o.night)]

    async def calendars(
        self, platform: str, stay: DateRange
    ) -> dict[ListingId, list[CalendarObservation]]:
        result: dict[ListingId, list[CalendarObservation]] = {}
        for listing_id in [x.id for x in await self.listings(platform)]:
            result[listing_id] = await self.calendar(listing_id, stay)
        return result


READER = StaticReader(
    Listing.from_parsed(parsed(), SNAPSHOT, NOW), [night(STAY.check_in), night(date(2026, 10, 16))]
)


async def test_quotes_use_the_platform_fee_policy() -> None:
    final = {"example": FeePolicy("example", True, "test")}
    quote = await QuoteStays(READER, final).quote(
        READER.listing.id, StayRequest(STAY, GuestCount(4))
    )
    assert quote is not None
    assert quote.total == MoneyRange.exact(Money.from_toman(2_000_000))


async def test_a_platform_without_a_policy_has_unknown_fees() -> None:
    quote = await QuoteStays(READER, {}).quote(READER.listing.id, StayRequest(STAY, GuestCount(4)))
    assert quote is not None
    assert Caveat.FEES_UNKNOWN in quote.caveats


async def test_unknown_listings_get_no_quote() -> None:
    request = StayRequest(STAY, GuestCount(4))
    assert await QuoteStays(READER, {}).quote(ListingId("example", "0"), request) is None


async def test_scenarios_are_quoted_for_every_group_size() -> None:
    scenario = StayScenario("weekend", "آخر هفته", STAY, (GuestCount(4), GuestCount(8)))
    quotes = await QuoteStays(READER, {}).scenarios(READER.listing.id, [scenario])
    assert [q.status for q in quotes] == [QuoteStatus.BOOKABLE, QuoteStatus.TOO_MANY_GUESTS]
    assert await QuoteStays(READER, {}).scenarios(ListingId("example", "0"), [scenario]) == []


def test_the_shipped_fee_policies_admit_that_fees_are_unknown() -> None:
    policies = load_fee_policies(CONFIG)
    assert set(policies) == {"jabama", "shab"}
    assert not any(p.fees_known for p in policies.values())
    assert all("2026-10-01" in p.source for p in policies.values())


def test_an_invalid_fees_file_is_a_configuration_error(tmp_path: Path) -> None:
    path = tmp_path / "fees.toml"
    path.write_text('[[policies]]\nplatform = "x"\n', encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_fee_policies(path)
