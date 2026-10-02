"""The summary review API: a task names the listing; verdicts are saved per listing."""

from collections.abc import Iterator
from typing import cast

import pytest
from fastapi.testclient import TestClient

from tests.fakes.llm import FixedClock
from tests.unit.enrichment.test_summary_review import Store
from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.summary_review import ReviewItem, SummaryReviewing
from villasanj.entrypoints.api.app import create_app
from villasanj.entrypoints.container import Container


class Stub:
    def __init__(self) -> None:
        self.store = Store()
        self.store.queues["summaries-v1"] = [
            ReviewItem(1, ListingId("p", "a")),
            ReviewItem(2, ListingId("p", "b")),
        ]

    def summary_reviewing(self) -> SummaryReviewing:
        return SummaryReviewing(self.store, FixedClock())

    async def aclose(self) -> None:
        return None


@pytest.fixture
def client() -> Iterator[TestClient]:
    stub = Stub()
    with TestClient(create_app(lambda: cast(Container, stub))) as test_client:
        test_client.stub = stub  # type: ignore[attr-defined]
        yield test_client


def test_a_verdict_is_saved_and_the_next_listing_comes(client: TestClient) -> None:
    first = client.get("/summary-reviews/task").json()
    assert (first["position"], first["platform"], first["external_id"]) == (1, "p", "a")
    assert first["faithful"] is None
    saved = client.post(
        "/summary-reviews",
        json={
            "queue": "summaries-v1",
            "platform": "p",
            "external_id": "a",
            "faithful": False,
            "note": "  یک نکته ساختگی است ",
        },
    )
    assert saved.status_code == 204
    after = client.get("/summary-reviews/task").json()
    assert (after["position"], after["reviewed"]) == (2, 1)
    back = client.get("/summary-reviews/task", params={"position": 1}).json()
    assert (back["faithful"], back["note"]) == (False, "یک نکته ساختگی است")


def test_unknown_queues_and_listings_are_404(client: TestClient) -> None:
    assert client.get("/summary-reviews/task", params={"queue": "nope"}).status_code == 404
    outside = {"queue": "summaries-v1", "platform": "p", "external_id": "z", "faithful": True}
    assert client.post("/summary-reviews", json=outside).status_code == 404
