"""Transparent rule baseline (ADR-0009 stage 3, M3): a sum of explained contributions.

Weights are hand-set, in log-odds-like points, and kept deliberately simple so that every merge can
be explained ("3 shared photos +7.5, same bedrooms +0.5, 400 m apart +1"). Only the decision
threshold is chosen from the gold set; Splink replaces the weights in M5.
"""

from __future__ import annotations

from dataclasses import dataclass

from villasanj.entity_resolution.domain.evidence import PairEvidence

MIN_PHOTOS_FOR_ABSENCE = 3  # "no shared photo" only counts when both sides show enough photos


@dataclass(frozen=True, slots=True)
class ScoreWeights:
    per_weighted_photo: float = 2.5
    max_weighted_photos: float = 4.0
    no_shared_photo: float = -2.0
    overlapping_location: float = 1.0
    far_m: float = 1000.0
    far: float = -3.0
    very_far_m: float = 3000.0
    very_far: float = -6.0
    same_bedrooms: float = 0.5
    bedrooms_off_by_one: float = -0.5
    bedrooms_off_by_more: float = -2.5
    capacity_far_apart: int = 3
    capacity_mismatch: float = -1.0
    area_ratio_min: float = 0.6
    area_mismatch: float = -1.0
    price_ratio_soft: float = 1.67
    price_soft_mismatch: float = -1.0
    price_ratio_hard: float = 2.5
    price_hard_mismatch: float = -2.0
    similar_titles_min: float = 0.5
    similar_titles: float = 1.0


DEFAULT_WEIGHTS = ScoreWeights()


@dataclass(frozen=True, slots=True)
class Contribution:
    feature: str
    points: float


@dataclass(frozen=True, slots=True)
class Score:
    value: float
    contributions: tuple[Contribution, ...]


def score(evidence: PairEvidence, weights: ScoreWeights = DEFAULT_WEIGHTS) -> Score:
    parts: list[Contribution] = []

    def add(feature: str, points: float) -> None:
        parts.append(Contribution(feature, round(points, 4)))

    photos = evidence.photos
    if photos.weighted_matches > 0:
        weighted = min(photos.weighted_matches, weights.max_weighted_photos)
        add("shared_photos", weights.per_weighted_photo * weighted)
    elif min(photos.compared_left, photos.compared_right) >= MIN_PHOTOS_FOR_ABSENCE:
        add("no_shared_photo", weights.no_shared_photo)

    distance = evidence.distance_min_m
    if distance is not None:
        if distance == 0:
            add("location_overlaps", weights.overlapping_location)
        elif distance > weights.very_far_m:
            add("very_far_apart", weights.very_far)
        elif distance > weights.far_m:
            add("far_apart", weights.far)

    if evidence.bedrooms_diff == 0:
        add("same_bedrooms", weights.same_bedrooms)
    elif evidence.bedrooms_diff == 1:
        add("bedrooms_off_by_one", weights.bedrooms_off_by_one)
    elif evidence.bedrooms_diff is not None:
        add("bedrooms_differ", weights.bedrooms_off_by_more)

    if evidence.capacity_diff is not None and evidence.capacity_diff >= weights.capacity_far_apart:
        add("capacity_differs", weights.capacity_mismatch)
    if evidence.area_ratio is not None and evidence.area_ratio < weights.area_ratio_min:
        add("area_differs", weights.area_mismatch)

    ratio = evidence.price_ratio
    if ratio is not None:
        if ratio > weights.price_ratio_hard:
            add("price_far_apart", weights.price_hard_mismatch)
        elif ratio > weights.price_ratio_soft:
            add("price_apart", weights.price_soft_mismatch)

    if evidence.title_similarity >= weights.similar_titles_min:
        add("similar_titles", weights.similar_titles)

    return Score(round(sum(p.points for p in parts), 4), tuple(parts))
