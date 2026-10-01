"""Money in Iranian rial (integer) with toman presentation, and ranges for partial knowledge."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from villasanj.shared.domain.errors import InvalidMoney

RIALS_PER_TOMAN = 10


def _require_non_negative_int(value: object, what: str) -> int:
    # bool is an int subclass; a boolean amount is always a bug.
    if not isinstance(value, int) or isinstance(value, bool):
        raise InvalidMoney(f"{what} must be an integer, got {type(value).__name__}")
    if value < 0:
        raise InvalidMoney(f"{what} must be non-negative, got {value}")
    return value


@dataclass(frozen=True, slots=True, order=True)
class Money:
    """A non-negative amount of Iranian money, stored exactly in rial.

    Platforms display toman (1 toman = 10 rial); unit detection belongs to the text normalizer.
    """

    amount_rial: int

    def __post_init__(self) -> None:
        _require_non_negative_int(self.amount_rial, "amount_rial")

    @classmethod
    def zero(cls) -> Money:
        return cls(0)

    @classmethod
    def from_rial(cls, amount: int) -> Money:
        return cls(amount)

    @classmethod
    def from_toman(cls, amount: int) -> Money:
        return cls(_require_non_negative_int(amount, "amount_toman") * RIALS_PER_TOMAN)

    @property
    def toman(self) -> Decimal:
        return Decimal(self.amount_rial) / RIALS_PER_TOMAN

    def __add__(self, other: Money) -> Money:
        return Money(self.amount_rial + other.amount_rial)

    def __sub__(self, other: Money) -> Money:
        if other.amount_rial > self.amount_rial:
            raise InvalidMoney("subtraction would produce a negative amount")
        return Money(self.amount_rial - other.amount_rial)

    def __mul__(self, factor: int) -> Money:
        return Money(self.amount_rial * _require_non_negative_int(factor, "factor"))

    __rmul__ = __mul__


@dataclass(frozen=True, slots=True)
class MoneyRange:
    """What we know about an amount: exact, bounded, or open-ended (``high is None``: ">= low").

    An open upper bound is how unknown components are represented: we never invent a cap.
    """

    low: Money
    high: Money | None

    def __post_init__(self) -> None:
        if self.high is not None and self.high < self.low:
            raise InvalidMoney("money range upper bound is below its lower bound")

    @classmethod
    def exact(cls, amount: Money) -> MoneyRange:
        return cls(amount, amount)

    @classmethod
    def between(cls, low: Money, high: Money) -> MoneyRange:
        return cls(low, high)

    @classmethod
    def at_least(cls, low: Money) -> MoneyRange:
        return cls(low, None)

    @property
    def is_exact(self) -> bool:
        return self.high is not None and self.high == self.low

    @property
    def is_open(self) -> bool:
        return self.high is None

    def contains(self, amount: Money) -> bool:
        return self.low <= amount and (self.high is None or amount <= self.high)

    def __add__(self, other: MoneyRange) -> MoneyRange:
        high = None if self.high is None or other.high is None else self.high + other.high
        return MoneyRange(self.low + other.low, high)

    def scale(self, factor: int) -> MoneyRange:
        return MoneyRange(self.low * factor, None if self.high is None else self.high * factor)
