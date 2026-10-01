"""Description claims against each listing's own amenity list (M9 groundwork, zero network).

The report says how often descriptions claim a feature, how often the same listing's structured
amenities agree, and how often they say the opposite. Cross-platform evidence (H4) needs canonical
villas (M5); photo tags and coastline distances come with M9.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import Listing
from villasanj.enrichment.domain.features import (
    Agreement,
    DescriptionClaim,
    Feature,
    against_amenities,
    extract_claims,
)

SAMPLES = 5


@dataclass(frozen=True, slots=True)
class AmenityMap:
    """Per platform: amenity code -> the feature it states (config/features.toml)."""

    codes: Mapping[str, Mapping[str, Feature]]

    def features_of(self, listing: Listing) -> dict[Feature, bool]:
        """What the listing's own amenity list says; "yes" wins if two codes disagree."""
        codes = self.codes.get(listing.id.platform, {})
        stated: dict[Feature, bool] = {}
        for amenity in listing.amenities:
            feature = codes.get(amenity.code)
            if feature is not None:
                stated[feature] = stated.get(feature, False) or amenity.present
        return stated


@dataclass(frozen=True, slots=True)
class Disagreement:
    listing: str
    claim: DescriptionClaim
    context: str  # the words around the span, for a human to check


@dataclass(slots=True)
class FeatureRow:
    feature: Feature
    amenity_yes: int = 0  # listings whose amenity list says it has the feature
    amenity_no: int = 0  # listings whose amenity list says it does not
    claims: Counter[str] = field(default_factory=Counter)  # "has", "has_not", "shared"
    agreement: Counter[str] = field(default_factory=Counter)
    disagreements: list[Disagreement] = field(default_factory=list)  # first few, for review


@dataclass(frozen=True, slots=True)
class FeatureClaimReport:
    platform: str
    listings: int
    with_description: int
    rows: list[FeatureRow]


class MeasureFeatureClaims:
    def __init__(self, listings: ListingReader, amenities: AmenityMap) -> None:
        self._listings = listings
        self._amenities = amenities

    async def run(self, platform: str) -> FeatureClaimReport:
        listings = await self._listings.listings(platform)
        rows = {f: FeatureRow(f) for f in Feature}
        described = 0
        for listing in listings:
            stated = self._amenities.features_of(listing)
            for feature, value in stated.items():
                rows[feature].amenity_yes += value
                rows[feature].amenity_no += not value
            text = listing.description_norm
            if not text:
                continue
            described += 1
            for claim in extract_claims(text):
                row = rows[claim.feature]
                row.claims["shared" if claim.shared else claim.polarity.value] += 1
                agreement = against_amenities(claim, stated)
                row.agreement[agreement.value] += 1
                if agreement is Agreement.AMENITIES_DISAGREE and len(row.disagreements) < SAMPLES:
                    window = text[max(0, claim.start - 40) : claim.end + 40]
                    row.disagreements.append(Disagreement(str(listing.id), claim, window))
        return FeatureClaimReport(platform, len(listings), described, list(rows.values()))
