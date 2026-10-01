"""Offers per listing and their distribution per platform, scenario and group (M6 criteria 2, 4)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import ListingId
from villasanj.pricing.domain.offer import DEFAULT_MAX_AGE, Offer
from villasanj.pricing.domain.quote import FeePolicy, StayRequest, quote_stay
from villasanj.shared.application.clock import Clock
from villasanj.shared.domain.stay import StayScenario


@dataclass(frozen=True, slots=True)
class OfferCounts:
    platform: str
    scenario: str
    guests: int
    listings: int
    by_status: dict[str, int] = field(default_factory=dict)
    by_kind: dict[str, int] = field(default_factory=dict)  # bookable offers only
    stale: int = 0


class OfferBook:
    def __init__(
        self,
        listings: ListingReader,
        fees: Mapping[str, FeePolicy],
        clock: Clock,
        max_age: timedelta = DEFAULT_MAX_AGE,
    ) -> None:
        self._listings = listings
        self._fees = fees
        self._clock = clock
        self._max_age = max_age

    def _fee_policy(self, platform: str) -> FeePolicy:
        return self._fees.get(platform) or FeePolicy(platform, False, "no fee policy configured")

    async def offer(self, listing_id: ListingId, request: StayRequest) -> Offer | None:
        listing = await self._listings.get(listing_id)
        if listing is None:
            return None
        observations = await self._listings.calendar(listing_id, request.stay)
        quote = quote_stay(listing, observations, request, self._fee_policy(listing_id.platform))
        return Offer(quote, self._clock.now(), self._max_age)

    async def distribution(
        self, platforms: Sequence[str], scenarios: Sequence[StayScenario]
    ) -> list[OfferCounts]:
        now = self._clock.now()
        rows = []
        for platform in platforms:
            listings = await self._listings.listings(platform)
            policy = self._fee_policy(platform)
            for scenario in scenarios:
                calendars = await self._listings.calendars(platform, scenario.stay)
                for guests in scenario.guests:
                    request = StayRequest(scenario.stay, guests)
                    statuses: Counter[str] = Counter()
                    kinds: Counter[str] = Counter()
                    stale = 0
                    for listing in listings:
                        quote = quote_stay(listing, calendars.get(listing.id, []), request, policy)
                        offer = Offer(quote, now, self._max_age)
                        statuses[quote.status.value] += 1
                        if offer.kind is not None:
                            kinds[offer.kind.value] += 1
                        stale += offer.stale
                    rows.append(
                        OfferCounts(
                            platform,
                            scenario.slug,
                            guests.value,
                            len(listings),
                            dict(sorted(statuses.items())),
                            dict(sorted(kinds.items())),
                            stale,
                        )
                    )
        return rows
