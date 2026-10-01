"""Composition root: the only place that decides which adapter implements which port."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.ingestion.application.crawl import CrawlPlatform, SnapshotReplayFetcher
from villasanj.ingestion.application.polite_fetcher import PoliteFetcher
from villasanj.ingestion.application.ports import Fetcher, SourceAdapter
from villasanj.ingestion.domain.pages import FetchedPage
from villasanj.ingestion.domain.policy import CrawlPolicy
from villasanj.ingestion.domain.region import Region
from villasanj.ingestion.infrastructure.http import HttpxFetcher, ProtegoRobotsParser
from villasanj.ingestion.infrastructure.registry import load_region, load_source_adapters
from villasanj.ingestion.infrastructure.repositories import (
    PgCrawlRunRepository,
    PgFrontierRepository,
    PgSnapshotRepository,
)
from villasanj.shared.application.clock import Clock
from villasanj.shared.application.errors import ConfigurationError
from villasanj.shared.application.health import CheckHealth
from villasanj.shared.application.llm.caching import CachingInvoker
from villasanj.shared.application.llm.client import RoutedLLMClient
from villasanj.shared.application.llm.cost import CostGoverningInvoker
from villasanj.shared.application.llm.estimation import HeuristicTokenEstimator
from villasanj.shared.application.llm.planning import DryRunEstimator
from villasanj.shared.application.llm.ports import LLMCacheStore, LLMLedger, RawModelProvider
from villasanj.shared.application.llm.retrying import RetryingInvoker
from villasanj.shared.application.llm.routing import LLMRouting, ModelCatalog
from villasanj.shared.application.llm.structured import StructuredOutputInvoker
from villasanj.shared.infrastructure.blob_store import LocalFsBlobStore
from villasanj.shared.infrastructure.clock import SystemClock
from villasanj.shared.infrastructure.db.engine import create_engine
from villasanj.shared.infrastructure.db.repositories import (
    PgJobRepository,
    PgLLMCache,
    PgLLMLedger,
)
from villasanj.shared.infrastructure.health_probes import (
    BlobStoreProbe,
    DatabaseProbe,
    LLMProviderProbe,
)
from villasanj.shared.infrastructure.llm.avalai import AvalAIProvider
from villasanj.shared.infrastructure.llm.config import load_catalog, load_routing
from villasanj.shared.infrastructure.llm.fake import FakeLLMProvider
from villasanj.shared.infrastructure.logging import configure_logging
from villasanj.shared.infrastructure.settings import Settings


@dataclass
class LLMStack:
    routing: LLMRouting
    catalog: ModelCatalog
    provider: RawModelProvider
    client: RoutedLLMClient
    dry_run: DryRunEstimator


@dataclass
class CrawlStack:
    adapters: dict[str, SourceAdapter]
    region: Region
    policy: CrawlPolicy
    snapshots: PgSnapshotRepository
    frontier: PgFrontierRepository
    runs: PgCrawlRunRepository


@dataclass
class Container:
    settings: Settings
    clock: SystemClock
    engine: AsyncEngine
    blobs: LocalFsBlobStore
    jobs: PgJobRepository
    ledger: PgLLMLedger
    llm: LLMStack
    crawl: CrawlStack
    health: CheckHealth
    http_fetchers: list[HttpxFetcher] = field(default_factory=list)

    def adapter(self, platform: str) -> SourceAdapter:
        try:
            return self.crawl.adapters[platform]
        except KeyError:
            known = ", ".join(sorted(self.crawl.adapters)) or "none"
            raise ConfigurationError(
                f"unknown platform {platform!r} (registered: {known})"
            ) from None

    def fetcher(self, live: bool) -> Fetcher:
        """Live: polite HTTP (needs CRAWL__CONTACT). Offline: stored snapshots only."""
        if not live:
            return SnapshotReplayFetcher(self.crawl.snapshots, self.blobs)
        if not self.settings.crawl.contact:
            raise ConfigurationError(
                "live crawling requires CRAWL__CONTACT (shown in the user agent)"
            )
        http = HttpxFetcher(self.crawl.policy.user_agent, self.clock)
        self.http_fetchers.append(http)
        profiles = {slug: adapter.profile for slug, adapter in self.crawl.adapters.items()}
        return PoliteFetcher(
            http,
            ProtegoRobotsParser(),
            self.crawl.policy,
            profiles,
            self.clock,
            asyncio.sleep,
            robots_sink=self.store_page,
        )

    async def store_page(self, page: FetchedPage) -> str:
        blob = await self.blobs.put(page.body)
        return (await self.crawl.snapshots.save(page, blob, None)).id

    def crawler(self, platform: str, live: bool) -> CrawlPlatform:
        return CrawlPlatform(
            self.adapter(platform),
            self.fetcher(live),
            self.blobs,
            self.crawl.snapshots,
            self.crawl.frontier,
            self.crawl.runs,
            self.clock,
        )

    async def aclose(self) -> None:
        for http in self.http_fetchers:
            await http.aclose()
        if isinstance(self.llm.provider, AvalAIProvider):
            await self.llm.provider.aclose()
        await self.engine.dispose()


def build_provider(settings: Settings, timeout_seconds: float) -> RawModelProvider:
    if settings.llm.provider == "fake":
        return FakeLLMProvider()
    if settings.avalai_api_key is None:
        raise ConfigurationError("LLM__PROVIDER=avalai requires AVALAI_API_KEY")
    return AvalAIProvider(settings.avalai_api_key, settings.avalai_base_url, timeout_seconds)


def build_llm_stack(
    settings: Settings,
    cache: LLMCacheStore,
    ledger: LLMLedger,
    clock: Clock,
    provider: RawModelProvider | None = None,
) -> LLMStack:
    """Assemble the decorator chain: routing -> cache -> retry -> cost -> structured -> provider."""
    routing = load_routing(settings.routing_path, settings.llm.budget.project_usd)
    catalog = load_catalog(settings.models_path, settings.routing_path)
    routing.validate_against(catalog)
    provider = provider or build_provider(settings, routing.retry.request_timeout_seconds)
    estimator = HeuristicTokenEstimator(catalog)
    structured = StructuredOutputInvoker(provider, estimator)
    governed = CostGoverningInvoker(
        structured, ledger, catalog, estimator, clock, routing.project_budget_usd
    )
    retrying = RetryingInvoker(governed, routing.retry, asyncio.sleep)
    caching = CachingInvoker(retrying, cache, ledger, clock, provider.name)
    return LLMStack(
        routing=routing,
        catalog=catalog,
        provider=provider,
        client=RoutedLLMClient(caching, routing),
        dry_run=DryRunEstimator(routing, catalog, estimator, cache, provider.name),
    )


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or Settings()
    configure_logging(settings.logging.level, settings.logging.format, settings.secret_values())
    clock = SystemClock()
    engine = create_engine(settings.database)
    blobs = LocalFsBlobStore(settings.blob.root)
    ledger = PgLLMLedger(engine)
    llm = build_llm_stack(settings, PgLLMCache(engine), ledger, clock)
    health = CheckHealth(
        [DatabaseProbe(engine), BlobStoreProbe(blobs), LLMProviderProbe(llm.provider, clock)],
        timeout_seconds=settings.health_timeout_seconds,
    )
    crawl = CrawlStack(
        adapters=load_source_adapters(),
        region=load_region(settings.region_path),
        policy=CrawlPolicy(
            user_agent=settings.crawl.user_agent(),
            robots_token=settings.crawl.bot_name,
            min_delay_seconds=settings.crawl.min_delay_seconds,
        ),
        snapshots=PgSnapshotRepository(engine),
        frontier=PgFrontierRepository(engine, clock),
        runs=PgCrawlRunRepository(engine, clock),
    )
    return Container(
        settings=settings,
        clock=clock,
        engine=engine,
        blobs=blobs,
        jobs=PgJobRepository(engine, clock),
        ledger=ledger,
        llm=llm,
        crawl=crawl,
        health=health,
    )
