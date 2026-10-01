"""Numbers mentioned in Persian text, in digits or words («چهار نفر», «۲ و نیم», «دو میلیون»).

Used to verify that every number an LLM puts into structured output (a search intent, an extracted
claim) was actually said (ADR-0007): a value no mention produces is an invented number. Mentions are
deliberately generous (extra mentions only allow, never invent), but a few readings are excluded
because they would allow numbers nobody said: weekday names («پنج شنبه» is Thursday, not five) and
adjacent numbers without «و» («دو سه نفر» is two or three, not five).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from villasanj.shared.domain.persian_text import ZWNJ, normalize_persian, to_latin_digits

_UNITS = {
    "صفر": 0,
    "یک": 1,
    "یه": 1,
    "دو": 2,
    "سه": 3,
    "چهار": 4,
    "پنج": 5,
    "شش": 6,
    "شیش": 6,
    "هفت": 7,
    "هشت": 8,
    "نه": 9,
    "ده": 10,
    "یازده": 11,
    "دوازده": 12,
    "سیزده": 13,
    "چهارده": 14,
    "پانزده": 15,
    "پونزده": 15,
    "شانزده": 16,
    "شونزده": 16,
    "هفده": 17,
    "هیفده": 17,
    "هجده": 18,
    "هیجده": 18,
    "نوزده": 19,
    "بیست": 20,
    "سی": 30,
    "چهل": 40,
    "پنجاه": 50,
    "شصت": 60,
    "هفتاد": 70,
    "هشتاد": 80,
    "نود": 90,
    "صد": 100,
    "یکصد": 100,
    "دویست": 200,
    "سیصد": 300,
    "چهارصد": 400,
    "پانصد": 500,
    "پونصد": 500,
    "ششصد": 600,
    "هفتصد": 700,
    "هشتصد": 800,
    "نهصد": 900,
}
_SCALES = {"هزار": 1_000, "میلیون": 1_000_000, "میلیارد": 1_000_000_000}
_HALF = "نیم"
_AND = "و"
_RANGE_WORDS = frozenset({"تا", "یا", "-"})
_WEEKDAY_TAIL = "شنبه"  # «یک/دو/سه/چهار/پنج شنبه» name weekdays
# A number word glued to one of these is still that number («چهارنفره», «دوخوابه»).
_GLUED_SUFFIXES = frozenset(
    {"نفره", "نفر", "نفری", "خوابه", "خواب", "شب", "شبه", "روز", "روزه", "ساعت", "ساعته", "تخته"}
)
_TOKEN = re.compile(r"\d+(?:[.,،٬٫]\d+)*|[^\W\d_]+|-")
_GROUPED_THOUSANDS = re.compile(r"^\d{1,3}([.,،٬]\d{3})+$")
_DECIMAL = re.compile(r"^(\d+)[.٫](\d{1,2})$")


@dataclass(frozen=True, slots=True)
class _Phrase:
    start: int
    end: int  # index after the phrase
    value: Decimal
    scale: int | None  # the scale word closing the phrase («میلیون»), if any


def number_mentions(text: str) -> list[Decimal]:
    """Every number the text mentions, in order (a compound like «دو میلیون و پانصد» once)."""
    tokens = _TOKEN.findall(to_latin_digits(normalize_persian(text)).replace(ZWNJ, " "))
    mentions: list[Decimal] = []
    previous: _Phrase | None = None
    index = 0
    while index < len(tokens):
        phrase = _phrase(tokens, index)
        if phrase is None:
            index += 1
            continue
        mentions.append(phrase.value)
        # «دو ساعت و نیم»: the half belongs to the number before the unit.
        if tokens[phrase.end + 1 : phrase.end + 3] == [_AND, _HALF]:
            mentions.append(phrase.value + Decimal("0.5"))
        # «۲ تا ۳ میلیون»: the second number's scale applies to the first.
        if (
            previous is not None
            and phrase.scale is not None
            and previous.scale is None
            and previous.end == phrase.start - 1
            and tokens[previous.end] in _RANGE_WORDS
        ):
            mentions.append(previous.value * phrase.scale)
        previous = phrase
        index = phrase.end
    return mentions


def unmentioned(values: Iterable[Decimal], text: str) -> list[Decimal]:
    """The values no mention in ``text`` produces (empty: every number was said)."""
    said = set(number_mentions(text))
    return [v for v in values if v not in said]


def _phrase(tokens: list[str], start: int) -> _Phrase | None:
    """One number phrase at ``start``: parts joined by «و» in decreasing size, with scale words."""
    total = Decimal(0)
    current: Decimal | None = None
    last_part: Decimal | None = None  # «و» may only add a smaller part
    scale: int | None = None
    index = start
    while True:
        value = _atom(tokens, index)
        if value is None or (last_part is not None and value >= last_part):
            if index > start:
                index -= 1  # the «و» before it is not part of the number
            break
        current = (current or Decimal(0)) + value
        last_part, scale = value, None
        index += 1
        while index < len(tokens) and (word_scale := _scale(tokens[index])) is not None:
            scale = word_scale
            total += current * scale
            current, last_part = Decimal(0), Decimal(scale)
            index += 1
        if index + 1 < len(tokens) and tokens[index] == _AND:
            index += 1
            continue
        break
    if index == start:
        return None
    return _Phrase(start, index, total + (current or 0), scale)


# Colloquial and adjective forms: «۱۰ میلیونه» ("it is ten million"), «ویلای ۵ میلیونی».
_SCALE_SUFFIXES = ("", "ه", "ی", "یه")


def _scale(token: str) -> int | None:
    for word, value in _SCALES.items():
        if token.startswith(word) and token[len(word) :] in _SCALE_SUFFIXES:
            return value
    return None


def _atom(tokens: list[str], index: int) -> Decimal | None:
    token = tokens[index]
    if token in _UNITS and tokens[index + 1 : index + 2] == [_WEEKDAY_TAIL]:
        return None  # a weekday name
    return _value(token)


def _value(token: str) -> Decimal | None:
    if token == _HALF:
        return Decimal("0.5")
    if token in _UNITS:
        return Decimal(_UNITS[token])
    if token[:1].isdigit():
        return _digits(token)
    for word, value in _UNITS.items():
        if token.startswith(word) and token[len(word) :] in _GLUED_SUFFIXES:
            return Decimal(value)
    return None


def _digits(token: str) -> Decimal | None:
    if token.isdigit():
        return Decimal(token)
    if _GROUPED_THOUSANDS.match(token):
        return Decimal(re.sub(r"[.,،٬]", "", token))
    decimal = _DECIMAL.match(token)
    if decimal:
        return Decimal(f"{decimal.group(1)}.{decimal.group(2)}")
    return None
