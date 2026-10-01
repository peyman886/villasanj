"""How much of the published proximity wording the distance-claim parser understands (M9 prep).

Measured over stored listings with zero network requests. Unparsed wordings are listed so a new
phrasing is added to the parser on evidence, never guessed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from villasanj.catalog.application.reading import ListingReader
from villasanj.enrichment.domain.distance_claims import ClaimTarget, parse_claim

TOP = 10


@dataclass(frozen=True, slots=True)
class ClaimParsingReport:
    platform: str
    listings: int
    with_claims: int
    claims: int
    parsed: int
    by_target: dict[str, int]  # parsed claims per target
    by_mode: dict[str, int]  # parsed claims per travel mode
    top_unparsed: list[tuple[str, int]]  # value wordings the parser rejected
    top_other_targets: list[tuple[str, int]]  # parsed, but the target maps to OTHER

    @property
    def coverage(self) -> float:
        return self.parsed / self.claims if self.claims else 0.0


class MeasureClaimParsing:
    def __init__(self, listings: ListingReader) -> None:
        self._listings = listings

    async def run(self, platform: str) -> ClaimParsingReport:
        listings = await self._listings.listings(platform)
        targets: Counter[str] = Counter()
        modes: Counter[str] = Counter()
        unparsed: Counter[str] = Counter()
        other: Counter[str] = Counter()
        claims = parsed = 0
        for listing in listings:
            for raw in listing.distance_claims:
                claims += 1
                claim = parse_claim(raw)
                if claim is None:
                    unparsed[raw.value_text] += 1
                    continue
                parsed += 1
                targets[claim.target.value] += 1
                modes[claim.mode.value] += 1
                if claim.target is ClaimTarget.OTHER:
                    other[raw.target_fa] += 1
        return ClaimParsingReport(
            platform=platform,
            listings=len(listings),
            with_claims=sum(bool(x.distance_claims) for x in listings),
            claims=claims,
            parsed=parsed,
            by_target=dict(targets.most_common()),
            by_mode=dict(modes.most_common()),
            top_unparsed=unparsed.most_common(TOP),
            top_other_targets=other.most_common(TOP),
        )
