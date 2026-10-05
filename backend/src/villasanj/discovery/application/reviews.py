"""The owner's reviews for M8: the expected intents of the query set, and search relevance.

Criterion 1 counts only on queries whose expected intent a person has checked: the owner reads
each drafted case and accepts it, corrects it or rejects it. Criterion 2 needs relevance
judgements: for each of about 30 queries the shipped ranking and two single-component baselines
(cheapest first, best rated first) are run once, their top results are pooled and shown blind
(no rank, no system), and the owner grades each villa 0, 1 or 2. nDCG@10 and Recall@20 are then
computed per system from the stored rankings, so the numbers do not move when the catalog does.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

from pydantic import ValidationError

from villasanj.discovery.application.intent import SearchIntent
from villasanj.discovery.application.search import SearchListings, SearchResult
from villasanj.discovery.domain.ranking import Ranked
from villasanj.enrichment.domain.features import FeatureEvidence
from villasanj.shared.application.clock import Clock
from villasanj.shared.application.llm.types import JobContext
from villasanj.shared.domain.jalali import iran_today

QUERY_KIND = "query"
RELEVANCE_KIND = "relevance"
GRADES = (0, 1, 2)  # not relevant, partly relevant, relevant
SYSTEMS = ("ranking", "price", "rating")  # the shipped order and two baselines
SAID = frozenset(  # evidence that the villa has a feature (the ranking's "confirmed")
    {
        FeatureEvidence.LISTED,
        FeatureEvidence.MEASURED,
        FeatureEvidence.PHOTO,
        FeatureEvidence.DESCRIBED,
    }
)
RANKING_DEPTH = 20  # Recall@20 needs the shipped ranking's top 20 judged
BASELINE_DEPTH = 10  # nDCG@10 needs the baselines' top 10 judged
MIN_RESULTS = 3  # a query with fewer results says little about ranking


class ReviewQueueExists(ValueError):
    """Queues are built once: a second build would change what was reviewed."""


@dataclass(frozen=True, slots=True)
class ReviewCase:
    position: int
    payload: Mapping[str, object]


class ReviewStore(Protocol):
    async def cases(self, queue: str) -> list[ReviewCase]: ...

    async def save_cases(
        self, queue: str, kind: str, cases: Sequence[ReviewCase], at: datetime
    ) -> None: ...

    async def labels(self, queue: str, labeler: str) -> dict[tuple[int, str], dict[str, object]]:
        """(position, item) -> the label; item is "" for a whole case."""
        ...

    async def save_label(
        self,
        queue: str,
        position: int,
        item: str,
        labeler: str,
        value: Mapping[str, object],
        at: datetime,
    ) -> None: ...


# ------------------------------------------------------------------ query review (criterion 1)


@dataclass(frozen=True, slots=True)
class DraftCase:
    query: str
    expected: dict[str, object]  # SearchIntent JSON as drafted
    note: str


@dataclass(frozen=True, slots=True)
class QueryVerdict:
    correct: bool
    corrected: dict[str, object] | None  # the intent the owner expects instead, if given
    note: str | None


class InvalidIntent(ValueError):
    """A corrected intent that the SearchIntent schema rejects."""


class BuildQueryReviewQueue:
    def __init__(self, store: ReviewStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    async def run(self, name: str, drafts: Sequence[DraftCase]) -> int:
        if await self._store.cases(name):
            raise ReviewQueueExists(name)
        cases = [
            ReviewCase(position, {"query": d.query, "expected": d.expected, "note": d.note})
            for position, d in enumerate(drafts, start=1)
        ]
        await self._store.save_cases(name, QUERY_KIND, cases, self._clock.now())
        return len(cases)


@dataclass(frozen=True, slots=True)
class QueryReviewTask:
    position: int
    total: int
    reviewed: int
    query: str
    expected: dict[str, object]
    note: str
    current: QueryVerdict | None
    done: bool


def _verdict(value: Mapping[str, object] | None) -> QueryVerdict | None:
    if value is None:
        return None
    corrected = value.get("corrected")
    note = value.get("note")
    return QueryVerdict(
        bool(value.get("correct")),
        dict(corrected) if isinstance(corrected, dict) else None,
        str(note) if note else None,
    )


def normalize_intent(raw: Mapping[str, object]) -> dict[str, object]:
    """The intent as the schema reads it (defaults dropped), or ``InvalidIntent``."""
    try:
        intent = SearchIntent.model_validate(raw)
    except ValidationError as error:
        raise InvalidIntent(str(error)) from None
    return intent.model_dump(mode="json", exclude_defaults=True)


class QueryReviewing:
    def __init__(self, store: ReviewStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    async def task(
        self, queue: str, labeler: str, position: int | None = None
    ) -> QueryReviewTask | None:
        """The case at ``position``, or the first not reviewed yet; ``None``: no such queue."""
        cases = await self._store.cases(queue)
        if not cases:
            return None
        labels = await self._store.labels(queue, labeler)
        if position is not None:
            case = next((c for c in cases if c.position == position), cases[0])
        else:
            case = next((c for c in cases if (c.position, "") not in labels), cases[-1])
        reviewed = sum((c.position, "") in labels for c in cases)
        expected = case.payload.get("expected")
        return QueryReviewTask(
            case.position,
            len(cases),
            reviewed,
            str(case.payload["query"]),
            dict(expected) if isinstance(expected, dict) else {},
            str(case.payload.get("note") or ""),
            _verdict(labels.get((case.position, ""))),
            reviewed == len(cases),
        )

    async def record(self, queue: str, position: int, labeler: str, verdict: QueryVerdict) -> bool:
        """``False`` when the case is not in the queue; ``InvalidIntent`` for a bad correction."""
        if position not in {c.position for c in await self._store.cases(queue)}:
            return False
        corrected = normalize_intent(verdict.corrected) if verdict.corrected is not None else None
        value: dict[str, object] = {"correct": verdict.correct, "note": verdict.note}
        if corrected is not None:
            value["corrected"] = corrected
        await self._store.save_label(queue, position, "", labeler, value, self._clock.now())
        return True


@dataclass(frozen=True, slots=True)
class ReviewedCases:
    cases: list[DraftCase]  # accepted as drafted, or with the owner's correction
    accepted: int
    corrected: int
    rejected: int  # wrong and not corrected: left out of the eval
    unreviewed: int


class ExportReviewedQueries:
    """The eval set the owner signed off: accepted cases as drafted, corrected ones as corrected."""

    def __init__(self, store: ReviewStore) -> None:
        self._store = store

    async def run(self, queue: str, labeler: str) -> ReviewedCases:
        labels = await self._store.labels(queue, labeler)
        out: list[DraftCase] = []
        accepted = corrected = rejected = unreviewed = 0
        for case in await self._store.cases(queue):
            verdict = _verdict(labels.get((case.position, "")))
            query = str(case.payload["query"])
            note = str(case.payload.get("note") or "")
            if verdict is None:
                unreviewed += 1
            elif verdict.correct:
                accepted += 1
                expected = case.payload.get("expected")
                out.append(
                    DraftCase(query, dict(expected) if isinstance(expected, dict) else {}, note)
                )
            elif verdict.corrected is not None:
                corrected += 1
                out.append(DraftCase(query, verdict.corrected, verdict.note or note))
            else:
                rejected += 1
        return ReviewedCases(out, accepted, corrected, rejected, unreviewed)


# ------------------------------------------------------------- relevance review (criterion 2)


def _pool_order(name: str, query: str, keys: Sequence[str]) -> list[str]:
    """A fixed blind order (seeded by the queue and the query): not any system's rank."""
    return sorted(keys, key=lambda k: hashlib.sha256(f"{name}:{query}:{k}".encode()).hexdigest())


