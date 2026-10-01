"""Read access to the catalog for downstream contexts (pricing, entity resolution)."""

from __future__ import annotations

from typing import Protocol

from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.shared.domain.stay import DateRange


class ListingReader(Protocol):
    async def get(self, listing_id: ListingId) -> Listing | None: ...

    async def listings(self, platform: str) -> list[Listing]:
        """Every stored listing of a platform, ordered by external id."""
        ...

    async def calendar(self, listing_id: ListingId, stay: DateRange) -> list[CalendarObservation]:
        """All stored observations for the stay's nights (every snapshot, not only the newest)."""
        ...
