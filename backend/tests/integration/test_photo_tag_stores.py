"""Photo tag scores, queues and labels against a real Postgres."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fakes.llm import NOW
from villasanj.enrichment.application.photo_tags import QueuedPhoto, TagScore
from villasanj.enrichment.domain.photo_tags import PhotoTag
from villasanj.enrichment.infrastructure.photo_tags import PgPhotoQueueStore, PgPhotoTagStore

pytestmark = pytest.mark.integration


async def test_scores_are_kept_per_image_model_and_tag(engine: AsyncEngine) -> None:
    store = PgPhotoTagStore(engine)
    model = f"model-{id(engine)}"
    rows = [
        TagScore("a" * 64, model, PhotoTag.POOL, 0.2, NOW),
        TagScore("a" * 64, model, PhotoTag.FOREST, 0.01, NOW),
    ]
    await store.save(rows)
    await store.save(rows)  # saving again changes nothing
    assert await store.scored(model) == {"a" * 64}
    assert await store.scores(model) == {"a" * 64: {PhotoTag.POOL: 0.2, PhotoTag.FOREST: 0.01}}
    assert await store.scores("other") == {}


async def test_queues_and_labels_round_trip_and_relabelling_replaces(engine: AsyncEngine) -> None:
    store = PgPhotoQueueStore(engine)
    queue = f"photos-{id(engine)}"
    items = [QueuedPhoto(queue, 1, "b" * 64, "https://cdn.test/b.jpg", "pool:top")]
    assert not await store.exists(queue)
    await store.save(items, NOW)
    assert await store.exists(queue)
    assert await store.items(queue) == items
    await store.save_label(
        queue, "b" * 64, frozenset({PhotoTag.POOL, PhotoTag.FOREST}), "owner", NOW
    )
    await store.save_label(queue, "b" * 64, frozenset({PhotoTag.POOL}), "owner", NOW)
    assert await store.labels(queue, "owner") == {"b" * 64: frozenset({PhotoTag.POOL})}
    await store.save_label(queue, "b" * 64, frozenset(), "second", NOW)
    assert await store.labels(queue, "second") == {
        "b" * 64: frozenset()
    }  # labelled, nothing present
