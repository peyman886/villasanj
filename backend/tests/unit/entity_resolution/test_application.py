"""Entity-resolution use cases: blocking union, scoring, the labelling queue, evaluation."""

from datetime import timedelta

import pytest

from tests.fakes.er import CandidateStoreFake, LabelStoreFake, ListingsFake, PhotoIndexFake
from tests.fakes.ingestion import SteppingClock
from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from villasanj.catalog.domain.listing import Listing, ListingId
from villasanj.entity_resolution.application.evaluation import EvaluateMatcher
from villasanj.entity_resolution.application.labeling import (
    BuildLabelQueue,
    LabelingSession,
    QueueExists,
    QueuePlan,
)
from villasanj.entity_resolution.application.matching import BlockingConfig, MatchListings
from villasanj.entity_resolution.application.ports import ScoredCandidate
from villasanj.entity_resolution.domain.evidence import PhotoSimilarity
from villasanj.entity_resolution.domain.labels import Label, PairLabel
from villasanj.entity_resolution.domain.pairs import BlockingSource, PairKey
from villasanj.entity_resolution.domain.scoring import Score
from villasanj.shared.domain.geo import GeoPoint

SNAPSHOT = "00000000-0000-0000-0000-000000000801"


def listing(platform: str, external_id: str, lat: float, **overrides: object) -> Listing:
    values: dict[str, object] = {
        "platform": platform,
        "external_id": external_id,
        "location": GeoPoint(lat, 50.66),
        "location_radius_m": 400 if platform == "jabama" else None,
        "bedrooms": 2,
    }
    values.update(overrides)
    return Listing.from_parsed(parsed(**values), SNAPSHOT, NOW)


J1 = listing("jabama", "1", 36.9000)
J2 = listing("jabama", "2", 36.9600)  # ~6.7 km north of everything else
S1 = listing("shab", "10", 36.9040)  # ~445 m from J1: inside radius + slack
S2 = listing("shab", "11", 36.9150, bedrooms=5)  # ~1.7 km and rooms differ: wide net only
S3 = listing("shab", "12", 36.9590)  # near J2
S4 = listing("shab", "13", 36.7000)  # far from everything; matched by a photo only
LISTINGS = [J1, J2, S1, S2, S3, S4]


async def run_match(index: PhotoIndexFake) -> CandidateStoreFake:
    store = CandidateStoreFake()
    await MatchListings(ListingsFake(LISTINGS), index, store, SteppingClock()).run(
        ["jabama", "shab"]
    )
    return store


async def test_blocking_unions_location_photos_and_a_wide_net() -> None:
    photo_pair = PairKey.of(J1.id, S4.id)
    same_platform = PairKey.of(S1.id, S3.id)
    index = PhotoIndexFake(
        counts={J1.id: 5, S4.id: 5},
        hash_pairs={photo_pair: 3, same_platform: 2, PairKey.of(J2.id, S2.id): 9},
        embedding_pairs={PairKey.of(J2.id, S4.id): 0.9, PairKey.of(S2.id, S4.id): 0.96},
        similarities={photo_pair: [PhotoSimilarity(0, 0, 3, 0.97, 1)]},
    )
    store = await run_match(index)
    by_key = {c.key: c for c in store.candidates}
    assert by_key[PairKey.of(J1.id, S1.id)].sources == {BlockingSource.GEO_ROOMS}
    assert by_key[PairKey.of(J2.id, S3.id)].sources == {BlockingSource.GEO_ROOMS}
    assert by_key[PairKey.of(J1.id, S2.id)].sources == {BlockingSource.WIDE}
    assert not by_key[PairKey.of(J1.id, S2.id)].blocked
    assert by_key[PairKey.of(J1.id, S2.id)].score is None
    assert by_key[photo_pair].sources == {BlockingSource.PHOTO_HASH}
    assert by_key[PairKey.of(J2.id, S2.id)].sources == {BlockingSource.PHOTO_HASH}
    assert by_key[PairKey.of(J2.id, S4.id)].sources == {BlockingSource.PHOTO_EMBEDDING}
    assert by_key[same_platform].sources == {BlockingSource.SAME_PLATFORM_PHOTOS}
    assert by_key[PairKey.of(S2.id, S4.id)].sources == {BlockingSource.SAME_PLATFORM_PHOTOS}
    scored = by_key[photo_pair].score
    assert scored is not None
    assert scored.contributions[0].feature == "shared_photos"
    run = store.runs[0]
    assert run.counts["blocked"] == sum(c.blocked for c in store.candidates)
    assert run.config["image_model"] == "fake-model"
    assert len(run.dataset_hash) == 64


