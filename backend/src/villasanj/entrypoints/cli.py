"""Command-line entrypoint (``villasanj ...``) for jobs and operations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Annotated

import typer

from villasanj.catalog.application.coverage import MeasureScenarioCoverage
from villasanj.catalog.application.places import MeasurePlaceResolution
from villasanj.catalog.application.reports import PhotoPipelineReport, RegionalInventory
from villasanj.catalog.domain.listing import ListingId
from villasanj.catalog.infrastructure.gazetteer_file import load_gazetteer
from villasanj.catalog.infrastructure.repositories import (
    PgCoverageQuery,
    PgPhotoStatsQuery,
    PgPlaceNameQuery,
)
from villasanj.discovery.application.hypotheses import render_markdown
from villasanj.entity_resolution.application.evaluation import EvaluationReport
from villasanj.entity_resolution.application.labeling import QueueExists
from villasanj.entity_resolution.domain.evaluation import Interval
from villasanj.entrypoints.container import Container, build_container
from villasanj.ingestion.application.capture import CAPTURE_KINDS, ScenarioCapture
from villasanj.ingestion.application.errors import CrawlError, SourceBlocked
from villasanj.ingestion.domain.pages import PageKind, PageRequest
from villasanj.ingestion.infrastructure.stats import PgCrawlStatsQuery
from villasanj.pricing.domain.quote import Quote, StayRequest
from villasanj.shared.application.jobs import JobStatus
from villasanj.shared.application.llm.smoke import LLMSmokeCheck
from villasanj.shared.domain.money import MoneyRange
from villasanj.shared.domain.stay import DateRange, GuestCount
from villasanj.shared.infrastructure.llm.models_snapshot import (
    compact_snapshot,
    fetch_models,
    write_snapshot,
)
from villasanj.shared.infrastructure.scenarios import load_scenarios
from villasanj.shared.infrastructure.settings import Settings

HYPOTHESIS_WINDOW_DAYS = 75  # jabama shows ~76 days of calendar

app = typer.Typer(no_args_is_help=True, add_completion=False)
llm_app = typer.Typer(no_args_is_help=True, help="LLM gateway operations.")
crawl_app = typer.Typer(no_args_is_help=True, help="Polite crawling (ADR-0008, ADR-0011).")
catalog_app = typer.Typer(no_args_is_help=True, help="Build the catalog from stored snapshots.")
pricing_app = typer.Typer(no_args_is_help=True, help="All-in quotes from stored observations.")
er_app = typer.Typer(no_args_is_help=True, help="Entity resolution: candidates, gold set, eval.")
app.add_typer(llm_app, name="llm")
app.add_typer(crawl_app, name="crawl")
app.add_typer(catalog_app, name="catalog")
app.add_typer(pricing_app, name="pricing")
app.add_typer(er_app, name="er")

DEFAULT_SMOKE_BUDGET_USD = "0.05"


@app.command()
def health() -> None:
    """Check database, blob store and LLM provider; exit 1 if anything is down."""

    async def run(container: Container) -> bool:
        report = await container.health()
        typer.echo(report.summary())
        return report.ok

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@llm_app.command("smoke")
def llm_smoke(
    dry_run: Annotated[bool, typer.Option(help="Estimate cost without calling the API.")] = False,
    budget_usd: Annotated[str, typer.Option(help="Job budget in USD.")] = DEFAULT_SMOKE_BUDGET_USD,
    fallbacks: Annotated[bool, typer.Option(help="Also check each fallback model.")] = True,
) -> None:
    """One tiny structured call per task route (and fallback model)."""

    async def run(container: Container) -> bool:
        check = LLMSmokeCheck(container.llm.client, container.llm.routing, fallbacks)
        if dry_run:
            report = await container.llm.dry_run.estimate(check.plan())
            for line in report.lines:
                typer.echo(
                    f"{line.task:<22} {line.model:<24} calls={line.calls} "
                    f"cached={line.cache_hits} expected=${line.expected_usd:.6f} "
                    f"worst=${line.worst_case_usd:.6f}"
                )
            typer.echo(
                f"TOTAL calls={report.calls} cached={report.cache_hits} "
                f"expected=${report.expected_usd:.6f} worst=${report.worst_case_usd:.6f}"
            )
            return True
        ctx = await container.jobs.start(
            "llm_smoke", Decimal(budget_usd), {"fallbacks": str(fallbacks)}
        )
        outcomes = await check.run(ctx)
        for outcome in outcomes:
            state = "ok" if outcome.ok else f"FAIL({outcome.error})"
            typer.echo(
                f"{outcome.task:<22} {outcome.model:<24} {state:<24} "
                f"${outcome.cost_usd:.6f}{' (cache)' if outcome.cache_hit else ''}"
            )
        spent = await container.ledger.spent_usd(ctx.job_id)
        all_ok = all(outcome.ok for outcome in outcomes)
        await container.jobs.finish(ctx.job_id, JobStatus.SUCCEEDED if all_ok else JobStatus.FAILED)
        typer.echo(f"job={ctx.job_id} spent=${spent:.6f}")
        return all_ok

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@llm_app.command("refresh-models")
def llm_refresh_models() -> None:
    """Refresh the model price/capability snapshot from AvalAI /v1/models (free)."""
    settings = Settings()
    if settings.avalai_api_key is None:
        typer.echo("AVALAI_API_KEY is not set", err=True)
        raise typer.Exit(code=1)
    models = asyncio.run(fetch_models(settings.avalai_api_key, settings.avalai_base_url))
    source = f"{settings.avalai_base_url.rstrip('/')}/models"
    write_snapshot(settings.models_path, compact_snapshot(models, datetime.now(UTC), source))
    typer.echo(f"wrote {settings.models_path}")


@crawl_app.command("probe")
def crawl_probe(
    platform: Annotated[str, typer.Argument(help="Registered platform slug.")],
    urls: Annotated[list[str], typer.Argument(help="URLs to fetch once each (live).")],
    kind: Annotated[PageKind, typer.Option(help="Page kind recorded on the snapshot.")] = (
        PageKind.OTHER
    ),
) -> None:
    """Fetch individual pages politely (robots.txt, pacing) and store them as snapshots."""

    async def run(container: Container) -> bool:
        fetcher = container.fetcher(live=True)
        all_ok = True
        for url in urls:
            request = PageRequest(platform, kind, url)
            try:
                page = await fetcher.fetch(request)
            except CrawlError as error:
                typer.echo(f"{url} -> {type(error).__name__}: {error}")
                all_ok = False
                continue
            snapshot_id = await container.store_page(page)
            typer.echo(
                f"{url} -> {page.status} {page.header('content-type') or '?'} "
                f"{len(page.body)}B snapshot={snapshot_id}"
            )
            all_ok = all_ok and page.ok
        return all_ok

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@crawl_app.command("run")
def crawl_run(
    platform: Annotated[str, typer.Argument(help="Registered platform slug.")],
    live: Annotated[bool, typer.Option(help="Allow network requests (default: replay).")] = False,
    max_requests: Annotated[int, typer.Option(min=1, help="Stop after this many fetches.")] = 50,
    kinds: Annotated[
        list[PageKind] | None, typer.Option("--kind", help="Only these page kinds (repeatable).")
    ] = None,
    after_block: Annotated[
        bool, typer.Option(help="The owner decided to crawl again after a block.")
    ] = False,
) -> None:
    """Crawl a platform's frontier for the configured region."""

    async def run(container: Container) -> bool:
        try:
            report = await container.crawler(platform, live).run(
                container.crawl.region, max_requests, live, kinds, after_block
            )
        except SourceBlocked as error:
            typer.echo(str(error), err=True)
            return False
        typer.echo(
            f"run={report.run_id} fetched={report.fetched} skipped={report.skipped} "
            f"retried={report.retried} gave_up={report.gave_up} discovered={report.discovered} "
            f"discover_errors={report.discover_errors} stop={report.stop_reason}"
        )
        return not report.stop_reason.startswith("blocked")

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@crawl_app.command("capture")
def crawl_capture(
    live: Annotated[
        bool, typer.Option(help="Queue and fetch (default: show the plan only).")
    ] = False,
    max_requests: Annotated[int, typer.Option(min=1, help="Per platform.")] = 10_000,
) -> None:
    """Re-observe calendars and prices of every known listing, all platforms in one window.

    Do not run it while a gold set is being labelled: it changes the catalog under the labels.
    """

    async def run(container: Container) -> bool:
        platforms = sorted(container.crawl.adapters)
        capture = ScenarioCapture(container.crawl.frontier, container.crawl.policy, container.clock)
        for plan in [await capture.plan(p) for p in platforms]:
            hosts = " ".join(f"{h}={n}" for h, n in sorted(plan.requests_by_host.items()))
            hours = plan.estimated.total_seconds() / 3600
            typer.echo(
                f"{plan.platform}: requests={plan.requests} ({hosts}) estimated={hours:.1f}h"
            )
        if not live:
            typer.echo("plan only: nothing was queued (add --live to capture)")
            return True
        queued = await capture.requeue(platforms)
        typer.echo("queued: " + " ".join(f"{p}={n}" for p, n in queued.items()))
        results = await asyncio.gather(
            *(
                container.crawler(p, live=True).run(
                    container.crawl.region, max_requests, True, CAPTURE_KINDS
                )
                for p in platforms
            ),
            return_exceptions=True,
        )
        ok = True
        for platform, result in zip(platforms, results, strict=True):
            if isinstance(result, BaseException):
                typer.echo(f"{platform}: {result}", err=True)
                ok = False
                continue
            typer.echo(f"{platform}: fetched={result.fetched} stop={result.stop_reason}")
            ok = ok and not result.stop_reason.startswith("blocked")
            await container.catalog_ingest().run(platform)
        await _echo_coverage(container)
        return ok

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@crawl_app.command("metrics")
def crawl_metrics(
    runs: Annotated[int, typer.Option(min=0, help="Latest runs to list.")] = 6,
) -> None:
    """Traffic per host (with measured pacing), queue progress and recent runs (zero network)."""

    async def run(container: Container) -> bool:
        stats = PgCrawlStatsQuery(container.engine)
        typer.echo("traffic (run requests; robots.txt checks excluded):")
        for t in await stats.traffic():
            statuses = " ".join(f"{s}:{n}" for s, n in t.statuses.items())
            typer.echo(
                f"  {t.platform:<7} {t.host:<16} responses={t.responses} [{statuses}] "
                f"stored={t.stored_bytes / 1e6:.0f}MB interval min={t.min_interval_s}s "
                f"median={t.median_interval_s}s {t.first:%m-%d %H:%M}..{t.last:%H:%M}Z"
            )
        typer.echo("queue:")
        for p in await stats.progress():
            statuses = " ".join(f"{s}={n}" for s, n in p.statuses.items())
            reasons = f" reasons={p.reasons}" if p.reasons else ""
            typer.echo(f"  {p.platform:<7} {p.kind:<9} {statuses}{reasons}")
        if runs:
            typer.echo("runs:")
            for r in await stats.runs(runs):
                end = f"{r.finished_at:%H:%M}Z" if r.finished_at else "-"
                typer.echo(
                    f"  {r.platform:<7} {r.status:<11} {r.started_at:%m-%d %H:%M}Z..{end} "
                    f"fetched={r.fetched if r.fetched is not None else '-'} "
                    f"stop={r.stop_reason or '-'}"
                )
        return True

    asyncio.run(_with_container(run))


