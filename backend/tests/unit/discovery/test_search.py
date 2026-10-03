"""Search end to end with fakes: intent, dates, places, offers, features, ranking."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from decimal import Decimal

from tests.fakes.er import ListingsFake
from tests.fakes.llm import NOW, FixedClock
from tests.unit.catalog.test_reports import listing
from tests.unit.discovery.test_holiday_calendar import SOURCES, Flags
from tests.unit.discovery.test_routing import Store as DriveStore
from tests.unit.discovery.test_understanding import ScriptedClient
from tests.unit.enrichment.test_coast import Store as CoastStore
from tests.unit.pricing.test_quote import night
from villasanj.catalog.domain.gazetteer import Gazetteer, Place, PlaceKind
from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.discovery.application.dates import BuildHolidayCalendar
from villasanj.discovery.application.intent import Budget, DateSpec, DriveLimit, SearchIntent
from villasanj.discovery.application.routing import DriveTime, Leg, Origin
from villasanj.discovery.application.search import Missing, SearchListings
from villasanj.discovery.application.understanding import UnderstandQuery
from villasanj.discovery.domain.ranking import Caution, Exclusion
from villasanj.enrichment.application.coast import CoastDistance
from villasanj.enrichment.application.features import AmenityMap
from villasanj.enrichment.domain.features import Feature, FeatureEvidence
from villasanj.enrichment.domain.geo import Blur
from villasanj.ingestion.domain.parsed import ParsedAmenity
from villasanj.pricing.application.offers import OfferBook
from villasanj.shared.application.llm.types import JobContext
from villasanj.shared.domain.geo import GeoPoint
from villasanj.shared.domain.stay import DateRange

CTX = JobContext("job", Decimal(1))
THU, FRI = date(2026, 10, 1), date(2026, 10, 2)
GAZETTEER = Gazetteer(
    [Place("ramsar", "رامسر", PlaceKind.CITY), Place("tonekabon", "تنکابن", PlaceKind.CITY)]
)
POOL = ParsedAmenity("pool", "استخر", True)
NO_POOL = ParsedAmenity("pool", "استخر", False)


class Calendars(ListingsFake):
    """Every listing is free on Thursday and Friday nights, at the same price."""

    async def calendars(
        self, platform: str, stay: DateRange
    ) -> dict[ListingId, list[CalendarObservation]]:
        return {
            x.id: [replace(night(d), listing_id=x.id) for d in (THU, FRI)]
            for x in self.by_id.values()
            if x.id.platform == platform
        }


LISTINGS: Sequence[Listing] = [
    listing("pool", city_fa="رامسر", amenities=(POOL,)),
    listing("no-pool", city_fa="رامسر", description="ویلا نزدیک دریا", amenities=(NO_POOL,)),
    # The amenity list says no pool, the description «ویلا با استخر»: contradicted, kept.
    listing("contradicted", city_fa="رامسر", amenities=(NO_POOL,)),
    listing("elsewhere", city_fa="تنکابن", amenities=(POOL,)),
]
WEEKEND = SearchIntent(
    dates=DateSpec(kind="weekend"),
    guest_parts=[4],
    budget=Budget(max_toman=5_000_000, basis="whole_stay"),
    places=["رامسر"],
    features=["pool"],
)


ORIGIN = Origin("tehran", "تهران", GeoPoint(35.7, 51.34), "test")


def coast_and_drives() -> tuple[CoastStore, DriveStore]:
    coast, drives = CoastStore(), DriveStore()
    near = ListingId("p", "pool")
    coast.rows = [CoastDistance(near, "osm", 300.0, 0.0, 700.0, Blur(400, False), NOW)]
    drives.rows = [
        DriveTime(
            near,
            "tehran",
            "osm",
            Leg(13_800.0, 200_000.0),
            13_500.0,
            14_100.0,
            9,
            Blur(400, False),
            NOW,
        ),
        DriveTime(
            ListingId("p", "no-pool"),
            "tehran",
            "osm",
            None,
            18_000.0,
            18_600.0,
            8,
            Blur(400, False),
            NOW,
        ),
    ]
    return coast, drives


def search(
    intent: SearchIntent,
    listings: Sequence[Listing] = LISTINGS,
    places: object = None,
    photos: object = None,
) -> SearchListings:
    reader = Calendars(listings)
    clock = FixedClock()
    coast, drives = coast_and_drives()
    return SearchListings(
        UnderstandQuery(ScriptedClient(intent)),
        BuildHolidayCalendar(Flags([]), SOURCES),
        reader,
        OfferBook(reader, {}, clock),
        AmenityMap({"p": {"pool": Feature.POOL}}),
        GAZETTEER,
        ["p"],
        clock,
        coast,
        drives,
        ORIGIN,
        places,  # type: ignore[arg-type]
        photos,  # type: ignore[arg-type]
    )


async def test_a_full_search_filters_by_place_and_feature_and_ranks() -> None:
    result = await search(WEEKEND).run(
        "ویلای استخردار در رامسر برای ۴ نفر آخر هفته زیر ۵ میلیون", CTX
    )
    assert result.dates is not None
    assert result.dates.window == DateRange(THU, date(2026, 10, 3))
    assert result.missing == ()
    assert [p.slug for p in result.places] == ["ramsar"]
    assert result.ranking is not None
    assert [r.candidate.id for r in result.ranking.results] == ["p:pool", "p:contradicted"]
    pool, contradicted = result.ranking.results
    # No fee policy: every offer is open ("at least"), so it may exceed the budget (rule 1).
    assert pool.warnings == {Caution.MAY_EXCEED_BUDGET}
    assert contradicted.warnings == {Caution.MAY_EXCEED_BUDGET, Caution.FEATURE_UNCONFIRMED}
    # "elsewhere" (Tonekabon) is not a candidate at all; "no-pool" is excluded with its reason.
    assert result.ranking.excluded == {Exclusion.FEATURE_DENIED: 1}
    assert set(result.offers) == {"p:pool", "p:no-pool", "p:contradicted"}
    assert result.listings["p:pool"].id == ListingId("p", "pool")


async def test_what_the_query_leaves_open_is_asked_not_guessed() -> None:
    no_dates = await search(SearchIntent(guest_parts=[4])).run("ویلا برای ۴ نفر", CTX)
    assert (no_dates.ranking, no_dates.missing) == (None, (Missing.DATES,))
    nowruz = await search(SearchIntent(dates=DateSpec(kind="nowruz"))).run("نوروز", CTX)
    assert nowruz.ranking is None
    assert nowruz.missing == (Missing.EXACT_STAY, Missing.GUESTS)
    past = SearchIntent(
        dates=DateSpec(kind="jalali_day", month=7, day=1, year=1405), guest_parts=[4]
    )
    result = await search(past).run("۱ مهر ۱۴۰۵ برای ۴ نفر", CTX)
    assert result.missing == (Missing.UNRESOLVABLE_DATES,)


async def test_an_unknown_place_is_reported_and_not_used_as_a_filter() -> None:
    intent = WEEKEND.model_copy(update={"places": ["سلمان شهر"], "features": []})
    result = await search(intent).run("آخر هفته ویلا در سلمان شهر برای ۴ نفر تا ۵ میلیون", CTX)
    assert result.unresolved_places == ("سلمان شهر",)
    assert result.ranking is not None
    assert len(result.ranking.results) == 4


async def test_the_map_answers_near_sea_and_the_drive_limit() -> None:
    intent = SearchIntent(
        dates=DateSpec(kind="weekend"),
        guest_parts=[4],
        features=["near_sea"],
        max_drive=DriveLimit(value=4, unit="hours"),
    )
    result = await search(intent).run("ویلا نزدیک دریا برای ۴ نفر آخر هفته، حداکثر ۴ ساعت", CTX)
    assert result.ranking is not None
    first = result.ranking.results[0]
    assert first.candidate.id == "p:pool"
    assert first.candidate.features[Feature.NEAR_SEA] is FeatureEvidence.MEASURED
    assert first.candidate.drive_minutes == (225.0, 235.0)
    assert result.ranking.excluded == {Exclusion.TOO_FAR: 1}  # 300 minutes at best
    assert result.geo["p:pool"].origin_fa == "تهران"
    assert result.drive_coverage == {
        3: 0,
        4: 1,
        5: 2,
        6: 2,
    }  # p:pool 225 min; p:no-pool 300 at best


async def test_removed_chips_widen_the_search() -> None:
    query = "ویلای استخردار در رامسر برای ۴ نفر آخر هفته زیر ۵ میلیون"
    result = await search(WEEKEND).run(query, CTX, drop=["place:رامسر", "feature:pool"])
    assert result.understanding.intent.places == []
    assert result.understanding.intent.features == []
    assert result.ranking is not None
    assert len(result.ranking.results) == 4


async def test_a_contradicted_distance_claim_is_a_caution_on_the_result() -> None:
    from tests.unit.enrichment.test_truth import Places, place
    from villasanj.enrichment.domain.places import PlaceKind
    from villasanj.ingestion.domain.parsed import ParsedDistanceClaim, TravelMode

    walk = (ParsedDistanceClaim("فاصله از مرکز شهر", "زیر 5 دقیقه", TravelMode.WALK),)
    homes = [
        listing("pool", city_fa="رامسر", amenities=(POOL,), distance_claims=walk),
        listing("contradicted", city_fa="رامسر", amenities=(POOL,), distance_claims=walk),
    ]
    far = place(ListingId("p", "contradicted"), PlaceKind.CITY_CENTER, 4000.0, 4800.0)
    near = place(ListingId("p", "pool"), PlaceKind.CITY_CENTER, 0.0, 800.0)
    query = "ویلای استخردار در رامسر برای ۴ نفر آخر هفته زیر ۵ میلیون"
    result = await search(WEEKEND, homes, Places([far, near])).run(query, CTX)
    assert result.ranking is not None
    warnings = {r.candidate.id: r.warnings for r in result.ranking.results}
    assert Caution.CLAIM_CONTRADICTED in warnings["p:contradicted"]
    assert Caution.CLAIM_CONTRADICTED not in warnings["p:pool"]


async def test_photos_turn_a_described_feature_into_a_seen_one() -> None:
    from tests.unit.enrichment.test_truth import Photos
    from villasanj.enrichment.domain.features import FeatureEvidence

    described = listing("described", city_fa="رامسر", description="ویلا با استخر")
    photos = Photos({described.id: frozenset({Feature.POOL})})
    query = "ویلای استخردار در رامسر برای ۴ نفر آخر هفته زیر ۵ میلیون"
    result = await search(WEEKEND, [described], None, photos).run(query, CTX)
    assert result.ranking is not None
    (only,) = result.ranking.results
    assert only.candidate.features[Feature.POOL] is FeatureEvidence.PHOTO
    assert Caution.FEATURE_ONLY_DESCRIBED not in only.warnings
