"""Scenario capture: plan per host, then re-queue only calendar-bearing pages."""

from tests.fakes.ingestion import (
    BASE,
    POLICY,
    REGION,
    InMemoryFrontierRepository,
    SteppingClock,
    World,
    page,
    request,
)
from villasanj.ingestion.application.capture import CAPTURE_KINDS, ScenarioCapture
from villasanj.ingestion.application.ports import FrontierStatus
from villasanj.ingestion.domain.pages import PageKind


async def finished_frontier(clock: SteppingClock) -> InMemoryFrontierRepository:
    frontier = InMemoryFrontierRepository()
    requests = [
        request("/stay/1"),
        request("/stay/2"),
        request("/calendar/1", PageKind.CALENDAR, host="api.example.test"),
        request("/photo/1.jpg", PageKind.PHOTO, host="cdn.example.test"),
        request("/search?page=1", PageKind.SEARCH),
    ]
    await frontier.enqueue(requests, None)
    while (item := await frontier.claim("example", clock.now())) is not None:
        await frontier.complete(item, "00000000-0000-0000-0000-000000000c01")
    return frontier


async def test_plan_counts_calendar_pages_per_host_and_estimates_the_window() -> None:
    clock = SteppingClock()
    capture = ScenarioCapture(await finished_frontier(clock), POLICY, clock)
    plan = await capture.plan("example")
    assert plan.requests_by_host == {"www.example.test": 2, "api.example.test": 1}
    assert plan.requests == 3
    per_request = POLICY.min_delay_seconds + POLICY.jitter_seconds / 2
    assert plan.estimated.total_seconds() == 2 * per_request  # the busiest host


async def test_requeue_touches_only_listing_and_calendar_pages() -> None:
    clock = SteppingClock()
    frontier = await finished_frontier(clock)
    queued = await ScenarioCapture(frontier, POLICY, clock).requeue(["example"])
    assert queued == {"example": 3}
    assert frontier.status_of(f"{BASE}/stay/1") is FrontierStatus.PENDING
    assert frontier.status_of("https://cdn.example.test/photo/1.jpg") is FrontierStatus.DONE
    assert frontier.status_of(f"{BASE}/search?page=1") is FrontierStatus.DONE


async def test_a_capture_run_fetches_the_requeued_pages_only(world: World) -> None:
    world.network.on(f"{BASE}/seed", page(request("/seed", PageKind.SEARCH), body=b"links:/a,/b"))
    world.network.on(f"{BASE}/a", page(request("/a")))
    world.network.on(f"{BASE}/b", page(request("/b")))
    await world.crawl().run(REGION, max_requests=10, live=True)
    before = len(world.network.calls)
    await ScenarioCapture(world.frontier, POLICY, world.clock).requeue(["example"])
    report = await world.crawl().run(REGION, max_requests=10, live=True, kinds=CAPTURE_KINDS)
    fetched = [url for url, _ in world.network.calls[before:]]
    # A new run reads robots.txt again; the search seed and anything else are not refetched.
    assert sorted(fetched) == [f"{BASE}/a", f"{BASE}/b", f"{BASE}/robots.txt"]
    assert report.fetched == 2
