"""Use cases: crawl a platform's frontier, and replay stored snapshots instead of the network."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta

import structlog

from villasanj.ingestion.application.errors import (
    CrawlDisallowed,
    SnapshotNotFound,
    SourceBlocked,
    TransientFetchError,
)
from villasanj.ingestion.application.ports import (
    CrawlReport,
    CrawlRunRepository,
    Fetcher,
    FrontierItem,
    FrontierRepository,
    SnapshotRepository,
    SourceAdapter,
)
from villasanj.ingestion.domain.pages import FetchedPage, PageKind, PageRequest
from villasanj.ingestion.domain.region import Region
from villasanj.shared.application.blobs import BlobStore
from villasanj.shared.application.clock import Clock

log = structlog.get_logger(__name__)

MAX_FETCH_ATTEMPTS = 5
OFFLINE_MISS = "offline-no-snapshot"
BASE_RETRY_DELAY = timedelta(minutes=2)
MAX_RETRY_DELAY = timedelta(hours=1)


class CrawlPlatform:
    def __init__(
        self,
        adapter: SourceAdapter,
        fetcher: Fetcher,
        blobs: BlobStore,
        snapshots: SnapshotRepository,
        frontier: FrontierRepository,
        runs: CrawlRunRepository,
        clock: Clock,
    ) -> None:
        self._adapter = adapter
        self._fetcher = fetcher
        self._blobs = blobs
        self._snapshots = snapshots
        self._frontier = frontier
        self._runs = runs
        self._clock = clock

    @property
    def platform(self) -> str:
        return self._adapter.profile.slug

    async def run(
        self,
        region: Region,
        max_requests: int,
        live: bool,
        kinds: Sequence[PageKind] | None = None,
        after_block: bool = False,
    ) -> CrawlReport:
        """Process the frontier; ``kinds`` restricts the run (e.g. photos on a CDN host).

        A platform that blocked the last live run stays blocked until the owner decides otherwise
        (``after_block=True``): no request is made until then.
        """
        if live and not after_block:
            reason = await self._runs.last_block(self.platform)
            if reason is not None:
                raise SourceBlocked(
                    f"{self.platform} blocked the last live run ({reason}); "
                    "ask the owner before crawling it again"
                )
        run_id = await self._runs.start(self.platform, live)
        report = CrawlReport(run_id=run_id, platform=self.platform, live=live)
        if not kinds or PageKind.SEARCH in kinds or PageKind.SITEMAP in kinds:
            new = await self._frontier.enqueue(self._adapter.seed_requests(region), None)
            report = replace(report, discovered=new)
        unavailable: set[int] = set()  # offline: items with no snapshot, released for a live run
        while report.fetched < max_requests:
            item = await self._frontier.claim(self.platform, self._clock.now(), kinds)
            if item is None:
                break
            if item.id in unavailable:
                await self._frontier.release(item)
                report = replace(report, stop_reason="offline-exhausted")
                break
            report = await self._process(item, region, report)
            if report.stop_reason == OFFLINE_MISS:
                unavailable.add(item.id)
                report = replace(report, stop_reason="frontier-empty")
            if report.stop_reason.startswith("blocked"):
                break
        else:
            report = replace(report, stop_reason="max-requests")
        await self._runs.finish(report)
        log.info("crawl.finished", **_report_fields(report))
        return report

    async def store(self, page: FetchedPage, run_id: str | None) -> str:
        blob = await self._blobs.put(page.body)
        return (await self._snapshots.save(page, blob, run_id)).id

    async def _process(
        self, item: FrontierItem, region: Region, report: CrawlReport
    ) -> CrawlReport:
        try:
            page = await self._fetcher.fetch(item.request)
        except CrawlDisallowed as error:
            await self._frontier.skip(item, str(error))
            return replace(report, skipped=report.skipped + 1)
        except SnapshotNotFound:
            await self._frontier.release(item)
            return replace(report, skipped=report.skipped + 1, stop_reason=OFFLINE_MISS)
        except SourceBlocked as error:
            await self._frontier.release(item)
            return replace(report, stop_reason=f"blocked: {error}")
        except TransientFetchError as error:
            return await self._retry(item, error, report)
        snapshot_id = await self.store(page, report.run_id)
        try:
            discovered = self._adapter.discover(page, region)
        except Exception as error:  # an adapter bug must not lose the stored snapshot
            log.error("crawl.discover_failed", url=page.final_url, error=type(error).__name__)
            await self._frontier.complete(item, snapshot_id)
            return replace(
                report, fetched=report.fetched + 1, discover_errors=report.discover_errors + 1
            )
        new = await self._frontier.enqueue(discovered, snapshot_id)
        await self._frontier.complete(item, snapshot_id)
        return replace(report, fetched=report.fetched + 1, discovered=report.discovered + new)

    async def _retry(
        self, item: FrontierItem, error: TransientFetchError, report: CrawlReport
    ) -> CrawlReport:
        if item.attempts + 1 >= MAX_FETCH_ATTEMPTS:
            await self._frontier.give_up(item, error.code)
            return replace(report, gave_up=report.gave_up + 1)
        backoff = min(MAX_RETRY_DELAY, BASE_RETRY_DELAY * (2**item.attempts))
        if error.retry_after_seconds:
            backoff = max(backoff, timedelta(seconds=error.retry_after_seconds))
        await self._frontier.retry_later(item, error.code, self._clock.now() + backoff)
        return replace(report, retried=report.retried + 1)


class SnapshotReplayFetcher:
    """Offline mode: answer requests from stored snapshots only (zero network)."""

    name = "replay"

    def __init__(self, snapshots: SnapshotRepository, blobs: BlobStore) -> None:
        self._snapshots = snapshots
        self._blobs = blobs

    async def fetch(self, request: PageRequest) -> FetchedPage:
        snapshot = await self._snapshots.latest(request.key)
        if snapshot is None:
            raise SnapshotNotFound(request.url)
        return FetchedPage(
            request=request,
            status=snapshot.status,
            final_url=snapshot.final_url,
            headers=snapshot.headers,
            body=await self._blobs.get(snapshot.blob_key),
            fetched_at=snapshot.fetched_at,
            fetcher=f"replay:{snapshot.fetcher}",
        )


def _report_fields(report: CrawlReport) -> dict[str, object]:
    return {
        "run_id": report.run_id,
        "platform": report.platform,
        "live": report.live,
        "fetched": report.fetched,
        "skipped": report.skipped,
        "retried": report.retried,
        "gave_up": report.gave_up,
        "discovered": report.discovered,
        "discover_errors": report.discover_errors,
        "stop_reason": report.stop_reason,
    }
