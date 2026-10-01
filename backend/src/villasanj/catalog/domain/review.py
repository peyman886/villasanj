"""Guest reviews as published, and a rating that does not over-trust a handful of votes."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

from villasanj.catalog.domain.listing import Listing, ListingId
from villasanj.ingestion.domain.parsed import DatePrecision, ParsedReview
from villasanj.shared.domain.persian_text import normalize_persian
from villasanj.shared.domain.provenance import Provenance, ProvenanceMethod, SourceRef

DEFAULT_PRIOR_WEIGHT = 5.0  # a listing's own votes outweigh the prior after five reviews


@dataclass(frozen=True, slots=True)
class ListingReview:
    listing_id: ListingId
    review_id: str
    rating: float | None
    text: str | None
    text_norm: str | None
    stayed_on: date | None
    stayed_precision: DatePrecision | None
    host_replied: bool
    provenance: Provenance

    @classmethod
    def from_parsed(
        cls, listing: Listing, review: ParsedReview, snapshot_id: str, observed_at: datetime
    ) -> ListingReview:
        return cls(
            listing_id=listing.id,
            review_id=review.review_id,
            rating=review.rating,
            text=review.text,
            text_norm=normalize_persian(review.text) if review.text else None,
            stayed_on=review.stayed_on,
            stayed_precision=review.stayed_precision,
            host_replied=review.host_replied,
            provenance=Provenance(
                ProvenanceMethod.OBSERVED,
                observed_at,
                SourceRef(listing.id.platform, listing.url),
                snapshot_id,
            ),
        )


@dataclass(frozen=True, slots=True)
class RatingPrior:
    """The platform-wide mean rating, used to pull small samples towards it (Bayesian average)."""

    mean: float
    weight: float = DEFAULT_PRIOR_WEIGHT

    @classmethod
    def from_listings(
        cls, listings: Iterable[Listing], weight: float = DEFAULT_PRIOR_WEIGHT
    ) -> RatingPrior | None:
        votes = total = 0.0
        for listing in listings:
            if listing.rating_avg is not None and listing.rating_count:
                votes += listing.rating_count
                total += listing.rating_avg * listing.rating_count
        return cls(total / votes, weight) if votes else None

    def shrink(self, average: float | None, count: int | None) -> float | None:
        """``None`` without published votes: no rating is better than an invented one."""
        if average is None or not count:
            return None
        return (self.weight * self.mean + count * average) / (self.weight + count)
