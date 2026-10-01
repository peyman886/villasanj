"""Postgres implementation of the crawl metrics queries (read-only)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.ingestion.application.stats import (
    HostTraffic,
    KindProgress,
    ResponseTotals,
    RunSummary,
)

# In _TRAFFIC, gaps of 600 s or more are pauses between runs or retries, not pacing.
_TRAFFIC = text(
    r"""
    WITH hosted AS (
        SELECT platform, substring(url from '^[a-z]+://([^/:]+)') AS host, run_id, status,
               blob_key, size, fetched_at
        FROM ingestion.snapshot
        WHERE run_id IS NOT NULL
    ), s AS (
        SELECT *, extract(epoch FROM fetched_at - lag(fetched_at) OVER (
                   PARTITION BY run_id, host ORDER BY fetched_at)) AS gap
        FROM hosted
    ), blobs AS (
        SELECT platform, host, sum(size) AS stored
        FROM (SELECT DISTINCT ON (platform, host, blob_key) platform, host, blob_key, size FROM s) b
        GROUP BY platform, host
    )
    SELECT s.platform, s.host, count(*) AS responses, max(blobs.stored) AS stored,
           min(fetched_at) AS first, max(fetched_at) AS last,
           min(gap) FILTER (WHERE gap < 600) AS min_gap,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY gap)
               FILTER (WHERE gap < 600) AS median_gap
    FROM s JOIN blobs USING (platform, host)
    GROUP BY s.platform, s.host
    ORDER BY s.platform, s.host
    """
)
_STATUSES = text(
    r"""
    SELECT platform, substring(url from '^[a-z]+://([^/:]+)') AS host, status, count(*) AS n
    FROM ingestion.snapshot WHERE run_id IS NOT NULL
    GROUP BY 1, 2, 3
    """
)
_PROGRESS = text(
    """
    SELECT platform, kind, status, coalesce(last_error, '') AS reason, count(*) AS n
    FROM ingestion.frontier GROUP BY 1, 2, 3, 4
    """
)
_RESPONSES = text(
    """
    WITH newest AS (
        SELECT DISTINCT ON (request_key) platform, kind, request_key, status
        FROM ingestion.snapshot WHERE kind = ANY(:kinds)
        ORDER BY request_key, fetched_at DESC
    ), blobs AS (
        SELECT platform, kind, sum(size) AS stored FROM (
            SELECT DISTINCT ON (platform, kind, blob_key) platform, kind, blob_key, size
            FROM ingestion.snapshot WHERE kind = ANY(:kinds)
        ) b GROUP BY 1, 2
    )
    SELECT n.platform, n.kind, n.status, count(*) AS requests, max(b.stored) AS stored
    FROM newest n JOIN blobs b USING (platform, kind)
    GROUP BY 1, 2, 3
    """
)
_RUNS = text(
    """
    SELECT platform, live, status, started_at, finished_at,
           (report->>'fetched')::int AS fetched, report->>'stop_reason' AS stop_reason
    FROM ingestion.crawl_run ORDER BY started_at DESC LIMIT :limit
    """
)


class PgCrawlStatsQuery:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def traffic(self) -> list[HostTraffic]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(_TRAFFIC)).all()
            statuses: defaultdict[tuple[str, str], dict[int, int]] = defaultdict(dict)
            for row in (await conn.execute(_STATUSES)).all():
                statuses[(row.platform, row.host)][int(row.status)] = int(row.n)
        return [
            HostTraffic(
                platform=row.platform,
                host=row.host,
                responses=int(row.responses),
                statuses=dict(sorted(statuses[(row.platform, row.host)].items())),
                stored_bytes=int(row.stored or 0),
                first=row.first,
                last=row.last,
                min_interval_s=_round(row.min_gap),
                median_interval_s=_round(row.median_gap),
            )
            for row in rows
        ]

    async def progress(self) -> list[KindProgress]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(_PROGRESS)).all()
        statuses: defaultdict[tuple[str, str], dict[str, int]] = defaultdict(dict)
        reasons: defaultdict[tuple[str, str], dict[str, int]] = defaultdict(dict)
        for row in rows:
            key = (row.platform, row.kind)
            statuses[key][row.status] = statuses[key].get(row.status, 0) + int(row.n)
            if row.reason and row.status != "done":
                reasons[key][row.reason] = reasons[key].get(row.reason, 0) + int(row.n)
        return [
            KindProgress(
                platform,
                kind,
                dict(sorted(statuses[(platform, kind)].items())),
                reasons.get((platform, kind), {}),
            )
            for platform, kind in sorted(statuses)
        ]

    async def responses(self, kinds: Sequence[str]) -> list[ResponseTotals]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(_RESPONSES, {"kinds": list(kinds)})).all()
        by_key: defaultdict[tuple[str, str], dict[int, int]] = defaultdict(dict)
        stored: dict[tuple[str, str], int] = {}
        for row in rows:
            by_key[(row.platform, row.kind)][int(row.status)] = int(row.requests)
            stored[(row.platform, row.kind)] = int(row.stored or 0)
        return [
            ResponseTotals(
                platform,
                kind,
                dict(sorted(by_key[(platform, kind)].items())),
                stored[(platform, kind)],
            )
            for platform, kind in sorted(by_key)
        ]

    async def runs(self, limit: int) -> list[RunSummary]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(_RUNS, {"limit": limit})).all()
        return [
            RunSummary(
                r.platform, r.live, r.status, r.started_at, r.finished_at, r.fetched, r.stop_reason
            )
            for r in rows
        ]


def _round(value: float | Decimal | None) -> float | None:
    return round(float(value), 2) if value is not None else None
