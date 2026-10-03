"""The entity resolution evaluation report (ROADMAP M5 criterion 3), generated from the database.

Pairwise precision, recall and F1 (weighted by stratum, Wilson 95% intervals), a precision-recall
curve of the rule score with the chosen threshold, every decision policy end to end with B-cubed,
the H5 ablations, and what the judge said about the production candidates. Nothing is typed by
hand: the same match run, labels and judgements always give the same report.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import datetime

from villasanj.entity_resolution.application.evaluation import (
    Ablation,
    EvaluateAblations,
    EvaluateMatcher,
    EvaluationReport,
)
from villasanj.entity_resolution.application.ports import CandidateStore, LabelStore
from villasanj.entity_resolution.application.villas import (
    ClusterEvaluation,
    DecisionEvaluation,
    DecisionPolicy,
    ErConfig,
    EvaluateDecisions,
    EvaluateVillas,
    JudgementStore,
)
from villasanj.entity_resolution.domain.evaluation import Interval, Metrics

CURVE = tuple(t / 4 for t in range(-12, 33))  # -3 .. 8 in steps of 0.25
MIN_PRECISION, MIN_PRECISION_LOW = 0.95, 0.92  # the M5 criterion 2 bar (ADR-0009)


@dataclass(frozen=True, slots=True)
class PolicyResult:
    name: str
    policy: DecisionPolicy
    pairwise: DecisionEvaluation
    clusters: ClusterEvaluation

    @property
    def meets_bar(self) -> bool:
        p = self.pairwise.metrics.precision
        return p.estimate is not None and p.estimate >= MIN_PRECISION and p.low >= MIN_PRECISION_LOW


@dataclass(slots=True)
class ErReport:
    generated_at: datetime
    config: ErConfig
    matcher: EvaluationReport
    policies: list[PolicyResult]
    ablations: list[Ablation]
    verdicts: Counter[str] = field(default_factory=Counter)  # "below:match:confident", ...
    queue: Counter[str] = field(default_factory=Counter)  # human queue stratum -> pairs


class BuildErReport:
    def __init__(
        self,
        candidates: CandidateStore,
        labels: LabelStore,
        judgements: JudgementStore,
        villas: EvaluateVillas,
        config: ErConfig,
    ) -> None:
        self._candidates = candidates
        self._labels = labels
        self._judgements = judgements
        self._villas = villas
        self._config = config

    def policies(self) -> list[tuple[str, DecisionPolicy]]:
        chosen = self._config.policy
        full = replace(chosen, judge_merges=True, judge_vetoes=True)
        return [
            ("rules alone", DecisionPolicy(chosen.threshold)),
            ("advisory judge (config/er.toml)", chosen),
            ("judge merges and vetoes", full),
            ("judge merges, no vetoes", replace(full, judge_vetoes=False)),
            ("judge vetoes only above the threshold", replace(full, judge_low=chosen.threshold)),
        ]

    async def run(self, queue: str, labeler: str, now: datetime) -> ErReport:
        matcher = await EvaluateMatcher(self._candidates, self._labels).run(queue, labeler, CURVE)
        decisions = EvaluateDecisions(self._candidates, self._labels, self._judgements)
        results = []
        for name, policy in self.policies():
            results.append(
                PolicyResult(
                    name,
                    policy,
                    await decisions.run(policy, queue, labeler),
                    await self._villas.run(policy, queue, labeler),
                )
            )
        ablations = await EvaluateAblations(self._candidates, self._labels).run(queue, labeler)
        report = ErReport(now, self._config, matcher, results, ablations)
        scores = {c.key: c.score.value for c in await self._candidates.current() if c.score}
        chosen = self._config.policy
        for j in await self._judgements.all():
            score = scores.get(j.key)
            if score is None or not chosen.judge_low <= score < chosen.judge_high:
                continue
            band = "below" if score < chosen.threshold else "above"
            sure = "confident" if j.confidence >= chosen.judge_min_confidence else "low"
            report.verdicts[f"{band}:{j.verdict}:{sure}"] += 1
        human = await self._labels.queue(self._config.human_queue)
        report.queue.update(item.stratum for item in human)
        return report


def _pct(interval: Interval) -> str:
    if interval.estimate is None:
        return "n/a"
    return f"{interval.estimate:.1%} ({interval.low:.1%}–{interval.high:.1%})"


def _f1(metrics: Metrics) -> str:
    return f"{metrics.f1:.3f}" if metrics.f1 is not None else "n/a"


def _policy_text(policy: DecisionPolicy) -> str:
    if policy.judge_low == policy.judge_high:
        return f"score ≥ {policy.threshold:g}"
    roles = []
    roles.append("merges" if policy.judge_merges else "suggests")
    roles.append("vetoes" if policy.judge_vetoes else "disputes")
    return (
        f"score ≥ {policy.threshold:g}; judge in [{policy.judge_low:g}, {policy.judge_high:g}) "
        f"at confidence ≥ {policy.judge_min_confidence:g} {' and '.join(roles)}"
    )


def render_markdown(report: ErReport) -> str:
    m = report.matcher
    run = m.run
    lines = [
        "# M5 entity resolution evaluation",
        "",
        f"Generated {report.generated_at:%Y-%m-%d %H:%M} UTC from the database. "
        f"Match run `{run.id if run else 'none'}`, dataset `{run.dataset_hash if run else '-'}`; "
        f"gold set `{m.queue}`, {m.labelled}/{m.queued} pairs labelled by `{m.labeler}` "
        f"(unsure {_pct(m.unsure)}). Reproduce: `uv run villasanj er report`.",
        "",
        "Precision and recall are over cross-platform pairs, weighted by stratum (each labelled "
        "pair stands for its stratum's candidates), with Wilson 95% intervals on the effective "
        "sample size. The bar (M5 criterion 2, ADR-0009): precision ≥ 95% and its lower bound "
        "≥ 92%.",
        "",
        "## Rule score: precision-recall curve",
        "",
        f"Blocking recall on gold matches: {_pct(m.blocking_recall)}. TP, FP and FN count "
        "labelled pairs (unweighted); precision and recall are weighted.",
        "",
        "| Threshold | Precision | Recall | F1 | TP | FP | FN |",
        "|---|---|---|---|---|---|---|",
    ]
    op = m.operating_point
    for point in m.curve:
        mark = " **(chosen)**" if op is not None and point.threshold == op.threshold else ""
        lines.append(
            f"| {point.threshold:g}{mark} | {_pct(point.precision)} | {_pct(point.recall)} | "
            f"{_f1(point)} | {point.true_positives} | {point.false_positives} | "
            f"{point.false_negatives} |"
        )
    if op is not None:
        lines += [
            "",
            f"Chosen threshold (the lowest that clears the bar): **{op.threshold:g}**, precision "
            f"{_pct(op.precision)}, recall {_pct(op.recall)}, F1 {_f1(op)}.",
        ]
    lines += [
        "",
        "## Decision policies end to end",
        "",
        "Each policy is scored with the owner's labels **not** applied (they would make it "
        "perfect). B-cubed compares the villas the policy builds with the clusters the labels "
        "imply, over the labelled listings (unweighted, so singletons dominate it).",
        "",
        "| Policy | Rule | Precision | Recall | F1 | TP/FP/FN | Waiting | B-cubed P/R/F1 | Bar |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in report.policies:
        p = r.pairwise.metrics
        b = r.clusters.bcubed
        cubed = f"{b.precision:.3f} / {b.recall:.3f} / {b.f1:.3f}" if b else "n/a"
        lines.append(
            f"| {r.name} | {_policy_text(r.policy)} | {_pct(p.precision)} | {_pct(p.recall)} | "
            f"{_f1(p)} | {p.true_positives}/{p.false_positives}/{p.false_negatives} | "
            f"{r.pairwise.waiting} | {cubed} | {'yes' if r.meets_bar else 'no'} |"
        )
    lines += ["", "## H5 ablations (M5 criterion 6)", ""]
    lines += ["| Evidence | At the bar | Best F1 |", "|---|---|---|"]
    for a in report.ablations:
        at_bar = (
            f"threshold {a.operating_point.threshold:g}: P {_pct(a.operating_point.precision)}, "
            f"R {_pct(a.operating_point.recall)}"
            if a.operating_point
            else "no threshold reaches it"
        )
        best = (
            f"{_f1(a.best_f1)} at {a.best_f1.threshold:g} (P {_pct(a.best_f1.precision)}, "
            f"R {_pct(a.best_f1.recall)})"
            if a.best_f1
            else "n/a"
        )
        lines.append(f"| {a.name} | {at_bar} | {best} |")
    chosen = report.config.policy
    lines += [
        "",
        "## The judge on the production candidates",
        "",
        f"Verdicts on candidates scored in [{chosen.judge_low:g}, {chosen.judge_high:g}), "
        f"below or at/above the threshold {chosen.threshold:g} (confident: ≥ "
        f"{chosen.judge_min_confidence:g}). The model bake-off is in the ADR-0005 amendment of "
        "2026-10-03.",
        "",
        "| Band | Verdict | Confident | Pairs |",
        "|---|---|---|---|",
    ]
    for key, count in sorted(report.verdicts.items()):
        band, verdict, sure = key.split(":")
        lines.append(f"| {band} | {verdict} | {'yes' if sure == 'confident' else 'no'} | {count} |")
    queued = sum(report.queue.values())
    parts = ", ".join(f"{k.removeprefix('judge:')} {v}" for k, v in sorted(report.queue.items()))
    lines += [
        "",
        f"Human queue `{report.config.human_queue}`: {queued} pairs ({parts}).",
        "",
    ]
    return "\n".join(lines)
