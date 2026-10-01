"""Relative stay dates resolved against today and a sourced holiday calendar (M8 groundwork)."""

from datetime import date

import pytest

from villasanj.discovery.domain.dates import (
    THURSDAY,
    DateCaveat,
    FixedHoliday,
    HolidayCalendar,
    HolidayKind,
    InJalaliMonth,
    InvalidDateExpression,
    NextHoliday,
    Nowruz,
    OnJalaliDay,
    RelativeDay,
    Weekday,
    Weekend,
    describe_fa,
    resolve,
)
from villasanj.shared.domain.stay import DateRange

TODAY = date(2026, 10, 1)  # Thursday, 1405/07/09
FIXED = (
    FixedHoliday(1, 1, "نوروز"),
    FixedHoliday(1, 2, "نوروز"),
    FixedHoliday(1, 3, "نوروز"),
    FixedHoliday(1, 4, "نوروز"),
    FixedHoliday(1, 12, "روز جمهوری اسلامی"),
    FixedHoliday(1, 13, "روز طبیعت"),
    FixedHoliday(11, 22, "پیروزی انقلاب"),
)
CALENDAR = HolidayCalendar(
    FIXED,
    "config/holidays.toml",
    observed={date(2026, 11, 13): "jabama: 2986 of 2986 listings"},
    known_until=date(2026, 12, 1),
)
NO_OBSERVATIONS = HolidayCalendar(FIXED, "config/holidays.toml")


def stay(check_in: date, check_out: date) -> DateRange:
    return DateRange(check_in, check_out)


@pytest.mark.parametrize(
    ("expression", "today", "nights", "window"),
    [
        (RelativeDay(0), TODAY, None, stay(date(2026, 10, 1), date(2026, 10, 2))),
        (RelativeDay(1), TODAY, 3, stay(date(2026, 10, 2), date(2026, 10, 5))),
        (Weekday(THURSDAY), date(2026, 10, 3), None, stay(date(2026, 10, 8), date(2026, 10, 9))),
        (Weekday(THURSDAY, 1), TODAY, 2, stay(date(2026, 10, 8), date(2026, 10, 10))),
        (Weekend(), TODAY, None, stay(date(2026, 10, 1), date(2026, 10, 3))),  # Thu..Sat
        (Weekend(1), TODAY, None, stay(date(2026, 10, 8), date(2026, 10, 10))),
        (Weekend(), date(2026, 10, 3), None, stay(date(2026, 10, 8), date(2026, 10, 10))),
        (Weekend(1), date(2026, 10, 2), None, stay(date(2026, 10, 8), date(2026, 10, 10))),
        (Weekend(), TODAY, 3, stay(date(2026, 10, 1), date(2026, 10, 4))),
        (OnJalaliDay(7, 15), TODAY, None, stay(date(2026, 10, 7), date(2026, 10, 8))),
    ],
)
def test_exact_stays(
    expression: Weekend, today: date, nights: int | None, window: DateRange
) -> None:
    resolved = resolve(expression, today, CALENDAR, nights)
    assert resolved.window == window
    assert not resolved.flexible
    assert resolved.caveats == frozenset()


def test_on_friday_this_weekend_is_only_friday_night() -> None:
    resolved = resolve(Weekend(), date(2026, 10, 2), CALENDAR)
    assert resolved.window == stay(date(2026, 10, 2), date(2026, 10, 3))
    assert resolved.caveats == {DateCaveat.PARTIAL_WEEKEND}


def test_a_passed_day_means_next_year_unless_the_year_is_explicit() -> None:
    resolved = resolve(OnJalaliDay(7, 1), TODAY, CALENDAR)
    assert resolved.window.check_in == date(2027, 9, 23)  # 1406/07/01
    assert DateCaveat.NEXT_YEAR in resolved.caveats
    assert DateCaveat.LUNAR_HOLIDAYS_UNKNOWN in resolved.caveats  # beyond the observations
    with pytest.raises(InvalidDateExpression):
        resolve(OnJalaliDay(7, 1, 1405), TODAY, CALENDAR)
    explicit = resolve(OnJalaliDay(8, 22, 1405), TODAY, CALENDAR)
    assert explicit.window.check_in == date(2026, 11, 13)


