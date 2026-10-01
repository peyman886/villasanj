"""Zero-shot photo tags as evidence for features, gated by hand labels (ROADMAP M9 criterion 2).

A tag's raw score is a sigmoid probability from an image-text model; only its rank is meaningful
until labels exist. From the owner's labels, each tag gets the lowest threshold whose precision is
at least ``MIN_PRECISION`` (with enough predicted positives to mean something). A tag that never
reaches it is not used as evidence at all.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from villasanj.enrichment.domain.features import Feature
from villasanj.entity_resolution.domain.evaluation import Interval, wilson

PROMPT_VERSION = "1"
MIN_PRECISION = 0.85
MIN_PREDICTED = 10  # fewer predicted positives than this cannot show 85% precision


class PhotoTag(StrEnum):
    POOL = "pool"
    JACUZZI = "jacuzzi"
    SEA_VIEW = "sea_view"
    FOREST = "forest"
    FIREPLACE = "fireplace"
    BARBECUE = "barbecue"


# One English prompt per tag (the image-text model was trained on English captions).
PROMPTS: dict[PhotoTag, str] = {
    PhotoTag.POOL: "a photo of a swimming pool",
    PhotoTag.JACUZZI: "a photo of a jacuzzi hot tub",
    PhotoTag.SEA_VIEW: "a photo with a view of the sea",
    PhotoTag.FOREST: "a photo of a forest",
    PhotoTag.FIREPLACE: "a photo of a fireplace",
    PhotoTag.BARBECUE: "a photo of a barbecue grill",
}

FEATURE_OF: dict[PhotoTag, Feature] = {
    PhotoTag.POOL: Feature.POOL,
    PhotoTag.JACUZZI: Feature.JACUZZI,
    PhotoTag.SEA_VIEW: Feature.SEA_VIEW,
    PhotoTag.FOREST: Feature.FOREST,
    PhotoTag.FIREPLACE: Feature.FIREPLACE,
    PhotoTag.BARBECUE: Feature.BARBECUE,
}


@dataclass(frozen=True, slots=True)
class Labelled:
    score: float
    present: bool


@dataclass(frozen=True, slots=True)
class TagThreshold:
    tag: PhotoTag
    threshold: float | None  # None: the tag never reaches the precision bar and is not used
    precision: Interval | None
    recall: Interval | None
    positives: int  # labelled photos that show the tag
    labelled: int


def choose_threshold(
    tag: PhotoTag,
    labels: Sequence[Labelled],
    min_precision: float = MIN_PRECISION,
    min_predicted: int = MIN_PREDICTED,
) -> TagThreshold:
    """The threshold with the best recall among those at or above the precision bar."""
    positives = sum(item.present for item in labels)
    best: tuple[float, int, int] | None = None  # (threshold, true positives, predicted)
    for threshold in sorted({item.score for item in labels}, reverse=True):
        predicted = [item for item in labels if item.score >= threshold]
        hits = sum(item.present for item in predicted)
        if len(predicted) < min_predicted or hits / len(predicted) < min_precision:
            continue
        if best is None or hits > best[1]:
            best = (threshold, hits, len(predicted))
    if best is None or positives == 0:
        return TagThreshold(tag, None, None, None, positives, len(labels))
    threshold, hits, called = best
    return TagThreshold(
        tag, threshold, wilson(hits, called), wilson(hits, positives), positives, len(labels)
    )
