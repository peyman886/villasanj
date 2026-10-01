"""Relative stay dates resolved deterministically (ROADMAP M8, built ahead of it).

The query-understanding LLM names a date expression ("this weekend", "15 Mehr", "the next
holiday"); it never computes dates. Code resolves the expression against today and a holiday
calendar whose every day has a source:
- Friday is the weekly holiday;
- fixed solar-calendar official holidays come from config (they fall on the same Jalali day every
  year);
- lunar holidays move every year, so they are known only where platform calendars flag them; past
  the observed horizon they are unknown and a result that depends on them says so.

Stay conventions (ARCHITECTURE §10): a weekend is Thursday to Saturday (the nights of Thursday and
Friday), as in config/scenarios.toml; a holiday stay starts on the eve of the first day off and ends
the day after the last one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum
from typing import assert_never

from villasanj.shared.domain.errors import DomainError
from villasanj.shared.domain.jalali import MONTH_NAMES, MONTHS_PER_YEAR, JalaliDate
from villasanj.shared.domain.persian_text import ZWNJ, to_persian_digits
from villasanj.shared.domain.stay import DateRange

FRIDAY = 4  # date.weekday()
THURSDAY = 3
DAYS_PER_WEEK = 7
WEEKEND_NIGHTS = 2
NOWRUZ_LAST_DAY = 13  # 13 Farvardin (Sizdah Bedar) closes the Nowruz holidays
SEARCH_DAYS = 400  # how far ahead "the next holiday" is looked for
WEEKDAY_NAMES = (
    "دوشنبه",
    f"سه{ZWNJ}شنبه",
    "چهارشنبه",
    "پنجشنبه",
    "جمعه",
    "شنبه",
    "یکشنبه",
)  # indexed by date.weekday()


class InvalidDateExpression(DomainError):
    """An expression that names no future stay (e.g. a past day with an explicit year)."""


class HolidayKind(StrEnum):
    WEEKLY = "weekly"  # Friday
    FIXED = "fixed"  # a fixed solar-calendar official holiday (config)
    OBSERVED = "observed"  # flagged by a platform's calendar for most of its listings


@dataclass(frozen=True, slots=True)
class FixedHoliday:
    month: int  # Jalali
    day: int
    name_fa: str


@dataclass(frozen=True, slots=True)
class Holiday:
    day: date
    kind: HolidayKind
    name_fa: str | None
    source: str  # where this is known from (a config file, a platform-flag summary)


@dataclass(frozen=True, slots=True)
class HolidayCalendar:
    fixed: tuple[FixedHoliday, ...]
    fixed_source: str
    observed: Mapping[date, str] = field(default_factory=dict)  # day -> source summary
    known_until: date | None = None  # lunar holidays on or after this day are unknown

    def holidays_on(self, day: date) -> list[Holiday]:
        found = []
        if day.weekday() == FRIDAY:
            found.append(Holiday(day, HolidayKind.WEEKLY, "جمعه", "weekly holiday"))
        jalali = JalaliDate.from_gregorian(day)
        found.extend(
            Holiday(day, HolidayKind.FIXED, f.name_fa, self.fixed_source)
            for f in self.fixed
            if (f.month, f.day) == (jalali.month, jalali.day)
        )
        if day in self.observed:
            found.append(Holiday(day, HolidayKind.OBSERVED, None, self.observed[day]))
        return found

    def is_off(self, day: date) -> bool:
        return bool(self.holidays_on(day))

    def lunar_known(self, day: date) -> bool:
        return self.known_until is not None and day < self.known_until


# Expressions the query-understanding step can name; resolution is code.
@dataclass(frozen=True, slots=True)
class RelativeDay:
    days: int  # 0 tonight, 1 tomorrow, 2 the day after


@dataclass(frozen=True, slots=True)
class Weekday:
    weekday: int  # date.weekday()
    weeks_ahead: int = 0  # 1: «... هفته بعد»


@dataclass(frozen=True, slots=True)
class Weekend:
    weeks_ahead: int = 0


@dataclass(frozen=True, slots=True)
class OnJalaliDay:
    month: int
    day: int
    year: int | None = None  # None: the next time that day comes


@dataclass(frozen=True, slots=True)
class InJalaliMonth:
    month: int
    year: int | None = None


@dataclass(frozen=True, slots=True)
class Nowruz:
    year: int | None = None


@dataclass(frozen=True, slots=True)
class NextHoliday:
    """The next run of days off that holds an official holiday (not just a Friday)."""


DateExpression = (
    RelativeDay | Weekday | Weekend | OnJalaliDay | InJalaliMonth | Nowruz | NextHoliday
)


class DateCaveat(StrEnum):
    NEXT_YEAR = "next_year"  # the named day or month has passed this year
    PARTIAL_WEEKEND = "partial_weekend"  # asked on Friday: only Friday night is left
    LUNAR_HOLIDAYS_UNKNOWN = "lunar_holidays_unknown"  # an unobserved lunar holiday may matter


@dataclass(frozen=True, slots=True)
class ResolvedDates:
    window: DateRange  # the stay; for a flexible expression, the span a stay must fit in
    flexible: bool  # True for a month or Nowruz: any stay inside the window
    holidays: tuple[Holiday, ...]  # the days off inside the window, with their sources
    caveats: frozenset[DateCaveat] = frozenset()


def resolve(
    expression: DateExpression,
    today: date,
    calendar: HolidayCalendar,
    nights: int | None = None,
) -> ResolvedDates:
    """The stay (or the window to search) an expression names, seen from ``today``."""
    caveats: set[DateCaveat] = set()
    flexible = False
    match expression:
        case RelativeDay(days):
            window = _stay(today + timedelta(days=days), nights or 1)
        case Weekday(weekday, weeks_ahead):
            start = today + timedelta(days=(weekday - today.weekday()) % DAYS_PER_WEEK)
            window = _stay(start + timedelta(weeks=weeks_ahead), nights or 1)
        case Weekend(weeks_ahead):
            window = _weekend(today, weeks_ahead, nights, caveats)
        case OnJalaliDay(month, day, year):
            start = _next_jalali(today, month, day, year, caveats)
            window = _stay(start, nights or 1)
        case InJalaliMonth(month, year):
            window, flexible = _month(today, month, year, caveats), True
        case Nowruz(year):
            window, flexible = _nowruz(today, year), True
        case NextHoliday():
            window = _next_holiday(today, calendar, nights, caveats)
        case _:  # pragma: no cover - exhaustive
            assert_never(expression)
    holidays = tuple(h for day in window.nights() for h in calendar.holidays_on(day))
    if not calendar.lunar_known(window.check_out - timedelta(days=1)):
        caveats.add(DateCaveat.LUNAR_HOLIDAYS_UNKNOWN)
    return ResolvedDates(window, flexible, holidays, frozenset(caveats))


def _stay(check_in: date, nights: int) -> DateRange:
    return DateRange(check_in, check_in + timedelta(days=nights))


def _weekend(
    today: date, weeks_ahead: int, nights: int | None, caveats: set[DateCaveat]
) -> DateRange:
    if today.weekday() == FRIDAY:  # this weekend began yesterday
        if weeks_ahead == 0:
            caveats.add(DateCaveat.PARTIAL_WEEKEND)
            return _stay(today, nights or 1)
        thursday = today - timedelta(days=1)
    else:
        thursday = today + timedelta(days=(THURSDAY - today.weekday()) % DAYS_PER_WEEK)
    return _stay(thursday + timedelta(weeks=weeks_ahead), nights or WEEKEND_NIGHTS)


def _next_jalali(
    today: date, month: int, day: int, year: int | None, caveats: set[DateCaveat]
) -> date:
    if year is not None:
        found = JalaliDate(year, month, day).to_gregorian()
        if found < today:
            raise InvalidDateExpression(f"{year}/{month}/{day} is in the past")
        return found
    this_year = JalaliDate.from_gregorian(today).year
    found = JalaliDate(this_year, month, day).to_gregorian()
    if found < today:
        caveats.add(DateCaveat.NEXT_YEAR)
        found = JalaliDate(this_year + 1, month, day).to_gregorian()
    return found


def _month(today: date, month: int, year: int | None, caveats: set[DateCaveat]) -> DateRange:
    start_year = year if year is not None else JalaliDate.from_gregorian(today).year
    start, end = _month_span(start_year, month)
    if end <= today + timedelta(days=1):  # not even one night is left in it
        if year is not None:
            raise InvalidDateExpression(f"{year}/{month} is in the past")
        caveats.add(DateCaveat.NEXT_YEAR)
        start, end = _month_span(start_year + 1, month)
    return DateRange(max(start, today), end)


def _month_span(year: int, month: int) -> tuple[date, date]:
    start = JalaliDate(year, month, 1).to_gregorian()
    if month == MONTHS_PER_YEAR:
        return start, JalaliDate(year + 1, 1, 1).to_gregorian()
    return start, JalaliDate(year, month + 1, 1).to_gregorian()


def _nowruz(today: date, year: int | None) -> DateRange:
    """The coming Nowruz unless a year is given (no caveat: that is what people mean)."""
    candidate = year if year is not None else JalaliDate.from_gregorian(today).year
    end = JalaliDate(candidate, 1, NOWRUZ_LAST_DAY + 1).to_gregorian()  # check out by the 14th
    if end <= today + timedelta(days=1):
        if year is not None:
            raise InvalidDateExpression(f"Nowruz {year} is in the past")
        candidate += 1
        end = JalaliDate(candidate, 1, NOWRUZ_LAST_DAY + 1).to_gregorian()
    start = JalaliDate(candidate, 1, 1).to_gregorian()
    return DateRange(max(start, today), end)


def _next_holiday(
    today: date, calendar: HolidayCalendar, nights: int | None, caveats: set[DateCaveat]
) -> DateRange:
    day = today
    for _ in range(SEARCH_DAYS):
        if calendar.is_off(day):
            run = _run_from(day, calendar)
            if any(h.kind is not HolidayKind.WEEKLY for d in run for h in calendar.holidays_on(d)):
                if not calendar.lunar_known(run[0]):
                    caveats.add(DateCaveat.LUNAR_HOLIDAYS_UNKNOWN)  # an earlier one may exist
                check_in = max(run[0] - timedelta(days=1), today)
                end = run[-1] + timedelta(days=1)
                return _stay(check_in, nights) if nights else DateRange(check_in, end)
            day = run[-1]
        day += timedelta(days=1)
    raise InvalidDateExpression(f"no official holiday within {SEARCH_DAYS} days")


def _run_from(day: date, calendar: HolidayCalendar) -> list[date]:
    run = [day]
    while calendar.is_off(run[-1] + timedelta(days=1)):
        run.append(run[-1] + timedelta(days=1))
    return run


def describe_fa(window: DateRange) -> str:
    """Persian chip text for a stay, e.g. «پنجشنبه ۲۴ مهر تا شنبه ۲۶ مهر»."""
    return f"{_day_fa(window.check_in)} تا {_day_fa(window.check_out)}"


def _day_fa(day: date) -> str:
    jalali = JalaliDate.from_gregorian(day)
    name = MONTH_NAMES[jalali.month - 1]
    return f"{WEEKDAY_NAMES[day.weekday()]} {to_persian_digits(str(jalali.day))} {name}"
