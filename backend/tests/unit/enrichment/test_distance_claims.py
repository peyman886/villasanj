"""Distance claims as ranges, and the truth-check verdicts (ROADMAP M9 criterion 3)."""

import pytest

from villasanj.enrichment.domain.distance_claims import (
    DRIVE_M_PER_MIN,
    WALK_M_PER_MIN,
    ClaimTarget,
    DistanceClaim,
    Unit,
    Verdict,
    assess,
    parse_claim,
    target_of,
)
from villasanj.ingestion.domain.parsed import ParsedDistanceClaim, TravelMode

ZWJ = "\N{ZERO WIDTH JOINER}"


def claim(target: str, value: str, mode: TravelMode = TravelMode.WALK) -> DistanceClaim:
    parsed = parse_claim(ParsedDistanceClaim(target, value, mode))
    assert parsed is not None
    return parsed


@pytest.mark.parametrize(
    ("text", "target"),
    [
        ("فاصله از دریا", ClaimTarget.SEA),
        ("ساحل", ClaimTarget.SEA),
        ("جنگل دالخانی", ClaimTarget.FOREST),
        ("فاصله از مرکزشهر", ClaimTarget.CITY_CENTER),
        ("فاصله تا سوپر مارکت", ClaimTarget.SUPERMARKET),
        ("سوپرمارکت و نانوایی", ClaimTarget.SUPERMARKET),
        ("نانوایی", ClaimTarget.BAKERY),
        ("فاصله تا بیمارستان (درمانگاه)", ClaimTarget.MEDICAL),
        ("فاصله از مراکز تفریحی", ClaimTarget.RECREATION),
        ("فاصله از مراکز خرید", ClaimTarget.SHOPPING),
        ("فاصله از حرم", ClaimTarget.SHRINE),
        ("تله کابین", ClaimTarget.OTHER),
        # Found on real claims: the sea is a whole word.
        ("دشت دریاسر", ClaimTarget.OTHER),
        ("پیاده راه ساحلی", ClaimTarget.OTHER),
        ("فاصله با دریا 4 دقیقه", ClaimTarget.SEA),
        ("لب ساحل", ClaimTarget.SEA),
        ("فاصله تا جنگل و دریا", ClaimTarget.OTHER),  # one value for two places
    ],
)
def test_targets(text: str, target: ClaimTarget) -> None:
    assert target_of(text) is target


@pytest.mark.parametrize(
    ("value", "unit", "low", "high"),
    [
        ("5 دقیقه", Unit.MINUTES, 0, 10),  # a rounded choice: "about five or less"
        ("۱۰ دقیقه", Unit.MINUTES, 0, 15),
        (f"زیر {ZWJ}۵ دقیقه", Unit.MINUTES, 0, 5),  # as published, with a stray joiner
        ("بیشتر از 30 دقیقه", Unit.MINUTES, 30, None),
        ("10 تا 15 دقیقه", Unit.MINUTES, 10, 15),
        ("200 متر", Unit.METRES, 0, 300),
        ("۲ کیلومتر", Unit.METRES, 0, 3000),
    ],
)
def test_published_wordings_become_ranges(
    value: str, unit: Unit, low: float, high: float | None
) -> None:
    parsed = claim("دریا", value)
    assert (parsed.unit, parsed.low, parsed.high) == (unit, low, high)


@pytest.mark.parametrize("value", ["نزدیک", "چند قدمی", "", "5"])
def test_unknown_wording_is_not_guessed(value: str) -> None:
    assert parse_claim(ParsedDistanceClaim("دریا", value, TravelMode.WALK)) is None


def test_minutes_become_generous_straight_line_ranges() -> None:
    walk = claim("دریا", "زیر 10 دقیقه", TravelMode.WALK)
    assert walk.metres() == (0.0, 10 * WALK_M_PER_MIN[1])
    drive = claim("دریا", "10 دقیقه", TravelMode.CAR)  # up to 15 minutes after rounding
    assert drive.metres() == (0.0, 15 * DRIVE_M_PER_MIN[1])
    unknown = claim(
        "دریا", "10 تا 20 دقیقه", TravelMode.UNKNOWN
    )  # an explicit range keeps its floor
    assert unknown.metres() == (10 * WALK_M_PER_MIN[0], 20 * DRIVE_M_PER_MIN[1])
    assert claim("دریا", "200 متر").metres() == (0, 300)


@pytest.mark.parametrize(
    ("value", "mode", "measured", "verdict"),
    [
        ("زیر 5 دقیقه", TravelMode.WALK, (100.0, 400.0), Verdict.SUPPORTED),
        ("زیر 5 دقیقه", TravelMode.WALK, (300.0, 1100.0), Verdict.NOT_CONFIRMED),  # obfuscated
        ("زیر 5 دقیقه", TravelMode.WALK, (2000.0, 2800.0), Verdict.CONTRADICTED),
        (
            "زیر 5 دقیقه",
            TravelMode.UNKNOWN,
            (2000.0, 2800.0),
            Verdict.NOT_CONFIRMED,
        ),  # maybe by car
        ("زیر 5 دقیقه", TravelMode.CAR, (6000.0, 6800.0), Verdict.CONTRADICTED),
        ("زیر 5 دقیقه", TravelMode.WALK, (100.0, None), Verdict.NOT_CONFIRMED),  # radius unknown
        (
            "بیشتر از 30 دقیقه",
            TravelMode.WALK,
            (100.0, 500.0),
            Verdict.NOT_CONFIRMED,
        ),  # understates
        ("بیشتر از 30 دقیقه", TravelMode.WALK, (5000.0, 6000.0), Verdict.SUPPORTED),
        ("200 متر", TravelMode.WALK, (150.0, 250.0), Verdict.SUPPORTED),
        # Found on real claims: a villa 0..638 m from the sea claiming five minutes by car.
        ("5 دقیقه", TravelMode.CAR, (0.0, 638.0), Verdict.SUPPORTED),
        ("5 دقیقه", TravelMode.WALK, (1808.0, 2808.0), Verdict.CONTRADICTED),
    ],
)
def test_contradicted_only_when_the_best_case_fails(
    value: str, mode: TravelMode, measured: tuple[float, float | None], verdict: Verdict
) -> None:
    result = assess(claim("دریا", value, mode), measured)
    assert result.verdict is verdict
    assert result.measured_m == measured


def test_an_unknown_mode_is_judged_under_both_readings() -> None:
    walk_or_drive = claim("دریا", "زیر 5 دقیقه", TravelMode.UNKNOWN)
    assert walk_or_drive.readings() == (
        (0.0, 5 * WALK_M_PER_MIN[1]),
        (0.0, 5 * DRIVE_M_PER_MIN[1]),
    )
    assert assess(walk_or_drive, (100.0, 300.0)).verdict is Verdict.SUPPORTED  # both hold
    assert assess(walk_or_drive, (9000.0, 9500.0)).verdict is Verdict.CONTRADICTED  # both fail
    more_than = claim("دریا", "بیشتر از 10 دقیقه", TravelMode.UNKNOWN)
    assert more_than.metres() == (10 * WALK_M_PER_MIN[0], None)