async def test_weak_same_platform_photo_links_are_not_candidates() -> None:
    pair = PairKey.of(S1.id, S3.id)
    store = await run_match(
        PhotoIndexFake(hash_pairs={pair: 9}, embedding_pairs={PairKey.of(S2.id, S4.id): 0.9})
    )
    keys = {c.key for c in store.candidates}
    assert pair not in keys
    assert PairKey.of(S2.id, S4.id) not in keys


async def test_the_same_inputs_give_the_same_dataset_hash() -> None:
    first = (await run_match(PhotoIndexFake())).runs[0]
    second = (await run_match(PhotoIndexFake())).runs[0]
    assert first.dataset_hash == second.dataset_hash
    assert first.id != second.id


async def test_photo_pairs_of_listings_missing_from_the_catalog_are_dropped() -> None:
    ghost = PairKey.of(ListingId("jabama", "999"), S1.id)
    store = await run_match(PhotoIndexFake(hash_pairs={ghost: 1}))
    assert ghost not in {c.key for c in store.candidates}


async def test_listings_without_location_are_only_found_by_photos() -> None:
    nowhere = listing("jabama", "3", 36.9, location=None)
    store = CandidateStoreFake()
    await MatchListings(
        ListingsFake([nowhere, S1]), PhotoIndexFake(), store, SteppingClock(), BlockingConfig()
    ).run(["jabama", "shab"])
    assert store.candidates == []


# ---------------------------------------------------------------- queue and labelling


def scored(
    key: PairKey, value: float, *sources: BlockingSource, blocked: bool = True
) -> ScoredCandidate:
    return ScoredCandidate(
        key, frozenset(sources), blocked, None, Score(value, ()) if blocked else None
    )


def ids(platform: str, count: int) -> list[ListingId]:
    return [ListingId(platform, f"{i:03d}") for i in range(count)]


JS, SS = ids("jabama", 40), ids("shab", 40)
CANDIDATES = [
    *(scored(PairKey.of(JS[i], SS[i]), i, BlockingSource.PHOTO_HASH) for i in range(20)),
    *(scored(PairKey.of(JS[i], SS[i - 1]), i, BlockingSource.GEO_ROOMS) for i in range(20, 30)),
    *(
        scored(PairKey.of(SS[i], SS[i + 1]), 1, BlockingSource.SAME_PLATFORM_PHOTOS)
        for i in range(30, 35)
    ),
    *(
        scored(PairKey.of(JS[i], SS[i]), 0, BlockingSource.WIDE, blocked=False)
        for i in range(30, 40)
    ),
]
PLAN = QueuePlan(photo_bands=(1, 4), geo_bands=(1, 1), same_platform=2, wide=3, seed=3)


async def test_queue_is_stratified_and_created_once() -> None:
    labels = LabelStoreFake()
    builder = BuildLabelQueue(CandidateStoreFake(CANDIDATES), labels)
    items = await builder.run("gold", PLAN)
    strata = {item.stratum for item in items}
    assert strata == {
        "photo:band01",
        "photo:band02",
        "geo:band01",
        "geo:band02",
        "same_platform",
        "wide",
    }
    assert len(items) == 1 + 4 + 1 + 1 + 2 + 3
    assert {i.stratum_size for i in items if i.stratum.startswith("photo")} == {10}
    with pytest.raises(QueueExists):
        await builder.run("gold", PLAN)


