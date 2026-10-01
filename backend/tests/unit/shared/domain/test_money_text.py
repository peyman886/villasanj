"""Table-driven messy-money cases (ROADMAP M2 criterion 4, together with test_persian_text)."""

import pytest

from villasanj.shared.domain.money import Money
from villasanj.shared.domain.money_text import parse_money_text

ARABIC_THOUSANDS = "\N{ARABIC THOUSANDS SEPARATOR}"
ARABIC_COMMA = "\N{ARABIC COMMA}"
ARABIC_DECIMAL = "\N{ARABIC DECIMAL SEPARATOR}"
ZWNJ = "\N{ZERO WIDTH NON-JOINER}"
T = Money.from_toman
R = Money.from_rial


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # plain numbers, toman by default
        ("1500000", T(1_500_000)),
        ("1500000 تومان", T(1_500_000)),
        ("۱۵۰۰۰۰۰ تومان", T(1_500_000)),
        ("١٥٠٠٠٠٠ تومان", T(1_500_000)),
        ("1500000 ریال", R(1_500_000)),
        ("۱۵۰۰۰۰۰ ريال", R(1_500_000)),  # Arabic yeh in «ريال»
        # thousands separators
        ("1,500,000 تومان", T(1_500_000)),
        (f"۱{ARABIC_COMMA}۵۰۰{ARABIC_COMMA}۰۰۰ تومان", T(1_500_000)),
        (f"۱{ARABIC_THOUSANDS}۵۰۰{ARABIC_THOUSANDS}۰۰۰ تومان", T(1_500_000)),
        ("1.500.000 تومان", T(1_500_000)),
        ("1 500 000 تومان", T(1_500_000)),
        ("2,850,000ریال", R(2_850_000)),
        ("شروع از: 1٬020٬000 تومان / هرشب", T(1_020_000)),
        # scale words
        ("۲۸۵ هزار تومان", T(285_000)),
        ("285هزار تومان", T(285_000)),
        ("۱۲ میلیون تومان", T(12_000_000)),
        (f"۱۲{ARABIC_DECIMAL}۵ میلیون تومان", T(12_500_000)),
        ("12.5 میلیون تومان", T(12_500_000)),
        ("۱٫۲۵ میلیون", T(1_250_000)),
        ("۳ میلیارد ریال", R(3_000_000_000)),
        ("۸۰۰ هزار ریال", R(800_000)),
        ("۱۰ تومن", T(10)),
        # compounds
        ("۵ میلیون و ۵۰۰ هزار تومان", T(5_500_000)),
        ("۲ میلیون و ۳۰۰ هزار و ۵۰۰ تومان", T(2_300_500)),
        (f"۵ میلیون و{ZWNJ} ۲۰۰ هزار", T(5_200_000)),
        # surrounding text and messy characters
        ("قیمت: ۳٬۴۰۰٬۰۰۰ تومان برای هر نفر اضافه", T(3_400_000)),
        ("هزینه گرمایش جداگانه شبی ۱،۵۰۰،۰۰۰ تومان", T(1_500_000)),
        ("  ۹۰۰ هزار  تومان  ", T(900_000)),
        ("0 تومان", T(0)),
        ("۱۲٫۵ تومان", R(125)),  # half a toman is a whole number of rial
        # Rejected inputs are ambiguous or invalid.
        ("", None),
        ("رایگان", None),
        ("تماس بگیرید", None),
        ("۱۲ تا ۱۵ میلیون تومان", None),  # a range is not one amount
        ("۵۰۰ هزار و ۲ میلیون", None),  # scales must decrease
        ("1.2345 میلیون", None),  # too many decimals to be a decimal, too few to be groups
        ("1,50,000 تومان", None),  # malformed grouping
        ("۱۰۰ تومان ۲۰۰ ریال", None),
        ("۱۰۰۰ ریال یا تومان", None),
    ],
)
def test_parse_money_text(text: str, expected: Money | None) -> None:
    assert parse_money_text(text) == expected


def test_fractional_toman_that_is_whole_rial_is_kept() -> None:
    assert parse_money_text("۱۲٫۵ هزار ریال") == R(12_500)
