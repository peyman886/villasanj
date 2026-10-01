"""An offer: one listing's quote for a stay and group, with the age of its evidence (M6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from villasanj.pricing.domain.quote import OfferKind, Quote

DEFAULT_MAX_AGE = timedelta(hours=24)


@dataclass(frozen=True, slots=True)
class Offer:
    """Prices are never merged across listings: each listing of a villa has its own offer."""

    quote: Quote
    as_of: datetime
    max_age: timedelta = DEFAULT_MAX_AGE

    @property
    def age(self) -> timedelta:
        """Age of the oldest observation the quote rests on (product rule 6)."""
        return self.as_of - self.quote.provenance.oldest_observation

    @property
    def stale(self) -> bool:
        return self.age > self.max_age

    @property
    def kind(self) -> OfferKind | None:
        return self.quote.kind
