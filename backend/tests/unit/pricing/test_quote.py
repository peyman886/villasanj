"""Pricing engine v1 (ROADMAP M3 criterion 3): every rule, including the unknowns."""

from datetime import date, timedelta

import pytest

from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.ingestion.domain.parsed import Availability, ParsedRateCard
from villasanj.pricing.domain.quote import (
    Caveat,
    DirectQuote,
    FeePolicy,
    QuoteSource,
    QuoteStatus,
    StayRequest,
    quote_stay,
)
from villasanj.shared.domain.money import Money, MoneyRange
from villasanj.shared.domain.stay import DateRange, GuestCount

SNAPSHOT = "00000000-0000-0000-0000-000000000501"
THU, FRI, SAT = date(2026, 10, 15), date(2026, 10, 16), date(2026, 10, 17)
STAY = DateRange(THU, SAT)  # two nights: Thursday and Friday
FINAL = FeePolicy("example", fees_known=True, source="terms: the listed price is final")
UNKNOWN_FEES = FeePolicy("example", fees_known=False, source="not published")
ID = ListingId("example", "42")


def toman(amount: int) -> Money:
    return Money.from_toman(amount)


def listing(**overrides: object) -> Listing:
    return Listing.from_parsed(parsed(**overrides), SNAPSHOT, NOW)


def night(
    day: date,
    price: int | None = 1_000_000,
    extra: int | None = None,
    availability: Availability = Availability.AVAILABLE,
    min_nights: int | None = None,
    is_holiday: bool | None = False,
    age_hours: int = 0,
) -> CalendarObservation:
    return CalendarObservation(
        listing_id=ID,
        night=day,
        availability=availability,
        nightly_price=toman(price) if price is not None else None,
        extra_guest_price=toman(extra) if extra is not None else None,
        min_nights=min_nights,
        is_holiday=is_holiday,
        snapshot_id=SNAPSHOT,
        observed_at=NOW - timedelta(hours=age_hours),
    )


def ask(guests: int = 4, stay: DateRange = STAY) -> StayRequest:
    return StayRequest(stay, GuestCount(guests))


def test_nightly_prices_are_summed() -> None:
    quote = quote_stay(listing(), [night(THU, 1_000_000), night(FRI, 1_200_000)], ask(), FINAL)
    assert quote.status is QuoteStatus.BOOKABLE
    assert quote.source is QuoteSource.CALENDAR
    assert quote.total == MoneyRange.exact(toman(2_200_000))
    assert [n.night for n in quote.nights] == [THU, FRI]
    assert quote.caveats == frozenset()


def test_the_newest_observation_of_a_night_wins_and_others_are_ignored() -> None:
    observations = [
        night(THU, 900_000, age_hours=30),
        night(THU, 1_000_000, age_hours=2),
        night(FRI, 1_000_000, age_hours=1),
        night(FRI, 800_000, age_hours=40),  # older, seen after the newer one
        night(SAT, 5_000_000),  # check-out day: not a night of this stay
    ]
    quote = quote_stay(listing(), observations, ask(), FINAL)
    assert quote.total == MoneyRange.exact(toman(2_000_000))
    assert quote.oldest_observation == NOW - timedelta(hours=2)
    assert quote.newest_observation == NOW - timedelta(hours=1)


def test_extra_guests_above_base_capacity_pay_per_night() -> None:
    quote = quote_stay(
        listing(base_capacity=4, extra_capacity=2),
        [night(THU, extra=300_000), night(FRI, extra=300_000)],
        ask(guests=6),
        FINAL,
    )
    assert quote.total == MoneyRange.exact(toman(2 * 1_000_000 + 2 * 2 * 300_000))
    assert all(n.extra_guests == 2 for n in quote.nights)


def test_more_guests_than_the_maximum_is_not_possible() -> None:
    quote = quote_stay(
        listing(base_capacity=4, extra_capacity=2), [night(THU), night(FRI)], ask(7), FINAL
    )
    assert quote.status is QuoteStatus.TOO_MANY_GUESTS
    assert quote.total is None


def test_one_unavailable_night_makes_the_stay_unavailable() -> None:
    observations = [night(THU), night(FRI, availability=Availability.BOOKED)]
    assert quote_stay(listing(), observations, ask(), FINAL).status is QuoteStatus.UNAVAILABLE


def test_unavailable_beats_unknown() -> None:
    observations = [night(THU, availability=Availability.UNAVAILABLE)]  # Friday never observed
    assert quote_stay(listing(), observations, ask(), FINAL).status is QuoteStatus.UNAVAILABLE


@pytest.mark.parametrize(
    "observations",
    [
        [night(THU)],  # Friday was never observed
        [night(THU), night(FRI, availability=Availability.UNKNOWN)],
        [],
    ],
)
def test_missing_or_unknown_nights_make_the_stay_unknown(
    observations: list[CalendarObservation],
) -> None:
    quote = quote_stay(listing(), observations, ask(), FINAL)
    assert quote.status is QuoteStatus.UNKNOWN
    assert quote.total is None


def test_min_nights_of_the_check_in_night_applies() -> None:
    observations = [night(THU, min_nights=3), night(FRI, min_nights=1)]
    assert quote_stay(listing(), observations, ask(), FINAL).status is QuoteStatus.BELOW_MIN_NIGHTS


