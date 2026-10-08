"""The LLM decorator chain, end to end with a scripted provider (zero network)."""

import asyncio
from dataclasses import replace
from decimal import Decimal

import pytest

from tests.fakes.llm import (
    FALLBACK,
    INVALID,
    NOW,
    PRIMARY,
    VALID,
    Answer,
    InMemoryLLMLedger,
    build_chain,
    job,
    request,
    routing,
)
from villasanj.shared.application.errors import (
    BudgetExceeded,
    ConfigurationError,
    LLMOutputInvalid,
    LLMUnavailable,
)
from villasanj.shared.application.llm.ports import (
    CallStatus,
    FinishReason,
    LedgerEntry,
    ModelCall,
    ProviderAuthError,
    ProviderCall,
    ProviderRejectedError,
    ProviderResult,
    ProviderTransientError,
)
from villasanj.shared.application.llm.types import LLMTask, TokenUsage, UsageSource
from villasanj.shared.infrastructure.llm.fake import FakeLLMProvider

USAGE = TokenUsage(input_tokens=1000, output_tokens=500)  # $0.001 + $0.001 at test prices


def statuses(ledger: InMemoryLLMLedger) -> list[tuple[str, CallStatus]]:
    return [(entry.model, entry.status) for entry in ledger.entries]


async def test_success_is_priced_and_recorded() -> None:
    chain = build_chain(FakeLLMProvider([VALID], usage=USAGE))
    response = await chain.client.generate(request(), job())
    assert response.value == Answer(answer="yes", confidence=0.9)
    assert response.cost_usd == Decimal("0.002")
    assert response.attempts == 1
    assert statuses(chain.ledger) == [(PRIMARY, CallStatus.OK)]


async def test_identical_request_hits_cache_and_costs_nothing() -> None:
    provider = FakeLLMProvider([VALID], usage=USAGE)
    chain = build_chain(provider)
    await chain.client.generate(request(), job())
    second = await chain.client.generate(request(), job())
    assert len(provider.calls) == 1
    assert second.cache_hit
    assert second.cost_usd == 0
    assert statuses(chain.ledger)[-1] == (PRIMARY, CallStatus.CACHE_HIT)
    assert chain.ledger.entries[-1].cost_usd == 0


async def test_a_fresh_job_skips_cache_reads_and_refreshes_the_cache() -> None:
    provider = FakeLLMProvider([VALID, VALID], usage=USAGE)
    chain = build_chain(provider)
    await chain.client.generate(request(), job())
    measured = await chain.client.generate(request(), replace(job(), fresh=True))
    assert len(provider.calls) == 2  # measured again, not served from the cache
    assert not measured.cache_hit
    again = await chain.client.generate(request(), job())
    assert again.cache_hit  # an ordinary job still reads the cache


async def test_prompt_version_change_misses_cache() -> None:
    provider = FakeLLMProvider([VALID, VALID])
    chain = build_chain(provider)
    await chain.client.generate(request(prompt_version="1"), job())
    await chain.client.generate(request(prompt_version="2"), job())
    assert len(provider.calls) == 2


async def test_invalid_then_valid_retries_with_feedback() -> None:
    provider = FakeLLMProvider([INVALID, VALID], usage=USAGE)
    chain = build_chain(provider)
    response = await chain.client.generate(request(), job())
    assert response.attempts == 2
    assert statuses(chain.ledger) == [
        (PRIMARY, CallStatus.INVALID_OUTPUT),
        (PRIMARY, CallStatus.OK),
    ]
    feedback = provider.calls[1].messages[-1].text
    assert "confidence: missing" in feedback
    assert response.cost_usd == Decimal("0.002")  # this attempt; the failed one is in the ledger
    assert await chain.ledger.spent_usd("job-1") == Decimal("0.004")


async def test_output_that_stays_invalid_raises_without_leaking_content() -> None:
    provider = FakeLLMProvider([INVALID, INVALID, INVALID])
    chain = build_chain(provider)
    with pytest.raises(LLMOutputInvalid) as caught:
        await chain.client.generate(request(), job())
    assert '"answer"' not in str(caught.value)
    assert len(chain.ledger.entries) == 3
    assert len(provider.calls) == 3  # never falls back to shop for a better answer


async def test_truncated_output_is_recorded_and_retried() -> None:
    truncated = ProviderResult(
        text='{"answ', usage=USAGE, finish_reason=FinishReason.LENGTH, latency_ms=5
    )
    chain = build_chain(FakeLLMProvider([truncated, VALID]))
    response = await chain.client.generate(request(), job())
    assert response.attempts == 2
    assert chain.ledger.entries[0].status is CallStatus.TRUNCATED


