"""Photo tag thresholds from hand labels: precision first, a tag below the bar is not used."""

import pytest

from villasanj.enrichment.domain.features import Feature
from villasanj.enrichment.domain.photo_tags import (
    FEATURE_OF,
    MIN_PREDICTED,
    PROMPTS,
    Labelled,
    PhotoTag,
    choose_threshold,
)


def labels(*pairs: tuple[float, bool]) -> list[Labelled]:
    return [Labelled(score, present) for score, present in pairs]


def test_every_tag_has_a_prompt_and_a_feature() -> None:
    assert set(PROMPTS) == set(PhotoTag)
    assert set(FEATURE_OF) == set(PhotoTag)
    assert all(isinstance(f, Feature) for f in FEATURE_OF.values())


def test_the_lowest_threshold_that_keeps_precision_wins() -> None:
    # 12 true pools score high, then one false positive, then two more pools, then negatives.
    data = labels(
        *[(0.9 - i * 0.01, True) for i in range(12)],
        (0.70, False),
        (0.65, True),
        (0.60, True),
        *[(0.1, False) for _ in range(20)],
    )
    chosen = choose_threshold(PhotoTag.POOL, data)
    assert chosen.threshold == 0.60  # 14 of 15 predicted are pools: 93% precision
    assert chosen.positives == 14
    assert chosen.precision is not None
    assert chosen.precision.estimate == pytest.approx(14 / 15)
    assert chosen.recall is not None
    assert chosen.recall.estimate == 1.0


def test_a_tag_that_never_reaches_the_bar_is_not_used() -> None:
    noisy = labels(*[(0.9 - i * 0.01, i % 2 == 0) for i in range(30)])  # 50% precision anywhere
    chosen = choose_threshold(PhotoTag.FIREPLACE, noisy)
    assert (chosen.threshold, chosen.precision, chosen.recall) == (None, None, None)
    few = labels(*[(0.9, True) for _ in range(MIN_PREDICTED - 1)])
    assert choose_threshold(PhotoTag.FIREPLACE, few).threshold is None  # too few to tell
    none = labels(*[(0.5, False) for _ in range(20)])
    assert choose_threshold(PhotoTag.FIREPLACE, none).threshold is None
