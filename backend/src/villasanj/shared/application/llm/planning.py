"""Dry-run: price planned LLM calls with zero provider calls."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from villasanj.shared.application.llm.caching import cache_key
from villasanj.shared.application.llm.ports import LLMCacheStore, ModelCall, TokenEstimator
from villasanj.shared.application.llm.routing import LLMRouting, ModelCatalog
from villasanj.shared.application.llm.types import JobContext, LLMRequest, LLMTask, TokenUsage

_DRY_RUN_CONTEXT = JobContext(job_id="dry-run", budget_usd=Decimal(0))


@dataclass(frozen=True, slots=True)
class DryRunLine:
    task: LLMTask
    model: str
    calls: int
    cache_hits: int
    expected_usd: Decimal  # input estimate + the task's expected output tokens
    worst_case_usd: Decimal  # input estimate + max output tokens


@dataclass(frozen=True, slots=True)
class DryRunReport:
    lines: tuple[DryRunLine, ...]

    @property
    def calls(self) -> int:
        return sum(line.calls for line in self.lines)

    @property
    def cache_hits(self) -> int:
        return sum(line.cache_hits for line in self.lines)

    @property
    def expected_usd(self) -> Decimal:
        return sum((line.expected_usd for line in self.lines), Decimal(0))

    @property
    def worst_case_usd(self) -> Decimal:
        return sum((line.worst_case_usd for line in self.lines), Decimal(0))


@dataclass
class _Accumulator:
    calls: int = 0
    cache_hits: int = 0
    expected: Decimal = Decimal(0)
    worst: Decimal = Decimal(0)


class DryRunEstimator:
    def __init__(
        self,
        routing: LLMRouting,
        catalog: ModelCatalog,
        estimator: TokenEstimator,
        cache: LLMCacheStore,
        provider_name: str,
    ) -> None:
        self._routing = routing
        self._catalog = catalog
        self._estimator = estimator
        self._cache = cache
        self._provider = provider_name

    async def estimate(self, requests: Sequence[LLMRequest[Any]]) -> DryRunReport:
        totals: defaultdict[tuple[LLMTask, str], _Accumulator] = defaultdict(_Accumulator)
        for request in requests:
            route = self._routing.route(request.task)
            call = ModelCall(request=request, route=route, model=route.model, ctx=_DRY_RUN_CONTEXT)
            acc = totals[(request.task, route.model)]
            acc.calls += 1
            if await self._cache.get(cache_key(self._provider, call)) is not None:
                acc.cache_hits += 1
                continue
            input_tokens = self._estimator.input_tokens(
                route.model, request.messages, request.output_schema.model_json_schema()
            )
            pricing = self._catalog.get(route.model).pricing
            expected_output = min(route.expected_output_tokens, call.max_output_tokens)
            acc.expected += pricing.cost(TokenUsage(input_tokens, expected_output))
            acc.worst += pricing.cost(TokenUsage(input_tokens, call.max_output_tokens))
        return DryRunReport(
            tuple(
                DryRunLine(task, model, acc.calls, acc.cache_hits, acc.expected, acc.worst)
                for (task, model), acc in sorted(totals.items())
            )
        )