def system_orders(results: Sequence[Ranked]) -> dict[str, list[str]]:
    """The shipped ranking and two baselines over the same filtered candidates."""
    ranking = [r.candidate.id for r in results]

    def price(r: Ranked) -> tuple[bool, float]:
        p = r.price_per_person_night_toman
        return (p is None, p or 0.0)

    def rating(r: Ranked) -> tuple[bool, float]:
        return (r.candidate.rating is None, -(r.candidate.rating or 0.0))

    return {
        "ranking": ranking[:RANKING_DEPTH],
        "price": [r.candidate.id for r in sorted(results, key=price)][:RANKING_DEPTH],
        "rating": [r.candidate.id for r in sorted(results, key=rating)][:RANKING_DEPTH],
    }


def _facts(result: SearchResult, ranked: Ranked) -> dict[str, object]:
    """What the reviewer sees for one villa: what the search knew, frozen at build time."""
    key = ranked.candidate.id
    listing = result.listings[key]
    offer = result.offers.get(key)
    geo = result.geo.get(key)
    total = offer.quote.total if offer else None
    coast = geo.coast if geo else None
    drive = geo.drive_minutes if geo else None
    return {
        "listing": key,
        "villa": result.villa_of.get(key),
        "title": listing.title,
        "place": " · ".join(p for p in (listing.locality_fa, listing.city_fa) if p),
        "bedrooms": listing.bedrooms,
        "max_capacity": listing.max_capacity,
        "total_low_toman": int(total.low.toman) if total else None,
        "total_high_toman": int(total.high.toman) if total and total.high else None,
        "per_person_night_toman": ranked.price_per_person_night_toman,
        "rating": ranked.candidate.rating,
        "features": sorted(
            f.value for f, evidence in ranked.candidate.features.items() if evidence in SAID
        ),
        "coast_m": [round(coast.low_m), round(coast.high_m)] if coast else None,
        "drive_min": [round(drive[0]), round(drive[1])] if drive else None,
        "other_platforms": list(result.siblings.get(key, ())),
    }


