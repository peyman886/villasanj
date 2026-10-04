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


@dataclass(frozen=True, slots=True)
class LabelRevision:
    """A correction of a labeler's decision, kept beside it (the history is never rewritten).

    Revisions follow the labelling protocol, at the labeler's request: e.g. on 2026-10-04 the
    owner asked to correct "same villa" labels on different units of one complex to N or U.
    """

    key: PairKey
    labeler: str
    before: Label
    after: Label
    reason: str  # the evidence, in words a reviewer can check
    revised_by: str
    revised_at: datetime


def as_originally_labelled(
    labels: list[PairLabel], revisions: list[LabelRevision]
) -> list[PairLabel]:
    """The labels as they were before any revision (the earliest ``before`` of each pair)."""
    first: dict[tuple[PairKey, str], LabelRevision] = {}
    for revision in sorted(revisions, key=lambda r: r.revised_at):
        first.setdefault((revision.key, revision.labeler), revision)
    return [
        PairLabel(lb.key, r.before, lb.labeler, lb.labeled_at, lb.seconds)
        if (r := first.get((lb.key, lb.labeler)))
        else lb
        for lb in labels
    ]
