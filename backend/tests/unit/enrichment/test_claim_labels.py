"""Claim labelling: descriptions drawn once, every feature stored, the rules scored on them."""

from collections.abc import Mapping, Sequence
from datetime import datetime

import pytest

from tests.fakes.er import ListingsFake
from tests.fakes.llm import FixedClock
from tests.unit.catalog.test_reports import listing
from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.claim_labels import (
    BuildClaimLabelQueue,
    ClaimItem,
    ClaimLabeling,
    ClaimQueueExists,
    EvaluateClaimExtraction,
)
from villasanj.enrichment.domain.claim_eval import Stance
from villasanj.enrichment.domain.features import Feature

LONG = "ویلای دوبلکس با استخر و شومینه در محیطی آرام و سرسبز، نزدیک به جاده و مرکز شهر، " * 2


class Store:
    def __init__(self) -> None:
        self.queues: dict[str, list[ClaimItem]] = {}
        self.saved: dict[tuple[str, ListingId, str], dict[Feature, Stance]] = {}

    async def items(self, queue: str) -> list[ClaimItem]:
        return self.queues.get(queue, [])

    async def save(self, queue: str, items: Sequence[ClaimItem], at: datetime) -> None:
        self.queues[queue] = list(items)

    async def labels(self, queue: str, labeler: str) -> dict[ListingId, dict[Feature, Stance]]:
        return {k[1]: v for k, v in self.saved.items() if k[0] == queue and k[2] == labeler}

    async def save_labels(
        self,
        queue: str,
        listing_id: ListingId,
        labeler: str,
        labels: Mapping[Feature, Stance],
        at: datetime,
    ) -> None:
        self.saved[(queue, listing_id, labeler)] = dict(labels)


async def test_only_real_descriptions_are_drawn_once() -> None:
    listings = ListingsFake(
        [listing("long", description=LONG), listing("short", description="ویلا")]
    )
    store = Store()
    build = BuildClaimLabelQueue(listings, store, FixedClock(), ["p"])
    (item,) = await build.run("claims-v1", 60)
    assert item.listing_id == ListingId("p", "long")
    with pytest.raises(ClaimQueueExists):
        await build.run("claims-v1", 60)


async def test_labels_complete_every_feature_and_score_the_rules() -> None:
    home = listing("long", description=LONG)
    store = Store()
    store.queues["q"] = [ClaimItem(1, home.id)]
    labeling = ClaimLabeling(store, FixedClock())
    assert await labeling.record(
        "q", home.id, "owner", {Feature.POOL: Stance.HAS, Feature.FOREST: Stance.HAS}
    )
    saved = store.saved[("q", home.id, "owner")]
    assert len(saved) == len(Feature)
    assert saved[Feature.FIREPLACE] is Stance.NONE  # not given: nothing said
    assert not await labeling.record("q", ListingId("p", "x"), "owner", {})
    task = await labeling.task("q", "owner")
    assert task is not None
    assert (task.labelled, task.done, task.current[Feature.POOL]) == (1, True, Stance.HAS)
    result = await EvaluateClaimExtraction(ListingsFake([home]), store).run("q", "owner")
    total = result.score.total
    # The rules find pool and fireplace; the label says pool and a forest, no fireplace.
    assert (total.true_positive, total.false_positive, total.false_negative) == (1, 1, 1)
