"""Load task routing (``config/llm.toml``) and the model catalog (``config/llm-models.json``)."""

from __future__ import annotations

import json
import tomllib
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from villasanj.shared.application.errors import ConfigurationError
from villasanj.shared.application.llm.routing import (
    LLMRouting,
    ModelCatalog,
    ModelPricing,
    ModelProfile,
    RetryPolicy,
    TaskRoute,
)
from villasanj.shared.application.llm.types import LLMTask


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _TaskFile(_Strict):
    model: str
    fallbacks: list[str] = []
    max_output_tokens: int = Field(gt=0)
    expected_output_tokens: int = Field(gt=0)
    concurrency: int = Field(default=4, gt=0)
    temperature: float | None = None
    reasoning_effort: str | None = None


class _Calibration(_Strict):
    chars_per_token: float = Field(gt=0)
    image_tokens: int = Field(ge=0)


class _EstimationFile(_Strict):
    default: _Calibration
    models: dict[str, _Calibration] = {}


class _BudgetFile(_Strict):
    default_job_usd: Decimal = Field(gt=0)


class _RetryFile(_Strict):
    max_transport_attempts: int = Field(ge=1)
    max_validation_retries: int = Field(ge=0)
    base_delay_seconds: float = Field(gt=0)
    max_delay_seconds: float = Field(gt=0)
    request_timeout_seconds: float = Field(gt=0)


class _RoutingFile(_Strict):
    budget: _BudgetFile
    retry: _RetryFile
    estimation: _EstimationFile
    tasks: dict[LLMTask, _TaskFile]


class _ModelEntry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str
    input_usd_per_mtok: Decimal
    output_usd_per_mtok: Decimal
    cached_input_usd_per_mtok: Decimal | None = None
    supports_vision: bool = False
    supports_response_schema: bool = False


class _ModelsFile(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    models: list[_ModelEntry]


def _read_routing_file(path: Path) -> _RoutingFile:
    try:
        with path.open("rb") as handle:
            return _RoutingFile.model_validate(tomllib.load(handle))
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        raise ConfigurationError(f"invalid routing file {path}: {error}") from None


def load_routing(path: Path, project_budget_usd: Decimal) -> LLMRouting:
    data = _read_routing_file(path)
    retry = data.retry
    return LLMRouting(
        routes={
            task: TaskRoute(
                task=task,
                model=entry.model,
                fallbacks=tuple(entry.fallbacks),
                max_output_tokens=entry.max_output_tokens,
                expected_output_tokens=entry.expected_output_tokens,
                concurrency=entry.concurrency,
                temperature=entry.temperature,
                reasoning_effort=entry.reasoning_effort,
            )
            for task, entry in data.tasks.items()
        },
        default_job_budget_usd=data.budget.default_job_usd,
        project_budget_usd=project_budget_usd,
        retry=RetryPolicy(
            max_transport_attempts=retry.max_transport_attempts,
            max_validation_retries=retry.max_validation_retries,
            base_delay_seconds=retry.base_delay_seconds,
            max_delay_seconds=retry.max_delay_seconds,
            request_timeout_seconds=retry.request_timeout_seconds,
        ),
    )


def load_catalog(models_path: Path, routing_path: Path) -> ModelCatalog:
    estimation = _read_routing_file(routing_path).estimation
    try:
        models = _ModelsFile.model_validate(json.loads(models_path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        raise ConfigurationError(f"invalid model catalog {models_path}: {error}") from None
    profiles = {}
    for entry in models.models:
        calibration = estimation.models.get(entry.id, estimation.default)
        profiles[entry.id] = ModelProfile(
            model_id=entry.id,
            pricing=ModelPricing(
                input_per_mtok=entry.input_usd_per_mtok,
                output_per_mtok=entry.output_usd_per_mtok,
                cached_input_per_mtok=entry.cached_input_usd_per_mtok,
            ),
            supports_vision=entry.supports_vision,
            supports_response_schema=entry.supports_response_schema,
            chars_per_token=calibration.chars_per_token,
            image_tokens=calibration.image_tokens,
        )
    return ModelCatalog(profiles)
