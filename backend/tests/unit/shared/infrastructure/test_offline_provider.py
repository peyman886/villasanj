"""The offline demo provider: cached answers only, never a connection (M11 criterion 1)."""

import pytest

from tests.fakes.llm import VALID, FixedClock, InMemoryLLMCache, InMemoryLLMLedger, job, request
from villasanj.entrypoints.container import build_llm_stack
from villasanj.shared.application.errors import LLMUnavailable
from villasanj.shared.infrastructure.llm.fake import FakeLLMProvider
from villasanj.shared.infrastructure.llm.offline import OfflineProvider
from villasanj.shared.infrastructure.settings import Settings


async def test_only_answers_cached_by_the_real_provider_are_served() -> None:
    settings = Settings(_env_file=None)
    cache, ledger, clock = InMemoryLLMCache(), InMemoryLLMLedger(), FixedClock()
    online = FakeLLMProvider(responder=lambda _call: VALID)
    online.name = "avalai"  # the provider whose answers the demo replays
    warm = build_llm_stack(settings, cache, ledger, clock, provider=online)
    asked = request(text="cached question")
    await warm.client.generate(asked, job())

    offline = build_llm_stack(settings, cache, ledger, clock, provider=OfflineProvider("avalai"))
    replayed = await offline.client.generate(asked, job())
    assert replayed.cache_hit
    assert replayed.value.answer == "yes"
    with pytest.raises(LLMUnavailable):
        await offline.client.generate(request(text="never asked"), job())
    assert await OfflineProvider("avalai").ready()
