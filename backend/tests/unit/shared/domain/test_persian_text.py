import pytest
from hypothesis import given
from hypothesis import strategies as st

from villasanj.shared.domain.persian_text import (
    ZWNJ,
    normalize_persian,
    to_latin_digits,
    to_persian_digits,
)

ARABIC_YEH = "\N{ARABIC LETTER YEH}"
ARABIC_KAF = "\N{ARABIC LETTER KAF}"
FARSI_YEH = "\N{ARABIC LETTER FARSI YEH}"
KEHEH = "\N{ARABIC LETTER KEHEH}"
TATWEEL = "\N{ARABIC TATWEEL}"
FATHA = "\N{ARABIC FATHA}"
ZWJ = "\N{ZERO WIDTH JOINER}"
NBSP = "\N{NO-BREAK SPACE}"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (f"{ARABIC_KAF}{ARABIC_YEH}", f"{KEHEH}{FARSI_YEH}"),
        ("۱۲۳٤٥", "12345"),  # Persian and Arabic-Indic digits
        (f"م{TATWEEL}{TATWEEL}ن", "من"),
        (f"م{FATHA}ن", "من"),
        (f"می{ZWNJ}{ZWNJ}خواهم", f"می{ZWNJ}خواهم"),
        (f"ویلا {ZWNJ} استخر", "ویلا استخر"),
        (f"{ZWNJ}ویلا{ZWNJ}", "ویلا"),
        (f"ویلا{ZWJ}ی", "ویلای"),
        (f"  ویلا{NBSP}{NBSP}  دریا  ", "ویلا دریا"),
        ("خط اول\n\n\n  خط دوم  ", "خط اول\nخط دوم"),
        ("", ""),
    ],
)
def test_normalize_cases(raw: str, expected: str) -> None:
    assert normalize_persian(raw) == expected


persian_like = st.text(
    alphabet=st.sampled_from(
        [*"ابپتکگیيكهۀـ۰۱۲٣٤0123456789 \n\t", ZWNJ, ZWJ, NBSP, FATHA, "\N{ZERO WIDTH SPACE}"]
    ),
    max_size=60,
)


@pytest.mark.parametrize("text", [f"0 {ZWNJ} {ZWNJ}0", f"a{ZWNJ} {ZWNJ} b"])
def test_idempotent_on_overlapping_joiners_and_spaces(text: str) -> None:
    once = normalize_persian(text)  # found by hypothesis on 2026-10-02
    assert normalize_persian(once) == once
    assert ZWNJ not in once


@given(persian_like)
def test_idempotent(text: str) -> None:
    once = normalize_persian(text)
    assert normalize_persian(once) == once


@given(persian_like)
def test_no_arabic_letters_or_digits_survive(text: str) -> None:
    result = normalize_persian(text)
    assert not set(result) & {ARABIC_YEH, ARABIC_KAF, TATWEEL, *"۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩"}


def test_digit_round_trip() -> None:
    assert to_latin_digits(to_persian_digits("1405/07/09")) == "1405/07/09"
    assert to_persian_digits("8") == "۸"
