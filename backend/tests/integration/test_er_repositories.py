"""Embedding, candidate, queue and label stores against a real Postgres."""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fakes.ingestion import SteppingClock
from tests.fakes.llm import NOW
from villasanj.catalog.domain.listing import ListingId
from villasanj.catalog.domain.photo import ListingPhoto, PerceptualFingerprint, PhotoEmbedding
from villasanj.catalog.infrastructure.repositories import PgEmbeddingStore, PgPhotoRepository
from villasanj.entity_resolution.application.ports import MatchRun, ScoredCandidate
from villasanj.entity_resolution.domain.evidence import PairEvidence, PhotoEvidence
from villasanj.entity_resolution.domain.labels import Label, LabelRevision, PairLabel, QueueItem
from villasanj.entity_resolution.domain.pairs import BlockingSource, PairKey
from villasanj.entity_resolution.domain.scoring import Contribution, Score
from villasanj.entity_resolution.infrastructure.repositories import PgCandidateStore, PgLabelStore

pytestmark = pytest.mark.integration


async def test_embeddings_are_stored_once_per_image_and_model(engine: AsyncEngine) -> None:
    store = PgEmbeddingStore(engine, SteppingClock())
    model = f"model-{id(engine)}"
    rows = [
        PhotoEmbedding("a" * 64, model, (0.6, 0.8)),
        PhotoEmbedding("b" * 64, model, (1.0, 0.0)),
    ]
    await store.save(rows)
    await store.save(rows[:1])  # idempotent
    await store.save([])
    assert await store.embedded(model) == {"a" * 64, "b" * 64}
    vectors = await store.vectors(model)
    assert vectors["a" * 64] == pytest.approx((0.6, 0.8))
    assert await store.embedded("other-model") == set()


async def test_photos_read_back_in_listing_order(engine: AsyncEngine) -> None:
    platform = f"photos-{id(engine)}"
    repo = PgPhotoRepository(engine)
    for position in (1, 0):
        await repo.save(
            ListingPhoto(
                ListingId(platform, "7"),
                position,
                f"https://c.test/{position}.jpg",
                "00000000-0000-0000-0000-000000000901",
                f"{position}" * 64,
                PerceptualFingerprint(-5, 7, 640, 480),
                NOW,
            )
        )
    photos = await repo.photos([platform])
    assert [p.position for p in photos] == [0, 1]
    assert photos[0].fingerprint == PerceptualFingerprint(-5, 7, 640, 480)


def candidate(key: PairKey, value: float | None) -> ScoredCandidate:
    evidence = PairEvidence(PhotoEvidence(5, 4, 2, 1, 2.5, 0.97, 3), 120.0, 0, 1, 2, 0.8, 1.2, 0.4)
    return ScoredCandidate(
        key,
        frozenset({BlockingSource.PHOTO_HASH, BlockingSource.GEO_ROOMS}),
        value is not None,
        evidence if value is not None else None,
        Score(value, (Contribution("shared_photos", value),)) if value is not None else None,
    )


async def test_candidates_replace_the_previous_run(engine: AsyncEngine) -> None:
    store = PgCandidateStore(engine)
    a, b, c = ListingId("jabama", "1"), ListingId("shab", "2"), ListingId("shab", "3")
    first = MatchRun("00000000-0000-0000-0000-00000000a001", "h1", {"x": 1}, {"total": 2}, NOW)
    await store.replace(
        first, [candidate(PairKey.of(a, b), 6.25), candidate(PairKey.of(a, c), None)]
    )
    assert {x.key for x in await store.current()} == {PairKey.of(a, b), PairKey.of(a, c)}
    stored = await store.get(PairKey.of(a, b))
    assert stored == candidate(PairKey.of(a, b), 6.25)
    second = MatchRun(
        "00000000-0000-0000-0000-00000000a002", "h2", {}, {"total": 1}, NOW + timedelta(hours=1)
    )
    await store.replace(second, [candidate(PairKey.of(a, c), 1.0)])
    assert [x.key for x in await store.current()] == [PairKey.of(a, c)]
    assert await store.get(PairKey.of(a, b)) is None
    latest = await store.latest_run()
    assert latest is not None
    assert (latest.id, latest.dataset_hash) == (second.id, "h2")


async def test_queue_and_labels_round_trip(engine: AsyncEngine) -> None:
    labels = PgLabelStore(engine, SteppingClock())
    queue = f"q-{id(engine)}"
    key = PairKey.of(ListingId("jabama", "1"), ListingId("shab", "2"))
    other = PairKey.of(ListingId("jabama", "3"), ListingId("shab", "4"))
    await labels.save_queue(
        queue, [QueueItem(0, key, "photo:band10", 300), QueueItem(1, other, "wide", 9000)]
    )
    assert [i.key for i in await labels.queue(queue)] == [key, other]
    assert (await labels.queue(queue))[1].stratum_size == 9000
    await labels.save_queue(f"{queue}-empty", [])
    await labels.save_label(PairLabel(key, Label.MATCH, "owner", NOW, 3.5))
    await labels.save_label(PairLabel(key, Label.UNSURE, "owner", NOW + timedelta(minutes=1), None))
    await labels.save_label(PairLabel(key, Label.NON_MATCH, "second-opinion", NOW))
    owner = await labels.labels("owner")
    assert [(x.key, x.label, x.seconds) for x in owner] == [(key, Label.UNSURE, None)]


async def test_a_revision_changes_the_label_and_keeps_the_original(engine: AsyncEngine) -> None:
    labels = PgLabelStore(engine, SteppingClock())
    key = PairKey.of(ListingId("jabama", "r1"), ListingId("shab", "r2"))
    who = f"owner-{id(engine)}"
    await labels.save_label(PairLabel(key, Label.MATCH, who, NOW, 2.0))
    revision = LabelRevision(key, who, Label.MATCH, Label.NON_MATCH, "units 2 and 4", "agent", NOW)
    await labels.revise(revision)
    ((now,),) = [[x.label for x in await labels.labels(who)]]
    assert now is Label.NON_MATCH
    assert await labels.revisions(who) == [revision]
    with pytest.raises(ValueError, match="is not labelled match"):
        await labels.revise(revision)  # the label no longer says "match": nothing changes
    assert len(await labels.revisions(who)) == 1
