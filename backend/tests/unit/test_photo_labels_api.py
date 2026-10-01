"""The photo-tag labelling API: tasks without scores, labels saved per photo."""

from collections.abc import Iterator
from typing import cast

import pytest
from fastapi.testclient import TestClient

from tests.fakes.llm import FixedClock
from tests.unit.enrichment.test_photo_tags_application import Queues
from villasanj.enrichment.application.photo_tags import PhotoLabeling, QueuedPhoto
from villasanj.enrichment.domain.photo_tags import PhotoTag
from villasanj.entrypoints.api.app import create_app
from villasanj.entrypoints.container import Container

SHA = "a" * 64


class Stub:
    def __init__(self) -> None:
        self.queues = Queues()
        self.queues.queue = [
            QueuedPhoto("photos-v1", 1, SHA, "https://cdn.test/a.jpg", "pool:top"),
            QueuedPhoto("photos-v1", 2, "b" * 64, "https://cdn.test/b.jpg", "pool:rest"),
        ]

    def photo_labeling(self) -> PhotoLabeling:
        return PhotoLabeling(self.queues, FixedClock())

    async def aclose(self) -> None:
        return None


@pytest.fixture
def client() -> Iterator[TestClient]:
    stub = Stub()
    with TestClient(create_app(lambda: cast(Container, stub))) as test_client:
        test_client.stub = stub  # type: ignore[attr-defined]
        yield test_client


def test_a_task_hides_scores_and_strata(client: TestClient) -> None:
    body = client.get("/photo-labels/task", params={"queue": "photos-v1"}).json()
    assert (body["position"], body["total"], body["labelled"], body["done"]) == (1, 2, 0, False)
    assert body["url"] == "https://cdn.test/a.jpg"
    assert "stratum" not in body
    assert "score" not in str(body)
    assert [t["code"] for t in body["tags"]] == [t.value for t in PhotoTag]


def test_labels_are_saved_and_the_next_task_moves_on(client: TestClient) -> None:
    response = client.post(
        "/photo-labels", json={"queue": "photos-v1", "sha256": SHA, "present": ["pool", "forest"]}
    )
    assert response.status_code == 204
    stub: Stub = client.stub  # type: ignore[attr-defined]
    assert stub.queues.labelled[("photos-v1", SHA, "owner")] == {PhotoTag.POOL, PhotoTag.FOREST}
    after = client.get("/photo-labels/task", params={"queue": "photos-v1"}).json()
    assert (after["position"], after["labelled"]) == (2, 1)
    back = client.get("/photo-labels/task", params={"queue": "photos-v1", "position": 1}).json()
    assert back["present"] == ["forest", "pool"]


def test_unknown_queues_and_tags_are_rejected(client: TestClient) -> None:
    assert client.get("/photo-labels/task", params={"queue": "nope"}).status_code == 404
    bad_tag = {"queue": "photos-v1", "sha256": SHA, "present": ["sauna"]}
    assert client.post("/photo-labels", json=bad_tag).status_code == 422
    missing = {"queue": "nope", "sha256": SHA, "present": []}
    assert client.post("/photo-labels", json=missing).status_code == 404
