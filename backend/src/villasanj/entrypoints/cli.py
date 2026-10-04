"""Command-line entrypoint (``villasanj ...``) for jobs and operations."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
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
from villasanj.catalog.domain.gazetteer import PlaceKind as GazetteerKind
from villasanj.catalog.domain.gazetteer import place_key
from villasanj.catalog.domain.listing import ListingId
from villasanj.catalog.domain.review import RatingPrior
from villasanj.catalog.infrastructure.gazetteer_file import load_gazetteer
from villasanj.catalog.infrastructure.repositories import (
    PgCoverageQuery,
    PgPhotoStatsQuery,
    PgPlaceNameQuery,
)
from villasanj.discovery.application.explanation import (
    ExplainChoice,
    Source,
    explain_first,
    planning_request,
)
from villasanj.discovery.application.explanation_eval import EvaluateExplanations
from villasanj.discovery.application.hypotheses import render_markdown
from villasanj.discovery.application.hypotheses import to_artifact as hypotheses_artifact
from villasanj.discovery.application.understanding import UnderstandQuery
from villasanj.discovery.application.understanding_eval import EvaluateUnderstanding
from villasanj.discovery.domain.dates import (
    DateExpression,
    HolidayKind,
    InvalidDateExpression,
    NextHoliday,
    Nowruz,
    Weekend,
    describe_fa,
    resolve,
)
from villasanj.discovery.infrastructure.eval_cases import load_cases
from villasanj.enrichment.application.claim_extraction import ReadClaimsWithLLM
from villasanj.enrichment.application.claim_labels import ClaimQueueExists
from villasanj.enrichment.application.claims import MeasureClaimParsing
from villasanj.enrichment.application.consistency import h4_artifact, render_h4_markdown
from villasanj.enrichment.application.features import MeasureFeatureClaims
from villasanj.enrichment.application.photo_tags import EvaluatePhotoTags, PhotoQueueExists
from villasanj.enrichment.application.summary_review import SummaryQueueExists
from villasanj.enrichment.application.truth import CheckSeaClaims
from villasanj.enrichment.domain.claim_eval import ClaimCounts
from villasanj.enrichment.infrastructure.coast import PgCoastDistanceStore
from villasanj.enrichment.infrastructure.features import load_amenity_map
from villasanj.entity_resolution.application.evaluation import EvaluateAblations, EvaluationReport
from villasanj.entity_resolution.application.judge import JudgeInput
from villasanj.entity_resolution.application.judge_eval import to_artifact as judge_eval_artifact
from villasanj.entity_resolution.application.labeling import QueueExists
from villasanj.entity_resolution.application.report import render_markdown as render_er_report
from villasanj.entity_resolution.application.report import to_artifact as er_report_artifact
from villasanj.entity_resolution.application.revisions import ReviseLabels
from villasanj.entity_resolution.application.villas import DecisionPolicy, EvaluateDecisions
from villasanj.entity_resolution.domain.evaluation import Interval, wilson
from villasanj.entity_resolution.infrastructure.revisions_file import load_revisions
from villasanj.entrypoints.api.app import create_app
from villasanj.entrypoints.container import Container, build_container
from villasanj.ingestion.application.capture import CAPTURE_KINDS, ScenarioCapture
from villasanj.ingestion.application.errors import CrawlError, SourceBlocked
from villasanj.ingestion.domain.pages import PageKind, PageRequest
from villasanj.ingestion.infrastructure.stats import PgCrawlStatsQuery
from villasanj.pricing.domain.quote import Quote, StayRequest
from villasanj.shared.application.errors import LLMError
from villasanj.shared.application.jobs import JobStatus
from villasanj.shared.application.llm.smoke import LLMSmokeCheck
from villasanj.shared.application.llm.types import LLMTask
from villasanj.shared.domain.jalali import iran_today
from villasanj.shared.domain.money import MoneyRange
from villasanj.shared.domain.stay import DateRange, GuestCount
from villasanj.shared.infrastructure.db.repositories import PgLLMSpendQuery
from villasanj.shared.infrastructure.llm.models_snapshot import (
    compact_snapshot,
    fetch_models,
    write_snapshot,
)
from villasanj.shared.infrastructure.scenarios import load_scenarios
from villasanj.shared.infrastructure.settings import Settings


def _write_report(path: Path, markdown: str, artifact: dict[str, object]) -> None:
    """A generated report: markdown for people, JSON beside it for the documentation portal."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    path.with_suffix(".json").write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


HYPOTHESIS_WINDOW_DAYS = 75  # jabama shows ~76 days of calendar
FEW_VOTES = 5  # below this a listing's own average is mostly noise

app = typer.Typer(no_args_is_help=True, add_completion=False)
llm_app = typer.Typer(no_args_is_help=True, help="LLM gateway operations.")
crawl_app = typer.Typer(no_args_is_help=True, help="Polite crawling (ADR-0008, ADR-0011).")
catalog_app = typer.Typer(no_args_is_help=True, help="Build the catalog from stored snapshots.")
pricing_app = typer.Typer(no_args_is_help=True, help="All-in quotes from stored observations.")
er_app = typer.Typer(no_args_is_help=True, help="Entity resolution: candidates, gold set, eval.")
api_app = typer.Typer(no_args_is_help=True, help="HTTP API tooling.")
enrichment_app = typer.Typer(no_args_is_help=True, help="Listing claims and their truth check.")
discovery_app = typer.Typer(no_args_is_help=True, help="Search: dates, intent, ranking.")
app.add_typer(llm_app, name="llm")
app.add_typer(crawl_app, name="crawl")
app.add_typer(catalog_app, name="catalog")
app.add_typer(pricing_app, name="pricing")
app.add_typer(er_app, name="er")
app.add_typer(api_app, name="api")
app.add_typer(enrichment_app, name="enrichment")
app.add_typer(discovery_app, name="discovery")

DEFAULT_SMOKE_BUDGET_USD = "0.05"


@api_app.command("openapi")
def api_openapi(
    out: Annotated[Path, typer.Option(help="Where to write the OpenAPI JSON.")] = Path(
        "../frontend/src/lib/api/openapi.json"
    ),
) -> None:
    """Write the API's OpenAPI schema (the frontend's types are generated from it)."""
    schema = create_app(build_container).openapi()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8")
    typer.echo(f"wrote {out} ({len(schema['paths'])} paths)")


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


@llm_app.command("spend")
def llm_spend() -> None:
    """LLM spend per task and model from the ledger, and what is left under the project cap."""

    async def run(container: Container) -> bool:
        rows = await PgLLMSpendQuery(container.engine).by_task_and_model()
        for r in rows:
            typer.echo(
                f"{r.task:<20} {r.model:<24} calls={r.calls} cache_hits={r.cache_hits} "
                f"failed={r.failed} in={r.input_tokens} out={r.output_tokens} "
                f"(reasoning {r.reasoning_tokens}) estimated_usage={r.estimated} "
                f"${r.cost_usd:.6f}"
            )
        total = sum((r.cost_usd for r in rows), Decimal(0))
        cap = container.llm.routing.project_budget_usd
        typer.echo(f"TOTAL ${total:.6f} of the ${cap} project cap (${cap - total:.6f} left)")
        return True

    asyncio.run(_with_container(run))


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


