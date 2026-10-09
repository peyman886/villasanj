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
from typing import Protocol

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.gazetteer import Gazetteer, Place
from villasanj.catalog.domain.listing import Listing, ListingId
from villasanj.catalog.domain.review import RatingPrior
from villasanj.discovery.application.dates import BuildHolidayCalendar
from villasanj.discovery.application.intent import SearchIntent, without
from villasanj.discovery.application.routing import DriveTime, DriveTimeStore, Origin
from villasanj.discovery.application.understanding import Understanding, UnderstandQuery
from villasanj.discovery.domain.area import MapArea
from villasanj.discovery.domain.dates import ResolvedDates, resolve
from villasanj.discovery.domain.filters import FacetRow, SearchFilters, passes
from villasanj.discovery.domain.ranking import (
    BudgetBasis,
    Candidate,
    Ranked,
    Ranking,
    Requirements,
    drive_coverage,
    rank,
)
from villasanj.enrichment.application.claim_extraction import ReadClaim, ReadClaimStore, as_read
from villasanj.enrichment.application.coast import CoastDistance, CoastDistanceStore
from villasanj.enrichment.application.features import AmenityMap
from villasanj.enrichment.application.photo_tags import PhotoFeatures
from villasanj.enrichment.application.places import PlaceDistanceStore
from villasanj.enrichment.application.truth import place_verdicts
from villasanj.enrichment.domain.distance_claims import Verdict
from villasanj.enrichment.domain.features import (
    Feature,
    FeatureEvidence,
    extract_claims,
    feature_evidence,
    near_sea_evidence,
    with_read_claims,
)
from villasanj.pricing.application.offers import OfferBook
from villasanj.pricing.domain.offer import Offer
from villasanj.pricing.domain.quote import QuoteStatus, StayRequest
from villasanj.shared.application.clock import Clock
from villasanj.shared.application.llm.types import JobContext
from villasanj.shared.domain.errors import DomainError
from villasanj.shared.domain.jalali import iran_today
from villasanj.shared.domain.persian_text import ZWNJ, normalize_persian
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
    # The query's unhandled wishes each result's own text mentions (the host's word, not checked)
    mentions: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    # Villas on more than one platform: a result's villa and its other listings with an offer
    # (one card per villa, each platform's own price; ranked by the villa's best listing).
    villa_of: Mapping[str, str] = field(default_factory=dict)
    siblings: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    # Every ranked listing (inside the map area, before the filters) as the filters see it.
    facets: tuple[FacetRow, ...] = ()


