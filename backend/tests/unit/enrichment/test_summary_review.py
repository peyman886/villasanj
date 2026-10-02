"""The owner's blind review of review summaries: drawn once, judged, counted against 18/20."""

from collections.abc import Sequence
from datetime import date, datetime

import pytest

from tests.fakes.er import ListingsFake
from tests.fakes.llm import NOW, FixedClock
from tests.unit.catalog.test_reports import listing
from villasanj.catalog.domain.listing import ListingId
from villasanj.catalog.domain.review import ListingReview
from villasanj.enrichment.application.summary_review import (
    BuildSummaryReviewQueue,
    EvaluateSummaryReviews,
    ReviewItem,
    SummaryQueueExists,
    SummaryReviewing,
    Verdict,
    draw,
)
from villasanj.ingestion.domain.parsed import DatePrecision, ParsedReview


class Store:
    def __init__(self) -> None:
        self.queues: dict[str, list[ReviewItem]] = {}
        self.saved: dict[tuple[str, ListingId, str], Verdict] = {}

    async def items(self, queue: str) -> list[ReviewItem]:
        return self.queues.get(queue, [])

    async def save(self, queue: str, items: Sequence[ReviewItem], at: datetime) -> None:
        self.queues[queue] = list(items)

    async def verdicts(self, queue: str, labeler: str) -> dict[ListingId, Verdict]:
        return {k[1]: v for k, v in self.saved.items() if k[0] == queue and k[2] == labeler}

    async def save_verdict(
        self, queue: str, listing_id: ListingId, labeler: str, verdict: Verdict, at: datetime
    ) -> None:
        self.saved[(queue, listing_id, labeler)] = verdict


class Reviews:
    def __init__(self, with_text: dict[str, int]) -> None:
        self.with_text = with_text

    async def reviews(self, listing_id: ListingId) -> list[ListingReview]:
        owner = listing(listing_id.external_id)
        return [
            ListingReview.from_parsed(
                owner,
                ParsedReview(f"R{i}", 5.0, "خوب بود", date(2026, 9, 1), DatePrecision.DAY, False),
                "00000000-0000-0000-0000-000000000d01",
                NOW,
            )
            for i in range(self.with_text.get(listing_id.external_id, 0))
        ]


def test_the_draw_is_deterministic_and_depends_on_the_name() -> None:
    ids = [ListingId("p", str(i)) for i in range(30)]
    assert draw("summaries-v1", ids, 5) == draw("summaries-v1", list(reversed(ids)), 5)
    assert draw("summaries-v1", ids, 5) != draw("summaries-v2", ids, 5)


async def test_only_listings_with_enough_reviews_are_drawn_once() -> None:
    listings = ListingsFake([listing("many"), listing("few"), listing("also-many")])
    store = Store()
    build = BuildSummaryReviewQueue(
        listings, Reviews({"many": 6, "few": 2, "also-many": 5}), store, FixedClock(), ["p"]
    )
    items = await build.run("summaries-v1", 20)
    assert {i.listing_id.external_id for i in items} == {"many", "also-many"}
    assert [i.position for i in items] == [1, 2]
    with pytest.raises(SummaryQueueExists):
        await build.run("summaries-v1", 20)


async def test_verdicts_advance_the_queue_and_count_against_the_target() -> None:
    store = Store()
    store.queues["q"] = [ReviewItem(i, ListingId("p", str(i))) for i in range(1, 21)]
    reviewing = SummaryReviewing(store, FixedClock())
    first = await reviewing.task("q", "owner")
    assert first is not None
    assert (first.item.position, first.reviewed, first.done) == (1, 0, False)
    for i in range(1, 21):
        assert await reviewing.record("q", ListingId("p", str(i)), "owner", Verdict(i > 2, None))
    assert not await reviewing.record(
        "q", ListingId("p", "elsewhere"), "owner", Verdict(True, None)
    )
    done = await reviewing.task("q", "owner")
    assert done is not None
    assert (done.reviewed, done.done) == (20, True)
    result = await EvaluateSummaryReviews(store).run("q", "owner")
    assert (result.reviewed, result.faithful, result.meets_target) == (20, 18, True)
    assert await reviewing.task("missing", "owner") is None


async def test_the_target_is_unknown_until_every_summary_is_reviewed() -> None:
    store = Store()
    store.queues["q"] = [ReviewItem(i, ListingId("p", str(i))) for i in range(1, 21)]
    await SummaryReviewing(store, FixedClock()).record(
        "q", ListingId("p", "1"), "owner", Verdict(False, "یک نکته در نظرها نیست")
    )
    result = await EvaluateSummaryReviews(store).run("q", "owner")
    assert result.meets_target is None
    assert result.unfaithful == [(ListingId("p", "1"), "یک نکته در نظرها نیست")]
