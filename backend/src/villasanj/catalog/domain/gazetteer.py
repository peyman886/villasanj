"""Gazetteer: resolve messy place names ("سفید تمشک", "روستای لرسانور") to canonical places."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum

from villasanj.shared.domain.persian_text import ZWNJ, normalize_persian

_PREFIXES = ("روستای ", "روستا ", "دهکده ", "شهر ", "منطقه ", "محله ")
_PARTS = re.compile(r"[،,.;/()\-]+|\s+و\s+")
_IGNORED = re.compile(rf"[\s{ZWNJ}]+")
# Orthographic variants writers use interchangeably in place names ("اکبراباد", "رجائی").
_SPELLING = str.maketrans(
    {
        "\N{ARABIC LETTER ALEF WITH MADDA ABOVE}": "\N{ARABIC LETTER ALEF}",
        "\N{ARABIC LETTER YEH WITH HAMZA ABOVE}": "\N{ARABIC LETTER FARSI YEH}",
        "\N{ARABIC LETTER HAMZA}": None,
    }
)


class PlaceKind(StrEnum):
    CITY = "city"
    LOCALITY = "locality"  # village or neighbourhood


@dataclass(frozen=True, slots=True)
class Place:
    slug: str
    name_fa: str
    kind: PlaceKind
    parent: str | None = None  # slug of the containing city
    aliases: frozenset[str] = field(default_factory=frozenset)


def place_key(text: str) -> str:
    """Spelling-insensitive key: normalized Persian, no prefixes, no spaces or ZWNJ, lower Latin."""
    normalized = normalize_persian(text).lower().translate(_SPELLING)
    for prefix in _PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized.removeprefix(prefix)
            break
    return _IGNORED.sub("", normalized)


class Gazetteer:
    def __init__(self, places: Iterable[Place]) -> None:
        self._places = {place.slug: place for place in places}
        self._index: dict[str, Place] = {}
        for place in self._places.values():
            for name in (place.name_fa, place.slug, *place.aliases):
                key = place_key(name)
                existing = self._index.get(key)
                if existing is not None and existing.slug != place.slug:
                    raise ValueError(f"name {name!r} is ambiguous: {existing.slug} / {place.slug}")
                self._index[key] = place

    def __len__(self) -> int:
        return len(self._places)

    def get(self, slug: str) -> Place | None:
        return self._places.get(slug)

    def resolve(self, text: str | None) -> Place | None:
        """The most specific known place mentioned in ``text``.

        Localities beat cities; among several, the last one wins, because addresses are written
        from general to specific ("منطقه دوهزار - روستای برسه"). Unknown text resolves to nothing.
        """
        if not text:
            return None
        whole = self._index.get(place_key(text))
        if whole is not None:
            return whole
        matches = [
            self._index[key]
            for part in _PARTS.split(text)
            if (key := place_key(part)) in self._index
        ]
        localities = [m for m in matches if m.kind is PlaceKind.LOCALITY]
        best = localities or matches
        return best[-1] if best else None
