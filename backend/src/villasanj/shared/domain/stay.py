"""Stay value objects: date ranges (check-out exclusive) and guest counts."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta

from villasanj.shared.domain.errors import InvalidDateRange, InvalidGuestCount

MIN_GUESTS = 1
MAX_GUESTS = 50
ONE_DAY = timedelta(days=1)


@dataclass(frozen=True, slots=True)
class DateRange:
    """A stay from ``check_in`` (first night) to ``check_out`` (departure day, not a night)."""

    check_in: date
    check_out: date

    def __post_init__(self) -> None:
        if self.check_out <= self.check_in:
            raise InvalidDateRange(
                f"check_out ({self.check_out}) must be after check_in ({self.check_in})"
            )

    @property
    def night_count(self) -> int:
        return (self.check_out - self.check_in).days

    def nights(self) -> Iterator[date]:
        night = self.check_in
        while night < self.check_out:
            yield night
            night += ONE_DAY

    def contains_night(self, night: date) -> bool:
        return self.check_in <= night < self.check_out

    def overlaps(self, other: DateRange) -> bool:
        return self.check_in < other.check_out and other.check_in < self.check_out


@dataclass(frozen=True, slots=True, order=True)
class GuestCount:
    """Number of people in the group (adults and children counted alike, as platforms do)."""

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise InvalidGuestCount(f"guest count must be an integer, got {self.value!r}")
        if not MIN_GUESTS <= self.value <= MAX_GUESTS:
            raise InvalidGuestCount(
                f"guest count must be within [{MIN_GUESTS}, {MAX_GUESTS}], got {self.value}"
            )

    def __int__(self) -> int:
        return self.value

    def above(self, base_capacity: int) -> int:
        """How many guests exceed ``base_capacity`` (the extra-guest count used for pricing)."""
        return max(0, self.value - base_capacity)
