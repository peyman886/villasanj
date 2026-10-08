"""Canonical villa read API (ROADMAP M7): one villa, its listings, where they disagree, each
listing's own offer (prices are never merged, product rule 3), the merged calendar with hidden
nights, and the reviews of every listing labelled by source. Location and amenity claims the
listings state differently are INCONSISTENT_ACROSS_PLATFORMS (M9): shown with each listing's own
words and source, never as which one is wrong.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel

from villasanj.catalog.domain.listing import Listing, ListingId
from villasanj.catalog.domain.review import ListingReview
from villasanj.discovery.domain.villa import conflicts, merge_calendars
from villasanj.enrichment.domain.consistency import VillaConsistency
from villasanj.entity_resolution.domain.clustering import CanonicalVilla
from villasanj.entrypoints.api.listings import (
    MAX_CALENDAR_DAYS,
    SUMMARY_BUDGET_USD,
    CalendarNightOut,
    ListingOut,
    OfferOut,
    ProvenanceOut,
    ReviewOut,
    ReviewSummaryOut,
    SummaryPointOut,
    _calendar_out,
    _claim_provenance,
    _listing_out,
    _offer_out,
    _review_out,
)
from villasanj.entrypoints.container import Container
from villasanj.pricing.domain.quote import StayRequest
from villasanj.shared.application.jobs import JobStatus
from villasanj.shared.domain.errors import DomainError
from villasanj.shared.domain.persian_text import ZWNJ, to_persian_digits
from villasanj.shared.domain.stay import DateRange, GuestCount

router = APIRouter(prefix="/villas", tags=["villas"])

HIDDEN_NIGHT_GAP = timedelta(hours=6)  # observations further apart are not compared (H3)
_MASK64 = (1 << 64) - 1  # hashes are stored as signed 64-bit integers


class ConflictOut(BaseModel):
    field: str
    values: dict[str, str | int]  # platform -> what it states


class StatementOut(BaseModel):
    platform: str
    says: Literal["has", "has_not"] | None  # a feature claim; None for a distance
    published: str | None  # a distance: the listing's claims as published, digits in Persian
    source: Literal["amenities", "description", "distances"]
    span: str | None  # the description's words, verbatim
    provenance: ProvenanceOut


class InconsistencyOut(BaseModel):
    kind: Literal["feature", "distance"]
    subject: str  # the feature or the distance target (slug)
    statements: list[StatementOut]


class GalleryPhotoOut(BaseModel):
    url: str
    platform: str
    phash: str | None  # 64-bit perceptual hash as 16 hex digits; None: not fingerprinted


class VillaOut(BaseModel):
    id: str
    members: list[ListingOut]  # at most one per platform
    gallery: list[GalleryPhotoOut]  # every member's photos in order, with the matcher's hashes
    conflicts: list[ConflictOut]
    inconsistencies: list[InconsistencyOut]  # location and amenity claims stated differently
    rating: float | None  # every platform's ratings together, weighted by their counts
    rating_count: int


class VillaNightOut(BaseModel):
    night: date
    by_platform: dict[str, CalendarNightOut]
    hidden: bool  # free on one platform, taken on another, observed < 6 h apart


class VillaReviewOut(ReviewOut):
    platform: str


def _container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


async def _villa(container: Container, villa_id: str) -> tuple[CanonicalVilla, list[Listing]]:
    villa = await container.villa_store().get(villa_id)
    if villa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "villa not found")
    members = [x for m in sorted(villa.members) if (x := await container.listings.get(m))]
    return villa, members


def _inconsistencies_out(found: VillaConsistency, members: list[Listing]) -> list[InconsistencyOut]:
    by_platform = {m.id.platform: m for m in members}
    out = []
    for f in found.features:
        statements = []
        for platform, said in sorted(f.by_platform.items()):
            listing = by_platform[platform]
            if said.from_amenities:
                source: Literal["amenities", "description"] = "amenities"
                provenance = ProvenanceOut.of(listing.provenance, "از فهرست امکانات آگهی")
            else:
                source = "description"
                provenance = _claim_provenance(listing, said.by_llm)
            statements.append(
                StatementOut(
                    platform=platform,
                    says="has" if said.says else "has_not",
                    published=None,
                    source=source,
                    span=said.span,
                    provenance=provenance,
                )
            )
        out.append(InconsistencyOut(kind="feature", subject=f.feature.value, statements=statements))
    for d in found.distances:
        statements = [
            StatementOut(
                platform=platform,
                says=None,
                published="، ".join(
                    f"{c.target_text}: {to_persian_digits(c.published)}" for c in claims
                ),
                source="distances",
                span=None,
                provenance=ProvenanceOut.of(
                    by_platform[platform].provenance,
                    f"از بخش فاصله{ZWNJ}ها در صفحه{ZWNJ}ی آگهی",
                ),
            )
            for platform, claims in sorted(d.by_platform.items())
        ]
        out.append(InconsistencyOut(kind="distance", subject=d.target.value, statements=statements))
    return out


def _combined_rating(members: list[Listing]) -> tuple[float | None, int]:
    rated = [(x.rating_avg, x.rating_count) for x in members if x.rating_avg and x.rating_count]
    count = sum(n for _, n in rated)
    if not count:
        return None, 0
    return round(sum(r * n for r, n in rated) / count, 2), count


class VillaSampleOut(BaseModel):
    villa_id: str


@router.get("/sample")
async def sample_villas(
    request: Request,
    n: Annotated[int, Query(ge=1, le=200)] = 50,
    seed: str = "7",
) -> list[VillaSampleOut]:
    """A deterministic sample of villas listed on more than one platform (smoke tests)."""
    ids = await _container(request).villa_store().multi_platform()
    ids.sort(key=lambda v: hashlib.sha256(f"{seed}:{v}".encode()).hexdigest())
    return [VillaSampleOut(villa_id=v) for v in ids[:n]]


@router.get("/{villa_id}")
async def get_villa(villa_id: str, request: Request) -> VillaOut:
    container = _container(request)
    villa, members = await _villa(container, villa_id)
    rating, count = _combined_rating(members)
    found = await container.villa_consistency().run(members)
    hashes = {
        p.url: p.fingerprint.phash
        for p in await container.catalog_photos().photos_of([m.id for m in members])
    }
    return VillaOut(
        id=villa.id,
        members=[_listing_out(container, x) for x in members],
        gallery=[
            GalleryPhotoOut(
                url=url,
                platform=m.id.platform,
                phash=f"{hashes[url] & _MASK64:016x}" if url in hashes else None,
            )
            for m in members
            for url in m.photos
        ],
        conflicts=[
            ConflictOut(
                field=c.field,
                values={k: v for k, v in c.values.items() if isinstance(v, str | int)},
            )
            for c in conflicts(members)
        ],
        inconsistencies=_inconsistencies_out(found, members),
        rating=rating,
        rating_count=count,
    )


@router.get("/{villa_id}/offers")
async def get_offers(
    villa_id: str,
    request: Request,
    check_in: date,
    check_out: date,
    guests: Annotated[int, Query(ge=1, le=50)],
) -> list[OfferOut]:
    """Each listing's own all-in offer for this stay and group, side by side."""
    try:
        stay = StayRequest(DateRange(check_in, check_out), GuestCount(guests))
    except DomainError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    container = _container(request)
    _, members = await _villa(container, villa_id)
    offers = []
    for member in members:
        offer = await container.offers().offer(member.id, stay)
        if offer is not None:
            offers.append(_offer_out(offer))
    return offers


