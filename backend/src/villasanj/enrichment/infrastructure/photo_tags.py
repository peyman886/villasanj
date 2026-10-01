"""Photo tag scores, the labelling queue and the labels in Postgres (``enrichment`` schema)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    delete,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.enrichment.application.photo_tags import QueuedPhoto, TagScore
from villasanj.enrichment.domain.photo_tags import PhotoTag

SCHEMA = "enrichment"
BATCH = 2000
metadata = MetaData(naming_convention={"pk": "pk_%(table_name)s", "uq": "uq_%(table_name)s_photo"})

photo_tag_score = Table(
    "photo_tag_score",
    metadata,
    Column("sha256", Text, nullable=False),
    Column("model", Text, nullable=False),
    Column("tag", Text, nullable=False),
    Column("score", Float, nullable=False),
    Column("computed_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("sha256", "model", "tag"),
    schema=SCHEMA,
)
photo_tag_queue = Table(
    "photo_tag_queue",
    metadata,
    Column("queue", Text, nullable=False),
    Column("position", Integer, nullable=False),
    Column("sha256", Text, nullable=False),
    Column("url", Text, nullable=False),
    Column("stratum", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("queue", "position"),
    UniqueConstraint("queue", "sha256"),
    schema=SCHEMA,
)
photo_tag_label = Table(
    "photo_tag_label",
    metadata,
    Column("queue", Text, nullable=False),
    Column("sha256", Text, nullable=False),
    Column("tag", Text, nullable=False),
    Column("present", Boolean, nullable=False),
    Column("labeler", Text, nullable=False),
    Column("labeled_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("queue", "sha256", "tag", "labeler"),
    schema=SCHEMA,
)


class PgPhotoTagStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def scored(self, model: str) -> set[str]:
        query = select(photo_tag_score.c.sha256).where(photo_tag_score.c.model == model).distinct()
        async with self._engine.connect() as conn:
            return {row.sha256 for row in await conn.execute(query)}

    async def save(self, rows: Sequence[TagScore]) -> None:
        values = [
            {
                "sha256": r.sha256,
                "model": r.model,
                "tag": r.tag.value,
                "score": r.score,
                "computed_at": r.computed_at,
            }
            for r in rows
        ]
        async with self._engine.begin() as conn:
            for start in range(0, len(values), BATCH):
                statement = insert(photo_tag_score).values(values[start : start + BATCH])
                await conn.execute(statement.on_conflict_do_nothing())

    async def scores(self, model: str) -> dict[str, dict[PhotoTag, float]]:
        query = select(photo_tag_score).where(photo_tag_score.c.model == model)
        found: dict[str, dict[PhotoTag, float]] = defaultdict(dict)
        async with self._engine.connect() as conn:
            for row in await conn.execute(query):
                found[row.sha256][PhotoTag(row.tag)] = row.score
        return dict(found)


class PgPhotoQueueStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def exists(self, queue: str) -> bool:
        query = select(func.count()).where(photo_tag_queue.c.queue == queue)
        async with self._engine.connect() as conn:
            return bool((await conn.execute(query)).scalar_one())

    async def save(self, items: Sequence[QueuedPhoto], created_at: datetime) -> None:
        values = [
            {
                "queue": i.queue,
                "position": i.position,
                "sha256": i.sha256,
                "url": i.url,
                "stratum": i.stratum,
                "created_at": created_at,
            }
            for i in items
        ]
        async with self._engine.begin() as conn:
            if values:
                await conn.execute(insert(photo_tag_queue), values)

    async def items(self, queue: str) -> list[QueuedPhoto]:
        query = (
            select(photo_tag_queue)
            .where(photo_tag_queue.c.queue == queue)
            .order_by(photo_tag_queue.c.position)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [QueuedPhoto(r.queue, r.position, r.sha256, r.url, r.stratum) for r in rows]

    async def labels(self, queue: str, labeler: str) -> dict[str, frozenset[PhotoTag]]:
        query = select(photo_tag_label).where(
            (photo_tag_label.c.queue == queue) & (photo_tag_label.c.labeler == labeler)
        )
        present: dict[str, set[PhotoTag]] = defaultdict(set)
        async with self._engine.connect() as conn:
            for row in await conn.execute(query):
                tags = present[row.sha256]
                if row.present:
                    tags.add(PhotoTag(row.tag))
        return {sha: frozenset(tags) for sha, tags in present.items()}

    async def save_label(
        self, queue: str, sha256: str, present: frozenset[PhotoTag], labeler: str, at: datetime
    ) -> None:
        values = [
            {
                "queue": queue,
                "sha256": sha256,
                "tag": tag.value,
                "present": tag in present,
                "labeler": labeler,
                "labeled_at": at,
            }
            for tag in PhotoTag
        ]
        async with self._engine.begin() as conn:
            await conn.execute(
                delete(photo_tag_label).where(
                    (photo_tag_label.c.queue == queue)
                    & (photo_tag_label.c.sha256 == sha256)
                    & (photo_tag_label.c.labeler == labeler)
                )
            )
            await conn.execute(insert(photo_tag_label), values)
