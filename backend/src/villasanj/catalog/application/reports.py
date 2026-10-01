"""Coverage reports for M4: the photo pipeline and the regional inventory per platform."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from villasanj.catalog.application.reading import ListingReader
from villasanj.ingestion.application.ports import FrontierStatus
from villasanj.ingestion.application.stats import CrawlStatsQuery
from villasanj.ingestion.domain.pages import PageKind
from villasanj.ingestion.domain.region import Region

HTTP_OK = 200
UNFINISHED = (FrontierStatus.PENDING.value, FrontierStatus.IN_PROGRESS.value)
GAVE_UP = (FrontierStatus.FAILED.value, FrontierStatus.SKIPPED.value)


@dataclass(frozen=True, slots=True)
class PhotoCounts:
    platform: str
    listings: int
    referenced: int  # photo URLs published on listing pages
    fingerprinted: int
    distinct_images: int
    embedded: int  # distinct images with a vector of the current model


class PhotoStatsQuery(Protocol):
    async def counts(self, model_id: str) -> list[PhotoCounts]: ...


@dataclass(frozen=True, slots=True)
class PhotoPipelineRow:
    platform: str
    listings: int
    referenced: int
    selected: int  # queued by the photo policy (coverage photos per listing)
    downloaded: int
    failed_responses: dict[int, int]
    unfinished: int
    failed_or_skipped: int
    fingerprinted: int
    embedded: int
    stored_bytes: int
    reasons: dict[str, int] = field(default_factory=dict)

    @property
    def coverage(self) -> float:
        """Downloaded or explained (a logged reason) out of what the policy selected."""
        explained = self.downloaded + self.failed_or_skipped + sum(self.failed_responses.values())
        return explained / self.selected if self.selected else 0.0


class PhotoPipelineReport:
    def __init__(self, crawl: CrawlStatsQuery, photos: PhotoStatsQuery) -> None:
        self._crawl = crawl
        self._photos = photos

    async def run(self, model_id: str) -> list[PhotoPipelineRow]:
        progress = {
            p.platform: p for p in await self._crawl.progress() if p.kind == PageKind.PHOTO.value
        }
        responses = {r.platform: r for r in await self._crawl.responses([PageKind.PHOTO.value])}
        rows = []
        for counts in await self._photos.counts(model_id):
            queue = progress.get(counts.platform)
            statuses = queue.statuses if queue else {}
            answered = responses.get(counts.platform)
            by_status = answered.requests_by_status if answered else {}
            rows.append(
                PhotoPipelineRow(
                    platform=counts.platform,
                    listings=counts.listings,
                    referenced=counts.referenced,
                    selected=sum(statuses.values()),
                    downloaded=by_status.get(HTTP_OK, 0),
                    failed_responses={s: n for s, n in by_status.items() if s != HTTP_OK},
                    unfinished=sum(statuses.get(s, 0) for s in UNFINISHED),
                    failed_or_skipped=sum(statuses.get(s, 0) for s in GAVE_UP),
                    fingerprinted=counts.fingerprinted,
                    embedded=counts.embedded,
                    stored_bytes=answered.stored_bytes if answered else 0,
                    reasons=queue.reasons if queue else {},
                )
            )
        return rows


@dataclass(frozen=True, slots=True)
class InventoryRow:
    platform: str
    discovered: int  # listing pages found by discovery (search pages or sitemaps)
    responses: dict[int, int]  # newest response status per listing page
    parsed: int
    in_region: int
    with_location: int
    with_capacity: int
    with_base_price: int


class RegionalInventory:
    def __init__(self, crawl: CrawlStatsQuery, listings: ListingReader, region: Region) -> None:
        self._crawl = crawl
        self._listings = listings
        self._region = region

    async def run(self, platforms: Sequence[str]) -> list[InventoryRow]:
        progress = {
            p.platform: p for p in await self._crawl.progress() if p.kind == PageKind.LISTING.value
        }
        responses = {r.platform: r for r in await self._crawl.responses([PageKind.LISTING.value])}
        rows = []
        for platform in platforms:
            listings = await self._listings.listings(platform)
            queue = progress.get(platform)
            answered = responses.get(platform)
            rows.append(
                InventoryRow(
                    platform=platform,
                    discovered=sum(queue.statuses.values()) if queue else 0,
                    responses=answered.requests_by_status if answered else {},
                    parsed=len(listings),
                    in_region=sum(
                        1
                        for x in listings
                        if x.location is not None and self._region.contains(x.location.point)
                    ),
                    with_location=sum(1 for x in listings if x.location is not None),
                    with_capacity=sum(1 for x in listings if x.base_capacity is not None),
                    with_base_price=sum(1 for x in listings if x.rate_card.base is not None),
                )
            )
        return rows
