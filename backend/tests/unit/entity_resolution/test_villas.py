"""Canonical villas from rule, judge and human decisions; B-cubed against the labels."""

from collections.abc import Sequence
from datetime import timedelta

from tests.fakes.er import CandidateStoreFake, LabelStoreFake, ListingsFake
from tests.fakes.llm import NOW
from tests.unit.entity_resolution.test_application import listing, scored
from villasanj.catalog.domain.listing import ListingId
from villasanj.entity_resolution.application.ports import MatchRun
from villasanj.entity_resolution.application.villas import (
    BuildVillas,
    DecisionPolicy,
    EvaluateVillas,
    StoredJudgement,
    decide,
    decisions,
)
from villasanj.entity_resolution.domain.clustering import CanonicalVilla, Decider, VillaEvent
from villasanj.entity_resolution.domain.labels import Label, PairLabel, QueueItem
from villasanj.entity_resolution.domain.pairs import BlockingSource, PairKey

J1, J2, J3 = (listing("jabama", str(i), 36.9) for i in range(1, 4))
S1, S2, S3 = (listing("shab", str(i), 36.9) for i in range(1, 4))
A = PairKey.of(J1.id, S1.id)  # rules: strong
B = PairKey.of(J2.id, S2.id)  # gray zone: the judge says match
C = PairKey.of(J3.id, S3.id)  # rules say match, the owner says no
D = PairKey.of(J1.id, S2.id)  # would put two shab listings in one villa
ZONE = DecisionPolicy(-0.25, judge_low=-2.0, judge_high=3.0, judge_min_confidence=0.8)


class Villas:
    def __init__(self) -> None:
        self.stored: dict[str, frozenset[ListingId]] = {}
        self.events: list[VillaEvent] = []

    async def current(self) -> dict[str, frozenset[ListingId]]:
        return dict(self.stored)

    async def replace(
        self, run_id: str, villas: Sequence[CanonicalVilla], events: Sequence[VillaEvent]
    ) -> None:
        self.stored = {v.id: v.members for v in villas}
        self.events.extend(events)

    async def get(self, villa_id: str) -> CanonicalVilla | None:
        members = self.stored.get(villa_id)
        return CanonicalVilla(villa_id, members) if members else None

    async def villa_of(self, listing: ListingId) -> CanonicalVilla | None:
        return next((CanonicalVilla(i, m) for i, m in self.stored.items() if listing in m), None)


class Judgements:
    async def all(self) -> list[StoredJudgement]:
        return [StoredJudgement(B, "match", 0.9, "m"), StoredJudgement(D, "match", 0.95, "m")]


def setup() -> tuple[BuildVillas, LabelStoreFake, Villas]:
    candidates = CandidateStoreFake(
        [
            scored(A, 6.0, BlockingSource.PHOTO_HASH),
            scored(B, -1.5, BlockingSource.GEO_ROOMS),
            scored(C, 3.0, BlockingSource.PHOTO_HASH),
            scored(D, 0.5, BlockingSource.GEO_ROOMS),
        ]
    )
    candidates.runs.append(MatchRun("00000000-0000-0000-0000-000000000123", "hash", {}, {}, NOW))
    labels = LabelStoreFake()
    villas = Villas()
    build = BuildVillas(
        candidates,
        labels,
        villas,
        ListingsFake([J1, J2, J3, S1, S2, S3]),
        ["jabama", "shab"],
        Judgements(),
    )
    return build, labels, villas


def test_the_judge_decides_its_zone_and_the_rules_the_rest() -> None:
    judged = [
        StoredJudgement(A, "non_match", 0.99, "m"),  # outside the zone: the rules decide
        StoredJudgement(B, "match", 0.9, "m"),
        StoredJudgement(C, "non_match", 0.95, "m"),  # in the zone: a veto of a rule match
        StoredJudgement(D, "unsure", 0.6, "m"),
    ]
    rows = [(A, 6.0, True), (B, -1.5, True), (C, 1.0, True), (D, 0.5, True)]
    found = decide(rows, judged, ZONE)
    by_key = {d.key: d for d in found.matches}
    assert by_key[A].decided_by is Decider.RULE
    assert by_key[B].decided_by is Decider.JUDGE
    assert by_key[B].weight < by_key[A].weight
    assert C not in by_key  # vetoed
    assert found.waiting == [D]  # unsure: a human decides
    low = decisions([(B, -1.5, True)], [StoredJudgement(B, "match", 0.7, "m")], ZONE)
    assert low == []  # below the confidence floor
    unjudged = decisions([(C, 1.0, True)], [], ZONE)
    assert [d.decided_by for d in unjudged] == [Decider.RULE]  # not judged: the rules decide
    judge_off = decisions(rows, judged, DecisionPolicy(-0.25))
    assert {d.key for d in judge_off} == {A, C, D}  # the rule threshold alone


async def test_villas_keep_one_listing_per_platform_and_obey_the_owner() -> None:
    build, labels, villas = setup()
    await labels.save_label(PairLabel(C, Label.NON_MATCH, "owner", NOW))
    report = await build.run(ZONE)
    groups = {frozenset(m) for m in villas.stored.values()}
    assert frozenset({J1.id, S1.id}) in groups
    assert frozenset({J2.id, S2.id}) in groups
    assert frozenset({J3.id}) in groups  # the owner's cannot-link holds
    assert frozenset({S3.id}) in groups
    assert report.blocked["same_platform"] == 1  # D would join S2 to J1's villa with S1
    assert report.blocked["cannot_link"] == 1
    assert (report.villas, report.multi_platform) == (4, 2)
    again = await build.run(ZONE)
    assert again.events.get("created", 0) == 0  # same clusters, same ids


async def test_bcubed_compares_the_machine_clustering_with_the_labels() -> None:
    build, labels, _ = setup()
    items = [QueueItem(i, key, "s", 3) for i, key in enumerate((A, B, C), start=1)]
    await labels.save_queue("gold", items)
    for key, verdict in ((A, Label.MATCH), (B, Label.MATCH), (C, Label.NON_MATCH)):
        await labels.save_label(PairLabel(key, verdict, "owner", NOW + timedelta(seconds=1)))
    without_judge = await EvaluateVillas(build, labels).run(DecisionPolicy(-0.25), "gold", "owner")
    assert without_judge.bcubed is not None
    assert without_judge.bcubed.precision < 1  # C was merged by the rules
    assert without_judge.bcubed.recall < 1  # B was missed
    with_judge = await EvaluateVillas(build, labels).run(ZONE, "gold", "owner")
    assert with_judge.bcubed is not None
    assert with_judge.bcubed.recall > without_judge.bcubed.recall
