"""Labelling API: next task, revisiting a position, recording labels, and what is never sent."""

import asyncio
from collections.abc import Iterator
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient

from tests.fakes.er import CandidateStoreFake, LabelStoreFake, ListingsFake
from tests.fakes.ingestion import SteppingClock
from tests.unit.entity_resolution.test_application import J1, S1, S4
from villasanj.entity_resolution.application.labeling import (
    BuildLabelQueue,
    LabelingSession,
    QueuePlan,
)
from villasanj.entity_resolution.application.ports import ScoredCandidate
from villasanj.entity_resolution.domain.pairs import BlockingSource, PairKey
from villasanj.entity_resolution.domain.scoring import Score
from villasanj.entrypoints.api.app import create_app
from villasanj.entrypoints.container import Container

PAIRS = [PairKey.of(J1.id, S1.id), PairKey.of(J1.id, S4.id)]


class _Stub:
    def __init__(self) -> None:
        self.store = LabelStoreFake()
        self.reader = ListingsFake([J1, S1, S4])
        self.clock = SteppingClock()
        self.crawl = SimpleNamespace(
            adapters={"jabama": SimpleNamespace(profile=SimpleNamespace(display_name="جاباما"))}
        )

    def labels(self) -> LabelStoreFake:
        return self.store

    def labeling(self) -> LabelingSession:
        return LabelingSession(self.store, self.reader, self.clock)

    async def aclose(self) -> None:
        return None


@pytest.fixture
def client() -> Iterator[TestClient]:
    stub = _Stub()
    candidates = [
        ScoredCandidate(key, frozenset({BlockingSource.PHOTO_HASH}), True, None, Score(9.5, ()))
        for key in PAIRS
    ]
    plan = QueuePlan(photo_bands=(2,), geo_bands=(), same_platform=0, wide=0)
    asyncio.run(BuildLabelQueue(CandidateStoreFake(candidates), stub.store).run("gold", plan))
    with TestClient(create_app(lambda: cast(Container, stub))) as test_client:
        yield test_client


def test_next_task_shows_both_listings_but_no_score_or_stratum(client: TestClient) -> None:
    response = client.get("/er/queues/gold/task", params={"labeler": "owner"})
    assert response.status_code == 200
    task = response.json()
    assert (task["position"], task["total"], task["labeled"]) == (0, 2, 0)
    assert task["left"]["platform_name"] == "جاباما"
    assert task["right"]["platform_name"] == "shab"  # falls back to the slug
    assert task["left"]["base_capacity"] == 4
    assert task["distance"]["centre_m"] >= 0
    text = response.text
    assert "score" not in text
    assert "stratum" not in text
    assert "band" not in text


def test_labels_are_recorded_and_the_queue_advances(client: TestClient) -> None:
    first = client.get("/er/queues/gold/task").json()
    saved = client.post(
        "/er/labels",
        json={
            "queue": "gold",
            "pair": first["pair"],
            "label": "match",
            "labeler": "owner",
            "seconds": 3,
        },
    )
    assert saved.status_code == 201
    assert saved.json()["label"] == "match"
    second = client.get("/er/queues/gold/task").json()
    assert (second["position"], second["labeled"]) == (1, 1)
    back = client.get("/er/queues/gold/task", params={"position": 0}).json()
    assert back["current_label"] == "match"
    client.post(
        "/er/labels",
        json={"queue": "gold", "pair": second["pair"], "label": "non_match", "labeler": "owner"},
    )
    assert client.get("/er/queues/gold/task").status_code == 204


@pytest.mark.parametrize(
    ("pair", "label", "status"),
    [
        ("not-a-pair", "match", 422),
        (str(PairKey.of(S1.id, S4.id)), "match", 404),  # not in the queue
        (str(PAIRS[0]), "maybe", 422),  # unknown label
    ],
)
def test_bad_labels_are_rejected(client: TestClient, pair: str, label: str, status: int) -> None:
    response = client.post(
        "/er/labels", json={"queue": "gold", "pair": pair, "label": label, "labeler": "owner"}
    )
    assert response.status_code == status


def test_unknown_position_is_404(client: TestClient) -> None:
    assert client.get("/er/queues/gold/task", params={"position": 42}).status_code == 404