def test_a_month_is_a_flexible_window_with_its_days_off() -> None:
    aban = resolve(InJalaliMonth(8), TODAY, CALENDAR)
    assert aban.flexible
    assert aban.window == stay(date(2026, 10, 23), date(2026, 11, 22))  # 1 Aban .. 1 Azar
    observed = [h for h in aban.holidays if h.kind is HolidayKind.OBSERVED]
    assert [h.day for h in observed] == [date(2026, 11, 13)]
    assert observed[0].source == "jabama: 2986 of 2986 listings"
    fridays = [h for h in aban.holidays if h.kind is HolidayKind.WEEKLY]
    assert len(fridays) == 5
    mehr = resolve(InJalaliMonth(7), TODAY, CALENDAR)  # the current month: from today
    assert mehr.window == stay(TODAY, date(2026, 10, 23))
    shahrivar = resolve(InJalaliMonth(6), TODAY, CALENDAR)
    assert shahrivar.window.check_in == date(2027, 8, 23)
    assert DateCaveat.NEXT_YEAR in shahrivar.caveats
    with pytest.raises(InvalidDateExpression):
        resolve(InJalaliMonth(6, 1405), TODAY, CALENDAR)
    esfand = resolve(InJalaliMonth(12), TODAY, CALENDAR)
    assert esfand.window == stay(date(2027, 2, 20), date(2027, 3, 21))


def test_nowruz_is_the_coming_one() -> None:
    resolved = resolve(Nowruz(), TODAY, CALENDAR)
    assert resolved.window == stay(date(2027, 3, 21), date(2027, 4, 3))  # 1..14 Farvardin 1406
    assert resolved.flexible
    names = {h.name_fa for h in resolved.holidays if h.kind is HolidayKind.FIXED}
    assert names == {"نوروز", "روز جمهوری اسلامی", "روز طبیعت"}
    assert DateCaveat.NEXT_YEAR not in resolved.caveats
    assert resolve(Nowruz(1406), TODAY, CALENDAR).window == resolved.window
    with pytest.raises(InvalidDateExpression):
        resolve(Nowruz(1405), TODAY, CALENDAR)
    during = resolve(Nowruz(), date(2027, 3, 25), CALENDAR)
    assert during.window == stay(date(2027, 3, 25), date(2027, 4, 3))


def test_next_holiday_uses_observed_lunar_holidays() -> None:
    resolved = resolve(NextHoliday(), TODAY, CALENDAR)
    # Friday 22 Aban is flagged: the eve to the day after, the "holiday" scenario exactly.
    assert resolved.window == stay(date(2026, 11, 12), date(2026, 11, 14))
    assert resolved.caveats == frozenset()
    longer = resolve(NextHoliday(), TODAY, CALENDAR, nights=3)
    assert longer.window == stay(date(2026, 11, 12), date(2026, 11, 15))


def test_without_observations_the_next_fixed_holiday_comes_with_a_caveat() -> None:
    resolved = resolve(NextHoliday(), TODAY, NO_OBSERVATIONS)
    # 22 Bahman 1405 is a Thursday; with Friday that is a two-day run.
    assert resolved.window == stay(date(2027, 2, 10), date(2027, 2, 13))
    assert DateCaveat.LUNAR_HOLIDAYS_UNKNOWN in resolved.caveats


def test_inside_a_holiday_run_the_stay_starts_today() -> None:
    resolved = resolve(NextHoliday(), date(2027, 3, 22), NO_OBSERVATIONS)
    assert resolved.window.check_in == date(2027, 3, 22)
    assert resolved.window.check_out == date(2027, 3, 25)  # the day after 4 Farvardin (Wed)


def test_no_holiday_at_all_is_an_error() -> None:
    with pytest.raises(InvalidDateExpression):
        resolve(NextHoliday(), TODAY, HolidayCalendar((), "none"))


def test_chip_text_names_weekdays_and_jalali_days() -> None:
    window = resolve(Weekend(), TODAY, CALENDAR).window
    assert describe_fa(window) == "پنجشنبه ۹ مهر تا شنبه ۱۱ مهر"
