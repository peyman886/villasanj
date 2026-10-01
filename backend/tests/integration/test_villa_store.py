"""Canonical villas in Postgres: the one-listing-per-platform rule is a database constraint too."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fakes.ingestion import SteppingClock
from villasanj.catalog.domain.listing import ListingId
from villasanj.entity_resolution.domain.clustering import (
    CanonicalVilla,
    VillaEvent,
    VillaEventKind,
    reconcile,
)
from villasanj.entity_resolution.infrastructure.repositories import PgVillaStore

pytestmark = pytest.mark.integration

J1, J2, S1 = ListingId("jabama", "v1"), ListingId("jabama", "v2"), ListingId("shab", "v1")


async def test_villas_round_trip_and_reconcile_against_what_is_stored(engine: AsyncEngine) -> None:
    store = PgVillaStore(engine, SteppingClock())
    first = reconcile({}, [frozenset({J1, S1}), frozenset({J2})])
    await store.replace(str(uuid.uuid4()), first.villas, first.events)
    stored = await store.current()
    assert set(stored.values()) == {frozenset({J1, S1}), frozenset({J2})}
    villa = await store.villa_of(S1)
    assert villa is not None
    assert villa.members == frozenset({J1, S1})
    assert await store.villa_of(ListingId("shab", "nope")) is None

    second = reconcile(stored, [frozenset({J1}), frozenset({S1}), frozenset({J2})])  # a split
    await store.replace(str(uuid.uuid4()), second.villas, second.events)
    assert len(await store.current()) == 3
    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT kind FROM er.villa_event"))).all()
    assert "split" in {row.kind for row in rows}
    await store.replace(str(uuid.uuid4()), [], [])
    assert await store.current() == {}


async def test_the_database_rejects_two_listings_of_one_platform_in_a_villa(
    engine: AsyncEngine,
) -> None:
    store = PgVillaStore(engine, SteppingClock())
    await store.replace(
        str(uuid.uuid4()),
        [CanonicalVilla("v-db", frozenset({J1}))],
        [VillaEvent(VillaEventKind.CREATED, "v-db")],
    )
    with pytest.raises(IntegrityError):  # bypasses the aggregate on purpose
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO er.villa_member (villa_id, platform, external_id) "
                    "VALUES ('v-db', 'jabama', 'other')"
                )
            )
