"""Jalali (Solar Hijri) calendar conversion without third-party libraries.

Port of the break-year algorithm used by jalaali-js (Borkowski), valid for Jalali years in
``[MIN_JALALI_YEAR, MAX_JALALI_YEAR)``. Day arithmetic uses ``date.toordinal()`` instead of Julian
day numbers, which only shifts the epoch and keeps the algorithm intact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from villasanj.shared.domain.errors import InvalidJalaliDate

# Jalali years where the leap-year cycle changes (from jalaali-js).
_BREAKS: tuple[int, ...] = (
    -61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210,
    1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178,
)  # fmt: skip
MIN_JALALI_YEAR = 1  # date.toordinal() requires Gregorian year >= 1
MAX_JALALI_YEAR = _BREAKS[-1]
JALALI_EPOCH_OFFSET = 621
MONTHS_PER_YEAR = 12
MONTH_NAMES = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)
FIRST_HALF_MONTHS = 6
FIRST_HALF_MONTH_DAYS = 31
SECOND_HALF_MONTH_DAYS = 30
ESFAND = 12
ESFAND_COMMON_DAYS = 29
ESFAND_LEAP_DAYS = 30
FIRST_HALF_LAST_DAY_INDEX = FIRST_HALF_MONTHS * FIRST_HALF_MONTH_DAYS - 1  # 185
DAYS_FROM_MEHR_TO_NOWRUZ_COMMON = 179
CYCLE = 33
LEAP_YEARS_PER_CYCLE = 8
GREGORIAN_MARCH = 3
FARVARDIN_BASE_DAY = 20
GREGORIAN_LEAP_CORRECTION = 150


def _div(a: int, b: int) -> int:
    """Integer division truncating toward zero (JavaScript ``~~(a / b)``)."""
    quotient = abs(a) // abs(b)
    return quotient if (a >= 0) == (b > 0) else -quotient


def _mod(a: int, b: int) -> int:
    """Remainder with the sign of the dividend, matching ``_div``."""
    return a - _div(a, b) * b


@dataclass(frozen=True, slots=True)
class _YearInfo:
    gregorian_year: int
    march_day: int  # Gregorian day in March that is 1 Farvardin
    leap: int  # years since the last leap year; 0 means this year is leap


def _require_supported_year(jy: int) -> None:
    if not MIN_JALALI_YEAR <= jy < MAX_JALALI_YEAR:
        raise InvalidJalaliDate(f"Jalali year {jy} is outside the supported range")


def _year_info(jy: int) -> _YearInfo:
    _require_supported_year(jy)
    gy = jy + JALALI_EPOCH_OFFSET
    leap_j = -14
    jp = _BREAKS[0]
    jump = 0
    for jm in _BREAKS[1:]:
        jump = jm - jp
        if jy < jm:
            break
        leap_j += _div(jump, CYCLE) * LEAP_YEARS_PER_CYCLE + _div(_mod(jump, CYCLE), 4)
        jp = jm
    n = jy - jp
    leap_j += _div(n, CYCLE) * LEAP_YEARS_PER_CYCLE + _div(_mod(n, CYCLE) + 3, 4)
    if _mod(jump, CYCLE) == 4 and jump - n == 4:  # noqa: PLR2004 - part of the published algorithm
        leap_j += 1
    leap_g = _div(gy, 4) - _div((_div(gy, 100) + 1) * 3, 4) - GREGORIAN_LEAP_CORRECTION
    march = FARVARDIN_BASE_DAY + leap_j - leap_g
    if jump - n < 6:  # noqa: PLR2004 - part of the published algorithm
        n = n - jump + _div(jump + 4, CYCLE) * CYCLE
    leap = _mod(_mod(n + 1, CYCLE) - 1, 4)
    if leap == -1:
        leap = 4
    return _YearInfo(gregorian_year=gy, march_day=march, leap=leap)


def is_jalali_leap_year(jy: int) -> bool:
    return _year_info(jy).leap == 0


def jalali_month_length(jy: int, jm: int) -> int:
    _require_supported_year(jy)
    if not 1 <= jm <= MONTHS_PER_YEAR:
        raise InvalidJalaliDate(f"Jalali month {jm} does not exist")
    if jm <= FIRST_HALF_MONTHS:
        return FIRST_HALF_MONTH_DAYS
    if jm < ESFAND:
        return SECOND_HALF_MONTH_DAYS
    return ESFAND_LEAP_DAYS if is_jalali_leap_year(jy) else ESFAND_COMMON_DAYS


def _nowruz_ordinal(jy: int) -> int:
    info = _year_info(jy)
    return date(info.gregorian_year, GREGORIAN_MARCH, info.march_day).toordinal()


@dataclass(frozen=True, slots=True, order=True)
class JalaliDate:
    """A calendar date in the Jalali calendar (e.g. 1405/07/09)."""

    year: int
    month: int
    day: int

    def __post_init__(self) -> None:
        length = jalali_month_length(self.year, self.month)
        if not 1 <= self.day <= length:
            raise InvalidJalaliDate(f"{self.year}/{self.month:02d} has no day {self.day}")

    @classmethod
    def from_gregorian(cls, value: date) -> JalaliDate:
        ordinal = value.toordinal()
        jy = value.year - JALALI_EPOCH_OFFSET
        info = _year_info(jy)
        k = ordinal - date(value.year, GREGORIAN_MARCH, info.march_day).toordinal()
        if k >= 0:
            if k <= FIRST_HALF_LAST_DAY_INDEX:
                return cls(jy, 1 + k // FIRST_HALF_MONTH_DAYS, k % FIRST_HALF_MONTH_DAYS + 1)
            k -= FIRST_HALF_LAST_DAY_INDEX + 1
        else:
            jy -= 1
            k += DAYS_FROM_MEHR_TO_NOWRUZ_COMMON
            if info.leap == 1:  # one year since the last leap year: the previous year was leap
                k += 1
        return cls(
            jy,
            FIRST_HALF_MONTHS + 1 + k // SECOND_HALF_MONTH_DAYS,
            k % SECOND_HALF_MONTH_DAYS + 1,
        )

    def to_gregorian(self) -> date:
        days_before_month = (self.month - 1) * FIRST_HALF_MONTH_DAYS - max(
            0, self.month - 1 - FIRST_HALF_MONTHS
        )
        return date.fromordinal(_nowruz_ordinal(self.year) + days_before_month + self.day - 1)

    def __str__(self) -> str:
        return f"{self.year:04d}/{self.month:02d}/{self.day:02d}"
