"""The holiday calendar the date resolver uses: config plus observed platform flags (M8 prep)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from villasanj.catalog.application.reading import CalendarFlagQuery
from villasanj.discovery.domain.dates import SEARCH_DAYS, FixedHoliday, HolidayCalendar

MIN_REPORTING = 20  # listings that must report a night before a platform's flags count for it
MIN_SHARE = 0.9  # share of them that must flag it: one host's own setting is not a holiday


@dataclass(frozen=True, slots=True)
class HolidaySources:
    fixed: tuple[FixedHoliday, ...]
    fixed_source: str
    observed_from: frozenset[str]  # platforms whose calendar flag means a public holiday


class BuildHolidayCalendar:
    def __init__(self, flags: CalendarFlagQuery, sources: HolidaySources) -> None:
        self._flags = flags
        self._sources = sources

    async def run(self, today: date) -> HolidayCalendar:
        rows = await self._flags.holiday_flags(today, today + timedelta(days=SEARCH_DAYS))
        observed: dict[date, list[str]] = {}
        known_until: date | None = None
        for row in rows:
            if row.platform not in self._sources.observed_from or row.reported < MIN_REPORTING:
                continue
            known_until = max(known_until or row.night, row.night + timedelta(days=1))
            if row.flagged / row.reported >= MIN_SHARE:
                observed.setdefault(row.night, []).append(
                    f"{row.platform} calendar: {row.flagged} of {row.reported} listings, "
                    f"observed {row.observed_at:%Y-%m-%d}"
                )
        return HolidayCalendar(
            self._sources.fixed,
            self._sources.fixed_source,
            {night: "; ".join(sources) for night, sources in observed.items()},
            known_until,
        )
