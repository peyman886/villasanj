"""Review summaries: cited points, code-labelled single opinions, retry once, then drop."""

import hashlib
from dataclasses import replace
from decimal import Decimal
from typing import Any

from tests.fakes.llm import NOW
from villasanj.catalog.domain.listing import ListingId
from villasanj.catalog.domain.review import ListingReview
from villasanj.enrichment.application import review_summary
from villasanj.enrichment.application.review_summary import (
    MAX_REVIEWS,
    PointOut,
    SummarizeReviews,
    SummaryOut,
)
from villasanj.shared.application.llm.types import (
    JobContext,
    LLMRequest,
    LLMResponse,
    LLMTask,
    Role,
    TokenUsage,
)
from villasanj.shared.domain.provenance import Provenance, ProvenanceMethod, SourceRef

# A prompt change needs a new version, so answers cached for the old prompt are not reused.
PINNED = {"1": "6456b8b470b12b3b75ae47efc348f58305c30af244e366cc111a51c191e8054d"}
CTX = JobContext("job", Decimal(1))
ZWNJ = "\N{ZERO WIDTH NON-JOINER}"
LISTING = ListingId("p", "1")


def review(n: int, text: str | None = "تمیز بود") -> ListingReview:
    return ListingReview(
        listing_id=LISTING,
        review_id=f"rev-{n}",
        rating=5.0,
        text=text,
        text_norm=text,
        stayed_on=None,
        stayed_precision=None,
        host_replied=False,
        provenance=Provenance(
            ProvenanceMethod.OBSERVED,
            NOW,
            SourceRef("p", "https://example.test/1"),
            "00000000-0000-0000-0000-000000000001",
        ),
    )


REVIEWS = [
    review(1, "خیلی تمیز بود"),
    review(2, "تمیز و مرتب"),
    review(3, None),
    review(4, "سرد بود"),
]


class Reviews:
    async def reviews(self, listing_id: ListingId) -> list[ListingReview]:
        return REVIEWS if listing_id == LISTING else REVIEWS[:2]


class ScriptedClient:
    def __init__(self, *answers: SummaryOut) -> None:
        self.answers = list(answers)
        self.requests: list[LLMRequest[Any]] = []

    async def generate(
        self, request: LLMRequest[Any], ctx: JobContext, *, model: str | None = None
    ) -> LLMResponse[Any]:
        self.requests.append(request)
        usage = TokenUsage(input_tokens=1200, output_tokens=300)
        return LLMResponse(self.answers.pop(0), "model-a", usage, Decimal("0.003"), False, 1, 9)


def test_prompt_changes_require_a_version_bump() -> None:
    text = review_summary.SYSTEM_PROMPT + review_summary.RETRY_TEMPLATE
    digest = hashlib.sha256(text.encode()).hexdigest()
    assert PINNED.get(review_summary.SUMMARY_PROMPT_VERSION) == digest, (
        "the summary prompt changed: bump SUMMARY_PROMPT_VERSION and pin the new hash"
    )


GOOD = SummaryOut(
    pros=[PointOut(text=f"مهمان{ZWNJ}ها از تمیزی راضی بودند", reviews=["R1", "R2", "R2"])],
    cons=[PointOut(text="یک مهمان خانه را سرد دید", reviews=["R3"])],
)


async def test_points_cite_real_reviews_and_single_opinions_are_labelled_by_code() -> None:
    client = ScriptedClient(GOOD)
    summary = await SummarizeReviews(client, Reviews()).for_listing(LISTING, CTX)
    assert summary is not None
    (pro,) = summary.pros
    assert [r.review_id for r in pro.reviews] == ["rev-1", "rev-2"]  # duplicates cited once
    assert not pro.single_opinion
    (con,) = summary.cons
    assert [r.review_id for r in con.reviews] == ["rev-4"]  # R3 is the third review with text
    assert con.single_opinion
    assert (summary.reviews_given, summary.retried, summary.dropped) == (3, False, 0)
    (request,) = client.requests
    assert request.task is LLMTask.REVIEW_SUMMARY
    assert "R3 (rating 5 of 5): سرد بود" in request.messages[-1].text


async def test_broken_points_are_retried_once_then_dropped() -> None:
    broken = SummaryOut(
        pros=[
            PointOut(text="از ۵ ستاره تمیزی گرفت", reviews=["R1"]),  # a digit
            PointOut(
                text=f"مهمان{ZWNJ}ها از تمیزی راضی بودند", reviews=["R1", "R9"]
            ),  # unknown review
        ],
        cons=[PointOut(text=f"از بقیه ارزان{ZWNJ}تر بود", reviews=["R2", "R3"])],
    )
    client = ScriptedClient(broken, broken)
    summary = await SummarizeReviews(client, Reviews()).for_listing(LISTING, CTX)
    assert summary is not None
    assert (summary.pros, summary.cons) == ((), ())
    assert (summary.retried, summary.dropped, summary.cost_usd) == (True, 3, Decimal("0.006"))
    retry = client.requests[1]
    assert [m.role for m in retry.messages] == [Role.SYSTEM, Role.USER, Role.ASSISTANT, Role.USER]
    feedback = retry.messages[-1].text
    assert "pros[0]: digit_outside_slot" in feedback
    assert "pros[1]: unknown_review" in feedback
    assert "cons[0]: comparative_outside_slot" in feedback


async def test_a_retry_that_fixes_the_points_keeps_them() -> None:
    broken = SummaryOut(pros=[PointOut(text="از ۵ ستاره", reviews=["R1"])])
    client = ScriptedClient(broken, GOOD)
    summary = await SummarizeReviews(client, Reviews()).for_listing(LISTING, CTX)
    assert summary is not None
    assert (len(summary.pros), summary.retried, summary.dropped) == (1, True, 0)


async def test_too_few_reviews_with_text_get_no_summary_and_no_call() -> None:
    client = ScriptedClient()
    use_case = SummarizeReviews(client, Reviews())
    assert await use_case.for_listing(ListingId("p", "2"), CTX) is None
    assert client.requests == []
    assert len(await use_case.requests([LISTING, ListingId("p", "2")])) == 1


async def test_only_the_most_recent_reviews_go_in() -> None:
    many = [replace(review(n), review_id=f"rev-{n}") for n in range(MAX_REVIEWS + 5)]
    client = ScriptedClient(SummaryOut())
    summary = await SummarizeReviews(client, Reviews()).summarize(many, CTX)
    assert summary is not None
    assert summary.reviews_given == MAX_REVIEWS
    assert f"R{MAX_REVIEWS}:" in client.requests[0].messages[-1].text.replace(
        " (rating 5 of 5)", ""
    )
