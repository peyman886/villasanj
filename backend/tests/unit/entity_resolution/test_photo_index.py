"""NumpyPhotoIndex: exact pHash and embedding neighbours, document frequency, digests."""

import math

from tests.fakes.llm import NOW
from villasanj.catalog.domain.listing import ListingId
from villasanj.catalog.domain.photo import ListingPhoto, PerceptualFingerprint
from villasanj.entity_resolution.domain.pairs import PairKey
from villasanj.entity_resolution.infrastructure.photo_index import NumpyPhotoIndex

A, B, C, D = (
    ListingId("jabama", "1"),
    ListingId("shab", "2"),
    ListingId("shab", "3"),
    ListingId("jabama", "4"),
)


def photo(listing: ListingId, position: int, phash: int, sha: str) -> ListingPhoto:
    fingerprint = PerceptualFingerprint(phash=phash, dhash=0, width=10, height=10)
    return ListingPhoto(listing, position, f"https://c.test/{sha}", "s", sha, fingerprint, NOW)


def unit(*values: float) -> tuple[float, ...]:
    norm = math.sqrt(sum(v * v for v in values))
    return tuple(v / norm for v in values)


SHARED = -(2**63) + 0b1011  # negative: signed 64-bit, as Postgres stores it
PHOTOS = [
    photo(A, 0, SHARED, "a0"),
    photo(A, 1, 0x00FF00FF00FF00FF, "a1"),
    photo(B, 0, SHARED ^ 0b111, "b0"),  # 3 bits from a0
    photo(B, 1, 0x0F0F0F0F0F0F0F0F, "b1"),
    photo(C, 0, SHARED, "c0"),  # the same shot again: a complex or a stock photo
    photo(D, 0, 0x123456789ABCDEF0, "d0"),
]
VECTORS = {
    "a0": unit(1, 0, 0),
    "a1": unit(0, 1, 0),
    "b0": unit(1, 0.05, 0),
    "b1": unit(0, 1, 0.1),  # close to a1 in embedding space only
    "c0": unit(1, 0, 0),
    # d0 has no vector
}


def index() -> NumpyPhotoIndex:
    return NumpyPhotoIndex(PHOTOS, VECTORS, "model@1")


def test_hash_pairs_keep_the_best_distance_per_listing_pair() -> None:
    pairs = index().hash_pairs(max_hamming=4)
    assert pairs == {PairKey.of(A, B): 3, PairKey.of(A, C): 0, PairKey.of(B, C): 3}


def test_embedding_pairs_find_visual_neighbours_across_listings() -> None:
    pairs = index().embedding_pairs(neighbours=2, min_cosine=0.9)
    assert PairKey.of(A, B) in pairs
    assert pairs[PairKey.of(A, C)] == 1.0
    assert all(D not in (key.left, key.right) for key in pairs)  # no vector, no neighbours


def test_similarities_compare_every_photo_with_document_frequency() -> None:
    sims = {(s.left_position, s.right_position): s for s in index().similarities(PairKey.of(A, B))}
    assert len(sims) == 4
    assert sims[(0, 0)].hamming == 3
    assert sims[(0, 0)].document_frequency == 3  # a0, b0 and c0 are one photo on 3 listings
    assert sims[(1, 1)].cosine is not None
    assert sims[(1, 1)].cosine > 0.99
    assert sims[(1, 1)].document_frequency == 2  # a1 and b1 match by embedding only
    no_vector = index().similarities(PairKey.of(A, D))
    assert all(s.cosine is None for s in no_vector)


def test_counts_model_and_digest() -> None:
    built = index()
    assert built.photo_count(A) == 2
    assert built.photo_count(ListingId("shab", "x")) == 0
    assert built.image_model == "model@1"
    assert built.digest == index().digest
    assert NumpyPhotoIndex(PHOTOS, {}, "model@1").image_model is None
    assert NumpyPhotoIndex(PHOTOS, {}, None).embedding_pairs(3, 0.5) == {}
