"""Shared evidence values for ER tests."""

from villasanj.entity_resolution.domain.evidence import PairEvidence, PhotoEvidence

NO_EVIDENCE = PairEvidence(
    photos=PhotoEvidence(5, 5, 0, 0, 0.0, None, None),
    distance_min_m=250.0,
    bedrooms_diff=0,
    bathrooms_diff=None,
    capacity_diff=None,
    area_ratio=None,
    price_ratio=None,
    title_similarity=0.0,
)
