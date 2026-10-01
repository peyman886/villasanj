"""Ports of the LLM gateway.

``LLMClient`` is what use cases depend on. Below it, ``ModelInvoker`` decorators each add one
concern (cache, retry, budget, structured output); the innermost ``RawModelProvider`` talks to a
vendor.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel

from villasanj.shared.application.errors import LLMError
from villasanj.shared.application.llm.routing import TaskRoute
from villasanj.shared.application.llm.types import (
    JobContext,
    LLMRequest,
    LLMResponse,
    LLMTask,
    Message,
    TokenUsage,
)

# ------------------------------------------------------------------ public port


class LLMClient(Protocol):
    async def generate[T: BaseModel](
        self, request: LLMRequest[T], ctx: JobContext, *, model: str | None = None
    ) -> LLMResponse[T]:
        """Run ``request`` on its routed models.

        ``model`` may pin one of the task's *configured* models (used by smoke checks only).
        """
        ...


class LLMCallPlanner(Protocol):
    """Implemented by every LLM-using use case so ``--dry-run`` can price it with zero calls."""

    def plan(self) -> Sequence[LLMRequest[Any]]: ...


# ------------------------------------------------------------------ provider port


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class CallMeta:
    """Bookkeeping that travels with a call; providers ignore it."""

    job_id: str
    task: LLMTask
    prompt_id: str
    prompt_version: str
    attempt: int


@dataclass(frozen=True, slots=True)
class ProviderCall:
    model: str
    messages: tuple[Message, ...]
    schema_name: str
    json_schema: Mapping[str, Any]
    max_output_tokens: int
    temperature: float | None
    reasoning_effort: str | None
    meta: CallMeta


@dataclass(frozen=True, slots=True)
class ProviderResult:
    text: str
    usage: TokenUsage | None  # None when the provider did not report usage
    finish_reason: FinishReason
    latency_ms: int
    rate_limit_rpm: int | None = None


class ProviderError(LLMError):
    """A provider-level failure. Subclasses define whether retry or fallback makes sense."""

    retriable: bool = False
    fallback_allowed: bool = False

    def __init__(self, code: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after_seconds = retry_after_seconds


class ProviderTransientError(ProviderError):
    """Timeouts, connection errors, 429 and 5xx: retry, then fall back."""

    retriable = True
    fallback_allowed = True


class ProviderRejectedError(ProviderError):
    """The request was refused (4xx such as unknown model or unsupported schema): fall back."""

    fallback_allowed = True


class ProviderAuthError(ProviderError):
    """Credentials were rejected: neither retry nor fallback can help."""


class RawModelProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def complete(self, call: ProviderCall) -> ProviderResult: ...

    async def ready(self) -> bool:
        """Cheap readiness check (must not spend tokens)."""
        ...


# ------------------------------------------------------------------ invoker chain


@dataclass(frozen=True, slots=True)
class ModelCall[T: BaseModel]:
    request: LLMRequest[T]
    route: TaskRoute
    model: str
    ctx: JobContext
    attempt: int = 1
    feedback: str | None = None  # validation error from the previous attempt

    @property
    def max_output_tokens(self) -> int:
        return self.request.max_output_tokens or self.route.max_output_tokens

    def retry(self, attempt: int, feedback: str | None) -> ModelCall[T]:
        return replace(self, attempt=attempt, feedback=feedback)


@dataclass(frozen=True, slots=True)
class Invocation[T: BaseModel]:
    value: T
    raw_text: str
    model: str
    usage: TokenUsage
    cost_usd: Decimal
    attempts: int
    latency_ms: int
    cache_hit: bool = False


class OutputValidationFailed(LLMError):
    """Internal: one attempt produced unusable output. Carries the tokens it still cost."""

    def __init__(self, reason: str, usage: TokenUsage, latency_ms: int, truncated: bool) -> None:
        super().__init__(reason)
        self.reason = reason
        self.usage = usage
        self.latency_ms = latency_ms
        self.truncated = truncated


class ModelInvoker(Protocol):
    async def invoke[T: BaseModel](self, call: ModelCall[T]) -> Invocation[T]: ...


# ------------------------------------------------------------------ stores and estimation


class CallStatus(StrEnum):
    OK = "ok"
    CACHE_HIT = "cache_hit"
    INVALID_OUTPUT = "invalid_output"
    TRUNCATED = "truncated"
    TRANSPORT_ERROR = "transport_error"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    job_id: str
    task: LLMTask
    model: str
    prompt_id: str
    prompt_version: str
    attempt: int
    status: CallStatus
    usage: TokenUsage
    cost_usd: Decimal
    latency_ms: int
    created_at: datetime
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class SpendRow:
    """Ledger totals for one task and model (every attempt, failed ones included)."""

    task: str
    model: str
    calls: int  # ledger rows: paid attempts and cache hits
    cache_hits: int
    failed: int  # attempts that did not return a valid answer (truncated, errors)
    input_tokens: int
    output_tokens: int  # reasoning included
    reasoning_tokens: int
    cost_usd: Decimal
    estimated: int  # calls whose usage the provider did not report


class LLMSpendQuery(Protocol):
    async def by_task_and_model(self) -> list[SpendRow]:
        """Totals over the whole ledger, most expensive first."""
        ...


class LLMLedger(Protocol):
    async def record(self, entry: LedgerEntry) -> None: ...

    async def spent_usd(self, job_id: str) -> Decimal: ...

    async def spent_total_usd(self) -> Decimal: ...


@dataclass(frozen=True, slots=True)
class CachedCompletion:
    text: str
    model: str
    usage: TokenUsage


class LLMCacheStore(Protocol):
    async def get(self, key: str) -> CachedCompletion | None: ...

    async def put(self, key: str, completion: CachedCompletion, task: LLMTask) -> None: ...


class TokenEstimator(Protocol):
    def input_tokens(
        self, model: str, messages: Sequence[Message], json_schema: Mapping[str, Any] | None
    ) -> int: ...

    def output_tokens(self, model: str, text: str) -> int: ...
