"""Perceptual fingerprints and the photo pipeline use cases."""

import io

import pytest
from PIL import Image, ImageDraw

from tests.fakes.ingestion import (
    InMemoryBlobStore,
    InMemoryFrontierRepository,
    InMemorySnapshotRepository,
)
from tests.fakes.llm import NOW
from villasanj.catalog.application.photos import (
    LISTING_CODE,
    PHOTO_POSITION,
    EnqueueListingPhotos,
    FingerprintPhotos,
)
from villasanj.catalog.domain.listing import ListingId
from villasanj.catalog.domain.photo import ListingPhoto, hamming
from villasanj.catalog.infrastructure.imaging import ImagehashHasher
from villasanj.ingestion.domain.pages import FetchedPage, PageKind, PageRequest

NEAR_DUPLICATE_MAX_BITS = 8


def villa_photo(size: tuple[int, int] = (800, 600), shift: int = 0) -> Image.Image:
    image = Image.new("RGB", size, (40, 110, 70))
    draw = ImageDraw.Draw(image)
    w, h = size
    draw.rectangle(
        (w * 0.1 + shift, h * 0.5, w * 0.6 + shift, h * 0.9), fill=(230, 220, 200)
    )  # house
    draw.polygon(
        [(w * 0.05 + shift, h * 0.5), (w * 0.35 + shift, h * 0.2), (w * 0.65 + shift, h * 0.5)],
        fill=(150, 60, 50),
    )
    draw.ellipse((w * 0.65, h * 0.6, w * 0.95, h * 0.85), fill=(60, 140, 220))  # pool
    return image


def encode(image: Image.Image, quality: int = 90) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def test_resized_and_recompressed_copies_stay_close() -> None:
    hasher = ImagehashHasher()
    original = hasher.fingerprint(encode(villa_photo()))
    copy = hasher.fingerprint(encode(villa_photo().resize((400, 300)), quality=55))
    assert original is not None
    assert copy is not None
    assert original.distance(copy) <= NEAR_DUPLICATE_MAX_BITS
    assert (original.width, original.height, copy.width) == (800, 600, 400)


def test_different_photos_are_far_apart() -> None:
    hasher = ImagehashHasher()
    flipped = villa_photo().transpose(Image.Transpose.FLIP_LEFT_RIGHT).rotate(90, expand=True)
    a = hasher.fingerprint(encode(villa_photo()))
    b = hasher.fingerprint(encode(flipped))
    assert a is not None
    assert b is not None
    assert a.distance(b) > NEAR_DUPLICATE_MAX_BITS


def test_hashes_fit_a_signed_bigint_and_hamming_handles_sign() -> None:
    fingerprint = ImagehashHasher().fingerprint(encode(villa_photo()))
    assert fingerprint is not None
    assert -(2**63) <= fingerprint.phash < 2**63
    assert hamming(-1, 0) == 64
    assert hamming(fingerprint.phash, fingerprint.phash) == 0


def test_unreadable_bytes_give_no_fingerprint() -> None:
    assert ImagehashHasher().fingerprint(b"<html>not an image</html>") is None


class _Source:
    async def photo_urls(
        self, platform: str, per_listing: int, listing_limit: int | None
    ) -> list[tuple[ListingId, int, str]]:
        return [
            (ListingId(platform, "42"), position, f"https://cdn.example.test/{position}.jpg")
            for position in range(per_listing)
        ]


class _Photos:
    def __init__(self) -> None:
        self.saved: list[ListingPhoto] = []

    async def save(self, photo: ListingPhoto) -> None:
        self.saved.append(photo)

    async def fingerprinted(self, platform: str) -> set[str]:
        return {p.snapshot_id for p in self.saved if p.listing_id.platform == platform}


async def test_enqueue_creates_attributed_photo_requests_once() -> None:
    frontier = InMemoryFrontierRepository()
    enqueue = EnqueueListingPhotos(_Source(), frontier)
    assert await enqueue.run("example", per_listing=3, listing_limit=None) == 3
    assert await enqueue.run("example", per_listing=3, listing_limit=None) == 0
    request = next(iter(frontier.rows.values())).item.request
    assert request.kind is PageKind.PHOTO
    assert request.context_value(LISTING_CODE) == "42"


@pytest.mark.parametrize("readable", [True, False])
async def test_fingerprinting_stored_photos(readable: bool) -> None:
    snapshots, blobs, photos = InMemorySnapshotRepository(), InMemoryBlobStore(), _Photos()
    body = encode(villa_photo()) if readable else b"oops"
    request = PageRequest(
        "example",
        PageKind.PHOTO,
        "https://cdn.example.test/0.jpg",
        context=((LISTING_CODE, "42"), (PHOTO_POSITION, "0")),
    )
    page = FetchedPage(
        request, 200, request.url, (("content-type", "image/jpeg"),), body, NOW, "test"
    )
    await snapshots.save(page, await blobs.put(body), None)
    report = await FingerprintPhotos(snapshots, blobs, ImagehashHasher(), photos).run("example")
    assert (report.fingerprinted, report.unreadable) == ((1, 0) if readable else (0, 1))
    if readable:
        assert photos.saved[0].listing_id == ListingId("example", "42")
        again = await FingerprintPhotos(snapshots, blobs, ImagehashHasher(), photos).run("example")
        assert (again.already_done, again.fingerprinted) == (1, 0)  # never hashed twice
        forced = await FingerprintPhotos(snapshots, blobs, ImagehashHasher(), photos).run(
            "example", force=True
        )
        assert forced.fingerprinted == 1
