"""The query-understanding eval: slot accuracy over the union, invented numbers, latency."""

from decimal import Decimal
from pathlib import Path

import pytest

from tests.unit.discovery.test_understanding import ScriptedClient
from villasanj.discovery.application.intent import Budget, DateSpec, SearchIntent
from villasanj.discovery.application.understanding import UnderstandQuery
from villasanj.discovery.application.understanding_eval import (
    EvalCase,
    EvaluateUnderstanding,
    slot_values,
)
from villasanj.discovery.infrastructure.eval_cases import load_cases
from villasanj.shared.application.errors import ConfigurationError
from villasanj.shared.application.llm.types import JobContext

CTX = JobContext("job", Decimal(1))
WEEKEND = SearchIntent(dates=DateSpec(kind="weekend"), guest_parts=[4, 2])


def test_slots_compare_meanings_not_spellings() -> None:
    assert slot_values(WEEKEND) == {"dates.kind": "weekend", "dates.which": "this", "guests": 6}
    assert slot_values(SearchIntent(party="couple")) == {"guests": 2}
    assert slot_values(SearchIntent(guest_parts=[2])) == {"guests": 2}  # same meaning
    tonight = slot_values(SearchIntent(dates=DateSpec(kind="tonight")))
    assert "dates.which" not in tonight  # "which" only matters for weekdays and weekends


async def test_the_report_counts_wrong_missing_and_extra_slots() -> None:
    cases = [
        EvalCase("آخر هفته برای ۴ بزرگسال و ۲ بچه", WEEKEND),
        EvalCase(
            "آخر هفته کلاً زیر ۵ میلیون",
            SearchIntent(
                dates=DateSpec(kind="weekend"),
                budget=Budget(max_toman=5_000_000, basis="whole_stay"),
            ),
        ),
    ]
    answers = (
        WEEKEND,
        SearchIntent(
            dates=DateSpec(kind="weekend", which="next"),
            budget=Budget(max_toman=5_000_000, basis="per_night"),
        ),
    )
    report = await EvaluateUnderstanding(UnderstandQuery(ScriptedClient(*answers))).run(cases, CTX)
    first, second = report.cases
    assert first.wrong == ()
    assert second.wrong == ("budget.basis", "dates.which")
    assert report.per_slot["dates.which"] == (1, 2)
    assert report.slot_accuracy == pytest.approx(5 / 7)  # 3 of 3, then 2 of 4
    assert report.exact_match == 0.5
    assert "-" not in report.latency_ms()  # a failed case has no latency to report
    assert report.invented == 0
    assert report.cost_usd == Decimal("0.002")
    assert report.latency_ms() == {"model-a": (2, 5, 5)}


def test_cases_load_from_json_lines(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(
        '// comment\n{"query": "امشب", "expected": {"dates": {"kind": "tonight"}}}\n\n',
        encoding="utf-8",
    )
    (case,) = load_cases(path)
    assert case.expected.dates is not None
    path.write_text('{"query": "امشب", "expected": {"guests": 4}}\n', encoding="utf-8")
    with pytest.raises(ConfigurationError, match=":1:"):
        load_cases(path)
    with pytest.raises(ConfigurationError):
        load_cases(tmp_path / "missing.jsonl")


def test_the_draft_cases_in_the_repository_load() -> None:
    path = Path(__file__).parents[4] / "eval" / "query-understanding" / "draft-v0.jsonl"
    assert len(load_cases(path)) >= 10


class FailingOnce:
    """A client whose answer for one query never passes validation."""

    def __init__(self, bad_query: str, answer: SearchIntent) -> None:
        self.bad_query, self.answer = bad_query, answer

    async def generate(
        self, request: object, ctx: JobContext, *, model: str | None = None
    ) -> object:
        from villasanj.shared.application.errors import LLMOutputInvalid
        from villasanj.shared.application.llm.types import LLMResponse, TokenUsage

        text = request.messages[-1].text  # type: ignore[attr-defined]
        if self.bad_query in text:
            raise LLMOutputInvalid("extra fields")
        return LLMResponse(self.answer, "m", TokenUsage(1, 1), Decimal("0.001"), False, 1, 5)


async def test_a_query_without_a_usable_answer_is_a_failed_case_not_a_crash() -> None:
    cases = [
        EvalCase("آخر هفته", SearchIntent(dates=DateSpec(kind="weekend"))),
        EvalCase("امشب", SearchIntent(dates=DateSpec(kind="tonight"))),
    ]
    client = FailingOnce("امشب", SearchIntent(dates=DateSpec(kind="weekend")))
    report = await EvaluateUnderstanding(UnderstandQuery(client)).run(cases, CTX)  # type: ignore[arg-type]
    assert report.failures == 1
    failed = report.cases[1]
    assert (failed.failure, failed.wrong) == ("LLMOutputInvalid", ("dates.kind",))
    assert report.exact_match == 0.5
    assert "-" not in report.latency_ms()  # a failed case has no latency to report
