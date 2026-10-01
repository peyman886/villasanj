"""Parse Persian money text ("۱۲٫۵ میلیون تومان", "۵ میلیون و ۵۰۰ هزار", "1,500,000 ریال").

Rules: digits in any script; thousands separators (comma, Arabic comma, Arabic thousands sign,
dot groups, spaces); decimal point ("٫" or "." followed by one or two digits); scale words
هزار/میلیون/میلیارد, including compounds joined by «و» with decreasing scales; unit تومان (the
default on Iranian listing sites when absent) or ریال. Anything ambiguous returns ``None``.
"""

from __future__ import annotations

import re
from decimal import Decimal

from villasanj.shared.domain.money import RIALS_PER_TOMAN, Money
from villasanj.shared.domain.persian_text import normalize_persian

_SCALES = {"هزار": 1_000, "میلیون": 1_000_000, "میلیارد": 1_000_000_000}
_RIAL_WORDS = ("ریال",)
_TOMAN_WORDS = ("تومان", "تومن", "toman")
_TERM = re.compile(r"(\d(?:[\d,،٬.٫' ]*\d)?)\s*(میلیارد|میلیون|هزار)?")
_GROUPED_THOUSANDS = re.compile(r"^\d{1,3}([,،٬.' ]\d{3})+$")
_DECIMAL = re.compile(r"^(\d+)[.٫](\d{1,2})$")
_PLAIN = re.compile(r"^\d+$")
_JOINER = re.compile(r"^\s*و\s*$")


def parse_money_text(text: str) -> Money | None:
    normalized = normalize_persian(text).lower()
    terms = list(_TERM.finditer(normalized))
    if not terms:
        return None
    amount = _sum_terms(normalized, terms)
    if amount is None:
        return None
    tail = normalized[terms[-1].end() :]
    is_rial = any(word in tail for word in _RIAL_WORDS)
    if is_rial and any(word in tail for word in _TOMAN_WORDS):
        return None  # contradictory units
    rial = amount * (1 if is_rial else RIALS_PER_TOMAN)
    if rial != rial.to_integral_value():
        return None
    return Money.from_rial(int(rial))


def _sum_terms(text: str, terms: list[re.Match[str]]) -> Decimal | None:
    total = Decimal(0)
    previous_scale: int | None = None
    for index, term in enumerate(terms):
        if index > 0 and not _JOINER.match(text[terms[index - 1].end() : term.start()]):
            return None  # two unrelated numbers: ambiguous
        number = _to_decimal(term.group(1))
        if number is None:
            return None
        scale = _SCALES.get(term.group(2) or "", 1)
        if previous_scale is not None and scale >= previous_scale:
            return None  # compounds must decrease: «۵ میلیون و ۵۰۰ هزار»
        total += number * scale
        previous_scale = scale
    return total


def _to_decimal(token: str) -> Decimal | None:
    if _PLAIN.match(token):
        return Decimal(token)
    if _GROUPED_THOUSANDS.match(token):
        return Decimal(re.sub(r"[,،٬.' ]", "", token))
    decimal = _DECIMAL.match(token)
    if decimal:
        return Decimal(f"{decimal.group(1)}.{decimal.group(2)}")
    return None
