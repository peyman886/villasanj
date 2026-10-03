"""Truth check of a listing's claims (ROADMAP M9 criteria 3 and 4; listing level).

Distance-to-the-sea claims are judged against the measured straight-line distance from the
listing's blur circle to the OSM coastline (``enrichment.coast_distance``). The verdict rule is
``assess``: CONTRADICTED only when every reading of the claim fails even in the best case,
SUPPORTED only when every reading holds anywhere in the circle, otherwise «تأیید نشد». Verdicts
that rest on an assumed blur radius (a platform that publishes none) are counted separately so
they can be shown with that caveat.

Feature claims in the description are compared with the same listing's amenity list, which is
the host's word too: agreeing is consistency, not proof, and silence is «تأیید نشد». "Near the
sea" words are vague, so the map can support them (A17) but never contradicts them. Photo tags
join as evidence once their thresholds come from labels; other platforms' fields with M5.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import Listing, ListingId
from villasanj.enrichment.application.coast import CoastDistance, CoastDistanceStore
from villasanj.enrichment.application.features import AmenityMap
from villasanj.enrichment.application.photo_tags import PhotoFeatures
from villasanj.enrichment.application.places import PlaceDistance, PlaceDistanceStore
from villasanj.enrichment.domain.distance_claims import (
    Assessment,
    ClaimTarget,
    DistanceClaim,
    Verdict,
    assess,
    parse_claim,
)
from villasanj.enrichment.domain.features import (
    Agreement,
    DescriptionClaim,
    Feature,
    FeatureEvidence,
    against_amenities,
    extract_claims,
    near_sea_evidence,
)
from villasanj.enrichment.domain.places import (
    KIND_OF_TARGET,
    PlaceKind,
    assess_place,
)
from villasanj.entity_resolution.domain.evaluation import Interval, wilson
from villasanj.ingestion.domain.parsed import ParsedDistanceClaim

SAMPLES = 8


@dataclass(frozen=True, slots=True)
class SeaVerdict:
    listing_id: ListingId
    claim: DistanceClaim
    assessment: Assessment
    radius_assumed: bool


@dataclass(slots=True)
class SeaTruthReport:
    platform: str
    listings_with_claim: int = 0
    listings_contradicted: int = 0  # at least one sea claim contradicted (H4, listing level)
    without_distance: int = 0  # a sea claim but no measured coast distance
    verdicts: Counter[str] = field(default_factory=Counter)
    verdicts_with_assumed_radius: Counter[str] = field(default_factory=Counter)
    by_mode: Counter[str] = field(default_factory=Counter)  # "car:contradicted", ...
    contradicted: list[SeaVerdict] = field(default_factory=list)  # first few, to check by hand

    def contradicted_share(self) -> Interval:
        """H4 for sea claims: listings with a contradicted claim among those measured (Wilson)."""
        return wilson(self.listings_contradicted, self.listings_with_claim - self.without_distance)


def sea_verdicts(
    claims: list[DistanceClaim], distance: CoastDistance, listing_id: ListingId
) -> list[SeaVerdict]:
    measured = (distance.low_m, distance.high_m)
    return [
        SeaVerdict(listing_id, claim, assess(claim, measured), distance.blur.assumed)
        for claim in claims
    ]


class CheckSeaClaims:
    def __init__(self, listings: ListingReader, distances: CoastDistanceStore) -> None:
        self._listings = listings
        self._distances = distances

    async def run(self, platform: str) -> SeaTruthReport:
        report = SeaTruthReport(platform)
        distances = await self._distances.of_platform(platform)
        for listing in await self._listings.listings(platform):
            claims = [
                c
                for raw in listing.distance_claims
                if (c := parse_claim(raw)) is not None and c.target is ClaimTarget.SEA
            ]
            if not claims:
                continue
            report.listings_with_claim += 1
            distance = distances.get(listing.id)
            if distance is None:
                report.without_distance += 1
                continue
            verdicts = sea_verdicts(claims, distance, listing.id)
            report.listings_contradicted += any(
                x.assessment.verdict is Verdict.CONTRADICTED for x in verdicts
            )
            for verdict in verdicts:
                value = verdict.assessment.verdict.value
                report.verdicts[value] += 1
                if verdict.radius_assumed:
                    report.verdicts_with_assumed_radius[value] += 1
                report.by_mode[f"{verdict.claim.mode.value}:{value}"] += 1
                if (
                    verdict.assessment.verdict is Verdict.CONTRADICTED
                    and len(report.contradicted) < SAMPLES
                ):
                    report.contradicted.append(verdict)
        return report


@dataclass(frozen=True, slots=True)
class DistanceClaimCheck:
    raw: ParsedDistanceClaim
    claim: DistanceClaim | None  # ``None``: wording not understood (never guessed)
    assessment: Assessment | None  # ``None``: not judged (no evidence for the target yet)
    radius_assumed: bool = False
    place: PlaceDistance | None = None  # the evidence for a target other than the sea


@dataclass(frozen=True, slots=True)
class FeatureClaimCheck:
    claim: DescriptionClaim
    agreement: Agreement  # against the same listing's amenity list
    map_evidence: FeatureEvidence | None = None  # near-sea words only: the coastline's answer
    photo_seen: bool = False  # the listing's own photos show the feature (M9 photo tags)


@dataclass(frozen=True, slots=True)
class ListingTruth:
    listing_id: ListingId
    distances: tuple[DistanceClaimCheck, ...]
    features: tuple[FeatureClaimCheck, ...]
    coast: CoastDistance | None


def place_verdicts(
    claims: Sequence[ParsedDistanceClaim],
    coast: CoastDistance | None,
    places: Mapping[PlaceKind, PlaceDistance],
) -> list[DistanceClaimCheck]:
    """Each published distance claim against its evidence: the coastline for the sea, the
    nearest mapped place of the target's kind otherwise (supporting only, unless complete)."""
    checks = []
    for raw in claims:
        parsed = parse_claim(raw)
        if parsed is None:
            checks.append(DistanceClaimCheck(raw, None, None))
        elif parsed.target is ClaimTarget.SEA and coast is not None:
            assessment = assess(parsed, (coast.low_m, coast.high_m))
            checks.append(DistanceClaimCheck(raw, parsed, assessment, coast.blur.assumed))
        elif (kind := KIND_OF_TARGET.get(parsed.target)) is not None and kind in places:
            place = places[kind]
            assessment = assess_place(parsed, kind, (place.low_m, place.high_m))
            assumed = place.blur.assumed
            checks.append(DistanceClaimCheck(raw, parsed, assessment, assumed, place))
        else:
            checks.append(DistanceClaimCheck(raw, parsed, None))
    return checks


