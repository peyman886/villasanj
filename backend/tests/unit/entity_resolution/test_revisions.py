"""Label corrections: applied all-or-nothing, idempotent, and the original kept beside them."""

from pathlib import Path

import pytest

from tests.fakes.er import LabelStoreFake
from tests.fakes.ingestion import SteppingClock
from tests.fakes.llm import NOW
from tests.unit.entity_resolution.test_villas import A, B, C
from villasanj.entity_resolution.application.revisions import (
    OriginalLabels,
    PlannedRevision,
    ReviseLabels,
)
from villasanj.entity_resolution.domain.labels import Label, PairLabel
from villasanj.entity_resolution.infrastructure.revisions_file import load_revisions
from villasanj.shared.application.errors import ConfigurationError

FILE = Path(__file__).parents[4] / "eval" / "labels" / "gold-v1-revisions-2026-10-04.toml"


async def labelled() -> LabelStoreFake:
    store = LabelStoreFake()
    for key, label in ((A, Label.MATCH), (B, Label.MATCH), (C, Label.NON_MATCH)):
        await store.save_label(PairLabel(key, label, "owner", NOW))
    return store


async def test_revisions_change_the_labels_and_keep_the_originals() -> None:
    store = await labelled()
    planned = [PlannedRevision(B, Label.MATCH, Label.NON_MATCH, "units 2 and 4")]
    report = await ReviseLabels(store, SteppingClock()).run(planned, "owner", "agent")
    assert (report.applied, report.already, report.conflicts) == (1, 0, [])
    now = {lb.key: lb.label for lb in await store.labels("owner")}
    assert now[B] is Label.NON_MATCH
    (revision,) = await store.revisions("owner")
    assert (revision.before, revision.after, revision.reason) == (
        Label.MATCH,
        Label.NON_MATCH,
        "units 2 and 4",
    )
    original = {lb.key: lb.label for lb in await OriginalLabels(store).labels("owner")}
    assert original == {A: Label.MATCH, B: Label.MATCH, C: Label.NON_MATCH}
    again = await ReviseLabels(store, SteppingClock()).run(planned, "owner", "agent")
    assert (again.applied, again.already) == (0, 1)  # a re-run changes nothing


async def test_one_conflict_applies_nothing() -> None:
    store = await labelled()
    planned = [
        PlannedRevision(A, Label.MATCH, Label.UNSURE, "ok"),
        PlannedRevision(C, Label.MATCH, Label.UNSURE, "C is labelled non_match, not match"),
    ]
    report = await ReviseLabels(store, SteppingClock()).run(planned, "owner", "agent")
    assert report.applied == 0
    assert len(report.conflicts) == 1
    assert await store.revisions("owner") == []
    with pytest.raises(PermissionError):
        await OriginalLabels(store).save_label(PairLabel(A, Label.MATCH, "owner", NOW))


def test_the_committed_gold_v1_revision_file_is_valid() -> None:
    revisions = load_revisions(FILE)
    assert revisions.labeler == "owner"
    assert len(revisions.revisions) == 48
    assert {r.before for r in revisions.revisions} == {Label.MATCH}
    assert all(r.reason for r in revisions.revisions)


def test_a_bad_revision_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "r.toml"
    path.write_text(
        'labeler = "owner"\nrevised_by = "x"\n'
        '[[revision]]\npair = "a:1|b:2"\nfrom = "match"\nto = "match"\nreason = "no-op"\n'
    )
    with pytest.raises(ConfigurationError):
        load_revisions(path)
