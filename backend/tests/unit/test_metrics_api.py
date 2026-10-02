"""The metrics endpoint: one read-only summary of crawl, coverage, offers, spend and labelling."""

from collections import Counter
from collections.abc import Iterator
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from tests.fakes.llm import NOW, FixedClock
from villasanj.catalog.application.reports import PhotoPipelineRow
from villasanj.enrichment.application.truth import SeaTruthReport
from villasanj.entrypoints.api.app import create_app
from villasanj.entrypoints.container import Container
from villasanj.ingestion.application.stats import HostTraffic
from villasanj.pricing.application.offers import OfferCounts
from villasanj.shared.application.llm.ports import SpendRow


class Async:
    """An object whose named methods are coroutines returning fixed values (callables: per call)."""

    def __init__(self, **results: Any) -> None:
        self._results = results

    def __getattr__(self, name: str) -> Any:
        result = self._results[name]

        async def method(*args: Any) -> Any:
            return result(*args) if callable(result) else result

        return method


def spend(task: str, cost: str, failed: int = 0) -> SpendRow:
    return SpendRow(task, "m", 2, 0, failed, 10, 5, 0, Decimal(cost), 0)


class Stub:
    def __init__(self, labelled: bool) -> None:
        self.crawl = SimpleNamespace(adapters={"beta": object(), "alpha": object()})
        self.clock = FixedClock()
        self.llm = SimpleNamespace(routing=SimpleNamespace(project_budget_usd=Decimal(30)))
        self.listings = Async(listings=lambda platform: [1, 2, 3] if platform == "alpha" else [1])
        self._labelled = labelled

    def crawl_stats(self) -> Async:
        host = HostTraffic("alpha", "cdn.alpha.test", 7, {200: 7}, 1, None, None, 3.05, 3.7)
        return Async(traffic=[host])

    def photo_pipeline(self) -> Async:
        row = PhotoPipelineRow("alpha", 3, 9, 8, 6, {}, 2, 0, 6, 6, 0)
        return Async(run=[row])

    def image_embedder(self) -> SimpleNamespace:
        return SimpleNamespace(model_id="embedder@1")

    def sea_truth(self) -> Async:
        def report(platform: str) -> SeaTruthReport:
            if platform != "alpha":
                return SeaTruthReport(platform)
            verdicts = Counter({"supported": 2, "contradicted": 1})
            return SeaTruthReport(platform, 2, 1, verdicts=verdicts)

        return Async(run=report)

    def distance_truth(self) -> Async:
        def report(platform: str) -> SimpleNamespace:
            judged = 3 if platform == "alpha" else 0
            return SimpleNamespace(listings_judged=judged, listings_contradicted=min(1, judged))

        return Async(run=report)

    def coast_store(self) -> Async:
        return Async(of_platform=lambda platform: {"1": 0, "2": 0} if platform == "alpha" else {})

    def routing_origin(self) -> SimpleNamespace:
        return SimpleNamespace(slug="origin")

    def drive_store(self) -> Async:
        routed = {"1": SimpleNamespace(routed_points=9), "2": SimpleNamespace(routed_points=0)}
        return Async(of_platform=lambda platform, origin: routed if platform == "alpha" else {})

    def offers(self) -> Async:
        counts = OfferCounts("alpha", "weekend", 4, 3, {"bookable": 2}, {"open": 2}, 1)
        return Async(distribution=[counts])

    def scenarios(self) -> list[object]:
        return []

    def llm_spend(self) -> Async:
        return Async(by_task_and_model=[spend("explanation", "0.25"), spend("judge", "0.1", 1)])

    def labeling(self) -> Async:
        task = SimpleNamespace(total=300, labeled=12) if self._labelled else None
        return Async(task=task)

    def photo_labeling(self) -> Async:
        return Async(task=None)

    async def aclose(self) -> None:
        return None


def client_for(stub: Stub) -> Iterator[TestClient]:
    with TestClient(create_app(lambda: cast(Container, stub))) as test_client:
        yield test_client


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield from client_for(Stub(labelled=True))


def test_metrics_report_every_platform_with_its_coverage_and_truth_check(
    client: TestClient,
) -> None:
    body = client.get("/metrics").json()
    assert body["computed_at"].startswith(NOW.isoformat()[:19])
    assert [p["platform"] for p in body["platforms"]] == ["alpha", "beta"]
    alpha, beta = body["platforms"]
    assert (alpha["listings"], alpha["photos_selected"], alpha["photos_downloaded"]) == (3, 8, 6)
    assert alpha["photo_coverage"] == 0.75
    assert (alpha["coast_measured"], alpha["drive_routed"]) == (2, 1)  # unrouted pins not counted
    assert (alpha["sea_claim_listings"], alpha["sea_contradicted_listings"]) == (2, 1)
    assert alpha["sea_measured_listings"] == 2
    assert (alpha["distance_judged_listings"], alpha["distance_contradicted_listings"]) == (3, 1)
    assert (beta["distance_contradicted_low"], beta["distance_contradicted_high"]) == (0.0, 1.0)
    assert 0.0 < alpha["sea_contradicted_low"] < 0.5 < alpha["sea_contradicted_high"] < 1.0
    assert alpha["sea_verdicts"] == {"supported": 2, "contradicted": 1}
    assert (beta["listings"], beta["photos_selected"], beta["photo_coverage"]) == (1, 0, 0.0)


def test_metrics_report_politeness_offers_spend_and_labelling(client: TestClient) -> None:
    body = client.get("/metrics").json()
    assert body["hosts"] == [
        {
            "platform": "alpha",
            "host": "cdn.alpha.test",
            "responses": 7,
            "min_interval_s": 3.05,
            "median_interval_s": 3.7,
        }
    ]
    assert body["offers"][0]["by_kind"] == {"open": 2}
    assert [s["task"] for s in body["llm_spend"]] == ["explanation", "judge"]
    assert (body["llm_total_usd"], body["llm_cap_usd"]) == (0.35, 30.0)
    assert body["labelling"] == [{"queue": "gold-v1", "total": 300, "labelled": 12}]


def test_queues_that_do_not_exist_yet_are_left_out() -> None:
    for client in client_for(Stub(labelled=False)):
        assert client.get("/metrics").json()["labelling"] == []
