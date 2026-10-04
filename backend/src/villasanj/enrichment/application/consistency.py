"""Cross-platform claim checks of canonical villas, and H4 with both kinds (ROADMAP M9).

``CheckVillaConsistency`` compares what the listings of one villa state (``domain.consistency``).
``MeasureH4`` counts, per platform, the listings with at least one location or amenity claim that
is CONTRADICTED by the map or INCONSISTENT_ACROSS_PLATFORMS, over the listings with at least one
claim either check could judge, with a Wilson 95% interval (criterion 4).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import Listing, ListingId
from villasanj.enrichment.application.claim_extraction import ReadClaimStore, as_read
from villasanj.enrichment.application.coast import CoastDistanceStore
from villasanj.enrichment.application.features import AmenityMap
from villasanj.enrichment.application.places import PlaceDistanceStore
from villasanj.enrichment.application.truth import place_verdicts
from villasanj.enrichment.domain.consistency import (
    MIN_PLATFORMS,
    MemberClaims,
    VillaConsistency,
    compare,
    feature_statements,
)
from villasanj.enrichment.domain.distance_claims import Verdict, parse_claim
from villasanj.enrichment.domain.features import extract_claims, with_read_claims
from villasanj.entity_resolution.domain.evaluation import Interval, wilson
from villasanj.shared.application.artifacts import envelope


class Villas(Protocol):
    async def current(self) -> dict[str, frozenset[ListingId]]:
        """Villa id -> its member listings."""
        ...


class CheckVillaConsistency:
    def __init__(self, amenities: AmenityMap, read_claims: ReadClaimStore | None = None) -> None:
        self._amenities = amenities
        self._read_claims = read_claims

    async def run(self, members: Sequence[Listing]) -> VillaConsistency:
        return compare([await self.claims_of(m) for m in members])

    async def claims_of(self, listing: Listing) -> MemberClaims:
        description = listing.description_norm or ""
        read = await self._read_claims.get(listing.id) if self._read_claims else []
        said = with_read_claims(extract_claims(description), as_read(read), description)
        distances = [c for raw in listing.distance_claims if (c := parse_claim(raw)) is not None]
        return MemberClaims(
            listing.id.platform,
            feature_statements(self._amenities.features_of(listing), said),
            tuple(distances),
        )


@dataclass(slots=True)
class H4Row:
    platform: str
    listings: int = 0
    in_multi_platform_villas: int = 0
    judged: int = 0  # at least one claim checked by the map or against another platform
    contradicted: int = 0  # at least one distance claim the map contradicts
    compared: int = 0  # at least one claim another platform of the villa also makes
    inconsistent: int = 0  # at least one such claim stated differently
    either: int = 0  # contradicted or inconsistent
    kinds: Counter[str] = field(default_factory=Counter)  # "feature:pool", "distance:sea", ...

    @property
    def share(self) -> Interval:
        return wilson(self.either, self.judged)

    @property
    def inconsistent_share(self) -> Interval:
        return wilson(self.inconsistent, self.compared)


class MeasureH4:
    def __init__(
        self,
        listings: ListingReader,
        villas: Villas,
        check: CheckVillaConsistency,
        coast: CoastDistanceStore,
        places: PlaceDistanceStore,
    ) -> None:
        self._listings = listings
        self._villas = villas
        self._check = check
        self._coast = coast
        self._places = places

    async def run(self, platforms: Sequence[str]) -> list[H4Row]:
        by_id: dict[ListingId, Listing] = {}
        rows = {p: H4Row(p) for p in platforms}
        contradicted: set[ListingId] = set()
        judged: set[ListingId] = set()
        for platform in platforms:
            coast = await self._coast.of_platform(platform)
            places = await self._places.of_platform(platform)
            for listing in await self._listings.listings(platform):
                by_id[listing.id] = listing
                rows[platform].listings += 1
                checks = place_verdicts(
                    listing.distance_claims, coast.get(listing.id), places.get(listing.id, {})
                )
                verdicts = [c.assessment.verdict for c in checks if c.assessment is not None]
                if verdicts:
                    judged.add(listing.id)
                if Verdict.CONTRADICTED in verdicts:
                    contradicted.add(listing.id)
        compared: set[ListingId] = set()
        inconsistent: set[ListingId] = set()
        for members in (await self._villas.current()).values():
            listed = [by_id[m] for m in sorted(members) if m in by_id]
            if len(listed) < MIN_PLATFORMS:
                continue
            for listing in listed:
                rows[listing.id.platform].in_multi_platform_villas += 1
            found = await self._check.run(listed)
            for listing in listed:
                platform = listing.id.platform
                if platform in found.compared:
                    compared.add(listing.id)
                if platform in found.inconsistent_platforms():
                    inconsistent.add(listing.id)
                for f in found.features:
                    if platform in f.by_platform:
                        rows[platform].kinds[f"feature:{f.feature.value}"] += 1
                for d in found.distances:
                    if platform in d.by_platform:
                        rows[platform].kinds[f"distance:{d.target.value}"] += 1
        for listing_id in by_id:
            row = rows[listing_id.platform]
            row.contradicted += listing_id in contradicted
            row.compared += listing_id in compared
            row.inconsistent += listing_id in inconsistent
            row.judged += listing_id in judged or listing_id in compared
            row.either += listing_id in contradicted or listing_id in inconsistent
        return [rows[p] for p in platforms]


def _share(interval: Interval) -> str:
    if interval.estimate is None:
        return "n/a"
    return f"{interval.estimate:.1%} ({interval.low:.1%}–{interval.high:.1%})"


def render_h4_markdown(rows: Sequence[H4Row], generated_at: datetime) -> str:
    """H4 as a report (M9 criterion 4), generated from the database like the other reports."""
    lines = [
        "# H4: listings with a location or amenity claim the evidence does not back",
        "",
        f"Generated {generated_at:%Y-%m-%d %H:%M} UTC from the database. Reproduce: "
        "`uv run villasanj enrichment h4 --out <file>`.",
        "",
        "A listing counts when at least one of its claims is CONTRADICTED by the map (a distance "
        "no reading can reach, even at the nearest point its blur circle allows) or "
        "INCONSISTENT_ACROSS_PLATFORMS (its villa's listing on the other platform states the "
        "opposite, each uncontested on its own platform). The share is over listings with at "
        "least one claim either check could judge, with a Wilson 95% interval. The research "
        "report's H4 expected at least 25%.",
        "",
        "| Platform | Listings | Judged | Contradicted | Inconsistent | Either | H4 share |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.platform} | {r.listings} | {r.judged} | {r.contradicted} | {r.inconsistent} | "
            f"{r.either} | {_share(r.share)} |"
        )
    lines += [
        "",
        "Cross-platform comparisons (listings in a villa on both platforms that state a claim "
        "the other listing also states):",
        "",
        "| Platform | In two-platform villas | Compared | Inconsistent | Share | By claim |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        kinds = ", ".join(f"{k} {n}" for k, n in r.kinds.most_common()) or "-"
        lines.append(
            f"| {r.platform} | {r.in_multi_platform_villas} | {r.compared} | {r.inconsistent} | "
            f"{_share(r.inconsistent_share)} | {kinds} |"
        )
    return "\n".join(lines) + "\n"


def h4_artifact(rows: Sequence[H4Row], generated_at: datetime, command: str) -> dict[str, object]:
    """H4 as data (reports/h4-*.json) for the documentation portal."""
    return envelope(
        "h4",
        command,
        generated_at,
        {"villas": "er.villa (the production clustering)", "evidence": "OSM map, listing text"},
        {
            "platforms": [
                {
                    "platform": r.platform,
                    "listings": r.listings,
                    "in_multi_platform_villas": r.in_multi_platform_villas,
                    "judged": r.judged,
                    "contradicted": r.contradicted,
                    "compared": r.compared,
                    "inconsistent": r.inconsistent,
                    "either": r.either,
                    "share": r.share.as_dict(),
                    "inconsistent_share": r.inconsistent_share.as_dict(),
                    "kinds": dict(r.kinds.most_common()),
                }
                for r in rows
            ]
        },
    )
