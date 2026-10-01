"""The holiday calendar from config and observed platform flags."""

from datetime import date, timedelta
from pathlib import Path

import pytest

from tests.fakes.llm import NOW
from villasanj.catalog.application.reading import HolidayFlags
from villasanj.discovery.application.dates import BuildHolidayCalendar, HolidaySources
from villasanj.discovery.domain.dates import FixedHoliday, HolidayKind
from villasanj.discovery.infrastructure.holidays import load_holiday_sources
from villasanj.shared.application.errors import ConfigurationError

TODAY = date(2026, 10, 1)
SOURCES = HolidaySources((FixedHoliday(11, 22, "پیروزی انقلاب"),), "config", frozenset({"a"}))


class Flags:
    def __init__(self, rows: list[HolidayFlags]) -> None:
        self.rows = rows
        self.asked: tuple[date, date] | None = None

    async def holiday_flags(self, start: date, end: date) -> list[HolidayFlags]:
        self.asked = (start, end)
        return self.rows


def row(platform: str, night: date, flagged: int, reported: int) -> HolidayFlags:
    return HolidayFlags(platform, night, flagged, reported, NOW)


async def test_only_listed_platforms_with_enough_reports_and_a_clear_majority_count() -> None:
    holiday, ordinary, thin = date(2026, 11, 13), date(2026, 11, 14), date(2026, 12, 20)
    flags = Flags(
        [
            row("a", holiday, 95, 100),
            row("a", ordinary, 3, 100),  # a few hosts' own setting
            row("a", thin, 5, 5),  # too few listings report it
            row("b", ordinary, 100, 100),  # a platform whose flag means something else
        ]
    )
    calendar = await BuildHolidayCalendar(flags, SOURCES).run(TODAY)
    assert flags.asked is not None
    assert flags.asked[0] == TODAY
    assert list(calendar.observed) == [holiday]
    assert calendar.observed[holiday].startswith("a calendar: 95 of 100 listings")
    assert calendar.known_until == ordinary + timedelta(days=1)
    kinds = [h.kind for h in calendar.holidays_on(holiday)]
    assert kinds == [HolidayKind.WEEKLY, HolidayKind.OBSERVED]  # a Friday that is also flagged
    assert calendar.holidays_on(date(2027, 2, 11))[0].name_fa == "پیروزی انقلاب"


async def test_without_observations_lunar_holidays_are_unknown() -> None:
    calendar = await BuildHolidayCalendar(Flags([]), SOURCES).run(TODAY)
    assert calendar.known_until is None
    assert not calendar.lunar_known(TODAY)


def test_the_project_config_loads() -> None:
    path = Path(__file__).parents[4] / "config" / "holidays.toml"
    sources = load_holiday_sources(path)
    assert len(sources.fixed) == 10
    assert all(1 <= h.month <= 12 and 1 <= h.day <= 31 for h in sources.fixed)
    assert sources.observed_from


def test_a_broken_config_is_a_configuration_error(tmp_path: Path) -> None:
    path = tmp_path / "holidays.toml"
    path.write_text('source = "x"\n', encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_holiday_sources(path)