class VillaMembers(Protocol):
    async def current(self) -> dict[str, frozenset[ListingId]]:
        """Villa id -> its member listings."""
        ...


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
        photos: PhotoFeatures | None = None,
        read_claims: ReadClaimStore | None = None,
        villas: VillaMembers | None = None,
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
        self._photos = photos
        self._read_claims = read_claims
        self._villas = villas

    async def run(
        self,
        query: str,
        ctx: JobContext,
        drop: Sequence[str] = (),
        area: MapArea | None = None,
        filters: SearchFilters | None = None,
    ) -> SearchResult:
        """``drop``: constraints the user removed from the understood query (editable chips).
        ``area``: only villas whose published point is inside it (the map's «search this area»).
        ``filters``: the filter panel's choices; they narrow the ranked listings, never re-rank."""
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
            pictured = await self._photos.seen(platform) if self._photos else {}
            read = await self._read_claims.of_platform(platform) if self._read_claims else {}
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
                    self._candidate(
                        key,
                        listing,
                        offer,
                        prior,
                        intent,
                        geo,
                        contradicted,
                        pictured.get(listing.id, frozenset()),
                        read.get(listing.id, []),
                    )
                )
        wants = _requirements(intent, dates)
        ranking = rank(candidates, wants)
        villa_of, siblings = await self._villa_groups(offers)
        ranked = ranking.results
        if area is not None:
            ranked = tuple(
                r
                for r in ranked
                if (where := listings[r.candidate.id].location) is not None
                and area.contains(where.point)
            )
        nights = (dates.window.check_out - dates.window.check_in).days
        facets = tuple(
            _facet(r.candidate, listings[r.candidate.id], geos[r.candidate.id], villa_of, nights)
            for r in ranked
        )
        if filters is not None and not filters.empty:
            keep = {row.listing for row in facets if passes(row, filters)}
            ranked = tuple(r for r in ranked if r.candidate.id in keep)
        ranking = replace(ranking, results=_one_per_villa(ranked, villa_of))
        mentions = {
            key: found
            for key, listing in listings.items()
            if (found := mentioned(intent.unhandled, listing))
        }
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
            mentions,
            villa_of,
            {k: siblings[k] for r in ranking.results if (k := r.candidate.id) in siblings},
            facets,
        )

    async def _villa_groups(
        self, offers: Mapping[str, Offer]
    ) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
        """Each listing of a multi-platform villa -> its villa, and -> its villa's other
        listings that have an offer for this stay."""
        if self._villas is None:
            return {}, {}
        villa_of: dict[str, str] = {}
        siblings: dict[str, tuple[str, ...]] = {}
        for villa_id, members in (await self._villas.current()).items():
            if len(members) < 2:  # noqa: PLR2004 - a villa on one platform has nothing to group
                continue
            keys = sorted(str(m) for m in members)
            for key in keys:
                villa_of[key] = villa_id
                siblings[key] = tuple(k for k in keys if k != key and k in offers)
        return villa_of, siblings

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
        pictured: frozenset[Feature] = frozenset(),
        read: Sequence[ReadClaim] = (),
    ) -> Candidate:
        stated = self._amenities.features_of(listing)
        description = listing.description_norm or ""
        claims = with_read_claims(extract_claims(description), as_read(read), description)
        features = {
            feature: feature_evidence(
                stated.get(feature),
                [c for c in claims if c.feature is feature],
                photo_seen=feature in pictured,
            )
            for feature in Feature  # every feature: the requested ones rank, all of them filter
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


def _words(text: str) -> str:
    return " ".join(normalize_persian(text).replace(ZWNJ, " ").split())


def mentioned(wishes: Sequence[str], listing: Listing) -> tuple[str, ...]:
    """The wishes the listing's own title or description mentions, word for word."""
    text = f" {_words(f'{listing.title_norm or ""} {listing.description_norm or ""}')} "
    return tuple(w for w in wishes if f" {_words(w)} " in text)


def _one_per_villa(results: Sequence[Ranked], villa_of: Mapping[str, str]) -> tuple[Ranked, ...]:
    """The best-ranked listing of each villa (results are already in rank order)."""
    seen: set[str] = set()
    kept = []
    for result in results:
        villa = villa_of.get(result.candidate.id)
        if villa is not None:
            if villa in seen:
                continue
            seen.add(villa)
        kept.append(result)
    return tuple(kept)


_PRESENT = frozenset(
    {
        FeatureEvidence.LISTED,
        FeatureEvidence.MEASURED,
        FeatureEvidence.PHOTO,
        FeatureEvidence.DESCRIBED,
    }
)


def _facet(
    candidate: Candidate, listing: Listing, geo: Geo, villa_of: Mapping[str, str], nights: int
) -> FacetRow:
    key = candidate.id
    return FacetRow(
        listing=key,
        villa=villa_of.get(key, key),
        platform=listing.id.platform,
        multi_platform=key in villa_of,
        total_toman=int(candidate.total.low.toman) if candidate.total is not None else None,
        nights=nights,
        bedrooms=listing.bedrooms,
        max_capacity=listing.max_capacity,
        property_type=listing.property_type,
        instant=listing.instant_booking,
        rating=listing.rating_avg,
        coast_low_m=geo.coast.low_m if geo.coast is not None else None,
        features=frozenset(f.value for f, e in candidate.features.items() if e in _PRESENT),
    )
