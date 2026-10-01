"""Read access to the catalog for downstream contexts (pricing, entity resolution)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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

    async def calendars(
        self, platform: str, stay: DateRange
    ) -> dict[ListingId, list[CalendarObservation]]:
        """The same for every listing of a platform at once (for batch reports)."""
        ...


@dataclass(frozen=True, slots=True)
class HolidayFlags:
    """How many of a platform's listings flag a night as a holiday (a national-calendar hint)."""

    platform: str
    night: date
    flagged: int  # listings with at least one observation flagging the night
    reported: int  # listings with an observation that says anything about it
    observed_at: datetime  # the newest of those observations


class CalendarFlagQuery(Protocol):
    async def holiday_flags(self, start: date, end: date) -> list[HolidayFlags]:
        """Per platform and night in [start, end), ordered by night then platform."""
        ...
