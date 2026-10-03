"""Listing-level read API (ROADMAP M7, built ahead of entity resolution).

Every number and claim leaves with its provenance (ADR-0007): the DTOs make the field required,
so a response without it cannot be built. Villa-level endpoints (several listings of one villa)
come with M5's canonical villas; prices stay per listing either way (product rule 3).
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from villasanj.catalog.domain.listing import CalendarObservation, Listing, ListingId
from villasanj.catalog.domain.review import ListingReview
from villasanj.discovery.application.routing import DriveTime, Origin
from villasanj.enrichment.application.coast import CoastDistance
from villasanj.enrichment.application.places import PlaceDistance
from villasanj.enrichment.application.review_summary import CitedPoint
from villasanj.enrichment.application.truth import (
    DistanceClaimCheck,
    FeatureClaimCheck,
    ListingTruth,
)
from villasanj.enrichment.domain.distance_claims import Assessment, ClaimTarget, Verdict
from villasanj.enrichment.domain.features import (
    NEAR_SEA_M,
    Agreement,
    FeatureEvidence,
    Polarity,
)
from villasanj.enrichment.domain.photo_tags import MIN_PRECISION
from villasanj.enrichment.domain.places import CENTRE_EXTENT_M, COMPLETE, PlaceKind
from villasanj.entrypoints.container import Container
from villasanj.pricing.domain.offer import Offer
from villasanj.pricing.domain.quote import NightCharge, StayRequest
from villasanj.shared.application.errors import ConfigurationError
from villasanj.shared.application.jobs import JobStatus
from villasanj.shared.domain.errors import DomainError
from villasanj.shared.domain.fa_format import fa_int, fa_metres, fa_metres_range, fa_minutes_range
from villasanj.shared.domain.money import MoneyRange
from villasanj.shared.domain.persian_text import ZWNJ, to_persian_digits
from villasanj.shared.domain.provenance import Provenance, ProvenanceMethod
from villasanj.shared.domain.stay import DateRange, GuestCount
from villasanj.shared.infrastructure.scenarios import load_scenarios

MAX_CALENDAR_DAYS = 120
SUMMARY_BUDGET_USD = Decimal("0.02")

router = APIRouter(prefix="/listings", tags=["listings"])
scenarios_router = APIRouter(tags=["scenarios"])


class SourceOut(BaseModel):
    platform: str
    url: str


class ProvenanceOut(BaseModel):
    method: Literal["observed", "derived", "llm_extracted", "human"]
    observed_at: datetime
    oldest_input_at: datetime  # the age of a value is the age of its oldest input
    source: SourceOut | None
    snapshot_id: str | None
    inputs: int  # values this one was derived from
    note: str | None = None  # how a derived value was made (Persian, shown on the source card)

    @classmethod
    def of(cls, provenance: Provenance, note: str | None = None) -> ProvenanceOut:
        source = provenance.source
        return cls(
            method=provenance.method.value,
            observed_at=provenance.observed_at,
            oldest_input_at=provenance.oldest_observation,
            source=SourceOut(platform=source.platform, url=source.url) if source else None,
            snapshot_id=provenance.snapshot_id,
            inputs=len(provenance.derived_from),
            note=note,
        )


class MoneyOut(BaseModel):
    """Rial is exact; toman is for display. ``high`` null means "at least ``low``"."""

    low_rial: int
    high_rial: int | None
    low_toman: int
    high_toman: int | None

    @classmethod
    def of(cls, amount: MoneyRange) -> MoneyOut:
        high = amount.high
        return cls(
            low_rial=amount.low.amount_rial,
            high_rial=high.amount_rial if high else None,
            low_toman=int(amount.low.toman),
            high_toman=int(high.toman) if high else None,
        )


class LocationOut(BaseModel):
    lat: float
    lon: float
    radius_m: int | None  # the published point may be up to this far from the villa


class ListingOut(BaseModel):
    id: str
    platform: str
    platform_name: str
    url: str
    title: str
    description: str | None
    property_type: str | None
    city: str | None
    locality: str | None
    location: LocationOut | None
    bedrooms: int | None
    bathrooms: int | None
    area_m2: int | None
    base_capacity: int | None
    max_capacity: int | None
    rating: float | None
    rating_count: int | None
    photos: list[str]
    provenance: ProvenanceOut


class NightOut(BaseModel):
    night: date
    price: MoneyOut
    price_provenance: ProvenanceOut
    extra_guests: int
    extra_guest_price: MoneyOut
    extra_guest_provenance: ProvenanceOut


class OfferOut(BaseModel):
    listing_id: str
    check_in: date
    check_out: date
    guests: int
    status: str
    kind: Literal["exact", "range", "open"] | None
    total: MoneyOut | None
    per_person: MoneyOut | None  # the total shared by ``guests``, rounded outwards (group mode)
    caveats: list[str]
    age_hours: float
    stale: bool
    provenance: ProvenanceOut
    nights: list[NightOut]


class CalendarNightOut(BaseModel):
    night: date
    availability: str
    price: MoneyOut | None
    extra_guest_price: MoneyOut | None
    min_nights: int | None
    is_holiday: bool | None
    provenance: ProvenanceOut


class ReviewOut(BaseModel):
    id: str
    rating: float | None
    text: str | None
    stayed_on: date | None
    stayed_precision: Literal["day", "month"] | None
    host_replied: bool
    provenance: ProvenanceOut


class GeoRangeOut(BaseModel):
    """A measured quantity over the listing's blur circle (ADR-0013)."""

    low: float
    high: float
    text: str  # Persian, widened outwards to round values
    radius_assumed: bool  # the platform publishes no blur radius: 500 m was assumed
    provenance: ProvenanceOut


