"""The owner's M8 reviews: the query set and blind relevance judgements, and their metrics."""

from collections.abc import Mapping, Sequence
from datetime import datetime

import pytest

from tests.fakes.llm import FixedClock
from tests.unit.discovery.test_search import CTX, search
from villasanj.discovery.application.intent import DateSpec, SearchIntent
from villasanj.discovery.application.reviews import (
    BuildQueryReviewQueue,
    BuildRelevanceQueue,
    DraftCase,
    EvaluateRelevance,
    ExportReviewedQueries,
    InvalidIntent,
    QueryReviewing,
    QueryVerdict,
    RelevanceReviewing,
    ReviewCase,
    ReviewQueueExists,
    ndcg,
    recall,
)
from villasanj.discovery.application.search import SearchResult


class Store:
    def __init__(self) -> None:
        self.queues: dict[str, list[ReviewCase]] = {}
        self.values: dict[tuple[str, int, str, str], dict[str, object]] = {}

    async def cases(self, queue: str) -> list[ReviewCase]:
        return list(self.queues.get(queue, []))

    async def save_cases(
        self, queue: str, kind: str, cases: Sequence[ReviewCase], at: datetime
    ) -> None:
        self.queues[queue] = list(cases)

    async def labels(self, queue: str, labeler: str) -> dict[tuple[int, str], dict[str, object]]:
        return {
            (p, i): v for (q, p, i, who), v in self.values.items() if (q, who) == (queue, labeler)
        }

    async def save_label(
        self,
        queue: str,
        position: int,
        item: str,
        labeler: str,
        value: Mapping[str, object],
        at: datetime,
    ) -> None:
        self.values[(queue, position, item, labeler)] = dict(value)


DRAFTS = [
    DraftCase("ویلا برای ۴ نفر آخر هفته", {"dates": {"kind": "weekend"}, "guest_parts": [4]}, "a"),
    DraftCase("ویلا در رامسر", {"places": ["رامسر"]}, "b"),
    DraftCase("سلام", {}, "c"),
]


async def test_the_query_set_is_reviewed_case_by_case_and_exported() -> None:
    store, clock = Store(), FixedClock()
    assert await BuildQueryReviewQueue(store, clock).run("q", DRAFTS) == 3
    with pytest.raises(ReviewQueueExists):
        await BuildQueryReviewQueue(store, clock).run("q", DRAFTS)
    reviewing = QueryReviewing(store, clock)
    first = await reviewing.task("q", "owner")
    assert first is not None
    assert (first.position, first.reviewed, first.query) == (1, 0, DRAFTS[0].query)
    assert await reviewing.record("q", 1, "owner", QueryVerdict(True, None, None))
    # A correction is validated and stored as the schema reads it (defaults dropped).
    fixed: dict[str, object] = {"places": ["رامسر"], "dates": {"kind": "weekend", "which": "this"}}
    assert await reviewing.record("q", 2, "owner", QueryVerdict(False, fixed, "dates were said"))
    with pytest.raises(InvalidIntent):
        await reviewing.record("q", 3, "owner", QueryVerdict(False, {"rooms": 3}, None))
    assert not await reviewing.record("q", 9, "owner", QueryVerdict(True, None, None))
    second = await reviewing.task("q", "owner")
    assert second is not None
    assert second.position == 3  # the first one not reviewed
    exported = await ExportReviewedQueries(store).run("q", "owner")
    assert (exported.accepted, exported.corrected, exported.rejected, exported.unreviewed) == (
        1,
        1,
        0,
        1,
    )
    assert exported.cases[1].expected == {"dates": {"kind": "weekend"}, "places": ["رامسر"]}
    await reviewing.record("q", 3, "owner", QueryVerdict(False, None, "not a search"))
    done = await ExportReviewedQueries(store).run("q", "owner")
    assert (len(done.cases), done.rejected, done.unreviewed) == (2, 1, 0)


