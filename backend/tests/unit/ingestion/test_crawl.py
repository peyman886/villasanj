"""CrawlPlatform over in-memory ports: frontier lifecycle, retries, blocking, offline replay."""

from datetime import timedelta

import pytest

from tests.fakes.ingestion import (
    BASE,
    PLATFORM,
    POLICY,
    PROFILE,
    REGION,
    InMemoryBlobStore,
    InMemoryCrawlRunRepository,
    InMemoryFrontierRepository,
    InMemorySnapshotRepository,
    LinkFollowingAdapter,
    ScriptedFetcher,
    SteppingClock,
    page,
    request,
)
from villasanj.ingestion.application.crawl import (
    MAX_FETCH_ATTEMPTS,
    CrawlPlatform,
    SnapshotReplayFetcher,
)
from villasanj.ingestion.application.errors import SourceBlocked, TransientFetchError
from villasanj.ingestion.application.polite_fetcher import PoliteFetcher
from villasanj.ingestion.application.ports import Fetcher, FrontierStatus
from villasanj.ingestion.domain.pages import PageKind
from villasanj.ingestion.infrastructure.http import ProtegoRobotsParser


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


@pytest.fixture
def world() -> World:
    return World()


async def test_seed_fetch_discover_store(world: World) -> None:
    world.network.on(f"{BASE}/seed", page(request("/seed"), body=b"links:/a,/b,/a"))
    world.network.on(f"{BASE}/a", page(request("/a"), body=b"links:/b"))
    world.network.on(f"{BASE}/b", page(request("/b"), body=b"leaf"))
    report = await world.crawl().run(REGION, max_requests=10, live=True)
    assert (report.fetched, report.discovered, report.stop_reason) == (3, 3, "frontier-empty")
    assert [s.request.url for s in world.snapshots.snapshots] == [
        f"{BASE}/seed",
        f"{BASE}/a",
        f"{BASE}/b",
    ]
    assert world.blobs.blobs[world.snapshots.snapshots[-1].blob_key] == b"leaf"
    assert world.runs.finished == [report]


async def test_max_requests_bounds_a_run(world: World) -> None:
    world.network.on(f"{BASE}/seed", page(request("/seed"), body=b"links:/a,/b"))
    report = await world.crawl().run(REGION, max_requests=1, live=True)
    assert (report.fetched, report.stop_reason) == (1, "max-requests")
    assert world.frontier.status_of(f"{BASE}/a") is FrontierStatus.PENDING


async def test_robots_disallowed_items_are_skipped(world: World) -> None:
    world.network.robots = "User-agent: *\nDisallow: /a\n"
    world.network.on(f"{BASE}/seed", page(request("/seed"), body=b"links:/a"))
    report = await world.crawl().run(REGION, max_requests=10, live=True)
    assert report.skipped == 1
    assert world.frontier.status_of(f"{BASE}/a") is FrontierStatus.SKIPPED


async def test_blocking_stops_the_run_and_keeps_the_item(world: World) -> None:
    world.network.on(f"{BASE}/seed", page(request("/seed"), body=b"links:/a,/b"))
    world.network.on(f"{BASE}/a", page(request("/a"), body=b'<i class="h-captcha"></i>'))
    report = await world.crawl().run(REGION, max_requests=10, live=True)
    assert report.stop_reason.startswith("blocked")
    assert world.frontier.status_of(f"{BASE}/a") is FrontierStatus.PENDING
    assert f"{BASE}/b" not in world.network.urls()


async def test_a_blocked_platform_stays_blocked_until_the_owner_decides(world: World) -> None:
    challenge = page(request("/seed"), body=b'<i class="h-captcha"></i>')
    world.network.on(f"{BASE}/seed", challenge, page(request("/seed")))
    crawl = world.crawl()
    await crawl.run(REGION, max_requests=10, live=True)
    calls = len(world.network.calls)
    with pytest.raises(SourceBlocked, match="ask the owner"):
        await crawl.run(REGION, max_requests=10, live=True)
    assert len(world.network.calls) == calls  # refused before any request
    await crawl.run(REGION, max_requests=10, live=False)  # replay is unaffected
    resumed = await crawl.run(REGION, max_requests=10, live=True, after_block=True)
    assert resumed.stop_reason == "frontier-empty"


async def test_items_left_in_progress_by_a_crashed_run_are_recovered(world: World) -> None:
    world.network.on(f"{BASE}/seed", page(request("/seed")))
    await world.frontier.enqueue([request("/seed", PageKind.SEARCH)], None)
    abandoned = await world.frontier.claim(PLATFORM, world.clock.now())  # the crash happened here
    assert abandoned is not None
    world.clock.advance(5 * 60)  # 5 minutes later: maybe still running, leave it alone
    early = await world.crawl().run(REGION, max_requests=10, live=True)
    assert early.recovered == 0
    world.clock.advance(10 * 60)
    report = await world.crawl().run(REGION, max_requests=10, live=True)
    assert report.recovered == 1
    assert world.frontier.status_of(f"{BASE}/seed") is FrontierStatus.DONE


async def test_transient_errors_back_off_then_give_up(world: World) -> None:
    world.network.on(f"{BASE}/seed", TransientFetchError("timeout"))
    crawl = world.crawl()
    first = await crawl.run(REGION, max_requests=10, live=True)
    assert first.retried == 1
    row = next(iter(world.frontier.rows.values()))
    assert row.not_before == world.clock.now() + timedelta(minutes=2)
    for _ in range(MAX_FETCH_ATTEMPTS):
        world.clock.advance(3600)
        await crawl.run(REGION, max_requests=10, live=True)
    assert world.frontier.status_of(f"{BASE}/seed") is FrontierStatus.FAILED


async def test_adapter_bugs_do_not_lose_snapshots(world: World) -> None:
    world.network.on(f"{BASE}/seed", page(request("/seed"), body=b"explode"))
    report = await world.crawl().run(REGION, max_requests=10, live=True)
    assert (report.fetched, report.discover_errors) == (1, 1)
    assert len(world.snapshots.snapshots) == 1


async def test_offline_replay_uses_snapshots_and_never_loops(world: World) -> None:
    world.network.on(f"{BASE}/seed", page(request("/seed"), body=b"links:/a,/b"))
    world.network.on(f"{BASE}/a", page(request("/a"), body=b"leaf-a"))
    await world.crawl().run(REGION, max_requests=2, live=True)  # fetched /seed and /a only

    offline = World()
    offline.blobs, offline.snapshots = world.blobs, world.snapshots
    replay = SnapshotReplayFetcher(offline.snapshots, offline.blobs)
    report = await offline.crawl(fetcher=replay).run(REGION, max_requests=10, live=False)
    assert report.fetched == 2  # /seed and /a replayed from storage
    assert report.stop_reason == "offline-exhausted"
    assert offline.network.calls == []
    assert offline.frontier.status_of(f"{BASE}/b") is FrontierStatus.PENDING
