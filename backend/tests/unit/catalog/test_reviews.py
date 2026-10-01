"""Reviews in the catalog and the Bayesian rating prior."""

from datetime import date

import pytest

from tests.fakes.catalog import InMemoryListingRepository, store_fixture
from tests.fakes.ingestion import InMemoryBlobStore, InMemorySnapshotRepository
from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from villasanj.catalog.application.ingest import IngestListingSnapshots
from villasanj.catalog.domain.listing import Listing
from villasanj.catalog.domain.review import ListingReview, RatingPrior
from villasanj.ingestion.domain.pages import PageKind, PageRequest
from villasanj.ingestion.domain.parsed import DatePrecision, ParsedReview
from villasanj.ingestion.infrastructure.sources.shab.adapter import SLUG, ShabAdapter
from villasanj.shared.domain.provenance import ProvenanceMethod

SNAPSHOT = "00000000-0000-0000-0000-000000000f01"


def listing(rating: float | None, count: int | None, external_id: str = "1") -> Listing:
    return Listing.from_parsed(
        parsed(external_id=external_id, rating_avg=rating, rating_count=count), SNAPSHOT, NOW
    )


def test_prior_is_the_vote_weighted_platform_mean() -> None:
    prior = RatingPrior.from_listings(
        [listing(5.0, 1, "1"), listing(4.0, 3, "2"), listing(None, None, "3"), listing(3.0, 0, "4")]
    )
    assert prior is not None
    assert prior.mean == pytest.approx((5 + 12) / 4)
    assert RatingPrior.from_listings([listing(None, None)]) is None


def test_shrinkage_pulls_small_samples_to_the_mean_and_leaves_unrated_unrated() -> None:
    prior = RatingPrior(mean=4.4, weight=5)
    one_vote = prior.shrink(5.0, 1)
    many = prior.shrink(5.0, 200)
    assert one_vote is not None
    assert many is not None
    assert 4.4 < one_vote < many < 5.0
    assert one_vote == pytest.approx((5 * 4.4 + 5.0) / 6)
    assert prior.shrink(None, 3) is None
    assert prior.shrink(4.0, 0) is None


def test_reviews_are_observed_from_the_listing_snapshot_with_normalized_text() -> None:
    review = ParsedReview("R1", 4.0, " خيلي  خوب ", date(2026, 8, 1), DatePrecision.DAY, True)
    stored = ListingReview.from_parsed(listing(4.0, 1), review, SNAPSHOT, NOW)
    assert stored.text_norm == "خیلی خوب"
    assert stored.provenance.method is ProvenanceMethod.OBSERVED
    assert stored.provenance.snapshot_id == SNAPSHOT
    empty = ListingReview.from_parsed(
        listing(4.0, 1), ParsedReview("R2", None, None, None, None, False), SNAPSHOT, NOW
    )
    assert empty.text_norm is None


async def test_ingest_stores_the_reviews_shown_on_listing_pages() -> None:
    snapshots, blobs, repo = (
        InMemorySnapshotRepository(),
        InMemoryBlobStore(),
        InMemoryListingRepository(),
    )
    request = PageRequest(SLUG, PageKind.LISTING, "https://www.shab.ir/houses/show/2085")
    await store_fixture(snapshots, blobs, request, "shab/house_with_reviews.html")
    report = await IngestListingSnapshots({SLUG: ShabAdapter()}, snapshots, blobs, repo).run(SLUG)
    assert report.reviews == 3
    assert sorted(review_id for _, review_id in repo.reviews) == ["RAA1", "RAA2", "RAA3"]
