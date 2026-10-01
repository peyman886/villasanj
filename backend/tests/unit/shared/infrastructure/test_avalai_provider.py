"""AvalAI adapter against a mocked HTTP transport (the SDK uses httpx2)."""

import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from pydantic import SecretStr

from tests.fakes.llm import Answer
from villasanj.shared.application.llm.ports import (
    CallMeta,
    FinishReason,
    ProviderAuthError,
    ProviderCall,
    ProviderRejectedError,
    ProviderTransientError,
)
from villasanj.shared.application.llm.types import ImagePart, LLMTask, Message
from villasanj.shared.infrastructure.llm.avalai import AvalAIProvider

API_KEY = "test-key-that-must-never-leak-1234567890"
BASE_URL = "https://gateway.test/v1"


def completion_body(
    content: str, finish: str = "stop", usage: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "id": "c1",
        "object": "chat.completion",
        "created": 0,
        "model": "m",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish,
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": usage
        if usage is not None
        else {
            "prompt_tokens": 120,
            "completion_tokens": 40,
            "total_tokens": 160,
            "prompt_tokens_details": {"cached_tokens": 20},
            "completion_tokens_details": {"reasoning_tokens": 5},
        },
    }


def provider(handler: Callable[[httpx2.Request], httpx2.Response]) -> AvalAIProvider:
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return AvalAIProvider(SecretStr(API_KEY), BASE_URL, timeout_seconds=5, http_client=client)


def call(*parts: str | ImagePart) -> ProviderCall:
    return ProviderCall(
        model="gemini-3.1-flash-lite",
        messages=(Message.system("sys"), Message.user(*(parts or ("hello",)))),
        schema_name="Answer",
        json_schema=Answer.model_json_schema(),
        max_output_tokens=300,
        temperature=0.0,
        reasoning_effort=None,
        meta=CallMeta(
            job_id="j", task=LLMTask.ER_JUDGE, prompt_id="p", prompt_version="1", attempt=1
        ),
    )


async def test_request_shape_and_response_mapping() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            200,
            json=completion_body('{"answer":"yes","confidence":1}'),
            headers={"x-ratelimit-limit-requests": "1000"},
        )

    result = await provider(handler).complete(call("compare", ImagePart(b"\x89PNG", "image/png")))

    assert seen["url"] == f"{BASE_URL}/chat/completions"
    assert seen["auth"] == f"Bearer {API_KEY}"
    body = seen["body"]
    assert body["max_completion_tokens"] == 300
    assert body["temperature"] == 0.0
    assert "reasoning_effort" not in body
    schema_format = body["response_format"]
    assert schema_format["type"] == "json_schema"
    assert schema_format["json_schema"]["strict"] is True
    assert schema_format["json_schema"]["schema"]["additionalProperties"] is False
    user_content = body["messages"][1]["content"]
    assert user_content[0] == {"type": "text", "text": "compare"}
    assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")

    assert result.text == '{"answer":"yes","confidence":1}'
    assert result.finish_reason is FinishReason.STOP
    assert result.rate_limit_rpm == 1000
    assert result.usage is not None
    assert (result.usage.input_tokens, result.usage.output_tokens) == (120, 40)
    assert (result.usage.cached_input_tokens, result.usage.reasoning_tokens) == (20, 5)


async def test_length_finish_reason_is_reported() -> None:
    result = await provider(
        lambda _r: httpx2.Response(200, json=completion_body('{"ans', finish="length"))
    ).complete(call())
    assert result.finish_reason is FinishReason.LENGTH


@pytest.mark.parametrize(
    ("status", "headers", "error_type", "retry_after"),
    [
        (429, {"retry-after": "3"}, ProviderTransientError, 3.0),
        (503, {}, ProviderTransientError, None),
        (404, {}, ProviderRejectedError, None),
        (400, {}, ProviderRejectedError, None),
        (401, {}, ProviderAuthError, None),
    ],
)
async def test_http_errors_are_mapped_without_leaking(
    status: int, headers: dict[str, str], error_type: type[Exception], retry_after: float | None
) -> None:
    def handler(_request: httpx2.Request) -> httpx2.Response:
        body = {"error": {"message": f"bad key {API_KEY} and prompt text", "type": "x"}}
        return httpx2.Response(status, json=body, headers=headers)

    with pytest.raises(error_type) as caught:
        await provider(handler).complete(call())
    assert API_KEY not in str(caught.value)
    assert "prompt text" not in str(caught.value)
    assert caught.value.code == f"http-{status}"  # type: ignore[attr-defined]
    assert caught.value.retry_after_seconds == retry_after  # type: ignore[attr-defined]


async def test_connection_failure_is_transient() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("boom", request=request)

    with pytest.raises(ProviderTransientError):
        await provider(handler).complete(call())


async def test_ready_lists_models() -> None:
    ok = provider(lambda _r: httpx2.Response(200, json={"object": "list", "data": []}))
    down = provider(lambda _r: httpx2.Response(401, json={"error": {"message": "no"}}))
    assert await ok.ready()
    assert not await down.ready()
