"""Frontier queue, snapshots and crawl runs against a real Postgres."""

import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fakes.ingestion import SteppingClock, page, request
from tests.fakes.llm import NOW, FixedClock
from villasanj.ingestion.application.ports import CrawlReport, FrontierStatus
from villasanj.ingestion.domain.pages import PageKind, PageRequest
from villasanj.ingestion.infrastructure.repositories import (
    PgCrawlRunRepository,
    PgFrontierRepository,
    PgSnapshotRepository,
)
from villasanj.shared.application.blobs import BlobRef

pytestmark = pytest.mark.integration


def unique(path: str) -> PageRequest:
    """Paths are made unique per test run because the database is shared by the session."""
    return request(f"/{id(path)}-{path}")


async def test_enqueue_deduplicates_and_claims_in_order(engine: AsyncEngine) -> None:
    frontier = PgFrontierRepository(engine, FixedClock())
    first, second = unique("a"), unique("b")
    assert await frontier.enqueue([first, second, first], None) == 2
    assert await frontier.enqueue([first], None) == 0
    claimed = await frontier.claim(first.platform, NOW)
    assert claimed is not None
    assert claimed.request == first
    await frontier.complete(claimed, "00000000-0000-0000-0000-000000000001")


async def test_enqueue_handles_more_rows_than_one_statement_can_bind(engine: AsyncEngine) -> None:
    frontier = PgFrontierRepository(engine, FixedClock())
    many = [unique(f"bulk-{n}") for n in range(5_000)]  # 5,000 x 14 columns > 65,535 parameters
    assert await frontier.enqueue(many, None) == len(many)
    assert await frontier.enqueue(many, None) == 0


async def test_only_stale_claims_are_released(engine: AsyncEngine) -> None:
    clock = SteppingClock()
    frontier = PgFrontierRepository(engine, clock)
    item = unique("stale")
    await frontier.enqueue([item], None)
    claimed = await frontier.claim(item.platform, clock.now())  # the claim time is "now"
    assert claimed is not None
    assert await frontier.release_stale(item.platform, clock.now() - timedelta(minutes=10)) == 0
    clock.advance(11 * 60)
    assert await frontier.release_stale(item.platform, clock.now() - timedelta(minutes=10)) >= 1
    again = await frontier.claim(item.platform, clock.now())
    assert again is not None


async def test_requeue_brings_back_only_finished_pages_of_the_given_kinds(
    engine: AsyncEngine,
) -> None:
    clock = SteppingClock()
    frontier = PgFrontierRepository(engine, clock)
    platform = f"capture-{id(engine)}"
    pages = [
        PageRequest(platform, PageKind.LISTING, f"https://www.capture.test/stay/{id(engine)}"),
        PageRequest(platform, PageKind.CALENDAR, f"https://api.capture.test/cal/{id(engine)}"),
        PageRequest(platform, PageKind.PHOTO, f"https://cdn.capture.test/{id(engine)}.jpg"),
    ]
    await frontier.enqueue(pages, None)
    while (item := await frontier.claim(platform, clock.now())) is not None:
        await frontier.complete(item, "00000000-0000-0000-0000-000000000c02")
    kinds = [PageKind.LISTING, PageKind.CALENDAR]
    assert await frontier.done_by_host(platform, kinds) == {
        "www.capture.test": 1,
        "api.capture.test": 1,
    }
    assert await frontier.requeue(platform, kinds, clock.now()) == 2
    counts = await frontier.counts(platform)
    assert (counts[FrontierStatus.PENDING], counts[FrontierStatus.DONE]) == (2, 1)
    assert await frontier.done_by_host(platform, kinds) == {}


async def test_concurrent_claims_never_hand_out_the_same_item(engine: AsyncEngine) -> None:
    frontier = PgFrontierRepository(engine, FixedClock())
    platform = f"concurrency-{id(engine)}"
    requests = [
        PageRequest(platform, PageKind.LISTING, f"https://www.example.test/c/{i}")
        for i in range(10)
    ]
    await frontier.enqueue(requests, None)
    claims = await asyncio.gather(*(frontier.claim(platform, NOW) for _ in range(12)))
    ids = [c.id for c in claims if c is not None]
    assert len(ids) == 10
    assert len(set(ids)) == 10


async def test_retry_later_hides_items_until_due(engine: AsyncEngine) -> None:
    frontier = PgFrontierRepository(engine, FixedClock())
    platform = f"retry-{id(engine)}"
    req = PageRequest(platform, PageKind.LISTING, "https://www.example.test/retry")
    await frontier.enqueue([req], None)
    item = await frontier.claim(platform, NOW)
    assert item is not None
    await frontier.retry_later(item, "timeout", NOW + timedelta(minutes=5))
    assert await frontier.claim(platform, NOW) is None
    again = await frontier.claim(platform, NOW + timedelta(minutes=6))
    assert again is not None
    assert again.attempts == 1
    await frontier.give_up(again, "timeout")
    assert await frontier.counts(platform) == {FrontierStatus.FAILED: 1}


async def test_snapshots_round_trip_and_latest_wins(engine: AsyncEngine) -> None:
    snapshots = PgSnapshotRepository(engine)
    req = PageRequest(
        f"snap-{id(engine)}",
        PageKind.CALENDAR,
        "https://api.example.test/cal",
        headers=(("accept", "application/json"),),
        context=(("listing_code", "42"),),
    )
    older = page(req, body=b"old")
    newer = replace(page(req, body=b"new"), fetched_at=NOW + timedelta(hours=1))
    first = await snapshots.save(older, BlobRef("a" * 64, 3), None)
    second = await snapshots.save(newer, BlobRef("b" * 64, 3), None)
    latest = await snapshots.latest(req.key)
    assert latest is not None
    assert latest.id == second.id != first.id
    assert latest.request == req
    listed = await snapshots.list_for(req.platform, [PageKind.CALENDAR])
    assert [s.id for s in listed] == [first.id, second.id]


async def test_crawl_runs_record_their_report(engine: AsyncEngine) -> None:
    runs = PgCrawlRunRepository(engine, FixedClock())
    run_id = await runs.start("example", live=False)
    await runs.finish(CrawlReport(run_id=run_id, platform="example", live=False, fetched=3))


async def test_a_blocked_live_run_is_remembered_until_a_later_run_finishes(
    engine: AsyncEngine,
) -> None:
    platform = f"blocked-{id(engine)}"
    clock = SteppingClock()
    runs = PgCrawlRunRepository(engine, clock)
    assert await runs.last_block(platform) is None
    blocked = await runs.start(platform, live=True)
    await runs.finish(
        CrawlReport(run_id=blocked, platform=platform, live=True, stop_reason="blocked: 3 x 403")
    )
    assert await runs.last_block(platform) == "blocked: 3 x 403"
    clock.advance(60)
    offline = await runs.start(platform, live=False)
    await runs.finish(CrawlReport(run_id=offline, platform=platform, live=False))
    assert await runs.last_block(platform) == "blocked: 3 x 403"  # replays do not clear it
    clock.advance(60)
    resumed = await runs.start(platform, live=True)
    await runs.finish(CrawlReport(run_id=resumed, platform=platform, live=True))
    assert await runs.last_block(platform) is None
