"""Postgres stores for candidates, the labelling queue and labels."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.catalog.domain.listing import ListingId
from villasanj.entity_resolution.application.ports import MatchRun, ScoredCandidate
from villasanj.entity_resolution.domain.clustering import CanonicalVilla, VillaEvent
from villasanj.entity_resolution.domain.evidence import PairEvidence, PhotoEvidence
from villasanj.entity_resolution.domain.labels import Label, PairLabel, QueueItem
from villasanj.entity_resolution.domain.pairs import BlockingSource, PairKey
from villasanj.entity_resolution.domain.scoring import Contribution, Score
from villasanj.entity_resolution.infrastructure.tables import (
    candidate,
    label,
    queue_item,
    run,
    villa,
    villa_event,
    villa_member,
)
from villasanj.shared.application.clock import Clock

_BATCH = 2000


def _pair_columns(key: PairKey) -> dict[str, str]:
    return {
        "left_platform": key.left.platform,
        "left_id": key.left.external_id,
        "right_platform": key.right.platform,
        "right_id": key.right.external_id,
    }


def _pair_key(row: Any) -> PairKey:
    return PairKey(
        ListingId(row.left_platform, row.left_id), ListingId(row.right_platform, row.right_id)
    )


def _evidence(data: dict[str, Any] | None) -> PairEvidence | None:
    if data is None:
        return None
    return PairEvidence(**{**data, "photos": PhotoEvidence(**data["photos"])})


def _score(value: float | None, parts: list[list[Any]] | None) -> Score | None:
    if value is None:
        return None
    return Score(value, tuple(Contribution(str(f), float(p)) for f, p in parts or []))


class PgCandidateStore:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def replace(self, match_run: MatchRun, candidates: Sequence[ScoredCandidate]) -> None:
        run_id = uuid.UUID(match_run.id)
        rows = [
            {
                **_pair_columns(c.key),
                "run_id": run_id,
                "sources": sorted(s.value for s in c.sources),
                "blocked": c.blocked,
                "score": c.score.value if c.score else None,
                "evidence": asdict(c.evidence) if c.evidence else None,
                "contributions": (
                    [[p.feature, p.points] for p in c.score.contributions] if c.score else None
                ),
            }
            for c in candidates
        ]
        async with self._engine.begin() as conn:
            await conn.execute(
                run.insert().values(
                    id=run_id,
                    dataset_hash=match_run.dataset_hash,
                    config=match_run.config,
                    counts=match_run.counts,
                    created_at=match_run.created_at,
                )
            )
            await conn.execute(delete(candidate))
            for start in range(0, len(rows), _BATCH):
                await conn.execute(insert(candidate).values(rows[start : start + _BATCH]))

    async def current(self) -> list[ScoredCandidate]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(candidate))).all()
        return [self._candidate(row) for row in rows]

    async def get(self, key: PairKey) -> ScoredCandidate | None:
        columns = _pair_columns(key)
        query = select(candidate).where(*(candidate.c[k] == v for k, v in columns.items()))
        async with self._engine.connect() as conn:
            row = (await conn.execute(query)).first()
        return self._candidate(row) if row is not None else None

    async def latest_run(self) -> MatchRun | None:
        query = select(run).order_by(run.c.created_at.desc()).limit(1)
        async with self._engine.connect() as conn:
            row = (await conn.execute(query)).first()
        if row is None:
            return None
        return MatchRun(str(row.id), row.dataset_hash, row.config, row.counts, row.created_at)

    @staticmethod
    def _candidate(row: Any) -> ScoredCandidate:
        return ScoredCandidate(
            key=_pair_key(row),
            sources=frozenset(BlockingSource(s) for s in row.sources),
            blocked=row.blocked,
            evidence=_evidence(row.evidence),
            score=_score(row.score, row.contributions),
        )


class PgLabelStore:
    def __init__(self, engine: AsyncEngine, clock: Clock) -> None:
        self._engine = engine
        self._clock = clock

    async def save_queue(self, queue: str, items: Sequence[QueueItem]) -> None:
        now = self._clock.now()
        rows = [
            {
                "queue": queue,
                "position": item.position,
                **_pair_columns(item.key),
                "stratum": item.stratum,
                "stratum_size": item.stratum_size,
                "created_at": now,
            }
            for item in items
        ]
        if rows:
            async with self._engine.begin() as conn:
                await conn.execute(insert(queue_item).values(rows))

    async def queue(self, queue: str) -> list[QueueItem]:
        query = (
            select(queue_item).where(queue_item.c.queue == queue).order_by(queue_item.c.position)
        )
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [QueueItem(r.position, _pair_key(r), r.stratum, r.stratum_size) for r in rows]

    async def save_label(self, decision: PairLabel) -> None:
        values = {
            **_pair_columns(decision.key),
            "labeler": decision.labeler,
            "label": decision.label.value,
            "labeled_at": decision.labeled_at,
            "seconds": decision.seconds,
        }
        statement = insert(label).values(values)
        upsert = statement.on_conflict_do_update(
            constraint="pk_label",
            set_={k: statement.excluded[k] for k in ("label", "labeled_at", "seconds")},
        )
        async with self._engine.begin() as conn:
            await conn.execute(upsert)

    async def labels(self, labeler: str) -> list[PairLabel]:
        query = select(label).where(label.c.labeler == labeler).order_by(label.c.labeled_at)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        return [
            PairLabel(_pair_key(r), Label(r.label), r.labeler, r.labeled_at, r.seconds)
            for r in rows
        ]


class PgVillaStore:
    def __init__(self, engine: AsyncEngine, clock: Clock) -> None:
        self._engine = engine
        self._clock = clock

    async def current(self) -> dict[str, frozenset[ListingId]]:
        async with self._engine.connect() as conn:
            rows = (await conn.execute(select(villa_member))).all()
        members: dict[str, set[ListingId]] = {}
        for row in rows:
            members.setdefault(row.villa_id, set()).add(ListingId(row.platform, row.external_id))
        return {villa_id: frozenset(group) for villa_id, group in members.items()}

    async def replace(
        self, run_id: str, villas: Sequence[CanonicalVilla], events: Sequence[VillaEvent]
    ) -> None:
        now = self._clock.now()
        run_uuid = uuid.UUID(run_id)
        members = [
            {"villa_id": v.id, "platform": m.platform, "external_id": m.external_id}
            for v in villas
            for m in sorted(v.members)
        ]
        async with self._engine.begin() as conn:
            await conn.execute(delete(villa))  # members cascade
            if villas:
                await conn.execute(
                    insert(villa).values(
                        [{"id": v.id, "run_id": run_uuid, "updated_at": now} for v in villas]
                    )
                )
            for start in range(0, len(members), _BATCH):
                await conn.execute(insert(villa_member).values(members[start : start + _BATCH]))
            if events:
                await conn.execute(
                    insert(villa_event).values(
                        [
                            {
                                "run_id": run_uuid,
                                "kind": e.kind.value,
                                "villa_id": e.villa_id,
                                "previous_ids": list(e.previous_ids),
                                "created_at": now,
                            }
                            for e in events
                        ]
                    )
                )

    async def villa_of(self, listing: ListingId) -> CanonicalVilla | None:
        owner = (
            select(villa_member.c.villa_id)
            .where(
                villa_member.c.platform == listing.platform,
                villa_member.c.external_id == listing.external_id,
            )
            .scalar_subquery()
        )
        query = select(villa_member).where(villa_member.c.villa_id == owner)
        async with self._engine.connect() as conn:
            rows = (await conn.execute(query)).all()
        if not rows:
            return None
        return CanonicalVilla(
            rows[0].villa_id, frozenset(ListingId(r.platform, r.external_id) for r in rows)
        )
