"""Claims the listings of one villa make differently (ROADMAP M9: INCONSISTENT_ACROSS_PLATFORMS).

Only what the platforms themselves say is compared: a listing's amenity list and its own
description, never the map or the photos (those are evidence, not statements). The rule is the
truth check's: an inconsistency is reported only when no reading can reconcile the statements.

- A feature is inconsistent when one listing says it has it and another says it does not, each
  uncontested on its own platform (a listing whose amenity list and description disagree says
  nothing either way, and a shared facility says nothing about the villa).
- A distance to one target is inconsistent when the straight-line distances one listing's claims
  allow (every reading, generous speeds, rounding margins) and the other's do not overlap.

An inconsistency says the listings disagree, not which one is wrong.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from villasanj.enrichment.domain.distance_claims import ClaimTarget, DistanceClaim
from villasanj.enrichment.domain.features import (
    DescriptionClaim,
    Feature,
    FeatureEvidence,
    Polarity,
    feature_evidence,
)

MIN_PLATFORMS = 2  # a comparison needs two listings that state the same thing
_SAYS_YES = frozenset({FeatureEvidence.LISTED, FeatureEvidence.DESCRIBED, FeatureEvidence.PHOTO})


@dataclass(frozen=True, slots=True)
class FeatureStatement:
    says: bool
    from_amenities: bool  # the amenity list says so (else only the description)
    span: str | None  # the description's words, when it says so
    by_llm: bool = False  # the span was read by the LLM (rules found nothing about the feature)


@dataclass(frozen=True, slots=True)
class MemberClaims:
    """What one listing of the villa states about features and distances."""

    platform: str
    features: Mapping[Feature, FeatureStatement]
    distances: Sequence[DistanceClaim]


def feature_statements(
    amenities: Mapping[Feature, bool], claims: Sequence[DescriptionClaim]
) -> dict[Feature, FeatureStatement]:
    """Each feature the listing states uncontested, with where it says so."""
    statements = {}
    for feature in Feature:
        own = [c for c in claims if c.feature is feature and not c.shared]
        evidence = feature_evidence(amenities.get(feature), own)
        if evidence in _SAYS_YES:
            says = True
        elif evidence is FeatureEvidence.DENIED:
            says = False
        else:
            continue
        listed = amenities.get(feature)
        said = next((c for c in own if (c.polarity is Polarity.HAS) == says), None)
        statements[feature] = FeatureStatement(
            says,
            listed is not None,
            said.span if said else None,
            said.by_llm if said else False,
        )
    return statements


@dataclass(frozen=True, slots=True)
class FeatureInconsistency:
    feature: Feature
    by_platform: dict[str, FeatureStatement]


@dataclass(frozen=True, slots=True)
class DistanceInconsistency:
    target: ClaimTarget
    by_platform: dict[str, tuple[DistanceClaim, ...]]
    metres: dict[str, tuple[float, float | None]]  # every distance the platform's claims allow


@dataclass(frozen=True, slots=True)
class VillaConsistency:
    features: tuple[FeatureInconsistency, ...]
    distances: tuple[DistanceInconsistency, ...]
    compared: frozenset[str]  # platforms with at least one claim another platform also makes

    def inconsistent_platforms(self) -> frozenset[str]:
        features = (p for x in self.features for p in x.by_platform)
        distances = (p for x in self.distances for p in x.by_platform)
        return frozenset((*features, *distances))


def compare(members: Sequence[MemberClaims]) -> VillaConsistency:
    features = []
    compared: set[str] = set()
    for feature in Feature:
        stated = {m.platform: m.features[feature] for m in members if feature in m.features}
        if len(stated) < MIN_PLATFORMS:
            continue
        compared.update(stated)
        if len({s.says for s in stated.values()}) > 1:
            features.append(FeatureInconsistency(feature, stated))
    distances = []
    for target in ClaimTarget:
        if target is ClaimTarget.OTHER:
            continue  # unnamed targets may be different places
        claims = {m.platform: tuple(c for c in m.distances if c.target is target) for m in members}
        claims = {p: cs for p, cs in claims.items() if cs}
        if len(claims) < MIN_PLATFORMS:
            continue
        compared.update(claims)
        ranges = {p: _union([c.metres() for c in cs]) for p, cs in claims.items()}
        if not _overlap(list(ranges.values())):
            distances.append(DistanceInconsistency(target, claims, ranges))
    return VillaConsistency(tuple(features), tuple(distances), frozenset(compared))


def _union(ranges: Sequence[tuple[float, float | None]]) -> tuple[float, float | None]:
    highs = [high for _, high in ranges]
    return min(low for low, _ in ranges), None if None in highs else max(
        h for h in highs if h is not None
    )


def _overlap(ranges: Sequence[tuple[float, float | None]]) -> bool:
    """Whether one distance fits every platform's range."""
    low = max(r[0] for r in ranges)
    highs = [r[1] for r in ranges if r[1] is not None]
    return not highs or low <= min(highs)
