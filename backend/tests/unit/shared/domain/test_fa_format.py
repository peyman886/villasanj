from villasanj.shared.domain.fa_format import fa_decimal, fa_int, fa_toman
from villasanj.shared.domain.money import Money, MoneyRange


def test_persian_numbers_match_the_ui() -> None:
    assert fa_int(2_500_000) == "۲٬۵۰۰٬۰۰۰"
    assert fa_int(7) == "۷"
    assert fa_decimal(4.8) == "۴٫۸"
    assert fa_decimal(5.0) == "۵"
    assert fa_decimal(1234.56, 2) == "۱٬۲۳۴٫۵۶"
    assert fa_decimal(3.4, 0) == "۳"


def test_money_ranges_never_invent_an_upper_bound() -> None:
    low, high = Money.from_toman(2_000_000), Money.from_toman(3_000_000)
    assert fa_toman(MoneyRange.exact(low)) == "۲٬۰۰۰٬۰۰۰ تومان"
    assert fa_toman(MoneyRange.between(low, high)) == "۲٬۰۰۰٬۰۰۰ تا ۳٬۰۰۰٬۰۰۰ تومان"
    assert fa_toman(MoneyRange.at_least(low)) == "حداقل ۲٬۰۰۰٬۰۰۰ تومان"


def test_time_and_distance_ranges_widen_to_round_values() -> None:
    from villasanj.shared.domain.fa_format import fa_metres_range, fa_minutes_range

    assert fa_minutes_range(15_500, 15_800) == "۴ ساعت و ۱۵ دقیقه تا ۴ ساعت و ۲۵ دقیقه"
    assert fa_minutes_range(14_400, 14_400) == "حدود ۴ ساعت"
    assert fa_minutes_range(600, 1_190) == "۱۰ دقیقه تا ۲۰ دقیقه"
    assert fa_metres_range(620, 990) == "۶۰۰ تا ۱٬۰۰۰ متر"
    assert fa_metres_range(1_150, 1_951) == "۱٫۱ تا ۲ کیلومتر"
