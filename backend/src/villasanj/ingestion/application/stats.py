"""Crawl metrics from what is stored (ROADMAP M4): traffic per host, queue progress, runs.

Everything here is read from snapshots and the frontier, so the numbers are what actually
happened, including the pacing between requests (the evidence for ADR-0008's politeness rules).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class HostTraffic:
    platform: str
    host: str
    responses: int
    statuses: dict[int, int]
    stored_bytes: int  # distinct blobs (identical bodies are stored once)
    first: datetime | None
    last: datetime | None
    min_interval_s: float | None  # between consecutive requests of one run to this host
    median_interval_s: float | None


@dataclass(frozen=True, slots=True)
class KindProgress:
    platform: str
    kind: str
    statuses: dict[str, int]
    reasons: dict[str, int] = field(default_factory=dict)  # last error of unfinished items


@dataclass(frozen=True, slots=True)
class ResponseTotals:
    platform: str
    kind: str
    requests_by_status: dict[int, int]  # distinct requests whose newest response had this status
    stored_bytes: int


@dataclass(frozen=True, slots=True)
class RunSummary:
    platform: str
    live: bool
    status: str
    started_at: datetime
    finished_at: datetime | None
    fetched: int | None
    stop_reason: str | None


class CrawlStatsQuery(Protocol):
    async def traffic(self) -> list[HostTraffic]: ...

    async def progress(self) -> list[KindProgress]: ...

    async def responses(self, kinds: Sequence[str]) -> list[ResponseTotals]: ...

    async def runs(self, limit: int) -> list[RunSummary]: ...
