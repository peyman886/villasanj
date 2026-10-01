"""The public LLMClient: routes a task to its models, falls back on availability failures."""

from __future__ import annotations

import asyncio

import structlog
from pydantic import BaseModel

from villasanj.shared.application.errors import ConfigurationError, LLMUnavailable
from villasanj.shared.application.llm.ports import (
    ModelCall,
    ModelInvoker,
    ProviderAuthError,
    ProviderError,
)
from villasanj.shared.application.llm.routing import LLMRouting
from villasanj.shared.application.llm.types import JobContext, LLMRequest, LLMResponse, LLMTask

log = structlog.get_logger(__name__)


class RoutedLLMClient:
    """Fallback is used only for transport/availability errors, never to shop for a nicer answer."""

    def __init__(self, invoker: ModelInvoker, routing: LLMRouting) -> None:
        self._invoker = invoker
        self._routing = routing
        self._semaphores = {
            task: asyncio.Semaphore(route.concurrency) for task, route in routing.routes.items()
        }

    async def generate[T: BaseModel](
        self, request: LLMRequest[T], ctx: JobContext, *, model: str | None = None
    ) -> LLMResponse[T]:
        route = self._routing.route(request.task)
        if model is not None and model not in route.models:
            raise ConfigurationError(f"{model} is not configured for task {request.task}")
        candidates = (model,) if model is not None else route.models
        async with self._semaphore(request.task):
            last_error: ProviderError | None = None
            for candidate in candidates:
                try:
                    invocation = await self._invoker.invoke(
                        ModelCall(request=request, route=route, model=candidate, ctx=ctx)
                    )
                except ProviderAuthError:
                    raise LLMUnavailable("the LLM provider rejected our credentials") from None
                except ProviderError as error:
                    if not error.fallback_allowed:
                        raise LLMUnavailable(f"{request.task}: {error.code}") from None
                    log.warning("llm.fallback", task=request.task, model=candidate, code=error.code)
                    last_error = error
                    continue
                return LLMResponse(
                    value=invocation.value,
                    model=invocation.model,
                    usage=invocation.usage,
                    cost_usd=invocation.cost_usd,
                    cache_hit=invocation.cache_hit,
                    attempts=invocation.attempts,
                    latency_ms=invocation.latency_ms,
                )
        code = last_error.code if last_error else "no-candidates"
        raise LLMUnavailable(f"{request.task}: all models failed (last: {code})")

    def _semaphore(self, task: LLMTask) -> asyncio.Semaphore:
        return self._semaphores[task]