async def test_transient_errors_back_off_then_fall_back() -> None:
    provider = FakeLLMProvider(
        [ProviderTransientError("http-503")] * 3 + [VALID]  # 3 attempts on primary, then fallback
    )
    chain = build_chain(provider)
    response = await chain.client.generate(request(), job())
    assert response.model == FALLBACK
    assert [call.model for call in provider.calls] == [PRIMARY] * 3 + [FALLBACK]
    assert statuses(chain.ledger)[-1] == (FALLBACK, CallStatus.OK)
    assert chain.sleep.delays == [1.0, 2.0]  # exponential backoff (jitter pinned to max)


async def test_retry_after_header_is_honoured() -> None:
    provider = FakeLLMProvider([ProviderTransientError("http-429", retry_after_seconds=7), VALID])
    chain = build_chain(provider)
    await chain.client.generate(request(), job())
    assert chain.sleep.delays == [7]


async def test_rejected_request_falls_back_without_retrying() -> None:
    provider = FakeLLMProvider([ProviderRejectedError("http-400"), VALID])
    chain = build_chain(provider)
    response = await chain.client.generate(request(), job())
    assert response.model == FALLBACK
    assert chain.sleep.delays == []
    assert statuses(chain.ledger)[0] == (PRIMARY, CallStatus.REJECTED)


async def test_all_models_failing_raises_unavailable() -> None:
    provider = FakeLLMProvider([ProviderRejectedError("http-404")] * 2)
    chain = build_chain(provider)
    with pytest.raises(LLMUnavailable, match="http-404"):
        await chain.client.generate(request(), job())


async def test_auth_failure_neither_retries_nor_falls_back() -> None:
    provider = FakeLLMProvider([ProviderAuthError("http-401"), VALID])
    chain = build_chain(provider)
    with pytest.raises(LLMUnavailable, match="credentials"):
        await chain.client.generate(request(), job())
    assert len(provider.calls) == 1


async def test_job_budget_is_checked_before_calling() -> None:
    provider = FakeLLMProvider([VALID])
    chain = build_chain(provider)
    with pytest.raises(BudgetExceeded, match="job budget"):
        await chain.client.generate(request(), job(budget="0.0001"))
    assert provider.calls == []


async def test_project_budget_is_checked_before_calling() -> None:
    ledger = InMemoryLLMLedger()
    await ledger.record(
        LedgerEntry(
            job_id="earlier-job",
            task=LLMTask.ER_JUDGE,
            model=PRIMARY,
            prompt_id="p",
            prompt_version="1",
            attempt=1,
            status=CallStatus.OK,
            usage=USAGE,
            cost_usd=Decimal("29.9995"),
            latency_ms=1,
            created_at=NOW,
        )
    )
    provider = FakeLLMProvider([VALID])
    chain = build_chain(provider, ledger=ledger)
    with pytest.raises(BudgetExceeded, match="project budget"):
        await chain.client.generate(request(), job())
    assert provider.calls == []


async def test_concurrent_calls_reserve_budget() -> None:
    gate = asyncio.Event()

    class SlowProvider(FakeLLMProvider):
        async def complete(self, call: ProviderCall) -> ProviderResult:
            await gate.wait()
            return await super().complete(call)

    provider = SlowProvider(responder=lambda _call: VALID)
    chain = build_chain(provider)
    worst = chain.governor.worst_case_cost(
        ModelCall(
            request=request(), route=routing().route(LLMTask.ER_JUDGE), model=PRIMARY, ctx=job()
        )
    )
    budget = str(worst * Decimal("1.5"))
    first = asyncio.create_task(chain.client.generate(request(text="first"), job(budget)))
    await asyncio.sleep(0)
    with pytest.raises(BudgetExceeded):
        await chain.client.generate(request(text="second"), job(budget))
    gate.set()
    assert (await first).value.answer == "yes"


async def test_missing_usage_is_estimated_and_labelled() -> None:
    no_usage = ProviderResult(text=VALID, usage=None, finish_reason=FinishReason.STOP, latency_ms=1)
    chain = build_chain(FakeLLMProvider([no_usage]))
    response = await chain.client.generate(request(), job())
    assert response.usage.source is UsageSource.ESTIMATED
    assert response.usage.input_tokens > 0
    assert response.cost_usd > 0


async def test_pinning_an_unconfigured_model_is_refused() -> None:
    chain = build_chain(FakeLLMProvider([VALID]))
    with pytest.raises(ConfigurationError):
        await chain.client.generate(request(), job(), model="some-other-model")


async def test_pinning_a_configured_fallback_uses_only_that_model() -> None:
    provider = FakeLLMProvider([VALID])
    chain = build_chain(provider)
    response = await chain.client.generate(request(), job(), model=FALLBACK)
    assert response.model == FALLBACK
    assert [call.model for call in provider.calls] == [FALLBACK]
