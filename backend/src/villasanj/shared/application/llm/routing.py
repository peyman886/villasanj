"""Task routing, model catalog (prices, capabilities, estimator calibration) and policies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from villasanj.shared.application.errors import ConfigurationError
from villasanj.shared.application.llm.types import VISION_TASKS, LLMTask, TokenUsage

TOKENS_PER_MILLION = Decimal(1_000_000)


@dataclass(frozen=True, slots=True)
class TaskRoute:
    task: LLMTask
    model: str
    fallbacks: tuple[str, ...]
    max_output_tokens: int
    expected_output_tokens: int
    concurrency: int
    temperature: float | None = None
    reasoning_effort: str | None = None

    @property
    def models(self) -> tuple[str, ...]:
        return (self.model, *self.fallbacks)


@dataclass(frozen=True, slots=True)
class ModelPricing:
    """USD per 1M tokens, from the AvalAI ``/v1/models`` snapshot."""

    input_per_mtok: Decimal
    output_per_mtok: Decimal
    cached_input_per_mtok: Decimal | None = None

    def cost(self, usage: TokenUsage) -> Decimal:
        cached = min(usage.cached_input_tokens, usage.input_tokens)
        cached_price = self.cached_input_per_mtok or self.input_per_mtok
        total = (
            (usage.input_tokens - cached) * self.input_per_mtok
            + cached * cached_price
            + usage.output_tokens * self.output_per_mtok
        )
        return total / TOKENS_PER_MILLION


@dataclass(frozen=True, slots=True)
class ModelProfile:
    model_id: str
    pricing: ModelPricing
    supports_vision: bool
    supports_response_schema: bool
    chars_per_token: float
    image_tokens: int


@dataclass(frozen=True, slots=True)
class ModelCatalog:
    profiles: Mapping[str, ModelProfile]

    def get(self, model_id: str) -> ModelProfile:
        try:
            return self.profiles[model_id]
        except KeyError:
            raise ConfigurationError(f"model {model_id!r} is not in the model catalog") from None


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_transport_attempts: int
    max_validation_retries: int
    base_delay_seconds: float
    max_delay_seconds: float
    request_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class LLMRouting:
    routes: Mapping[LLMTask, TaskRoute]
    default_job_budget_usd: Decimal
    project_budget_usd: Decimal
    retry: RetryPolicy

    def route(self, task: LLMTask) -> TaskRoute:
        try:
            return self.routes[task]
        except KeyError:
            raise ConfigurationError(f"no route configured for task {task}") from None

    def validate_against(self, catalog: ModelCatalog) -> None:
        """Fail fast at startup if a route points to a missing or incapable model."""
        missing = [task for task in LLMTask if task not in self.routes]
        if missing:
            raise ConfigurationError(f"tasks without a route: {', '.join(missing)}")
        for route in self.routes.values():
            for model_id in route.models:
                profile = catalog.get(model_id)
                if not profile.supports_response_schema:
                    raise ConfigurationError(f"{model_id} lacks structured output ({route.task})")
                if route.task in VISION_TASKS and not profile.supports_vision:
                    raise ConfigurationError(f"{model_id} lacks vision ({route.task})")
