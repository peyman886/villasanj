"""AvalAI provider: an OpenAI-compatible gateway reached through the official OpenAI SDK."""

from __future__ import annotations

import base64
import time
from typing import Any

import httpx2
import openai
import structlog
from openai import AsyncOpenAI
from pydantic import SecretStr

from villasanj.shared.application.llm.ports import (
    FinishReason,
    ProviderAuthError,
    ProviderCall,
    ProviderError,
    ProviderRejectedError,
    ProviderResult,
    ProviderTransientError,
)
from villasanj.shared.application.llm.types import ImagePart, Message, TextPart, TokenUsage
from villasanj.shared.infrastructure.llm.strict_schema import to_strict_json_schema

log = structlog.get_logger(__name__)

_FINISH_REASONS = {
    "stop": FinishReason.STOP,
    "length": FinishReason.LENGTH,
    "content_filter": FinishReason.CONTENT_FILTER,
}
_MS_PER_SECOND = 1000
_HTTP_TOO_MANY_REQUESTS = 429
_HTTP_SERVER_ERROR = 500


class AvalAIProvider:
    name = "avalai"

    def __init__(
        self,
        api_key: SecretStr,
        base_url: str,
        timeout_seconds: float,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key.get_secret_value(),
            base_url=base_url,
            timeout=timeout_seconds,
            max_retries=0,  # retries are owned by RetryingInvoker
            http_client=http_client,
        )

    async def complete(self, call: ProviderCall) -> ProviderResult:
        started = time.perf_counter()
        try:
            raw = await self._client.chat.completions.with_raw_response.create(
                **_request_kwargs(call)
            )
        except openai.OpenAIError as error:
            raise _map_error(error) from None
        completion = raw.parse()
        latency_ms = int((time.perf_counter() - started) * _MS_PER_SECOND)
        if not completion.choices:
            raise ProviderRejectedError("empty-choices")
        choice = completion.choices[0]
        rpm_limit = _int_header(raw.headers, "x-ratelimit-limit-requests")
        log.info(
            "llm.provider.call",
            provider=self.name,
            model=call.model,
            task=call.meta.task,
            latency_ms=latency_ms,
            finish_reason=choice.finish_reason,
            rpm_limit=rpm_limit,
            tpm_limit=_int_header(raw.headers, "x-ratelimit-limit-tokens"),
        )
        return ProviderResult(
            text=choice.message.content or "",
            usage=_usage(completion.usage),
            finish_reason=_FINISH_REASONS.get(choice.finish_reason or "", FinishReason.OTHER),
            latency_ms=latency_ms,
            rate_limit_rpm=rpm_limit,
        )

    async def ready(self) -> bool:
        """Lists models: free of charge and proves the key and the gateway work."""
        try:
            await self._client.models.list()
        except openai.OpenAIError:
            return False
        return True

    async def aclose(self) -> None:
        await self._client.close()


def _request_kwargs(call: ProviderCall) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "model": call.model,
        "messages": [_message(message) for message in call.messages],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": call.schema_name,
                "strict": True,
                "schema": to_strict_json_schema(call.json_schema),
            },
        },
        "max_completion_tokens": call.max_output_tokens,
    }
    if call.temperature is not None:
        kwargs["temperature"] = call.temperature
    if call.reasoning_effort is not None:
        kwargs["reasoning_effort"] = call.reasoning_effort
    return kwargs


def _message(message: Message) -> dict[str, Any]:
    if not message.images:
        return {"role": message.role.value, "content": message.text}
    content: list[dict[str, Any]] = []
    for part in message.parts:
        if isinstance(part, TextPart):
            content.append({"type": "text", "text": part.text})
        else:
            content.append({"type": "image_url", "image_url": {"url": _data_url(part)}})
    return {"role": message.role.value, "content": content}


def _data_url(part: ImagePart) -> str:
    return f"data:{part.media_type};base64,{base64.b64encode(part.data).decode('ascii')}"


def _usage(usage: Any) -> TokenUsage | None:
    if usage is None:
        return None
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    completion_details = getattr(usage, "completion_tokens_details", None)
    return TokenUsage(
        input_tokens=usage.prompt_tokens or 0,
        output_tokens=usage.completion_tokens or 0,
        cached_input_tokens=getattr(prompt_details, "cached_tokens", None) or 0,
        reasoning_tokens=getattr(completion_details, "reasoning_tokens", None) or 0,
    )


def _int_header(headers: Any, name: str) -> int | None:
    value = headers.get(name)
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _retry_after(error: openai.APIStatusError) -> float | None:
    value = error.response.headers.get("retry-after")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _map_error(error: openai.OpenAIError) -> ProviderError:
    """Translate SDK errors without carrying messages (they may echo request content)."""
    if isinstance(error, openai.APITimeoutError):
        return ProviderTransientError("timeout")
    if isinstance(error, openai.APIConnectionError):
        return ProviderTransientError("connection")
    if isinstance(error, openai.AuthenticationError | openai.PermissionDeniedError):
        return ProviderAuthError(f"http-{error.status_code}")
    if isinstance(error, openai.APIStatusError):
        code = f"http-{error.status_code}"
        if error.status_code == _HTTP_TOO_MANY_REQUESTS or error.status_code >= _HTTP_SERVER_ERROR:
            return ProviderTransientError(code, retry_after_seconds=_retry_after(error))
        return ProviderRejectedError(code)
    return ProviderTransientError(type(error).__name__)
