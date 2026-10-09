"""Search API (ROADMAP M8/M10 groundwork, listing level until M5's canonical villas).

One request makes at most three LLM calls (query understanding, one retry if a rule broke, the
explanation; cached answers are free). Every number in the response carries provenance, and the
explanation comes as segments so the UI can link each filled slot to its source.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel, Field

from villasanj.catalog.domain.listing import Listing
from villasanj.discovery.application.explanation import ExplainChoice, Explanation, explain_first
from villasanj.discovery.application.routing import Origin
from villasanj.discovery.application.search import SearchResult
from villasanj.discovery.domain.area import InvalidArea, MapArea
from villasanj.discovery.domain.dates import describe_fa
from villasanj.discovery.domain.filters import FacetRow, SearchFilters
from villasanj.discovery.domain.ranking import WEIGHTS, Ranked
from villasanj.enrichment.domain.features import NEAR_SEA_M, Feature, FeatureEvidence
from villasanj.enrichment.domain.geo import UNKNOWN_RADIUS_M
from villasanj.enrichment.domain.places import CENTRE_EXTENT_M
from villasanj.entrypoints.api.listings import GeoOut, LocationOut, MoneyOut, ProvenanceOut, geo_out
from villasanj.entrypoints.container import Container
from villasanj.shared.application.jobs import JobStatus
from villasanj.shared.application.llm.types import JobContext
from villasanj.shared.domain.slots import SLOT

MAX_RESULTS = 20
CARD_PHOTOS = 5
SEARCH_BUDGET_USD = Decimal("0.02")

router = APIRouter(tags=["search"])


class FiltersIn(BaseModel):
    """The filter panel's choices (``discovery.domain.filters``); every field optional."""

    price_min: int | None = Field(default=None, ge=0)
    price_max: int | None = Field(default=None, ge=0)
    per_night: bool = False
    bedrooms_min: int | None = Field(default=None, ge=1, le=20)
    capacity_min: int | None = Field(default=None, ge=1, le=50)
    features: list[Feature] = Field(default_factory=list, max_length=8)
    property_types: list[str] = Field(default_factory=list, max_length=12)
    platforms: list[str] = Field(default_factory=list, max_length=4)
    multi_platform: bool = False
    instant: bool = False
    rating_min: float | None = Field(default=None, ge=0, le=5)
    coast_max_m: float | None = Field(default=None, ge=0)

    def domain(self) -> SearchFilters:
        return SearchFilters(
            price_min=self.price_min,
            price_max=self.price_max,
            per_night=self.per_night,
            bedrooms_min=self.bedrooms_min,
            capacity_min=self.capacity_min,
            features=frozenset(f.value for f in self.features),
            property_types=frozenset(self.property_types),
            platforms=frozenset(self.platforms),
            multi_platform=self.multi_platform,
            instant=self.instant,
            rating_min=self.rating_min,
            coast_max_m=self.coast_max_m,
        )


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    # Constraints the user removed: "dates", "nights", "guests", "bedrooms", "budget", "drive",
    # "place:<name>", "feature:<code>" (editable chips). Removing never adds a number.
    drop: list[str] = Field(default_factory=list, max_length=12)
    # False: results only; the page then streams ``POST /search/explanation`` in after them, so
    # the explanation's latency (one LLM call, ADR-0005) never holds the results back.
    explain: bool = True
    # The map's visible bounds [west, south, east, north] when the user searched "this area".
    area: list[float] | None = Field(default=None, min_length=4, max_length=4)
    filters: FiltersIn | None = None

    def map_area(self) -> MapArea | None:
        if self.area is None:
            return None
        try:
            return MapArea(*self.area)
        except InvalidArea as error:
            raise HTTPException(http_status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None


class DatesOut(BaseModel):
    check_in: str
    check_out: str
    text: str  # Persian, e.g. «پنجشنبه ۱۶ مهر تا شنبه ۱۸ مهر»
    flexible: bool
    caveats: list[str]


class ContributionOut(BaseModel):
    component: str
    normalized: float
    weight: float
    points: float


class AlsoOnOut(BaseModel):
    """The same villa on another platform: its own offer, never merged (rule 3)."""

    listing_id: str
    platform: str
    platform_name: str
    external_id: str
    status: str
    total: MoneyOut | None
    total_provenance: ProvenanceOut
    stale: bool  # the offer rests on an observation older than the stale limit (24 h)
    area_m2: int | None


class ConfirmedOut(BaseModel):
    """A requested feature with independent or listed evidence (never the description alone)."""

    feature: str
    source: Literal["photo", "map", "amenities"]


class ResultOut(BaseModel):
    listing_id: str
    platform: str
    external_id: str
    platform_name: str
    title: str
    photo: str | None
    photos: list[str]  # the listing's first photos (the card's carousel)
    location: LocationOut | None  # the published point and blur radius, never more precise
    bedrooms: int | None
    max_capacity: int | None
    area_m2: int | None
    rating: float | None  # the platform's own average
    rating_count: int | None
    stale: bool
    confirmed: list[ConfirmedOut]
    total: MoneyOut | None
    per_person: MoneyOut | None  # the total shared by the group, rounded outwards
    total_provenance: ProvenanceOut
    price_per_person_night_toman: float | None
    confirmed_features: int
    score: float
    contributions: list[ContributionOut]
    cautions: list[str]
    geo: GeoOut | None
    mentions: list[str]  # the query's unhandled wishes this listing's own text mentions
    villa_id: str | None  # set when the villa is on more than one platform
    also_on: list[AlsoOnOut]
    listing_provenance: ProvenanceOut  # the listing page those words were read from


class SegmentOut(BaseModel):
    text: str
    slot: str | None  # the fact or comparison this text fills, if any
    provenance: ProvenanceOut | None


class ExplanationOut(BaseModel):
    source: Literal["llm", "template"]
    text: str
    segments: list[SegmentOut]


class SearchOut(BaseModel):
    query: str
    intent: dict[str, object]
    dates: DatesOut | None
    missing: list[str]
    places: list[str]
    unresolved_places: list[str]
    unhandled: list[str]  # wishes the search cannot measure: said back, never used to rank
    budget_readings: dict[str, int] | None
    excluded: dict[str, int]
    total_results: int
    drive_coverage: dict[str, int]  # free-flow hours from the origin -> results with that limit
    results: list[ResultOut]
    explanation: ExplanationOut | None


def _result_out(
    container: Container, ranked: Ranked, result: SearchResult, origin: Origin | None
) -> ResultOut:
    key = ranked.candidate.id
    listing, offer = result.listings[key], result.offers[key]
    adapter = container.crawl.adapters.get(listing.id.platform)
    total = offer.quote.total
    return ResultOut(
        listing_id=key,
        platform=listing.id.platform,
        external_id=listing.id.external_id,
        platform_name=adapter.profile.display_name if adapter else listing.id.platform,
        title=listing.title_norm,
        photo=listing.photos[0] if listing.photos else None,
        photos=list(listing.photos[:CARD_PHOTOS]),
        location=_location(listing),
        bedrooms=listing.bedrooms,
        max_capacity=listing.max_capacity,
        area_m2=listing.area_m2,
        rating=listing.rating_avg,
        rating_count=listing.rating_count,
        stale=offer.stale,
        confirmed=_confirmed(ranked, result),
        total=MoneyOut.of(total) if total else None,
        per_person=MoneyOut.of(total.shared_by(offer.quote.request.guests.value))
        if total
        else None,
        total_provenance=ProvenanceOut.of(offer.quote.provenance),
        price_per_person_night_toman=ranked.price_per_person_night_toman,
        confirmed_features=ranked.confirmed,
        score=round(ranked.score, 4),
        contributions=[
            ContributionOut(
                component=c.component,
                normalized=round(c.normalized, 4),
                weight=c.weight,
                points=round(c.points, 4),
            )
            for c in ranked.contributions
        ],
        cautions=sorted(ranked.warnings),
        geo=_geo(result, key, origin),
        mentions=list(result.mentions.get(key, ())),
        villa_id=result.villa_of.get(key),
        also_on=[_also_on(container, result, other) for other in result.siblings.get(key, ())],
        listing_provenance=ProvenanceOut.of(listing.provenance),
    )


def _also_on(container: Container, result: SearchResult, key: str) -> AlsoOnOut:
    offer, listing = result.offers[key], result.listings[key]
    adapter = container.crawl.adapters.get(listing.id.platform)
    total = offer.quote.total
    return AlsoOnOut(
        listing_id=key,
        platform=listing.id.platform,
        platform_name=adapter.profile.display_name if adapter else listing.id.platform,
        external_id=listing.id.external_id,
        status=offer.quote.status.value,
        total=MoneyOut.of(total) if total else None,
        total_provenance=ProvenanceOut.of(offer.quote.provenance),
        stale=offer.stale,
        area_m2=listing.area_m2,
    )


_CONFIRMING: dict[FeatureEvidence, Literal["photo", "map", "amenities"]] = {
    FeatureEvidence.PHOTO: "photo",
    FeatureEvidence.MEASURED: "map",
    FeatureEvidence.LISTED: "amenities",
}


def _confirmed(ranked: Ranked, result: SearchResult) -> list[ConfirmedOut]:
    """The requested features this listing's evidence backs, strongest source first."""
    found = []
    for code in result.understanding.intent.features:
        evidence = ranked.candidate.features.get(Feature(code))
        if evidence in _CONFIRMING:
            found.append(ConfirmedOut(feature=code, source=_CONFIRMING[evidence]))
    order = {"photo": 0, "map": 1, "amenities": 2}
    return sorted(found, key=lambda c: order[c.source])


def _location(listing: Listing) -> LocationOut | None:
    where = listing.location
    if where is None:
        return None
    return LocationOut(lat=where.point.lat, lon=where.point.lon, radius_m=where.radius_m)


def _geo(result: SearchResult, key: str, origin: Origin | None) -> GeoOut | None:
    geo = result.geo.get(key)
    if geo is None or origin is None:
        return None
    return geo_out(result.listings[key], geo.coast, geo.drive, origin)


def _segments(explanation: Explanation) -> list[SegmentOut]:
    slots = explanation.slots
    segments: list[SegmentOut] = []
    position = 0
    for match in SLOT.finditer(explanation.slotted):
        if match.start() > position:
            segments.append(
                SegmentOut(
                    text=explanation.slotted[position : match.start()], slot=None, provenance=None
                )
            )
        slot = match.group(1)
        value = slots.facts.get(slot) or slots.comparisons[slot]
        segments.append(
            SegmentOut(text=value.text, slot=slot, provenance=ProvenanceOut.of(value.provenance))
        )
        position = match.end()
    if position < len(explanation.slotted):
        segments.append(SegmentOut(text=explanation.slotted[position:], slot=None, provenance=None))
    return segments


class RankingRulesOut(BaseModel):
    """The numbers the public "how we rank" page states, from the code that uses them."""

    weights: dict[str, float]  # score = sum of weight x normalized component (0..1 in a search)
    near_sea_m: float  # «نزدیک دریا» from the map (A17)
    centre_extent_m: float  # a town centre is an area this wide around its point (A20)
    unknown_radius_m: int  # assumed blur when a platform publishes none (A14)
    origin: str | None  # where drive times start


@router.get("/search/ranking")
async def ranking_rules(request: Request) -> RankingRulesOut:
    container: Container = request.app.state.container
    return RankingRulesOut(
        weights=dict(WEIGHTS),
        near_sea_m=NEAR_SEA_M,
        centre_extent_m=CENTRE_EXTENT_M,
        unknown_radius_m=UNKNOWN_RADIUS_M,
        origin=container.routing_origin().name_fa,
    )


@router.post("/search")
async def search(body: SearchIn, request: Request) -> SearchOut:
    """A Persian query to ranked listings with reasons, and why the first one fits."""
    container: Container = request.app.state.container
    ctx = await container.jobs.start("search", SEARCH_BUDGET_USD, {})
    status = JobStatus.FAILED
    try:
        result = await container.search().run(
            body.query,
            ctx,
            body.drop,
            body.map_area(),
            body.filters.domain() if body.filters else None,
        )
        why = await _explain(container, result, ctx) if body.explain else None
        status = JobStatus.SUCCEEDED
    finally:
        await container.jobs.finish(ctx.job_id, status)
    ranking = result.ranking
    dates = result.dates
    origin = container.routing_origin() if result.geo else None
    return SearchOut(
        query=body.query,
        intent=result.understanding.intent.model_dump(exclude_none=True),
        dates=DatesOut(
            check_in=dates.window.check_in.isoformat(),
            check_out=dates.window.check_out.isoformat(),
            text=describe_fa(dates.window),
            flexible=dates.flexible,
            caveats=sorted(dates.caveats),
        )
        if dates
        else None,
        missing=list(result.missing),
        places=[p.name_fa for p in result.places],
        unresolved_places=list(result.unresolved_places),
        unhandled=list(result.understanding.intent.unhandled),
        budget_readings=dict(ranking.budget_readings)
        if ranking and ranking.budget_readings
        else None,
        excluded=dict(ranking.excluded) if ranking else {},
        total_results=len(ranking.results) if ranking else 0,
        drive_coverage={str(hours): count for hours, count in result.drive_coverage.items()},
        results=[_result_out(container, r, result, origin) for r in ranking.results[:MAX_RESULTS]]
        if ranking
        else [],
        explanation=_explanation_out(why),
    )


async def _explain(
    container: Container, result: SearchResult, ctx: JobContext
) -> Explanation | None:
    names = {p: a.profile.display_name for p, a in container.crawl.adapters.items()}
    return await explain_first(
        ExplainChoice(container.llm.client), result, names, container.clock.now(), ctx
    )


def _explanation_out(why: Explanation | None) -> ExplanationOut | None:
    if why is None:
        return None
    return ExplanationOut(source=why.source.value, text=why.rendered.text, segments=_segments(why))


@router.post("/search/explanation")
async def search_explanation(body: SearchIn, request: Request) -> ExplanationOut | None:
    """Why the first result fits, for a search already shown (the understanding is cached)."""
    container: Container = request.app.state.container
    ctx = await container.jobs.start("search_explanation", SEARCH_BUDGET_USD, {})
    status = JobStatus.FAILED
    try:
        result = await container.search().run(
            body.query,
            ctx,
            body.drop,
            body.map_area(),
            body.filters.domain() if body.filters else None,
        )
        why = await _explain(container, result, ctx)
        status = JobStatus.SUCCEEDED
    finally:
        await container.jobs.finish(ctx.job_id, status)
    return _explanation_out(why)


class FacetOut(BaseModel):
    listing: str
    villa: str
    platform: str
    multi_platform: bool
    total_toman: int | None
    nights: int
    bedrooms: int | None
    max_capacity: int | None
    property_type: str | None
    instant: bool | None
    rating: float | None
    coast_low_m: float | None
    features: list[str]

    @classmethod
    def of(cls, row: FacetRow) -> FacetOut:
        return cls(
            listing=row.listing,
            villa=row.villa,
            platform=row.platform,
            multi_platform=row.multi_platform,
            total_toman=row.total_toman,
            nights=row.nights,
            bedrooms=row.bedrooms,
            max_capacity=row.max_capacity,
            property_type=row.property_type,
            instant=row.instant,
            rating=row.rating,
            coast_low_m=round(row.coast_low_m, 1) if row.coast_low_m is not None else None,
            features=sorted(row.features),
        )


@router.post("/search/facets")
async def search_facets(body: SearchIn, request: Request) -> list[FacetOut]:
    """Every ranked listing of the query (inside the map area, before the filters), as the filter
    panel needs it for its live count and price histogram. The filters in the body are ignored."""
    container: Container = request.app.state.container
    ctx = await container.jobs.start("search_facets", SEARCH_BUDGET_USD, {})
    status = JobStatus.FAILED
    try:
        result = await container.search().run(body.query, ctx, body.drop, body.map_area())
        status = JobStatus.SUCCEEDED
    finally:
        await container.jobs.finish(ctx.job_id, status)
    return [FacetOut.of(row) for row in result.facets]
