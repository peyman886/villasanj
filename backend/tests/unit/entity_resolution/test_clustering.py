"""Constrained clustering, stable canonical ids and B-cubed metrics."""

import pytest

from villasanj.catalog.domain.listing import ListingId
from villasanj.entity_resolution.domain.clustering import (
    BlockReason,
    CanonicalVilla,
    Decider,
    InvalidVilla,
    MatchDecision,
    VillaEventKind,
    cluster,
    new_villa_id,
    reconcile,
)
from villasanj.entity_resolution.domain.evaluation import bcubed
from villasanj.entity_resolution.domain.pairs import PairKey

J1, J2, J3 = (ListingId("jabama", str(i)) for i in (1, 2, 3))
S1, S2 = (ListingId("shab", str(i)) for i in (1, 2))
O1 = ListingId("otaghak", "1")


def match(a: ListingId, b: ListingId, weight: float, **extra: object) -> MatchDecision:
    values: dict[str, object] = {"decided_by": Decider.RULE}
    values.update(extra)
    return MatchDecision(PairKey.of(a, b), weight, **values)  # type: ignore[arg-type]


def test_strongest_matches_merge_first_and_one_listing_per_platform_holds() -> None:
    result = cluster(
        [J1, J2, S1, O1],
        [match(J1, S1, 9.0), match(J2, S1, 7.0), match(S1, O1, 5.0)],
    )
    assert set(result.clusters) == {frozenset({J1, S1, O1}), frozenset({J2})}
    assert [b.reason for b in result.blocked] == [BlockReason.SAME_PLATFORM]
    assert result.blocked[0].decision.key == PairKey.of(J2, S1)
    assert len(result.applied) == 2


def test_human_cannot_links_are_never_overridden_even_transitively() -> None:
    result = cluster(
        [J1, S1, O1],
        [match(J1, S1, 9.0), match(S1, O1, 8.0)],
        cannot_links=[PairKey.of(J1, O1)],  # merging S1-O1 would put J1 and O1 together
    )
    assert set(result.clusters) == {frozenset({J1, S1}), frozenset({O1})}
    assert result.blocked[0].reason is BlockReason.CANNOT_LINK


def test_complex_unit_matches_wait_for_a_human() -> None:
    blocked = cluster([J1, S1], [match(J1, S1, 9.0, complex_unit=True)])
    assert blocked.blocked[0].reason is BlockReason.COMPLEX_UNIT
    confirmed = cluster([J1, S1], [match(J1, S1, 9.0, complex_unit=True, decided_by=Decider.HUMAN)])
    assert confirmed.clusters == (frozenset({J1, S1}),)


def test_redundant_matches_inside_a_cluster_are_ignored_and_unknown_listings_join() -> None:
    result = cluster([], [match(J1, S1, 9.0), match(S1, O1, 8.0), match(J1, O1, 7.0)])
    assert result.clusters == (frozenset({J1, S1, O1}),)
    assert len(result.applied) == 2
    assert result.blocked == ()


def test_a_villa_never_holds_two_listings_of_one_platform() -> None:
    with pytest.raises(InvalidVilla):
        CanonicalVilla("v1", frozenset({J1, J2}))
    with pytest.raises(InvalidVilla):
        CanonicalVilla("v1", frozenset())
    villa = CanonicalVilla("v1", frozenset({J1, S1}))
    assert villa.listing_on("shab") == S1
    assert villa.listing_on("otaghak") is None


def test_ids_are_kept_where_the_villa_continues_and_history_is_recorded() -> None:
    previous = {"v-a": frozenset({J1, S1}), "v-b": frozenset({J2, S2}), "v-c": frozenset({J3})}
    clusters = [
        frozenset({J1, S1, O1}),
        frozenset({J2}),
        frozenset({S2}),
        frozenset({J3, ListingId("shab", "9")}),
    ]
    result = reconcile(previous, clusters)
    ids = {v.members: v.id for v in result.villas}
    assert ids[frozenset({J1, S1, O1})] == "v-a"  # grew, same villa
    assert ids[frozenset({J3, ListingId("shab", "9")})] == "v-c"
    split_heirs = {ids[frozenset({J2})], ids[frozenset({S2})]}
    assert "v-b" in split_heirs  # one heir keeps the id, the other is new
    kinds = {(e.kind, e.villa_id) for e in result.events}
    assert (VillaEventKind.SPLIT, "v-b") in kinds
    assert (VillaEventKind.CREATED, (split_heirs - {"v-b"}).pop()) in kinds


def test_merges_and_retired_ids_are_recorded() -> None:
    previous = {"v-a": frozenset({J1}), "v-b": frozenset({S1})}
    result = reconcile(previous, [frozenset({J1, S1})])
    (villa,) = result.villas
    assert villa.id == "v-a"  # ties go to the smaller id
    kinds = [(e.kind, e.villa_id, e.previous_ids) for e in result.events]
    assert (VillaEventKind.MERGED, "v-a", ("v-a", "v-b")) in kinds
    assert (VillaEventKind.RETIRED, "v-b", ()) in kinds


def test_new_ids_are_deterministic() -> None:
    assert new_villa_id([S1, J1]) == new_villa_id([J1, S1])
    assert new_villa_id([J1]).startswith("v-")
    assert reconcile({}, [frozenset({J1})]).villas[0].id == new_villa_id([J1])


def test_a_split_never_gives_two_villas_one_id() -> None:
    # The merged villa was born as J1 alone, so J1 alone hashes to its id; after the split the
    # old id goes to the first part, and J1 needs another one (found on real data, 2026-10-03).
    born = new_villa_id([J1])
    result = reconcile({born: frozenset({J1, S1})}, [frozenset({S1}), frozenset({J1})])
    ids = [v.id for v in result.villas]
    assert ids[0] == born
    assert len(set(ids)) == 2
    assert ids[1] == new_villa_id([J1], {born})  # still deterministic
    retired = reconcile({born: frozenset({S1})}, [frozenset({J1})])
    assert retired.villas[0].id != born  # a retired id is never reused for another villa


def test_bcubed_rewards_exact_clusters_and_penalises_over_and_under_merging() -> None:
    gold = [frozenset({J1, S1}), frozenset({J2}), frozenset({S2})]
    perfect = bcubed(gold, gold)
    assert perfect is not None
    assert (perfect.precision, perfect.recall, perfect.f1, perfect.elements) == (1.0, 1.0, 1.0, 4)
    over = bcubed([frozenset({J1, S1, J2})], gold)
    assert over is not None
    assert over.recall == 1.0
    assert over.precision == pytest.approx((2 / 3 + 2 / 3 + 1 / 3) / 3)
    under = bcubed([frozenset({J1}), frozenset({S1})], gold)
    assert under is not None
    assert (under.precision, under.recall) == (1.0, 0.5)
    assert bcubed([frozenset({O1})], gold) is None