class CheckListingClaims:
    """Every claim of one listing with its evidence; what has no evidence yet says so."""

    def __init__(
        self,
        amenities: AmenityMap,
        distances: CoastDistanceStore,
        places: PlaceDistanceStore | None = None,
        photos: PhotoFeatures | None = None,
    ) -> None:
        self._amenities = amenities
        self._distances = distances
        self._places = places
        self._photos = photos

    async def run(self, listing: Listing) -> ListingTruth:
        coast = await self._distances.get(listing.id)
        places = await self._places.get(listing.id) if self._places else {}
        distances = place_verdicts(listing.distance_claims, coast, places)
        stated = self._amenities.features_of(listing)
        features = []
        seen = await self._photos.seen_for(listing.id) if self._photos else frozenset()
        for said in extract_claims(listing.description_norm or ""):
            on_map = None
            if said.feature is Feature.NEAR_SEA and coast is not None:
                on_map = near_sea_evidence(coast.low_m, coast.high_m)
            agreement = against_amenities(said, stated)
            features.append(FeatureClaimCheck(said, agreement, on_map, said.feature in seen))
        return ListingTruth(listing.id, tuple(distances), tuple(features), coast)


@dataclass(slots=True)
class DistanceTruthReport:
    """Verdicts of every published distance claim of one platform, per target (M9)."""

    platform: str
    verdicts: Counter[str] = field(default_factory=Counter)  # "city_center:supported", ...
    listings_contradicted: int = 0  # at least one distance claim contradicted
    listings_judged: int = 0  # at least one distance claim with evidence


class CheckDistanceClaims:
    def __init__(
        self, listings: ListingReader, coast: CoastDistanceStore, places: PlaceDistanceStore
    ) -> None:
        self._listings = listings
        self._coast = coast
        self._places = places

    async def run(self, platform: str) -> DistanceTruthReport:
        report = DistanceTruthReport(platform)
        coast = await self._coast.of_platform(platform)
        places = await self._places.of_platform(platform)
        for listing in await self._listings.listings(platform):
            checks = place_verdicts(
                listing.distance_claims, coast.get(listing.id), places.get(listing.id, {})
            )
            judged = [c for c in checks if c.assessment is not None and c.claim is not None]
            for check in checks:
                target = check.claim.target.value if check.claim else "not_understood"
                verdict = check.assessment.verdict.value if check.assessment else "not_checked"
                report.verdicts[f"{target}:{verdict}"] += 1
            report.listings_judged += bool(judged)
            report.listings_contradicted += any(
                c.assessment is not None and c.assessment.verdict is Verdict.CONTRADICTED
                for c in judged
            )
        return report