@router.get("/{villa_id}/calendar")
async def get_calendar(
    villa_id: str, request: Request, start: date, end: date
) -> list[VillaNightOut]:
    if not start < end or (end - start).days > MAX_CALENDAR_DAYS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"need start < end and at most {MAX_CALENDAR_DAYS} days",
        )
    container = _container(request)
    _, members = await _villa(container, villa_id)
    window = DateRange(start, end)
    by_platform = {m.id.platform: await container.listings.calendar(m.id, window) for m in members}
    by_listing = {m.id.platform: m for m in members}
    return [
        VillaNightOut(
            night=night.night,
            by_platform={
                p: _calendar_out(by_listing[p], o) for p, o in sorted(night.by_platform.items())
            },
            hidden=night.hidden,
        )
        for night in merge_calendars(by_platform, HIDDEN_NIGHT_GAP)
    ]


async def _reviews(container: Container, members: list[Listing]) -> list[ListingReview]:
    """Every listing's reviews, most recent stays first."""
    reviews = [r for m in members for r in await container.listings.reviews(m.id)]
    reviews.sort(key=lambda r: (r.stayed_on or date.min, r.review_id), reverse=True)
    return reviews


def review_key(review: ListingReview) -> str:
    """A review's id across platforms (each platform numbers its own)."""
    return f"{review.listing_id.platform}:{review.review_id}"


@router.get("/{villa_id}/reviews")
async def get_reviews(villa_id: str, request: Request) -> list[VillaReviewOut]:
    """Every listing's reviews, most recent stays first, each with its platform."""
    container = _container(request)
    _, members = await _villa(container, villa_id)
    return [
        VillaReviewOut(**_review_out(r).model_dump(), platform=r.listing_id.platform)
        for r in await _reviews(container, members)
    ]