async def test_labeling_session_walks_the_queue_and_keeps_the_latest_label() -> None:
    labels = LabelStoreFake()
    reader = ListingsFake(
        [
            listing(key.platform, key.external_id, 36.9)
            for c in CANDIDATES
            for key in (c.key.left, c.key.right)
        ]
    )
    items = await BuildLabelQueue(CandidateStoreFake(CANDIDATES), labels).run("gold", PLAN)
    clock = SteppingClock()
    session = LabelingSession(labels, reader, clock)
    first = await session.task("gold", "owner")
    assert first is not None
    assert (first.item.position, first.labeled, first.total, first.current) == (
        0,
        0,
        len(items),
        None,
    )
    await session.record(first.item.key, Label.MATCH, "owner", 4.2)
    clock.advance(10)
    await session.record(first.item.key, Label.NON_MATCH, "owner", 1.0)  # changed my mind
    second = await session.task("gold", "owner")
    assert second is not None
    assert (second.item.position, second.labeled) == (1, 1)
    again = await session.task("gold", "owner", position=0)
    assert again is not None
    assert again.current is Label.NON_MATCH
    assert await session.task("gold", "owner", position=999) is None
    assert await session.task("gold", "someone-else") is not None


async def test_a_finished_queue_has_no_next_task() -> None:
    labels = LabelStoreFake()
    reader = ListingsFake([listing(k.platform, k.external_id, 36.9) for k in (JS[0], SS[0])])
    candidates = [scored(PairKey.of(JS[0], SS[0]), 5, BlockingSource.PHOTO_HASH)]
    await BuildLabelQueue(CandidateStoreFake(candidates), labels).run(
        "tiny", QueuePlan(photo_bands=(1,), geo_bands=(), same_platform=0, wide=0)
    )
    session = LabelingSession(labels, reader, SteppingClock())
    task = await session.task("tiny", "owner")
    assert task is not None
    await session.record(task.item.key, Label.UNSURE, "owner", None)
    assert await session.task("tiny", "owner") is None


async def test_a_pair_whose_listing_disappeared_cannot_be_shown() -> None:
    labels = LabelStoreFake()
    candidates = [scored(PairKey.of(JS[0], SS[0]), 5, BlockingSource.PHOTO_HASH)]
    await BuildLabelQueue(CandidateStoreFake(candidates), labels).run(
        "tiny", QueuePlan(photo_bands=(1,), geo_bands=(), same_platform=0, wide=0)
    )
    assert (
        await LabelingSession(labels, ListingsFake([]), SteppingClock()).task("tiny", "owner")
        is None
    )


# ---------------------------------------------------------------- evaluation


async def test_evaluation_weights_strata_and_reports_blocking_recall() -> None:
    labels = LabelStoreFake()
    store = CandidateStoreFake(CANDIDATES)
    items = await BuildLabelQueue(store, labels).run("gold", PLAN)
    for item in items:
        candidate = await store.get(item.key)
        assert candidate is not None
        if not item.key.cross_platform:
            verdict = Label.NON_MATCH
        elif not candidate.blocked:
            verdict = Label.MATCH  # a match only the wide net found
        else:
            verdict = (
                Label.MATCH if candidate.score and candidate.score.value >= 10 else Label.NON_MATCH
            )
        at = NOW + timedelta(seconds=item.position)
        await labels.save_label(PairLabel(item.key, verdict, "owner", at))
    report = await EvaluateMatcher(store, labels).run("gold", "owner")
    assert report.labelled == report.queued == len(items)
    assert report.same_platform == {"non_match": 2}
    assert report.blocking_recall.estimate is not None
    assert report.blocking_recall.estimate < 1  # the wide-net matches count as missed
    at_ten = next(m for m in report.curve if m.threshold == 10)
    assert at_ten.precision.estimate == 1.0
    assert report.unsure.estimate == 0.0
    assert set(report.labels_by_stratum) == {i.stratum for i in items}
