from datetime import date, timedelta

import jdatetime
import pytest
from hypothesis import given
from hypothesis import strategies as st

from villasanj.shared.domain.errors import InvalidJalaliDate
from villasanj.shared.domain.jalali import JalaliDate, is_jalali_leap_year, jalali_month_length

# Two full centuries, day by day, against an independent implementation.
FIRST_DAY = date(1925, 3, 21)  # 1304/01/01
LAST_DAY = date(2125, 3, 20)


def test_every_day_of_two_centuries_matches_jdatetime() -> None:
    day = FIRST_DAY
    checked = 0
    while day <= LAST_DAY:
        expected = jdatetime.date.fromgregorian(date=day)
        actual = JalaliDate.from_gregorian(day)
        assert (actual.year, actual.month, actual.day) == (
            expected.year,
            expected.month,
            expected.day,
        ), day
        assert actual.to_gregorian() == day
        day += timedelta(days=1)
        checked += 1
    assert checked > 73_000


@pytest.mark.parametrize(
    ("gregorian", "jalali"),
    [
        (date(2026, 10, 1), "1405/07/09"),
        (date(2026, 3, 21), "1405/01/01"),
        (date(2025, 3, 20), "1403/12/30"),  # 1403 is a leap year
        (date(1979, 2, 11), "1357/11/22"),
    ],
)
def test_known_dates(gregorian: date, jalali: str) -> None:
    assert str(JalaliDate.from_gregorian(gregorian)) == jalali


@given(st.dates(min_value=date(1900, 1, 1), max_value=date(2400, 12, 31)))
def test_round_trip(day: date) -> None:
    assert JalaliDate.from_gregorian(day).to_gregorian() == day


def test_leap_years_and_month_lengths() -> None:
    assert is_jalali_leap_year(1403)
    assert not is_jalali_leap_year(1404)
    assert jalali_month_length(1404, 1) == 31
    assert jalali_month_length(1404, 7) == 30
    assert jalali_month_length(1404, 12) == 29
    assert jalali_month_length(1403, 12) == 30


@pytest.mark.parametrize(("y", "m", "d"), [(1404, 12, 30), (1404, 13, 1), (1404, 7, 31), (0, 1, 1)])
def test_rejects_nonexistent_dates(y: int, m: int, d: int) -> None:
    with pytest.raises(InvalidJalaliDate):
        JalaliDate(y, m, d)


def test_ordering() -> None:
    assert JalaliDate(1404, 12, 29) < JalaliDate(1405, 1, 1)
