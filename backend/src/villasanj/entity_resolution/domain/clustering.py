"""Constrained clustering of matched listings into canonical villas (ADR-0009 stages 5 and 6).

Merges are applied greedily, strongest match first. A merge that would break a constraint is
not forced; it is reported as blocked, with its reason, for human review:
- a canonical villa holds at most one listing per platform (product rule 4);
- a human "not the same villa" (cannot-link) is never overridden;
- a match into a complex's shared photos without non-photo evidence stays "same complex, unit
  unknown" (stage 7).

Canonical ids are stable across runs: a new cluster inherits the id of the old cluster it
overlaps most, and splits and merges are recorded.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from villasanj.catalog.domain.listing import ListingId
from villasanj.entity_resolution.domain.pairs import PairKey
from villasanj.shared.domain.errors import DomainError


class InvalidVilla(DomainError):
    """A canonical villa that breaks product rule 4 (two listings of one platform)."""


class Decider(StrEnum):
    RULE = "rule"
    MODEL = "model"
    JUDGE = "judge"
    HUMAN = "human"


@dataclass(frozen=True, slots=True)
class MatchDecision:
    key: PairKey
    weight: float
    decided_by: Decider
    complex_unit: bool = False  # photo-only evidence into a complex's shared photo group


class BlockReason(StrEnum):
    SAME_PLATFORM = "same_platform"
    CANNOT_LINK = "cannot_link"
    COMPLEX_UNIT = "complex_unit"


@dataclass(frozen=True, slots=True)
class BlockedMerge:
    decision: MatchDecision
    reason: BlockReason


@dataclass(frozen=True, slots=True)
class CanonicalVilla:
    id: str
    members: frozenset[ListingId]

    def __post_init__(self) -> None:
        platforms = [m.platform for m in self.members]
        if len(platforms) != len(set(platforms)):
            raise InvalidVilla(f"villa {self.id} has two listings of one platform")
        if not self.members:
            raise InvalidVilla(f"villa {self.id} has no listings")

    def listing_on(self, platform: str) -> ListingId | None:
        return next((m for m in self.members if m.platform == platform), None)


@dataclass(frozen=True, slots=True)
class Clustering:
    clusters: tuple[frozenset[ListingId], ...]  # every listing appears exactly once
    applied: tuple[MatchDecision, ...]
    blocked: tuple[BlockedMerge, ...]


def cluster(
    listings: Iterable[ListingId],
    decisions: Sequence[MatchDecision],
    cannot_links: Iterable[PairKey] = (),
) -> Clustering:
    members: dict[ListingId, set[ListingId]] = {}
    for listing in listings:
        members.setdefault(listing, {listing})
    forbidden = set(cannot_links)
    applied: list[MatchDecision] = []
    blocked: list[BlockedMerge] = []
    for decision in sorted(decisions, key=lambda d: (-d.weight, d.key)):
        left = members.setdefault(decision.key.left, {decision.key.left})
        right = members.setdefault(decision.key.right, {decision.key.right})
        if left is right:
            continue  # already together through stronger matches
        reason = _conflict(decision, left, right, forbidden)
        if reason is not None:
            blocked.append(BlockedMerge(decision, reason))
            continue
        left |= right
        for listing in right:
            members[listing] = left
        applied.append(decision)
    unique = {id(group): frozenset(group) for group in members.values()}
    clusters = tuple(sorted(unique.values(), key=lambda group: min(group)))
    return Clustering(clusters, tuple(applied), tuple(blocked))


def _conflict(
    decision: MatchDecision,
    left: set[ListingId],
    right: set[ListingId],
    forbidden: set[PairKey],
) -> BlockReason | None:
    if {m.platform for m in left} & {m.platform for m in right}:
        return BlockReason.SAME_PLATFORM
    if any(PairKey.of(a, b) in forbidden for a in left for b in right):
        return BlockReason.CANNOT_LINK
    if decision.complex_unit and decision.decided_by is not Decider.HUMAN:
        return BlockReason.COMPLEX_UNIT
    return None


class VillaEventKind(StrEnum):
    CREATED = "created"  # a new id (previous_ids: the old villas its listings came from)
    MERGED = "merged"  # one new villa covers listings of several old villas
    SPLIT = "split"  # listings of one old villa now belong to several villas
    RETIRED = "retired"  # an old id no longer names any villa


@dataclass(frozen=True, slots=True)
class VillaEvent:
    kind: VillaEventKind
    villa_id: str
    previous_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Reconciliation:
    villas: tuple[CanonicalVilla, ...]
    events: tuple[VillaEvent, ...] = field(default=())


def new_villa_id(members: Iterable[ListingId]) -> str:
    """Deterministic id for a cluster without a predecessor."""
    digest = hashlib.sha256("|".join(str(m) for m in sorted(members)).encode()).hexdigest()
    return f"v-{digest[:12]}"


def reconcile(
    previous: Mapping[str, frozenset[ListingId]], clusters: Sequence[frozenset[ListingId]]
) -> Reconciliation:
    """Keep canonical ids stable: each old id goes to the new cluster it overlaps most."""
    overlaps = sorted(
        (
            (len(group & old_members), old_id, index)
            for index, group in enumerate(clusters)
            for old_id, old_members in previous.items()
            if group & old_members
        ),
        key=lambda item: (-item[0], item[1], item[2]),
    )
    assigned: dict[int, str] = {}
    used: set[str] = set()
    for _, old_id, index in overlaps:
        if index not in assigned and old_id not in used:
            assigned[index] = old_id
            used.add(old_id)
    villas = []
    events = []
    for index, group in enumerate(clusters):
        villa_id = assigned.get(index) or new_villa_id(group)
        villas.append(CanonicalVilla(villa_id, group))
        sources = tuple(sorted(old for old, members in previous.items() if group & members))
        if index not in assigned:  # a new id, perhaps born from a split: name where it came from
            events.append(VillaEvent(VillaEventKind.CREATED, villa_id, sources))
        if len(sources) > 1:
            events.append(VillaEvent(VillaEventKind.MERGED, villa_id, sources))
    for old_id, old_members in sorted(previous.items()):
        heirs = sorted(v.id for v in villas if v.members & old_members)
        if len(heirs) > 1:
            events.append(VillaEvent(VillaEventKind.SPLIT, old_id, tuple(heirs)))
        if old_id not in used:
            events.append(VillaEvent(VillaEventKind.RETIRED, old_id))
    return Reconciliation(tuple(villas), tuple(events))
