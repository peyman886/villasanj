"""Canonical villas from rule, judge and human decisions; B-cubed against the labels."""

from collections.abc import Sequence
from dataclasses import replace
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
    Waiting,
    WaitReason,
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
    def __init__(self, judged: Sequence[StoredJudgement] | None = None) -> None:
        default = [StoredJudgement(B, "match", 0.9, "m"), StoredJudgement(D, "match", 0.95, "m")]
        self._judged = list(judged or default)

    async def all(self) -> list[StoredJudgement]:
        return list(self._judged)


def setup(
    judged: Sequence[StoredJudgement] | None = None, human_queue: str | None = None
) -> tuple[BuildVillas, LabelStoreFake, Villas]:
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
        Judgements(judged),
        human_queue,
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
    assert [j.key for j in found.waiting] == [D]  # unsure: a human decides
    low = decide([(B, -1.5, True)], [StoredJudgement(B, "match", 0.7, "m")], ZONE)
    assert low.matches == []  # below the confidence floor...
    assert [j.key for j in low.waiting] == [B]  # ...a human decides
    shaky = decide([(C, 1.0, True)], [StoredJudgement(C, "non_match", 0.6, "m")], ZONE)
    assert (shaky.matches, [j.key for j in shaky.waiting]) == ([], [C])  # no merge meanwhile
    unjudged = decisions([(C, 1.0, True)], [], ZONE)
    assert [d.decided_by for d in unjudged] == [Decider.RULE]  # not judged: the rules decide
    judge_off = decisions(rows, judged, DecisionPolicy(-0.25))
    assert {d.key for d in judge_off} == {A, C, D}  # the rule threshold alone


def test_an_advisory_judge_leaves_the_merges_to_the_rules_and_orders_the_queue() -> None:
    advisory = replace(ZONE, judge_merges=False, judge_vetoes=False)
    judged = [
        StoredJudgement(B, "match", 0.9, "m"),  # below the threshold: a suggestion
        StoredJudgement(C, "non_match", 0.95, "m"),  # against a rule match: a dispute
        StoredJudgement(D, "unsure", 0.6, "m"),  # a rule match the judge cannot decide
    ]
    rows = [(A, 6.0, True), (B, -1.5, True), (C, 1.0, True), (D, 0.5, True)]
    found = decide(rows, judged, advisory)
    assert {d.key: d.decided_by for d in found.matches} == {
        A: Decider.RULE,
        C: Decider.RULE,
        D: Decider.RULE,
    }
    by_reason = {w.key: w.reason for w in found.waiting}
    assert by_reason == {B: WaitReason.SUGGESTED, C: WaitReason.DISPUTED, D: WaitReason.UNSURE}
    assert [w.key for w in sorted(found.waiting, key=Waiting.priority)] == [B, C, D]
    rules = {d.key for d in decisions(rows, [], DecisionPolicy(-0.25))}
    assert {d.key for d in found.matches} == rules  # the same merges as the rules alone


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


async def test_unsure_pairs_wait_for_a_human_and_a_label_resolves_them_once() -> None:
    judged = [StoredJudgement(B, "unsure", 0.5, "m"), StoredJudgement(D, "match", 0.6, "m")]
    build, labels, villas = setup(judged, human_queue="human")
    first = await build.run(ZONE)
    queue = await labels.queue("human")
    assert [(i.position, i.key, i.stratum) for i in queue] == [
        (0, D, "judge:unsure"),  # a "match" below the floor; more confident than B's
        (1, B, "judge:unsure"),
    ]
    assert (first.waiting_for_human, first.queued) == (2, 2)
    again = await build.run(ZONE)
    assert (again.queued, len(await labels.queue("human"))) == (0, 2)  # nothing added twice
    await labels.save_label(PairLabel(B, Label.MATCH, "owner", NOW))
    resolved = await build.run(ZONE)
    assert frozenset({J2.id, S2.id}) in {frozenset(m) for m in villas.stored.values()}
    assert (resolved.waiting_for_human, resolved.queued) == (1, 0)
    assert resolved.applied[Decider.HUMAN.value] == 1
    assert resolved.events["merged"] == 1
    settled = await build.run(ZONE)
    assert not settled.events  # the same labels: the same villas, the same ids


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
