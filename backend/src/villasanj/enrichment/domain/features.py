"""Villa features, claims about them in descriptions, and a listing's own evidence (M9 groundwork).

One vocabulary is shared by search intents and the truth check, so "a villa with a pool" means the
same thing in a query, a description and a platform's amenity list.

Description claims are found by rules, deterministic first (ADR-0004): every claim is a verbatim
span of the description (it is a slice of it), with its polarity («بدون استخر» says there is no
pool) and whether it names a shared facility («استخر مشاع» is the complex's pool, not the villa's).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from villasanj.shared.domain.persian_text import ZWNJ


class Feature(StrEnum):
    POOL = "pool"
    JACUZZI = "jacuzzi"
    NEAR_SEA = "near_sea"
    SEA_VIEW = "sea_view"
    FOREST = "forest"
    FIREPLACE = "fireplace"
    PARKING = "parking"
    BARBECUE = "barbecue"


_J = f"[ {ZWNJ}]?"  # words are written joined, spaced or with a joiner
_PATTERNS: dict[Feature, str] = {
    Feature.POOL: "استخر",
    Feature.JACUZZI: "جکوزی",
    Feature.SEA_VIEW: f"(?:ویو|ویوی|چشم{_J}انداز|منظره|دید)(?: ابدی| کامل| رو به| به)? دریا",
    Feature.NEAR_SEA: f"(?:ساحل اختصاصی|ساحلی|کنار دریا|لب دریا|ساحل{_J}دار|دسترسی به ساحل)",
    Feature.FOREST: "(?:جنگلی|ویو جنگل|ویوی جنگل|دل جنگل|کنار جنگل|داخل جنگل)",
    Feature.FIREPLACE: "شومینه",
    Feature.PARKING: "پارکینگ",
    Feature.BARBECUE: f"(?:باربیکیو|باربکیو|کباب{_J}پز|منقل)",
}
_MATCHERS = {feature: re.compile(pattern) for feature, pattern in _PATTERNS.items()}
_CLAUSE_END = re.compile(r"[.،,!؟?\n;؛:]")
_NEGATION_BEFORE = re.compile(r"(?:بدون|فاقد|به جز)\s*$")
# "Not available to guests" counts as not having it («فعلا قابل استفاده نیست»).
_NEGATION_AFTER = re.compile(
    rf"^\s*(?:\S+\s+){{0,2}}?(?:ندارد|نداره|نداریم|موجود نیست|وجود ندارد"
    rf"|قابل استفاده نیست|غیر{_J}فعال|فعال نیست|در دسترس نیست)"
)
_SHARED_AFTER = re.compile(r"^\s*(?:\S+\s+){0,3}?(?:مشاع|مشاعات|مشترک|اشتراکی|عمومی|شهرک|مجموعه)")
_NOT_A_CLAIM_BEFORE = re.compile(rf"بی{_J}نیاز از\s*$")  # «بی نیاز از استخر»: no claim
NEARBY_WORDS = re.compile(r"(?:نزدیک|نزدیکی|فاصله|متری|دقیقه|تا)\s*$")


class Polarity(StrEnum):
    HAS = "has"
    HAS_NOT = "has_not"


@dataclass(frozen=True, slots=True)
class DescriptionClaim:
    feature: Feature
    polarity: Polarity
    start: int
    end: int
    span: str  # description[start:end]: verbatim by construction
    shared: bool = False  # a facility of the complex or the town, not of the villa


def extract_claims(description: str) -> list[DescriptionClaim]:
    """Feature claims in a (normalized) description, in order: one per feature and polarity, and
    no "has" beside a "has not" for the same facility of the villa."""
    found: dict[tuple[Feature, Polarity], DescriptionClaim] = {}
    for feature, matcher in _MATCHERS.items():
        for match in matcher.finditer(description):
            start, end = match.span()
            clause_start = _clause_start(description, start)
            clause_end = _clause_end(description, end)
            before = description[clause_start:start]
            after = description[end:clause_end]
            if feature in (Feature.POOL, Feature.JACUZZI) and NEARBY_WORDS.search(before):
                continue  # «نزدیک استخر», «۵ دقیقه تا استخر»: a place nearby, not a feature
            if _NOT_A_CLAIM_BEFORE.search(before):
                continue
            negated = bool(_NEGATION_BEFORE.search(before) or _NEGATION_AFTER.search(after))
            polarity = Polarity.HAS_NOT if negated else Polarity.HAS
            shared = bool(_SHARED_AFTER.search(after))
            key = (feature, polarity)
            if key not in found:
                found[key] = DescriptionClaim(
                    feature, polarity, start, end, description[start:end], shared
                )
    # «استخر اختصاصی … استخر فعلا قابل استفاده نیست»: the explicit "not available" wins.
    for feature in {f for f, polarity in found if polarity is Polarity.HAS_NOT}:
        has = found.get((feature, Polarity.HAS))
        if has is not None and not has.shared:
            del found[(feature, Polarity.HAS)]
    return sorted(found.values(), key=lambda c: (c.start, c.feature))


def _clause_start(text: str, index: int) -> int:
    ends = [m.end() for m in _CLAUSE_END.finditer(text, 0, index)]
    return ends[-1] if ends else 0


def _clause_end(text: str, index: int) -> int:
    match = _CLAUSE_END.search(text, index)
    return match.start() if match else len(text)


class Agreement(StrEnum):
    AGREES = "agrees"  # the listing's own amenity list says the same
    AMENITIES_DISAGREE = "amenities_disagree"  # the same listing's amenity list says the opposite
    AMENITIES_SILENT = "amenities_silent"  # the amenity list says nothing about the feature


def against_amenities(claim: DescriptionClaim, amenities: Mapping[Feature, bool]) -> Agreement:
    """Compare a description claim with the listing's own structured amenities.

    A shared facility claim («استخر مشاع») is not compared: the amenity list may describe the
    villa alone, so neither answer would contradict it.
    """
    stated = amenities.get(claim.feature)
    if stated is None or claim.shared:
        return Agreement.AMENITIES_SILENT
    claims_has = claim.polarity is Polarity.HAS
    return Agreement.AGREES if stated == claims_has else Agreement.AMENITIES_DISAGREE


class FeatureEvidence(StrEnum):
    LISTED = "listed"  # the platform's amenity list says yes
    DESCRIBED = "described"  # only the description says so
    DENIED = "denied"  # the amenity list or the description says no
    UNKNOWN = "unknown"  # nothing said, or the two sources contradict each other


def feature_evidence(amenity: bool | None, claims: Sequence[DescriptionClaim]) -> FeatureEvidence:
    """One feature's evidence from the listing's amenity list and its own description claims.

    Shared facilities say nothing about the villa. When the amenity list and the description
    contradict each other, the evidence is unknown: only an uncontested statement can exclude.
    """
    own = {c.polarity for c in claims if not c.shared}
    if amenity is True:
        return FeatureEvidence.UNKNOWN if Polarity.HAS_NOT in own else FeatureEvidence.LISTED
    if amenity is False:
        return FeatureEvidence.UNKNOWN if Polarity.HAS in own else FeatureEvidence.DENIED
    if Polarity.HAS_NOT in own:
        return FeatureEvidence.DENIED
    if Polarity.HAS in own:
        return FeatureEvidence.DESCRIBED
    return FeatureEvidence.UNKNOWN
