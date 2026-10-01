"""Load ``config/holidays.toml``: fixed solar holidays and which platforms flag public holidays."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from villasanj.discovery.application.dates import HolidaySources
from villasanj.discovery.domain.dates import FixedHoliday
from villasanj.shared.application.errors import ConfigurationError


class _Holiday(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: int
    day: int
    name_fa: str


class _HolidaysFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    observed_from: list[str]
    holidays: list[_Holiday]


def load_holiday_sources(path: Path) -> HolidaySources:
    try:
        with path.open("rb") as handle:
            data = _HolidaysFile.model_validate(tomllib.load(handle))
        fixed = tuple(FixedHoliday(h.month, h.day, h.name_fa) for h in data.holidays)
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        raise ConfigurationError(f"invalid holidays file {path}: {error}") from None
    return HolidaySources(fixed, data.source, frozenset(data.observed_from))
