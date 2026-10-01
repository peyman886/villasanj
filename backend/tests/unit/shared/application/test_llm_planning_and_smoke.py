from decimal import Decimal
from typing import Any

import pytest

from tests.fakes.llm import (
    FALLBACK,
    PRIMARY,
    VALID,
    build_chain,
    catalog,
    job,
    request,
    routing,
)
from villasanj.shared.application.errors import ConfigurationError
from villasanj.shared.application.llm.caching import cache_key
from villasanj.shared.application.llm.estimation import HeuristicTokenEstimator
from villasanj.shared.application.llm.planning import DryRunEstimator
from villasanj.shared.application.llm.ports import ModelCall, ProviderCall
from villasanj.shared.application.llm.smoke import LLMSmokeCheck, SmokeReply
from villasanj.shared.application.llm.types import ImagePart, LLMRequest, LLMTask, Message
from villasanj.shared.infrastructure.llm.fake import FakeLLMProvider


def _call(req: LLMRequest[Any], model: str = PRIMARY) -> ModelCall[Any]:
    return ModelCall(request=req, route=routing().route(req.task), model=model, ctx=job())


async def test_dry_run_prices_without_calling_and_counts_cache_hits() -> None:
    provider = FakeLLMProvider([VALID])
    chain = build_chain(provider)
    estimator = DryRunEstimator(
        routing(), catalog(), HeuristicTokenEstimator(catalog()), chain.cache, provider.name
    )
    before = await estimator.estimate([request(), request(text="another pair")])
    assert provider.calls == []
    assert (before.calls, before.cache_hits) == (2, 0)
    assert Decimal(0) < before.expected_usd < before.worst_case_usd

    await chain.client.generate(request(), job())
    after = await estimator.estimate([request(), request(text="another pair")])
    assert (after.calls, after.cache_hits) == (2, 1)
    assert after.expected_usd < before.expected_usd


def test_cache_key_depends_on_everything_that_changes_output() -> None:
    base = cache_key("avalai", _call(request()))
    assert base == cache_key("avalai", _call(request()))
    assert base != cache_key("avalai", _call(request(prompt_version="2")))
    assert base != cache_key("avalai", _call(request(), model=FALLBACK))
    assert base != cache_key("other", _call(request()))

    def with_image(data: bytes) -> str:
        req = request()
        image_req = LLMRequest(
            task=req.task,
            prompt_id=req.prompt_id,
            prompt_version=req.prompt_version,
            messages=(Message.user("compare", ImagePart(data, "image/png")),),
            output_schema=req.output_schema,
        )
        return cache_key("avalai", _call(image_req))

    assert with_image(b"photo-a") != with_image(b"photo-b")
    assert with_image(b"photo-a") == with_image(b"photo-a")


def test_routing_validation_rejects_incapable_models() -> None:
    routing().validate_against(catalog())
    with pytest.raises(ConfigurationError, match="vision"):
        routing().validate_against(catalog(vision=False))
    with pytest.raises(ConfigurationError, match="structured output"):
        routing().validate_against(catalog(schema=False))


async def test_smoke_check_covers_every_task_and_each_fallback_once() -> None:
    def responder(call: ProviderCall) -> str:
        task = call.messages[-1].text.split('"')[3]
        return SmokeReply(task=task, ok=True).model_dump_json()

    provider = FakeLLMProvider(responder=responder)
    chain = build_chain(provider)
    check = LLMSmokeCheck(chain.client, routing(), include_fallbacks=True)
    assert len(check.plan()) == len(LLMTask) + 1
    outcomes = await check.run(job())
    assert all(outcome.ok for outcome in outcomes)
    assert [o.model for o in outcomes].count(FALLBACK) == 1


async def test_smoke_check_reports_failures_instead_of_raising() -> None:
    chain = build_chain(FakeLLMProvider())  # unscripted: every call is rejected
    outcomes = await LLMSmokeCheck(chain.client, routing(), include_fallbacks=False).run(job())
    assert len(outcomes) == len(LLMTask)
    assert not any(outcome.ok for outcome in outcomes)
    assert {outcome.error for outcome in outcomes} == {"LLMUnavailable"}
