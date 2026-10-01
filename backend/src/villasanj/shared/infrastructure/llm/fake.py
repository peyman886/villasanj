"""Deterministic provider for tests and offline development (``LLM__PROVIDER=fake``).

Replies come from a script (consumed in order) and then from an optional responder function.
Unscripted calls are rejected rather than answered with invented content.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable

from villasanj.shared.application.llm.ports import (
    FinishReason,
    ProviderCall,
    ProviderError,
    ProviderRejectedError,
    ProviderResult,
)
from villasanj.shared.application.llm.types import TokenUsage

type FakeReply = str | ProviderResult | ProviderError
type Responder = Callable[[ProviderCall], FakeReply]

DEFAULT_FAKE_USAGE = TokenUsage(input_tokens=100, output_tokens=50)


class FakeLLMProvider:
    name = "fake"

    def __init__(
        self,
        script: Iterable[FakeReply] = (),
        responder: Responder | None = None,
        usage: TokenUsage = DEFAULT_FAKE_USAGE,
    ) -> None:
        self._script: deque[FakeReply] = deque(script)
        self._responder = responder
        self._usage = usage
        self.calls: list[ProviderCall] = []

    async def complete(self, call: ProviderCall) -> ProviderResult:
        self.calls.append(call)
        reply = self._next_reply(call)
        if isinstance(reply, ProviderError):
            raise reply
        if isinstance(reply, ProviderResult):
            return reply
        return ProviderResult(
            text=reply, usage=self._usage, finish_reason=FinishReason.STOP, latency_ms=1
        )

    async def ready(self) -> bool:
        return True

    def _next_reply(self, call: ProviderCall) -> FakeReply:
        if self._script:
            return self._script.popleft()
        if self._responder is not None:
            return self._responder(call)
        return ProviderRejectedError("fake-unscripted")