class GeoOut(BaseModel):
    coast_m: GeoRangeOut | None  # straight-line distance to the coastline
    drive_s: GeoRangeOut | None  # free-flow drive time from ``origin``
    origin: str | None


def _map_provenance(listing: Listing, computed: datetime, what: str, dataset: str) -> ProvenanceOut:
    derived = Provenance(ProvenanceMethod.DERIVED, computed, derived_from=(listing.provenance,))
    return ProvenanceOut.of(
        derived,
        f"{what}، از نقشه{ZWNJ}ی OpenStreetMap ({dataset}) و نقطه{ZWNJ}ی منتشرشده{ZWNJ}ی آگهی",
    )


def geo_out(
    listing: Listing, coast: CoastDistance | None, drive: DriveTime | None, origin: Origin
) -> GeoOut:
    def provenance(computed: datetime, what: str, dataset: str) -> ProvenanceOut:
        return _map_provenance(listing, computed, what, dataset)

    return GeoOut(
        coast_m=GeoRangeOut(
            low=coast.low_m,
            high=coast.high_m,
            text=f"{fa_metres_range(coast.low_m, coast.high_m)} تا ساحل در خط مستقیم",
            radius_assumed=coast.blur.assumed,
            provenance=provenance(coast.computed_at, "فاصله تا خط ساحل", coast.dataset),
        )
        if coast
        else None,
        drive_s=GeoRangeOut(
            low=drive.low_s,
            high=drive.high_s,
            text=f"{fa_minutes_range(drive.low_s, drive.high_s)} از {origin.name_fa}، بدون ترافیک",
            radius_assumed=drive.blur.assumed,
            provenance=provenance(drive.computed_at, "مسیر بدون ترافیک (OSRM)", drive.dataset),
        )
        if drive and drive.low_s is not None and drive.high_s is not None
        else None,
        origin=origin.name_fa,
    )


ClaimVerdict = Literal[
    "supported",  # independent evidence (the map) agrees
    "consistent",  # the listing's own amenity list says the same (the host's word twice)
    "not_confirmed",  # «تأیید نشد»
    "inconsistent",  # the listing's own amenity list says the opposite
    "contradicted",  # even the best case of the evidence cannot reach the claim
    "shared",  # a facility of the complex: says nothing about the villa
    "not_checked",  # no evidence for this kind of claim yet, or wording not understood
]
_MODE_FA = {"walk": "پیاده", "car": "با ماشین", "unknown": ""}


class DistanceClaimOut(BaseModel):
    text: str  # as published, digits shown in Persian
    target: str
    verdict: ClaimVerdict
    evidence: str  # built by code from measured values
    radius_assumed: bool
    provenance: ProvenanceOut  # the listing page that published the claim
    evidence_provenance: ProvenanceOut | None


class FeatureClaimOut(BaseModel):
    feature: str
    span: str  # verbatim from the description
    polarity: Literal["has", "has_not"]
    verdict: ClaimVerdict
    evidence: str
    provenance: ProvenanceOut
    evidence_provenance: ProvenanceOut | None


class ClaimsOut(BaseModel):
    distances: list[DistanceClaimOut]
    features: list[FeatureClaimOut]


