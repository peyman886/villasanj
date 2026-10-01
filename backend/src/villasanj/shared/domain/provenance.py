"""Provenance: where every user-visible value came from, and when (ADR-0007)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from villasanj.shared.domain.errors import InvalidProvenance


class ProvenanceMethod(StrEnum):
    OBSERVED = "observed"  # read from a stored snapshot of a source page
    DERIVED = "derived"  # computed deterministically from other sourced values
    LLM_EXTRACTED = "llm_extracted"  # extracted by an LLM from sourced text, then verified
    HUMAN = "human"  # decided or labelled by a person


@dataclass(frozen=True, slots=True)
class SourceRef:
    platform: str
    url: str


@dataclass(frozen=True, slots=True)
class Provenance:
    method: ProvenanceMethod
    observed_at: datetime
    source: SourceRef | None = None
    snapshot_id: str | None = None
    derived_from: tuple[Provenance, ...] = field(default=())

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise InvalidProvenance("observed_at must be timezone-aware")
        if self.method is ProvenanceMethod.OBSERVED and (
            self.source is None or not self.snapshot_id
        ):
            raise InvalidProvenance("observed values need a source and a snapshot id")
        needs_inputs = (ProvenanceMethod.DERIVED, ProvenanceMethod.LLM_EXTRACTED)
        if self.method in needs_inputs and not self.derived_from:
            raise InvalidProvenance(f"{self.method} values must reference their inputs")

    @property
    def oldest_observation(self) -> datetime:
        """The age of a value is the age of its oldest input."""
        return min((self.observed_at, *(p.oldest_observation for p in self.derived_from)))


@dataclass(frozen=True, slots=True)
class Sourced[T]:
    """A value together with its provenance."""

    value: T
    provenance: Provenance
