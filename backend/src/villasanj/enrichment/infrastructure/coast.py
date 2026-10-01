"""The coastline in PostGIS (OSM ``natural=coastline`` lines) and the stored coast distances."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

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
    text,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.coast import CoastDistance
from villasanj.enrichment.domain.geo import Blur
from villasanj.shared.domain.geo import GeoPoint

SCHEMA = "enrichment"
BATCH = 1000
metadata = MetaData(naming_convention={"pk": "pk_%(table_name)s"})

coast_distance = Table(
    "coast_distance",
    metadata,
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("dataset", Text, nullable=False),
    Column("center_m", Float, nullable=False),
    Column("low_m", Float, nullable=False),
    Column("high_m", Float, nullable=False),
    Column("radius_m", Integer, nullable=False),
    Column("radius_assumed", Boolean, nullable=False),
    Column("computed_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("platform", "external_id"),
    schema=SCHEMA,
)

_INSERT_LINE = text(
    "INSERT INTO enrichment.coastline (osm_way_id, dataset, geom) "
    "VALUES (:way, :dataset, ST_GeomFromGeoJSON(:geometry)::geography) "
    "ON CONFLICT (dataset, osm_way_id) DO UPDATE SET geom = EXCLUDED.geom"
)
_DISTANCES = text(
    """
    SELECT p.i, (
        SELECT min(ST_Distance(c.geom, p.g))
        FROM enrichment.coastline c
        WHERE c.dataset = :dataset AND ST_DWithin(c.geom, p.g, :max_m)
    ) AS distance
    FROM (
        SELECT i, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography AS g
        FROM unnest(CAST(:ids AS int[]), CAST(:lons AS float8[]), CAST(:lats AS float8[]))
            AS t(i, lon, lat)
    ) p
    ORDER BY p.i
    """
)


class PgCoastline:
    """``natural=coastline`` lines of one OSM snapshot (``dataset``), queried with PostGIS."""

    def __init__(self, engine: AsyncEngine, dataset: str) -> None:
        self._engine = engine
        self._dataset = dataset

    async def load(self, geojsonseq_lines: Sequence[str]) -> int:
        """Load the lines ``osmium export -f geojsonseq --add-unique-id=type_id`` wrote."""
        rows = []
        for line in geojsonseq_lines:
            if not line.strip():
                continue
            feature = json.loads(line.lstrip("\x1e"))  # RFC 8142 record separator
            geometry = feature.get("geometry") or {}
            if geometry.get("type") != "LineString" or not str(feature.get("id", "")).startswith(
                "w"
            ):
                continue
            way = int(str(feature["id"])[1:])
            rows.append({"way": way, "dataset": self._dataset, "geometry": json.dumps(geometry)})
        async with self._engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM enrichment.coastline WHERE dataset = :dataset"),
                {"dataset": self._dataset},
            )
            for start in range(0, len(rows), BATCH):
                await conn.execute(_INSERT_LINE, rows[start : start + BATCH])
        return len(rows)

    async def distances_m(self, points: Sequence[GeoPoint], max_m: float) -> list[float | None]:
        found: list[float | None] = []
        async with self._engine.connect() as conn:
            for start in range(0, len(points), BATCH):
                part = points[start : start + BATCH]
                result = await conn.execute(
                    _DISTANCES,
                    {
                        "dataset": self._dataset,
                        "max_m": max_m,
                        "ids": list(range(len(part))),
                        "lons": [p.lon for p in part],
                        "lats": [p.lat for p in part],
                    },
                )
                found.extend(
                    float(row.distance) if row.distance is not None else None for row in result
                )
        return found


class PgCoastDistanceStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def replace(self, platform: str, rows: Sequence[CoastDistance]) -> None:
        values = [
            {
                "platform": r.listing_id.platform,
                "external_id": r.listing_id.external_id,
                "dataset": r.dataset,
                "center_m": r.center_m,
                "low_m": r.low_m,
                "high_m": r.high_m,
                "radius_m": r.blur.radius_m,
                "radius_assumed": r.blur.assumed,
                "computed_at": r.computed_at,
            }
            for r in rows
        ]
        async with self._engine.begin() as conn:
            await conn.execute(delete(coast_distance).where(coast_distance.c.platform == platform))
            for start in range(0, len(values), BATCH):
                await conn.execute(insert(coast_distance), values[start : start + BATCH])

    async def of_platform(self, platform: str) -> dict[ListingId, CoastDistance]:
        query = select(coast_distance).where(coast_distance.c.platform == platform)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return {ListingId(r.platform, r.external_id): _coast(r) for r in rows}

    async def get(self, listing_id: ListingId) -> CoastDistance | None:
        query = select(coast_distance).where(
            (coast_distance.c.platform == listing_id.platform)
            & (coast_distance.c.external_id == listing_id.external_id)
        )
        async with self._engine.connect() as conn:
            row = (await conn.execute(query)).one_or_none()
        return _coast(row) if row is not None else None


def _coast(r: Row[Any]) -> CoastDistance:
    return CoastDistance(
        ListingId(r.platform, r.external_id),
        r.dataset,
        r.center_m,
        r.low_m,
        r.high_m,
        Blur(r.radius_m, r.radius_assumed),
        r.computed_at,
    )
