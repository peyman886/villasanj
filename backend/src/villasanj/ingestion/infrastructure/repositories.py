"""Postgres repositories for snapshots, the crawl frontier (SKIP LOCKED queue) and crawl runs."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.ingestion.application.ports import (
    CrawlReport,
    FrontierItem,
    FrontierStatus,
)
from villasanj.ingestion.domain.pages import (
    FetchedPage,
    HttpMethod,
    PageKind,
    PageRequest,
    Pairs,
    Snapshot,
)
from villasanj.ingestion.infrastructure.tables import crawl_run, frontier, snapshot
from villasanj.shared.application.blobs import BlobRef
from villasanj.shared.application.clock import Clock


def _pairs(value: Any) -> Pairs:
    return tuple((str(k), str(v)) for k, v in value)


def _frontier_request(row: Any) -> PageRequest:
    return PageRequest(
        platform=row.platform,
        kind=PageKind(row.kind),
        url=row.url,
        method=HttpMethod(row.method),
        body=row.body,
        headers=_pairs(row.headers),
        context=_pairs(row.context),
    )


def _snapshot_request(row: Any) -> PageRequest:
    return PageRequest(
        platform=row.platform,
        kind=PageKind(row.kind),
        url=row.url,
        method=HttpMethod(row.method),
        body=row.request_body,
        headers=_pairs(row.request_headers),
        context=_pairs(row.context),
    )


class PgSnapshotRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, page: FetchedPage, blob: BlobRef, run_id: str | None) -> Snapshot:
        snapshot_id = uuid.uuid4()
        request = page.request
        async with self._engine.begin() as conn:
            await conn.execute(
                snapshot.insert().values(
                    id=snapshot_id,
                    platform=request.platform,
                    request_key=request.key,
                    kind=request.kind.value,
                    method=request.method.value,
                    url=request.url,
                    request_headers=[list(p) for p in request.headers],
                    request_body=request.body,
                    context=[list(p) for p in request.context],
                    status=page.status,
                    final_url=page.final_url,
                    headers=[list(p) for p in page.headers],
                    blob_key=blob.key,
                    size=blob.size,
                    fetcher=page.fetcher,
                    fetched_at=page.fetched_at,
                    run_id=uuid.UUID(run_id) if run_id else None,
                )
            )
        return Snapshot(
            id=str(snapshot_id),
            request=request,
            status=page.status,
            final_url=page.final_url,
            headers=page.headers,
            blob_key=blob.key,
            size=blob.size,
            fetched_at=page.fetched_at,
            fetcher=page.fetcher,
            run_id=run_id,
        )

    async def latest(self, request_key: str) -> Snapshot | None:
        query = (
            select(snapshot)
            .where(snapshot.c.request_key == request_key)
            .order_by(snapshot.c.fetched_at.desc())
            .limit(1)
        )
        async with self._engine.connect() as conn:
            row = (await conn.execute(query)).one_or_none()
        return None if row is None else _snapshot_from(row)

    async def list_for(self, platform: str, kinds: Sequence[PageKind]) -> Sequence[Snapshot]:
        query = (
            select(snapshot)
            .where(snapshot.c.platform == platform, snapshot.c.kind.in_([k.value for k in kinds]))
            .order_by(snapshot.c.fetched_at)
        )
        async with self._engine.connect() as conn:
            return [_snapshot_from(row) for row in await conn.execute(query)]


def _snapshot_from(row: Any) -> Snapshot:
    return Snapshot(
        id=str(row.id),
        request=_snapshot_request(row),
        status=row.status,
        final_url=row.final_url,
        headers=_pairs(row.headers),
        blob_key=row.blob_key,
        size=row.size,
        fetched_at=row.fetched_at,
        fetcher=row.fetcher,
        run_id=str(row.run_id) if row.run_id else None,
    )


class PgFrontierRepository:
    def __init__(self, engine: AsyncEngine, clock: Clock) -> None:
        self._engine = engine
        self._clock = clock

    async def enqueue(self, requests: Sequence[PageRequest], discovered_from: str | None) -> int:
        if not requests:
            return 0
        now = self._clock.now()
        rows = [
            {
                "platform": r.platform,
                "request_key": r.key,
                "kind": r.kind.value,
                "method": r.method.value,
                "url": r.url,
                "body": r.body,
                "headers": [list(p) for p in r.headers],
                "context": [list(p) for p in r.context],
                "status": FrontierStatus.PENDING.value,
                "attempts": 0,
                "next_attempt_at": now,
                "discovered_from": uuid.UUID(discovered_from) if discovered_from else None,
                "created_at": now,
                "updated_at": now,
            }
            for r in {r.key: r for r in requests}.values()
        ]
        statement = (
            insert(frontier)
            .values(rows)
            .on_conflict_do_nothing(index_elements=[frontier.c.request_key])
            .returning(frontier.c.id)
        )
        async with self._engine.begin() as conn:
            return len((await conn.execute(statement)).all())

    async def claim(self, platform: str, now: datetime) -> FrontierItem | None:
        candidate = (
            select(frontier.c.id)
            .where(
                frontier.c.platform == platform,
                frontier.c.status == FrontierStatus.PENDING.value,
                frontier.c.next_attempt_at <= now,
            )
            .order_by(frontier.c.next_attempt_at, frontier.c.id)
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        statement = (
            update(frontier)
            .where(frontier.c.id == candidate)
            .values(status=FrontierStatus.IN_PROGRESS.value, updated_at=now)
            .returning(frontier)
        )
        async with self._engine.begin() as conn:
            row = (await conn.execute(statement)).one_or_none()
        if row is None:
            return None
        return FrontierItem(id=row.id, request=_frontier_request(row), attempts=row.attempts)

    async def complete(self, item: FrontierItem, snapshot_id: str) -> None:
        await self._set(item, FrontierStatus.DONE, snapshot_id=uuid.UUID(snapshot_id))

    async def skip(self, item: FrontierItem, reason: str) -> None:
        await self._set(item, FrontierStatus.SKIPPED, last_error=reason)

    async def give_up(self, item: FrontierItem, reason: str) -> None:
        await self._set(item, FrontierStatus.FAILED, last_error=reason, attempts=item.attempts + 1)

    async def retry_later(self, item: FrontierItem, reason: str, not_before: datetime) -> None:
        await self._set(
            item,
            FrontierStatus.PENDING,
            last_error=reason,
            attempts=item.attempts + 1,
            next_attempt_at=not_before,
        )

    async def release(self, item: FrontierItem) -> None:
        await self._set(item, FrontierStatus.PENDING)

    async def counts(self, platform: str) -> dict[FrontierStatus, int]:
        query = (
            select(frontier.c.status, func.count())
            .where(frontier.c.platform == platform)
            .group_by(frontier.c.status)
        )
        async with self._engine.connect() as conn:
            return {FrontierStatus(status): count for status, count in await conn.execute(query)}

    async def _set(self, item: FrontierItem, status: FrontierStatus, **values: Any) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                update(frontier)
                .where(frontier.c.id == item.id)
                .values(status=status.value, updated_at=self._clock.now(), **values)
            )


class PgCrawlRunRepository:
    def __init__(self, engine: AsyncEngine, clock: Clock) -> None:
        self._engine = engine
        self._clock = clock

    async def start(self, platform: str, live: bool) -> str:
        run_id = uuid.uuid4()
        async with self._engine.begin() as conn:
            await conn.execute(
                crawl_run.insert().values(
                    id=run_id,
                    platform=platform,
                    live=live,
                    status="running",
                    started_at=self._clock.now(),
                )
            )
        return str(run_id)

    async def finish(self, report: CrawlReport) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                update(crawl_run)
                .where(crawl_run.c.id == uuid.UUID(report.run_id))
                .values(status="finished", report=asdict(report), finished_at=self._clock.now())
            )
