"""The M5 evaluation report: every policy scored the same way, before and after human review."""

from dataclasses import replace
from datetime import timedelta

from tests.fakes.ingestion import SteppingClock
from tests.fakes.llm import NOW
from tests.unit.entity_resolution.test_villas import ZONE, A, B, C, setup
from villasanj.entity_resolution.application.report import (
    BuildErReport,
    render_markdown,
    to_artifact,
)
from villasanj.entity_resolution.application.revisions import PlannedRevision, ReviseLabels
from villasanj.entity_resolution.application.villas import ErConfig, StoredJudgement
from villasanj.entity_resolution.domain.labels import Label, PairLabel, QueueItem


class Judgements:
    async def all(self) -> list[StoredJudgement]:
        return [StoredJudgement(B, "match", 0.9, "m"), StoredJudgement(C, "non_match", 0.95, "m")]


async def test_the_report_scores_each_policy_before_and_after_the_revisions() -> None:
    build, labels, _ = setup()
    await labels.save_queue("gold", [QueueItem(i, k, "s", 3) for i, k in enumerate((A, B, C))])
    for key in (A, B, C):  # C: the owner first said "same villa"...
        await labels.save_label(PairLabel(key, Label.MATCH, "owner", NOW + timedelta(seconds=1)))
    revision = PlannedRevision(C, Label.MATCH, Label.NON_MATCH, "units 2 and 4 of one complex")
    await ReviseLabels(labels, SteppingClock()).run([revision], "owner", "agent")  # ...then N
    config = ErConfig(replace(ZONE, judge_high=4.0, judge_merges=False), "human")
    report = await BuildErReport(
        build._candidates,
        labels,
        Judgements(),
        build,
        config,
    ).run("gold", "owner", NOW)
    revised = {r.name: r for r in report.revised.policies}
    original = {r.name: r for r in report.original.policies}
    rules_now = revised["rules alone"].pairwise.metrics
    rules_then = original["rules alone"].pairwise.metrics
    assert (rules_then.true_positives, rules_then.false_positives) == (2, 0)  # C counted right
    assert (rules_now.true_positives, rules_now.false_positives) == (1, 1)  # C now a false merge
    vetoes = revised["judge vetoes, a human merges"]
    assert vetoes.configured
    assert vetoes.pairwise.metrics.false_positives == 0  # the judge vetoes C
    assert [r.after for r in report.revisions] == [Label.NON_MATCH]
    assert report.villas_now.labels == "revised"
    text = render_markdown(report)
    assert "## What changed after human review" in text
    assert "units 2 and 4 of one complex" in text
    artifact = to_artifact(report)
    assert artifact["kind"] == "er-eval"
    assert artifact["provenance"]["revisions"] == 1  # type: ignore[index]
    candidates = artifact["data"]["candidates"]  # type: ignore[index]
    assert candidates == {"total": report.candidates, "blocked": report.blocked}
    assert report.candidates >= report.blocked > 0
    assert f"Candidate pairs: {report.candidates}" in text
