"""Why two listings are one villa, from what the pipeline recorded (M12 «چرا مطمئنیم؟»).

Nothing here decides anything or invents a reason: the explanation reads the pair's stored
candidate (its evidence and rule score), the judge's stored verdict, the owner's label, and the
photo pairs behind the evidence's photo matches. Photo pairs are recomputed from the stored
fingerprints and embeddings with the same similarity code and thresholds as the matcher, one to
one and strongest first, and never more than the evidence counted.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from villasanj.catalog.domain.listing import ListingId
from villasanj.entity_resolution.application.ports import CandidateStore, LabelStore
from villasanj.entity_resolution.application.villas import DecisionPolicy, StoredJudgement
from villasanj.entity_resolution.domain.evidence import PairEvidence, PhotoSimilarity
from villasanj.entity_resolution.domain.pairs import PairKey

MAX_PHOTO_PAIRS = 4


class PairPhotos(Protocol):
    """The stored photos of two listings, compared exactly as the matcher compares them."""

    async def similarities(self, key: PairKey) -> list[PhotoSimilarity]: ...

    async def urls(self, listing: ListingId) -> dict[int, str]:
        """Photo position -> URL, for the fingerprinted photos of a listing."""
        ...


class PairJudgements(Protocol):
    async def of_pair(self, key: PairKey) -> StoredJudgement | None: ...


@dataclass(frozen=True, slots=True)
class PhotoPair:
    left_url: str
    right_url: str
    hamming: int | None
    cosine: float | None
    strong: bool  # near-identical (else a close match, counted at half weight)


@dataclass(frozen=True, slots=True)
class MatchExplanation:
    key: PairKey
    evidence: PairEvidence | None  # None: the pair was never a scored candidate
    rule_score: float | None
    threshold: float
    contributions: tuple[tuple[str, float], ...]  # (feature, points), as the score recorded
    photo_pairs: tuple[PhotoPair, ...]
    judge: StoredJudgement | None
    human: str | None  # the owner's label ("match", "non_match", "unsure"), if any

    @property
    def rules_match(self) -> bool:
        return self.rule_score is not None and self.rule_score >= self.threshold


def shown_pairs(similarities: Sequence[PhotoSimilarity], limit: int) -> list[PhotoSimilarity]:
    """The matched photo pairs, one to one and strongest first (the evidence's own matching)."""
    ranked = sorted(
        (p for p in similarities if p.strength > 0),
        key=lambda p: (-p.strength, -(p.cosine or 0.0), p.hamming if p.hamming is not None else 64),
    )
    used_left: set[int] = set()
    used_right: set[int] = set()
    chosen: list[PhotoSimilarity] = []
    for pair in ranked:
        if pair.left_position in used_left or pair.right_position in used_right:
            continue
        used_left.add(pair.left_position)
        used_right.add(pair.right_position)
        chosen.append(pair)
    return chosen[:limit]


class ExplainMatch:
    def __init__(
        self,
        candidates: CandidateStore,
        judgements: PairJudgements,
        labels: LabelStore,
        photos: PairPhotos,
        policy: DecisionPolicy,
        labeler: str = "owner",
    ) -> None:
        self._candidates = candidates
        self._judgements = judgements
        self._labels = labels
        self._photos = photos
        self._policy = policy
        self._labeler = labeler

    async def run(self, a: ListingId, b: ListingId) -> MatchExplanation:
        key = PairKey.of(a, b)
        candidate = await self._candidates.get(key)
        evidence = candidate.evidence if candidate else None
        score = candidate.score if candidate else None
        human = next(
            (lb.label.value for lb in await self._labels.labels(self._labeler) if lb.key == key),
            None,
        )
        matched = evidence.photos.strong_matches + evidence.photos.weak_matches if evidence else 0
        pairs: tuple[PhotoPair, ...] = ()
        if matched:
            left_urls = await self._photos.urls(key.left)
            right_urls = await self._photos.urls(key.right)
            chosen = shown_pairs(
                await self._photos.similarities(key), min(matched, MAX_PHOTO_PAIRS)
            )
            pairs = tuple(
                PhotoPair(
                    left_urls[p.left_position],
                    right_urls[p.right_position],
                    p.hamming,
                    p.cosine,
                    p.strength == 1.0,
                )
                for p in chosen
                if p.left_position in left_urls and p.right_position in right_urls
            )
        return MatchExplanation(
            key=key,
            evidence=evidence,
            rule_score=score.value if score else None,
            threshold=self._policy.threshold,
            contributions=tuple((c.feature, c.points) for c in score.contributions)
            if score
            else (),
            photo_pairs=pairs,
            judge=await self._judgements.of_pair(key),
            human=human,
        )
