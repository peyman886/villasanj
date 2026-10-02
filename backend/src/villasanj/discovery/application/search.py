"""Search: a Persian query to a ranked, explained list of listings (ROADMAP M8; provisional).

Built ahead of M8 at listing level: until M5 the same villa can appear once per platform, and
each listing keeps its own offer (product rule 3). The query becomes a verified intent (LLM), the
dates are resolved by code, place names by the gazetteer, and the candidates are filtered and
ranked deterministically (``discovery.domain.ranking``). What the query leaves open is returned as
a question, never guessed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.gazetteer import Gazetteer, Place
from villasanj.catalog.domain.listing import Listing
from villasanj.catalog.domain.review import RatingPrior
from villasanj.discovery.application.dates import BuildHolidayCalendar
from villasanj.discovery.application.intent import SearchIntent, without
from villasanj.discovery.application.routing import DriveTime, DriveTimeStore, Origin
from villasanj.discovery.application.understanding import Understanding, UnderstandQuery
from villasanj.discovery.domain.dates import ResolvedDates, resolve
from villasanj.discovery.domain.ranking import (
    BudgetBasis,
    Candidate,
    Ranking,
    Requirements,
    drive_coverage,
    rank,
)
from villasanj.enrichment.application.coast import CoastDistance, CoastDistanceStore
from villasanj.enrichment.application.features import AmenityMap
from villasanj.enrichment.application.places import PlaceDistanceStore
from villasanj.enrichment.application.truth import place_verdicts
from villasanj.enrichment.domain.distance_claims import Verdict
from villasanj.enrichment.domain.features import (
    Feature,
    FeatureEvidence,
    extract_claims,
    feature_evidence,
    near_sea_evidence,
)
from villasanj.pricing.application.offers import OfferBook
from villasanj.pricing.domain.offer import Offer
from villasanj.pricing.domain.quote import QuoteStatus, StayRequest
from villasanj.shared.application.clock import Clock
from villasanj.shared.application.llm.types import JobContext
from villasanj.shared.domain.errors import DomainError
from villasanj.shared.domain.jalali import iran_today
from villasanj.shared.domain.stay import GuestCount


class Missing(StrEnum):
    """What the query leaves open and the user is asked for."""

    DATES = "dates"  # no date said
    EXACT_STAY = "exact_stay"  # a month or Nowruz: which nights?
    UNRESOLVABLE_DATES = "unresolvable_dates"  # e.g. a day in the past
    GUESTS = "guests"  # no group size: prices are for one guest


@dataclass(frozen=True, slots=True)
class SearchResult:
    understanding: Understanding
    dates: ResolvedDates | None
    missing: tuple[Missing, ...]
    places: tuple[Place, ...]  # the places the query names, as resolved
    unresolved_places: tuple[str, ...]  # names the gazetteer does not know: not used as filters
    ranking: Ranking | None
    offers: Mapping[str, Offer] = field(default_factory=dict)  # by candidate id
    listings: Mapping[str, Listing] = field(default_factory=dict)
    geo: Mapping[str, Geo] = field(default_factory=dict)
    drive_coverage: Mapping[int, int] = field(default_factory=dict)  # hours -> results


@dataclass(frozen=True, slots=True)
class Geo:
    """What the map says about a candidate (ADR-0013); ``None``: not measured."""

    coast: CoastDistance | None
    drive: DriveTime | None
    origin_fa: str | None = None  # where the drive times start, e.g. «میدان آزادی تهران»

    @property
    def drive_minutes(self) -> tuple[float, float] | None:
        if self.drive is None or self.drive.low_s is None or self.drive.high_s is None:
            return None
        return self.drive.low_s / 60, self.drive.high_s / 60


class SearchListings:
    def __init__(
        self,
        understand: UnderstandQuery,
        holidays: BuildHolidayCalendar,
        listings: ListingReader,
        offers: OfferBook,
        amenities: AmenityMap,
        gazetteer: Gazetteer,
        platforms: Sequence[str],
        clock: Clock,
        coast: CoastDistanceStore | None = None,
        drives: DriveTimeStore | None = None,
        origin: Origin | None = None,
        places: PlaceDistanceStore | None = None,
    ) -> None:
        self._understand = understand
        self._holidays = holidays
        self._listings = listings
        self._offers = offers
        self._amenities = amenities
        self._gazetteer = gazetteer
        self._platforms = tuple(platforms)
        self._clock = clock
        self._coast = coast
        self._drives = drives
        self._origin = origin
        self._place_distances = places

    async def run(self, query: str, ctx: JobContext, drop: Sequence[str] = ()) -> SearchResult:
        """``drop``: constraints the user removed from the understood query (editable chips)."""
        understanding = await self._understand.run(query, ctx)
        if drop:
            understanding = replace(understanding, intent=without(understanding.intent, drop))
        intent = understanding.intent
        places, unresolved = self._places(intent)
        dates, missing = await self._dates(intent)
        if intent.guests is None:
            missing.append(Missing.GUESTS)
        if dates is None or dates.flexible:
            return SearchResult(understanding, dates, tuple(missing), places, unresolved, None)
        request = StayRequest(dates.window, GuestCount(intent.guests or 1))
        candidates: list[Candidate] = []
        offers: dict[str, Offer] = {}
        listings: dict[str, Listing] = {}
        geos: dict[str, Geo] = {}
        for platform in self._platforms:
            every = await self._listings.listings(platform)
            prior = RatingPrior.from_listings(every)  # the platform-wide mean, before filtering
            platform_listings = [x for x in every if self._in(x, places)]
            platform_offers = await self._offers.offers(platform, request)
            coast = await self._coast.of_platform(platform) if self._coast else {}
            drives = (
                await self._drives.of_platform(platform, self._origin.slug)
                if self._drives and self._origin
                else {}
            )
            nearby = (
                await self._place_distances.of_platform(platform) if self._place_distances else {}
            )
            for listing in platform_listings:
                offer = platform_offers.get(listing.id)
                if offer is None:
                    continue
                key = str(listing.id)
                offers[key] = offer
                listings[key] = listing
                geo = Geo(
                    coast.get(listing.id),
                    drives.get(listing.id),
                    self._origin.name_fa if self._origin else None,
                )
                geos[key] = geo
                contradicted = sum(
                    check.assessment is not None
                    and check.assessment.verdict is Verdict.CONTRADICTED
                    for check in place_verdicts(
                        listing.distance_claims, geo.coast, nearby.get(listing.id, {})
                    )
                )
                candidates.append(
                    self._candidate(key, listing, offer, prior, intent, geo, contradicted)
                )
        wants = _requirements(intent, dates)
        ranking = rank(candidates, wants)
        coverage = (
            drive_coverage(candidates, wants) if any(c.drive_minutes for c in candidates) else {}
        )
        return SearchResult(
            understanding,
            dates,
            tuple(missing),
            places,
            unresolved,
            ranking,
            offers,
            listings,
            geos,
            coverage,
        )

    def _places(self, intent: SearchIntent) -> tuple[tuple[Place, ...], tuple[str, ...]]:
        found, unknown = [], []
        for name in intent.places:
            place = self._gazetteer.resolve(name)
            if place is None:
                unknown.append(name)
            else:
                found.append(place)
        return tuple(found), tuple(unknown)

    def _in(self, listing: Listing, places: Sequence[Place]) -> bool:
        if not places:
            return True
        here = [
            p
            for p in (
                self._gazetteer.resolve(listing.locality_fa),
                self._gazetteer.resolve(listing.city_fa),
            )
            if p is not None
        ]
        wanted = {p.slug for p in places}
        return any(p.slug in wanted or p.parent in wanted for p in here)

    async def _dates(self, intent: SearchIntent) -> tuple[ResolvedDates | None, list[Missing]]:
        expression = intent.dates.expression() if intent.dates else None
        if expression is None:
            return None, [Missing.DATES]
        today = iran_today(self._clock.now())
        calendar = await self._holidays.run(today)
        try:
            dates = resolve(expression, today, calendar, intent.nights)
        except DomainError:  # InvalidDateExpression and impossible ranges alike
            return None, [Missing.UNRESOLVABLE_DATES]
        return dates, [Missing.EXACT_STAY] if dates.flexible else []

    def _candidate(
        self,
        key: str,
        listing: Listing,
        offer: Offer,
        prior: RatingPrior | None,
        intent: SearchIntent,
        geo: Geo,
        contradicted: int = 0,
    ) -> Candidate:
        stated = self._amenities.features_of(listing)
        claims = extract_claims(listing.description_norm or "")
        features = {
            feature: feature_evidence(
                stated.get(feature), [c for c in claims if c.feature is feature]
            )
            for feature in (Feature(f) for f in intent.features)
        }
        if Feature.NEAR_SEA in features and geo.coast is not None:
            measured = near_sea_evidence(geo.coast.low_m, geo.coast.high_m)
            if measured is not FeatureEvidence.UNKNOWN:  # the map decides when it can
                features[Feature.NEAR_SEA] = measured
        rating = (
            prior.shrink(listing.rating_avg, listing.rating_count)
            if prior is not None
            else listing.rating_avg
        )
        return Candidate(
            id=key,
            total=offer.quote.total,
            bookable=offer.quote.status is QuoteStatus.BOOKABLE,
            max_capacity=listing.max_capacity,
            bedrooms=listing.bedrooms,
            rating=rating,
            features=features,
            drive_minutes=geo.drive_minutes,
            contradicted_claims=contradicted,
        )


def _requirements(intent: SearchIntent, dates: ResolvedDates) -> Requirements:
    budget = intent.budget
    return Requirements(
        nights=dates.window.night_count,
        guests=intent.guests,
        bedrooms_min=intent.bedrooms_min,
        budget_toman=budget.max_toman if budget else None,
        budget_basis=BudgetBasis(budget.basis) if budget else BudgetBasis.UNKNOWN,
        features=tuple(Feature(f) for f in intent.features),
        max_drive_minutes=intent.max_drive.minutes if intent.max_drive else None,
    )
