"""Blocking, evidence and scoring for every candidate pair (ADR-0009 stages 1-3)."""

from __future__ import annotations

import bisect
import hashlib
import json
import uuid
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass

import structlog

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import Listing, ListingId
from villasanj.entity_resolution.application.ports import (
    CandidateStore,
    MatchRun,
    PhotoIndex,
    ScoredCandidate,
)
from villasanj.entity_resolution.domain.evidence import (
    distance_min_m,
    pair_evidence,
    photo_evidence,
)
from villasanj.entity_resolution.domain.pairs import BlockingSource, PairKey
from villasanj.entity_resolution.domain.scoring import DEFAULT_WEIGHTS, ScoreWeights, score
from villasanj.shared.application.clock import Clock

log = structlog.get_logger(__name__)

METRES_PER_DEGREE_LAT = 111_000.0
MAX_RADIUS_M = 1000  # largest obfuscation radius we expect on the other side


@dataclass(frozen=True, slots=True)
class BlockingConfig:
    geo_slack_m: float = 500.0  # beyond the published obfuscation radii
    rooms_tolerance: int = 1
    max_hamming: int = 10
    same_platform_hamming: int = 6
    neighbours: int = 5
    min_cosine: float = 0.85
    same_platform_cosine: float = 0.95
    wide_slack_m: float = 2000.0


DEFAULT_BLOCKING = BlockingConfig()


class MatchListings:
    def __init__(
        self,
        listings: ListingReader,
        index: PhotoIndex,
        store: CandidateStore,
        clock: Clock,
        config: BlockingConfig = DEFAULT_BLOCKING,
        weights: ScoreWeights = DEFAULT_WEIGHTS,
    ) -> None:
        self._listings = listings
        self._index = index
        self._store = store
        self._clock = clock
        self._config = config
        self._weights = weights

    async def run(self, platforms: Sequence[str]) -> MatchRun:
        listings = {
            listing.id: listing
            for platform in platforms
            for listing in await self._listings.listings(platform)
        }
        sources = self._block(listings, platforms)
        candidates = []
        for key in sorted(sources):
            if key.left not in listings or key.right not in listings:
                continue  # photos of a listing that is no longer in the catalog
            blocked = bool(sources[key] - {BlockingSource.WIDE})
            evidence = score_value = None
            if blocked:
                photos = photo_evidence(
                    self._index.similarities(key),
                    self._index.photo_count(key.left),
                    self._index.photo_count(key.right),
                )
                evidence = pair_evidence(listings[key.left], listings[key.right], photos)
                score_value = score(evidence, self._weights)
            candidates.append(
                ScoredCandidate(key, frozenset(sources[key]), blocked, evidence, score_value)
            )
        counts = Counter(source.value for c in candidates for source in c.sources)
        counts.update(blocked=sum(c.blocked for c in candidates), total=len(candidates))
        config: dict[str, object] = {
            "platforms": list(platforms),
            "blocking": asdict(self._config),
            "weights": asdict(self._weights),
            "image_model": self._index.image_model,
        }
        run = MatchRun(
            id=str(uuid.uuid4()),
            dataset_hash=self._dataset_hash(listings, config),
            config=config,
            counts=dict(counts),
            created_at=self._clock.now(),
        )
        await self._store.replace(run, candidates)
        log.info("er.match.finished", run_id=run.id, **run.counts)
        return run

    def _block(
        self, listings: dict[ListingId, Listing], platforms: Sequence[str]
    ) -> dict[PairKey, set[BlockingSource]]:
        config = self._config
        sources: defaultdict[PairKey, set[BlockingSource]] = defaultdict(set)
        by_platform = {p: [x for x in listings.values() if x.id.platform == p] for p in platforms}
        for i, first in enumerate(platforms):
            for second in platforms[i + 1 :]:
                for left, right in _nearby(by_platform[first], by_platform[second], config):
                    distance = distance_min_m(left, right)
                    if distance is None:
                        continue
                    key = PairKey.of(left.id, right.id)
                    if distance <= config.geo_slack_m and _rooms_compatible(left, right, config):
                        sources[key].add(BlockingSource.GEO_ROOMS)
                    elif distance <= config.wide_slack_m:
                        sources[key].add(BlockingSource.WIDE)
        for key, hamming in self._index.hash_pairs(config.max_hamming).items():
            if key.cross_platform:
                sources[key].add(BlockingSource.PHOTO_HASH)
            elif hamming <= config.same_platform_hamming:
                sources[key].add(BlockingSource.SAME_PLATFORM_PHOTOS)
        for key, cosine in self._index.embedding_pairs(
            config.neighbours, config.min_cosine
        ).items():
            if key.cross_platform:
                sources[key].add(BlockingSource.PHOTO_EMBEDDING)
            elif cosine >= config.same_platform_cosine:
                sources[key].add(BlockingSource.SAME_PLATFORM_PHOTOS)
        for found in sources.values():  # the wide net only holds unblocked pairs
            if len(found) > 1:
                found.discard(BlockingSource.WIDE)
        return dict(sources)

    def _dataset_hash(self, listings: dict[ListingId, Listing], config: dict[str, object]) -> str:
        digest = hashlib.sha256()
        for listing_id in sorted(listings):
            digest.update(f"{listing_id}={listings[listing_id].provenance.snapshot_id}\n".encode())
        digest.update(self._index.digest.encode())
        digest.update(json.dumps(config, sort_keys=True).encode())
        return digest.hexdigest()


def _rooms_compatible(left: Listing, right: Listing, config: BlockingConfig) -> bool:
    if left.bedrooms is None or right.bedrooms is None:
        return True
    return abs(left.bedrooms - right.bedrooms) <= config.rooms_tolerance


def _nearby(
    first: Sequence[Listing], second: Sequence[Listing], config: BlockingConfig
) -> list[tuple[Listing, Listing]]:
    """Pairs within the wide-net latitude band (cheap prefilter before exact distances)."""
    located = sorted(
        ((x.location.point.lat, x) for x in second if x.location is not None),
        key=lambda item: (item[0], item[1].id),
    )
    lats = [lat for lat, _ in located]
    pairs: list[tuple[Listing, Listing]] = []
    for left in first:
        if left.location is None:
            continue
        reach = config.wide_slack_m + (left.location.radius_m or 0) + MAX_RADIUS_M
        band = reach / METRES_PER_DEGREE_LAT
        lat = left.location.point.lat
        start = bisect.bisect_left(lats, lat - band)
        stop = bisect.bisect_right(lats, lat + band)
        pairs.extend((left, right) for _, right in located[start:stop])
    return pairs
