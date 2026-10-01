"""The search intent: numbers must be said, dates are named and resolved by code."""

import pytest

from villasanj.discovery.application.intent import (
    Budget,
    DateSpec,
    DriveLimit,
    SearchIntent,
    drop_violations,
    verify_intent,
    without,
)
from villasanj.discovery.domain.dates import (
    FRIDAY,
    InJalaliMonth,
    NextHoliday,
    Nowruz,
    OnJalaliDay,
    RelativeDay,
    Weekday,
    Weekend,
)
from villasanj.shared.domain.slots import ViolationCode

ZWNJ = "\N{ZERO WIDTH NON-JOINER}"


@pytest.mark.parametrize(
    ("spec", "expression"),
    [
        (DateSpec(kind="tonight"), RelativeDay(0)),
        (DateSpec(kind="day_after_tomorrow"), RelativeDay(2)),
        (DateSpec(kind="weekday", weekday="friday", which="next"), Weekday(FRIDAY, 1)),
        (DateSpec(kind="weekend", which="after_next"), Weekend(2)),
        (DateSpec(kind="jalali_day", month=7, day=15), OnJalaliDay(7, 15)),
        (DateSpec(kind="jalali_month", month=8, year=1405), InJalaliMonth(8, 1405)),
        (DateSpec(kind="nowruz"), Nowruz()),
        (DateSpec(kind="next_holiday"), NextHoliday()),
        (DateSpec(kind="weekday"), None),
        (DateSpec(kind="jalali_day", month=7), None),
        (DateSpec(kind="jalali_month"), None),
    ],
)
def test_date_specs_name_resolver_expressions(spec: DateSpec, expression: object) -> None:
    assert spec.expression() == expression


def test_an_honest_intent_passes() -> None:
    query = (
        f"ویلای استخردار دو خوابه برای ۴ بزرگسال و ۲ بچه، آخر هفته{ZWNJ}ی بعد، زیر ۵ میلیون، رامسر"
    )
    intent = SearchIntent(
        dates=DateSpec(kind="weekend", which="next"),
        guest_parts=[4, 2],
        bedrooms_min=2,
        budget=Budget(max_toman=5_000_000, basis="unknown"),
        places=["رامسر"],
    )
    assert verify_intent(intent, query) == []
    assert intent.guests == 6


def test_invented_numbers_and_places_are_caught() -> None:
    query = "یه ویلای دنج نزدیک دریا برای من و همسرم"
    intent = SearchIntent(
        guest_parts=[2],  # derived from words: must be party="couple"
        nights=2,
        budget=Budget(max_toman=3_000_000),
        places=["کلارآباد"],
    )
    codes = [(v.code, v.detail) for v in verify_intent(intent, query)]
    assert codes == [
        (ViolationCode.NUMBER_NOT_IN_SOURCE, "2"),
        (ViolationCode.NUMBER_NOT_IN_SOURCE, "2"),
        (ViolationCode.NUMBER_NOT_IN_SOURCE, "3000000"),
        (ViolationCode.SPAN_NOT_IN_SOURCE, "کلارآباد"),
    ]
    kept, dropped = drop_violations(
        intent.model_copy(update={"places": ["کلارآباد", "دریا"]}), query
    )
    assert dropped == ("nights", "guest_parts", "budget", "places")
    assert kept == SearchIntent(places=["دریا"])
    honest = SearchIntent(party="couple")
    assert verify_intent(honest, query) == []
    assert honest.guests == 2


def test_drive_limits_and_explicit_dates_are_checked_as_said() -> None:
    query = "حداکثر دو ساعت و نیم از تهران، ۱۵ مهر ۱۴۰۵ برای سه شب"
    intent = SearchIntent(
        dates=DateSpec(kind="jalali_day", month=7, day=15, year=1405),
        nights=3,
        max_drive=DriveLimit(value=2.5, unit="hours"),
    )
    assert verify_intent(intent, query) == []
    assert intent.max_drive is not None
    assert intent.max_drive.minutes == 150
    assert DriveLimit(value=90, unit="minutes").minutes == 90
    wrong = intent.model_copy(update={"max_drive": DriveLimit(value=150, unit="minutes")})
    assert [v.detail for v in verify_intent(wrong, query)] == ["150"]


def test_an_incomplete_date_is_a_violation() -> None:
    intent = SearchIntent(dates=DateSpec(kind="weekday"))
    assert [v.code for v in verify_intent(intent, "یه روز")] == [ViolationCode.INCOMPLETE_DATE]
    assert SearchIntent().guests is None


def test_the_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="extra"):
        SearchIntent.model_validate({"guests": 4})


def test_dropping_constraints_never_adds_a_number() -> None:
    intent = SearchIntent(
        dates=DateSpec(kind="weekend"),
        guest_parts=[4, 2],
        budget=Budget(max_toman=5_000_000),
        places=["رامسر", "تنکابن"],
        features=["pool", "jacuzzi"],
    )
    edited = without(intent, ["budget", "guests", "place:رامسر", "feature:pool", "unknown"])
    assert edited == SearchIntent(
        dates=DateSpec(kind="weekend"), places=["تنکابن"], features=["jacuzzi"]
    )
    query = "آخر هفته برای ۴ بزرگسال و ۲ بچه زیر ۵ میلیون، رامسر یا تنکابن، استخر و جکوزی"
    assert verify_intent(edited, query) == []
    assert without(intent, []) == intent
