"""Postgres ListingRepository: newest observation wins; calendar observations are append-only."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from villasanj.catalog.application.coverage import CoverageCounts
from villasanj.catalog.application.places import PlaceNames
from villasanj.catalog.application.reading import HolidayFlags
from villasanj.catalog.application.reports import PhotoCounts
from villasanj.catalog.domain.listing import (
    CalendarObservation,
    Listing,
    ListingId,
    LocationEvidence,
)
from villasanj.catalog.domain.photo import ListingPhoto, PerceptualFingerprint, PhotoEmbedding
from villasanj.catalog.domain.review import ListingReview
from villasanj.catalog.infrastructure.tables import (
    calendar_observation,
    listing,
    parse_failure,
    photo,
    photo_embedding,
    review,
)
from villasanj.ingestion.domain.parsed import (
    Availability,
    DatePrecision,
    ParsedAmenity,
    ParsedDistanceClaim,
    ParsedRateCard,
    TravelMode,
)
from villasanj.shared.application.blobs import BlobStore
from villasanj.shared.application.clock import Clock
from villasanj.shared.domain.geo import GeoPoint
from villasanj.shared.domain.money import Money
from villasanj.shared.domain.provenance import Provenance, ProvenanceMethod, SourceRef
from villasanj.shared.domain.stay import DateRange

_CALENDAR_BATCH = 500


def _rial(value: Money | None) -> int | None:
    return value.amount_rial if value is not None else None


def _listing_row(item: Listing) -> dict[str, Any]:
    card = item.rate_card
    return {
        "platform": item.id.platform,
        "external_id": item.id.external_id,
        "url": item.url,
        "title": item.title,
        "title_norm": item.title_norm,
        "description": item.description,
        "description_norm": item.description_norm,
        "property_type": item.property_type,
        "city_fa": item.city_fa,
        "city_slug": item.city_slug,
        "locality_fa": item.locality_fa,
        "lat": item.location.point.lat if item.location else None,
        "lon": item.location.point.lon if item.location else None,
        "location_radius_m": item.location.radius_m if item.location else None,
        "bedrooms": item.bedrooms,
        "bathrooms": item.bathrooms,
        "area_m2": item.area_m2,
        "base_capacity": item.base_capacity,
        "extra_capacity": item.extra_capacity,
        "rating_avg": item.rating_avg,
        "rating_count": item.rating_count,
        "check_in_time": item.check_in_time,
        "check_out_time": item.check_out_time,
        "min_nights": item.min_nights,
        "instant_booking": item.instant_booking,
        "host_ref": item.host_ref,
        "cancellation_policy_text": item.cancellation_policy_text,
        "vat_applies": item.vat_applies,
        "rate_base_rial": _rial(card.base),
        "rate_weekend_rial": _rial(card.weekend),
        "rate_holiday_rial": _rial(card.holiday),
        "extra_guest_base_rial": _rial(card.extra_guest_base),
        "extra_guest_weekend_rial": _rial(card.extra_guest_weekend),
        "extra_guest_holiday_rial": _rial(card.extra_guest_holiday),
        "photos": list(item.photos),
        "amenities": [[a.code, a.label_fa, a.present] for a in item.amenities],
        "distance_claims": [
            [c.target_fa, c.value_text, c.mode.value] for c in item.distance_claims
        ],
        "snapshot_id": uuid.UUID(item.provenance.snapshot_id or ""),
        "observed_at": item.provenance.observed_at,
    }


def _money(rial: int | None) -> Money | None:
    return Money.from_rial(rial) if rial is not None else None


def _listing_from_row(row: Any) -> Listing:
    location = (
        LocationEvidence(GeoPoint(row.lat, row.lon), row.location_radius_m)
        if row.lat is not None and row.lon is not None
        else None
    )
    return Listing(
        id=ListingId(row.platform, row.external_id),
        url=row.url,
        title=row.title,
        title_norm=row.title_norm,
        description=row.description,
        description_norm=row.description_norm,
        property_type=row.property_type,
        city_fa=row.city_fa,
        city_slug=row.city_slug,
        locality_fa=row.locality_fa,
        location=location,
        bedrooms=row.bedrooms,
        bathrooms=row.bathrooms,
        area_m2=row.area_m2,
        base_capacity=row.base_capacity,
        extra_capacity=row.extra_capacity,
        rating_avg=row.rating_avg,
        rating_count=row.rating_count,
        check_in_time=row.check_in_time,
        check_out_time=row.check_out_time,
        min_nights=row.min_nights,
        instant_booking=row.instant_booking,
        host_ref=row.host_ref,
        cancellation_policy_text=row.cancellation_policy_text,
        vat_applies=row.vat_applies,
        rate_card=ParsedRateCard(
            base=_money(row.rate_base_rial),
            weekend=_money(row.rate_weekend_rial),
            holiday=_money(row.rate_holiday_rial),
            extra_guest_base=_money(row.extra_guest_base_rial),
            extra_guest_weekend=_money(row.extra_guest_weekend_rial),
            extra_guest_holiday=_money(row.extra_guest_holiday_rial),
        ),
        provenance=Provenance(
            method=ProvenanceMethod.OBSERVED,
            observed_at=row.observed_at,
            source=SourceRef(row.platform, row.url),
            snapshot_id=str(row.snapshot_id),
        ),
        photos=tuple(str(url) for url in row.photos),
        amenities=tuple(ParsedAmenity(c, label, bool(p)) for c, label, p in row.amenities),
        distance_claims=tuple(
            ParsedDistanceClaim(target, value, TravelMode(mode))
            for target, value, mode in row.distance_claims
        ),
    )


def _calendar_from_row(row: Any) -> CalendarObservation:
    return CalendarObservation(
        listing_id=ListingId(row.platform, row.external_id),
        night=row.night,
        availability=Availability(row.availability),
        nightly_price=_money(row.nightly_rial),
        extra_guest_price=_money(row.extra_guest_rial),
        min_nights=row.min_nights,
        is_holiday=row.is_holiday,
        snapshot_id=str(row.snapshot_id),
        observed_at=row.observed_at,
    )


def _calendar_row(observation: CalendarObservation) -> dict[str, Any]:
    return {
        "platform": observation.listing_id.platform,
        "external_id": observation.listing_id.external_id,
        "night": observation.night,
        "snapshot_id": uuid.UUID(observation.snapshot_id),
        "availability": observation.availability.value,
        "nightly_rial": _rial(observation.nightly_price),
        "extra_guest_rial": _rial(observation.extra_guest_price),
        "min_nights": observation.min_nights,
        "is_holiday": observation.is_holiday,
        "observed_at": observation.observed_at,
    }


class PgListingRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, item: Listing, calendar: Sequence[CalendarObservation]) -> bool:
        row = _listing_row(item)
        candidate = insert(listing).values(row)
        upsert = candidate.on_conflict_do_update(
            index_elements=[listing.c.platform, listing.c.external_id],
            set_={
                key: candidate.excluded[key]
                for key in row
                if key not in ("platform", "external_id")
            },
            where=candidate.excluded.observed_at >= listing.c.observed_at,
        ).returning(listing.c.external_id)
        async with self._engine.begin() as conn:
            updated = (await conn.execute(upsert)).first() is not None
            await self._append_calendar(conn, calendar)
        return updated

    async def save_calendar(self, calendar: Sequence[CalendarObservation]) -> None:
        async with self._engine.begin() as conn:
            await self._append_calendar(conn, calendar)

    @staticmethod
    async def _append_calendar(
        conn: AsyncConnection, calendar: Sequence[CalendarObservation]
    ) -> None:
        rows = [_calendar_row(o) for o in calendar]
        for start in range(0, len(rows), _CALENDAR_BATCH):
            await conn.execute(
                insert(calendar_observation)
                .values(rows[start : start + _CALENDAR_BATCH])
                .on_conflict_do_nothing()
            )

    async def save_reviews(self, reviews: Sequence[ListingReview]) -> None:
        rows = [
            {
                "platform": r.listing_id.platform,
                "review_id": r.review_id,
                "external_id": r.listing_id.external_id,
                "rating": r.rating,
                "text": r.text,
                "text_norm": r.text_norm,
                "stayed_on": r.stayed_on,
                "stayed_precision": r.stayed_precision.value if r.stayed_precision else None,
                "host_replied": r.host_replied,
                "snapshot_id": uuid.UUID(r.provenance.snapshot_id or ""),
                "observed_at": r.provenance.observed_at,
            }
            for r in {r.review_id: r for r in reviews}.values()
        ]
        if not rows:
            return
        statement = insert(review).values(rows)
        upsert = statement.on_conflict_do_update(
            index_elements=[review.c.platform, review.c.review_id],
            set_={k: statement.excluded[k] for k in rows[0] if k not in ("platform", "review_id")},
            where=statement.excluded.observed_at >= review.c.observed_at,
        )
        async with self._engine.begin() as conn:
            await conn.execute(upsert)

    async def review_counts(self, platform: str) -> dict[str, int]:
        query = select(
            func.count().label("reviews"),
            func.count(func.distinct(review.c.external_id)).label("listings"),
            func.count(review.c.text).label("with_text"),
            func.count().filter(review.c.host_replied).label("host_replied"),
        ).where(review.c.platform == platform)
        async with self._engine.connect() as conn:
            row = (await conn.execute(query)).one()
        return {k: int(v) for k, v in row._mapping.items()}

    async def reviews(self, listing_id: ListingId) -> list[ListingReview]:
        query = (
            select(review, listing.c.url)
            .join(
                listing,
                (listing.c.platform == review.c.platform)
                & (listing.c.external_id == review.c.external_id),
            )
            .where(
                review.c.platform == listing_id.platform,
                review.c.external_id == listing_id.external_id,
            )
            .order_by(review.c.stayed_on.desc().nulls_last(), review.c.review_id)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [
            ListingReview(
                listing_id=listing_id,
                review_id=r.review_id,
                rating=r.rating,
                text=r.text,
                text_norm=r.text_norm,
                stayed_on=r.stayed_on,
                stayed_precision=DatePrecision(r.stayed_precision) if r.stayed_precision else None,
                host_replied=r.host_replied,
                provenance=Provenance(
                    ProvenanceMethod.OBSERVED,
                    r.observed_at,
                    SourceRef(listing_id.platform, r.url),
                    str(r.snapshot_id),
                ),
            )
            for r in rows
        ]

    async def record_failure(self, snapshot_id: str, platform: str, reason: str) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                insert(parse_failure)
                .values(snapshot_id=uuid.UUID(snapshot_id), platform=platform, reason=reason)
                .on_conflict_do_nothing()
            )

    async def photo_urls(
        self, platform: str, per_listing: int, listing_limit: int | None
    ) -> Sequence[tuple[ListingId, int, str]]:
        query = (
            select(listing.c.external_id, listing.c.photos)
            .where(listing.c.platform == platform)
            .order_by(listing.c.external_id)
            .limit(listing_limit)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [
            (ListingId(platform, row.external_id), position, str(url))
            for row in rows
            for position, url in enumerate(row.photos[:per_listing])
        ]

    async def count(self, platform: str) -> int:
        query = select(func.count()).select_from(listing).where(listing.c.platform == platform)
        async with self._engine.connect() as conn:
            return int((await conn.execute(query)).scalar_one())

    async def get(self, listing_id: ListingId) -> Listing | None:
        query = select(listing).where(
            listing.c.platform == listing_id.platform,
            listing.c.external_id == listing_id.external_id,
        )
        async with self._engine.connect() as conn:
            row = (await conn.execute(query)).first()
        return _listing_from_row(row) if row is not None else None

    async def listings(self, platform: str) -> list[Listing]:
        query = (
            select(listing).where(listing.c.platform == platform).order_by(listing.c.external_id)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [_listing_from_row(row) for row in rows]

    async def calendars(
        self, platform: str, stay: DateRange
    ) -> dict[ListingId, list[CalendarObservation]]:
        query = (
            select(calendar_observation)
            .where(
                calendar_observation.c.platform == platform,
                calendar_observation.c.night >= stay.check_in,
                calendar_observation.c.night < stay.check_out,
            )
            .order_by(
                calendar_observation.c.external_id,
                calendar_observation.c.night,
                calendar_observation.c.observed_at,
            )
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        grouped: dict[ListingId, list[CalendarObservation]] = {}
        for row in rows:
            observation = _calendar_from_row(row)
            grouped.setdefault(observation.listing_id, []).append(observation)
        return grouped

    async def calendar(self, listing_id: ListingId, stay: DateRange) -> list[CalendarObservation]:
        query = (
            select(calendar_observation)
            .where(
                calendar_observation.c.platform == listing_id.platform,
                calendar_observation.c.external_id == listing_id.external_id,
                calendar_observation.c.night >= stay.check_in,
                calendar_observation.c.night < stay.check_out,
            )
            .order_by(calendar_observation.c.night, calendar_observation.c.observed_at)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [_calendar_from_row(row) for row in rows]


class PgPhotoRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def urls(self, sha256s: Sequence[str]) -> dict[str, str]:
        """A platform URL for each image content hash (the first listing position that has it)."""
        found: dict[str, str] = {}
        async with self._engine.connect() as conn:
            for start in range(0, len(sha256s), 5000):
                query = (
                    select(photo.c.sha256, photo.c.url)
                    .where(photo.c.sha256.in_(sha256s[start : start + 5000]))
                    .order_by(
                        photo.c.sha256, photo.c.platform, photo.c.external_id, photo.c.position
                    )
                )
                for row in await conn.execute(query):
                    found.setdefault(row.sha256, row.url)
        return found

    async def save(self, item: ListingPhoto) -> None:
        row = {
            "platform": item.listing_id.platform,
            "external_id": item.listing_id.external_id,
            "position": item.position,
            "url": item.url,
            "snapshot_id": uuid.UUID(item.snapshot_id),
            "sha256": item.sha256,
            "width": item.fingerprint.width,
            "height": item.fingerprint.height,
            "phash": item.fingerprint.phash,
            "dhash": item.fingerprint.dhash,
            "observed_at": item.observed_at,
        }
        candidate = insert(photo).values(row)
        upsert = candidate.on_conflict_do_update(
            index_elements=[photo.c.platform, photo.c.external_id, photo.c.position],
            set_={
                k: candidate.excluded[k]
                for k in row
                if k not in ("platform", "external_id", "position")
            },
            where=candidate.excluded.observed_at >= photo.c.observed_at,
        )
        async with self._engine.begin() as conn:
            await conn.execute(upsert)

    async def fingerprinted(self, platform: str) -> set[str]:
        query = select(photo.c.snapshot_id).where(photo.c.platform == platform)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return {str(row.snapshot_id) for row in rows}

    async def photos(self, platforms: Sequence[str]) -> list[ListingPhoto]:
        query = (
            select(photo)
            .where(photo.c.platform.in_(list(platforms)))
            .order_by(photo.c.platform, photo.c.external_id, photo.c.position)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [
            ListingPhoto(
                listing_id=ListingId(row.platform, row.external_id),
                position=row.position,
                url=row.url,
                snapshot_id=str(row.snapshot_id),
                sha256=row.sha256,
                fingerprint=PerceptualFingerprint(row.phash, row.dhash, row.width, row.height),
                observed_at=row.observed_at,
            )
            for row in rows
        ]


class PgEmbeddingStore:
    def __init__(self, engine: AsyncEngine, clock: Clock) -> None:
        self._engine = engine
        self._clock = clock

    async def embedded(self, model_id: str) -> set[str]:
        query = select(photo_embedding.c.sha256).where(photo_embedding.c.model_id == model_id)
        async with self._engine.connect() as conn:
            return set((await conn.execute(query)).scalars())

    async def save(self, embeddings: Sequence[PhotoEmbedding]) -> None:
        if not embeddings:
            return
        now = self._clock.now()
        rows = [
            {
                "sha256": e.sha256,
                "model_id": e.model_id,
                "vector": list(e.vector),
                "created_at": now,
            }
            for e in embeddings
        ]
        async with self._engine.begin() as conn:
            await conn.execute(insert(photo_embedding).values(rows).on_conflict_do_nothing())

    async def vectors(self, model_id: str) -> dict[str, tuple[float, ...]]:
        query = select(photo_embedding.c.sha256, photo_embedding.c.vector).where(
            photo_embedding.c.model_id == model_id
        )
        async with self._engine.connect() as conn:
            return {row.sha256: tuple(row.vector) for row in (await conn.execute(query)).all()}


_COVERAGE_SQL = text(
    """
    WITH latest AS (
        SELECT DISTINCT ON (external_id, night) external_id, night, observed_at
        FROM catalog.calendar_observation
        WHERE platform = :platform AND night = ANY(:nights)
        ORDER BY external_id, night, observed_at DESC
    ), per_listing AS (
        SELECT external_id, count(*) AS nights, min(observed_at) AS first_seen,
               max(observed_at) AS last_seen
        FROM latest GROUP BY external_id
    )
    SELECT (SELECT count(*) FROM catalog.listing WHERE platform = :platform) AS listings,
           count(*) FILTER (WHERE nights = :night_count) AS covered,
           min(first_seen) FILTER (WHERE nights = :night_count) AS earliest,
           max(last_seen) FILTER (WHERE nights = :night_count) AS latest
    FROM per_listing
    """
)


class PgCoverageQuery:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def counts(self, platform: str, nights: Sequence[date]) -> CoverageCounts:
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(
                    _COVERAGE_SQL,
                    {"platform": platform, "nights": list(nights), "night_count": len(nights)},
                )
            ).one()
        return CoverageCounts(
            listings=int(row.listings),
            covered=int(row.covered or 0),
            earliest=row.earliest,
            latest=row.latest,
        )


class PgPlaceNameQuery:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def names(self, platform: str) -> list[PlaceNames]:
        query = (
            select(listing.c.city_fa, listing.c.locality_fa, func.count().label("listings"))
            .where(listing.c.platform == platform)
            .group_by(listing.c.city_fa, listing.c.locality_fa)
            .order_by(listing.c.city_fa, listing.c.locality_fa)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [PlaceNames(row.city_fa, row.locality_fa, int(row.listings)) for row in rows]


_PHOTO_COUNTS = text(
    """
    WITH listings AS (
        SELECT platform, count(*) AS listings, sum(jsonb_array_length(photos)) AS referenced
        FROM catalog.listing GROUP BY platform
    ), photos AS (
        SELECT platform, count(*) AS fingerprinted, count(DISTINCT sha256) AS distinct_images
        FROM catalog.photo GROUP BY platform
    ), embedded AS (
        SELECT p.platform, count(DISTINCT p.sha256) AS embedded
        FROM catalog.photo p
        JOIN catalog.photo_embedding e ON e.sha256 = p.sha256 AND e.model_id = :model
        GROUP BY p.platform
    )
    SELECT l.platform, l.listings, l.referenced, coalesce(p.fingerprinted, 0) AS fingerprinted,
           coalesce(p.distinct_images, 0) AS distinct_images, coalesce(e.embedded, 0) AS embedded
    FROM listings l
    LEFT JOIN photos p USING (platform)
    LEFT JOIN embedded e USING (platform)
    ORDER BY l.platform
    """
)


class PgPhotoStatsQuery:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def counts(self, model_id: str) -> list[PhotoCounts]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(_PHOTO_COUNTS, {"model": model_id})).all()
        return [
            PhotoCounts(
                r.platform,
                int(r.listings),
                int(r.referenced or 0),
                int(r.fingerprinted),
                int(r.distinct_images),
                int(r.embedded),
            )
            for r in rows
        ]


class StoredPhotoBytes:
    """A listing's stored photo images in page order (what the matcher saw)."""

    def __init__(self, engine: AsyncEngine, blobs: BlobStore) -> None:
        self._engine = engine
        self._blobs = blobs

    async def photos(self, listing_id: ListingId, limit: int) -> list[bytes]:
        query = (
            select(photo.c.sha256)
            .where(
                photo.c.platform == listing_id.platform,
                photo.c.external_id == listing_id.external_id,
            )
            .order_by(photo.c.position)
            .limit(limit)
        )
        async with self._engine.connect() as conn:
            keys = [row.sha256 for row in (await conn.execute(query)).all()]
        return [await self._blobs.get(key) for key in keys]


_HOLIDAY_FLAGS = text(
    """
    SELECT platform, night,
           count(DISTINCT external_id) FILTER (WHERE is_holiday) AS flagged,
           count(DISTINCT external_id) FILTER (WHERE is_holiday IS NOT NULL) AS reported,
           max(observed_at) AS observed_at
    FROM catalog.calendar_observation
    WHERE night >= :start AND night < :end
    GROUP BY platform, night
    ORDER BY night, platform
    """
)


class PgCalendarFlagQuery:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def holiday_flags(self, start: date, end: date) -> list[HolidayFlags]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(_HOLIDAY_FLAGS, {"start": start, "end": end})).all()
        return [
            HolidayFlags(r.platform, r.night, int(r.flagged), int(r.reported), r.observed_at)
            for r in rows
        ]
