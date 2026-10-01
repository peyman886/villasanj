"""Retries: backoff for transient provider errors, feedback retries for invalid output."""

from __future__ import annotations

import random
from collections.abc import Awaitable, Callable
from dataclasses import replace

from pydantic import BaseModel

from villasanj.shared.application.errors import LLMOutputInvalid
from villasanj.shared.application.llm.ports import (
    Invocation,
    ModelCall,
    ModelInvoker,
    OutputValidationFailed,
    ProviderError,
)
from villasanj.shared.application.llm.routing import RetryPolicy

type Sleep = Callable[[float], Awaitable[None]]


class RetryingInvoker:
    def __init__(
        self,
        inner: ModelInvoker,
        policy: RetryPolicy,
        sleep: Sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._inner = inner
        self._policy = policy
        self._sleep = sleep
        self._jitter = jitter

    async def invoke[T: BaseModel](self, call: ModelCall[T]) -> Invocation[T]:
        transport_failures = 0
        validation_failures = 0
        attempt = 1
        feedback: str | None = None
        while True:
            try:
                invocation = await self._inner.invoke(call.retry(attempt, feedback))
                return replace(invocation, attempts=attempt)
            except OutputValidationFailed as failure:
                validation_failures += 1
                if validation_failures > self._policy.max_validation_retries:
                    raise LLMOutputInvalid(
                        f"task {call.request.task} prompt {call.request.prompt_id}@"
                        f"{call.request.prompt_version} on {call.model}: output stayed invalid "
                        f"after {attempt} attempts"
                    ) from None
                feedback = failure.reason
            except ProviderError as error:
                transport_failures += 1
                if not error.retriable or transport_failures >= self._policy.max_transport_attempts:
                    raise
                await self._sleep(self._delay(transport_failures, error.retry_after_seconds))
            attempt += 1

    def _delay(self, failures: int, retry_after: float | None) -> float:
        backoff = self._policy.base_delay_seconds * (2 ** (failures - 1))
        backoff = min(self._policy.max_delay_seconds, backoff) * (0.5 + self._jitter() / 2)
        return float(max(backoff, retry_after or 0.0))