@crawl_app.command("status")
def crawl_status(platform: Annotated[str, typer.Argument(help="Platform slug.")]) -> None:
    """Frontier counts per status."""

    async def run(container: Container) -> bool:
        counts = await container.crawl.frontier.counts(platform)
        typer.echo(" ".join(f"{status}={count}" for status, count in sorted(counts.items())))
        return True

    asyncio.run(_with_container(run))


@catalog_app.command("ingest")
def catalog_ingest(
    platforms: Annotated[
        list[str] | None, typer.Argument(help="Platforms to (re)parse; default: all registered.")
    ] = None,
) -> None:
    """(Re)build listings and calendar observations from snapshots. Zero network requests."""

    async def run(container: Container) -> bool:
        ingest = container.catalog_ingest()
        for platform in platforms or sorted(container.crawl.adapters):
            report = await ingest.run(platform)
            total = await container.listings.count(platform)
            typer.echo(
                f"{platform}: snapshots={report.snapshots} saved={report.saved} "
                f"superseded={report.superseded} not_listing={report.not_listing} "
                f"failed={report.failed} listings_in_catalog={total}"
            )
        return True

    asyncio.run(_with_container(run))


@catalog_app.command("enqueue-photos")
def catalog_enqueue_photos(
    platform: Annotated[str, typer.Argument(help="Platform slug.")],
    per_listing: Annotated[int, typer.Option(min=1, help="Photos per listing.")] = 5,
    listing_limit: Annotated[int | None, typer.Option(help="Only the first N listings.")] = None,
) -> None:
    """Queue listing photos for polite fetching (then: crawl run --kind photo)."""

    async def run(container: Container) -> bool:
        added = await container.enqueue_photos().run(platform, per_listing, listing_limit)
        typer.echo(f"{platform}: queued {added} new photo requests")
        return True

    asyncio.run(_with_container(run))


