"""The entity resolution evaluation report (ROADMAP M5 criterion 3), generated from the database.

Pairwise precision, recall and F1 (weighted by stratum, Wilson 95% intervals), a precision-recall
curve of the rule score with the threshold the gold set chooses, every decision policy end to end
with B-cubed, the H5 ablations, what the judge said about the production candidates, and what
changed after human review: the same policies on the labels as first given, every label revision
with its reason, and the canonical villas before and after. Nothing is typed by hand: the same
match run, labels, revisions and judgements always give the same report.
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
from villasanj.entity_resolution.application.revisions import OriginalLabels
from villasanj.entity_resolution.application.villas import (
    BuildVillas,
    ClusterEvaluation,
    DecisionEvaluation,
    DecisionPolicy,
    ErConfig,
    EvaluateDecisions,
    EvaluateVillas,
    JudgementStore,
    describe_policy,
)
from villasanj.entity_resolution.domain.evaluation import Interval, Metrics, wilson
from villasanj.entity_resolution.domain.labels import LabelRevision
from villasanj.shared.application.artifacts import envelope

CURVE = tuple(t / 4 for t in range(-12, 33))  # -3 .. 8 in steps of 0.25
MIN_PRECISION, MIN_PRECISION_LOW = 0.95, 0.92  # the M5 criterion 2 bar (ADR-0009)
COMMAND = "uv run villasanj er report"
# The policy in force before the owner's label revision of 2026-10-04 (config/er.toml at 6321b08):
# kept here so the report can show what the revision changed.
PREVIOUS_POLICY = DecisionPolicy(-0.25, -2.0, 3.0, 0.8, judge_merges=False, judge_vetoes=False)


@dataclass(frozen=True, slots=True)
class PolicyResult:
    name: str
    policy: DecisionPolicy
    pairwise: DecisionEvaluation
    clusters: ClusterEvaluation
    configured: bool = False  # the policy config/er.toml runs in production

    @property
    def meets_bar(self) -> bool:
        p = self.pairwise.metrics.precision
        return p.estimate is not None and p.estimate >= MIN_PRECISION and p.low >= MIN_PRECISION_LOW


@dataclass(frozen=True, slots=True)
class VillaCounts:
    policy: DecisionPolicy
    labels: str  # "revised" or "as first given"
    listings: int
    villas: int
    multi_platform: int
    applied: dict[str, int]  # decider -> merges
    refused: dict[str, int]  # reason -> merges refused


@dataclass(frozen=True, slots=True)
class LabelledEvaluation:
    """The matcher and every policy against one version of the labels."""

    matcher: EvaluationReport
    policies: list[PolicyResult]


@dataclass(slots=True)
class ErReport:
    generated_at: datetime
    config: ErConfig
    revised: LabelledEvaluation
    original: LabelledEvaluation
    revisions: list[LabelRevision]
    villas_now: VillaCounts
    villas_before: VillaCounts
    ablations: list[Ablation]
    stratum_of: dict[str, str] = field(default_factory=dict)  # pair -> its gold stratum
    candidates: int = 0  # candidate pairs of the match run
    blocked: int = 0  # of those, found by the production blocking (the rest: the wide net)
    verdicts: Counter[str] = field(default_factory=Counter)  # "below:match:confident", ...
    queue: Counter[str] = field(default_factory=Counter)  # human queue stratum -> pairs
    # The owner's labels on the human queue, per reason: "judge:suggested" -> {"match": 70, ...}
    queue_labels: dict[str, Counter[str]] = field(default_factory=dict)

    def judge_on_queue(self) -> dict[str, Interval]:
        """How the judge's calls held up against the labels a person gave on its own queue:
        its suggested matches (merges it would make below the threshold) and its vetoes."""
        suggested = self.queue_labels.get("judge:suggested", Counter())
        disputed = self.queue_labels.get("judge:disputed", Counter())
        return {
            "suggested_match_precision": wilson(
                suggested["match"], suggested["match"] + suggested["non_match"]
            ),
            "veto_precision": wilson(
                disputed["non_match"], disputed["match"] + disputed["non_match"]
            ),
        }


class BuildErReport:
    def __init__(
        self,
        candidates: CandidateStore,
        labels: LabelStore,
        judgements: JudgementStore,
        villas: BuildVillas,
        config: ErConfig,
    ) -> None:
        self._candidates = candidates
        self._labels = labels
        self._judgements = judgements
        self._villas = villas
        self._config = config

    def policies(self, gold_threshold: float | None) -> list[tuple[str, DecisionPolicy]]:
        chosen = self._config.policy
        full = replace(chosen, judge_merges=True, judge_vetoes=True)
        named = [("rules alone", DecisionPolicy(chosen.threshold))]
        if gold_threshold is not None and gold_threshold != chosen.threshold:
            named.append(("rules alone at the gold-set threshold", DecisionPolicy(gold_threshold)))
        named += [
            ("advisory judge", replace(full, judge_merges=False, judge_vetoes=False)),
            ("judge vetoes, a human merges", replace(full, judge_merges=False)),
            ("judge merges and vetoes", full),
            ("judge merges, no vetoes", replace(full, judge_vetoes=False)),
        ]
        return named

    async def _evaluate(self, labels: LabelStore, queue: str, labeler: str) -> LabelledEvaluation:
        matcher = await EvaluateMatcher(self._candidates, labels).run(queue, labeler, CURVE)
        point = matcher.operating_point
        decisions = EvaluateDecisions(self._candidates, labels, self._judgements)
        clusters = EvaluateVillas(self._villas.with_labels(labels), labels)
        results = []
        for name, policy in self.policies(point.threshold if point else None):
            results.append(
                PolicyResult(
                    name,
                    policy,
                    await decisions.run(policy, queue, labeler),
                    await clusters.run(policy, queue, labeler),
                    configured=policy == self._config.policy,
                )
            )
        return LabelledEvaluation(matcher, results)

    async def _villa_counts(
        self, policy: DecisionPolicy, labels: LabelStore, name: str, labeler: str
    ) -> VillaCounts:
        listing_ids, clustering, _ = await self._villas.with_labels(labels).clustering(
            policy, labeler
        )
        return VillaCounts(
            policy,
            name,
            len(listing_ids),
            len(clustering.clusters),
            sum(len(c) > 1 for c in clustering.clusters),
            dict(Counter(d.decided_by.value for d in clustering.applied)),
            dict(Counter(b.reason.value for b in clustering.blocked)),
        )

    async def run(self, queue: str, labeler: str, now: datetime) -> ErReport:
        original_labels = OriginalLabels(self._labels)
        report = ErReport(
            now,
            self._config,
            revised=await self._evaluate(self._labels, queue, labeler),
            original=await self._evaluate(original_labels, queue, labeler),
            revisions=await self._labels.revisions(labeler),
            villas_now=await self._villa_counts(
                self._config.policy, self._labels, "revised", labeler
            ),
            villas_before=await self._villa_counts(
                PREVIOUS_POLICY, original_labels, "as first given", labeler
            ),
            ablations=await EvaluateAblations(self._candidates, self._labels).run(queue, labeler),
            stratum_of={str(i.key): i.stratum for i in await self._labels.queue(queue)},
        )
        current = await self._candidates.current()
        report.candidates = len(current)
        report.blocked = sum(c.blocked for c in current)
        scores = {c.key: c.score.value for c in current if c.score}
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
        given = {label.key: label.label for label in await self._labels.labels(labeler)}
        for item in human:
            if item.key in given:
                counts = report.queue_labels.setdefault(item.stratum, Counter())
                counts[given[item.key].value] += 1
        return report


def _pct(interval: Interval) -> str:
    if interval.estimate is None:
        return "n/a"
    return f"{interval.estimate:.1%} ({interval.low:.1%}–{interval.high:.1%})"


def _f1(metrics: Metrics) -> str:
    return f"{metrics.f1:.3f}" if metrics.f1 is not None else "n/a"


def _revision_kind(report: ErReport, revision: LabelRevision) -> str:
    stratum = report.stratum_of.get(str(revision.key), "-")
    side = "same platform" if not revision.key.cross_platform else "cross-platform"
    return f"{side} ({stratum})"


def _policy_table(evaluation: LabelledEvaluation) -> list[str]:
    lines = [
        "| Policy | Rule | Precision | Recall | F1 | TP/FP/FN | Waiting | B-cubed P/R/F1 | Bar |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in evaluation.policies:
        p = r.pairwise.metrics
        b = r.clusters.bcubed
        cubed = f"{b.precision:.3f} / {b.recall:.3f} / {b.f1:.3f}" if b else "n/a"
        name = f"**{r.name}** (config/er.toml)" if r.configured else r.name
        lines.append(
            f"| {name} | {describe_policy(r.policy)} | {_pct(p.precision)} | {_pct(p.recall)} | "
            f"{_f1(p)} | {p.true_positives}/{p.false_positives}/{p.false_negatives} | "
            f"{r.pairwise.waiting} | {cubed} | {'yes' if r.meets_bar else 'no'} |"
        )
    return lines


def _configured(evaluation: LabelledEvaluation, policy: DecisionPolicy) -> PolicyResult | None:
    return next((r for r in evaluation.policies if r.policy == policy), None)


def render_markdown(report: ErReport) -> str:
    m = report.revised.matcher
    run = m.run
    now_policy = report.config.policy
    after = _configured(report.revised, now_policy)
    before = _configured(report.original, PREVIOUS_POLICY)
    lines = [
        "# M5 entity resolution evaluation",
        "",
        f"Generated {report.generated_at:%Y-%m-%d %H:%M} UTC from the database. Match run "
        f"`{run.id if run else 'none'}`, dataset `{run.dataset_hash if run else '-'}`; gold set "
        f"`{m.queue}`, {m.labelled}/{m.queued} pairs labelled by `{m.labeler}` "
        f"(unsure {_pct(m.unsure)}), {len(report.revisions)} labels revised. Reproduce: "
        f"`{COMMAND}`.",
        "",
        "Precision and recall are over cross-platform pairs, weighted by stratum (each labelled "
        "pair stands for its stratum's candidates), with Wilson 95% intervals on the effective "
        "sample size. The bar (M5 criterion 2, ADR-0009): precision ≥ 95% and its lower bound "
        "≥ 92%; the chosen policy is the one with the highest recall that clears it.",
        "",
        "## What changed after human review",
        "",
        "| | Before (labels as first given) | After (revised labels) |",
        "|---|---|---|",
        f"| Policy | {describe_policy(PREVIOUS_POLICY)} | {describe_policy(now_policy)} |",
    ]
    if before and after:
        bp, ap = before.pairwise.metrics, after.pairwise.metrics
        lines += [
            f"| Precision | {_pct(bp.precision)} | {_pct(ap.precision)} |",
            f"| Recall | {_pct(bp.recall)} | {_pct(ap.recall)} |",
        ]
    ob, oa = report.original.matcher.operating_point, m.operating_point
    lines += [
        "| Threshold the gold set picks for the rules alone | "
        f"{ob.threshold if ob else 'none':} | {oa.threshold if oa else 'none'} |",
        f"| Canonical villas (two-platform) | {report.villas_before.villas} "
        f"({report.villas_before.multi_platform}) | {report.villas_now.villas} "
        f"({report.villas_now.multi_platform}) |",
        "",
    ]
    lines += [
        "## Rule score: precision-recall curve",
        "",
        f"Candidate pairs: {report.candidates} ({report.blocked} from the production blocking). "
        f"Blocking recall on gold matches: {_pct(m.blocking_recall)}. TP, FP and FN count "
        "labelled pairs (unweighted); precision and recall are weighted.",
        "",
        "| Threshold | Precision | Recall | F1 | TP | FP | FN |",
        "|---|---|---|---|---|---|---|",
    ]
    for point in m.curve:
        mark = " **(gold-set pick)**" if oa is not None and point.threshold == oa.threshold else ""
        lines.append(
            f"| {point.threshold:g}{mark} | {_pct(point.precision)} | {_pct(point.recall)} | "
            f"{_f1(point)} | {point.true_positives} | {point.false_positives} | "
            f"{point.false_negatives} |"
        )
    lines += [
        "",
        "## Decision policies end to end",
        "",
        "Each policy is scored with the owner's labels **not** applied (they would make it "
        "perfect). B-cubed compares the villas the policy builds with the clusters the labels "
        "imply, over the labelled listings (unweighted, so singletons dominate it).",
        "",
        *_policy_table(report.revised),
        "",
        "### The same policies on the labels as first given (history)",
        "",
        *_policy_table(report.original),
        "",
        "## Label revisions",
        "",
    ]
    by_change = Counter(
        (_revision_kind(report, r).split(" (")[0], r.before.value, r.after.value)
        for r in report.revisions
    )
    lines += ["| Pairs | From | To | Count |", "|---|---|---|---|"]
    for (side, before_label, after_label), count in sorted(by_change.items()):
        lines.append(f"| {side} | {before_label} | {after_label} | {count} |")
    lines += ["", "| Pair | Kind | From → to | Reason |", "|---|---|---|---|"]
    for r in report.revisions:
        lines.append(
            f"| `{r.key}` | {_revision_kind(report, r)} | {r.before.value} → {r.after.value} | "
            f"{r.reason} |"
        )
    lines += ["", "## Canonical villas", ""]
    lines += ["| | Policy | Villas | Two-platform | Merges by decider | Refused |"]
    lines += ["|---|---|---|---|---|---|"]
    for counts in (report.villas_before, report.villas_now):
        lines.append(
            f"| labels {counts.labels} | {describe_policy(counts.policy)} | {counts.villas} | "
            f"{counts.multi_platform} | {dict(sorted(counts.applied.items()))} | "
            f"{dict(sorted(counts.refused.items()))} |"
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
    lines += [
        "",
        "## The judge on the production candidates",
        "",
        f"Verdicts on candidates scored in [{now_policy.judge_low:g}, {now_policy.judge_high:g}), "
        f"below or at/above the threshold {now_policy.threshold:g} (confident: ≥ "
        f"{now_policy.judge_min_confidence:g}). The model bake-off is in ADR-0005.",
        "",
        "| Band | Verdict | Confident | Pairs |",
        "|---|---|---|---|",
    ]
    for key, count in sorted(report.verdicts.items()):
        band, verdict, sure = key.split(":")
        lines.append(f"| {band} | {verdict} | {'yes' if sure == 'confident' else 'no'} | {count} |")
    queued = sum(report.queue.values())
    parts = ", ".join(f"{k.removeprefix('judge:')} {v}" for k, v in sorted(report.queue.items()))
    lines += ["", f"Human queue `{report.config.human_queue}`: {queued} pairs ({parts}).", ""]
    if report.queue_labels:
        judged = report.judge_on_queue()
        lines += [
            "## The human queue against the judge",
            "",
            "The owner's labels on the queue the judge ordered (its own pairs, not a random "
            "sample: they measure the judge's calls in the zone, not the matcher's precision).",
            "",
            "| Why queued | Same villa | Not the same | Unsure |",
            "|---|---|---|---|",
            *(
                f"| {stratum.removeprefix('judge:')} | {c['match']} | {c['non_match']} | "
                f"{c['unsure']} |"
                for stratum, c in sorted(report.queue_labels.items())
            ),
            "",
            "Judge's suggested matches confirmed: "
            f"{_pct(judged['suggested_match_precision'])}; vetoes confirmed: "
            f"{_pct(judged['veto_precision'])} (unsure labels left out).",
            "",
        ]
    return "\n".join(lines)


def _policy_json(r: PolicyResult) -> dict[str, object]:
    b = r.clusters.bcubed
    return {
        "name": r.name,
        "rule": describe_policy(r.policy),
        "configured": r.configured,
        "meets_bar": r.meets_bar,
        "metrics": r.pairwise.metrics.as_dict(),
        "waiting": r.pairwise.waiting,
        "bcubed": (
            {"precision": b.precision, "recall": b.recall, "f1": b.f1, "elements": b.elements}
            if b
            else None
        ),
    }


def _evaluation_json(evaluation: LabelledEvaluation) -> dict[str, object]:
    m = evaluation.matcher
    point = m.operating_point
    return {
        "labelled": m.labelled,
        "queued": m.queued,
        "unsure": m.unsure.as_dict(),
        "blocking_recall": m.blocking_recall.as_dict(),
        "gold_threshold": point.as_dict() if point else None,
        "curve": [c.as_dict() for c in m.curve],
        "labels_by_stratum": m.labels_by_stratum,
        "policies": [_policy_json(r) for r in evaluation.policies],
    }


def _villas_json(counts: VillaCounts) -> dict[str, object]:
    return {
        "labels": counts.labels,
        "rule": describe_policy(counts.policy),
        "listings": counts.listings,
        "villas": counts.villas,
        "multi_platform": counts.multi_platform,
        "applied": counts.applied,
        "refused": counts.refused,
    }


def to_artifact(report: ErReport) -> dict[str, object]:
    run = report.revised.matcher.run
    return envelope(
        "er-eval",
        COMMAND,
        report.generated_at,
        {
            "match_run": run.id if run else None,
            "dataset_hash": run.dataset_hash if run else None,
            "queue": report.revised.matcher.queue,
            "labeler": report.revised.matcher.labeler,
            "revisions": len(report.revisions),
            "policy": describe_policy(report.config.policy),
            "previous_policy": describe_policy(PREVIOUS_POLICY),
        },
        {
            "revised": _evaluation_json(report.revised),
            "original": _evaluation_json(report.original),
            "revisions": [
                {
                    "pair": str(r.key),
                    "kind": _revision_kind(report, r),
                    "before": r.before.value,
                    "after": r.after.value,
                    "reason": r.reason,
                    "revised_by": r.revised_by,
                    "revised_at": r.revised_at.isoformat(),
                }
                for r in report.revisions
            ],
            "villas_now": _villas_json(report.villas_now),
            "villas_before": _villas_json(report.villas_before),
            "ablations": [
                {
                    "name": a.name,
                    "at_bar": a.operating_point.as_dict() if a.operating_point else None,
                    "best_f1": a.best_f1.as_dict() if a.best_f1 else None,
                }
                for a in report.ablations
            ],
            "candidates": {"total": report.candidates, "blocked": report.blocked},
            "judge_verdicts": dict(sorted(report.verdicts.items())),
            "human_queue": dict(sorted(report.queue.items())),
            "human_queue_labels": {
                k: dict(sorted(v.items())) for k, v in sorted(report.queue_labels.items())
            },
            "judge_on_human_queue": {k: v.as_dict() for k, v in report.judge_on_queue().items()},
        },
    )
