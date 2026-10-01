"""EmbedPhotos: each distinct image is embedded once per model, and never again."""

import io
from collections.abc import Sequence

import pytest
from PIL import Image

from tests.fakes.ingestion import InMemoryBlobStore, InMemorySnapshotRepository, page, request
from villasanj.catalog.application.embeddings import EmbedPhotos
from villasanj.catalog.domain.photo import PhotoEmbedding
from villasanj.catalog.infrastructure.dinov2 import INPUT_SIZE, DinoV2Embedder, _pixels
from villasanj.ingestion.domain.pages import PageKind


class FakeEmbedder:
    model_id = "fake@1"

    def __init__(self) -> None:
        self.calls: list[int] = []

    async def embed(self, images: Sequence[bytes]) -> list[tuple[float, ...] | None]:
        self.calls.append(len(images))
        return [None if image == b"broken" else (1.0, 0.0) for image in images]


class FakeStore:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], PhotoEmbedding] = {}

    async def embedded(self, model_id: str) -> set[str]:
        return {sha for sha, model in self.rows if model == model_id}

    async def save(self, embeddings: Sequence[PhotoEmbedding]) -> None:
        for e in embeddings:
            self.rows[(e.sha256, e.model_id)] = e

    async def vectors(self, model_id: str) -> dict[str, tuple[float, ...]]:
        return {sha: e.vector for (sha, model), e in self.rows.items() if model == model_id}


async def store_photo(
    snapshots: InMemorySnapshotRepository,
    blobs: InMemoryBlobStore,
    path: str,
    body: bytes,
    status: int = 200,
) -> None:
    req = request(path, PageKind.PHOTO, host="cdn.example.test")
    blob = await blobs.put(body)
    await snapshots.save(page(req, status=status, body=body, content_type="image/jpeg"), blob, None)


async def test_distinct_images_are_embedded_once_and_skipped_next_time() -> None:
    snapshots, blobs, store, embedder = (
        InMemorySnapshotRepository(),
        InMemoryBlobStore(),
        FakeStore(),
        FakeEmbedder(),
    )
    await store_photo(snapshots, blobs, "/a.jpg", b"same-image")
    await store_photo(snapshots, blobs, "/b.jpg", b"same-image")  # another listing, same photo
    await store_photo(snapshots, blobs, "/c.jpg", b"other-image")
    await store_photo(snapshots, blobs, "/d.jpg", b"broken")
    await store_photo(snapshots, blobs, "/e.jpg", b"not found", status=404)
    use_case = EmbedPhotos(snapshots, blobs, embedder, store, batch_size=2)
    first = await use_case.run(["example"])
    assert (first.images, first.already_embedded, first.embedded, first.unreadable) == (3, 0, 2, 1)
    assert embedder.calls == [2, 1]
    second = await use_case.run(["example"])
    # Only the unreadable image is tried again (and is still unreadable).
    assert (second.already_embedded, second.embedded, second.unreadable) == (2, 0, 1)
    assert embedder.calls == [2, 1, 1]


def jpeg(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (200, 30, 30)).save(buffer, "JPEG")
    return buffer.getvalue()


def test_pixels_are_the_whole_image_resized_and_normalised() -> None:
    pixels = _pixels(jpeg(400, 300))
    assert pixels is not None
    assert pixels.shape == (INPUT_SIZE, INPUT_SIZE, 3)
    assert _pixels(b"not an image") is None


def test_model_id_pins_the_revision_without_loading_weights() -> None:
    embedder = DinoV2Embedder(revision="0123456789abcdef")
    assert embedder.model_id == "facebook/dinov2-small@0123456789ab"


@pytest.mark.ml
async def test_real_model_is_deterministic_unit_length_and_skips_broken_images() -> None:
    embedder = DinoV2Embedder()
    first = await embedder.embed([jpeg(400, 300), b"broken", jpeg(300, 400)])
    again = await embedder.embed([jpeg(400, 300)])
    assert first[1] is None
    vector = first[0]
    assert vector is not None
    assert len(vector) == 384
    assert sum(v * v for v in vector) == pytest.approx(1.0, abs=1e-4)
    assert again[0] == pytest.approx(vector, abs=1e-5)
