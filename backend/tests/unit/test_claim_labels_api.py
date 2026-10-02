"""The claim labelling API: the description without the rules' output; labels per feature."""

from collections.abc import Iterator
from typing import cast

import pytest
from fastapi.testclient import TestClient

from tests.fakes.er import ListingsFake
from tests.fakes.llm import FixedClock
from tests.unit.catalog.test_reports import listing
from tests.unit.enrichment.test_claim_labels import LONG, Store
from villasanj.enrichment.application.claim_labels import ClaimItem, ClaimLabeling
from villasanj.entrypoints.api.app import create_app
from villasanj.entrypoints.container import Container

HOME = listing("long", description=LONG)


class Stub:
    def __init__(self) -> None:
        self.store = Store()
        self.store.queues["claims-v1"] = [ClaimItem(1, HOME.id)]
        self.listings = ListingsFake([HOME])

    def claim_labeling(self) -> ClaimLabeling:
        return ClaimLabeling(self.store, FixedClock())

    async def aclose(self) -> None:
        return None


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(lambda: cast(Container, Stub()))) as test_client:
        yield test_client


def test_a_task_shows_the_description_but_not_the_extraction(client: TestClient) -> None:
    body = client.get("/claim-labels/task").json()
    assert body["description"] == HOME.description_norm
    assert body["current"] == {}
    assert "pool" in body["features"]
    assert "claims" not in body
    saved = client.post(
        "/claim-labels",
        json={
            "queue": "claims-v1",
            "platform": "p",
            "external_id": "long",
            "stances": {"pool": "has", "parking": "has_not"},
        },
    )
    assert saved.status_code == 204
    again = client.get("/claim-labels/task").json()
    assert (again["labelled"], again["current"]["pool"], again["current"]["jacuzzi"]) == (
        1,
        "has",
        "none",
    )


def test_bad_stances_queues_and_listings_are_rejected(client: TestClient) -> None:
    bad = {
        "queue": "claims-v1",
        "platform": "p",
        "external_id": "long",
        "stances": {"pool": "maybe"},
    }
    assert client.post("/claim-labels", json=bad).status_code == 422
    assert client.get("/claim-labels/task", params={"queue": "nope"}).status_code == 404
    outside = {**bad, "external_id": "x", "stances": {}}
    assert client.post("/claim-labels", json=outside).status_code == 404
