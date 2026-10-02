"""Scoring rule-based feature claims against a person's reading of the same description (M9
criterion 1: claim-level precision ≥ 90%, recall ≥ 80%; spans are verbatim by construction)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from villasanj.enrichment.domain.features import DescriptionClaim, Feature, Polarity


class Stance(StrEnum):
    HAS = "has"  # the villa has it
    HAS_NOT = "has_not"  # the description says it has not
    SHARED = "shared"  # a facility of the complex or the town, not of the villa
    NONE = "none"  # the description says nothing about it


def stances(claims: Sequence[DescriptionClaim]) -> dict[Feature, Stance]:
    """What the extracted claims say about each feature (the villa's own word wins)."""
    found: dict[Feature, Stance] = {}
    for feature in Feature:
        mine = [c for c in claims if c.feature is feature]
        own = {c.polarity for c in mine if not c.shared}
        if Polarity.HAS in own:
            found[feature] = Stance.HAS
        elif Polarity.HAS_NOT in own:
            found[feature] = Stance.HAS_NOT
        elif mine:
            found[feature] = Stance.SHARED
        else:
            found[feature] = Stance.NONE
    return found


@dataclass(slots=True)
class ClaimCounts:
    true_positive: int = 0  # a claim extracted with the stance the person read
    false_positive: int = 0  # a claim extracted that the person did not read
    false_negative: int = 0  # a claim the person read that was not extracted as such


@dataclass(slots=True)
class ClaimScore:
    total: ClaimCounts = field(default_factory=ClaimCounts)
    per_feature: dict[Feature, ClaimCounts] = field(default_factory=dict)

    def add(self, predicted: Mapping[Feature, Stance], labelled: Mapping[Feature, Stance]) -> None:
        for feature in Feature:
            got = predicted.get(feature, Stance.NONE)
            said = labelled.get(feature, Stance.NONE)
            counts = self.per_feature.setdefault(feature, ClaimCounts())
            for target in (counts, self.total):
                if got is not Stance.NONE and got is said:
                    target.true_positive += 1
                    continue
                if got is not Stance.NONE:
                    target.false_positive += 1
                if said is not Stance.NONE:
                    target.false_negative += 1
