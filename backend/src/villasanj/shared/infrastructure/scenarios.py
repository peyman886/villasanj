"""Load stay scenarios from ``config/scenarios.toml``."""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from villasanj.shared.application.errors import ConfigurationError
from villasanj.shared.domain.stay import DateRange, GuestCount, StayScenario


class _Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str
    name_fa: str
    check_in: date
    check_out: date


class _ScenariosFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    guests: list[int]
    scenarios: list[_Scenario]


def load_scenarios(path: Path) -> list[StayScenario]:
    try:
        with path.open("rb") as handle:
            data = _ScenariosFile.model_validate(tomllib.load(handle))
        guests = tuple(GuestCount(g) for g in data.guests)
        return [
            StayScenario(s.slug, s.name_fa, DateRange(s.check_in, s.check_out), guests)
            for s in data.scenarios
        ]
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        raise ConfigurationError(f"invalid scenarios file {path}: {error}") from None
