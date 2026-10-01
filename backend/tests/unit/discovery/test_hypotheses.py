"""Hypothesis measures and the report: price gaps, hidden nights, one partner per listing."""

from datetime import date, timedelta

from tests.fakes.er import CandidateStoreFake
from tests.fakes.llm import NOW
from tests.unit.catalog.test_listing import parsed
from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.discovery.application.hypotheses import BuildHypothesisReport, render_markdown
from villasanj.discovery.domain.hypotheses import compare_calendars, price_gap, summarize_gaps
from villasanj.entity_resolution.application.ports import MatchRun, ScoredCandidate
from villasanj.entity_resolution.domain.evaluation import Interval
from villasanj.entity_resolution.domain.pairs import BlockingSource, PairKey
from villasanj.entity_resolution.domain.scoring import Score
from villasanj.ingestion.domain.parsed import Availability
from villasanj.pricing.application.quotes import QuoteStays
from villasanj.pricing.domain.quote import Quote, QuoteSource, QuoteStatus, StayRequest
from villasanj.shared.domain.money import Money, MoneyRange
from villasanj.shared.domain.stay import DateRange, GuestCount, StayScenario

SNAPSHOT = "00000000-0000-0000-0000-000000000b01"
STAY = DateRange(date(2026, 10, 15), date(2026, 10, 17))
J, S = ListingId("jabama", "1"), ListingId("shab", "2")


def quote(
    listing: ListingId, toman: int | None, status: QuoteStatus = QuoteStatus.BOOKABLE
) -> Quote:
    total = MoneyRange.at_least(Money.from_toman(toman)) if toman is not None else None
    return Quote(listing, StayRequest(STAY, GuestCount(4)), status, total, QuoteSource.CALENDAR)


def test_price_gap_compares_listed_totals() -> None:
    gap = price_gap(quote(J, 2_000_000), quote(S, 3_000_000))
    assert gap is not None
    assert (gap.cheaper_platform, gap.ratio) == ("jabama", 1.5)
    equal = price_gap(quote(J, 1_000), quote(S, 1_000))
    assert equal is not None
    assert equal.cheaper_platform is None
    assert price_gap(quote(J, 1_000), quote(S, None, QuoteStatus.UNAVAILABLE)) is None
    assert price_gap(quote(J, 0), quote(S, 1_000)) is None


def test_gap_summary() -> None:
    gaps = [g for g in (price_gap(quote(J, 100), quote(S, x)) for x in (100, 110, 150, 300)) if g]
    summary = summarize_gaps(gaps)
    assert summary.pairs == 4
    assert summary.median_ratio == 1.3
    assert summary.p90_ratio == 3.0
    assert summary.cheaper == {"jabama": 3}
    assert summarize_gaps([]).median_ratio is None


def obs(
    listing: ListingId, night: date, availability: Availability, hours: float = 0
) -> CalendarObservation:
    return CalendarObservation(
        listing, night, availability, None, None, None, None, SNAPSHOT, NOW + timedelta(hours=hours)
    )


A, U, K = Availability.AVAILABLE, Availability.UNAVAILABLE, Availability.UNKNOWN
D1, D2, D3, D4, D5 = (date(2026, 10, d) for d in (10, 11, 12, 13, 14))


def test_hidden_nights_need_close_observations() -> None:
    first = [
        obs(J, D1, A),
        obs(J, D2, A),
        obs(J, D3, A),
        obs(J, D4, K),
        obs(J, D5, A),
        obs(J, D1, U, -5),
    ]
    second = [
        obs(S, D1, U, 2),
        obs(S, D2, A, 1),
        obs(S, D3, U, 9),
        obs(S, D4, U),
        obs(S, date(2026, 10, 20), U),
    ]
    result = compare_calendars(first, second, timedelta(hours=6))
    assert result.compared == 2  # D1 and D2 (D3 too far apart in time, D4 unknown, D5 one side)
    assert result.hidden == (D1,)


def listing(key: ListingId) -> Listing:
    return Listing.from_parsed(
        parsed(platform=key.platform, external_id=key.external_id), SNAPSHOT, NOW
    )


class Reader:
    def __init__(self, calendars: dict[ListingId, list[CalendarObservation]]) -> None:
        self.calendars = calendars
        self.all = {key: listing(key) for key in calendars}

    async def get(self, listing_id: ListingId) -> Listing | None:
        return self.all.get(listing_id)

    async def listings(self, platform: str) -> list[Listing]:
        return [x for x in self.all.values() if x.id.platform == platform]

    async def calendar(self, listing_id: ListingId, stay: DateRange) -> list[CalendarObservation]:
        return [o for o in self.calendars.get(listing_id, []) if stay.contains_night(o.night)]


def priced(listing_id: ListingId, night: date, toman: int) -> CalendarObservation:
    return CalendarObservation(
        listing_id, night, A, Money.from_toman(toman), None, 1, False, SNAPSHOT, NOW
    )


async def test_report_pairs_each_listing_once_and_measures_everything() -> None:
    j2, s3 = ListingId("jabama", "3"), ListingId("shab", "4")
    nights = (date(2026, 10, 15), date(2026, 10, 16))
    calendars = {
        J: [priced(J, n, 1_000_000) for n in nights] + [obs(J, D1, A)],
        S: [priced(S, n, 1_500_000) for n in nights] + [obs(S, D1, U)],
        j2: [priced(j2, n, 900_000) for n in nights],
        s3: [priced(s3, n, 800_000) for n in nights],
    }

    def candidate(key: PairKey, value: float) -> ScoredCandidate:
        return ScoredCandidate(
            key, frozenset({BlockingSource.PHOTO_HASH}), True, None, Score(value, ())
        )

    store = CandidateStoreFake(
        [
            candidate(PairKey.of(J, S), 12),
            candidate(PairKey.of(J, s3), 11),  # J is already taken by a stronger pair
            candidate(PairKey.of(j2, s3), 9),
            candidate(PairKey.of(j2, S), 3),  # below the threshold
        ]
    )
    store.runs.append(MatchRun("r1", "a" * 64, {}, {}, NOW))
    reader = Reader(calendars)
    scenario = StayScenario("weekend", "آخر هفته", STAY, (GuestCount(4),))
    report = await BuildHypothesisReport(store, reader, QuoteStays(reader, {})).run(
        ["jabama", "shab"],
        threshold=5,
        scenarios=[scenario],
        window=DateRange(date(2026, 10, 1), date(2026, 12, 1)),
        precision=Interval(0.96, 0.93, 0.98),
    )
    assert report.pairs == 2
    assert report.matched == {"jabama": 2, "shab": 2}
    assert report.listings == {"jabama": 2, "shab": 2}
    weekend = report.gaps[0].summary
    assert weekend.pairs == 2
    assert weekend.cheaper == {"jabama": 1, "shab": 1}
    assert report.hidden_nights == 1
    assert report.pairs_with_hidden_night == 1
    assert report.nights_compared == 5  # 2 priced nights x 2 pairs + D1 on the first pair
    text = render_markdown(report)
    assert "# M3 hypothesis report" in text
    assert "96.0%" in text
    assert "| jabama | 2 | 2 | 100.0% |" in text
