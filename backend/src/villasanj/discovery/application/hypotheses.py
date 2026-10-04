"""The M3 hypothesis report (H1 overlap, H2 price gaps, H3 hidden nights), built from the DB."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import ListingId
from villasanj.discovery.domain.hypotheses import (
    GapSummary,
    OverlapEstimate,
    PriceGap,
    compare_calendars,
    corrected_overlap,
    price_gap,
    summarize_gaps,
)
from villasanj.entity_resolution.application.ports import CandidateStore, MatchRun
from villasanj.entity_resolution.application.villas import (
    DecisionPolicy,
    JudgementStore,
    decide,
    describe_policy,
)
from villasanj.entity_resolution.domain.evaluation import Interval
from villasanj.entity_resolution.domain.pairs import PairKey
from villasanj.pricing.application.quotes import QuoteStays
from villasanj.pricing.domain.quote import StayRequest
from villasanj.shared.application.artifacts import envelope
from villasanj.shared.domain.stay import DateRange, StayScenario

DEFAULT_MAX_GAP = timedelta(hours=6)


@dataclass(frozen=True, slots=True)
class ScenarioGaps:
    scenario: str
    guests: int
    summary: GapSummary


@dataclass(frozen=True, slots=True)
class HypothesisReport:
    policy: DecisionPolicy  # the production decision policy that chose the matched pairs
    run: MatchRun | None
    listings: dict[str, int]  # per platform, in the catalog
    matched: dict[str, int]  # per platform, listings with a predicted cross-platform match
    pairs: int
    precision: Interval | None
    recall: Interval | None
    gaps: tuple[ScenarioGaps, ...]
    pairs_compared_across_scenarios: int
    pairs_where_cheaper_platform_flips: int
    nights_compared: int
    hidden_nights: int
    pairs_with_hidden_night: int
    max_gap: timedelta
    window: DateRange
    notes: tuple[str, ...] = field(default=())


class BuildHypothesisReport:
    def __init__(
        self,
        candidates: CandidateStore,
        listings: ListingReader,
        quotes: QuoteStays,
        judgements: JudgementStore | None = None,
    ) -> None:
        self._candidates = candidates
        self._listings = listings
        self._quotes = quotes
        self._judgements = judgements

    async def run(
        self,
        platforms: Sequence[str],
        policy: DecisionPolicy,
        scenarios: Sequence[StayScenario],
        window: DateRange,
        precision: Interval | None = None,
        recall: Interval | None = None,
        max_gap: timedelta = DEFAULT_MAX_GAP,
    ) -> HypothesisReport:
        pairs = await self._matched_pairs(policy)
        counts = {p: len(await self._listings.listings(p)) for p in platforms}
        matched: Counter[str] = Counter()
        for key in pairs:
            matched.update([key.left.platform, key.right.platform])

        gaps: list[ScenarioGaps] = []
        cheaper_by_pair: dict[PairKey, set[str | None]] = {}
        for scenario in scenarios:
            for guests in scenario.guests:
                request = StayRequest(scenario.stay, guests)
                found: list[PriceGap] = []
                for key in pairs:
                    left = await self._quotes.quote(key.left, request)
                    right = await self._quotes.quote(key.right, request)
                    gap = price_gap(left, right) if left and right else None
                    if gap is not None:
                        found.append(gap)
                        cheaper_by_pair.setdefault(key, set()).add(gap.cheaper_platform)
                gaps.append(ScenarioGaps(scenario.slug, guests.value, summarize_gaps(found)))
        compared_pairs = [seen for seen in cheaper_by_pair.values() if seen]
        flips = sum(1 for seen in compared_pairs if len(seen - {None}) > 1)

        nights = hidden = with_hidden = 0
        for key in pairs:
            comparison = compare_calendars(
                await self._listings.calendar(key.left, window),
                await self._listings.calendar(key.right, window),
                max_gap,
            )
            nights += comparison.compared
            hidden += len(comparison.hidden)
            with_hidden += bool(comparison.hidden)

        return HypothesisReport(
            policy=policy,
            run=await self._candidates.latest_run(),
            listings=counts,
            matched=dict(sorted(matched.items())),
            pairs=len(pairs),
            precision=precision,
            recall=recall,
            gaps=tuple(gaps),
            pairs_compared_across_scenarios=len(compared_pairs),
            pairs_where_cheaper_platform_flips=flips,
            nights_compared=nights,
            hidden_nights=hidden,
            pairs_with_hidden_night=with_hidden,
            max_gap=max_gap,
            window=window,
        )

    async def _matched_pairs(self, policy: DecisionPolicy) -> list[PairKey]:
        """The policy's machine matches, at most one partner per listing, strongest first
        (ADR-0009: <= 1 per platform). The owner's labels are not applied: the report measures
        the matcher, whose precision and recall correct H1."""
        rows = [
            (c.key, c.score.value, c.blocked)
            for c in await self._candidates.current()
            if c.score is not None
        ]
        judged = await self._judgements.all() if self._judgements else []
        decided = decide(rows, judged, policy).matches
        taken: set[ListingId] = set()
        chosen = []
        for decision in sorted(decided, key=lambda d: (-d.weight, d.key)):
            key = decision.key
            if key.left in taken or key.right in taken:
                continue
            taken.update((key.left, key.right))
            chosen.append(key)
        return chosen


def _corrected(report: HypothesisReport) -> OverlapEstimate | None:
    p, r = report.precision, report.recall
    if p is None or r is None or p.estimate is None or r.estimate is None:
        return None
    cap = min(report.listings.values(), default=0)
    return corrected_overlap(
        report.pairs, (p.estimate, p.low, p.high), (r.estimate, r.low, r.high), cap
    )


def _interval(value: Interval | None) -> str:
    if value is None or value.estimate is None:
        return "not measured"
    return f"{value.estimate:.1%} (95% CI {value.low:.1%}–{value.high:.1%})"


def render_markdown(report: HypothesisReport) -> str:
    run = report.run
    lines = [
        "# M3 hypothesis report",
        "",
        f"Generated from the database. Match run `{run.id if run else '-'}`, dataset "
        f"`{run.dataset_hash[:12] if run else '-'}`. "
        f"Decision policy: {describe_policy(report.policy)}.",
        f"Matcher precision {_interval(report.precision)}, recall {_interval(report.recall)} "
        "(the policy end to end on the gold set, labels not applied).",
        "",
        "## H1 — overlap between platforms",
        "",
        f"Predicted cross-platform matches: **{report.pairs}** (at most one partner per listing).",
        "",
        "| Platform | Listings | With a predicted match | Share |",
        "|---|---|---|---|",
    ]
    for platform, total in report.listings.items():
        hits = report.matched.get(platform, 0)
        share = f"{hits / total:.1%}" if total else "-"
        lines.append(f"| {platform} | {total} | {hits} | {share} |")
    corrected = _corrected(report)
    if corrected is not None:
        total = sum(report.listings.values())

        def villas(pairs: float) -> str:
            return f"{pairs / (total - pairs):.1%}"

        shares = ", ".join(
            f"{platform} {corrected.estimate / n:.1%} ({corrected.low / n:.1%}–"
            f"{corrected.high / n:.1%})"
            for platform, n in report.listings.items()
            if n
        )
        lines += [
            "",
            f"Corrected for the matcher (real ≈ predicted × precision / recall): about "
            f"**{corrected.estimate:.0f}** real pairs (range {corrected.low:.0f}–"
            f"{corrected.high:.0f}, from the ends of the two Wilson intervals and capped by the "
            f"smaller platform; not itself a 95% interval). Listings with a partner: {shares}. "
            f"Distinct villas on both platforms: **{villas(corrected.estimate)}** of all villas "
            f"in the catalog (range {villas(corrected.low)}–{villas(corrected.high)}).",
        ]
    lines += [
        "",
        "Caveats: predicted matches include false positives (see precision) and miss pairs the "
        "matcher or the blocking did not find (see recall), so the shares are estimates, not "
        "counts of real villas. The crawl covers the Ramsar–Tonekabon region of two platforms; "
        "villas listed only on other platforms are not counted.",
        "",
        "## H2 — listed totals for the same villa and stay",
        "",
        "Totals are listed prices (nights + extra guests). Neither platform publishes its fees, "
        'so both sides are lower bounds ("≥ X") and the comparison excludes fees.',
        "",
        "| Scenario | Guests | Pairs bookable on both | Median higher/lower | p90 | Cheaper on |",
        "|---|---|---|---|---|---|",
    ]
    for item in report.gaps:
        s = item.summary
        cheaper = ", ".join(f"{k}: {v}" for k, v in s.cheaper.items()) or "-"
        median = f"{s.median_ratio:.2f}×" if s.median_ratio else "-"
        p90 = f"{s.p90_ratio:.2f}×" if s.p90_ratio else "-"
        lines.append(
            f"| {item.scenario} | {item.guests} | {s.pairs} | {median} | {p90} | {cheaper} |"
        )
    lines += [
        "",
        f"The cheaper platform changes between scenarios for "
        f"**{report.pairs_where_cheaper_platform_flips}** of "
        f"{report.pairs_compared_across_scenarios} pairs compared in more than one scenario.",
        "",
        "## H3 — hidden nights",
        "",
        f"Nights from {report.window.check_in} to {report.window.check_out} observed on both "
        f"platforms less than {report.max_gap.total_seconds() / 3600:g} h apart: "
        f"**{report.nights_compared}**. Free on one platform and taken on the other: "
        f"**{report.hidden_nights}**"
        + (
            f" ({report.hidden_nights / report.nights_compared:.1%})"
            if report.nights_compared
            else ""
        )
        + f", in {report.pairs_with_hidden_night} of {report.pairs} pairs.",
        "",
        "Some platforms do not say whether a taken night is booked or closed by the host "
        "(stored as unavailable), so a hidden night means *shown free elsewhere*, not *bookable*.",
        "",
    ]
    lines += [f"- {note}" for note in report.notes]
    return "\n".join(lines).rstrip() + "\n"


def to_artifact(
    report: HypothesisReport, generated_at: datetime, command: str
) -> dict[str, object]:
    """The report as data (reports/hypotheses-*.json) for the documentation portal."""
    run = report.run
    corrected = _corrected(report)
    total = sum(report.listings.values())
    return envelope(
        "hypotheses",
        command,
        generated_at,
        {
            "match_run": run.id if run else None,
            "dataset_hash": run.dataset_hash if run else None,
            "policy": describe_policy(report.policy),
            "window": [report.window.check_in.isoformat(), report.window.check_out.isoformat()],
            "notes": list(report.notes),
        },
        {
            "precision": report.precision.as_dict() if report.precision else None,
            "recall": report.recall.as_dict() if report.recall else None,
            "h1": {
                "listings": report.listings,
                "matched": report.matched,
                "pairs": report.pairs,
                "corrected_pairs": (
                    {"estimate": corrected.estimate, "low": corrected.low, "high": corrected.high}
                    if corrected
                    else None
                ),
                "villas_on_both_share": (
                    {
                        "estimate": corrected.estimate / (total - corrected.estimate),
                        "low": corrected.low / (total - corrected.low),
                        "high": corrected.high / (total - corrected.high),
                    }
                    if corrected
                    else None
                ),
            },
            "h2": [
                {
                    "scenario": g.scenario,
                    "guests": g.guests,
                    "pairs": g.summary.pairs,
                    "median_ratio": g.summary.median_ratio,
                    "p90_ratio": g.summary.p90_ratio,
                    "cheaper": g.summary.cheaper,
                }
                for g in report.gaps
            ],
            "h2_flips": {
                "pairs": report.pairs_compared_across_scenarios,
                "flips": report.pairs_where_cheaper_platform_flips,
            },
            "h3": {
                "nights_compared": report.nights_compared,
                "hidden_nights": report.hidden_nights,
                "pairs_with_hidden_night": report.pairs_with_hidden_night,
                "pairs": report.pairs,
                "max_gap_hours": report.max_gap.total_seconds() / 3600,
            },
        },
    )