@catalog_app.command("fingerprint-photos")
def catalog_fingerprint_photos(
    platforms: Annotated[
        list[str] | None, typer.Argument(help="Platforms to fingerprint; default: all registered.")
    ] = None,
    force: Annotated[bool, typer.Option(help="Recompute photos already fingerprinted.")] = False,
) -> None:
    """Compute perceptual hashes for new photo snapshots (zero network requests)."""

    async def run(container: Container) -> bool:
        fingerprint = container.fingerprint_photos()
        for platform in platforms or sorted(container.crawl.adapters):
            report = await fingerprint.run(platform, force)
            typer.echo(
                f"{platform}: snapshots={report.snapshots} already_done={report.already_done} "
                f"fingerprinted={report.fingerprinted} "
                f"unreadable={report.unreadable} unattributed={report.unattributed}"
            )
        return True

    asyncio.run(_with_container(run))


@catalog_app.command("coverage")
def catalog_coverage() -> None:
    """Share of listings whose stored calendars cover every night of each stay scenario."""

    async def run(container: Container) -> bool:
        await _echo_coverage(container)
        return True

    asyncio.run(_with_container(run))


@catalog_app.command("photo-report")
def catalog_photo_report() -> None:
    """Photo pipeline per platform: selected, downloaded, failed, hashed, embedded, stored."""

    async def run(container: Container) -> bool:
        report = PhotoPipelineReport(
            PgCrawlStatsQuery(container.engine), PgPhotoStatsQuery(container.engine)
        )
        for r in await report.run(container.image_embedder().model_id):
            failed = sum(r.failed_responses.values())
            typer.echo(
                f"{r.platform:<7} listings={r.listings} referenced={r.referenced} "
                f"selected={r.selected} downloaded={r.downloaded} failed={failed} "
                f"failed_or_skipped={r.failed_or_skipped} unfinished={r.unfinished} "
                f"coverage={r.coverage:.1%} fingerprinted={r.fingerprinted} "
                f"embedded={r.embedded} stored={r.stored_bytes / 1e9:.2f}GB"
            )
            if r.reasons:
                typer.echo(f"    reasons: {r.reasons}")
        return True

    asyncio.run(_with_container(run))


