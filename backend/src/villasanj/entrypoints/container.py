"""Composition root: the only place that decides which adapter implements which port."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

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
class Container:
    settings: Settings
    engine: AsyncEngine
    blobs: LocalFsBlobStore
    jobs: PgJobRepository
    ledger: PgLLMLedger
    llm: LLMStack
    health: CheckHealth

    async def aclose(self) -> None:
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
    return Container(
        settings=settings,
        engine=engine,
        blobs=blobs,
        jobs=PgJobRepository(engine, clock),
        ledger=ledger,
        llm=llm,
        health=health,
    )
