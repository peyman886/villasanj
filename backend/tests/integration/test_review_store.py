"""Review queues and labels (M8 query set and relevance) against a real Postgres."""

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.fakes.llm import NOW
from villasanj.discovery.application.reviews import ReviewCase
from villasanj.discovery.infrastructure.reviews import PgReviewStore

pytestmark = pytest.mark.integration


async def test_cases_and_labels_round_trip_and_relabelling_replaces(engine: AsyncEngine) -> None:
    store = PgReviewStore(engine)
    queue = f"queries-{id(engine)}"
    cases = [
        ReviewCase(1, {"query": "ویلا در رامسر", "expected": {"places": ["رامسر"]}}),
        ReviewCase(2, {"query": "سلام", "expected": {}}),
    ]
    assert await store.cases(queue) == []
    await store.save_cases(queue, "query", cases, NOW)
    assert await store.cases(queue) == cases
    await store.save_label(queue, 1, "", "owner", {"correct": True}, NOW)
    await store.save_label(queue, 1, "", "owner", {"correct": False, "note": "x"}, NOW)
    await store.save_label(queue, 2, "p:1", "owner", {"grade": 2}, NOW)
    await store.save_label(queue, 2, "p:1", "other", {"grade": 0}, NOW)
    assert await store.labels(queue, "owner") == {
        (1, ""): {"correct": False, "note": "x"},
        (2, "p:1"): {"grade": 2},
    }
