"""Postgres ListingRepository: newest observation wins; calendar observations are append-only."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from villasanj.catalog.domain.listing import CalendarObservation, Listing
from villasanj.catalog.infrastructure.tables import calendar_observation, listing, parse_failure
from villasanj.shared.domain.money import Money

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

    async def record_failure(self, snapshot_id: str, platform: str, reason: str) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(
                insert(parse_failure)
                .values(snapshot_id=uuid.UUID(snapshot_id), platform=platform, reason=reason)
                .on_conflict_do_nothing()
            )

    async def count(self, platform: str) -> int:
        query = select(func.count()).select_from(listing).where(listing.c.platform == platform)
        async with self._engine.connect() as conn:
            return int((await conn.execute(query)).scalar_one())
