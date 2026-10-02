"""Places a listing's distance claims name, as OSM maps them (M9 truth check, ADR-0013 amendment).

A map lists only some shops, bakeries, restaurants, clinics and woods: a missing one on the map
is not a missing one on the ground. The nearest *mapped* place is therefore an upper bound on the
nearest real one, which can support a "within N" claim but never contradict one. City and town
centres are all on the map (checked against the gazetteer, A20), so for them the nearest mapped
centre is the best case and can contradict, like the coastline.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from enum import StrEnum

from villasanj.catalog.domain.gazetteer import place_key
from villasanj.enrichment.domain.distance_claims import (
    Assessment,
    ClaimTarget,
    DistanceClaim,
    Verdict,
    assess,
)


class PlaceKind(StrEnum):
    SUPERMARKET = "supermarket"
    BAKERY = "bakery"
    RESTAURANT = "restaurant"
    MEDICAL = "medical"
    CITY_CENTER = "city_center"
    FOREST = "forest"
    SHOPPING = "shopping"  # malls, department stores, markets


KIND_OF_TARGET: Mapping[ClaimTarget, PlaceKind] = {
    ClaimTarget.SUPERMARKET: PlaceKind.SUPERMARKET,
    ClaimTarget.BAKERY: PlaceKind.BAKERY,
    ClaimTarget.RESTAURANT: PlaceKind.RESTAURANT,
    ClaimTarget.MEDICAL: PlaceKind.MEDICAL,
    ClaimTarget.CITY_CENTER: PlaceKind.CITY_CENTER,
    ClaimTarget.FOREST: PlaceKind.FOREST,
    ClaimTarget.SHOPPING: PlaceKind.SHOPPING,
}
COMPLETE: frozenset[PlaceKind] = frozenset({PlaceKind.CITY_CENTER})
# A town's centre is an area around its OSM point, not the point: anything within this distance
# of the point counts as the centre (A20), so the best case is read generously both ways.
CENTRE_EXTENT_M = 1500.0

_SHOPS = {
    "supermarket": PlaceKind.SUPERMARKET,
    "convenience": PlaceKind.SUPERMARKET,  # «سوپرمارکت» is usually a corner shop
    "grocery": PlaceKind.SUPERMARKET,
    "general": PlaceKind.SUPERMARKET,
    "bakery": PlaceKind.BAKERY,
    "mall": PlaceKind.SHOPPING,
    "department_store": PlaceKind.SHOPPING,
}
_AMENITIES = {
    "restaurant": PlaceKind.RESTAURANT,
    "fast_food": PlaceKind.RESTAURANT,
    "hospital": PlaceKind.MEDICAL,
    "clinic": PlaceKind.MEDICAL,
    "doctors": PlaceKind.MEDICAL,
    "marketplace": PlaceKind.SHOPPING,
}


def kind_of(tags: Mapping[str, str], city_names: Collection[str]) -> PlaceKind | None:
    """The kind an OSM feature counts as; a village is a centre only if platforms call it a
    city (``city_names``: ``place_key`` of the gazetteer's cities), e.g. Javaherdeh."""
    if (shop := _SHOPS.get(tags.get("shop", ""))) is not None:
        return shop
    if (amenity := _AMENITIES.get(tags.get("amenity", ""))) is not None:
        return amenity
    place = tags.get("place")
    if place in ("city", "town"):
        return PlaceKind.CITY_CENTER
    if place == "village" and place_key(tags.get("name", "")) in city_names:
        return PlaceKind.CITY_CENTER
    if tags.get("landuse") == "forest" or tags.get("natural") == "wood":
        return PlaceKind.FOREST
    return None


def assess_place(
    claim: DistanceClaim, kind: PlaceKind, measured_m: tuple[float, float | None]
) -> Assessment:
    """A distance claim against the nearest mapped place of its kind."""
    if kind is PlaceKind.CITY_CENTER:
        low, high = measured_m
        measured_m = (
            max(0.0, low - CENTRE_EXTENT_M),
            None if high is None else max(0.0, high - CENTRE_EXTENT_M),
        )
    if kind in COMPLETE:
        return assess(claim, measured_m)
    verdicts = {_supported_by_a_partial_map(r, measured_m) for r in claim.readings()}
    verdict = verdicts.pop() if len(verdicts) == 1 else Verdict.NOT_CONFIRMED
    return Assessment(verdict, claim.metres(), measured_m)


def _supported_by_a_partial_map(
    claimed: tuple[float, float | None], measured: tuple[float, float | None]
) -> Verdict:
    claim_high, farthest = claimed[1], measured[1]
    if claim_high is not None and farthest is not None and farthest <= claim_high:
        return Verdict.SUPPORTED  # a mapped place is within the claim from anywhere in the circle
    return Verdict.NOT_CONFIRMED  # an unmapped place may be nearer: never a contradiction
