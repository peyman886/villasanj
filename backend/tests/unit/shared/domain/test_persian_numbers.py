"""Numbers mentioned in Persian text (the M8 intent verifier and M9 claim extraction use them)."""

from decimal import Decimal

import pytest

from villasanj.shared.domain.persian_numbers import number_mentions, unmentioned

ZWNJ = "\N{ZERO WIDTH NON-JOINER}"


def d(*values: str | int) -> list[Decimal]:
    return [Decimal(str(v)) for v in values]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ویلا برای ۴ نفر", d(4)),
        ("ویلا برای 4 نفر", d(4)),
        ("ویلای چهار نفره", d(4)),
        ("ویلای چهارنفره دوخوابه", d(4, 2)),
        ("بیست و پنج نفر", d(25)),
        ("صد و بیست متر", d(120)),
        ("سیصد و پنجاه و پنج", d(355)),
        ("زیر ۵ میلیون", d(5_000_000)),
        ("زیر پنج میلیون تومن", d(5_000_000)),
        ("دو میلیون و پانصد هزار", d(2_500_000)),
        ("یک میلیون و دویست و پنجاه هزار", d(1_250_000)),
        ("۲.۵ میلیون", d(2_500_000)),
        ("۱۲٫۵ میلیون", d(12_500_000)),
        ("2,500,000 تومان", d(2_500_000)),
        ("دو و نیم میلیون", d(2_500_000)),
        ("دو و نیم ساعت", d("2.5")),
        ("نیم ساعت", d("0.5")),
        ("یه ویلا", d(1)),
    ],
)
def test_mentions(text: str, expected: list[Decimal]) -> None:
    assert number_mentions(text) == expected


def test_a_half_after_the_unit_belongs_to_the_number() -> None:
    assert Decimal("2.5") in number_mentions("حداکثر دو ساعت و نیم از تهران")


def test_a_range_shares_its_scale() -> None:
    assert number_mentions("۲ تا ۳ میلیون") == d(2, 3_000_000, 2_000_000)
    assert number_mentions("۲ میلیون تا ۳ میلیون") == d(2_000_000, 3_000_000)


@pytest.mark.parametrize(
    "text",
    [
        "پنج شنبه",
        f"سه{ZWNJ}شنبه",
        "پنجشنبه",
        "یکشنبه تا دوشنبه",
        "دور از شلوغی",  # «دو» + «ر» is not a number
        "سیب",
        "کد 12,34",  # not a grouped or decimal number
    ],
)
def test_weekdays_and_lookalike_words_are_not_numbers(text: str) -> None:
    assert number_mentions(text) == []


def test_side_by_side_numbers_stay_apart() -> None:
    assert number_mentions("دو سه نفر") == d(2, 3)  # two or three people, never five
    assert number_mentions("۴ و ۵ نفر") == d(4, 5)  # «و» only joins a smaller part


def test_numbers_nobody_said_are_reported() -> None:
    query = "ویلا برای ۶ نفر آخر هفته زیر ۸ میلیون"
    assert unmentioned(d(6, 8_000_000), query) == []
    assert unmentioned(d(6, 3, 8_000_000, 8_000), query) == d(3, 8_000)
