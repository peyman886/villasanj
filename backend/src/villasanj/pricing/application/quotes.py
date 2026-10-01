"""Quote stays from the catalog's newest observations (pricing engine v1)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import ListingId
from villasanj.pricing.domain.quote import FeePolicy, Quote, StayRequest, quote_stay
from villasanj.shared.domain.stay import StayScenario


class QuoteStays:
    def __init__(self, listings: ListingReader, fees: Mapping[str, FeePolicy]) -> None:
        self._listings = listings
        self._fees = fees

    def fee_policy(self, platform: str) -> FeePolicy:
        return self._fees.get(platform) or FeePolicy(platform, False, "no fee policy configured")

    async def quote(self, listing_id: ListingId, request: StayRequest) -> Quote | None:
        """``None`` when the listing is not in the catalog."""
        listing = await self._listings.get(listing_id)
        if listing is None:
            return None
        observations = await self._listings.calendar(listing_id, request.stay)
        return quote_stay(listing, observations, request, self.fee_policy(listing_id.platform))

    async def scenarios(
        self, listing_id: ListingId, scenarios: Sequence[StayScenario]
    ) -> list[Quote]:
        quotes = []
        for scenario in scenarios:
            for guests in scenario.guests:
                quote = await self.quote(listing_id, StayRequest(scenario.stay, guests))
                if quote is not None:
                    quotes.append(quote)
        return quotes