def _measured(coast: CoastDistance) -> str:
    return f"نقشه: {fa_metres_range(coast.low_m, coast.high_m)} تا ساحل در خط مستقیم"


_PLACE_FA = {
    PlaceKind.SUPERMARKET: "سوپرمارکت",
    PlaceKind.BAKERY: "نانوایی",
    PlaceKind.RESTAURANT: "رستوران",
    PlaceKind.MEDICAL: "مرکز درمانی",
    PlaceKind.CITY_CENTER: "مرکز شهر",
    PlaceKind.FOREST: "جنگل",
    PlaceKind.SHOPPING: "مرکز خرید",
}


def _place_measured(place: PlaceDistance) -> str:
    distance = f"{fa_metres_range(place.low_m, place.high_m)} در خط مستقیم"
    if place.kind is PlaceKind.CITY_CENTER:
        name = place.nearest_name or "نزدیک" + f"{ZWNJ}ترین شهر"
        return (
            f"نقشه: نقطه{ZWNJ}ی مرکز {name} {distance} (تا {fa_metres(CENTRE_EXTENT_M)} "
            f"دورتر از این نقطه هم مرکز شهر حساب شده)"
        )
    return f"نقشه: نزدیک{ZWNJ}ترین {_PLACE_FA[place.kind]} ثبت{ZWNJ}شده در OpenStreetMap {distance}"


def _judged(
    assessment: Assessment, measured: str, *, partial: bool, kind_fa: str
) -> tuple[ClaimVerdict, str]:
    claim_high = assessment.claimed_m[1]
    if assessment.verdict is Verdict.SUPPORTED:
        return "supported", f"{measured}؛ از همه{ZWNJ}ی محدوده{ZWNJ}ی مکان آگهی در حد ادعاست."
    if assessment.verdict is Verdict.CONTRADICTED and claim_high is not None:
        return "contradicted", (
            f"{measured}، اما این ادعا حتی با سخاوتمندانه{ZWNJ}ترین برداشت "
            f"حداکثر {fa_metres(claim_high)} است."
        )
    if partial:
        return "not_confirmed", (
            f"{measured}. نقشه همه{ZWNJ}ی {kind_fa}{ZWNJ}ها را ندارد، پس دورتر بودن "
            f"نزدیک{ZWNJ}ترین مورد ثبت{ZWNJ}شده ادعا را رد نمی{ZWNJ}کند."
        )
    return "not_confirmed", f"{measured}؛ با این شواهد نمی{ZWNJ}شود گفت درست است یا نه."


def _distance_out(
    listing: Listing, check: DistanceClaimCheck, coast: CoastDistance | None
) -> DistanceClaimOut:
    raw, claim, assessment, place = check.raw, check.claim, check.assessment, check.place
    mode = _MODE_FA[raw.mode.value]
    text = f"{raw.target_fa}: {to_persian_digits(raw.value_text)}" + (f" {mode}" if mode else "")
    verdict: ClaimVerdict = "not_checked"
    evidence_provenance = None
    if claim is None:
        evidence = "این عبارت را نتوانستیم به فاصله تبدیل کنیم."
    elif assessment is not None and place is not None:
        kind_fa = _PLACE_FA[place.kind]
        evidence_provenance = _map_provenance(
            listing, place.computed_at, f"فاصله تا نزدیک{ZWNJ}ترین {kind_fa}", place.dataset
        )
        verdict, evidence = _judged(
            assessment, _place_measured(place), partial=place.kind not in COMPLETE, kind_fa=kind_fa
        )
    elif assessment is not None and coast is not None:
        evidence_provenance = _map_provenance(
            listing, coast.computed_at, "فاصله تا خط ساحل", coast.dataset
        )
        verdict, evidence = _judged(assessment, _measured(coast), partial=False, kind_fa="")
    elif claim.target is ClaimTarget.SEA:
        evidence = f"فاصله{ZWNJ}ی این آگهی تا ساحل اندازه{ZWNJ}گیری نشده است."
    else:
        evidence = f"برای این مقصد هنوز داده{ZWNJ}ی نقشه نداریم."
    return DistanceClaimOut(
        text=text,
        target=claim.target.value if claim else ClaimTarget.OTHER.value,
        verdict=verdict,
        evidence=evidence,
        radius_assumed=check.radius_assumed,
        provenance=ProvenanceOut.of(
            listing.provenance, f"از بخش فاصله{ZWNJ}ها در صفحه{ZWNJ}ی آگهی"
        ),
        evidence_provenance=evidence_provenance,
    )