@catalog_app.command("inventory")
def catalog_inventory() -> None:
    """Listings per platform: discovered, fetched, parsed, in the region, with key fields."""

    async def run(container: Container) -> bool:
        inventory = RegionalInventory(
            PgCrawlStatsQuery(container.engine), container.listings, container.crawl.region
        )
        for r in await inventory.run(sorted(container.crawl.adapters)):
            responses = " ".join(f"{s}:{n}" for s, n in r.responses.items())
            typer.echo(
                f"{r.platform:<7} discovered={r.discovered} responses=[{responses}] "
                f"parsed={r.parsed} in_region={r.in_region} with_location={r.with_location} "
                f"with_capacity={r.with_capacity} with_base_price={r.with_base_price}"
            )
        return True

    asyncio.run(_with_container(run))


@catalog_app.command("places")
def catalog_places() -> None:
    """How many listings the gazetteer places at locality or city level (zero network requests)."""

    async def run(container: Container) -> bool:
        gazetteer = load_gazetteer(container.settings.gazetteer_path)
        measure = MeasurePlaceResolution(PgPlaceNameQuery(container.engine), gazetteer)
        typer.echo(f"gazetteer: {len(gazetteer)} places")
        for platform in sorted(container.crawl.adapters):
            r = await measure.run(platform)
            typer.echo(
                f"{platform:<8} listings={r.listings} locality_text={r.with_locality_text} "
                f"locality={r.locality_resolved} city_only={r.city_resolved} "
                f"unresolved={r.unresolved}"
            )
            for name, count in r.top_unresolved:
                typer.echo(f"    unresolved locality text ({count}): {name}")
        return True

    asyncio.run(_with_container(run))


