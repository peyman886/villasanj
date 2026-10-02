"""POST /search: ranked results with provenance and an explanation in linkable segments."""

from collections.abc import Iterator
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from tests.fakes.llm import FixedClock
from tests.unit.discovery.test_explanation import ScriptedClient as ExplanationClient
from tests.unit.discovery.test_search import ORIGIN, WEEKEND, search
from villasanj.discovery.application.intent import SearchIntent
from villasanj.discovery.application.routing import Origin
from villasanj.discovery.application.search import SearchListings
from villasanj.entrypoints.api.app import create_app
from villasanj.entrypoints.container import Container
from villasanj.shared.application.jobs import JobStatus
from villasanj.shared.application.llm.types import JobContext

QUERY = "ویلای استخردار در رامسر برای ۴ نفر آخر هفته زیر ۵ میلیون"


class Jobs:
    def __init__(self) -> None:
        self.finished: list[JobStatus] = []

    async def start(self, kind: str, budget: Decimal, params: dict[str, Any]) -> JobContext:
        return JobContext(f"{kind}-1", budget)

    async def finish(self, job_id: str, status: JobStatus) -> None:
        self.finished.append(status)


class Stub:
    def __init__(self, intent: SearchIntent, explanation: str) -> None:
        self._intent = intent
        self.jobs = Jobs()
        self.clock = FixedClock()
        self.crawl = SimpleNamespace(
            adapters={"p": SimpleNamespace(profile=SimpleNamespace(display_name="پلتفرم"))}
        )
        self.llm = SimpleNamespace(client=ExplanationClient(explanation))

    def search(self) -> SearchListings:
        return search(self._intent)  # a new one per request, like the container

    def routing_origin(self) -> Origin:
        return ORIGIN

    async def aclose(self) -> None:
        return None


def client_for(intent: SearchIntent, explanation: str = "{F3} برای {F1}.") -> Iterator[TestClient]:
    stub = Stub(intent, explanation)
    with TestClient(create_app(lambda: cast(Container, stub))) as test_client:
        test_client.stub = stub  # type: ignore[attr-defined]
        yield test_client


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield from client_for(WEEKEND)


def test_search_returns_ranked_results_with_provenance(client: TestClient) -> None:
    response = client.post("/search", json={"query": QUERY})
    assert response.status_code == 200
    body = response.json()
    assert body["dates"]["text"] == "پنجشنبه ۹ مهر تا شنبه ۱۱ مهر"
    assert body["places"] == ["رامسر"]
    assert body["excluded"] == {"feature_denied": 1}
    assert body["drive_coverage"] == {"3": 0, "4": 1, "5": 1, "6": 1}
    assert [r["listing_id"] for r in body["results"]] == ["p:pool", "p:contradicted"]
    first = body["results"][0]
    assert first["total"]["high_toman"] is None  # no fee policy: an open "at least" offer
    guests = body["intent"]["guest_parts"][0]
    assert first["per_person"]["low_toman"] * guests <= first["total"]["low_toman"]
    assert first["per_person"]["high_toman"] is None
    assert first["total_provenance"]["method"] == "derived"
    assert [c["component"] for c in first["contributions"]] == ["price", "rating"]
    assert first["platform_name"] == "پلتفرم"
    assert first["geo"]["coast_m"]["text"] == "۰ تا ۷۰۰ متر تا ساحل در خط مستقیم"
    assert first["geo"]["drive_s"]["text"].endswith("از تهران، بدون ترافیک")
    assert client.stub.jobs.finished == [JobStatus.SUCCEEDED]  # type: ignore[attr-defined]


def test_the_explanation_comes_as_linkable_segments(client: TestClient) -> None:
    explanation = client.post("/search", json={"query": QUERY}).json()["explanation"]
    assert explanation["source"] == "llm"
    filled = [s for s in explanation["segments"] if s["slot"]]
    assert [s["slot"] for s in filled] == ["F3", "F1"]
    assert all(s["provenance"] is not None for s in filled)
    assert "".join(s["text"] for s in explanation["segments"]) == explanation["text"]


def test_results_can_come_first_and_the_explanation_on_its_own(client: TestClient) -> None:
    body = client.post("/search", json={"query": QUERY, "explain": False}).json()
    assert body["explanation"] is None
    assert body["results"]
    explanation = client.post("/search/explanation", json={"query": QUERY}).json()
    assert explanation["source"] == "llm"
    assert [s["slot"] for s in explanation["segments"] if s["slot"]] == ["F3", "F1"]


def test_open_questions_come_back_without_results() -> None:
    for test_client in client_for(SearchIntent(guest_parts=[4])):
        body = test_client.post("/search", json={"query": "ویلا برای ۴ نفر"}).json()
        assert (body["missing"], body["results"], body["explanation"]) == (["dates"], [], None)


def test_a_too_short_query_is_rejected(client: TestClient) -> None:
    assert client.post("/search", json={"query": "و"}).status_code == 422
