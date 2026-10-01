"""OSRM's table service for free-flow drive times, and the stored drive times (ADR-0013)."""

from __future__ import annotations

import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Row,
    Table,
    Text,
    delete,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.catalog.domain.listing import ListingId
from villasanj.discovery.application.routing import DriveTime, Leg, Origin
from villasanj.enrichment.domain.geo import Blur
from villasanj.shared.application.errors import ConfigurationError
from villasanj.shared.domain.geo import GeoPoint

SCHEMA = "discovery"
TABLE_BATCH = 300  # destinations per OSRM table request (osrm-routed --max-table-size 10000)
DB_BATCH = 1000
metadata = MetaData(naming_convention={"pk": "pk_%(table_name)s"})

drive_time = Table(
    "drive_time",
    metadata,
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("origin", Text, nullable=False),
    Column("dataset", Text, nullable=False),
    Column("center_s", Float),
    Column("low_s", Float),
    Column("high_s", Float),
    Column("center_m", Float),
    Column("routed_points", Integer, nullable=False),
    Column("radius_m", Integer, nullable=False),
    Column("radius_assumed", Boolean, nullable=False),
    Column("computed_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("platform", "external_id", "origin"),
    schema=SCHEMA,
)


class OsrmRoutingService:
    """``/table/v1/driving`` with one source: durations and distances to many destinations."""

    def __init__(
        self,
        base_url: str,
        timeout_s: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._transport = transport  # tests pass a MockTransport

    async def legs(self, origin: GeoPoint, destinations: Sequence[GeoPoint]) -> list[Leg | None]:
        found: list[Leg | None] = []
        async with httpx.AsyncClient(timeout=self._timeout_s, transport=self._transport) as client:
            for start in range(0, len(destinations), TABLE_BATCH):
                found.extend(
                    await self._batch(client, origin, destinations[start : start + TABLE_BATCH])
                )
        return found

    async def _batch(
        self, client: httpx.AsyncClient, origin: GeoPoint, destinations: Sequence[GeoPoint]
    ) -> list[Leg | None]:
        coordinates = ";".join(f"{p.lon:.6f},{p.lat:.6f}" for p in (origin, *destinations))
        response = await client.get(
            f"{self._base_url}/table/v1/driving/{coordinates}",
            params={"sources": "0", "annotations": "duration,distance"},
        )
        response.raise_for_status()
        body = response.json()
        if body.get("code") != "Ok":
            raise RuntimeError(f"OSRM table failed: {body.get('code')} {body.get('message')}")
        durations, distances = body["durations"][0][1:], body["distances"][0][1:]
        return [
            Leg(float(s), float(m)) if s is not None and m is not None else None
            for s, m in zip(durations, distances, strict=True)
        ]


def load_origin(path: Path) -> Origin:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)["origin"]
        return Origin(
            data["slug"], data["name_fa"], GeoPoint(data["lat"], data["lon"]), data["source"]
        )
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError, ValueError) as error:
        raise ConfigurationError(f"invalid routing file {path}: {error}") from None


class PgDriveTimeStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def replace(self, platform: str, origin: str, rows: Sequence[DriveTime]) -> None:
        values = [
            {
                "platform": r.listing_id.platform,
                "external_id": r.listing_id.external_id,
                "origin": r.origin,
                "dataset": r.dataset,
                "center_s": r.center.seconds if r.center else None,
                "center_m": r.center.meters if r.center else None,
                "low_s": r.low_s,
                "high_s": r.high_s,
                "routed_points": r.routed_points,
                "radius_m": r.blur.radius_m,
                "radius_assumed": r.blur.assumed,
                "computed_at": r.computed_at,
            }
            for r in rows
        ]
        async with self._engine.begin() as conn:
            await conn.execute(
                delete(drive_time).where(
                    (drive_time.c.platform == platform) & (drive_time.c.origin == origin)
                )
            )
            for start in range(0, len(values), DB_BATCH):
                await conn.execute(insert(drive_time), values[start : start + DB_BATCH])

    async def of_platform(self, platform: str, origin: str) -> dict[ListingId, DriveTime]:
        query = select(drive_time).where(
            (drive_time.c.platform == platform) & (drive_time.c.origin == origin)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return {ListingId(r.platform, r.external_id): _drive(r) for r in rows}

    async def get(self, listing_id: ListingId, origin: str) -> DriveTime | None:
        query = select(drive_time).where(
            (drive_time.c.platform == listing_id.platform)
            & (drive_time.c.external_id == listing_id.external_id)
            & (drive_time.c.origin == origin)
        )
        async with self._engine.connect() as conn:
            row = (await conn.execute(query)).one_or_none()
        return _drive(row) if row is not None else None


def _drive(r: Row[Any]) -> DriveTime:
    return DriveTime(
        ListingId(r.platform, r.external_id),
        r.origin,
        r.dataset,
        Leg(r.center_s, r.center_m) if r.center_s is not None else None,
        r.low_s,
        r.high_s,
        r.routed_points,
        Blur(r.radius_m, r.radius_assumed),
        r.computed_at,
    )