@catalog_app.command("embed-photos")
def catalog_embed_photos(
    platforms: Annotated[
        list[str] | None, typer.Argument(help="Platforms; default: all registered.")
    ] = None,
) -> None:
    """Embed every not-yet-embedded photo image with the local image model (zero network)."""

    async def run(container: Container) -> bool:
        chosen = platforms or sorted(container.crawl.adapters)
        report = await container.embed_photos().run(chosen)
        typer.echo(
            f"model={report.model_id} images={report.images} "
            f"already_embedded={report.already_embedded} embedded={report.embedded} "
            f"unreadable={report.unreadable}"
        )
        return True

    asyncio.run(_with_container(run))


@er_app.command("match")
def er_match() -> None:
    """Blocking + evidence + rule scores for all platforms; replaces the current candidates."""

    async def run(container: Container) -> bool:
        platforms = sorted(container.crawl.adapters)
        result = await (await container.match_listings(platforms)).run(platforms)
        counts = " ".join(f"{k}={v}" for k, v in sorted(result.counts.items()))
        typer.echo(f"run={result.id} dataset={result.dataset_hash[:12]} {counts}")
        return True

    asyncio.run(_with_container(run))


@er_app.command("queue")
def er_queue(
    name: Annotated[str, typer.Option(help="Queue name (used once).")] = "gold-v1",
) -> None:
    """Draw the stratified labelling queue from the current candidates."""

    async def run(container: Container) -> bool:
        try:
            items = await container.build_label_queue().run(name)
        except QueueExists:
            typer.echo(f"queue {name!r} already exists; choose a new name", err=True)
            return False
        strata: dict[str, int] = {}
        for item in items:
            strata[item.stratum] = strata.get(item.stratum, 0) + 1
        typer.echo(f"queue={name} pairs={len(items)}")
        for stratum, count in sorted(strata.items()):
            size = next(i.stratum_size for i in items if i.stratum == stratum)
            typer.echo(f"  {stratum:<22} {count:>4} of {size}")
        return True

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@er_app.command("evaluate")
def er_evaluate(
    queue: Annotated[str, typer.Option(help="Queue name.")] = "gold-v1",
    labeler: Annotated[str, typer.Option(help="Whose labels.")] = "owner",
) -> None:
    """Precision/recall with Wilson 95% intervals against the labels (zero network)."""

    async def run(container: Container) -> bool:
        report = await container.evaluate_matcher().run(queue, labeler)
        typer.echo(_render_evaluation(report))
        return True

    asyncio.run(_with_container(run))


@er_app.command("hypotheses")
def er_hypotheses(
    queue: Annotated[str, typer.Option(help="Gold-set queue for the operating point.")] = "gold-v1",
    labeler: Annotated[str, typer.Option(help="Whose labels.")] = "owner",
    threshold: Annotated[
        float | None, typer.Option(help="Override the operating point (marked provisional).")
    ] = None,
    out: Annotated[Path, typer.Option(help="Markdown report path.")] = Path("../reports"),
) -> None:
    """H1-H3 report from the current matches, pricing and calendars (zero network)."""

    async def run(container: Container) -> bool:
        evaluation = await container.evaluate_matcher().run(queue, labeler)
        point = evaluation.operating_point
        notes = []
        if threshold is not None:
            chosen = threshold
            notes.append(f"Threshold {threshold:g} was set by hand, not chosen from the gold set.")
        elif point is not None:
            chosen = point.threshold
        else:
            typer.echo("no operating point yet (label the gold set, or pass --threshold)", err=True)
            return False
        latest = await container.candidates().latest_run()
        start = (latest.created_at if latest else datetime.now(UTC)).date()
        report = await container.hypothesis_report().run(
            sorted(container.crawl.adapters),
            chosen,
            load_scenarios(container.settings.scenarios_path),
            DateRange(start, start + timedelta(days=HYPOTHESIS_WINDOW_DAYS)),
            precision=point.precision if point and threshold is None else None,
            recall=point.recall if point and threshold is None else None,
        )
        report = replace(report, notes=tuple(notes))
        path = out / f"hypotheses-{start.isoformat()}.md" if out.suffix != ".md" else out
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(report), encoding="utf-8")
        typer.echo(f"pairs={report.pairs} report={path}")
        return True

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


