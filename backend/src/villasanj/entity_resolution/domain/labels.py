"""Human labels: the only evaluation truth (ADR-0009). LLM output never becomes a label."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from villasanj.entity_resolution.domain.pairs import PairKey


class Label(StrEnum):
    MATCH = "match"
    NON_MATCH = "non_match"
    UNSURE = "unsure"  # excluded from precision/recall; its rate is reported


@dataclass(frozen=True, slots=True)
class PairLabel:
    key: PairKey
    label: Label
    labeler: str
    labeled_at: datetime
    seconds: float | None = None  # time the labeler spent on the pair


@dataclass(frozen=True, slots=True)
class QueueItem:
    """A pair chosen for labelling, with the stratum it was drawn from and that stratum's size.

    Weights are computed at evaluation time as stratum size / pairs labelled in the stratum, so
    stopping the queue early still gives unbiased estimates.
    """

    position: int
    key: PairKey
    stratum: str
    stratum_size: int
