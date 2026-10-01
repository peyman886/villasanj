"""Photo tags: scored once per image and model, a stratified queue, labels and the eval."""

from collections.abc import Sequence
from datetime import datetime

import pytest

from tests.fakes.ingestion import InMemoryBlobStore, InMemorySnapshotRepository
from tests.fakes.llm import FixedClock
from tests.unit.catalog.test_embeddings import store_photo
from villasanj.enrichment.application.photo_tags import (
    MIDDLE,
    REST,
    TOP,
    BuildPhotoTagQueue,
    EvaluatePhotoTags,
    PhotoLabeling,
    PhotoQueueExists,
    QueuedPhoto,
    TagPhotos,
    TagScore,
    draw_queue,
)
from villasanj.enrichment.domain.photo_tags import PhotoTag
from villasanj.enrichment.infrastructure.siglip import SigLip2Tagger

MODEL = "fake@1#prompts-1"


class FakeTagger:
    model_id = MODEL

    def __init__(self) -> None:
        self.calls: list[int] = []

    async def scores(self, images: Sequence[bytes]) -> list[dict[PhotoTag, float] | None]:
        self.calls.append(len(images))
        return [
            None if i == b"broken" else {PhotoTag.POOL: 0.2, PhotoTag.FOREST: 0.01} for i in images
        ]


class Scores:
    def __init__(self, preset: dict[str, dict[PhotoTag, float]] | None = None) -> None:
        self.rows: dict[tuple[str, str], dict[PhotoTag, float]] = {}
        for sha, scores in (preset or {}).items():
            self.rows[(sha, MODEL)] = scores

    async def scored(self, model: str) -> set[str]:
        return {sha for sha, m in self.rows if m == model}

    async def save(self, rows: Sequence[TagScore]) -> None:
        for r in rows:
            self.rows.setdefault((r.sha256, r.model), {})[r.tag] = r.score

    async def scores(self, model: str) -> dict[str, dict[PhotoTag, float]]:
        return {sha: s for (sha, m), s in self.rows.items() if m == model}


class Queues:
    def __init__(self) -> None:
        self.queue: list[QueuedPhoto] = []
        self.labelled: dict[tuple[str, str, str], frozenset[PhotoTag]] = {}

    async def exists(self, queue: str) -> bool:
        return any(i.queue == queue for i in self.queue)

    async def save(self, items: Sequence[QueuedPhoto], created_at: datetime) -> None:
        self.queue.extend(items)

    async def items(self, queue: str) -> list[QueuedPhoto]:
        return [i for i in self.queue if i.queue == queue]

    async def labels(self, queue: str, labeler: str) -> dict[str, frozenset[PhotoTag]]:
        return {
            sha: tags
            for (q, sha, who), tags in self.labelled.items()
            if q == queue and who == labeler
        }

    async def save_label(
        self, queue: str, sha256: str, present: frozenset[PhotoTag], labeler: str, at: datetime
    ) -> None:
        self.labelled[(queue, sha256, labeler)] = present


class Urls:
    async def urls(self, sha256s: Sequence[str]) -> dict[str, str]:
        return {s: f"https://cdn.test/{s}.jpg" for s in sha256s if not s.startswith("orphan")}


async def test_each_image_is_scored_once_per_model() -> None:
    snapshots, blobs, store, tagger = (
        InMemorySnapshotRepository(),
        InMemoryBlobStore(),
        Scores(),
        FakeTagger(),
    )
    await store_photo(snapshots, blobs, "/a.jpg", b"same-image")
    await store_photo(snapshots, blobs, "/b.jpg", b"same-image")
    await store_photo(snapshots, blobs, "/c.jpg", b"broken")
    await store_photo(snapshots, blobs, "/d.jpg", b"gone", status=404)
    use_case = TagPhotos(snapshots, blobs, tagger, store, FixedClock(), batch_size=1)
    first = await use_case.run(["example"])
    assert (first.images, first.scored, first.unreadable) == (2, 1, 1)
    second = await use_case.run(["example"])
    assert (second.already_scored, second.scored) == (1, 0)  # only the broken one is tried again
    assert tagger.calls == [1, 1, 1]
    (scores,) = (await store.scores(MODEL)).values()
    assert scores == {PhotoTag.POOL: 0.2, PhotoTag.FOREST: 0.01}


