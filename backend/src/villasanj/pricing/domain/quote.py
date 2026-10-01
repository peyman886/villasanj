"""All-in price of one listing for one stay and group size, from what the platform showed.

Rules (ROADMAP M3 criterion 3, product rules 1 and 6):
- Each night uses its newest calendar observation; a night without one makes the stay unknown.
- A night observed as unavailable makes the stay unavailable, whatever else is known.
- Guests above the base capacity pay the extra-guest price per night; above the maximum capacity
  the stay is not possible.
- A missing price is never guessed. The listing's rate card may fill it, as a range when the day
  type (holiday or not) is unknown; otherwise the total gets an open upper bound ("≥ X").
- Platform fees that are not published make the upper bound open as well.
- A direct quote from the platform for exactly this stay and group wins over the calendar, unless
  the calendar was observed after it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.ingestion.domain.parsed import Availability, ParsedRateCard
from villasanj.shared.domain.money import Money, MoneyRange
from villasanj.shared.domain.stay import DateRange, GuestCount


class QuoteStatus(StrEnum):
    BOOKABLE = "bookable"
    UNAVAILABLE = "unavailable"  # at least one night was observed unavailable
    TOO_MANY_GUESTS = "too_many_guests"
    BELOW_MIN_NIGHTS = "below_min_nights"
    UNKNOWN = "unknown"  # at least one night has no usable observation


class Caveat(StrEnum):
    NIGHT_PRICE_FROM_RATE_CARD = "night_price_from_rate_card"
    NIGHT_PRICE_UNKNOWN = "night_price_unknown"
    EXTRA_GUEST_PRICE_FROM_RATE_CARD = "extra_guest_price_from_rate_card"
    EXTRA_GUEST_PRICE_UNKNOWN = "extra_guest_price_unknown"
    CAPACITY_UNKNOWN = "capacity_unknown"
    FEES_UNKNOWN = "fees_unknown"


class QuoteSource(StrEnum):
    CALENDAR = "calendar"
    DIRECT_QUOTE = "direct_quote"


@dataclass(frozen=True, slots=True)
class StayRequest:
    stay: DateRange
    guests: GuestCount


@dataclass(frozen=True, slots=True)
class FeePolicy:
    """What a platform adds on top of the listed prices, as far as we can source it."""

    platform: str
    fees_known: bool  # True only when a source says the listed price is the final price
    source: str  # where the statement comes from (URL or document), or why it is unknown


@dataclass(frozen=True, slots=True)
class DirectQuote:
    """An all-in total the platform itself returned for exactly this stay and group."""

    listing_id: ListingId
    request: StayRequest
    total: Money
    snapshot_id: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class NightCharge:
    night: date
    price: MoneyRange
    extra_guests: int
    extra_guest_price: MoneyRange  # per guest; exact zero when nobody is extra


@dataclass(frozen=True, slots=True)
class Quote:
    listing_id: ListingId
    request: StayRequest
    status: QuoteStatus
    total: MoneyRange | None  # only for bookable stays
    source: QuoteSource
    nights: tuple[NightCharge, ...] = ()
    caveats: frozenset[Caveat] = frozenset()
    oldest_observation: datetime | None = None
    newest_observation: datetime | None = None


_BLOCKING = frozenset({Availability.UNAVAILABLE, Availability.BOOKED, Availability.BLOCKED})


def quote_stay(
    listing: Listing,
    observations: Iterable[CalendarObservation],
    request: StayRequest,
    fees: FeePolicy,
    direct_quote: DirectQuote | None = None,
) -> Quote:
    latest = _latest_per_night(observations, request.stay)
    used = list(latest.values())
    oldest = min((o.observed_at for o in used), default=None)
    newest = max((o.observed_at for o in used), default=None)

    if (
        direct_quote is not None
        and direct_quote.listing_id == listing.id
        and direct_quote.request == request
        and (newest is None or direct_quote.observed_at >= newest)
    ):
        return Quote(
            listing_id=listing.id,
            request=request,
            status=QuoteStatus.BOOKABLE,
            total=MoneyRange.exact(direct_quote.total),
            source=QuoteSource.DIRECT_QUOTE,
            oldest_observation=direct_quote.observed_at,
            newest_observation=direct_quote.observed_at,
        )

    def outcome(status: QuoteStatus) -> Quote:
        return Quote(
            listing.id, request, status, None, QuoteSource.CALENDAR, (), frozenset(), oldest, newest
        )

    maximum = listing.max_capacity
    if maximum is not None and request.guests.value > maximum:
        return outcome(QuoteStatus.TOO_MANY_GUESTS)
    if any(o.availability in _BLOCKING for o in used):
        return outcome(QuoteStatus.UNAVAILABLE)
    minimum = _min_nights(listing, latest.get(request.stay.check_in))
    if minimum is not None and request.stay.night_count < minimum:
        return outcome(QuoteStatus.BELOW_MIN_NIGHTS)
    if len(used) < request.stay.night_count or any(
        o.availability is not Availability.AVAILABLE for o in used
    ):
        return outcome(QuoteStatus.UNKNOWN)

    caveats: set[Caveat] = set()
    extra_guests = _extra_guests(listing, request.guests, caveats)
    nights = tuple(
        _charge(latest[night], listing.rate_card, extra_guests, caveats)
        for night in request.stay.nights()
    )
    total = MoneyRange.exact(Money.zero())
    for charge in nights:
        total = total + charge.price + charge.extra_guest_price.scale(charge.extra_guests)
    if extra_guests is None:  # we cannot tell whether extra-guest charges apply
        total = MoneyRange.at_least(total.low)
    if not fees.fees_known:
        caveats.add(Caveat.FEES_UNKNOWN)
        total = MoneyRange.at_least(total.low)
    return Quote(
        listing_id=listing.id,
        request=request,
        status=QuoteStatus.BOOKABLE,
        total=total,
        source=QuoteSource.CALENDAR,
        nights=nights,
        caveats=frozenset(caveats),
        oldest_observation=oldest,
        newest_observation=newest,
    )


def _latest_per_night(
    observations: Iterable[CalendarObservation], stay: DateRange
) -> dict[date, CalendarObservation]:
    latest: dict[date, CalendarObservation] = {}
    for observation in observations:
        if not stay.contains_night(observation.night):
            continue
        current = latest.get(observation.night)
        if current is None or observation.observed_at > current.observed_at:
            latest[observation.night] = observation
    return latest


def _min_nights(listing: Listing, check_in: CalendarObservation | None) -> int | None:
    """The minimum that applies to a check-in on the first night (the night's own rule first)."""
    if check_in is not None and check_in.min_nights is not None:
        return check_in.min_nights
    return listing.min_nights


def _extra_guests(listing: Listing, guests: GuestCount, caveats: set[Caveat]) -> int | None:
    if listing.base_capacity is None:
        caveats.add(Caveat.CAPACITY_UNKNOWN)
        return None
    return max(0, guests.value - listing.base_capacity)


def _charge(
    night: CalendarObservation,
    card: ParsedRateCard,
    extra_guests: int | None,
    caveats: set[Caveat],
) -> NightCharge:
    if night.nightly_price is not None:
        price = MoneyRange.exact(night.nightly_price)
    else:
        price = _from_card(night.is_holiday, (card.base, card.weekend, card.holiday))
        caveats.add(
            Caveat.NIGHT_PRICE_UNKNOWN if price.is_open else Caveat.NIGHT_PRICE_FROM_RATE_CARD
        )
    if not extra_guests:
        extra = MoneyRange.exact(Money.zero())
    elif night.extra_guest_price is not None:
        extra = MoneyRange.exact(night.extra_guest_price)
    else:
        extra = _from_card(
            night.is_holiday,
            (card.extra_guest_base, card.extra_guest_weekend, card.extra_guest_holiday),
        )
        caveats.add(
            Caveat.EXTRA_GUEST_PRICE_UNKNOWN
            if extra.is_open
            else Caveat.EXTRA_GUEST_PRICE_FROM_RATE_CARD
        )
    return NightCharge(night.night, price, extra_guests or 0, extra)


def _from_card(
    is_holiday: bool | None, prices: tuple[Money | None, Money | None, Money | None]
) -> MoneyRange:
    """Rate-card price for a night, from (base, weekend, holiday) prices.

    We do not guess which nights a platform calls "weekend", so an ordinary night costs the base or
    the weekend price: a range unless they are equal. An unset weekend price means no special price
    (the base applies). A night that is, or may be, a holiday needs the holiday price; without it
    the price is open-ended.
    """
    base, weekend, holiday = prices
    if is_holiday is False:
        known = [p for p in (base, weekend) if p is not None]
        complete = bool(known)
    else:
        known = [p for p in (holiday,) if p is not None]
        if is_holiday is None:
            known += [p for p in (base, weekend) if p is not None]
        complete = holiday is not None and (is_holiday is True or base is not None)
    if not complete:
        return MoneyRange.at_least(Money.zero())  # no safe lower bound for an unknown price
    return MoneyRange(min(known), max(known))
