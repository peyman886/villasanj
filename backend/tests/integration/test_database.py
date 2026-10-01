"""Migrations, ops repositories and the database probe against a real Postgres (Docker)."""

import asyncio
from decimal import Decimal

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fakes.llm import NOW, FixedClock
from tests.integration.conftest import alembic_config
from villasanj.shared.application.jobs import JobStatus
from villasanj.shared.application.llm.ports import CachedCompletion, CallStatus, LedgerEntry
from villasanj.shared.application.llm.types import LLMTask, TokenUsage, UsageSource
from villasanj.shared.infrastructure.db.repositories import (
    PgJobRepository,
    PgLLMCache,
    PgLLMLedger,
    PgLLMSpendQuery,
)
from villasanj.shared.infrastructure.db.tables import CONTEXT_SCHEMAS, REQUIRED_EXTENSIONS
from villasanj.shared.infrastructure.health_probes import DatabaseProbe

pytestmark = pytest.mark.integration


async def _scalars(engine: AsyncEngine, sql: str) -> set[str]:
    async with engine.connect() as conn:
        return {row[0] for row in await conn.execute(text(sql))}


async def test_baseline_creates_extensions_schemas_and_tables(engine: AsyncEngine) -> None:
    assert set(REQUIRED_EXTENSIONS) <= await _scalars(engine, "SELECT extname FROM pg_extension")
    schemas = await _scalars(engine, "SELECT schema_name FROM information_schema.schemata")
    assert set(CONTEXT_SCHEMAS) <= schemas
    tables = await _scalars(
        engine, "SELECT table_name FROM information_schema.tables WHERE table_schema = 'ops'"
    )
    assert tables == {"job", "llm_cache", "llm_call"}


def test_downgrade_and_upgrade_round_trip(database_url: str) -> None:
    config = alembic_config(database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")


async def test_ledger_sums_per_job_and_in_total(engine: AsyncEngine) -> None:
    ledger = PgLLMLedger(engine)
    base_total = await ledger.spent_total_usd()

    def entry(job_id: str, cost: str, status: CallStatus = CallStatus.OK) -> LedgerEntry:
        return LedgerEntry(
            job_id=job_id,
            task=LLMTask.ER_JUDGE,
            model="m",
            prompt_id="p",
            prompt_version="1",
            attempt=1,
            status=status,
            usage=TokenUsage(10, 5, source=UsageSource.ESTIMATED),
            cost_usd=Decimal(cost),
            latency_ms=3,
            created_at=NOW,
        )

    await asyncio.gather(
        ledger.record(entry("job-a", "0.00000125")),
        ledger.record(entry("job-a", "0.5")),
        ledger.record(entry("job-b", "0", CallStatus.CACHE_HIT)),
    )
    assert await ledger.spent_usd("job-a") == Decimal("0.50000125")
    assert await ledger.spent_usd("job-b") == 0
    assert await ledger.spent_total_usd() - base_total == Decimal("0.50000125")


async def test_cache_round_trip_keeps_first_writer(engine: AsyncEngine) -> None:
    cache = PgLLMCache(engine)
    usage = TokenUsage(100, 20, cached_input_tokens=10, reasoning_tokens=2)
    first = CachedCompletion(text='{"ok": true}', model="m1", usage=usage)
    await cache.put("k" * 64, first, LLMTask.CLAIM_EXTRACTION)
    await cache.put("k" * 64, CachedCompletion("{}", "m2", usage), LLMTask.CLAIM_EXTRACTION)
    assert await cache.get("k" * 64) == first
    assert await cache.get("z" * 64) is None


async def test_jobs_start_and_finish(engine: AsyncEngine) -> None:
    jobs = PgJobRepository(engine, FixedClock())
    ctx = await jobs.start("llm_smoke", Decimal("0.05"), {"fallbacks": "True"})
    await jobs.finish(ctx.job_id, JobStatus.SUCCEEDED)
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT status, budget_usd, params FROM ops.job WHERE id = :id"),
                {"id": ctx.job_id},
            )
        ).one()
    assert (row.status, row.budget_usd, row.params) == (
        "succeeded",
        Decimal("0.05"),
        {"fallbacks": "True"},
    )


async def test_database_probe(engine: AsyncEngine) -> None:
    assert (await DatabaseProbe(engine).check()).detail == "ok"


async def test_spend_report_groups_by_task_and_model(engine: AsyncEngine) -> None:
    model = f"spend-model-{id(engine)}"
    ledger = PgLLMLedger(engine)

    def entry(status: CallStatus, cost: str, source: UsageSource) -> LedgerEntry:
        return LedgerEntry(
            job_id="spend-job",
            task=LLMTask.REVIEW_SUMMARY,
            model=model,
            prompt_id="p",
            prompt_version="1",
            attempt=1,
            status=status,
            usage=TokenUsage(100, 50, reasoning_tokens=20, source=source),
            cost_usd=Decimal(cost),
            latency_ms=3,
            created_at=NOW,
        )

    for status, cost, source in (
        (CallStatus.OK, "0.002", UsageSource.REPORTED),
        (CallStatus.TRUNCATED, "0.003", UsageSource.REPORTED),
        (CallStatus.CACHE_HIT, "0", UsageSource.ESTIMATED),
    ):
        await ledger.record(entry(status, cost, source))
    (row,) = [r for r in await PgLLMSpendQuery(engine).by_task_and_model() if r.model == model]
    assert (row.task, row.calls, row.cache_hits, row.failed, row.estimated) == (
        "review_summary",
        3,
        1,
        1,
        1,
    )
    assert (row.input_tokens, row.output_tokens, row.reasoning_tokens) == (300, 150, 60)
    assert row.cost_usd == Decimal("0.005")
