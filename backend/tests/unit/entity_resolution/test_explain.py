"""The match explanation (M12 «چرا مطمئنیم؟»): only what the pipeline recorded for the pair."""

from tests.fakes.er import CandidateStoreFake, LabelStoreFake
from tests.fakes.llm import NOW
from villasanj.catalog.domain.listing import ListingId
from villasanj.entity_resolution.application.explain import ExplainMatch, shown_pairs
from villasanj.entity_resolution.application.ports import ScoredCandidate
from villasanj.entity_resolution.application.villas import DecisionPolicy, StoredJudgement
from villasanj.entity_resolution.domain.evidence import (
    PairEvidence,
    PhotoEvidence,
    PhotoSimilarity,
)
from villasanj.entity_resolution.domain.labels import Label, PairLabel
from villasanj.entity_resolution.domain.pairs import BlockingSource, PairKey
from villasanj.entity_resolution.domain.scoring import Contribution, Score

J = ListingId("jabama", "1")
S = ListingId("shab", "2")
KEY = PairKey.of(J, S)


class Photos:
    def __init__(self, similarities: list[PhotoSimilarity]) -> None:
        self._similarities = similarities

    async def similarities(self, key: PairKey) -> list[PhotoSimilarity]:
        return self._similarities

    async def urls(self, listing: ListingId) -> dict[int, str]:
        return {i: f"https://{listing.platform}/{i}.jpg" for i in range(5)}


class Judgements:
    def __init__(self, found: StoredJudgement | None) -> None:
        self._found = found

    async def of_pair(self, key: PairKey) -> StoredJudgement | None:
        return self._found if self._found and self._found.key == key else None


def evidence(strong: int, weak: int) -> PairEvidence:
    return PairEvidence(
        photos=PhotoEvidence(5, 5, strong, weak, float(strong), 0.99, 0),
        distance_min_m=0.0,
        bedrooms_diff=0,
        bathrooms_diff=0,
        capacity_diff=0,
        area_ratio=0.97,
        price_ratio=1.0,
        title_similarity=0.9,
    )


SIMILAR = [
    PhotoSimilarity(0, 0, 0, 0.99, 1),  # strong
    PhotoSimilarity(0, 1, 2, 0.95, 1),  # strong, but left 0 is taken
    PhotoSimilarity(1, 1, 4, 0.93, 1),  # strong
    PhotoSimilarity(2, 3, 9, 0.86, 1),  # weak
    PhotoSimilarity(3, 4, 30, 0.40, 1),  # not a match
]


def explain(strong: int, weak: int, judge: StoredJudgement | None = None) -> ExplainMatch:
    candidate = ScoredCandidate(
        KEY,
        frozenset({BlockingSource.PHOTO_HASH}),
        True,
        evidence(strong, weak),
        Score(8.75, (Contribution("shared_photos", 6.25), Contribution("same_bedrooms", 0.5))),
    )
    return ExplainMatch(
        CandidateStoreFake([candidate]),
        Judgements(judge),
        LabelStoreFake(),
        Photos(SIMILAR),
        DecisionPolicy(threshold=-0.25),
    )


def test_photo_pairs_are_one_to_one_and_strongest_first() -> None:
    chosen = shown_pairs(SIMILAR, 10)
    assert [(p.left_position, p.right_position) for p in chosen] == [(0, 0), (1, 1), (2, 3)]


async def test_the_explanation_shows_no_more_photo_pairs_than_the_evidence_counted() -> None:
    found = await explain(strong=2, weak=0).run(S, J)
    assert found.key == KEY
    assert [p.left_url for p in found.photo_pairs] == [
        "https://jabama/0.jpg",
        "https://jabama/1.jpg",
    ]
    assert all(p.strong for p in found.photo_pairs)
    assert found.rules_match
    assert found.contributions == (("shared_photos", 6.25), ("same_bedrooms", 0.5))
    assert found.judge is None
    assert found.human is None


async def test_without_photo_matches_no_photo_pair_is_shown() -> None:
    assert (await explain(strong=0, weak=0).run(J, S)).photo_pairs == ()


async def test_the_judge_and_the_owner_come_from_their_stores() -> None:
    judge = StoredJudgement(KEY, "match", 0.92, "judge-model", ("same_interior", "same_view"))
    use_case = explain(strong=1, weak=1, judge=judge)
    labels = use_case._labels
    await labels.save_label(PairLabel(KEY, Label.MATCH, "owner", NOW))
    await labels.save_label(
        PairLabel(PairKey.of(J, ListingId("shab", "9")), Label.NON_MATCH, "owner", NOW)
    )
    found = await use_case.run(J, S)
    assert found.judge == judge
    assert found.human == "match"
    assert len(found.photo_pairs) == 2  # strong + weak counted: the two strongest pairs


async def test_a_pair_that_was_never_a_candidate_has_no_evidence() -> None:
    use_case = ExplainMatch(
        CandidateStoreFake(),
        Judgements(None),
        LabelStoreFake(),
        Photos(SIMILAR),
        DecisionPolicy(threshold=-0.25),
    )
    found = await use_case.run(J, S)
    assert found.evidence is None
    assert found.rule_score is None
    assert not found.rules_match
    assert found.photo_pairs == ()
