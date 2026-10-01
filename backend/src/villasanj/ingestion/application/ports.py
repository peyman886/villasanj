"""Ports of the ingestion context."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from villasanj.ingestion.domain.pages import FetchedPage, PageKind, PageRequest, Snapshot
from villasanj.ingestion.domain.parsed import ParsedCalendar, ParsedListing
from villasanj.ingestion.domain.policy import SourceProfile
from villasanj.ingestion.domain.region import Region
from villasanj.shared.application.blobs import BlobRef


class Fetcher(Protocol):
    """Performs one HTTP exchange. Must not follow redirects (the polite layer checks each hop)."""

    @property
    def name(self) -> str: ...

    async def fetch(self, request: PageRequest) -> FetchedPage: ...


class RobotsRules(Protocol):
    def allows(self, url: str, token: str) -> bool: ...

    def crawl_delay(self, token: str) -> float | None: ...


class RobotsParser(Protocol):
    def parse(self, content: str) -> RobotsRules: ...

    def allow_all(self) -> RobotsRules: ...

    def disallow_all(self) -> RobotsRules: ...


class SourceAdapter(Protocol):
    """Everything platform-specific. Pure: no I/O, so it is contract-testable on stored fixtures."""

    @property
    def profile(self) -> SourceProfile: ...

    def seed_requests(self, region: Region) -> Sequence[PageRequest]:
        """Entry points for a region (sitemaps, city pages)."""
        ...

    def discover(self, page: FetchedPage, region: Region) -> Sequence[PageRequest]:
        """Follow-up requests found in a fetched page (pagination, listings, calendars)."""
        ...

    def parse_listing(self, page: FetchedPage) -> ParsedListing | None:
        """The listing on a listing page; ``None`` for other kinds or unusable pages.

        Raises ``PageStructureChanged`` when a listing page no longer has the expected shape.
        """
        ...

    def parse_calendar(self, page: FetchedPage) -> ParsedCalendar | None:
        """A calendar served on its own page; ``None`` when the platform embeds it elsewhere."""
        ...


class SnapshotRepository(Protocol):
    async def save(self, page: FetchedPage, blob: BlobRef, run_id: str | None) -> Snapshot: ...

    async def latest(self, request_key: str) -> Snapshot | None: ...

    async def list_for(self, platform: str, kinds: Sequence[PageKind]) -> Sequence[Snapshot]: ...


class FrontierStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class FrontierItem:
    id: int
    request: PageRequest
    attempts: int


class FrontierRepository(Protocol):
    async def enqueue(self, requests: Sequence[PageRequest], discovered_from: str | None) -> int:
        """Add requests not seen before; returns how many were new."""
        ...

    async def claim(
        self, platform: str, now: datetime, kinds: Sequence[PageKind] | None = None
    ) -> FrontierItem | None: ...

    async def complete(self, item: FrontierItem, snapshot_id: str) -> None: ...

    async def skip(self, item: FrontierItem, reason: str) -> None: ...

    async def retry_later(self, item: FrontierItem, reason: str, not_before: datetime) -> None: ...

    async def give_up(self, item: FrontierItem, reason: str) -> None: ...

    async def release(self, item: FrontierItem) -> None:
        """Return an item to the queue untouched (e.g. the run stopped because we were blocked)."""
        ...

    async def release_stale(self, platform: str, claimed_before: datetime) -> int:
        """Return items left in progress by a crashed run (claimed before the cut-off)."""
        ...

    async def done_by_host(self, platform: str, kinds: Sequence[PageKind]) -> dict[str, int]:
        """Finished items of these kinds, per host (input to a re-capture estimate)."""
        ...

    async def requeue(self, platform: str, kinds: Sequence[PageKind], now: datetime) -> int:
        """Put finished items of these kinds back in the queue, to observe them again."""
        ...

    async def counts(self, platform: str) -> dict[FrontierStatus, int]: ...


@dataclass(frozen=True, slots=True)
class CrawlReport:
    run_id: str
    platform: str
    live: bool
    fetched: int = 0
    skipped: int = 0
    retried: int = 0
    gave_up: int = 0
    discovered: int = 0
    discover_errors: int = 0
    recovered: int = 0  # items a crashed earlier run had left in progress
    stop_reason: str = "frontier-empty"


class CrawlRunRepository(Protocol):
    async def start(self, platform: str, live: bool) -> str: ...

    async def finish(self, report: CrawlReport) -> None: ...

    async def last_block(self, platform: str) -> str | None:
        """Stop reason of the platform's latest live run if that run ended blocked."""
        ...