def test_listing_min_nights_applies_when_the_night_has_none() -> None:
    observations = [night(THU), night(FRI)]
    quote = quote_stay(listing(min_nights=3), observations, ask(), FINAL)
    assert quote.status is QuoteStatus.BELOW_MIN_NIGHTS


def test_no_min_nights_anywhere_means_no_restriction() -> None:
    quote = quote_stay(listing(min_nights=None), [night(THU), night(FRI)], ask(), FINAL)
    assert quote.status is QuoteStatus.BOOKABLE


def test_unknown_fees_open_the_upper_bound() -> None:
    quote = quote_stay(listing(), [night(THU), night(FRI)], ask(), UNKNOWN_FEES)
    assert quote.total == MoneyRange.at_least(toman(2_000_000))
    assert Caveat.FEES_UNKNOWN in quote.caveats


def test_unknown_base_capacity_opens_the_upper_bound() -> None:
    quote = quote_stay(
        listing(base_capacity=None, extra_capacity=None),
        [night(THU), night(FRI)],
        ask(guests=8),
        FINAL,
    )
    assert quote.status is QuoteStatus.BOOKABLE
    assert quote.total == MoneyRange.at_least(toman(2_000_000))
    assert Caveat.CAPACITY_UNKNOWN in quote.caveats


CARD = ParsedRateCard(
    base=toman(1_000_000),
    weekend=toman(1_300_000),
    holiday=toman(1_600_000),
    extra_guest_base=toman(200_000),
    extra_guest_weekend=toman(200_000),
    extra_guest_holiday=toman(400_000),
)


def test_extra_guest_price_falls_back_to_the_rate_card() -> None:
    quote = quote_stay(
        listing(rate_card=CARD),
        [night(THU), night(FRI, is_holiday=True)],
        ask(guests=5),
        FINAL,
    )
    assert quote.total == MoneyRange.exact(toman(2_000_000 + 200_000 + 400_000))
    assert Caveat.EXTRA_GUEST_PRICE_FROM_RATE_CARD in quote.caveats


def test_extra_guest_price_that_nobody_published_is_open_ended() -> None:
    quote = quote_stay(listing(), [night(THU), night(FRI)], ask(guests=5), FINAL)
    assert quote.total == MoneyRange.at_least(toman(2_000_000))
    assert Caveat.EXTRA_GUEST_PRICE_UNKNOWN in quote.caveats


@pytest.mark.parametrize(
    ("is_holiday", "card", "expected"),
    [
        # An ordinary night costs base or weekend: we do not guess which nights are "weekend".
        (False, CARD, MoneyRange(toman(1_000_000), toman(1_300_000))),
        (False, ParsedRateCard(base=toman(1_000_000)), MoneyRange.exact(toman(1_000_000))),
        (False, ParsedRateCard(), MoneyRange.at_least(Money.zero())),
        (True, CARD, MoneyRange.exact(toman(1_600_000))),
        (True, ParsedRateCard(base=toman(1_000_000)), MoneyRange.at_least(Money.zero())),
        (None, CARD, MoneyRange(toman(1_000_000), toman(1_600_000))),
        (None, ParsedRateCard(holiday=toman(1_600_000)), MoneyRange.at_least(Money.zero())),
    ],
)
def test_missing_night_price_falls_back_to_the_rate_card(
    is_holiday: bool | None, card: ParsedRateCard, expected: MoneyRange
) -> None:
    stay = DateRange(THU, FRI)
    quote = quote_stay(
        listing(rate_card=card), [night(THU, None, is_holiday=is_holiday)], ask(stay=stay), FINAL
    )
    assert quote.total == expected
    caveat = Caveat.NIGHT_PRICE_UNKNOWN if expected.is_open else Caveat.NIGHT_PRICE_FROM_RATE_CARD
    assert caveat in quote.caveats


def test_a_direct_quote_wins_when_it_is_at_least_as_new_as_the_calendar() -> None:
    direct = DirectQuote(ID, ask(), toman(2_500_000), SNAPSHOT, NOW)
    observations = [night(THU, age_hours=1), night(FRI, age_hours=1)]
    quote = quote_stay(listing(), observations, ask(), UNKNOWN_FEES, direct)
    assert quote.source is QuoteSource.DIRECT_QUOTE
    assert quote.total == MoneyRange.exact(toman(2_500_000))
    assert quote.newest_observation == NOW


def test_a_direct_quote_without_any_calendar_still_counts() -> None:
    direct = DirectQuote(ID, ask(), toman(2_500_000), SNAPSHOT, NOW)
    assert quote_stay(listing(), [], ask(), FINAL, direct).source is QuoteSource.DIRECT_QUOTE


@pytest.mark.parametrize(
    "direct",
    [
        DirectQuote(ID, ask(), toman(2_500_000), SNAPSHOT, NOW - timedelta(hours=5)),  # older
        DirectQuote(ID, ask(guests=2), toman(2_500_000), SNAPSHOT, NOW),  # another group size
        DirectQuote(ListingId("example", "7"), ask(), toman(2_500_000), SNAPSHOT, NOW),
    ],
)
def test_a_stale_or_different_direct_quote_is_ignored(direct: DirectQuote) -> None:
    observations = [night(THU, age_hours=1), night(FRI, availability=Availability.UNAVAILABLE)]
    quote = quote_stay(listing(), observations, ask(), FINAL, direct)
    assert quote.source is QuoteSource.CALENDAR
    assert quote.status is QuoteStatus.UNAVAILABLE