IN_RAMSAR = SearchIntent(dates=DateSpec(kind="weekend"), guest_parts=[4], places=["رامسر"])


class Searches:
    """One fake search per query (each scripted with its own intent)."""

    def __init__(self, intents: Mapping[str, SearchIntent]) -> None:
        self._intents = intents

    async def run(self, query: str, ctx: object, drop: Sequence[str] = ()) -> SearchResult:
        return await search(self._intents[query]).run(query, CTX)


async def test_relevance_pools_three_systems_blind_and_skips_what_cannot_rank() -> None:
    store, clock = Store(), FixedClock()
    searches = Searches({"ویلا برای ۴ نفر در رامسر آخر هفته": IN_RAMSAR, "ویلا": SearchIntent()})
    built = await BuildRelevanceQueue(searches, store, clock).run(  # type: ignore[arg-type]
        "r", ["ویلا برای ۴ نفر در رامسر آخر هفته", "ویلا"], CTX
    )
    assert built.queued == 1
    assert list(built.skipped) == ["ویلا"]
    (case,) = store.queues["r"]
    orders = case.payload["orders"]
    assert isinstance(orders, dict)
    assert set(orders) == {"ranking", "price", "rating"}
    items = case.payload["items"]
    assert isinstance(items, list)
    keys = [i["listing"] for i in items]
    assert sorted(keys) == sorted(orders["ranking"])  # three results: all pooled
    assert {"title", "place", "per_person_night_toman", "features"} <= set(items[0])
    with pytest.raises(ReviewQueueExists):
        await BuildRelevanceQueue(searches, store, clock).run("r", ["ویلا"], CTX)  # type: ignore[arg-type]


async def test_relevance_grades_complete_a_query_and_score_each_system() -> None:
    store, clock = Store(), FixedClock()
    store.queues["r"] = [
        ReviewCase(
            1,
            {
                "query": "q",
                "orders": {"ranking": ["a", "b", "c"], "price": ["c", "b", "a"], "rating": ["b"]},
                "items": [{"listing": k} for k in ("b", "a", "c")],
            },
        )
    ]
    reviewing = RelevanceReviewing(store, clock)
    assert not await reviewing.record("r", 1, "x", "owner", 2)  # not in the pool
    assert not await reviewing.record("r", 1, "a", "owner", 3)  # not a grade
    for key, grade in (("a", 2), ("b", 1)):
        assert await reviewing.record("r", 1, key, "owner", grade)
    task = await reviewing.task("r", "owner")
    assert task is not None
    assert (task.queries_done, task.done) == (0, False)
    await reviewing.record("r", 1, "c", "owner", 0)
    task = await reviewing.task("r", "owner")
    assert task is not None
    assert (task.queries_done, task.done, task.grades["a"]) == (1, True, 2)
    report = await EvaluateRelevance(store).run("r", "owner")
    scores = {s.system: s for s in report.systems}
    assert (report.judged, report.judgements) == (1, 3)
    assert scores["ranking"].ndcg_at_10 == pytest.approx(1.0)  # the ideal order
    price = scores["price"].ndcg_at_10
    assert price is not None
    assert price < 1.0
    assert scores["rating"].recall_at_20 == pytest.approx(0.5)  # finds b, misses a


def test_ndcg_and_recall_by_hand() -> None:
    grades = {"a": 2, "b": 0, "c": 1}
    # DCG = 3/log2(2) + 0 + 1/log2(4) = 3.5; ideal = 3 + 1/log2(3)
    assert ndcg(["a", "b", "c"], grades, 10) == pytest.approx(3.5 / (3 + 1 / 1.584962500721156))
    assert ndcg(["x"], {"x": 0}, 10) is None  # nothing relevant: the query does not count
    assert recall(["a", "b"], grades, 20) == pytest.approx(0.5)
    assert recall(["b", "c", "a"], grades, 1) == 0.0
