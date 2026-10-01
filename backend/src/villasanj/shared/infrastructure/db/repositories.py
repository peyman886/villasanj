"""Postgres implementations of the ops ports: jobs, LLM ledger and LLM cache."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.shared.application.clock import Clock
from villasanj.shared.application.jobs import JobStatus
from villasanj.shared.application.llm.ports import CachedCompletion, LedgerEntry
from villasanj.shared.application.llm.types import JobContext, LLMTask, TokenUsage, UsageSource
from villasanj.shared.infrastructure.db.tables import job, llm_cache, llm_call


class PgJobRepository:
    def __init__(self, engine: AsyncEngine, clock: Clock) -> None:
        self._engine = engine
        self._clock = clock

    async def start(self, kind: str, budget_usd: Decimal, params: Mapping[str, str]) -> JobContext:
        job_id = uuid.uuid4()
        async with self._engine.begin() as conn:
            await conn.execute(
                job.insert().values(
                    id=job_id,
                    kind=kind,
                    params=dict(params),
                    budget_usd=budget_usd,
                    status=JobStatus.RUNNING.value,
                    started_at=self._clock.now(),
                )
            )
        return JobContext(job_id=str(job_id), budget_usd=budget_usd)

    async def finish(self, job_id: str, status: JobStatus) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                update(job)
                .where(job.c.id == uuid.UUID(job_id))
                .values(status=status.value, finished_at=self._clock.now())
            )


class PgLLMLedger:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record(self, entry: LedgerEntry) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                llm_call.insert().values(
                    job_id=entry.job_id,
                    task=entry.task.value,
                    model=entry.model,
                    prompt_id=entry.prompt_id,
                    prompt_version=entry.prompt_version,
                    attempt=entry.attempt,
                    status=entry.status.value,
                    input_tokens=entry.usage.input_tokens,
                    cached_input_tokens=entry.usage.cached_input_tokens,
                    output_tokens=entry.usage.output_tokens,
                    reasoning_tokens=entry.usage.reasoning_tokens,
                    usage_source=entry.usage.source.value,
                    cost_usd=entry.cost_usd,
                    latency_ms=entry.latency_ms,
                    error_code=entry.error_code,
                    created_at=entry.created_at,
                )
            )

    async def spent_usd(self, job_id: str) -> Decimal:
        return await self._sum(job_id)

    async def spent_total_usd(self) -> Decimal:
        return await self._sum(None)

    async def _sum(self, job_id: str | None) -> Decimal:
        query = select(func.coalesce(func.sum(llm_call.c.cost_usd), 0))
        if job_id is not None:
            query = query.where(llm_call.c.job_id == job_id)
        async with self._engine.connect() as conn:
            return Decimal((await conn.execute(query)).scalar_one())


class PgLLMCache:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def get(self, key: str) -> CachedCompletion | None:
        query = select(llm_cache.c.response_text, llm_cache.c.model, llm_cache.c.usage).where(
            llm_cache.c.key == key
        )
        async with self._engine.connect() as conn:
            row = (await conn.execute(query)).one_or_none()
        if row is None:
            return None
        return CachedCompletion(text=row.response_text, model=row.model, usage=_usage(row.usage))

    async def put(self, key: str, completion: CachedCompletion, task: LLMTask) -> None:
        statement = (
            insert(llm_cache)
            .values(
                key=key,
                task=task.value,
                model=completion.model,
                response_text=completion.text,
                usage=_usage_json(completion.usage),
            )
            .on_conflict_do_nothing(index_elements=[llm_cache.c.key])
        )
        async with self._engine.begin() as conn:
            await conn.execute(statement)


def _usage_json(usage: TokenUsage) -> dict[str, int | str]:
    return {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cached_input_tokens": usage.cached_input_tokens,
        "reasoning_tokens": usage.reasoning_tokens,
        "source": usage.source.value,
    }


def _usage(data: Mapping[str, int | str]) -> TokenUsage:
    return TokenUsage(
        input_tokens=int(data["input_tokens"]),
        output_tokens=int(data["output_tokens"]),
        cached_input_tokens=int(data["cached_input_tokens"]),
        reasoning_tokens=int(data["reasoning_tokens"]),
        source=UsageSource(str(data["source"])),
    )
