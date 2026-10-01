from datetime import date

import pytest

from villasanj.shared.domain.errors import InvalidDateRange, InvalidGuestCount
from villasanj.shared.domain.stay import MAX_GUESTS, DateRange, GuestCount


class TestDateRange:
    def test_nights_exclude_check_out(self) -> None:
        stay = DateRange(date(2026, 10, 1), date(2026, 10, 3))
        assert stay.night_count == 2
        assert list(stay.nights()) == [date(2026, 10, 1), date(2026, 10, 2)]
        assert stay.contains_night(date(2026, 10, 2))
        assert not stay.contains_night(date(2026, 10, 3))

    @pytest.mark.parametrize("check_out", [date(2026, 10, 1), date(2026, 9, 30)])
    def test_rejects_empty_or_inverted(self, check_out: date) -> None:
        with pytest.raises(InvalidDateRange):
            DateRange(date(2026, 10, 1), check_out)

    def test_overlap_is_half_open(self) -> None:
        first = DateRange(date(2026, 10, 1), date(2026, 10, 3))
        assert first.overlaps(DateRange(date(2026, 10, 2), date(2026, 10, 5)))
        assert not first.overlaps(DateRange(date(2026, 10, 3), date(2026, 10, 5)))


class TestGuestCount:
    @pytest.mark.parametrize("bad", [0, -1, MAX_GUESTS + 1, True, 2.0])
    def test_bounds(self, bad: object) -> None:
        with pytest.raises(InvalidGuestCount):
            GuestCount(bad)  # type: ignore[arg-type]

    def test_extra_guests_above_base_capacity(self) -> None:
        assert GuestCount(8).above(6) == 2
        assert GuestCount(4).above(6) == 0
        assert int(GuestCount(8)) == 8
