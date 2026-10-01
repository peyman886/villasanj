"""Source-agnostic Persian text normalization (pure functions, idempotent).

Covers the messy-data basics seen on Iranian platforms: Arabic yeh/kaf, mixed digit scripts,
zero-width characters, tatweel, diacritics and irregular whitespace. Parsing money and dates is
done elsewhere on top of this.
"""

from __future__ import annotations

import re

ZWNJ = "\N{ZERO WIDTH NON-JOINER}"

_CHAR_MAP = str.maketrans(
    {
        "\N{ARABIC LETTER YEH}": "\N{ARABIC LETTER FARSI YEH}",
        "\N{ARABIC LETTER ALEF MAKSURA}": "\N{ARABIC LETTER FARSI YEH}",
        "\N{ARABIC LETTER KAF}": "\N{ARABIC LETTER KEHEH}",
        # The ezafe marker on HEH is dropped for matching purposes.
        "\N{ARABIC LETTER HEH WITH YEH ABOVE}": "\N{ARABIC LETTER HEH}",
        "\N{ARABIC TATWEEL}": None,
        "\N{ZERO WIDTH SPACE}": None,
        "\N{ZERO WIDTH JOINER}": None,
        "\N{ZERO WIDTH NO-BREAK SPACE}": None,
        "\N{SOFT HYPHEN}": None,
        "\N{LEFT-TO-RIGHT MARK}": None,
        "\N{RIGHT-TO-LEFT MARK}": None,
        "\N{NO-BREAK SPACE}": " ",
        "\N{NARROW NO-BREAK SPACE}": " ",
    }
)
_DIACRITICS = re.compile(
    "[\N{ARABIC FATHATAN}-\N{ARABIC WAVY HAMZA BELOW}\N{ARABIC LETTER SUPERSCRIPT ALEF}]"
)
_PERSIAN_DIGITS = "".join(chr(code) for code in range(0x06F0, 0x06FA))  # EXTENDED ARABIC-INDIC
_ARABIC_DIGITS = "".join(chr(code) for code in range(0x0660, 0x066A))  # ARABIC-INDIC
_LATIN_DIGITS = "0123456789"
_DIGITS_TO_LATIN = str.maketrans(_PERSIAN_DIGITS + _ARABIC_DIGITS, _LATIN_DIGITS * 2)
_LATIN_TO_PERSIAN = str.maketrans(_LATIN_DIGITS, _PERSIAN_DIGITS)
_SPACES = re.compile(r"[ \t\r\f\v]+")
_ZWNJ_RUNS = re.compile(f"{ZWNJ}+")
# Any run of spaces and ZWNJs that holds a space is one space (a single pass, so the result is
# stable: overlapping " ZWNJ " pairs used to leave a ZWNJ for the next call to remove).
_ZWNJ_BESIDE_SPACE = re.compile(f"[ {ZWNJ}]* [ {ZWNJ}]*")
_ZWNJ_AT_LINE_EDGES = re.compile(f"^{ZWNJ}|{ZWNJ}$", re.MULTILINE)


def to_latin_digits(text: str) -> str:
    """Map Persian and Arabic-Indic digits to ASCII digits."""
    return text.translate(_DIGITS_TO_LATIN)


def to_persian_digits(text: str) -> str:
    """Map ASCII digits to Persian digits (for display)."""
    return text.translate(_LATIN_TO_PERSIAN)


def normalize_persian(text: str) -> str:
    """Canonical form used for matching, search and display-independent comparison.

    Idempotent: ``normalize_persian(normalize_persian(x)) == normalize_persian(x)``.
    """
    text = text.translate(_CHAR_MAP)
    text = _DIACRITICS.sub("", text)
    text = to_latin_digits(text)
    text = _ZWNJ_RUNS.sub(ZWNJ, text)
    text = _SPACES.sub(" ", text)
    # A ZWNJ next to a space or at a line edge carries no meaning.
    text = _ZWNJ_BESIDE_SPACE.sub(" ", text)
    lines = (_ZWNJ_AT_LINE_EDGES.sub("", line.strip()).strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)