@crawl_app.command("requeue")
def crawl_requeue(
    platform: Annotated[str, typer.Argument(help="Platform slug.")],
    kinds: Annotated[list[PageKind], typer.Option("--kind", help="Page kinds (repeatable).")],
) -> None:
    """Queue finished pages of these kinds again, e.g. search pages to find new listings.

    Discovery de-duplicates by request, so pages already fetched are not fetched again unless
    their own kind was re-queued. Then run `crawl run <platform> --live --kind ...`.
    """

    async def run(container: Container) -> bool:
        container.adapter(platform)  # unknown platforms fail here
        count = await container.crawl.frontier.requeue(platform, kinds, container.clock.now())
        typer.echo(f"{platform}: re-queued {count} pages ({', '.join(k.value for k in kinds)})")
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


@catalog_app.command("reviews")
def catalog_reviews() -> None:
    """Stored reviews per platform and the Bayesian prior used to rate listings with few votes."""

    async def run(container: Container) -> bool:
        for platform in sorted(container.crawl.adapters):
            listings = await container.listings.listings(platform)
            counts = await container.listings.review_counts(platform)
            prior = RatingPrior.from_listings(listings)
            few = [x for x in listings if x.rating_count and x.rating_count < FEW_VOTES]
            rated = sum(bool(x.rating_count) for x in listings)
            mean = f"{prior.mean:.2f}" if prior else "-"
            typer.echo(
                f"{platform:<7} listings={len(listings)} rated={rated} "
                f"stored_reviews={counts['reviews']} on_listings={counts['listings']} "
                f"with_text={counts['with_text']} host_replied={counts['host_replied']} "
                f"prior_mean={mean} listings_with_<{FEW_VOTES}_votes={len(few)}"
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


@enrichment_app.command("claims")
def enrichment_claims() -> None:
    """How many published distance claims the parser understands, per platform (zero network)."""

    async def run(container: Container) -> bool:
        measure = MeasureClaimParsing(container.listings)
        for platform in sorted(container.crawl.adapters):
            r = await measure.run(platform)
            targets = " ".join(f"{k}={v}" for k, v in r.by_target.items()) or "-"
            modes = " ".join(f"{k}={v}" for k, v in r.by_mode.items()) or "-"
            typer.echo(
                f"{platform:<7} listings={r.listings} with_claims={r.with_claims} "
                f"claims={r.claims} parsed={r.parsed} coverage={r.coverage:.1%}"
            )
            typer.echo(f"    targets[{targets}] modes[{modes}]")
            for text, count in r.top_unparsed:
                typer.echo(f"    unparsed wording ({count}): {text}")
            for text, count in r.top_other_targets:
                typer.echo(f"    target without a category ({count}): {text}")
        return True

    asyncio.run(_with_container(run))


@enrichment_app.command("features")
def enrichment_features() -> None:
    """Feature claims in descriptions against each listing's own amenity list (zero network)."""

    async def run(container: Container) -> bool:
        measure = MeasureFeatureClaims(
            container.listings, load_amenity_map(container.settings.features_path)
        )
        for platform in sorted(container.crawl.adapters):
            r = await measure.run(platform)
            typer.echo(f"{platform:<7} listings={r.listings} with_description={r.with_description}")
            for row in r.rows:
                claims = " ".join(f"{k}={v}" for k, v in sorted(row.claims.items())) or "-"
                agreement = " ".join(f"{k}={v}" for k, v in sorted(row.agreement.items())) or "-"
                typer.echo(
                    f"  {row.feature:<10} amenity_yes={row.amenity_yes} "
                    f"amenity_no={row.amenity_no} claims[{claims}] vs_amenities[{agreement}]"
                )
                for d in row.disagreements:
                    typer.echo(f"      {d.listing} {d.claim.polarity}: …{d.context}…")
        return True

    asyncio.run(_with_container(run))


@enrichment_app.command("coastline-load")
def enrichment_coastline_load() -> None:
    """Load the exported OSM coastline (infra/osm/prepare.sh) into PostGIS."""

    async def run(container: Container) -> bool:
        path = container.settings.geo.osm_dir / "coastline.geojsonseq"
        lines = path.read_text(encoding="utf-8").splitlines()
        loaded = await container.coastline().load(lines)
        typer.echo(f"dataset={container.settings.geo.dataset} coastline_ways={loaded}")
        return loaded > 0

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@enrichment_app.command("claim-queue")
def enrichment_claim_queue(
    name: Annotated[str, typer.Option(help="Queue name, e.g. claims-v1.")] = "claims-v1",
    n: Annotated[int, typer.Option(min=1, max=200, help="Descriptions to label.")] = 60,
) -> None:
    """Draw the descriptions whose feature claims the owner labels (M9 criterion 1), once."""

    async def run(container: Container) -> bool:
        try:
            items = await container.claim_label_queue().run(name, n)
        except ClaimQueueExists:
            typer.echo(f"queue {name} exists: queues are drawn once")
            return False
        typer.echo(f"queue={name} descriptions={len(items)} label at /label/claims")
        return bool(items)

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@enrichment_app.command("read-claims")
def enrichment_read_claims(
    dry_run: Annotated[bool, typer.Option(help="Price the calls without making them.")] = False,
    budget_usd: Annotated[str, typer.Option(help="Job budget in USD.")] = "3.00",
) -> None:
    """The LLM pass for feature claims the rules miss, over every description (M9; cached)."""

    async def run(container: Container) -> bool:
        job = container.read_all_claims()
        if dry_run:
            for platform in sorted(container.crawl.adapters):
                descriptions = await job.descriptions(platform)
                plan = ReadClaimsWithLLM(container.llm.client).plan(descriptions)
                estimate = await container.llm.dry_run.estimate(plan)
                typer.echo(
                    f"{platform:<7} descriptions={len(descriptions)} calls={estimate.calls} "
                    f"cache_hits={estimate.cache_hits} expected=${estimate.expected_usd:.4f} "
                    f"worst_case=${estimate.worst_case_usd:.4f}"
                )
            return True
        ctx = await container.jobs.start("read_claims", Decimal(budget_usd), {})
        status = JobStatus.FAILED
        try:
            for platform in sorted(container.crawl.adapters):
                r = await job.run(platform, ctx)
                typer.echo(
                    f"{platform:<7} descriptions={r.descriptions} claims={r.claims} "
                    f"dropped_quotes={r.dropped} retried={r.retried} failed={r.failed} "
                    f"cost=${r.cost_usd:.4f}"
                )
            status = JobStatus.SUCCEEDED
        finally:
            await container.jobs.finish(ctx.job_id, status)
        return True

    asyncio.run(_with_container(run))


@enrichment_app.command("claims-eval")
def enrichment_claims_eval(
    queue: Annotated[str, typer.Option(help="Queue name.")] = "claims-v1",
    labeler: Annotated[str, typer.Option(help="Who labelled.")] = "owner",
    llm: Annotated[bool, typer.Option(help="Also score the rules plus the LLM residue.")] = False,
    dry_run: Annotated[bool, typer.Option(help="Price the LLM pass without calling.")] = False,
    budget_usd: Annotated[str, typer.Option(help="Job budget in USD.")] = "0.20",
) -> None:
    """Claim-level precision and recall against the owner's labels (M9 criterion 1)."""

    async def run(container: Container) -> bool:
        evaluate = container.claim_eval(with_llm=llm)
        if llm and dry_run:
            descriptions = await evaluate.descriptions(queue, labeler)
            plan = ReadClaimsWithLLM(container.llm.client).plan(descriptions)
            estimate = await container.llm.dry_run.estimate(plan)
            typer.echo(
                f"descriptions={len(descriptions)} calls={estimate.calls} "
                f"cache_hits={estimate.cache_hits} expected=${estimate.expected_usd:.6f} "
                f"worst_case=${estimate.worst_case_usd:.6f} (a retry is at most one more each)"
            )
            return True
        ctx = await container.jobs.start("claims_eval", Decimal(budget_usd), {}) if llm else None
        r = await evaluate.run(queue, labeler, ctx)
        if ctx is not None:
            await container.jobs.finish(ctx.job_id, JobStatus.SUCCEEDED)

        def line(name: str, c: ClaimCounts) -> str:
            p = wilson(c.true_positive, c.true_positive + c.false_positive)
            q = wilson(c.true_positive, c.true_positive + c.false_negative)
            return (
                f"  {name:<10} tp={c.true_positive} fp={c.false_positive} fn={c.false_negative} "
                f"precision={_interval(p)} recall={_interval(q)}"
            )

        typer.echo(f"queue={r.queue} labelled={r.labelled}/{r.total} (targets: P>=90%, R>=80%)")
        for title, score in (("rules", r.score), ("rules+llm", r.with_llm)):
            if score is None:
                continue
            typer.echo(f"{title}:")
            typer.echo(line("all", score.total))
            for feature, counts in sorted(score.per_feature.items()):
                typer.echo(line(feature.value, counts))
        if r.with_llm is not None:
            typer.echo(f"llm quotes dropped={r.llm_dropped} cost=${r.llm_cost:.6f}")
        return True

    asyncio.run(_with_container(run))


@enrichment_app.command("summary-queue")
def enrichment_summary_queue(
    name: Annotated[str, typer.Option(help="Queue name, e.g. summaries-v1.")] = "summaries-v1",
    n: Annotated[int, typer.Option(min=1, max=100, help="Listings to review.")] = 20,
) -> None:
    """Draw the listings whose review summaries the owner judges (M10 criterion 3), once."""

    async def run(container: Container) -> bool:
        try:
            items = await container.summary_review_queue().run(name, n)
        except SummaryQueueExists:
            typer.echo(f"queue {name} exists: queues are drawn once")
            return False
        typer.echo(f"queue={name} listings={len(items)} review at /label/summaries")
        return bool(items)

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@enrichment_app.command("summary-review-eval")
def enrichment_summary_review_eval(
    queue: Annotated[str, typer.Option(help="Queue name.")] = "summaries-v1",
    labeler: Annotated[str, typer.Option(help="Who reviewed.")] = "owner",
) -> None:
    """Faithful summaries among those the owner reviewed (target: at least 18 of 20)."""

    async def run(container: Container) -> bool:
        r = await container.summary_review_eval().run(queue, labeler)
        target = {None: "not all reviewed yet", True: "met", False: "NOT met"}[r.meets_target]
        typer.echo(
            f"queue={r.queue} reviewed={r.reviewed}/{r.total} faithful={r.faithful} "
            f"target(>=18/20)={target}"
        )
        for listing_id, note in r.unfaithful:
            typer.echo(f"  UNFAITHFUL {listing_id}: {note or '-'}")
        return True

    asyncio.run(_with_container(run))


@enrichment_app.command("places-load")
def enrichment_places_load() -> None:
    """Load the exported OSM places (infra/osm/prepare.sh) that distance claims name."""

    async def run(container: Container) -> bool:
        path = container.settings.geo.osm_dir / "poi.geojsonseq"
        lines = path.read_text(encoding="utf-8").splitlines()
        gazetteer = load_gazetteer(container.settings.gazetteer_path)
        cities = {
            place_key(name)
            for place in gazetteer.of_kind(GazetteerKind.CITY)
            for name in (place.name_fa, *place.aliases)
        }
        loaded = await container.places().load(lines, cities)
        typer.echo(f"dataset={container.settings.geo.dataset} places={loaded}")
        return loaded > 0

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@enrichment_app.command("places")
def enrichment_places() -> None:
    """Distance from every listing to the nearest mapped place of each kind."""

    async def run(container: Container) -> bool:
        measure = container.place_distances()
        for platform in sorted(container.crawl.adapters):
            r = await measure.run(platform)
            kinds = " ".join(f"{k}={v}" for k, v in sorted(r.measured.items())) or "-"
            typer.echo(f"{platform:<7} with_location={r.with_location} measured[{kinds}]")
        return True

    asyncio.run(_with_container(run))


@enrichment_app.command("truth-distances")
def enrichment_truth_distances() -> None:
    """Every published distance claim against the map, per target (zero network)."""

    async def run(container: Container) -> bool:
        check = container.distance_truth()
        for platform in sorted(container.crawl.adapters):
            r = await check.run(platform)
            share = wilson(r.listings_contradicted, r.listings_judged)
            h4 = (
                f" ({share.estimate:.1%}, 95% CI {share.low:.1%}-{share.high:.1%})"
                if share.estimate is not None
                else ""
            )
            typer.echo(
                f"{platform:<7} listings_judged={r.listings_judged} "
                f"listings_with_a_contradiction={r.listings_contradicted}{h4}"
            )
            by_target: dict[str, list[str]] = {}
            for key, count in sorted(r.verdicts.items()):
                target, verdict = key.split(":")
                by_target.setdefault(target, []).append(f"{verdict}={count}")
            for target, parts in by_target.items():
                typer.echo(f"    {target:<15} {' '.join(parts)}")
        return True

    asyncio.run(_with_container(run))


@enrichment_app.command("h4")
def enrichment_h4(
    out: Annotated[Path | None, typer.Option(help="Also write the report here (markdown).")] = None,
) -> None:
    """H4 (M9 crit. 4): listings with a location or amenity claim CONTRADICTED by the map or
    INCONSISTENT_ACROSS_PLATFORMS within their villa (zero network; villas from `er villas`)."""

    def ci(share: Interval) -> str:
        if share.estimate is None:
            return "n/a"
        return f"{share.estimate:.1%} (95% CI {share.low:.1%}-{share.high:.1%})"

    async def run(container: Container) -> bool:
        rows = await container.h4().run(sorted(container.crawl.adapters))
        if out is not None:
            now = container.clock.now()
            command = f"uv run villasanj enrichment h4 --out {out}"
            _write_report(out, render_h4_markdown(rows, now), h4_artifact(rows, now, command))
            typer.echo(f"wrote {out} and {out.with_suffix('.json')}")
        for r in rows:
            typer.echo(
                f"{r.platform:<7} listings={r.listings} in_two_platform_villas="
                f"{r.in_multi_platform_villas} judged={r.judged} contradicted={r.contradicted} "
                f"inconsistent={r.inconsistent} either={r.either}"
            )
            typer.echo(f"    H4 share: {ci(r.share)}")
            typer.echo(f"    inconsistent of compared ({r.compared}): {ci(r.inconsistent_share)}")
            for kind, count in r.kinds.most_common():
                typer.echo(f"    {kind:<22} {count}")
        return True

    asyncio.run(_with_container(run))


@enrichment_app.command("coast")
def enrichment_coast() -> None:
    """Distance from every listing to the coastline, with its range over the blur circle."""

    async def run(container: Container) -> bool:
        measure = container.coast_distances()
        for platform in sorted(container.crawl.adapters):
            r = await measure.run(platform)
            typer.echo(
                f"{platform:<7} listings={r.listings} with_location={r.with_location} "
                f"measured={r.measured} radius_assumed={r.radius_assumed}"
            )
        return True

    asyncio.run(_with_container(run))


@enrichment_app.command("truth-sea")
def enrichment_truth_sea() -> None:
    """Published distance-to-the-sea claims against the measured coast distance (zero network)."""

    async def run(container: Container) -> bool:
        check = CheckSeaClaims(container.listings, PgCoastDistanceStore(container.engine))
        for platform in sorted(container.crawl.adapters):
            r = await check.run(platform)
            verdicts = " ".join(f"{k}={v}" for k, v in sorted(r.verdicts.items())) or "-"
            assumed = " ".join(
                f"{k}={v}" for k, v in sorted(r.verdicts_with_assumed_radius.items())
            )
            modes = " ".join(f"{k}={v}" for k, v in sorted(r.by_mode.items()))
            share = r.contradicted_share()
            h4 = (
                f" ({share.estimate:.1%}, 95% CI {share.low:.1%}-{share.high:.1%})"
                if share.estimate is not None
                else ""
            )
            typer.echo(
                f"{platform:<7} listings_with_sea_claim={r.listings_with_claim} "
                f"no_distance={r.without_distance} "
                f"listings_with_a_contradiction={r.listings_contradicted}{h4} verdicts[{verdicts}]"
            )
            typer.echo(f"    by_mode[{modes}]")
            if assumed:
                typer.echo(f"    with an assumed radius[{assumed}]")
            for v in r.contradicted:
                low, high = v.assessment.measured_m
                claim_low, claim_high = v.assessment.claimed_m
                typer.echo(
                    f"    CONTRADICTED {v.listing_id}: «{v.claim.target_text}: …» "
                    f"mode={v.claim.mode} claims {claim_low:.0f}..{claim_high or 0:.0f} m, "
                    f"measured {low:.0f}..{high:.0f} m"
                )
        return True

    asyncio.run(_with_container(run))


@enrichment_app.command("tag-photos")
def enrichment_tag_photos() -> None:
    """Zero-shot tag scores for every stored photo, once per image and model (local SigLIP 2)."""

    async def run(container: Container) -> bool:
        r = await container.tag_photos().run(sorted(container.crawl.adapters))
        typer.echo(
            f"model={r.model} images={r.images} already_scored={r.already_scored} "
            f"scored={r.scored} unreadable={r.unreadable}"
        )
        return True

    asyncio.run(_with_container(run))


@enrichment_app.command("photo-queue")
def enrichment_photo_queue(
    name: Annotated[str, typer.Option(help="Queue name (drawn once).")] = "photos-v1",
) -> None:
    """Draw the stratified photo-tag labelling queue (per tag: top, middle and rest)."""

    async def run(container: Container) -> bool:
        try:
            items = await container.photo_tag_queue().run(name)
        except PhotoQueueExists:
            typer.echo(f"queue {name} already exists (queues are drawn once)", err=True)
            return False
        strata = Counter(i.stratum for i in items)
        typer.echo(f"queue={name} photos={len(items)}")
        for stratum, count in sorted(strata.items()):
            typer.echo(f"  {stratum:<18} {count}")
        return True

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@enrichment_app.command("photo-tags-eval")
def enrichment_photo_tags_eval(
    queue: Annotated[str, typer.Option(help="Labelled queue.")] = "photos-v1",
    labeler: Annotated[str, typer.Option(help="Whose labels.")] = "owner",
    save: Annotated[
        bool, typer.Option(help="Store the thresholds: photo tags become evidence.")
    ] = False,
) -> None:
    """M9 criterion 2: per tag, the threshold reaching 85% precision, or "not used"."""

    async def run(container: Container) -> bool:
        evaluation = await EvaluatePhotoTags(
            container.photo_tags(), container.photo_queues(), container.photo_tagger().model_id
        ).run(queue, labeler)
        typer.echo(f"model={evaluation.model} labelled_photos={evaluation.labelled_photos}")
        for t in evaluation.thresholds:
            if t.threshold is None or t.precision is None or t.recall is None:
                typer.echo(f"  {t.tag:<10} NOT USED (positives={t.positives}/{t.labelled})")
                continue
            typer.echo(
                f"  {t.tag:<10} threshold={t.threshold:.4f} "
                f"precision={t.precision.estimate:.1%} "
                f"[{t.precision.low:.1%}, {t.precision.high:.1%}] "
                f"recall={t.recall.estimate:.1%} positives={t.positives}/{t.labelled}"
            )
        if save:
            await container.photo_thresholds().replace(
                evaluation.model, evaluation.thresholds, queue, container.clock.now()
            )
            used = sum(t.threshold is not None for t in evaluation.thresholds)
            typer.echo(f"saved {used} thresholds for {evaluation.model}")
        return True

    asyncio.run(_with_container(run))


@enrichment_app.command("summarize")
def enrichment_summarize(
    platform: Annotated[str, typer.Argument(help="Platform slug.")],
    external_ids: Annotated[list[str], typer.Argument(help="Listing ids on that platform.")],
    dry_run: Annotated[bool, typer.Option(help="Price the calls without making them.")] = False,
    budget_usd: Annotated[str, typer.Option(help="Job budget in USD.")] = "0.05",
) -> None:
    """Pros and cons of a listing's reviews, each point citing its reviews (M10 groundwork)."""

    async def run(container: Container) -> bool:
        summaries = container.review_summaries()
        listing_ids = [ListingId(platform, e) for e in external_ids]
        if dry_run:
            report = await container.llm.dry_run.estimate(await summaries.requests(listing_ids))
            typer.echo(
                f"listings={len(listing_ids)} calls={report.calls} "
                f"cache_hits={report.cache_hits} expected=${report.expected_usd:.6f} "
                f"worst_case=${report.worst_case_usd:.6f} (a retry adds at most one call each)"
            )
            return True
        ctx = await container.jobs.start("review_summary", Decimal(budget_usd), {})
        for listing_id in listing_ids:
            summary = await summaries.for_listing(listing_id, ctx)
            typer.echo(f"listing {listing_id}:")
            if summary is None:
                typer.echo("  too few reviews with text: no summary")
                continue
            typer.echo(
                f"  reviews={summary.reviews_given} retried={summary.retried} "
                f"dropped={summary.dropped} models={','.join(summary.models)}"
            )
            for side, points in (("+", summary.pros), ("-", summary.cons)):
                for point in points:
                    cited = ",".join(r.review_id for r in point.reviews)
                    single = " (one opinion)" if point.single_opinion else ""
                    typer.echo(f"  {side} {point.text}{single} [{cited}]")
        await container.jobs.finish(ctx.job_id, JobStatus.SUCCEEDED)
        typer.echo(f"job={ctx.job_id} spent=${await container.ledger.spent_usd(ctx.job_id):.6f}")
        return True

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@discovery_app.command("search")
def discovery_search(
    query: Annotated[str, typer.Argument(help="A Persian search query.")],
    top: Annotated[int, typer.Option(min=1, help="How many results to print.")] = 10,
    explain: Annotated[bool, typer.Option(help="Explain the first result (one more call).")] = True,
    budget_usd: Annotated[str, typer.Option(help="Job budget in USD.")] = "0.02",
) -> None:
    """Query to ranked listings with reasons, and why the first fits (M8/M10 groundwork)."""

    async def run(container: Container) -> bool:
        ctx = await container.jobs.start("search", Decimal(budget_usd), {})
        result = await container.search().run(query, ctx)
        await container.jobs.finish(ctx.job_id, JobStatus.SUCCEEDED)
        intent = result.understanding.intent
        typer.echo(f"intent: {intent.model_dump_json(exclude_none=True)}")
        if result.dates is not None:
            typer.echo(
                f"dates: {describe_fa(result.dates.window)} flexible={result.dates.flexible}"
            )
        places = ",".join(p.slug for p in result.places) or "-"
        typer.echo(f"places={places} unresolved={','.join(result.unresolved_places) or '-'}")
        if result.missing:
            typer.echo(f"ask the user for: {','.join(result.missing)}")
        if result.ranking is None:
            return True
        ranking = result.ranking
        excluded = " ".join(f"{k}={v}" for k, v in sorted(ranking.excluded.items())) or "-"
        typer.echo(f"kept={len(ranking.results)} excluded[{excluded}]")
        if ranking.budget_readings:
            readings = " ".join(f"{k}={v}" for k, v in ranking.budget_readings.items())
            typer.echo(f"budget basis is ambiguous: ask ({readings})")
        for r in ranking.results[:top]:
            listing = result.listings[r.candidate.id]
            total = r.candidate.total
            parts = " ".join(f"{c.component}={c.points:.2f}" for c in r.contributions)
            cautions = ",".join(sorted(r.warnings)) or "-"
            price = _toman(total) if total else "no price"
            typer.echo(
                f"  {r.confirmed}/{len(intent.features)} {r.score:.3f} {r.candidate.id:<16} "
                f"{price:<24} [{parts}] cautions={cautions} | {listing.title_norm[:40]}"
            )
        if explain:
            names = {p: a.profile.display_name for p, a in container.crawl.adapters.items()}
            why = await explain_first(
                ExplainChoice(container.llm.client), result, names, container.clock.now(), ctx
            )
            if why is not None:
                typer.echo(f"why ({why.source}, retried={why.retried}): {why.rendered.text}")
        spent = await container.ledger.spent_usd(ctx.job_id)
        typer.echo(f"job={ctx.job_id} spent=${spent:.6f}")
        return True

    asyncio.run(_with_container(run))


@discovery_app.command("eval-explanations")
def discovery_eval_explanations(
    path: Annotated[Path, typer.Argument(help="JSON lines of queries (expected intents unused).")],
    dry_run: Annotated[bool, typer.Option(help="Price the calls without making them.")] = False,
    budget_usd: Annotated[str, typer.Option(help="Job budget in USD.")] = "0.20",
    show_texts: Annotated[bool, typer.Option(help="Print every explanation for review.")] = False,
) -> None:
    """M10 criteria 2 and 4: LLM text vs template fallback, retries and latency per model."""

    async def run(container: Container) -> bool:
        queries = [c.query for c in load_cases(path)]
        if dry_run:
            understand = UnderstandQuery(container.llm.client, queries)
            requests = [*understand.plan(), *(planning_request(q) for q in queries)]
            estimate = await container.llm.dry_run.estimate(requests)
            typer.echo(
                f"queries={len(queries)} calls={estimate.calls} "
                f"cache_hits={estimate.cache_hits} expected=${estimate.expected_usd:.6f} "
                f"worst_case=${estimate.worst_case_usd:.6f} (explanations priced from a "
                f"representative slot set; a retry is at most one more call each)"
            )
            return True
        names = {p: a.profile.display_name for p, a in container.crawl.adapters.items()}
        ctx = await container.jobs.start("eval_explanations", Decimal(budget_usd), {})
        evaluate = EvaluateExplanations(
            container.search(), ExplainChoice(container.llm.client), names, container.clock
        )
        report = await evaluate.run(queries, ctx)
        await container.jobs.finish(ctx.job_id, JobStatus.SUCCEEDED)
        llm, template = report.share(Source.LLM), report.share(Source.TEMPLATE)
        typer.echo(
            f"queries={len(report.cases)} explained={len(report.explained)} "
            f"llm_text={llm if llm is None else f'{llm:.1%}'} "
            f"template_fallback={template if template is None else f'{template:.1%}'} "
            f"retried={report.retried} failed={report.failures} cost=${report.cost_usd:.6f}"
        )
        for model, (calls, p50, p95) in report.latency_ms().items():
            typer.echo(f"  latency {model}: uncached={calls} p50={p50}ms p95={p95}ms")
        for case in report.cases:
            if case.failure is not None:
                typer.echo(f"  FAILED {case.failure}: {case.query}")
            elif case.source is Source.TEMPLATE:
                typer.echo(f"  TEMPLATE: {case.query}")
            if show_texts and case.source is not None:
                retried = " (retried)" if case.retried else ""
                typer.echo(f"  [{case.source.value}{retried}] {case.query}\n      {case.text}")
        return True

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@discovery_app.command("eval-understanding")
def discovery_eval_understanding(
    path: Annotated[Path, typer.Argument(help="JSON lines of query + expected intent.")],
    dry_run: Annotated[bool, typer.Option(help="Price the calls without making them.")] = False,
    budget_usd: Annotated[str, typer.Option(help="Job budget in USD.")] = "0.10",
) -> None:
    """M8 criterion 1: slot accuracy, invented numbers and latency per model on a case file."""

    async def run(container: Container) -> bool:
        cases = load_cases(path)
        understand = UnderstandQuery(container.llm.client, [c.query for c in cases])
        if dry_run:
            estimate = await container.llm.dry_run.estimate(understand.plan())
            typer.echo(
                f"cases={len(cases)} calls={estimate.calls} cache_hits={estimate.cache_hits} "
                f"expected=${estimate.expected_usd:.6f} "
                f"worst_case=${estimate.worst_case_usd:.6f}"
            )
            return True
        ctx = await container.jobs.start("eval_understanding", Decimal(budget_usd), {})
        report = await EvaluateUnderstanding(understand).run(cases, ctx)
        await container.jobs.finish(ctx.job_id, JobStatus.SUCCEEDED)
        typer.echo(
            f"cases={len(report.cases)} slot_accuracy={report.slot_accuracy:.1%} "
            f"exact_match={report.exact_match:.1%} invented_numbers={report.invented} "
            f"failed_cases={report.failures} "
            f"retried={sum(c.retried for c in report.cases)} "
            f"dropped_fields={sum(len(c.dropped) for c in report.cases)} "
            f"cost=${report.cost_usd:.6f}"
        )
        for name, (right, seen) in sorted(report.per_slot.items()):
            typer.echo(f"  {name:<18} {right}/{seen}")
        for model, (calls, p50, p95) in report.latency_ms().items():
            typer.echo(f"  latency {model}: uncached={calls} p50={p50}ms p95={p95}ms")
        for case in report.cases:
            if case.wrong:
                typer.echo(f"  WRONG {case.query}")
                for name in case.wrong:
                    typer.echo(
                        f"      {name}: expected={case.expected.get(name)} got={case.got.get(name)}"
                    )
        return True

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@discovery_app.command("drive-times")
def discovery_drive_times() -> None:
    """Free-flow drive times from the origin to every listing (needs the routing profile up)."""

    async def run(container: Container) -> bool:
        compute = container.drive_times()
        for platform in sorted(container.crawl.adapters):
            r = await compute.run(platform)
            typer.echo(
                f"{platform:<7} listings={r.listings} with_location={r.with_location} "
                f"routed={r.routed} pin_unroutable_but_circle_routed={r.center_unroutable}"
            )
        return True

    asyncio.run(_with_container(run))


@discovery_app.command("holidays")
def discovery_holidays(
    days: Annotated[int, typer.Option(help="How many days ahead to list.")] = 120,
) -> None:
    """Days off the date resolver knows, with sources, and how common expressions resolve."""

    async def run(container: Container) -> bool:
        today = iran_today(container.clock.now())
        calendar = await container.holiday_calendar().run(today)
        horizon = calendar.known_until or "none (no observed platform flags)"
        typer.echo(f"today={today} lunar holidays known until {horizon}")
        for offset in range(days):
            day = today + timedelta(days=offset)
            for h in calendar.holidays_on(day):
                if h.kind is not HolidayKind.WEEKLY:
                    typer.echo(f"  {day} {h.kind:<8} {h.name_fa or '-'} [{h.source}]")
        expressions: list[tuple[str, DateExpression]] = [
            ("this weekend", Weekend()),
            ("next weekend", Weekend(1)),
            ("next holiday", NextHoliday()),
            ("Nowruz", Nowruz()),
        ]
        for label, expression in expressions:
            r = resolve(expression, today, calendar)
            caveats = ",".join(sorted(r.caveats)) or "-"
            typer.echo(
                f"  {label:<13} {r.window.check_in}..{r.window.check_out} "
                f"flexible={r.flexible} caveats={caveats} | {describe_fa(r.window)}"
            )
        return True

    asyncio.run(_with_container(run))


@discovery_app.command("understand")
def discovery_understand(
    queries: Annotated[list[str], typer.Argument(help="Persian search queries.")],
    dry_run: Annotated[bool, typer.Option(help="Price the calls without making them.")] = False,
    budget_usd: Annotated[str, typer.Option(help="Job budget in USD.")] = "0.05",
) -> None:
    """Turn queries into verified search intents and resolve their dates (M8 groundwork)."""

    async def run(container: Container) -> bool:
        understand = UnderstandQuery(container.llm.client, queries)
        if dry_run:
            report = await container.llm.dry_run.estimate(understand.plan())
            typer.echo(
                f"calls={report.calls} cache_hits={report.cache_hits} "
                f"expected=${report.expected_usd:.6f} worst_case=${report.worst_case_usd:.6f} "
                "(a retry adds at most one call per query)"
            )
            return True
        today = iran_today(container.clock.now())
        calendar = await container.holiday_calendar().run(today)
        ctx = await container.jobs.start("query_understanding", Decimal(budget_usd), {})
        for query in queries:
            result = await understand.run(query, ctx)
            typer.echo(f"query: {query}")
            typer.echo(f"  intent: {result.intent.model_dump_json(exclude_none=True)}")
            typer.echo(
                f"  retried={result.retried} dropped={','.join(result.dropped) or '-'} "
                f"models={','.join(result.models)} guests={result.intent.guests}"
            )
            expression = result.intent.dates.expression() if result.intent.dates else None
            if expression is not None:
                try:
                    r = resolve(expression, today, calendar, result.intent.nights)
                except InvalidDateExpression as error:
                    typer.echo(f"  dates: not resolvable ({error})")
                else:
                    caveats = ",".join(sorted(r.caveats)) or "-"
                    typer.echo(
                        f"  dates: {r.window.check_in}..{r.window.check_out} "
                        f"flexible={r.flexible} caveats={caveats} | {describe_fa(r.window)}"
                    )
        await container.jobs.finish(ctx.job_id, JobStatus.SUCCEEDED)
        spent = await container.ledger.spent_usd(ctx.job_id)
        typer.echo(f"job={ctx.job_id} spent=${spent:.6f}")
        return True

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


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
        notes = []
        if threshold is not None:
            policy = DecisionPolicy(threshold)
            notes.append(f"Threshold {threshold:g} was set by hand, not chosen from the gold set.")
        else:
            policy = container.er_config().policy
        evaluation = await EvaluateDecisions(
            container.candidates(), container.labels(), container.judgements()
        ).run(policy, queue, labeler)
        metrics = evaluation.metrics
        latest = await container.candidates().latest_run()
        start = (latest.created_at if latest else datetime.now(UTC)).date()
        report = await container.hypothesis_report().run(
            sorted(container.crawl.adapters),
            policy,
            load_scenarios(container.settings.scenarios_path),
            DateRange(start, start + timedelta(days=HYPOTHESIS_WINDOW_DAYS)),
            precision=metrics.precision if threshold is None else None,
            recall=metrics.recall if threshold is None else None,
        )
        report = replace(report, notes=tuple(notes))
        path = out / f"hypotheses-{start.isoformat()}.md" if out.suffix != ".md" else out
        command = "uv run villasanj er hypotheses" + (
            f" --threshold {threshold}" if threshold else ""
        )
        _write_report(
            path,
            render_markdown(report),
            hypotheses_artifact(report, container.clock.now(), command),
        )
        typer.echo(f"pairs={report.pairs} report={path}")
        return True

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@er_app.command("judge")
def er_judge(
    low: Annotated[float, typer.Option(help="Lowest rule score of the gray zone.")],
    high: Annotated[float, typer.Option(help="Highest rule score of the gray zone.")],
    limit: Annotated[int, typer.Option(min=1, help="At most this many pairs.")] = 500,
    dry_run: Annotated[
        bool, typer.Option(help="Price the requests (the only mode for now).")
    ] = True,
) -> None:
    """Price LLM-judging the gray zone of the current candidates (zero calls).

    Live judging waits for the M5 bake-off on the gold set (model, thresholds, and whether the
    judge ships at all are decided there), so only --dry-run is accepted.
    """

    async def run(container: Container) -> bool:
        if not dry_run:
            typer.echo(
                "live judging is not enabled before the M5 bake-off; use --dry-run", err=True
            )
            return False
        candidates = [
            c
            for c in await container.candidates().current()
            if c.blocked
            and c.key.cross_platform
            and c.score is not None
            and c.evidence is not None
            and low <= c.score.value <= high
        ]
        candidates.sort(key=lambda c: (-(c.score.value if c.score else 0.0), c.key))
        inputs = [JudgeInput(c.key, c.evidence) for c in candidates[:limit] if c.evidence]
        report = await container.llm.dry_run.estimate(await container.judge().requests(inputs))
        typer.echo(
            f"gray zone [{low:g}, {high:g}]: {len(candidates)} pairs, priced {len(inputs)}: "
            f"calls={report.calls} cache_hits={report.cache_hits} "
            f"expected=${report.expected_usd:.4f} worst_case=${report.worst_case_usd:.4f}"
        )
        return True

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@er_app.command("judge-zone")
def er_judge_zone(
    low: Annotated[float, typer.Option(help="Lowest rule score judged.")],
    high: Annotated[float, typer.Option(help="Highest rule score judged.")],
    limit: Annotated[int, typer.Option(min=1, help="At most this many pairs.")] = 2000,
    dry_run: Annotated[bool, typer.Option(help="Price the calls without making them.")] = False,
    budget_usd: Annotated[str, typer.Option(help="Job budget in USD.")] = "5.00",
) -> None:
    """Judge the current candidates whose rule score is in [low, high] and store the verdicts."""

    async def run(container: Container) -> bool:
        done = {j.key for j in await container.judgements().all()}
        candidates = sorted(
            (
                c
                for c in await container.candidates().current()
                if c.blocked
                and c.key.cross_platform
                and c.score is not None
                and c.evidence is not None
                and low <= c.score.value <= high
                and c.key not in done
            ),
            key=lambda c: (-(c.score.value if c.score else 0.0), c.key),
        )
        inputs = [JudgeInput(c.key, c.evidence) for c in candidates[:limit] if c.evidence]
        if dry_run:
            estimate = await container.llm.dry_run.estimate(
                await container.judge().requests(inputs)
            )
            typer.echo(
                f"[{low:g}, {high:g}]: {len(candidates)} pairs not judged yet, "
                f"priced {len(inputs)}: "
                f"calls={estimate.calls} expected=${estimate.expected_usd:.4f} "
                f"worst_case=${estimate.worst_case_usd:.4f}"
            )
            return True
        ctx = await container.jobs.start("judge_zone", Decimal(budget_usd), {})
        counts: Counter[str] = Counter()
        failed = 0
        gate = asyncio.Semaphore(4)  # the er_judge route's concurrency
        judge, store = container.judge(), container.judgements()

        async def one(item: JudgeInput) -> None:
            nonlocal failed
            async with gate:
                try:
                    judged = await judge.run([item], ctx)
                except LLMError:
                    failed += 1
                    return
            await store.save(judged)  # saved as it goes: an interrupted run resumes
            counts.update(j.verdict.verdict for j in judged)

        await asyncio.gather(*(one(item) for item in inputs))
        await container.jobs.finish(ctx.job_id, JobStatus.SUCCEEDED)
        typer.echo(f"judged={sum(counts.values())} {dict(counts)} failed={failed}")
        return True

    asyncio.run(_with_container(run))


_POLICY_HELP = "Overrides config/er.toml."


def _er_policy(
    container: Container,
    threshold: float | None,
    judge_low: float | None,
    judge_high: float | None,
    judge_min_confidence: float | None,
    judge_merges: bool | None = None,
    judge_vetoes: bool | None = None,
) -> DecisionPolicy:
    base = container.er_config().policy
    return DecisionPolicy(
        base.threshold if threshold is None else threshold,
        base.judge_low if judge_low is None else judge_low,
        base.judge_high if judge_high is None else judge_high,
        base.judge_min_confidence if judge_min_confidence is None else judge_min_confidence,
        base.judge_merges if judge_merges is None else judge_merges,
        base.judge_vetoes if judge_vetoes is None else judge_vetoes,
    )


@er_app.command("villas")
def er_villas(
    threshold: Annotated[float | None, typer.Option(help=_POLICY_HELP)] = None,
    judge_low: Annotated[float | None, typer.Option(help=_POLICY_HELP)] = None,
    judge_high: Annotated[float | None, typer.Option(help=_POLICY_HELP)] = None,
    judge_min_confidence: Annotated[float | None, typer.Option(help=_POLICY_HELP)] = None,
    labels: Annotated[bool, typer.Option(help="Apply the owner's labels.")] = True,
) -> None:
    """Cluster the match decisions into canonical villas (<= 1 listing per platform); pairs the
    judge was unsure about join the human queue (label them at /label?queue=<queue>)."""

    async def run(container: Container) -> bool:
        policy = _er_policy(container, threshold, judge_low, judge_high, judge_min_confidence)
        r = await container.build_villas().run(policy, "owner" if labels else None)
        typer.echo(f"policy: {policy}")
        typer.echo(
            f"run={r.run_id} listings={r.listings} villas={r.villas} "
            f"on_both_platforms={r.multi_platform} waiting_for_a_human={r.waiting_for_human} "
            f"newly_queued={r.queued} queue={container.er_config().human_queue}"
        )
        typer.echo(f"  merges applied by decider: {dict(sorted(r.applied.items()))}")
        typer.echo(f"  merges refused: {dict(sorted(r.blocked.items()))}")
        typer.echo(f"  id history: {dict(sorted(r.events.items()))}")
        return True

    asyncio.run(_with_container(run))


@er_app.command("villas-eval")
def er_villas_eval(
    threshold: Annotated[float | None, typer.Option(help=_POLICY_HELP)] = None,
    judge_low: Annotated[float | None, typer.Option(help=_POLICY_HELP)] = None,
    judge_high: Annotated[float | None, typer.Option(help=_POLICY_HELP)] = None,
    judge_min_confidence: Annotated[float | None, typer.Option(help=_POLICY_HELP)] = None,
    judge_merges: Annotated[bool | None, typer.Option(help=_POLICY_HELP)] = None,
    judge_vetoes: Annotated[bool | None, typer.Option(help=_POLICY_HELP)] = None,
    queue: Annotated[str, typer.Option(help="Gold queue.")] = "gold-v1",
) -> None:
    """Pairwise (weighted) and B-cubed scores of the machine decisions against the labels."""

    async def run(container: Container) -> bool:
        policy = _er_policy(
            container,
            threshold,
            judge_low,
            judge_high,
            judge_min_confidence,
            judge_merges,
            judge_vetoes,
        )
        typer.echo(f"policy: {policy}")
        pairwise = await EvaluateDecisions(
            container.candidates(), container.labels(), container.judgements()
        ).run(policy, queue, "owner")
        m = pairwise.metrics
        typer.echo(
            f"pairwise (weighted): precision={_interval(m.precision)} "
            f"recall={_interval(m.recall)} tp={m.true_positives} fp={m.false_positives} "
            f"fn={m.false_negatives} tn={m.true_negatives} waiting_for_a_human={pairwise.waiting}"
        )
        r = await container.villas_eval().run(policy, queue, "owner")
        if r.bcubed is not None:
            typer.echo(
                f"B-cubed over {r.bcubed.elements} labelled listings "
                f"({r.gold_clusters} gold clusters): precision={r.bcubed.precision:.3f} "
                f"recall={r.bcubed.recall:.3f} f1={r.bcubed.f1:.3f}"
            )
        return True

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@er_app.command("revise-labels")
def er_revise_labels(
    file: Annotated[Path, typer.Argument(help="A revision file under eval/labels/.")],
) -> None:
    """Apply label corrections from a committed file; the original labels are kept beside them."""

    async def run(container: Container) -> bool:
        planned = load_revisions(file)
        report = await ReviseLabels(container.labels(), container.clock).run(
            planned.revisions, planned.labeler, planned.revised_by
        )
        for conflict in report.conflicts:
            typer.echo(f"conflict: {conflict}")
        typer.echo(
            f"labeler={planned.labeler} applied={report.applied} already={report.already} "
            f"conflicts={len(report.conflicts)} (nothing applied when there is a conflict)"
        )
        return not report.conflicts

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


@er_app.command("report")
def er_report(
    queue: Annotated[str, typer.Option(help="Gold queue.")] = "gold-v1",
    labeler: Annotated[str, typer.Option(help="Whose labels.")] = "owner",
    out: Annotated[Path | None, typer.Option(help="Defaults to reports/er-eval-<date>.md.")] = None,
) -> None:
    """M5 crit. 3: reports/er-eval-<date>.md (curve, policies, B-cubed, ablations, judge)."""

    async def run(container: Container) -> bool:
        now = container.clock.now()
        report = await container.er_report().run(queue, labeler, now)
        path = out or Path("../reports") / f"er-eval-{now:%Y-%m-%d}.md"
        _write_report(path, render_er_report(report), er_report_artifact(report))
        typer.echo(f"wrote {path}")
        return True

    asyncio.run(_with_container(run))


@er_app.command("ablations")
def er_ablations(
    queue: Annotated[str, typer.Option(help="Gold queue.")] = "gold-v1",
    labeler: Annotated[str, typer.Option(help="Whose labels.")] = "owner",
) -> None:
    """H5 (M5 criterion 6): recall at the precision bar from photos, other evidence, both."""

    async def run(container: Container) -> bool:
        results = await EvaluateAblations(container.candidates(), container.labels()).run(
            queue, labeler
        )
        for a in results:
            point = a.operating_point
            if point is None:
                at_bar = "no threshold reaches precision >= 95% (Wilson low >= 92%)"
            else:
                at_bar = (
                    f"threshold {point.threshold:g}: precision={_interval(point.precision)} "
                    f"recall={_interval(point.recall)}"
                )
            best = a.best_f1
            f1 = (
                f"best F1 {best.f1:.3f} at {best.threshold:g} "
                f"(precision={_interval(best.precision)}, recall={_interval(best.recall)})"
                if best and best.f1 is not None
                else "best F1 n/a"
            )
            typer.echo(f"{a.name:<15} {at_bar}\n{'':<15} {f1}")
        return True

    asyncio.run(_with_container(run))


@er_app.command("judge-eval")
def er_judge_eval(
    low: Annotated[float, typer.Option(help="Lowest rule score of the band.")] = -3.0,
    high: Annotated[float, typer.Option(help="Highest rule score of the band.")] = 3.0,
    queue: Annotated[str, typer.Option(help="Gold queue.")] = "gold-v1",
    labeler: Annotated[str, typer.Option(help="Whose labels.")] = "owner",
    dry_run: Annotated[bool, typer.Option(help="Price the calls without making them.")] = False,
    budget_usd: Annotated[str, typer.Option(help="Job budget in USD.")] = "2.00",
    show: Annotated[bool, typer.Option(help="Print each pair's verdict.")] = False,
    out: Annotated[Path | None, typer.Option(help="Also write a report (and JSON) here.")] = None,
) -> None:
    """M5 criterion 4: the judge's verdicts on the gold pairs of a score band, against labels."""

    async def run(container: Container) -> bool:
        evaluate = container.judge_eval()
        gold = await evaluate.gold_in_band(queue, labeler, low, high)
        if dry_run:
            requests = await container.judge().requests([g[0] for g in gold])
            estimate = await container.llm.dry_run.estimate(requests)
            typer.echo(
                f"band [{low:g}, {high:g}]: {len(gold)} gold pairs, calls={estimate.calls} "
                f"cache_hits={estimate.cache_hits} expected=${estimate.expected_usd:.4f} "
                f"worst_case=${estimate.worst_case_usd:.4f}"
            )
            return True
        ctx = await container.jobs.start("judge_eval", Decimal(budget_usd), {})
        report = await evaluate.run(queue, labeler, low, high, ctx)
        await container.jobs.finish(ctx.job_id, JobStatus.SUCCEEDED)
        typer.echo(
            f"band [{low:g}, {high:g}]: pairs={len(report.pairs)} judged={len(report.judged)} "
            f"unsure={report.unsure_rate:.1%} cost=${report.cost_usd:.4f}"
        )
        for label, verdicts in sorted(report.confusion.items()):
            typer.echo(f"  label {label:<10} {dict(sorted(verdicts.items()))}")
        for confidence in (0.0, 0.7, 0.8, 0.9):
            typer.echo(
                f"  match when confidence >= {confidence:.1f}: "
                f"precision={_interval(report.match_precision(confidence))} "
                f"recall={_interval(report.match_recall(confidence))}"
            )
        for model, values in report.latency_ms().items():
            ordered = sorted(values)
            p95 = ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]
            typer.echo(f"  latency {model}: uncached={len(values)} p95={p95}ms")
        if show:
            for p in report.pairs:
                j = p.judgement
                verdict = f"{j.verdict.verdict}@{j.verdict.confidence:.2f}" if j else p.failure
                typer.echo(f"  {p.label.value:<9} {verdict:<16} {p.score:+.2f} {p.key}")
        if out is not None:
            model = container.llm.routing.route(LLMTask.ER_JUDGE).model
            command = f"uv run villasanj er judge-eval --low {low:g} --high {high:g}"
            artifact = judge_eval_artifact(
                report, model, (low, high), container.clock.now(), command
            )
            lines = [
                f"# Judge evaluation: {model}",
                "",
                f"`{command}` on gold `{queue}` (labels of `{labeler}`), band [{low:g}, {high:g}]: "
                f"{len(report.pairs)} pairs, {len(report.judged)} judged, unsure "
                f"{report.unsure_rate:.1%}, cost ${report.cost_usd:.4f} (0 when replayed from the "
                "cache; the first run's cost and latency are in ADR-0005).",
                "",
                "| Label | Verdicts |",
                "|---|---|",
                *(
                    f"| {label} | {dict(sorted(v.items()))} |"
                    for label, v in sorted(report.confusion.items())
                ),
                "",
                "| Match at confidence ≥ | Precision | Recall |",
                "|---|---|---|",
                *(
                    f"| {c:.1f} | {_interval(report.match_precision(c))} | "
                    f"{_interval(report.match_recall(c))} |"
                    for c in (0.0, 0.7, 0.8, 0.9)
                ),
                "",
            ]
            _write_report(out, "\n".join(lines), artifact)
            typer.echo(f"wrote {out}")
        return True

    asyncio.run(_with_container(run))


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


@pricing_app.command("offers")
def pricing_offers() -> None:
    """Per platform, scenario and group size: offer status, EXACT/RANGE/OPEN and stale counts."""

    async def run(container: Container) -> bool:
        scenarios = load_scenarios(container.settings.scenarios_path)
        rows = await container.offers().distribution(sorted(container.crawl.adapters), scenarios)
        for r in rows:
            statuses = " ".join(f"{k}={v}" for k, v in r.by_status.items())
            kinds = " ".join(f"{k}={v}" for k, v in r.by_kind.items()) or "-"
            typer.echo(
                f"{r.platform:<7} {r.scenario:<8} x{r.guests:<2} listings={r.listings} "
                f"[{statuses}] kinds[{kinds}] stale={r.stale}"
            )
        return True

    asyncio.run(_with_container(run))


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
