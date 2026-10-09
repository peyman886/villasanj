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
    # What the card and the map need, no more precise than the listing published it.
    assert first["location"] == {"lat": 36.9, "lon": 50.66, "radius_m": 400}
    assert first["stale"] is False
    assert first["confirmed"] == [{"feature": "pool", "source": "amenities"}]
    assert first["rating_count"] == 12


def test_choosing_the_budget_basis_keeps_every_other_chip(client: TestClient) -> None:
    body = client.post("/search", json={"query": QUERY, "drop": ["basis:per_night"]}).json()
    assert body["intent"]["budget"]["basis"] == "per_night"
    assert body["places"] == ["رامسر"]
    assert body["budget_readings"] is None


def test_the_filter_panel_gets_every_ranked_listing_and_filters_narrow(client: TestClient) -> None:
    facets = client.post("/search/facets", json={"query": QUERY}).json()
    assert [f["listing"] for f in facets] == ["p:pool", "p:contradicted"]
    assert facets[0]["features"] == sorted(facets[0]["features"])
    cheapest = min(f["total_toman"] for f in facets)
    body = client.post(
        "/search", json={"query": QUERY, "filters": {"price_max": cheapest, "features": ["pool"]}}
    ).json()
    kept = [
        f["listing"] for f in facets if f["total_toman"] <= cheapest and "pool" in f["features"]
    ]
    assert [r["listing_id"] for r in body["results"]] == kept
    bad = client.post("/search", json={"query": QUERY, "area": [51.0, 36.0, 50.0, 37.0]})
    assert bad.status_code == 422
    assert (
        client.post("/search", json={"query": QUERY, "filters": {"features": ["x"]}}).status_code
        == 422
    )


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


def test_the_ranking_rules_page_reads_the_numbers_from_the_code(client: TestClient) -> None:
    body = client.get("/search/ranking").json()
    assert body["weights"] == {"price": 0.6, "rating": 0.4}
    assert (body["near_sea_m"], body["centre_extent_m"], body["unknown_radius_m"]) == (
        1000.0,
        1500.0,
        500,
    )
    assert body["origin"] == ORIGIN.name_fa


def test_unhandled_wishes_are_said_back_and_matched_in_the_listing_text() -> None:
    from dataclasses import replace

    from tests.unit.discovery.test_search import LISTINGS
    from villasanj.discovery.application.search import mentioned

    pool = LISTINGS[0]
    duplex = replace(pool, description_norm="ویلای دوبلکس با حیاط")
    assert mentioned(["دوبلکس", "حیاط بزرگ"], duplex) == ("دوبلکس",)
    assert mentioned(["سونا"], replace(pool, description_norm="نزدیک سونامی")) == ()
    intent = WEEKEND.model_copy(update={"unhandled": ["دوبلکس"]})
    query = "ویلای دوبلکس استخردار در رامسر برای ۴ نفر آخر هفته زیر ۵ میلیون"
    for test_client in client_for(intent):
        body = test_client.post("/search", json={"query": query, "explain": False}).json()
        assert body["unhandled"] == ["دوبلکس"]
        assert all(r["mentions"] == [] for r in body["results"])  # no listing says it
        assert all(r["listing_provenance"]["method"] == "observed" for r in body["results"])
