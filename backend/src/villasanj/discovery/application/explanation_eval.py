"""Explanation eval (ROADMAP M10 criteria 2 and 4): how often the LLM text is shown, latency.

Each query runs through search and its first result is explained, as the search page does.
Every displayed explanation passed the verifier by construction (a text that fails twice is
replaced by the deterministic template), so the report counts how often the LLM text was used,
how often it needed its one retry and how often the template was shown instead. Latency
percentiles use uncached explanations only and are reported per model.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from villasanj.discovery.application.explanation import ExplainChoice, Source, explain_first
from villasanj.discovery.application.search import SearchListings
from villasanj.discovery.application.understanding_eval import PERCENTILE_95, percentile
from villasanj.shared.application.clock import Clock
from villasanj.shared.application.errors import LLMError
from villasanj.shared.application.llm.types import JobContext


@dataclass(frozen=True, slots=True)
class ExplainedCase:
    query: str
    source: Source | None  # ``None``: nothing to explain (no result, or no dates to price)
    retried: bool = False
    latency_ms: int = 0
    cache_hit: bool = False
    model: str = "-"
    failure: str | None = None  # the search or the explanation raised (counted, not hidden)
    text: str = ""  # the rendered explanation, for a human to read


@dataclass(frozen=True, slots=True)
class ExplanationReport:
    cases: list[ExplainedCase]
    cost_usd: Decimal = Decimal(0)

    @property
    def explained(self) -> list[ExplainedCase]:
        return [c for c in self.cases if c.source is not None]

    def share(self, source: Source) -> float | None:
        explained = self.explained
        if not explained:
            return None
        return sum(c.source is source for c in explained) / len(explained)

    @property
    def retried(self) -> int:
        return sum(c.retried for c in self.explained)

    @property
    def failures(self) -> int:
        return sum(c.failure is not None for c in self.cases)

    def latency_ms(self) -> dict[str, tuple[int, int, int]]:
        """Per model: (uncached explanations, p50, p95) in milliseconds."""
        by_model: dict[str, list[int]] = defaultdict(list)
        for case in self.explained:
            if not case.cache_hit:
                by_model[case.model].append(case.latency_ms)
        return {
            model: (len(values), percentile(values, 0.5), percentile(values, PERCENTILE_95))
            for model, values in sorted(by_model.items())
        }


class EvaluateExplanations:
    def __init__(
        self,
        search: SearchListings,
        explainer: ExplainChoice,
        platform_names: Mapping[str, str],
        clock: Clock,
    ) -> None:
        self._search = search
        self._explainer = explainer
        self._names = platform_names
        self._clock = clock

    async def run(self, queries: Sequence[str], ctx: JobContext) -> ExplanationReport:
        cases: list[ExplainedCase] = []
        cost = Decimal(0)
        for query in queries:
            try:
                result = await self._search.run(query, ctx)
                cost += result.understanding.cost_usd
                why = await explain_first(
                    self._explainer, result, self._names, self._clock.now(), ctx
                )
            except LLMError as error:
                cases.append(ExplainedCase(query, None, failure=type(error).__name__))
                continue
            if why is None:
                cases.append(ExplainedCase(query, None))
                continue
            cost += why.cost_usd
            cases.append(
                ExplainedCase(
                    query,
                    why.source,
                    why.retried,
                    why.latency_ms,
                    why.cache_hit,
                    why.models[-1] if why.models else "-",
                    failure=why.failure,  # no model answer: counted, though the template showed
                    text=why.rendered.text,
                )
            )
        return ExplanationReport(cases, cost)
