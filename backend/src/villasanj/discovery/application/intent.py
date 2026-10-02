"""The structured search intent and its deterministic checks (ROADMAP M8; provisional schema).

The query-understanding LLM fills ``SearchIntent``. Two rules keep it honest (ADR-0007):
- every number it writes must be a number the query says («۴ نفر», «زیر ۵ میلیون», «دو شب»);
  anything derived from words is a code instead («زوج» is ``party="couple"``, «هفته بعد» is
  ``which="next"``) and code turns codes into numbers;
- dates are never computed by the LLM: it names a ``DateSpec`` and the resolver
  (``discovery.domain.dates``) produces the stay.

A violation means the intent is retried once with the violations, then the offending field is
dropped and the user asked (M8 ambiguity flow). The field set is provisional until the M8 eval.

A budget's basis (per night or the whole stay) is kept only when the query says it in words;
otherwise it becomes ``unknown`` and the search shows the counts under both readings, because a
guessed basis silently changes the results.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal
from typing import Literal, assert_never

from pydantic import BaseModel, ConfigDict, Field

from villasanj.discovery.domain.dates import (
    DateExpression,
    InJalaliMonth,
    NextHoliday,
    Nowruz,
    OnJalaliDay,
    RelativeDay,
    Weekday,
    Weekend,
)
from villasanj.shared.domain.persian_numbers import number_mentions
from villasanj.shared.domain.persian_text import normalize_persian
from villasanj.shared.domain.slots import Violation, ViolationCode, verify_span

WeekdayName = Literal["saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
# What a query can ask the villa to have (provisional: M9's evidence decides what can be checked).
Feature = Literal[
    "pool", "jacuzzi", "near_sea", "sea_view", "forest", "fireplace", "parking", "barbecue"
]
_WEEKDAYS: dict[str, int] = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
_WHICH: dict[str, int] = {"this": 0, "next": 1, "after_next": 2}
_RELATIVE: dict[str, int] = {"tonight": 0, "tomorrow": 1, "day_after_tomorrow": 2}
_PARTY: dict[str, int] = {"solo": 1, "couple": 2}
MINUTES_PER_HOUR = 60


class DateSpec(BaseModel):
    """The date expression the query uses, named, not computed."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "tonight",
        "tomorrow",
        "day_after_tomorrow",
        "weekday",
        "weekend",
        "jalali_day",
        "jalali_month",
        "nowruz",
        "next_holiday",
    ]
    which: Literal["this", "next", "after_next"] = "this"  # for weekday and weekend
    weekday: WeekdayName | None = None
    month: int | None = Field(default=None, ge=1, le=12)  # Jalali, «مهر» is 7
    day: int | None = Field(default=None, ge=1, le=31)
    year: int | None = Field(default=None, ge=1400, le=1500)  # Jalali, only when said

    def expression(self) -> DateExpression | None:
        """The resolver's expression, or ``None`` when a required part is missing."""
        match self.kind:
            case "tonight" | "tomorrow" | "day_after_tomorrow":
                return RelativeDay(_RELATIVE[self.kind])
            case "weekday":
                if self.weekday is None:
                    return None
                return Weekday(_WEEKDAYS[self.weekday], _WHICH[self.which])
            case "weekend":
                return Weekend(_WHICH[self.which])
            case "jalali_day":
                if self.month is None or self.day is None:
                    return None
                return OnJalaliDay(self.month, self.day, self.year)
            case "jalali_month":
                return None if self.month is None else InJalaliMonth(self.month, self.year)
            case "nowruz":
                return Nowruz(self.year)
            case "next_holiday":
                return NextHoliday()
            case _:  # pragma: no cover - exhaustive
                assert_never(self.kind)


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_toman: int = Field(gt=0)  # as said: «زیر ۵ میلیون» is 5000000
    basis: Literal["per_night", "whole_stay", "unknown"] = "unknown"


class DriveLimit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float = Field(gt=0)  # as said: «دو ساعت و نیم» is 2.5 hours
    unit: Literal["hours", "minutes"]

    @property
    def minutes(self) -> float:
        return self.value * MINUTES_PER_HOUR if self.unit == "hours" else self.value


class SearchIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dates: DateSpec | None = None
    nights: int | None = Field(default=None, ge=1, le=30)
    guest_parts: list[int] = Field(default_factory=list, max_length=6)  # «۴ بزرگسال و ۲ بچه»
    party: Literal["solo", "couple"] | None = None  # a group size said in words only
    bedrooms_min: int | None = Field(default=None, ge=1, le=20)
    budget: Budget | None = None
    max_drive: DriveLimit | None = None  # from Tehran
    places: list[str] = Field(default_factory=list, max_length=5)  # destinations, verbatim
    features: list[Feature] = Field(default_factory=list, max_length=8)
    # Wishes no field can hold («دوبلکس», «حیاط بزرگ»), verbatim: said back to the user, never
    # used to filter or rank (nothing measures them).
    unhandled: list[str] = Field(default_factory=list, max_length=5)

    @property
    def guests(self) -> int | None:
        """The group size: the stated parts summed by code, or the size a party word implies."""
        if self.guest_parts:
            return sum(self.guest_parts)
        return _PARTY[self.party] if self.party else None


def field_violations(intent: SearchIntent, query: str) -> dict[str, list[Violation]]:
    """Each field's broken rules: numbers the query does not say, places not verbatim in it."""
    said = set(number_mentions(query))
    problems: dict[str, list[Violation]] = {}

    def check(field: str, *values: float | None) -> None:
        for value in values:
            if value is not None and Decimal(str(value)) not in said:
                detail = f"{Decimal(str(value)).normalize():f}"
                problems.setdefault(field, []).append(
                    Violation(ViolationCode.NUMBER_NOT_IN_SOURCE, detail)
                )

    check("nights", intent.nights)
    check("guest_parts", *intent.guest_parts)
    check("bedrooms_min", intent.bedrooms_min)
    if intent.budget is not None:
        check("budget", intent.budget.max_toman)
    if intent.max_drive is not None:
        check("max_drive", intent.max_drive.value)
    if intent.dates is not None:
        check("dates", intent.dates.day, intent.dates.year)
        if intent.dates.expression() is None:
            problems.setdefault("dates", []).append(
                Violation(ViolationCode.INCOMPLETE_DATE, intent.dates.kind)
            )
    for place in intent.places:
        if spans := verify_span(place, query):
            problems.setdefault("places", []).extend(spans)
    for wish in intent.unhandled:
        if spans := verify_span(wish, query):
            problems.setdefault("unhandled", []).extend(spans)
    return problems


_BASIS_WORDS = {  # matched on the normalized query (no diacritics: «کلاً» is «کلا»)
    "per_night": re.compile(r"\bشبی\b|هر ?شب|\bشبانه\b"),
    "whole_stay": re.compile(r"\bکل(?:ا|ش)?\b|\bمجموع|\bجمعا\b|\bروی ?هم\b"),
}


def with_stated_basis(intent: SearchIntent, query: str) -> SearchIntent:
    """The intent whose budget basis is ``unknown`` unless the query names that basis."""
    budget = intent.budget
    if budget is None or budget.basis == "unknown":
        return intent
    if _BASIS_WORDS[budget.basis].search(normalize_persian(query)):
        return intent
    unstated = budget.model_copy(update={"basis": "unknown"})
    return intent.model_copy(update={"budget": unstated})


def verify_intent(intent: SearchIntent, query: str) -> list[Violation]:
    """Every broken rule (empty: every number was said and every place is verbatim)."""
    return [v for violations in field_violations(intent, query).values() for v in violations]


def drop_violations(intent: SearchIntent, query: str) -> tuple[SearchIntent, tuple[str, ...]]:
    """The intent without the fields that break a rule (places: only the non-verbatim ones)."""
    problems = field_violations(intent, query)
    update: dict[str, object] = {}
    for field in problems:
        if field == "places":
            update[field] = [p for p in intent.places if not verify_span(p, query)]
        elif field == "unhandled":
            update[field] = [w for w in intent.unhandled if not verify_span(w, query)]
        elif field == "guest_parts":
            update[field] = []
        else:
            update[field] = None
    return intent.model_copy(update=update), tuple(problems)


# What a user can remove from an understood query (editable chips, M8). Removing never adds a
# number, so an edited intent is still one whose every number the query said.
DROP_FIELDS: dict[str, dict[str, object]] = {
    "dates": {"dates": None},
    "nights": {"nights": None},
    "guests": {"guest_parts": [], "party": None},
    "bedrooms": {"bedrooms_min": None},
    "budget": {"budget": None},
    "drive": {"max_drive": None},
}


def without(intent: SearchIntent, drops: Sequence[str]) -> SearchIntent:
    """The intent without the dropped constraints: "budget", "place:<name>", "feature:<code>"."""
    update: dict[str, object] = {}
    places, features = list(intent.places), list(intent.features)
    for drop in drops:
        kind, _, value = drop.partition(":")
        if drop in DROP_FIELDS:
            update.update(DROP_FIELDS[drop])
        elif kind == "place":
            places = [p for p in places if p != value]
        elif kind == "feature":
            features = [f for f in features if f != value]
    update["places"], update["features"] = places, features
    return intent.model_copy(update=update)
