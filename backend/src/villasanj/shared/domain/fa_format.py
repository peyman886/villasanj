"""Numbers and money as Persian text («۲٬۵۰۰٬۰۰۰ تومان», «۴٫۸»), the way the UI shows them.

Only code formats numbers (ADR-0007): these strings fill the fact slots of LLM-written text.
"""

from __future__ import annotations

from villasanj.shared.domain.money import MoneyRange
from villasanj.shared.domain.persian_text import to_persian_digits

THOUSANDS = "\N{ARABIC THOUSANDS SEPARATOR}"
DECIMAL = "\N{ARABIC DECIMAL SEPARATOR}"


def fa_int(value: int) -> str:
    return to_persian_digits(f"{value:,}".replace(",", THOUSANDS))


def fa_decimal(value: float, places: int = 1) -> str:
    text = f"{value:,.{places}f}".rstrip("0").rstrip(".") if places else f"{value:,.0f}"
    return to_persian_digits(text.replace(",", THOUSANDS).replace(".", DECIMAL))


def fa_toman(amount: MoneyRange) -> str:
    """Exact, a range, or "at least" when part of the cost is unknown (product rule 1)."""
    low = fa_int(int(amount.low.toman))
    if amount.high is None:
        return f"حداقل {low} تومان"
    if amount.is_exact:
        return f"{low} تومان"
    return f"{low} تا {fa_int(int(amount.high.toman))} تومان"
