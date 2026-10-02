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


MINUTE_STEP = 5  # free-flow estimates are not minute-precise: ranges widen to whole 5 minutes
METRE_STEP = 50
KM_STEP = 100
METRES_PER_KM = 1000


def _hours_minutes(total_minutes: int) -> str:
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{fa_int(hours)} ساعت و {fa_int(minutes)} دقیقه"
    if hours:
        return f"{fa_int(hours)} ساعت"
    return f"{fa_int(minutes)} دقیقه"


def fa_minutes_range(low_s: float, high_s: float) -> str:
    """«۴ ساعت و ۱۵ تا ۴ ساعت و ۲۵ دقیقه»: widened outwards to whole 5-minute steps."""
    low = int(low_s / 60 // MINUTE_STEP * MINUTE_STEP)
    high = _ceil(high_s / 60)
    if low == high:
        return f"حدود {_hours_minutes(low)}"
    return f"{_hours_minutes(low)} تا {_hours_minutes(high)}"


def _ceil(minutes: float) -> int:
    steps = -(-minutes // MINUTE_STEP)
    return int(steps * MINUTE_STEP)


def fa_metres_range(low_m: float, high_m: float) -> str:
    """«۶۰۰ تا ۱٬۴۰۰ متر» or «۱٫۲ تا ۲ کیلومتر», widened outwards to round values."""
    if high_m < METRES_PER_KM:
        low = int(low_m // METRE_STEP * METRE_STEP)
        high = int(-(-high_m // METRE_STEP) * METRE_STEP)
        return f"{fa_int(low)} تا {fa_int(high)} متر"
    low_km = (low_m // KM_STEP) * KM_STEP / METRES_PER_KM
    high_km = -(-high_m // KM_STEP) * KM_STEP / METRES_PER_KM
    return f"{fa_decimal(low_km)} تا {fa_decimal(high_km)} کیلومتر"


def fa_metres(metres: float) -> str:
    """«۵۵۰ متر» or «۱۰ کیلومتر»: one bound, rounded up (it is a limit someone may reach)."""
    if metres < METRES_PER_KM:
        return f"{fa_int(int(-(-metres // METRE_STEP) * METRE_STEP))} متر"
    return f"{fa_decimal(-(-metres // KM_STEP) * KM_STEP / METRES_PER_KM)} کیلومتر"
