"""Cost governor: refuses calls that could exceed budgets; records every attempt in the ledger."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from villasanj.shared.application.clock import Clock
from villasanj.shared.application.errors import BudgetExceeded
from villasanj.shared.application.llm.ports import (
    CallStatus,
    Invocation,
    LedgerEntry,
    LLMLedger,
    ModelCall,
    ModelInvoker,
    OutputValidationFailed,
    ProviderAuthError,
    ProviderError,
    ProviderTransientError,
    TokenEstimator,
)
from villasanj.shared.application.llm.routing import ModelCatalog
from villasanj.shared.application.llm.types import TokenUsage


class CostGoverningInvoker:
    """Budget check before each attempt (worst case), ledger write after each attempt.

    Concurrent calls reserve their worst-case cost so parallel pre-checks cannot jointly overspend.
    """

    def __init__(
        self,
        inner: ModelInvoker,
        ledger: LLMLedger,
        catalog: ModelCatalog,
        estimator: TokenEstimator,
        clock: Clock,
        project_budget_usd: Decimal,
    ) -> None:
        self._inner = inner
        self._ledger = ledger
        self._catalog = catalog
        self._estimator = estimator
        self._clock = clock
        self._project_budget = project_budget_usd
        self._lock = asyncio.Lock()
        self._reserved_by_job: defaultdict[str, Decimal] = defaultdict(Decimal)

    async def invoke[T: BaseModel](self, call: ModelCall[T]) -> Invocation[T]:
        worst_case = self.worst_case_cost(call)
        await self._reserve(call, worst_case)
        try:
            return await self._invoke_and_record(call)
        finally:
            async with self._lock:
                self._reserved_by_job[call.ctx.job_id] -= worst_case

    def worst_case_cost(self, call: ModelCall[Any]) -> Decimal:
        input_tokens = self._estimator.input_tokens(
            call.model, call.request.messages, call.request.output_schema.model_json_schema()
        )
        usage = TokenUsage(input_tokens=input_tokens, output_tokens=call.max_output_tokens)
        return self._catalog.get(call.model).pricing.cost(usage)

    async def _reserve(self, call: ModelCall[Any], worst_case: Decimal) -> None:
        job_id = call.ctx.job_id
        async with self._lock:
            reserved_total = sum(self._reserved_by_job.values(), Decimal(0))
            job_spent = await self._ledger.spent_usd(job_id) + self._reserved_by_job[job_id]
            total_spent = await self._ledger.spent_total_usd() + reserved_total
            if job_spent + worst_case > call.ctx.budget_usd:
                raise BudgetExceeded(
                    f"job {job_id}: worst-case ${worst_case:.6f} would exceed the job budget "
                    f"${call.ctx.budget_usd} (spent or reserved ${job_spent:.6f})"
                )
            if total_spent + worst_case > self._project_budget:
                raise BudgetExceeded(
                    f"worst-case ${worst_case:.6f} would exceed the project budget "
                    f"${self._project_budget} (spent or reserved ${total_spent:.6f})"
                )
            self._reserved_by_job[job_id] += worst_case

    async def _invoke_and_record[T: BaseModel](self, call: ModelCall[T]) -> Invocation[T]:
        try:
            invocation = await self._inner.invoke(call)
        except OutputValidationFailed as failure:
            status = CallStatus.TRUNCATED if failure.truncated else CallStatus.INVALID_OUTPUT
            await self._record(call, status, failure.usage, failure.latency_ms, failure.reason)
            raise
        except ProviderError as error:
            await self._record(call, _status_for(error), TokenUsage.zero(), 0, error.code)
            raise
        cost = await self._record(call, CallStatus.OK, invocation.usage, invocation.latency_ms)
        return replace(invocation, cost_usd=cost)

    async def _record(
        self,
        call: ModelCall[Any],
        status: CallStatus,
        usage: TokenUsage,
        latency_ms: int,
        error_code: str | None = None,
    ) -> Decimal:
        cost = self._catalog.get(call.model).pricing.cost(usage)
        await self._ledger.record(
            LedgerEntry(
                job_id=call.ctx.job_id,
                task=call.request.task,
                model=call.model,
                prompt_id=call.request.prompt_id,
                prompt_version=call.request.prompt_version,
                attempt=call.attempt,
                status=status,
                usage=usage,
                cost_usd=cost,
                latency_ms=latency_ms,
                created_at=self._clock.now(),
                error_code=error_code,
            )
        )
        return cost


def _status_for(error: ProviderError) -> CallStatus:
    if isinstance(error, ProviderTransientError | ProviderAuthError):
        return CallStatus.TRANSPORT_ERROR
    return CallStatus.REJECTED
