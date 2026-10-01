"""Slot-based generation and its deterministic verifier (ADR-0007 decisions 4 and 5).

An LLM writes prose with slots (``{F3}`` for a fact, ``{C1}`` for a comparison) and never writes
digits, money words or measurable comparatives itself. Code computed every fact and every
comparison's direction, so the renderer can fill them in, and a wrong number or a reversed
"cheaper" becomes structurally impossible. The verifier enforces it; the caller retries once with
the violations, then falls back to a deterministic template.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from villasanj.shared.domain.persian_text import ZWNJ, normalize_persian
from villasanj.shared.domain.provenance import Provenance

SLOT = re.compile(r"\{([FC]\d{1,4})\}")
_DIGITS = re.compile(
    "[0-9"
    "\N{ARABIC-INDIC DIGIT ZERO}-\N{ARABIC-INDIC DIGIT NINE}"
    "\N{EXTENDED ARABIC-INDIC DIGIT ZERO}-\N{EXTENDED ARABIC-INDIC DIGIT NINE}]"
)
_MONEY_AND_MAGNITUDE = re.compile("(تومان|ریال|هزار|میلیون|میلیارد|درصد|\N{ARABIC PERCENT SIGN}|%)")
# Measurable comparatives only (price, distance, size, amount); subjective ones ("بهتر") are prose.
_COMPARATIVE = re.compile(rf"(ارزان|گران|نزدیک|دور|بزرگ|کوچک|جادار|وسیع|بیش|کم)[{ZWNJ} ]?تر(ین)?")


class Relation(StrEnum):
    CHEAPER = "cheaper"
    PRICIER = "pricier"
    CLOSER = "closer"
    FARTHER = "farther"
    LARGER = "larger"
    SMALLER = "smaller"


RELATION_WORD: dict[Relation, str] = {
    Relation.CHEAPER: f"ارزان{ZWNJ}تر",
    Relation.PRICIER: f"گران{ZWNJ}تر",
    Relation.CLOSER: f"نزدیک{ZWNJ}تر",
    Relation.FARTHER: "دورتر",
    Relation.LARGER: f"بزرگ{ZWNJ}تر",
    Relation.SMALLER: f"کوچک{ZWNJ}تر",
}


@dataclass(frozen=True, slots=True)
class Fact:
    """A value code computed and formatted, with where it came from (``id`` like ``F3``)."""

    id: str
    text: str
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class Comparison:
    """A comparative statement whose direction code decided (``id`` like ``C1``)."""

    id: str
    relation: Relation
    provenance: Provenance

    @property
    def text(self) -> str:
        return RELATION_WORD[self.relation]


class ViolationCode(StrEnum):
    DIGIT_OUTSIDE_SLOT = "digit_outside_slot"
    MONEY_WORD_OUTSIDE_SLOT = "money_word_outside_slot"
    COMPARATIVE_OUTSIDE_SLOT = "comparative_outside_slot"
    UNKNOWN_SLOT = "unknown_slot"
    NO_CITATION = "no_citation"
    UNKNOWN_REVIEW = "unknown_review"
    SINGLE_OPINION_NOT_LABELLED = "single_opinion_not_labelled"
    SPAN_NOT_IN_SOURCE = "span_not_in_source"


@dataclass(frozen=True, slots=True)
class Violation:
    code: ViolationCode
    detail: str


class SlotError(ValueError):
    """Rendering was asked for a text the verifier rejects."""

    def __init__(self, violations: Sequence[Violation]) -> None:
        super().__init__("; ".join(f"{v.code}: {v.detail}" for v in violations))
        self.violations = tuple(violations)


def verify_text(
    text: str, facts: Mapping[str, Fact], comparisons: Mapping[str, Comparison]
) -> list[Violation]:
    """Every violation of the slot rules in an LLM-written text (empty list: the text is fine)."""
    violations = [
        Violation(ViolationCode.UNKNOWN_SLOT, slot)
        for slot in SLOT.findall(text)
        if slot not in facts and slot not in comparisons
    ]
    prose = normalize_persian(SLOT.sub(" ", text))
    for pattern, code in (
        (_DIGITS, ViolationCode.DIGIT_OUTSIDE_SLOT),
        (_MONEY_AND_MAGNITUDE, ViolationCode.MONEY_WORD_OUTSIDE_SLOT),
        (_COMPARATIVE, ViolationCode.COMPARATIVE_OUTSIDE_SLOT),
    ):
        violations.extend(Violation(code, m.group(0)) for m in pattern.finditer(prose))
    return violations


@dataclass(frozen=True, slots=True)
class RenderedText:
    text: str
    used: tuple[str, ...]  # slot ids in order of appearance (the UI links each to provenance)


def render(
    text: str, facts: Mapping[str, Fact], comparisons: Mapping[str, Comparison]
) -> RenderedText:
    """Fill the slots of a verified text; refuses texts with violations."""
    violations = verify_text(text, facts, comparisons)
    if violations:
        raise SlotError(violations)
    used: list[str] = []

    def fill(match: re.Match[str]) -> str:
        slot = match.group(1)
        used.append(slot)
        value = facts.get(slot) or comparisons[slot]
        return value.text

    return RenderedText(SLOT.sub(fill, text), tuple(used))


@dataclass(frozen=True, slots=True)
class SummaryPoint:
    """One pro or con of a review summary, with the reviews that support it."""

    text: str
    review_ids: tuple[str, ...]
    single_opinion: bool = False


def verify_points(
    points: Sequence[SummaryPoint], known_reviews: Collection[str]
) -> list[Violation]:
    """Each point cites existing reviews; a point backed by one review says it is one opinion."""
    violations: list[Violation] = []
    for index, point in enumerate(points):
        where = f"point {index + 1}"
        if not point.review_ids:
            violations.append(Violation(ViolationCode.NO_CITATION, where))
        unknown = [r for r in point.review_ids if r not in known_reviews]
        violations.extend(Violation(ViolationCode.UNKNOWN_REVIEW, f"{where}: {r}") for r in unknown)
        if len(set(point.review_ids)) == 1 and not point.single_opinion:
            violations.append(Violation(ViolationCode.SINGLE_OPINION_NOT_LABELLED, where))
    return violations


def verify_span(span: str, source: str) -> list[Violation]:
    """An extracted claim must be a verbatim part of its source (after normalization)."""
    if span and normalize_persian(span) in normalize_persian(source):
        return []
    return [Violation(ViolationCode.SPAN_NOT_IN_SOURCE, span[:80])]
