"""The explanation eval: LLM text vs template, retries, failures and uncached latency."""

from decimal import Decimal
from typing import Any

from tests.fakes.llm import FixedClock
from tests.unit.discovery.test_explanation import ScriptedClient
from tests.unit.discovery.test_search import CTX, WEEKEND, search
from villasanj.discovery.application.explanation import ExplainChoice, Source
from villasanj.discovery.application.explanation_eval import EvaluateExplanations
from villasanj.discovery.application.intent import SearchIntent
from villasanj.shared.application.errors import LLMOutputInvalid
from villasanj.shared.application.llm.types import JobContext, LLMRequest, LLMResponse

QUERY = "ویلای استخردار در رامسر برای ۴ نفر آخر هفته زیر ۵ میلیون"
NAMES = {"p": "پلتفرم"}


async def evaluate(intent: SearchIntent, client: Any) -> Any:
    run = EvaluateExplanations(search(intent), ExplainChoice(client), NAMES, FixedClock())
    return await run.run([QUERY], CTX)


async def test_a_verified_text_counts_as_llm_with_its_latency() -> None:
    report = await evaluate(WEEKEND, ScriptedClient("این ویلا {F1} است و {F2}."))
    (case,) = report.cases
    assert (case.source, case.retried, case.model) == (Source.LLM, False, "model-a")
    assert report.share(Source.LLM) == 1.0
    assert report.latency_ms() == {"model-a": (1, 900, 900)}
    assert report.cost_usd == Decimal("0.003")  # understanding + explanation


async def test_a_text_that_fails_twice_is_counted_as_a_template_fallback() -> None:
    report = await evaluate(WEEKEND, ScriptedClient("۲ خوابه", "۳ خوابه"))
    (case,) = report.cases
    assert (case.source, case.retried) == (Source.TEMPLATE, True)
    assert report.share(Source.TEMPLATE) == 1.0
    assert report.retried == 1
    assert report.latency_ms() == {"model-a": (1, 1800, 1800)}  # both calls


async def test_nothing_to_explain_and_failures_are_counted_apart() -> None:
    no_dates = await evaluate(SearchIntent(guest_parts=[4]), ScriptedClient())
    assert no_dates.cases[0].source is None
    assert no_dates.explained == []
    assert no_dates.share(Source.LLM) is None

    class Broken:
        async def generate(
            self, request: LLMRequest[Any], ctx: JobContext, *, model: str | None = None
        ) -> LLMResponse[Any]:
            raise LLMOutputInvalid("never matched the schema")

    broken = await evaluate(WEEKEND, Broken())
    assert broken.failures == 1
    assert broken.cases[0].failure == "LLMOutputInvalid"
