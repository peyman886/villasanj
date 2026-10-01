"""Command-line entrypoint (``villasanj ...``) for jobs and operations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

import typer

from villasanj.entrypoints.container import Container, build_container
from villasanj.ingestion.application.errors import CrawlError
from villasanj.ingestion.domain.pages import PageKind, PageRequest
from villasanj.shared.application.jobs import JobStatus
from villasanj.shared.application.llm.smoke import LLMSmokeCheck
from villasanj.shared.infrastructure.llm.models_snapshot import (
    compact_snapshot,
    fetch_models,
    write_snapshot,
)
from villasanj.shared.infrastructure.settings import Settings

app = typer.Typer(no_args_is_help=True, add_completion=False)
llm_app = typer.Typer(no_args_is_help=True, help="LLM gateway operations.")
crawl_app = typer.Typer(no_args_is_help=True, help="Polite crawling (ADR-0008, ADR-0011).")
catalog_app = typer.Typer(no_args_is_help=True, help="Build the catalog from stored snapshots.")
app.add_typer(llm_app, name="llm")
app.add_typer(crawl_app, name="crawl")
app.add_typer(catalog_app, name="catalog")

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
) -> None:
    """Crawl a platform's frontier for the configured region."""

    async def run(container: Container) -> bool:
        report = await container.crawler(platform, live).run(
            container.crawl.region, max_requests, live
        )
        typer.echo(
            f"run={report.run_id} fetched={report.fetched} skipped={report.skipped} "
            f"retried={report.retried} gave_up={report.gave_up} discovered={report.discovered} "
            f"discover_errors={report.discover_errors} stop={report.stop_reason}"
        )
        return not report.stop_reason.startswith("blocked")

    if not asyncio.run(_with_container(run)):
        raise typer.Exit(code=1)


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


async def _with_container[R](run: Callable[[Container], Awaitable[R]]) -> R:
    container = build_container()
    try:
        return await run(container)
    finally:
        await container.aclose()
