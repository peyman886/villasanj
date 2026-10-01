"""Re-observe calendars and prices for every known listing in one short window (ROADMAP M4).

Comparing platforms needs observations taken close together, so a capture re-fetches the pages
that carry calendars (listing and calendar pages) for every platform at once. Snapshots are
append-only: earlier observations stay, and the newest wins when the catalog is rebuilt.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from villasanj.ingestion.application.ports import FrontierRepository
from villasanj.ingestion.domain.pages import PageKind
from villasanj.ingestion.domain.policy import CrawlPolicy
from villasanj.shared.application.clock import Clock

CAPTURE_KINDS = (PageKind.LISTING, PageKind.CALENDAR)


@dataclass(frozen=True, slots=True)
class CapturePlan:
    platform: str
    requests_by_host: dict[str, int]
    estimated: timedelta  # the busiest host bounds the duration (hosts are paced independently)

    @property
    def requests(self) -> int:
        return sum(self.requests_by_host.values())


class ScenarioCapture:
    def __init__(self, frontier: FrontierRepository, policy: CrawlPolicy, clock: Clock) -> None:
        self._frontier = frontier
        self._policy = policy
        self._clock = clock

    async def plan(self, platform: str) -> CapturePlan:
        hosts = await self._frontier.done_by_host(platform, CAPTURE_KINDS)
        per_request = self._policy.min_delay_seconds + self._policy.jitter_seconds / 2
        busiest = max(hosts.values(), default=0)
        return CapturePlan(platform, hosts, timedelta(seconds=busiest * per_request))

    async def requeue(self, platforms: Sequence[str]) -> dict[str, int]:
        """Queue every finished calendar-bearing page again (the crawl run then fetches them)."""
        now = self._clock.now()
        return {p: await self._frontier.requeue(p, CAPTURE_KINDS, now) for p in platforms}
