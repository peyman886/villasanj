"""One villa across its listings (ROADMAP M7): where they disagree and the merged calendar.

Nothing is averaged or merged into a single value: a field the listings disagree on is shown
with each platform's value (a conflict badge), and each night keeps each platform's observation.
A night free on one platform and taken on another, observed less than ``max_gap`` apart, is a
"hidden night": free elsewhere, which is the point of looking at both.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from villasanj.catalog.domain.listing import CalendarObservation, Listing
from villasanj.ingestion.domain.parsed import Availability

AREA_TOLERANCE = 0.15  # areas within 15% of each other are the same measurement, rounded
_TAKEN = frozenset({Availability.UNAVAILABLE, Availability.BOOKED, Availability.BLOCKED})

_FIELDS: Mapping[str, Callable[[Listing], object]] = {
    "property_type": lambda x: x.property_type,
    "bedrooms": lambda x: x.bedrooms,
    "bathrooms": lambda x: x.bathrooms,
    "area_m2": lambda x: x.area_m2,
    "base_capacity": lambda x: x.base_capacity,
    "max_capacity": lambda x: x.max_capacity,
}


@dataclass(frozen=True, slots=True)
class FieldConflict:
    field: str
    values: dict[str, object]  # platform -> its value (only platforms that state one)


def conflicts(listings: Sequence[Listing]) -> list[FieldConflict]:
    """Fields two or more listings state differently (a missing value is not a conflict)."""
    found = []
    for name, read in _FIELDS.items():
        values = {x.id.platform: read(x) for x in listings if read(x) is not None}
        if len(set(values.values())) <= 1:
            continue  # stated once, or the same everywhere
        if name == "area_m2" and _close([v for v in values.values() if isinstance(v, int)]):
            continue
        found.append(FieldConflict(name, values))
    return found


def _close(areas: Sequence[int]) -> bool:
    return bool(areas) and min(areas) >= (1 - AREA_TOLERANCE) * max(areas)


@dataclass(frozen=True, slots=True)
class MergedNight:
    night: date
    by_platform: dict[str, CalendarObservation]  # the newest observation per platform
    hidden: bool  # free on one platform, taken on another, observed close together


def merge_calendars(
    by_platform: Mapping[str, Sequence[CalendarObservation]], max_gap: timedelta
) -> list[MergedNight]:
    newest: dict[str, dict[date, CalendarObservation]] = {}
    for platform, observations in by_platform.items():
        per_night: dict[date, CalendarObservation] = {}
        for o in observations:
            if o.night not in per_night or o.observed_at > per_night[o.night].observed_at:
                per_night[o.night] = o
        newest[platform] = per_night
    nights = sorted({n for per_night in newest.values() for n in per_night})
    merged = []
    for night in nights:
        seen = {p: per[night] for p, per in newest.items() if night in per}
        merged.append(MergedNight(night, seen, _hidden(list(seen.values()), max_gap)))
    return merged


def _hidden(observations: Sequence[CalendarObservation], max_gap: timedelta) -> bool:
    free = [o for o in observations if o.availability is Availability.AVAILABLE]
    taken = [o for o in observations if o.availability in _TAKEN]
    return any(abs(f.observed_at - t.observed_at) <= max_gap for f in free for t in taken)