@dataclass(frozen=True, slots=True)
class RelevanceBuild:
    queued: int
    skipped: dict[str, str]  # query -> why it was left out


class BuildRelevanceQueue:
    def __init__(self, search: SearchListings, store: ReviewStore, clock: Clock) -> None:
        self._search = search
        self._store = store
        self._clock = clock

    async def run(self, name: str, queries: Sequence[str], ctx: JobContext) -> RelevanceBuild:
        if await self._store.cases(name):
            raise ReviewQueueExists(name)
        today = iran_today(self._clock.now())
        cases: list[ReviewCase] = []
        skipped: dict[str, str] = {}
        for query in queries:
            result = await self._search.run(query, ctx)
            if result.ranking is None or result.dates is None:
                skipped[query] = "no concrete dates or group: the search asks instead of ranking"
                continue
            results = result.ranking.results
            if len(results) < MIN_RESULTS:
                skipped[query] = f"{len(results)} results"
                continue
            orders = system_orders(results)
            pooled = set(orders["ranking"][:RANKING_DEPTH])
            for system in ("price", "rating"):
                pooled.update(orders[system][:BASELINE_DEPTH])
            by_key = {r.candidate.id: r for r in results}
            items = [_facts(result, by_key[k]) for k in _pool_order(name, query, list(pooled))]
            cases.append(
                ReviewCase(
                    len(cases) + 1,
                    {
                        "query": query,
                        "today": today.isoformat(),
                        "check_in": result.dates.window.check_in.isoformat(),
                        "check_out": result.dates.window.check_out.isoformat(),
                        "guests": result.understanding.intent.guests,
                        "intent": result.understanding.intent.model_dump(
                            mode="json", exclude_defaults=True
                        ),
                        "results": len(results),
                        "orders": orders,
                        "items": items,
                    },
                )
            )
        if cases:
            await self._store.save_cases(name, RELEVANCE_KIND, cases, self._clock.now())
        return RelevanceBuild(len(cases), skipped)


@dataclass(frozen=True, slots=True)
class RelevanceTask:
    position: int
    total: int
    queries_done: int
    payload: Mapping[str, object]
    grades: dict[str, int]  # listing key -> grade, this reviewer's so far
    done: bool


def _items(case: ReviewCase) -> list[Mapping[str, object]]:
    items = case.payload.get("items")
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def _grades(
    case: ReviewCase, labels: Mapping[tuple[int, str], Mapping[str, object]]
) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in _items(case):
        label = labels.get((case.position, str(item["listing"])))
        grade = label.get("grade") if label else None
        if isinstance(grade, int):
            out[str(item["listing"])] = grade
    return out


