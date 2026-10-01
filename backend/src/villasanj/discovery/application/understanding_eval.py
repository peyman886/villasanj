"""Query-understanding eval (ROADMAP M8 criterion 1): slot accuracy, invented numbers, latency.

Each case is a query and the intent a person expects. Slots are compared one by one over the union
of the expected and the predicted slots, so a missing slot and an extra slot both count as wrong.
Invented numbers are counted on the final intents (after the verifier and the drop step), where
the target is zero; retries and dropped fields show how often the model needed correcting.
Latency percentiles use uncached calls only and are reported per model.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from villasanj.discovery.application.intent import SearchIntent, verify_intent
from villasanj.discovery.application.understanding import UnderstandQuery
from villasanj.shared.application.llm.types import JobContext

PERCENTILE_95 = 0.95


@dataclass(frozen=True, slots=True)
class EvalCase:
    query: str
    expected: SearchIntent


def slot_values(intent: SearchIntent) -> dict[str, object]:
    """The intent as comparable slots (absent slots are left out)."""
    dates = intent.dates
    values: dict[str, object] = {
        "dates.kind": dates.kind if dates else None,
        "dates.which": dates.which if dates and dates.kind in ("weekday", "weekend") else None,
        "dates.weekday": dates.weekday if dates else None,
        "dates.month": dates.month if dates else None,
        "dates.day": dates.day if dates else None,
        "dates.year": dates.year if dates else None,
        "nights": intent.nights,
        "guests": intent.guests,
        "bedrooms_min": intent.bedrooms_min,
        "budget.max_toman": intent.budget.max_toman if intent.budget else None,
        "budget.basis": intent.budget.basis if intent.budget else None,
        "max_drive.minutes": intent.max_drive.minutes if intent.max_drive else None,
        "places": frozenset(intent.places) or None,
        "features": frozenset(intent.features) or None,
    }
    return {name: value for name, value in values.items() if value is not None}


@dataclass(frozen=True, slots=True)
class CaseResult:
    query: str
    expected: dict[str, object]
    got: dict[str, object]
    wrong: tuple[str, ...]  # slots that differ (missing, extra or a different value)
    invented: int  # numbers in the final intent the query does not say (target: 0)
    retried: bool
    dropped: tuple[str, ...]
    latency_ms: int
    cache_hit: bool
    model: str


@dataclass(frozen=True, slots=True)
class UnderstandingReport:
    cases: list[CaseResult]
    per_slot: dict[str, tuple[int, int]] = field(default_factory=dict)  # slot -> (right, seen)
    cost_usd: Decimal = Decimal(0)

    @property
    def slot_accuracy(self) -> float:
        right = sum(r for r, _ in self.per_slot.values())
        seen = sum(s for _, s in self.per_slot.values())
        return right / seen if seen else 1.0

    @property
    def exact_match(self) -> float:
        return sum(not c.wrong for c in self.cases) / len(self.cases) if self.cases else 1.0

    @property
    def invented(self) -> int:
        return sum(c.invented for c in self.cases)

    def latency_ms(self) -> dict[str, tuple[int, int, int]]:
        """Per model: (uncached calls, p50, p95) in milliseconds."""
        by_model: dict[str, list[int]] = defaultdict(list)
        for case in self.cases:
            if not case.cache_hit:
                by_model[case.model].append(case.latency_ms)
        return {
            model: (len(values), _percentile(values, 0.5), _percentile(values, PERCENTILE_95))
            for model, values in sorted(by_model.items())
        }


def _percentile(values: list[int], q: float) -> int:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


class EvaluateUnderstanding:
    def __init__(self, understand: UnderstandQuery) -> None:
        self._understand = understand

    async def run(self, cases: Sequence[EvalCase], ctx: JobContext) -> UnderstandingReport:
        results: list[CaseResult] = []
        per_slot: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        cost = Decimal(0)
        for case in cases:
            understanding = await self._understand.run(case.query, ctx)
            cost += understanding.cost_usd
            expected, got = slot_values(case.expected), slot_values(understanding.intent)
            wrong = []
            for name in sorted(expected.keys() | got.keys()):
                per_slot[name][1] += 1
                if expected.get(name) == got.get(name):
                    per_slot[name][0] += 1
                else:
                    wrong.append(name)
            results.append(
                CaseResult(
                    query=case.query,
                    expected=expected,
                    got=got,
                    wrong=tuple(wrong),
                    invented=len(verify_intent(understanding.intent, case.query)),
                    retried=understanding.retried,
                    dropped=understanding.dropped,
                    latency_ms=understanding.latency_ms,
                    cache_hit=understanding.cache_hit,
                    model=understanding.models[-1],
                )
            )
        return UnderstandingReport(
            results, {name: (r, s) for name, (r, s) in per_slot.items()}, cost
        )
