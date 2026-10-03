"""The M5 evaluation report: every policy scored the same way, nothing typed by hand."""

from dataclasses import replace
from datetime import timedelta

from tests.fakes.llm import NOW
from tests.unit.entity_resolution.test_villas import ZONE, A, B, C, setup
from villasanj.entity_resolution.application.report import BuildErReport, render_markdown
from villasanj.entity_resolution.application.villas import (
    ErConfig,
    EvaluateVillas,
    StoredJudgement,
)
from villasanj.entity_resolution.domain.labels import Label, PairLabel, QueueItem


class Judgements:
    async def all(self) -> list[StoredJudgement]:
        return [StoredJudgement(B, "match", 0.9, "m"), StoredJudgement(C, "non_match", 0.95, "m")]


async def test_the_report_scores_each_policy_and_marks_the_chosen_threshold() -> None:
    build, labels, _ = setup()
    await labels.save_queue("gold", [QueueItem(i, k, "s", 3) for i, k in enumerate((A, B, C))])
    for key, verdict in ((A, Label.MATCH), (B, Label.MATCH), (C, Label.NON_MATCH)):
        await labels.save_label(PairLabel(key, verdict, "owner", NOW + timedelta(seconds=1)))
    config = ErConfig(replace(ZONE, judge_high=4.0), "human")  # C (score 3) inside the zone
    report = await BuildErReport(
        build._candidates,
        labels,
        Judgements(),
        EvaluateVillas(build, labels),
        config,
    ).run("gold", "owner", NOW)
    names = [r.name for r in report.policies]
    assert names[0] == "rules alone"
    assert "judge merges and vetoes" in names
    rules = report.policies[0].pairwise.metrics
    assert (rules.true_positives, rules.false_positives) == (1, 1)  # C merged by the rules
    full = next(r for r in report.policies if r.name == "judge merges and vetoes")
    assert (full.pairwise.metrics.true_positives, full.pairwise.metrics.false_positives) == (2, 0)
    assert report.verdicts == {"below:match:confident": 1, "above:non_match:confident": 1}
    text = render_markdown(report)
    assert text.startswith("# M5 entity resolution evaluation")
    assert "## Decision policies end to end" in text
    assert "Reproduce: `uv run villasanj er report`" in text
