"""Corrections of human labels (protocol-driven, at the labeler's request), and the labels as
they were before them, so every evaluation can be reproduced both ways ("what changed after
human review")."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from villasanj.entity_resolution.application.ports import LabelStore
from villasanj.entity_resolution.domain.labels import (
    Label,
    LabelRevision,
    PairLabel,
    QueueItem,
    as_originally_labelled,
)
from villasanj.entity_resolution.domain.pairs import PairKey
from villasanj.shared.application.clock import Clock


@dataclass(frozen=True, slots=True)
class PlannedRevision:
    key: PairKey
    before: Label
    after: Label
    reason: str


@dataclass(slots=True)
class RevisionReport:
    applied: int = 0
    already: int = 0  # the label already says what the file wants (a re-run)
    conflicts: list[str] = field(default_factory=list)  # nothing is applied when there is one


class ReviseLabels:
    def __init__(self, labels: LabelStore, clock: Clock) -> None:
        self._labels = labels
        self._clock = clock

    async def run(
        self, planned: Sequence[PlannedRevision], labeler: str, revised_by: str
    ) -> RevisionReport:
        report = RevisionReport()
        current = {lb.key: lb.label for lb in await self._labels.labels(labeler)}
        todo = []
        for p in planned:
            label = current.get(p.key)
            if label is p.after:
                report.already += 1
            elif label is p.before:
                todo.append(p)
            else:
                found = label.value if label else "no label"
                report.conflicts.append(f"{p.key}: expected {p.before.value}, found {found}")
        if report.conflicts:
            return report
        now = self._clock.now()
        for p in todo:
            revision = LabelRevision(p.key, labeler, p.before, p.after, p.reason, revised_by, now)
            await self._labels.revise(revision)
            report.applied += 1
        return report


class OriginalLabels:
    """A read-only label store that answers with the labels as first given (before revisions)."""

    def __init__(self, labels: LabelStore) -> None:
        self._labels = labels

    async def queue(self, queue: str) -> list[QueueItem]:
        return await self._labels.queue(queue)

    async def labels(self, labeler: str) -> list[PairLabel]:
        return as_originally_labelled(
            await self._labels.labels(labeler), await self._labels.revisions(labeler)
        )

    async def revisions(self, labeler: str) -> list[LabelRevision]:
        return []  # as first given: nothing was revised yet

    async def save_queue(self, queue: str, items: Sequence[QueueItem]) -> None:
        raise PermissionError("the original labels are read-only")

    async def save_label(self, label: PairLabel) -> None:
        raise PermissionError("the original labels are read-only")

    async def revise(self, revision: LabelRevision) -> None:
        raise PermissionError("the original labels are read-only")
