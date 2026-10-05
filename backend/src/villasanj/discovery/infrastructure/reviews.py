"""Review queues and the owner's labels in Postgres (``discovery`` schema), and the draft loader."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.discovery.application.reviews import (
    DraftCase,
    InvalidIntent,
    ReviewCase,
    normalize_intent,
)
from villasanj.shared.application.errors import ConfigurationError

SCHEMA = "discovery"
metadata = MetaData(naming_convention={"pk": "pk_%(table_name)s"})

review_case = Table(
    "review_case",
    metadata,
    Column("queue", Text, nullable=False),
    Column("position", Integer, nullable=False),
    Column("kind", Text, nullable=False),  # "query" | "relevance"
    Column("payload", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("queue", "position"),
    schema=SCHEMA,
)
review_label = Table(
    "review_label",
    metadata,
    Column("queue", Text, nullable=False),
    Column("position", Integer, nullable=False),
    Column("item", Text, nullable=False),  # "" for a whole case; a listing key for relevance
    Column("labeler", Text, nullable=False),
    Column("value", JSONB, nullable=False),
    Column("labeled_at", DateTime(timezone=True), nullable=False),
    PrimaryKeyConstraint("queue", "position", "item", "labeler"),
    schema=SCHEMA,
)


class PgReviewStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def cases(self, queue: str) -> list[ReviewCase]:
        query = (
            select(review_case.c.position, review_case.c.payload)
            .where(review_case.c.queue == queue)
            .order_by(review_case.c.position)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [ReviewCase(r.position, r.payload) for r in rows]

    async def save_cases(
        self, queue: str, kind: str, cases: Sequence[ReviewCase], at: datetime
    ) -> None:
        values = [
            {
                "queue": queue,
                "position": c.position,
                "kind": kind,
                "payload": dict(c.payload),
                "created_at": at,
            }
            for c in cases
        ]
        async with self._engine.begin() as conn:
            await conn.execute(insert(review_case), values)

    async def labels(self, queue: str, labeler: str) -> dict[tuple[int, str], dict[str, object]]:
        query = select(review_label.c.position, review_label.c.item, review_label.c.value).where(
            review_label.c.queue == queue, review_label.c.labeler == labeler
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return {(r.position, r.item): dict(r.value) for r in rows}

    async def save_label(
        self,
        queue: str,
        position: int,
        item: str,
        labeler: str,
        value: Mapping[str, object],
        at: datetime,
    ) -> None:
        statement = insert(review_label).values(
            queue=queue,
            position=position,
            item=item,
            labeler=labeler,
            value=dict(value),
            labeled_at=at,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["queue", "position", "item", "labeler"],
            set_={"value": statement.excluded.value, "labeled_at": statement.excluded.labeled_at},
        )
        async with self._engine.begin() as conn:
            await conn.execute(statement)


def load_drafts(path: Path) -> list[DraftCase]:
    """JSON lines of ``{"query", "expected", "note"}``; ``//`` lines are comments."""
    drafts = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ConfigurationError(f"cannot read {path}: {error}") from None
    for number, line in enumerate(lines, start=1):
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        try:
            item = json.loads(line)
            drafts.append(
                DraftCase(
                    str(item["query"]),
                    normalize_intent(item["expected"]),
                    str(item.get("note", "")),
                )
            )
        except (json.JSONDecodeError, KeyError, TypeError, InvalidIntent) as error:
            raise ConfigurationError(f"{path}:{number}: invalid case: {error}") from None
    return drafts


def write_cases(path: Path, cases: Sequence[DraftCase], header: Sequence[str]) -> None:
    """The reviewed eval set, in the format ``load_cases`` reads."""
    lines = [f"// {h}" for h in header]
    lines += [
        json.dumps({"query": c.query, "expected": c.expected, "note": c.note}, ensure_ascii=False)
        for c in cases
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_queries(path: Path) -> list[str]:
    """One query per line; ``//`` lines are comments."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ConfigurationError(f"cannot read {path}: {error}") from None
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("//")]
