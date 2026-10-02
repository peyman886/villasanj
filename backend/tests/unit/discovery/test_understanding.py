"""Query understanding: verified intents, one retry with the violations, then drop."""

import hashlib
from decimal import Decimal
from typing import Any

from villasanj.discovery.application import understanding
from villasanj.discovery.application.intent import Budget, DateSpec, SearchIntent
from villasanj.discovery.application.understanding import UnderstandQuery
from villasanj.shared.application.llm.types import (
    JobContext,
    LLMRequest,
    LLMResponse,
    LLMTask,
    Role,
    TokenUsage,
)

# A prompt change needs a new version, so answers cached for the old prompt are not reused.
PINNED = {"3": "6472f1a32629739c387bfa7a057b4fcb592492e6237f7d6bbb5faebf900bc5e1"}
CTX = JobContext("job", Decimal(1))
QUERY = "ویلا برای ۴ نفر آخر هفته زیر ۵ میلیون در رامسر"


class ScriptedClient:
    def __init__(self, *answers: SearchIntent) -> None:
        self.answers = list(answers)
        self.requests: list[LLMRequest[Any]] = []

    async def generate(
        self, request: LLMRequest[Any], ctx: JobContext, *, model: str | None = None
    ) -> LLMResponse[Any]:
        self.requests.append(request)
        value = self.answers.pop(0)
        usage = TokenUsage(input_tokens=900, output_tokens=80)
        return LLMResponse(value, "model-a", usage, Decimal("0.001"), False, 1, 5)


def test_prompt_changes_require_a_version_bump() -> None:
    text = understanding.SYSTEM_PROMPT + understanding.RETRY_TEMPLATE
    digest = hashlib.sha256(text.encode()).hexdigest()
    assert PINNED.get(understanding.QUERY_PROMPT_VERSION) == digest, (
        "the query prompt changed: bump QUERY_PROMPT_VERSION and pin the new hash"
    )


HONEST = SearchIntent(
    dates=DateSpec(kind="weekend"),
    guest_parts=[4],
    budget=Budget(max_toman=5_000_000),
    places=["رامسر"],
)


async def test_an_honest_answer_is_used_as_is_with_one_call() -> None:
    client = ScriptedClient(HONEST)
    result = await UnderstandQuery(client).run(QUERY, CTX)
    assert result.intent == HONEST
    assert (result.retried, result.dropped, result.models) == (False, (), ("model-a",))
    (request,) = client.requests
    assert request.task is LLMTask.QUERY_UNDERSTANDING
    assert request.messages[-1].text == f"Query: {QUERY}"


async def test_a_broken_rule_is_retried_once_with_the_violations() -> None:
    invented = HONEST.model_copy(update={"nights": 2})  # "آخر هفته" says no number of nights
    client = ScriptedClient(invented, HONEST)
    result = await UnderstandQuery(client).run(QUERY, CTX)
    assert result.intent == HONEST
    assert result.retried
    assert result.cost_usd == Decimal("0.002")
    retry = client.requests[1]
    assert [m.role for m in retry.messages] == [Role.SYSTEM, Role.USER, Role.ASSISTANT, Role.USER]
    assert '"nights":2' in retry.messages[2].text
    assert "number_not_in_source: 2" in retry.messages[3].text


async def test_what_is_still_broken_after_the_retry_is_dropped() -> None:
    invented = HONEST.model_copy(update={"nights": 2, "places": ["رامسر", "کلارآباد"]})
    result = await UnderstandQuery(ScriptedClient(invented, invented)).run(QUERY, CTX)
    assert result.intent == HONEST
    assert result.dropped == ("nights", "places")


def test_plan_prices_one_request_per_query_with_zero_calls() -> None:
    requests = UnderstandQuery(ScriptedClient(), [QUERY, "امشب"]).plan()
    assert [r.messages[-1].text for r in requests] == [f"Query: {QUERY}", "Query: امشب"]


async def test_a_guessed_budget_basis_becomes_unknown_without_a_retry() -> None:
    assert HONEST.budget is not None
    guessed = HONEST.model_copy(
        update={"budget": HONEST.budget.model_copy(update={"basis": "whole_stay"})}
    )
    client = ScriptedClient(guessed)
    result = await UnderstandQuery(client).run(QUERY, CTX)
    assert result.intent == HONEST  # the query says no basis: the search asks instead
    assert (result.retried, result.dropped) == (False, ())
    assert len(client.requests) == 1
