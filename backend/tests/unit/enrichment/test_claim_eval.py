"""Claim-level precision and recall of the rule-based extraction against a person's labels."""

from villasanj.enrichment.domain.claim_eval import ClaimScore, Stance, stances
from villasanj.enrichment.domain.features import Feature, extract_claims


def test_stances_follow_the_villas_own_word() -> None:
    found = stances(extract_claims("ویلا با استخر و شومینه، بدون پارکینگ، استخر مشاع شهرک"))
    assert found[Feature.POOL] is Stance.HAS  # its own pool beats the shared one
    assert found[Feature.FIREPLACE] is Stance.HAS
    assert found[Feature.PARKING] is Stance.HAS_NOT
    assert found[Feature.JACUZZI] is Stance.NONE
    shared = stances(extract_claims("استخر مشاع مجموعه"))
    assert shared[Feature.POOL] is Stance.SHARED


def test_a_wrong_stance_is_both_a_false_positive_and_a_false_negative() -> None:
    score = ClaimScore()
    score.add(
        {Feature.POOL: Stance.HAS, Feature.PARKING: Stance.HAS, Feature.FOREST: Stance.NONE},
        {Feature.POOL: Stance.HAS, Feature.PARKING: Stance.HAS_NOT, Feature.FOREST: Stance.HAS},
    )
    total = score.total
    assert (total.true_positive, total.false_positive, total.false_negative) == (1, 1, 2)
    assert score.per_feature[Feature.FOREST].false_negative == 1
    assert score.per_feature[Feature.JACUZZI].true_positive == 0  # nothing said, nothing counted
