"""Photo pipeline: queue listing photos for polite fetching, then fingerprint photo snapshots."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from villasanj.catalog.domain.listing import ListingId
from villasanj.catalog.domain.photo import ListingPhoto, PerceptualFingerprint
from villasanj.ingestion.application.ports import FrontierRepository, SnapshotRepository
from villasanj.ingestion.domain.pages import PageKind, PageRequest
from villasanj.shared.application.blobs import BlobStore

HTTP_OK = 200
LISTING_CODE = "listing_code"
PHOTO_POSITION = "photo_position"


class PerceptualHasher(Protocol):
    def fingerprint(self, image: bytes) -> PerceptualFingerprint | None:
        """``None`` when the bytes are not a readable image."""
        ...


class PhotoUrlSource(Protocol):
    async def photo_urls(
        self, platform: str, per_listing: int, listing_limit: int | None
    ) -> Sequence[tuple[ListingId, int, str]]:
        """(listing, position, url) for the first ``per_listing`` photos of each listing."""
        ...


class PhotoRepository(Protocol):
    async def save(self, photo: ListingPhoto) -> None: ...


class PhotoReader(Protocol):
    async def photos(self, platforms: Sequence[str]) -> list[ListingPhoto]:
        """Fingerprinted photos of these platforms, ordered by listing and position."""
        ...


@dataclass(frozen=True, slots=True)
class FingerprintReport:
    platform: str
    snapshots: int = 0
    fingerprinted: int = 0
    unreadable: int = 0
    unattributed: int = 0


class EnqueueListingPhotos:
    def __init__(self, source: PhotoUrlSource, frontier: FrontierRepository) -> None:
        self._source = source
        self._frontier = frontier

    async def run(self, platform: str, per_listing: int, listing_limit: int | None) -> int:
        requests = [
            PageRequest(
                platform,
                PageKind.PHOTO,
                url,
                context=((LISTING_CODE, listing.external_id), (PHOTO_POSITION, str(position))),
            )
            for listing, position, url in await self._source.photo_urls(
                platform, per_listing, listing_limit
            )
        ]
        return await self._frontier.enqueue(requests, None)


class FingerprintPhotos:
    def __init__(
        self,
        snapshots: SnapshotRepository,
        blobs: BlobStore,
        hasher: PerceptualHasher,
        photos: PhotoRepository,
    ) -> None:
        self._snapshots = snapshots
        self._blobs = blobs
        self._hasher = hasher
        self._photos = photos

    async def run(self, platform: str) -> FingerprintReport:
        report = FingerprintReport(platform=platform)
        for snapshot in await self._snapshots.list_for(platform, [PageKind.PHOTO]):
            report = replace(report, snapshots=report.snapshots + 1)
            code = snapshot.request.context_value(LISTING_CODE)
            position = snapshot.request.context_value(PHOTO_POSITION)
            if code is None or position is None or snapshot.status != HTTP_OK:
                report = replace(report, unattributed=report.unattributed + 1)
                continue
            fingerprint = self._hasher.fingerprint(await self._blobs.get(snapshot.blob_key))
            if fingerprint is None:
                report = replace(report, unreadable=report.unreadable + 1)
                continue
            await self._photos.save(
                ListingPhoto(
                    listing_id=ListingId(platform, code),
                    position=int(position),
                    url=snapshot.request.url,
                    snapshot_id=snapshot.id,
                    sha256=snapshot.blob_key,
                    fingerprint=fingerprint,
                    observed_at=snapshot.fetched_at,
                )
            )
            report = replace(report, fingerprinted=report.fingerprinted + 1)
        return report
