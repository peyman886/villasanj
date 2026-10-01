"""In-memory stores, a fixed clock and a small routing/catalog for LLM chain tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from villasanj.shared.application.llm.caching import CachingInvoker
from villasanj.shared.application.llm.client import RoutedLLMClient
from villasanj.shared.application.llm.cost import CostGoverningInvoker
from villasanj.shared.application.llm.estimation import HeuristicTokenEstimator
from villasanj.shared.application.llm.ports import (
    CachedCompletion,
    LedgerEntry,
    RawModelProvider,
)
from villasanj.shared.application.llm.retrying import RetryingInvoker
from villasanj.shared.application.llm.routing import (
    LLMRouting,
    ModelCatalog,
    ModelPricing,
    ModelProfile,
    RetryPolicy,
    TaskRoute,
)
from villasanj.shared.application.llm.structured import StructuredOutputInvoker
from villasanj.shared.application.llm.types import (
    JobContext,
    LLMRequest,
    LLMTask,
    Message,
)

PRIMARY = "primary-model"
FALLBACK = "fallback-model"
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


class FixedClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


class InMemoryLLMLedger:
    def __init__(self) -> None:
        self.entries: list[LedgerEntry] = []

    async def record(self, entry: LedgerEntry) -> None:
        self.entries.append(entry)

    async def spent_usd(self, job_id: str) -> Decimal:
        return sum((e.cost_usd for e in self.entries if e.job_id == job_id), Decimal(0))

    async def spent_total_usd(self) -> Decimal:
        return sum((e.cost_usd for e in self.entries), Decimal(0))


class InMemoryLLMCache:
    def __init__(self) -> None:
        self.entries: dict[str, CachedCompletion] = {}

    async def get(self, key: str) -> CachedCompletion | None:
        return self.entries.get(key)

    async def put(self, key: str, completion: CachedCompletion, task: LLMTask) -> None:
        self.entries.setdefault(key, completion)


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    confidence: float


VALID = '{"answer": "yes", "confidence": 0.9}'
INVALID = '{"answer": "yes"}'


def catalog(*, vision: bool = True, schema: bool = True) -> ModelCatalog:
    pricing = ModelPricing(Decimal(1), Decimal(2), Decimal("0.1"))  # USD per 1M tokens
    return ModelCatalog(
        {
            model: ModelProfile(
                model, pricing, vision, schema, chars_per_token=4, image_tokens=1000
            )
            for model in (PRIMARY, FALLBACK)
        }
    )


def routing(
    *, max_transport_attempts: int = 3, max_validation_retries: int = 2, project_usd: str = "30"
) -> LLMRouting:
    return LLMRouting(
        routes={
            task: TaskRoute(
                task=task,
                model=PRIMARY,
                fallbacks=(FALLBACK,),
                max_output_tokens=1000,
                expected_output_tokens=200,
                concurrency=4,
            )
            for task in LLMTask
        },
        default_job_budget_usd=Decimal(1),
        project_budget_usd=Decimal(project_usd),
        retry=RetryPolicy(
            max_transport_attempts=max_transport_attempts,
            max_validation_retries=max_validation_retries,
            base_delay_seconds=1.0,
            max_delay_seconds=8.0,
            request_timeout_seconds=10.0,
        ),
    )


def request(prompt_version: str = "1", text: str = "Is this the same villa?") -> LLMRequest[Answer]:
    return LLMRequest(
        task=LLMTask.ER_JUDGE,
        prompt_id="test-judge",
        prompt_version=prompt_version,
        messages=(Message.system("You compare listings."), Message.user(text)),
        output_schema=Answer,
    )


def job(budget: str = "1") -> JobContext:
    return JobContext(job_id="job-1", budget_usd=Decimal(budget))


@dataclass
class RecordingSleep:
    delays: list[float] = field(default_factory=list)

    async def __call__(self, seconds: float) -> None:
        self.delays.append(seconds)


@dataclass
class Chain:
    client: RoutedLLMClient
    ledger: InMemoryLLMLedger
    cache: InMemoryLLMCache
    sleep: RecordingSleep
    governor: CostGoverningInvoker


def build_chain(
    provider: RawModelProvider,
    llm_routing: LLMRouting | None = None,
    ledger: InMemoryLLMLedger | None = None,
) -> Chain:
    llm_routing = llm_routing or routing()
    model_catalog = catalog()
    ledger = ledger or InMemoryLLMLedger()
    cache = InMemoryLLMCache()
    sleep = RecordingSleep()
    clock = FixedClock()
    estimator = HeuristicTokenEstimator(model_catalog)
    governor = CostGoverningInvoker(
        StructuredOutputInvoker(provider, estimator),
        ledger,
        model_catalog,
        estimator,
        clock,
        llm_routing.project_budget_usd,
    )
    retrying = RetryingInvoker(governor, llm_routing.retry, sleep, jitter=lambda: 1.0)
    caching = CachingInvoker(retrying, cache, ledger, clock, provider.name)
    return Chain(RoutedLLMClient(caching, llm_routing), ledger, cache, sleep, governor)