@router.get("/{villa_id}/review-summary")
async def get_review_summary(villa_id: str, request: Request) -> ReviewSummaryOut | None:
    """Pros and cons over every platform's reviews of the villa, each point citing its reviews
    as ``platform:review_id`` (one cached LLM call, verified like a listing's); null with too few
    reviews."""
    container = _container(request)
    _, members = await _villa(container, villa_id)
    reviews = await _reviews(container, members)
    ctx = await container.jobs.start("review_summary", SUMMARY_BUDGET_USD, {"villa": villa_id})
    status_ = JobStatus.FAILED
    try:
        summary = await container.review_summaries().summarize(reviews, ctx)
        status_ = JobStatus.SUCCEEDED
    finally:
        await container.jobs.finish(ctx.job_id, status_)
    if summary is None:
        return None
    return ReviewSummaryOut(
        pros=[
            SummaryPointOut(
                text=p.text,
                review_ids=[review_key(r) for r in p.reviews],
                single_opinion=p.single_opinion,
            )
            for p in summary.pros
        ],
        cons=[
            SummaryPointOut(
                text=p.text,
                review_ids=[review_key(r) for r in p.reviews],
                single_opinion=p.single_opinion,
            )
            for p in summary.cons
        ],
        reviews_given=summary.reviews_given,
        source="llm",
    )


class VillaRefOut(BaseModel):
    villa_id: str
    members: int


@router.get("/of/{platform}/{external_id}")
async def villa_of(platform: str, external_id: str, request: Request) -> VillaRefOut:
    """The villa a listing belongs to (every listing has one; members counts its listings)."""
    villa = await _container(request).villa_store().villa_of(ListingId(platform, external_id))
    if villa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no villa for this listing")
    return VillaRefOut(villa_id=villa.id, members=len(villa.members))


class PhotoPairOut(BaseModel):
    left_url: str
    right_url: str
    strong: bool  # near-identical; otherwise a close match (half weight in the score)


class JudgeOut(BaseModel):
    verdict: str  # match / non_match / unsure
    confidence: float
    evidence: list[str]  # the judge's cited codes, e.g. "same_interior"


class MatchPairOut(BaseModel):
    """Why two member listings are one villa: only what the pipeline recorded for the pair."""

    left: str
    right: str
    photo_pairs: list[PhotoPairOut]
    photos_compared: list[int]  # fingerprinted photos of each listing
    strong_photo_matches: int
    weak_photo_matches: int
    distance_min_m: float | None  # smallest possible distance between the published areas
    bedrooms: list[int | None]  # each listing's own value, in the pair's order
    max_capacity: list[int | None]
    area_m2: list[int | None]
    title_similarity: float | None
    rule_score: float | None
    threshold: float
    rules_match: bool
    contributions: dict[str, float]
    judge: JudgeOut | None
    human: str | None  # the owner's label for the pair, if any


@router.get("/{villa_id}/match")
async def get_match(villa_id: str, request: Request) -> list[MatchPairOut]:
    """The recorded evidence for each pair of member listings (empty for a one-listing villa)."""
    container = _container(request)
    _, members = await _villa(container, villa_id)
    explain = container.explain_match()
    by_id = {m.id: m for m in members}
    out = []
    for i, a in enumerate(members):
        for b in members[i + 1 :]:
            found = await explain.run(a.id, b.id)
            left, right = by_id[found.key.left], by_id[found.key.right]
            evidence = found.evidence
            out.append(
                MatchPairOut(
                    left=str(left.id),
                    right=str(right.id),
                    photo_pairs=[
                        PhotoPairOut(left_url=p.left_url, right_url=p.right_url, strong=p.strong)
                        for p in found.photo_pairs
                    ],
                    photos_compared=[
                        evidence.photos.compared_left if evidence else 0,
                        evidence.photos.compared_right if evidence else 0,
                    ],
                    strong_photo_matches=evidence.photos.strong_matches if evidence else 0,
                    weak_photo_matches=evidence.photos.weak_matches if evidence else 0,
                    distance_min_m=evidence.distance_min_m if evidence else None,
                    bedrooms=[left.bedrooms, right.bedrooms],
                    max_capacity=[left.max_capacity, right.max_capacity],
                    area_m2=[left.area_m2, right.area_m2],
                    title_similarity=evidence.title_similarity if evidence else None,
                    rule_score=found.rule_score,
                    threshold=found.threshold,
                    rules_match=found.rules_match,
                    contributions=dict(found.contributions),
                    judge=JudgeOut(
                        verdict=found.judge.verdict,
                        confidence=found.judge.confidence,
                        evidence=list(found.judge.evidence),
                    )
                    if found.judge
                    else None,
                    human=found.human,
                )
            )
    return out
