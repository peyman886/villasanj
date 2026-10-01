"""In-memory fakes for the ingestion ports, plus a clock that only moves when the code sleeps."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from tests.fakes.llm import NOW
from villasanj.ingestion.application.crawl import CrawlPlatform
from villasanj.ingestion.application.polite_fetcher import PoliteFetcher
from villasanj.ingestion.application.ports import (
    CrawlReport,
    Fetcher,
    FrontierItem,
    FrontierStatus,
)
from villasanj.ingestion.domain.pages import FetchedPage, PageKind, PageRequest, Snapshot
from villasanj.ingestion.domain.parsed import ParsedCalendar, ParsedListing
from villasanj.ingestion.domain.policy import CrawlPolicy, SourceProfile
from villasanj.ingestion.domain.region import Place, Region
from villasanj.ingestion.infrastructure.http import ProtegoRobotsParser
from villasanj.shared.application.blobs import BlobRef
from villasanj.shared.domain.geo import GeoPoint

PLATFORM = "example"
HOST = "www.example.test"
BASE = f"https://{HOST}"
POLICY = CrawlPolicy(user_agent="VillasanjBot/0.1 (test)", robots_token="VillasanjBot")
PROFILE = SourceProfile(
    slug=PLATFORM,
    display_name="Example",
    base_url=BASE,
    allowed_hosts=frozenset({HOST, "cdn.example.test"}),
    terms_url=f"{BASE}/terms",
)
REGION = Region(
    slug="test-region",
    name_fa="منطقه",
    places=(Place("town", "شهر"),),
    south_west=GeoPoint(36.5, 50.3),
    north_east=GeoPoint(37.1, 51.1),
)


class SteppingClock:
    """Time advances only through ``sleep`` (and explicit ``advance``), so pacing is measurable."""

    def __init__(self, start: datetime = NOW) -> None:
        self.current = start
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self.current

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += timedelta(seconds=seconds)

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


type Reply = FetchedPage | Exception | Callable[[PageRequest], FetchedPage]


def page(
    request: PageRequest,
    status: int = 200,
    body: bytes = b"ok",
    content_type: str = "text/html",
    headers: Sequence[tuple[str, str]] = (),
) -> FetchedPage:
    return FetchedPage(
        request=request,
        status=status,
        final_url=request.url,
        headers=(("content-type", content_type), *headers),
        body=body,
        fetched_at=NOW,
        fetcher="scripted",
    )


@dataclass
class ScriptedFetcher:
    """Answers by URL. ``robots`` is the robots.txt body (or a status code) for every origin."""

    clock: SteppingClock
    replies: dict[str, list[Reply]] = field(default_factory=dict)
    robots: str | int = "User-agent: *\nAllow: /\n"
    calls: list[tuple[str, datetime]] = field(default_factory=list)
    name: str = "scripted"

    def on(self, url: str, *replies: Reply) -> None:
        self.replies.setdefault(url, []).extend(replies)

    async def fetch(self, request: PageRequest) -> FetchedPage:
        self.calls.append((request.url, self.clock.now()))
        if request.url.endswith("/robots.txt") and request.url not in self.replies:
            if isinstance(self.robots, int):
                return page(request, status=self.robots, body=b"", content_type="text/plain")
            return page(request, body=self.robots.encode(), content_type="text/plain")
        queue = self.replies.get(request.url)
        if not queue:
            return page(request, status=404, body=b"not found")
        reply = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            return reply(request)
        return reply

    def urls(self) -> list[str]:
        return [url for url, _ in self.calls]


class InMemoryBlobStore:
    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    async def put(self, data: bytes) -> BlobRef:
        import hashlib

        key = hashlib.sha256(data).hexdigest()
        self.blobs[key] = data
        return BlobRef(key=key, size=len(data))

    async def get(self, key: str) -> bytes:
        return self.blobs[key]

    async def exists(self, key: str) -> bool:
        return key in self.blobs


class InMemorySnapshotRepository:
    def __init__(self) -> None:
        self.snapshots: list[Snapshot] = []

    async def save(self, page: FetchedPage, blob: BlobRef, run_id: str | None) -> Snapshot:
        snapshot = Snapshot(
            id=str(uuid.uuid4()),
            request=page.request,
            status=page.status,
            final_url=page.final_url,
            headers=page.headers,
            blob_key=blob.key,
            size=blob.size,
            fetched_at=page.fetched_at,
            fetcher=page.fetcher,
            run_id=run_id,
        )
        self.snapshots.append(snapshot)
        return snapshot

    async def latest(self, request_key: str) -> Snapshot | None:
        matches = [s for s in self.snapshots if s.request.key == request_key]
        return matches[-1] if matches else None

    async def list_for(self, platform: str, kinds: Sequence[PageKind]) -> Sequence[Snapshot]:
        return [
            s for s in self.snapshots if s.request.platform == platform and s.request.kind in kinds
        ]


@dataclass
class _Row:
    item: FrontierItem
    status: FrontierStatus
    not_before: datetime
    reason: str | None = None
    claimed_at: datetime | None = None


class InMemoryFrontierRepository:
    def __init__(self) -> None:
        self.rows: dict[str, _Row] = {}
        self._next_id = 1

    async def enqueue(self, requests: Sequence[PageRequest], discovered_from: str | None) -> int:
        new = 0
        for request in requests:
            if request.key in self.rows:
                continue
            item = FrontierItem(id=self._next_id, request=request, attempts=0)
            self.rows[request.key] = _Row(item, FrontierStatus.PENDING, NOW - timedelta(days=1))
            self._next_id += 1
            new += 1
        return new

    async def claim(
        self, platform: str, now: datetime, kinds: Sequence[PageKind] | None = None
    ) -> FrontierItem | None:
        for row in sorted(self.rows.values(), key=lambda r: (r.not_before, r.item.id)):
            if kinds and row.item.request.kind not in kinds:
                continue
            if row.status is FrontierStatus.PENDING and row.not_before <= now:
                row.status = FrontierStatus.IN_PROGRESS
                row.claimed_at = now
                return row.item
        return None

    async def complete(self, item: FrontierItem, snapshot_id: str) -> None:
        self.rows[item.request.key].status = FrontierStatus.DONE

    async def skip(self, item: FrontierItem, reason: str) -> None:
        row = self.rows[item.request.key]
        row.status, row.reason = FrontierStatus.SKIPPED, reason

    async def give_up(self, item: FrontierItem, reason: str) -> None:
        row = self.rows[item.request.key]
        row.status, row.reason = FrontierStatus.FAILED, reason

    async def retry_later(self, item: FrontierItem, reason: str, not_before: datetime) -> None:
        row = self.rows[item.request.key]
        row.item = FrontierItem(item.id, item.request, item.attempts + 1)
        row.status, row.reason, row.not_before = FrontierStatus.PENDING, reason, not_before

    async def release(self, item: FrontierItem) -> None:
        self.rows[item.request.key].status = FrontierStatus.PENDING

    async def done_by_host(self, platform: str, kinds: Sequence[PageKind]) -> dict[str, int]:
        hosts: dict[str, int] = {}
        for row in self.rows.values():
            request = row.item.request
            if (
                request.platform == platform
                and request.kind in kinds
                and row.status is FrontierStatus.DONE
            ):
                hosts[request.host] = hosts.get(request.host, 0) + 1
        return hosts

    async def requeue(self, platform: str, kinds: Sequence[PageKind], now: datetime) -> int:
        count = 0
        for row in self.rows.values():
            request = row.item.request
            if (
                request.platform == platform
                and request.kind in kinds
                and row.status is FrontierStatus.DONE
            ):
                row.status, row.not_before, count = FrontierStatus.PENDING, now, count + 1
        return count

    async def release_stale(self, platform: str, claimed_before: datetime) -> int:
        stale = [
            row
            for row in self.rows.values()
            if row.item.request.platform == platform
            and row.status is FrontierStatus.IN_PROGRESS
            and row.claimed_at is not None
            and row.claimed_at < claimed_before
        ]
        for row in stale:
            row.status = FrontierStatus.PENDING
        return len(stale)

    async def counts(self, platform: str) -> dict[FrontierStatus, int]:
        result: dict[FrontierStatus, int] = {}
        for row in self.rows.values():
            result[row.status] = result.get(row.status, 0) + 1
        return result

    def status_of(self, url: str) -> FrontierStatus:
        return next(r.status for r in self.rows.values() if r.item.request.url == url)


class InMemoryCrawlRunRepository:
    def __init__(self) -> None:
        self.finished: list[CrawlReport] = []

    async def start(self, platform: str, live: bool) -> str:
        return str(uuid.uuid4())

    async def finish(self, report: CrawlReport) -> None:
        self.finished.append(report)

    async def last_block(self, platform: str) -> str | None:
        live = [r for r in self.finished if r.platform == platform and r.live]
        if live and live[-1].stop_reason.startswith("blocked"):
            return live[-1].stop_reason
        return None


def request(path: str, kind: PageKind = PageKind.LISTING, host: str = HOST) -> PageRequest:
    return PageRequest(platform=PLATFORM, kind=kind, url=f"https://{host}{path}")


class LinkFollowingAdapter:
    """Seeds ``/seed``; a page body like ``links:/a,/b`` discovers those paths."""

    profile = PROFILE

    def seed_requests(self, region: Region) -> Sequence[PageRequest]:
        return [request("/seed", PageKind.SEARCH)]

    def discover(self, page: FetchedPage, region: Region) -> Sequence[PageRequest]:
        text = page.body.decode()
        if text == "explode":
            raise ValueError("adapter bug")
        if not text.startswith("links:"):
            return []
        return [request(path) for path in text.removeprefix("links:").split(",") if path]

    def parse_listing(self, page: FetchedPage) -> ParsedListing | None:
        return None

    def parse_calendar(self, page: FetchedPage) -> ParsedCalendar | None:
        return None


# A whole crawl over in-memory ports, with a scripted network and a clock that moves on sleep.
class World:
    def __init__(self) -> None:
        self.clock = SteppingClock()
        self.network = ScriptedFetcher(self.clock)
        self.blobs = InMemoryBlobStore()
        self.snapshots = InMemorySnapshotRepository()
        self.frontier = InMemoryFrontierRepository()
        self.runs = InMemoryCrawlRunRepository()

    def polite(self) -> PoliteFetcher:
        return PoliteFetcher(
            self.network,
            ProtegoRobotsParser(),
            POLICY,
            {PROFILE.slug: PROFILE},
            self.clock,
            self.clock.sleep,
            jitter=lambda: 0.0,
        )

    def crawl(self, fetcher: Fetcher | None = None) -> CrawlPlatform:
        return CrawlPlatform(
            LinkFollowingAdapter(),
            fetcher or self.polite(),
            self.blobs,
            self.snapshots,
            self.frontier,
            self.runs,
            self.clock,
        )