def _interval(interval: Interval) -> str:
    if interval.estimate is None:
        return "n/a"
    return f"{interval.estimate:.1%} [{interval.low:.1%}, {interval.high:.1%}]"


def _render_evaluation(report: EvaluationReport) -> str:
    lines = [
        f"queue={report.queue} labeler={report.labeler} labelled={report.labelled}/{report.queued}"
        f" unsure={_interval(report.unsure)}",
        f"run={report.run.id if report.run else '-'} "
        f"dataset={report.run.dataset_hash[:12] if report.run else '-'}",
        f"blocking recall on gold matches: {_interval(report.blocking_recall)}",
    ]
    point = report.operating_point
    if point is None:
        lines.append("operating point: none meets precision >= 95% with lower bound >= 92%")
    else:
        lines.append(
            f"operating point: score >= {point.threshold:g} precision={_interval(point.precision)}"
            f" recall={_interval(point.recall)} tp={point.true_positives} "
            f"fp={point.false_positives} fn={point.false_negatives} tn={point.true_negatives}"
        )
    for metrics in report.curve:
        lines.append(
            f"  score >= {metrics.threshold:>4g}: precision={_interval(metrics.precision)} "
            f"recall={_interval(metrics.recall)}"
        )
    for stratum, counts in report.labels_by_stratum.items():
        lines.append(f"  {stratum:<22} {counts}")
    return "\n".join(lines)


@pricing_app.command("quote")
def pricing_quote(
    platform: Annotated[str, typer.Argument(help="Platform slug.")],
    external_id: Annotated[str, typer.Argument(help="The platform's listing id.")],
    check_in: Annotated[
        datetime | None, typer.Option(formats=["%Y-%m-%d"], help="Default: every scenario.")
    ] = None,
    check_out: Annotated[datetime | None, typer.Option(formats=["%Y-%m-%d"])] = None,
    guests: Annotated[int, typer.Option(min=1)] = 4,
) -> None:
    """Quote one listing for a stay, or for every scenario x group size (zero network)."""

    async def run(container: Container) -> bool:
        quotes = container.quotes()
        listing_id = ListingId(platform, external_id)
        if check_in and check_out:
            request = StayRequest(DateRange(check_in.date(), check_out.date()), GuestCount(guests))
            quote = await quotes.quote(listing_id, request)
            results = [quote] if quote else []
        else:
            scenarios = load_scenarios(container.settings.scenarios_path)
            results = await quotes.scenarios(listing_id, scenarios)
        if not results:
            typer.echo(f"{listing_id}: not in the catalog", err=True)
            return False
        for quote in results:
            typer.echo(_render_quote(quote))
        return True

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


def _toman(amount: MoneyRange) -> str:
    low = f"{amount.low.toman:,.0f}"
    if amount.high is None:
        return f">= {low} toman"
    if amount.is_exact:
        return f"{low} toman"
    return f"{low}-{amount.high.toman:,.0f} toman"


def _render_quote(quote: Quote) -> str:
    stay = quote.request.stay
    head = f"{stay.check_in}..{stay.check_out} x{quote.request.guests.value}: {quote.status}"
    total = f" total={_toman(quote.total)}" if quote.total else ""
    caveats = f" caveats={','.join(sorted(quote.caveats))}" if quote.caveats else ""
    seen = (
        f" observed={quote.newest_observation:%Y-%m-%d %H:%M}Z" if quote.newest_observation else ""
    )
    return f"{head}{total} source={quote.source}{caveats}{seen}"


async def _echo_coverage(container: Container) -> None:
    scenarios = load_scenarios(container.settings.scenarios_path)
    query = MeasureScenarioCoverage(PgCoverageQuery(container.engine))
    for row in await query.run(sorted(container.crawl.adapters), scenarios):
        spread = f"{row.spread.total_seconds() / 3600:.1f}h" if row.spread else "-"
        typer.echo(
            f"{row.platform:<8} {row.scenario:<8} covered={row.covered}/{row.listings} "
            f"({row.ratio:.1%}) observation_spread={spread}"
        )


async def _with_container[R](run: Callable[[Container], Awaitable[R]]) -> R:
    container = build_container()
    try:
        return await run(container)
    finally:
        await container.aclose()
