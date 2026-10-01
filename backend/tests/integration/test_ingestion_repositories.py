"""Frontier queue, snapshots and crawl runs against a real Postgres."""

import asyncio
from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fakes.ingestion import page, request
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
