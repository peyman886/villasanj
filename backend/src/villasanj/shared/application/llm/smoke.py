"""Smoke check: one tiny structured call per task route (and per fallback model)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from villasanj.shared.application.errors import LLMError
from villasanj.shared.application.llm.ports import LLMClient
from villasanj.shared.application.llm.routing import LLMRouting
from villasanj.shared.application.llm.types import JobContext, LLMRequest, LLMTask, Message

SMOKE_PROMPT_ID = "smoke"
SMOKE_PROMPT_VERSION = "1"
SMOKE_MAX_OUTPUT_TOKENS = 512


class SmokeReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str
    ok: bool


@dataclass(frozen=True, slots=True)
class SmokeOutcome:
    task: LLMTask
    model: str
    ok: bool
    cost_usd: Decimal
    cache_hit: bool
    error: str | None = None


def smoke_request(task: LLMTask) -> LLMRequest[SmokeReply]:
    return LLMRequest(
        task=task,
        prompt_id=SMOKE_PROMPT_ID,
        prompt_version=SMOKE_PROMPT_VERSION,
        messages=(
            Message.system("You are a connectivity check for a JSON API. Reply with JSON only."),
            Message.user(f'Return a JSON object with "task" set to "{task.value}" and "ok" true.'),
        ),
        output_schema=SmokeReply,
        max_output_tokens=SMOKE_MAX_OUTPUT_TOKENS,
    )


class LLMSmokeCheck:
    def __init__(self, client: LLMClient, routing: LLMRouting, include_fallbacks: bool) -> None:
        self._client = client
        self._routing = routing
        self._include_fallbacks = include_fallbacks

    def plan(self) -> list[LLMRequest[SmokeReply]]:
        return [smoke_request(task) for task, _ in self._targets()]

    async def run(self, ctx: JobContext) -> list[SmokeOutcome]:
        return [await self._check(task, model, ctx) for task, model in self._targets()]

    def _targets(self) -> list[tuple[LLMTask, str]]:
        targets: list[tuple[LLMTask, str]] = []
        covered: set[str] = set()
        for task in LLMTask:
            route = self._routing.route(task)
            targets.append((task, route.model))
            covered.add(route.model)
        if self._include_fallbacks:
            for task in LLMTask:
                for model in self._routing.route(task).fallbacks:
                    if model not in covered:
                        targets.append((task, model))
                        covered.add(model)
        return targets

    async def _check(self, task: LLMTask, model: str, ctx: JobContext) -> SmokeOutcome:
        try:
            response = await self._client.generate(smoke_request(task), ctx, model=model)
        except LLMError as error:
            return SmokeOutcome(task, model, False, Decimal(0), False, type(error).__name__)
        reply = response.value
        ok = reply.ok and reply.task == task.value
        return SmokeOutcome(task, model, ok, response.cost_usd, response.cache_hit)
