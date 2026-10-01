"""Stratified sampling of pairs for the gold set (ADR-0009 evaluation protocol)."""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from villasanj.entity_resolution.domain.labels import QueueItem
from villasanj.entity_resolution.domain.pairs import PairKey


@dataclass(frozen=True, slots=True)
class ScoredPair:
    key: PairKey
    score: float


@dataclass(frozen=True, slots=True)
class Stratum:
    name: str
    pairs: tuple[ScoredPair, ...]
    sample: int  # how many pairs to draw


def score_bands(name: str, pairs: Sequence[ScoredPair], allocation: Sequence[int]) -> list[Stratum]:
    """Equal-size score bands, lowest first; ``allocation[i]`` pairs are drawn from band i."""
    ranked = sorted(pairs, key=lambda p: (p.score, p.key))
    bands = len(allocation)
    return [
        Stratum(
            f"{name}:band{index + 1:02d}",
            tuple(ranked[index * len(ranked) // bands : (index + 1) * len(ranked) // bands]),
            sample,
        )
        for index, sample in enumerate(allocation)
    ]


def build_queue(strata: Sequence[Stratum], seed: int) -> list[QueueItem]:
    """Draw each stratum uniformly, then interleave so every prefix covers all strata evenly.

    Strata must be disjoint. The same seed and strata always give the same queue.
    """
    rng = random.Random(seed)  # noqa: S311 - reproducible sampling, not security
    drawn: list[tuple[float, Stratum, ScoredPair]] = []
    seen: set[PairKey] = set()
    for stratum in strata:
        chosen = rng.sample(list(stratum.pairs), min(stratum.sample, len(stratum.pairs)))
        for rank, pair in enumerate(chosen):
            if pair.key in seen:
                raise ValueError(f"strata overlap on {pair.key}")
            seen.add(pair.key)
            drawn.append(((rank + rng.random()) / len(chosen), stratum, pair))
    drawn.sort(key=lambda item: item[0])
    return [
        QueueItem(position, pair.key, stratum.name, len(stratum.pairs))
        for position, (_, stratum, pair) in enumerate(drawn)
    ]
