"""The structured search intent and its deterministic checks (ROADMAP M8; provisional schema).

The query-understanding LLM fills ``SearchIntent``. Two rules keep it honest (ADR-0007):
- every number it writes must be a number the query says («۴ نفر», «زیر ۵ میلیون», «دو شب»);
  anything derived from words is a code instead («زوج» is ``party="couple"``, «هفته بعد» is
  ``which="next"``) and code turns codes into numbers;
- dates are never computed by the LLM: it names a ``DateSpec`` and the resolver
  (``discovery.domain.dates``) produces the stay.

A violation means the intent is retried once with the violations, then the offending field is
dropped and the user asked (M8 ambiguity flow). The field set is provisional until the M8 eval.
"""

from __future__ import annotations

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
from villasanj.shared.domain.persian_numbers import unmentioned
from villasanj.shared.domain.slots import Violation, ViolationCode, verify_span

WeekdayName = Literal["saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]
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
    places: list[str] = Field(default_factory=list, max_length=5)  # verbatim names

    @property
    def guests(self) -> int | None:
        """The group size: the stated parts summed by code, or the size a party word implies."""
        if self.guest_parts:
            return sum(self.guest_parts)
        return _PARTY[self.party] if self.party else None

    def stated_numbers(self) -> list[Decimal]:
        """Every number the intent claims the query said."""
        values: list[float | int | None] = [
            self.nights,
            *self.guest_parts,
            self.bedrooms_min,
            self.budget.max_toman if self.budget else None,
            self.max_drive.value if self.max_drive else None,
        ]
        if self.dates is not None:
            values.extend([self.dates.day, self.dates.year])
        return [Decimal(str(v)) for v in values if v is not None]


def verify_intent(intent: SearchIntent, query: str) -> list[Violation]:
    """Numbers the query does not say, and places that are not verbatim in it."""
    violations = [
        Violation(ViolationCode.NUMBER_NOT_IN_SOURCE, f"{value.normalize():f}")
        for value in unmentioned(intent.stated_numbers(), query)
    ]
    for place in intent.places:
        violations.extend(verify_span(place, query))
    if intent.dates is not None and intent.dates.expression() is None:
        violations.append(Violation(ViolationCode.INCOMPLETE_DATE, intent.dates.kind))
    return violations
