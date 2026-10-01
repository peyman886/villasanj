from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from villasanj.shared.domain.errors import InvalidMoney
from villasanj.shared.domain.money import Money, MoneyRange

amounts = st.integers(min_value=0, max_value=10**15)


class TestMoney:
    def test_toman_is_ten_rial(self) -> None:
        assert Money.from_toman(1_500_000) == Money(15_000_000)
        assert Money(15_000_000).toman == Decimal(1_500_000)

    def test_toman_keeps_fractional_rial(self) -> None:
        assert Money(15).toman == Decimal("1.5")

    @pytest.mark.parametrize("bad", [-1, 1.5, "10", True, None])
    def test_rejects_invalid_amounts(self, bad: object) -> None:
        with pytest.raises(InvalidMoney):
            Money(bad)  # type: ignore[arg-type]

    def test_subtraction_cannot_go_negative(self) -> None:
        assert Money(10) - Money(4) == Money(6)
        with pytest.raises(InvalidMoney):
            Money(4) - Money(10)

    def test_multiplication_by_non_negative_int(self) -> None:
        assert Money(7) * 3 == Money(21)
        assert 3 * Money(7) == Money(21)
        with pytest.raises(InvalidMoney):
            Money(7) * -1

    @given(amounts, amounts)
    def test_addition_is_commutative(self, a: int, b: int) -> None:
        assert Money(a) + Money(b) == Money(b) + Money(a)

    def test_ordering(self) -> None:
        assert Money.zero() < Money(1) <= Money(1)


class TestMoneyRange:
    def test_exact_and_open(self) -> None:
        assert MoneyRange.exact(Money(5)).is_exact
        assert MoneyRange.at_least(Money(5)).is_open
        assert not MoneyRange.between(Money(1), Money(2)).is_exact

    def test_rejects_inverted_range(self) -> None:
        with pytest.raises(InvalidMoney):
            MoneyRange.between(Money(10), Money(5))

    def test_open_plus_bounded_stays_open(self) -> None:
        total = MoneyRange.at_least(Money(10)) + MoneyRange.exact(Money(5))
        assert total == MoneyRange.at_least(Money(15))

    def test_bounded_sum(self) -> None:
        total = MoneyRange.between(Money(1), Money(2)) + MoneyRange.between(Money(10), Money(20))
        assert total == MoneyRange.between(Money(11), Money(22))

    def test_scale(self) -> None:
        assert MoneyRange.between(Money(1), Money(2)).scale(3) == MoneyRange.between(
            Money(3), Money(6)
        )
        assert MoneyRange.at_least(Money(2)).scale(2) == MoneyRange.at_least(Money(4))

    @given(amounts, amounts, amounts)
    def test_contains(self, a: int, b: int, c: int) -> None:
        low, high = sorted((a, b))
        money_range = MoneyRange.between(Money(low), Money(high))
        assert money_range.contains(Money(c)) == (low <= c <= high)
        assert MoneyRange.at_least(Money(low)).contains(Money(c)) == (c >= low)
