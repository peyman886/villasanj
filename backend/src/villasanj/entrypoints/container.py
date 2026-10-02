"""Composition root: the only place that decides which adapter implements which port."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.catalog.application.embeddings import EmbedPhotos, ImageEmbedder
from villasanj.catalog.application.ingest import IngestListingSnapshots
from villasanj.catalog.application.photos import EnqueueListingPhotos, FingerprintPhotos
from villasanj.catalog.application.reports import PhotoPipelineReport
from villasanj.catalog.infrastructure.dinov2 import DinoV2Embedder
from villasanj.catalog.infrastructure.gazetteer_file import load_gazetteer
from villasanj.catalog.infrastructure.imaging import ImagehashHasher
from villasanj.catalog.infrastructure.repositories import (
    PgCalendarFlagQuery,
    PgEmbeddingStore,
    PgListingRepository,
    PgPhotoRepository,
    PgPhotoStatsQuery,
    StoredPhotoBytes,
)
from villasanj.discovery.application.dates import BuildHolidayCalendar
from villasanj.discovery.application.hypotheses import BuildHypothesisReport
from villasanj.discovery.application.routing import ComputeDriveTimes, Origin
from villasanj.discovery.application.search import SearchListings
from villasanj.discovery.application.understanding import UnderstandQuery
from villasanj.discovery.infrastructure.holidays import load_holiday_sources
from villasanj.discovery.infrastructure.routing import (
    OsrmRoutingService,
    PgDriveTimeStore,
    load_origin,
)
from villasanj.enrichment.application.claim_labels import (
    BuildClaimLabelQueue,
    ClaimLabeling,
    EvaluateClaimExtraction,
)
from villasanj.enrichment.application.coast import MeasureCoastDistances
from villasanj.enrichment.application.photo_tags import (
    BuildPhotoTagQueue,
    PhotoLabeling,
    TagPhotos,
)
from villasanj.enrichment.application.places import MeasurePlaceDistances
from villasanj.enrichment.application.review_summary import SummarizeReviews
from villasanj.enrichment.application.summary_review import (
    BuildSummaryReviewQueue,
    EvaluateSummaryReviews,
    SummaryReviewing,
)
from villasanj.enrichment.application.truth import (
    CheckDistanceClaims,
    CheckListingClaims,
    CheckSeaClaims,
)
from villasanj.enrichment.infrastructure.claim_labels import PgClaimLabelStore
from villasanj.enrichment.infrastructure.coast import PgCoastDistanceStore, PgCoastline
from villasanj.enrichment.infrastructure.features import load_amenity_map
from villasanj.enrichment.infrastructure.photo_tags import PgPhotoQueueStore, PgPhotoTagStore
from villasanj.enrichment.infrastructure.places import PgPlaceDistanceStore, PgPlaces
from villasanj.enrichment.infrastructure.siglip import SigLip2Tagger
from villasanj.enrichment.infrastructure.summary_review import PgSummaryReviewStore
from villasanj.entity_resolution.application.evaluation import EvaluateMatcher
from villasanj.entity_resolution.application.judge import JudgePairs
from villasanj.entity_resolution.application.labeling import BuildLabelQueue, LabelingSession
from villasanj.entity_resolution.application.matching import MatchListings
from villasanj.entity_resolution.infrastructure.grid import PillowGridRenderer
from villasanj.entity_resolution.infrastructure.photo_index import NumpyPhotoIndex
from villasanj.entity_resolution.infrastructure.repositories import PgCandidateStore, PgLabelStore
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
from villasanj.ingestion.infrastructure.stats import PgCrawlStatsQuery
from villasanj.pricing.application.offers import OfferBook
from villasanj.pricing.application.quotes import QuoteStays
from villasanj.pricing.infrastructure.fees_file import load_fee_policies
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
from villasanj.shared.domain.stay import StayScenario
from villasanj.shared.infrastructure.blob_store import LocalFsBlobStore
from villasanj.shared.infrastructure.clock import SystemClock
from villasanj.shared.infrastructure.db.engine import create_engine
from villasanj.shared.infrastructure.db.repositories import (
    PgJobRepository,
    PgLLMCache,
    PgLLMLedger,
    PgLLMSpendQuery,
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
from villasanj.shared.infrastructure.scenarios import load_scenarios
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
    listings: PgListingRepository
    health: CheckHealth
    http_fetchers: list[HttpxFetcher] = field(default_factory=list)
    _image_embedder: ImageEmbedder | None = None

    def catalog_ingest(self) -> IngestListingSnapshots:
        return IngestListingSnapshots(
            self.crawl.adapters, self.crawl.snapshots, self.blobs, self.listings
        )

    def enqueue_photos(self) -> EnqueueListingPhotos:
        return EnqueueListingPhotos(self.listings, self.crawl.frontier)

    def fingerprint_photos(self) -> FingerprintPhotos:
        return FingerprintPhotos(
            self.crawl.snapshots, self.blobs, ImagehashHasher(), PgPhotoRepository(self.engine)
        )

    def image_embedder(self) -> ImageEmbedder:
        """Local DINOv2 (ADR-0012). Loading the weights is deferred to the first embedding."""
        if self._image_embedder is None:
            self._image_embedder = DinoV2Embedder()
        return self._image_embedder

    def embed_photos(self) -> EmbedPhotos:
        return EmbedPhotos(
            self.crawl.snapshots,
            self.blobs,
            self.image_embedder(),
            PgEmbeddingStore(self.engine, self.clock),
        )

    async def photo_index(self, platforms: list[str]) -> NumpyPhotoIndex:
        model_id = self.image_embedder().model_id
        photos = await PgPhotoRepository(self.engine).photos(platforms)
        vectors = await PgEmbeddingStore(self.engine, self.clock).vectors(model_id)
        return NumpyPhotoIndex(photos, vectors, model_id)

    def candidates(self) -> PgCandidateStore:
        return PgCandidateStore(self.engine)

    def labels(self) -> PgLabelStore:
        return PgLabelStore(self.engine, self.clock)

    async def match_listings(self, platforms: list[str]) -> MatchListings:
        index = await self.photo_index(platforms)
        return MatchListings(self.listings, index, self.candidates(), self.clock)

    def build_label_queue(self) -> BuildLabelQueue:
        return BuildLabelQueue(self.candidates(), self.labels())

    def labeling(self) -> LabelingSession:
        return LabelingSession(self.labels(), self.listings, self.clock)

    def evaluate_matcher(self) -> EvaluateMatcher:
        return EvaluateMatcher(self.candidates(), self.labels())

    def judge(self) -> JudgePairs:
        return JudgePairs(
            self.listings,
            StoredPhotoBytes(self.engine, self.blobs),
            PillowGridRenderer(),
            self.llm.client,
        )

    def quotes(self) -> QuoteStays:
        return QuoteStays(self.listings, load_fee_policies(self.settings.fees_path))

    def offers(self) -> OfferBook:
        return OfferBook(
            self.listings,
            load_fee_policies(self.settings.fees_path),
            self.clock,
            timedelta(hours=self.settings.pricing.offer_max_age_hours),
        )

    def hypothesis_report(self) -> BuildHypothesisReport:
        return BuildHypothesisReport(self.candidates(), self.listings, self.quotes())

    def search(self) -> SearchListings:
        return SearchListings(
            UnderstandQuery(self.llm.client),
            self.holiday_calendar(),
            self.listings,
            self.offers(),
            load_amenity_map(self.settings.features_path),
            load_gazetteer(self.settings.gazetteer_path),
            sorted(self.crawl.adapters),
            self.clock,
            PgCoastDistanceStore(self.engine),
            PgDriveTimeStore(self.engine),
            load_origin(self.settings.routing_origin_path),
            self.place_store(),
        )

    def routing_origin(self) -> Origin:
        return load_origin(self.settings.routing_origin_path)

    def crawl_stats(self) -> PgCrawlStatsQuery:
        return PgCrawlStatsQuery(self.engine)

    def photo_pipeline(self) -> PhotoPipelineReport:
        return PhotoPipelineReport(self.crawl_stats(), PgPhotoStatsQuery(self.engine))

    def sea_truth(self) -> CheckSeaClaims:
        return CheckSeaClaims(self.listings, self.coast_store())

    def listing_claims(self) -> CheckListingClaims:
        return CheckListingClaims(
            load_amenity_map(self.settings.features_path), self.coast_store(), self.place_store()
        )

    def places(self) -> PgPlaces:
        return PgPlaces(self.engine, self.settings.geo.dataset)

    def place_store(self) -> PgPlaceDistanceStore:
        return PgPlaceDistanceStore(self.engine)

    def place_distances(self) -> MeasurePlaceDistances:
        return MeasurePlaceDistances(
            self.listings, self.places(), self.place_store(), self.clock, self.settings.geo.dataset
        )

    def distance_truth(self) -> CheckDistanceClaims:
        return CheckDistanceClaims(self.listings, self.coast_store(), self.place_store())

    def llm_spend(self) -> PgLLMSpendQuery:
        return PgLLMSpendQuery(self.engine)

    def scenarios(self) -> list[StayScenario]:
        return load_scenarios(self.settings.scenarios_path)

    def coast_store(self) -> PgCoastDistanceStore:
        return PgCoastDistanceStore(self.engine)

    def drive_store(self) -> PgDriveTimeStore:
        return PgDriveTimeStore(self.engine)

    def coastline(self) -> PgCoastline:
        return PgCoastline(self.engine, self.settings.geo.dataset)

    def coast_distances(self) -> MeasureCoastDistances:
        return MeasureCoastDistances(
            self.listings,
            self.coastline(),
            PgCoastDistanceStore(self.engine),
            self.clock,
            self.settings.geo.dataset,
        )

    def drive_times(self) -> ComputeDriveTimes:
        return ComputeDriveTimes(
            self.listings,
            OsrmRoutingService(self.settings.geo.osrm_url),
            PgDriveTimeStore(self.engine),
            self.clock,
            load_origin(self.settings.routing_origin_path),
            self.settings.geo.dataset,
        )

    def photo_tagger(self) -> SigLip2Tagger:
        return SigLip2Tagger()

    def photo_tags(self) -> PgPhotoTagStore:
        return PgPhotoTagStore(self.engine)

    def photo_queues(self) -> PgPhotoQueueStore:
        return PgPhotoQueueStore(self.engine)

    def tag_photos(self) -> TagPhotos:
        return TagPhotos(
            self.crawl.snapshots, self.blobs, self.photo_tagger(), self.photo_tags(), self.clock
        )

    def photo_tag_queue(self) -> BuildPhotoTagQueue:
        return BuildPhotoTagQueue(
            self.photo_tags(),
            PgPhotoRepository(self.engine),
            self.photo_queues(),
            self.clock,
            self.photo_tagger().model_id,
        )

    def photo_labeling(self) -> PhotoLabeling:
        return PhotoLabeling(self.photo_queues(), self.clock)

    def claim_label_queue(self) -> BuildClaimLabelQueue:
        return BuildClaimLabelQueue(
            self.listings, PgClaimLabelStore(self.engine), self.clock, sorted(self.crawl.adapters)
        )

    def claim_labeling(self) -> ClaimLabeling:
        return ClaimLabeling(PgClaimLabelStore(self.engine), self.clock)

    def claim_eval(self) -> EvaluateClaimExtraction:
        return EvaluateClaimExtraction(self.listings, PgClaimLabelStore(self.engine))

    def summary_review_queue(self) -> BuildSummaryReviewQueue:
        return BuildSummaryReviewQueue(
            self.listings,
            self.listings,
            PgSummaryReviewStore(self.engine),
            self.clock,
            sorted(self.crawl.adapters),
        )

    def summary_reviewing(self) -> SummaryReviewing:
        return SummaryReviewing(PgSummaryReviewStore(self.engine), self.clock)

    def summary_review_eval(self) -> EvaluateSummaryReviews:
        return EvaluateSummaryReviews(PgSummaryReviewStore(self.engine))

    def review_summaries(self) -> SummarizeReviews:
        return SummarizeReviews(self.llm.client, self.listings)

    def holiday_calendar(self) -> BuildHolidayCalendar:
        return BuildHolidayCalendar(
            PgCalendarFlagQuery(self.engine), load_holiday_sources(self.settings.holidays_path)
        )

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
        listings=PgListingRepository(engine),
        health=health,
    )