def _complete(case: ReviewCase, grades: Mapping[str, int]) -> bool:
    return all(str(i["listing"]) in grades for i in _items(case))


class RelevanceReviewing:
    def __init__(self, store: ReviewStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    async def task(
        self, queue: str, labeler: str, position: int | None = None
    ) -> RelevanceTask | None:
        cases = await self._store.cases(queue)
        if not cases:
            return None
        labels = await self._store.labels(queue, labeler)
        complete = {c.position for c in cases if _complete(c, _grades(c, labels))}
        if position is not None:
            case = next((c for c in cases if c.position == position), cases[0])
        else:
            case = next((c for c in cases if c.position not in complete), cases[-1])
        return RelevanceTask(
            case.position,
            len(cases),
            len(complete),
            case.payload,
            _grades(case, labels),
            len(complete) == len(cases),
        )

    async def record(self, queue: str, position: int, key: str, labeler: str, grade: int) -> bool:
        """``False`` when the villa is not in that query's pool."""
        if grade not in GRADES:
            return False
        case = next((c for c in await self._store.cases(queue) if c.position == position), None)
        if case is None or key not in {str(i["listing"]) for i in _items(case)}:
            return False
        await self._store.save_label(
            queue, position, key, labeler, {"grade": grade}, self._clock.now()
        )
        return True


def ndcg(order: Sequence[str], grades: Mapping[str, int], k: int) -> float | None:
    """nDCG@k with gain 2^g - 1; unjudged items count as 0. ``None``: nothing relevant."""

    def gain(grade: int, rank: int) -> float:
        return float(2**grade - 1) / math.log2(rank + 2)

    ideal = sorted(grades.values(), reverse=True)[:k]
    idcg = sum(gain(g, i) for i, g in enumerate(ideal))
    if idcg == 0:
        return None
    dcg = sum(gain(grades.get(key, 0), i) for i, key in enumerate(order[:k]))
    return dcg / idcg


def recall(order: Sequence[str], grades: Mapping[str, int], k: int) -> float | None:
    """Share of the pool's relevant villas (grade ≥ 1) in the top k. ``None``: none relevant."""
    relevant = {key for key, g in grades.items() if g >= 1}
    if not relevant:
        return None
    return len(relevant & set(order[:k])) / len(relevant)


@dataclass(frozen=True, slots=True)
class SystemScore:
    system: str
    ndcg_at_10: float | None
    recall_at_20: float | None
    queries: int  # queries with at least one relevant villa (the ones that count)


@dataclass(frozen=True, slots=True)
class RelevanceReport:
    queue: str
    total: int
    judged: int  # queries with every pooled villa graded
    judgements: int
    systems: list[SystemScore] = field(default_factory=list)
    window: tuple[date, date] | None = None


class EvaluateRelevance:
    def __init__(self, store: ReviewStore) -> None:
        self._store = store

    async def run(self, queue: str, labeler: str) -> RelevanceReport:
        cases = await self._store.cases(queue)
        labels = await self._store.labels(queue, labeler)
        judged = [(c, g) for c in cases if _complete(c, g := _grades(c, labels))]
        scores = []
        for system in SYSTEMS:
            ndcgs: list[float] = []
            recalls: list[float] = []
            for case, grades in judged:
                orders = case.payload.get("orders")
                order = orders.get(system, []) if isinstance(orders, dict) else []
                n = ndcg([str(k) for k in order], grades, 10)
                r = recall([str(k) for k in order], grades, 20)
                if n is not None:
                    ndcgs.append(n)
                if r is not None:
                    recalls.append(r)
            scores.append(
                SystemScore(
                    system,
                    sum(ndcgs) / len(ndcgs) if ndcgs else None,
                    sum(recalls) / len(recalls) if recalls else None,
                    len(ndcgs),
                )
            )
        return RelevanceReport(
            queue,
            len(cases),
            len(judged),
            sum(len(g) for _, g in judged),
            scores,
        )
