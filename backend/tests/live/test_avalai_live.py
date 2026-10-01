"""Opt-in live checks against AvalAI (``make test-live``). Real calls; capped at $0.05 total."""

from decimal import Decimal
from pathlib import Path

import pytest

from tests.fakes.llm import FixedClock, InMemoryLLMCache, InMemoryLLMLedger
from villasanj.entrypoints.container import build_llm_stack
from villasanj.shared.application.llm.smoke import LLMSmokeCheck
from villasanj.shared.application.llm.types import JobContext
from villasanj.shared.infrastructure.settings import Settings

pytestmark = pytest.mark.live_llm

LIVE_BUDGET_USD = Decimal("0.05")
CONFIG = Path(__file__).resolve().parents[3] / "config"


@pytest.fixture
def settings() -> Settings:
    settings = Settings(config_dir=CONFIG)
    if settings.avalai_api_key is None:
        pytest.skip("AVALAI_API_KEY is not set")
    avalai = settings.llm.model_copy(update={"provider": "avalai"})
    return settings.model_copy(update={"llm": avalai})


async def test_every_task_route_and_fallback_returns_valid_structured_output(
    settings: Settings,
) -> None:
    ledger = InMemoryLLMLedger()
    stack = build_llm_stack(settings, InMemoryLLMCache(), ledger, FixedClock())
    assert await stack.provider.ready()

    outcomes = await LLMSmokeCheck(stack.client, stack.routing, include_fallbacks=True).run(
        JobContext(job_id="live-test", budget_usd=LIVE_BUDGET_USD)
    )
    for outcome in outcomes:
        print(f"{outcome.task:<22} {outcome.model:<24} ok={outcome.ok} ${outcome.cost_usd:.6f}")
    spent = await ledger.spent_total_usd()
    print(f"total ledger spend: ${spent:.6f} over {len(ledger.entries)} attempts")

    assert all(outcome.ok for outcome in outcomes), [o for o in outcomes if not o.ok]
    assert spent < LIVE_BUDGET_USD
