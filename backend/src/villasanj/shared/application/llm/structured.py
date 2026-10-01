"""Innermost invoker: turns a ModelCall into a provider call and validates structured output."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ValidationError

from villasanj.shared.application.llm.ports import (
    CallMeta,
    FinishReason,
    Invocation,
    ModelCall,
    OutputValidationFailed,
    ProviderCall,
    ProviderResult,
    RawModelProvider,
    TokenEstimator,
)
from villasanj.shared.application.llm.types import Message, TokenUsage, UsageSource

MAX_FEEDBACK_ERRORS = 5
FEEDBACK_TEMPLATE = (
    "Your previous reply was rejected: {reason}. "
    "Reply again with only a JSON object that matches the required schema."
)


def schema_name(schema: type[BaseModel]) -> str:
    return schema.__name__


def summarize_validation_error(error: ValidationError) -> str:
    """A short, content-free description (field paths and error types only)."""
    parts = [
        f"{'.'.join(str(loc) for loc in item['loc']) or '<root>'}: {item['type']}"
        for item in error.errors()[:MAX_FEEDBACK_ERRORS]
    ]
    return "; ".join(parts)


class StructuredOutputInvoker:
    def __init__(self, provider: RawModelProvider, estimator: TokenEstimator) -> None:
        self._provider = provider
        self._estimator = estimator

    async def invoke[T: BaseModel](self, call: ModelCall[T]) -> Invocation[T]:
        provider_call = self._provider_call(call)
        result = await self._provider.complete(provider_call)
        usage = self._usage(provider_call, result)
        if result.finish_reason is FinishReason.LENGTH:
            raise OutputValidationFailed(
                "output was truncated at the token limit; be more concise",
                usage,
                result.latency_ms,
                truncated=True,
            )
        try:
            value = call.request.output_schema.model_validate_json(result.text)
        except ValidationError as error:
            raise OutputValidationFailed(
                summarize_validation_error(error), usage, result.latency_ms, truncated=False
            ) from None
        return Invocation(
            value=value,
            raw_text=result.text,
            model=call.model,
            usage=usage,
            cost_usd=Decimal(0),  # priced by CostGoverningInvoker
            attempts=call.attempt,
            latency_ms=result.latency_ms,
        )

    @staticmethod
    def _provider_call(call: ModelCall[Any]) -> ProviderCall:
        messages = call.request.messages
        if call.feedback:
            messages = (*messages, Message.user(FEEDBACK_TEMPLATE.format(reason=call.feedback)))
        return ProviderCall(
            model=call.model,
            messages=messages,
            schema_name=schema_name(call.request.output_schema),
            json_schema=call.request.output_schema.model_json_schema(),
            max_output_tokens=call.max_output_tokens,
            temperature=call.route.temperature,
            reasoning_effort=call.route.reasoning_effort,
            meta=CallMeta(
                job_id=call.ctx.job_id,
                task=call.request.task,
                prompt_id=call.request.prompt_id,
                prompt_version=call.request.prompt_version,
                attempt=call.attempt,
            ),
        )

    def _usage(self, call: ProviderCall, result: ProviderResult) -> TokenUsage:
        reported = result.usage
        if reported is not None and reported.input_tokens > 0:
            return reported
        # Some models report nothing or zeros: estimate and say so.
        return TokenUsage(
            input_tokens=self._estimator.input_tokens(call.model, call.messages, call.json_schema),
            output_tokens=self._estimator.output_tokens(call.model, result.text),
            source=UsageSource.ESTIMATED,
        )