def _claim_provenance(listing: Listing, by_llm: bool) -> ProvenanceOut:
    if not by_llm:
        return ProvenanceOut.of(listing.provenance, "از متن توضیحات آگهی")
    read = Provenance(
        ProvenanceMethod.LLM_EXTRACTED,
        listing.provenance.observed_at,
        derived_from=(listing.provenance,),
    )
    return ProvenanceOut.of(
        read,
        f"از متن توضیحات آگهی، خوانده{ZWNJ}شده با مدل زبانی؛ عبارت عیناً در متن هست",
    )


def _feature_out(
    listing: Listing, check: FeatureClaimCheck, coast: CoastDistance | None
) -> FeatureClaimOut:
    claim, evidence_provenance = check.claim, None
    verdict: ClaimVerdict
    if claim.shared:
        verdict = "shared"
        evidence = f"امکانی مشاع است؛ درباره{ZWNJ}ی خود ویلا چیزی نمی{ZWNJ}گوید."
    elif check.map_evidence is not None and coast is not None:
        evidence_provenance = _map_provenance(
            listing, coast.computed_at, "فاصله تا خط ساحل", coast.dataset
        )
        if check.map_evidence is FeatureEvidence.MEASURED:
            verdict = "supported"
            evidence = f"{_measured(coast)}؛ همه{ZWNJ}ی محدوده کمتر از {fa_metres(NEAR_SEA_M)} است."
        else:  # a vague word: the map can support it, never contradict it
            verdict = "not_confirmed"
            evidence = (
                f"{_measured(coast)}. «نزدیک» اندازه{ZWNJ}ی مشخصی ندارد، "
                f"پس این را رد نمی{ZWNJ}کنیم."
            )
    elif check.photo_seen and claim.polarity is Polarity.HAS:
        verdict = "supported"
        evidence = f"در عکس{ZWNJ}های همین آگهی دیده می{ZWNJ}شود (تشخیص خودکار تصویر)"
        if check.agreement is Agreement.AMENITIES_DISAGREE:
            evidence += "؛ ولی فهرست امکانات آگهی آن را ندارد"
        evidence += "."
        derived = Provenance(
            ProvenanceMethod.DERIVED,
            listing.provenance.observed_at,
            derived_from=(listing.provenance,),
        )
        evidence_provenance = ProvenanceOut.of(
            derived,
            f"برچسب خودکار عکس{ZWNJ}ها (SigLIP 2)؛ آستانه{ZWNJ}ی هر برچسب از برچسب{ZWNJ}های "
            f"انسانی عکس{ZWNJ}ها، با دقت دست{ZWNJ}کم {fa_int(round(MIN_PRECISION * 100))}٪",
        )
    elif check.agreement is Agreement.AGREES:
        verdict = "consistent"
        evidence = f"فهرست امکانات همین آگهی هم همین را می{ZWNJ}گوید؛ هر دو گفته{ZWNJ}ی میزبان است."
    elif check.agreement is Agreement.AMENITIES_DISAGREE:
        verdict = "inconsistent"
        evidence = (
            "فهرست امکانات همین آگهی آن را ندارد."
            if claim.polarity is Polarity.HAS
            else "فهرست امکانات همین آگهی آن را دارد."
        )
    else:
        verdict = "not_confirmed"
        evidence = f"فهرست امکانات آگهی چیزی درباره{ZWNJ}اش نمی{ZWNJ}گوید و شاهد دیگری نداریم."
    return FeatureClaimOut(
        feature=claim.feature.value,
        span=claim.span,
        polarity="has" if claim.polarity is Polarity.HAS else "has_not",
        verdict=verdict,
        evidence=evidence,
        provenance=_claim_provenance(listing, claim.by_llm),
        evidence_provenance=evidence_provenance,
    )


def claims_out(listing: Listing, truth: ListingTruth) -> ClaimsOut:
    return ClaimsOut(
        distances=[_distance_out(listing, c, truth.coast) for c in truth.distances],
        features=[_feature_out(listing, c, truth.coast) for c in truth.features],
    )


class ScenarioOut(BaseModel):
    slug: str
    name: str
    check_in: date
    check_out: date
    guests: list[int]


def _container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


async def _listing(container: Container, platform: str, external_id: str) -> Listing:
    found = await container.listings.get(ListingId(platform, external_id))
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "listing not found")
    return found


