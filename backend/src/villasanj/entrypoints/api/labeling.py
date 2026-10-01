"""Labelling API for the gold set (local tool; no auth, never exposed beyond localhost).

Scores, strata and model suggestions are deliberately absent from the responses, so the labeller
is not anchored by the matcher (ADR-0009).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from villasanj.catalog.domain.listing import Listing
from villasanj.entity_resolution.domain.labels import Label
from villasanj.entity_resolution.domain.pairs import PairKey
from villasanj.entrypoints.container import Container

MAX_PHOTOS = 24
MAX_DESCRIPTION = 900

router = APIRouter(prefix="/er", tags=["entity-resolution"])


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
    bedrooms: int | None
    bathrooms: int | None
    area_m2: int | None
    base_capacity: int | None
    max_capacity: int | None
    base_price_toman: int | None
    rating: float | None
    rating_count: int | None
    photos: list[str]


class DistanceOut(BaseModel):
    centre_m: float
    min_m: float
    max_m: float | None


class TaskOut(BaseModel):
    queue: str
    position: int
    total: int
    labeled: int
    pair: str
    current_label: Label | None
    left: ListingOut
    right: ListingOut
    distance: DistanceOut | None


class LabelIn(BaseModel):
    queue: str
    pair: str
    label: Label
    labeler: str = Field(min_length=1, max_length=40)
    seconds: float | None = Field(default=None, ge=0)


class LabelOut(BaseModel):
    pair: str
    label: Label
    labeled_at: str


def _listing(container: Container, listing: Listing) -> ListingOut:
    adapter = container.crawl.adapters.get(listing.id.platform)
    description = listing.description_norm
    return ListingOut(
        id=str(listing.id),
        platform=listing.id.platform,
        platform_name=adapter.profile.display_name if adapter else listing.id.platform,
        url=listing.url,
        title=listing.title_norm,
        description=description[:MAX_DESCRIPTION] if description else None,
        property_type=listing.property_type,
        city=listing.city_fa,
        locality=listing.locality_fa,
        bedrooms=listing.bedrooms,
        bathrooms=listing.bathrooms,
        area_m2=listing.area_m2,
        base_capacity=listing.base_capacity,
        max_capacity=listing.max_capacity,
        base_price_toman=int(listing.rate_card.base.toman) if listing.rate_card.base else None,
        rating=listing.rating_avg,
        rating_count=listing.rating_count,
        photos=list(listing.photos[:MAX_PHOTOS]),
    )


def _distance(left: Listing, right: Listing) -> DistanceOut | None:
    if left.location is None or right.location is None:
        return None
    centre = left.location.point.distance_m(right.location.point)
    low, high = left.location.distance_range_m(right.location.point)
    other = right.location.radius_m
    return DistanceOut(
        centre_m=round(centre, 1),
        min_m=round(max(0.0, low - (other or 0)), 1),
        max_m=round(high + other, 1) if high is not None and other is not None else None,
    )


@router.get("/queues/{queue}/task", response_model=None)
async def task(
    queue: str, request: Request, labeler: str = "owner", position: int | None = None
) -> TaskOut | Response:
    """The pair at ``position``, or the next unlabelled one (204 when the queue is done)."""
    container: Container = request.app.state.container
    found = await container.labeling().task(queue, labeler, position)
    if found is None:
        if position is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"no pair at position {position}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return TaskOut(
        queue=queue,
        position=found.item.position,
        total=found.total,
        labeled=found.labeled,
        pair=str(found.item.key),
        current_label=found.current,
        left=_listing(container, found.left),
        right=_listing(container, found.right),
        distance=_distance(found.left, found.right),
    )


@router.post("/labels", status_code=status.HTTP_201_CREATED)
async def record_label(body: LabelIn, request: Request) -> LabelOut:
    container: Container = request.app.state.container
    try:
        key = PairKey.parse(body.pair)
    except (ValueError, TypeError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "malformed pair") from None
    queued = {item.key for item in await container.labels().queue(body.queue)}
    if key not in queued:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pair is not in this queue")
    decision = await container.labeling().record(key, body.label, body.labeler, body.seconds)
    return LabelOut(
        pair=str(decision.key), label=decision.label, labeled_at=decision.labeled_at.isoformat()
    )
