"""Truth check of published "distance to the sea" claims (ROADMAP M9 criterion 3; listing level).

Evidence is the measured straight-line distance from the listing's blur circle to the OSM
coastline (``enrichment.coast_distance``). The verdict rule is ``assess``: CONTRADICTED only when
every reading of the claim fails even in the best case, SUPPORTED only when every reading holds
anywhere in the circle, otherwise «تأیید نشد». Verdicts that rest on an assumed blur radius (a
platform that publishes none) are counted separately so they can be shown with that caveat.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.coast import CoastDistance, CoastDistanceStore
from villasanj.enrichment.domain.distance_claims import (
    Assessment,
    ClaimTarget,
    DistanceClaim,
    Verdict,
    assess,
    parse_claim,
)

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