def _listing_out(container: Container, listing: Listing) -> ListingOut:
    adapter = container.crawl.adapters.get(listing.id.platform)
    location = listing.location
    return ListingOut(
        id=str(listing.id),
        platform=listing.id.platform,
        platform_name=adapter.profile.display_name if adapter else listing.id.platform,
        url=listing.url,
        title=listing.title_norm,
        description=listing.description_norm,
        property_type=listing.property_type,
        city=listing.city_fa,
        locality=listing.locality_fa,
        location=LocationOut(
            lat=location.point.lat, lon=location.point.lon, radius_m=location.radius_m
        )
        if location
        else None,
        bedrooms=listing.bedrooms,
        bathrooms=listing.bathrooms,
        area_m2=listing.area_m2,
        base_capacity=listing.base_capacity,
        max_capacity=listing.max_capacity,
        rating=listing.rating_avg,
        rating_count=listing.rating_count,
        photos=list(listing.photos),
        provenance=ProvenanceOut.of(listing.provenance),
    )


def _night_out(charge: NightCharge) -> NightOut:
    return NightOut(
        night=charge.night,
        price=MoneyOut.of(charge.price),
        price_provenance=ProvenanceOut.of(charge.price_provenance),
        extra_guests=charge.extra_guests,
        extra_guest_price=MoneyOut.of(charge.extra_guest_price),
        extra_guest_provenance=ProvenanceOut.of(charge.extra_guest_provenance),
    )


def _offer_out(offer: Offer) -> OfferOut:
    quote = offer.quote
    return OfferOut(
        listing_id=str(quote.listing_id),
        check_in=quote.request.stay.check_in,
        check_out=quote.request.stay.check_out,
        guests=quote.request.guests.value,
        status=quote.status.value,
        kind=quote.kind.value if quote.kind else None,
        total=MoneyOut.of(quote.total) if quote.total else None,
        per_person=MoneyOut.of(quote.total.shared_by(quote.request.guests.value))
        if quote.total
        else None,
        caveats=sorted(c.value for c in quote.caveats),
        age_hours=round(offer.age / timedelta(hours=1), 2),
        stale=offer.stale,
        provenance=ProvenanceOut.of(quote.provenance),
        nights=[_night_out(n) for n in quote.nights],
    )


def _calendar_out(listing: Listing, observation: CalendarObservation) -> CalendarNightOut:
    price, extra = observation.nightly_price, observation.extra_guest_price
    return CalendarNightOut(
        night=observation.night,
        availability=observation.availability.value,
        price=MoneyOut.of(MoneyRange.exact(price)) if price else None,
        extra_guest_price=MoneyOut.of(MoneyRange.exact(extra)) if extra else None,
        min_nights=observation.min_nights,
        is_holiday=observation.is_holiday,
        provenance=ProvenanceOut.of(
            Provenance(
                listing.provenance.method,
                observation.observed_at,
                listing.provenance.source,
                observation.snapshot_id,
            )
        ),
    )


def _review_out(review: ListingReview) -> ReviewOut:
    return ReviewOut(
        id=review.review_id,
        rating=review.rating,
        text=review.text,
        stayed_on=review.stayed_on,
        stayed_precision=review.stayed_precision.value if review.stayed_precision else None,
        host_replied=review.host_replied,
        provenance=ProvenanceOut.of(review.provenance),
    )


class ListingRefOut(BaseModel):
    platform: str
    external_id: str
    title: str | None


MAX_SAMPLE = 200


@router.get("/sample")
async def sample_listings(
    request: Request,
    n: Annotated[int, Query(ge=1, le=MAX_SAMPLE)] = 50,
    seed: str = "7",
) -> list[ListingRefOut]:
    """A deterministic sample across platforms (the same ``seed`` gives the same listings), for
    smoke tests and for reviewers who want to browse."""
    container = _container(request)
    every = [
        listing
        for platform in sorted(container.crawl.adapters)
        for listing in await container.listings.listings(platform)
    ]
    every.sort(key=lambda x: hashlib.sha256(f"{seed}:{x.id}".encode()).hexdigest())
    return [
        ListingRefOut(platform=x.id.platform, external_id=x.id.external_id, title=x.title_norm)
        for x in every[:n]
    ]


@router.get("/{platform}/{external_id}")
async def get_listing(platform: str, external_id: str, request: Request) -> ListingOut:
    container = _container(request)
    return _listing_out(container, await _listing(container, platform, external_id))


