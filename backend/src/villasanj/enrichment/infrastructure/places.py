"""OSM places in PostGIS (points and areas of one snapshot) and the stored distances to them."""

from __future__ import annotations

import json
from collections.abc import Collection, Sequence
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
from villasanj.enrichment.application.places import Nearest, PlaceDistance
from villasanj.enrichment.domain.geo import Blur
from villasanj.enrichment.domain.places import PlaceKind, kind_of
from villasanj.shared.domain.geo import GeoPoint

SCHEMA = "enrichment"
BATCH = 1000
_AREAS = ("Point", "Polygon", "MultiPolygon")  # osmium also writes closed ways as lines: skipped
metadata = MetaData(naming_convention={"pk": "pk_%(table_name)s"})

place_distance = Table(
    "place_distance",
    metadata,
    Column("platform", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("kind", Text, nullable=False),
    Column("dataset", Text, nullable=False),
    Column("center_m", Float, nullable=False),
    Column("low_m", Float, nullable=False),
    Column("high_m", Float, nullable=False),
    Column("radius_m", Integer, nullable=False),
    Column("radius_assumed", Boolean, nullable=False),
    Column("nearest_name", Text),
    Column("computed_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("platform", "external_id", "kind"),
    schema=SCHEMA,
)

_INSERT = text(
    "INSERT INTO enrichment.place (dataset, osm_id, kind, name, geom) "
    "VALUES (:dataset, :osm_id, :kind, :name, ST_GeomFromGeoJSON(:geometry)::geography) "
    "ON CONFLICT DO NOTHING"
)
_NEAREST = text(
    """
    SELECT p.i, n.distance, n.name
    FROM (
        SELECT i, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography AS g
        FROM unnest(CAST(:ids AS int[]), CAST(:lons AS float8[]), CAST(:lats AS float8[]))
            AS t(i, lon, lat)
    ) p
    LEFT JOIN LATERAL (
        SELECT ST_Distance(x.geom, p.g) AS distance, x.name
        FROM enrichment.place x
        WHERE x.dataset = :dataset AND x.kind = :kind AND ST_DWithin(x.geom, p.g, :max_m)
        ORDER BY ST_Distance(x.geom, p.g)
        LIMIT 1
    ) n ON true
    ORDER BY p.i
    """
)


class PgPlaces:
    """The places of one OSM snapshot (``dataset``) that distance claims can name."""

    def __init__(self, engine: AsyncEngine, dataset: str) -> None:
        self._engine = engine
        self._dataset = dataset

    async def load(self, geojsonseq_lines: Sequence[str], city_names: Collection[str]) -> int:
        """Load what ``osmium export -f geojsonseq --add-unique-id=type_id`` wrote."""
        rows = []
        for line in geojsonseq_lines:
            if not line.strip():
                continue
            feature = json.loads(line.lstrip("\x1e"))  # RFC 8142 record separator
            geometry = feature.get("geometry") or {}
            if geometry.get("type") not in _AREAS:
                continue
            tags = {k: str(v) for k, v in (feature.get("properties") or {}).items()}
            kind = kind_of(tags, city_names)
            if kind is None:
                continue
            rows.append(
                {
                    "dataset": self._dataset,
                    "osm_id": str(feature.get("id", "")),
                    "kind": kind.value,
                    "name": tags.get("name"),
                    "geometry": json.dumps(geometry),
                }
            )
        async with self._engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM enrichment.place WHERE dataset = :dataset"),
                {"dataset": self._dataset},
            )
            for start in range(0, len(rows), BATCH):
                await conn.execute(_INSERT, rows[start : start + BATCH])
        return len(rows)

    async def nearest(
        self, points: Sequence[GeoPoint], kind: PlaceKind, max_m: float
    ) -> list[Nearest | None]:
        found: list[Nearest | None] = []
        async with self._engine.connect() as conn:
            for start in range(0, len(points), BATCH):
                part = points[start : start + BATCH]
                result = await conn.execute(
                    _NEAREST,
                    {
                        "dataset": self._dataset,
                        "kind": kind.value,
                        "max_m": max_m,
                        "ids": list(range(len(part))),
                        "lons": [p.lon for p in part],
                        "lats": [p.lat for p in part],
                    },
                )
                found.extend(
                    Nearest(float(row.distance), row.name) if row.distance is not None else None
                    for row in result
                )
        return found


class PgPlaceDistanceStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def replace(self, platform: str, rows: Sequence[PlaceDistance]) -> None:
        values = [
            {
                "platform": r.listing_id.platform,
                "external_id": r.listing_id.external_id,
                "kind": r.kind.value,
                "dataset": r.dataset,
                "center_m": r.center_m,
                "low_m": r.low_m,
                "high_m": r.high_m,
                "radius_m": r.blur.radius_m,
                "radius_assumed": r.blur.assumed,
                "nearest_name": r.nearest_name,
                "computed_at": r.computed_at,
            }
            for r in rows
        ]
        async with self._engine.begin() as conn:
            await conn.execute(delete(place_distance).where(place_distance.c.platform == platform))
            for start in range(0, len(values), BATCH):
                await conn.execute(insert(place_distance), values[start : start + BATCH])

    async def get(self, listing_id: ListingId) -> dict[PlaceKind, PlaceDistance]:
        query = select(place_distance).where(
            (place_distance.c.platform == listing_id.platform)
            & (place_distance.c.external_id == listing_id.external_id)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return {PlaceKind(r.kind): _distance(r) for r in rows}

    async def of_platform(self, platform: str) -> dict[ListingId, dict[PlaceKind, PlaceDistance]]:
        query = select(place_distance).where(place_distance.c.platform == platform)
        found: dict[ListingId, dict[PlaceKind, PlaceDistance]] = {}
        async with self._engine.connect() as conn:
            for r in await conn.execute(query):
                found.setdefault(ListingId(r.platform, r.external_id), {})[PlaceKind(r.kind)] = (
                    _distance(r)
                )
        return found


def _distance(r: Row[Any]) -> PlaceDistance:
    return PlaceDistance(
        ListingId(r.platform, r.external_id),
        PlaceKind(r.kind),
        r.dataset,
        r.center_m,
        r.low_m,
        r.high_m,
        Blur(r.radius_m, r.radius_assumed),
        r.nearest_name,
        r.computed_at,
    )
