"""How well the stored calendars cover each stay scenario (ROADMAP M2 criterion 7)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol

from villasanj.shared.domain.stay import StayScenario


@dataclass(frozen=True, slots=True)
class CoverageCounts:
    listings: int
    covered: int  # listings with an observation for every scenario night
    earliest: datetime | None
    latest: datetime | None


class CoverageQuery(Protocol):
    async def counts(self, platform: str, nights: Sequence[date]) -> CoverageCounts: ...


@dataclass(frozen=True, slots=True)
class ScenarioCoverage:
    platform: str
    scenario: str
    listings: int
    covered: int
    spread: timedelta | None  # time between the oldest and newest observation used

    @property
    def ratio(self) -> float:
        return self.covered / self.listings if self.listings else 0.0


class MeasureScenarioCoverage:
    def __init__(self, query: CoverageQuery) -> None:
        self._query = query

    async def run(
        self, platforms: Sequence[str], scenarios: Sequence[StayScenario]
    ) -> list[ScenarioCoverage]:
        results = []
        for platform in platforms:
            for scenario in scenarios:
                counts = await self._query.counts(platform, list(scenario.stay.nights()))
                spread = (
                    counts.latest - counts.earliest
                    if counts.latest is not None and counts.earliest is not None
                    else None
                )
                results.append(
                    ScenarioCoverage(
                        platform, scenario.slug, counts.listings, counts.covered, spread
                    )
                )
        return results