@router.get("/{platform}/{external_id}/offer")
async def get_offer(
    platform: str,
    external_id: str,
    request: Request,
    check_in: date,
    check_out: date,
    guests: Annotated[int, Query(ge=1, le=50)],
) -> OfferOut:
    """The listing's own all-in offer for this stay and group (never merged with others)."""
    try:
        stay_request = StayRequest(DateRange(check_in, check_out), GuestCount(guests))
    except DomainError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    offer = await _container(request).offers().offer(ListingId(platform, external_id), stay_request)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "listing not found")
    return _offer_out(offer)


@router.get("/{platform}/{external_id}/calendar")
async def get_calendar(
    platform: str, external_id: str, request: Request, start: date, end: date
) -> list[CalendarNightOut]:
    """The newest observation of each night in [start, end) — an observation, not a state."""
    if not start < end or (end - start).days > MAX_CALENDAR_DAYS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"need start < end and at most {MAX_CALENDAR_DAYS} days",
        )
    container = _container(request)
    listing = await _listing(container, platform, external_id)
    newest: dict[date, CalendarObservation] = {}
    for observation in await container.listings.calendar(listing.id, DateRange(start, end)):
        current = newest.get(observation.night)
        if current is None or observation.observed_at > current.observed_at:
            newest[observation.night] = observation
    return [_calendar_out(listing, newest[night]) for night in sorted(newest)]


@router.get("/{platform}/{external_id}/reviews")
async def get_reviews(platform: str, external_id: str, request: Request) -> list[ReviewOut]:
    """The reviews the listing page showed (most recent stays first); names are not stored."""
    container = _container(request)
    listing = await _listing(container, platform, external_id)
    return [_review_out(r) for r in await container.listings.reviews(listing.id)]


@router.get("/{platform}/{external_id}/geo")
async def get_geo(platform: str, external_id: str, request: Request) -> GeoOut:
    """Distance to the coast and free-flow drive time, each a range over the blur circle."""
    container = _container(request)
    listing = await _listing(container, platform, external_id)
    origin = container.routing_origin()
    coast = await container.coast_store().get(listing.id)
    drive = await container.drive_store().get(listing.id, origin.slug)
    return geo_out(listing, coast, drive, origin)


@router.get("/{platform}/{external_id}/claims")
async def get_claims(platform: str, external_id: str, request: Request) -> ClaimsOut:
    """The listing's own claims, each beside its evidence; what has none yet says so."""
    container = _container(request)
    listing = await _listing(container, platform, external_id)
    return claims_out(listing, await container.listing_claims().run(listing))


class SummaryPointOut(BaseModel):
    text: str  # verified: no digits, money words or measurable comparatives (ADR-0007)
    review_ids: list[str]
    single_opinion: bool  # decided from the citations, never by the model


class ReviewSummaryOut(BaseModel):
    pros: list[SummaryPointOut]
    cons: list[SummaryPointOut]
    reviews_given: int
    source: Literal["llm"]


@router.get("/{platform}/{external_id}/review-summary")
async def get_review_summary(
    platform: str, external_id: str, request: Request
) -> ReviewSummaryOut | None:
    """Pros and cons that cite their reviews (one cached LLM call); null with too few reviews."""
    container = _container(request)
    listing = await _listing(container, platform, external_id)
    ctx = await container.jobs.start("review_summary", SUMMARY_BUDGET_USD, {})
    status_ = JobStatus.FAILED
    try:
        summary = await container.review_summaries().for_listing(listing.id, ctx)
        status_ = JobStatus.SUCCEEDED
    finally:
        await container.jobs.finish(ctx.job_id, status_)
    if summary is None:
        return None

    def points(items: tuple[CitedPoint, ...]) -> list[SummaryPointOut]:
        return [
            SummaryPointOut(
                text=p.text,
                review_ids=[r.review_id for r in p.reviews],
                single_opinion=p.single_opinion,
            )
            for p in items
        ]

    return ReviewSummaryOut(
        pros=points(summary.pros),
        cons=points(summary.cons),
        reviews_given=summary.reviews_given,
        source="llm",
    )


@scenarios_router.get("/scenarios")
async def get_scenarios(request: Request) -> list[ScenarioOut]:
    """The stay scenarios the catalog is captured for (config/scenarios.toml)."""
    try:
        scenarios = load_scenarios(_container(request).settings.scenarios_path)
    except ConfigurationError as error:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(error)) from None
    return [
        ScenarioOut(
            slug=s.slug,
            name=s.name_fa,
            check_in=s.stay.check_in,
            check_out=s.stay.check_out,
            guests=[g.value for g in s.guests],
        )
        for s in scenarios
    ]