def ranked_scores(count: int) -> dict[str, dict[PhotoTag, float]]:
    return {f"{i:04d}": dict.fromkeys(PhotoTag, (count - i) / count) for i in range(count)}


def test_the_queue_mixes_top_middle_and_rest_per_tag_and_is_deterministic() -> None:
    scores = ranked_scores(1000)
    drawn = draw_queue("photos-v1", scores)
    assert drawn == draw_queue("photos-v1", scores)
    assert draw_queue("photos-v2", scores) != drawn
    assert len({sha for sha, _ in drawn}) == len(drawn)  # each photo once
    strata = [stratum for _, stratum in drawn]
    # Every tag ranks the same here, so the first tag takes the top 20 and later ones get less.
    assert strata.count("pool:top") == TOP
    assert strata.count("pool:middle") == MIDDLE
    assert strata.count("pool:rest") == REST
    assert len(drawn) == len(PhotoTag) * (MIDDLE + REST) + TOP  # later tags' top is taken


async def test_a_queue_is_drawn_once_and_skips_photos_without_a_url() -> None:
    scores = ranked_scores(50) | {"orphan": dict.fromkeys(PhotoTag, 0.99)}
    queues = Queues()
    build = BuildPhotoTagQueue(Scores(scores), Urls(), queues, FixedClock(), MODEL)
    items = await build.run("photos-v1")
    assert [i.position for i in items] == list(range(1, len(items) + 1))
    assert all(i.url.startswith("https://cdn.test/") for i in items)
    assert "orphan" not in {i.sha256 for i in items}
    with pytest.raises(PhotoQueueExists):
        await build.run("photos-v1")


async def test_labelling_walks_the_queue_and_the_eval_uses_the_labels() -> None:
    scores = {f"{i:02d}": {PhotoTag.POOL: 1 - i / 30} for i in range(30)}
    queues = Queues()
    queues.queue = [
        QueuedPhoto("q", i + 1, sha, f"u{sha}", "pool:top") for i, sha in enumerate(scores)
    ]
    labeling = PhotoLabeling(queues, FixedClock())
    first = await labeling.task("q", "owner")
    assert first is not None
    assert (first.item.position, first.labelled, first.done) == (1, 0, False)
    for sha in scores:  # the 15 best-scored photos show a pool
        await labeling.label(
            "q", sha, frozenset({PhotoTag.POOL}) if int(sha) < 15 else frozenset(), "owner"
        )
    last = await labeling.task("q", "owner")
    assert last is not None
    assert last.done
    again = await labeling.task("q", "owner", position=3)
    assert again is not None
    assert again.present == frozenset({PhotoTag.POOL})
    assert await labeling.task("missing", "owner") is None
    evaluation = await EvaluatePhotoTags(Scores(scores), queues, MODEL).run("q", "owner")
    pool = next(t for t in evaluation.thresholds if t.tag is PhotoTag.POOL)
    assert evaluation.labelled_photos == 30
    assert pool.threshold == pytest.approx(1 - 14 / 30)
    assert pool.precision is not None
    assert pool.precision.estimate == 1.0
    fireplace = next(t for t in evaluation.thresholds if t.tag is PhotoTag.FIREPLACE)
    assert fireplace.threshold is None  # no positives: not used


def test_the_tagger_id_pins_model_revision_and_prompts_without_loading() -> None:
    assert SigLip2Tagger().model_id == "google/siglip2-base-patch16-224@75de2d55ec2d#prompts-1"
