"""Claim labelling API (M9 criterion 1; local tool, no auth). The task carries the description
only: what the rules extracted is never shown, so the labeller is not anchored."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.domain.claim_eval import Stance
from villasanj.enrichment.domain.features import Feature
from villasanj.entrypoints.container import Container

router = APIRouter(prefix="/claim-labels", tags=["claim-labels"])


class ClaimTaskOut(BaseModel):
    queue: str
    position: int
    total: int
    labelled: int
    done: bool
    platform: str
    external_id: str
    title: str | None
    description: str | None
    features: list[Feature]
    current: dict[Feature, Stance]  # empty until this labeller saves this description


class ClaimLabelsIn(BaseModel):
    queue: str = Field(min_length=1, max_length=64)
    platform: str = Field(min_length=1, max_length=32)
    external_id: str = Field(min_length=1, max_length=64)
    stances: dict[Feature, Stance]
    labeler: str = Field(default="owner", min_length=1, max_length=32)


def _container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


@router.get("/task")
async def get_task(
    request: Request,
    queue: str = "claims-v1",
    labeler: str = "owner",
    position: Annotated[int | None, Query(ge=1)] = None,
) -> ClaimTaskOut:
    container = _container(request)
    task = await container.claim_labeling().task(queue, labeler, position)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no queue {queue}")
    listing = await container.listings.get(task.item.listing_id)
    return ClaimTaskOut(
        queue=queue,
        position=task.item.position,
        total=task.total,
        labelled=task.labelled,
        done=task.done,
        platform=task.item.listing_id.platform,
        external_id=task.item.listing_id.external_id,
        title=listing.title_norm if listing else None,
        description=listing.description_norm if listing else None,
        features=list(Feature),
        current=task.current,
    )


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def post_labels(body: ClaimLabelsIn, request: Request) -> Response:
    recorded = (
        await _container(request)
        .claim_labeling()
        .record(body.queue, ListingId(body.platform, body.external_id), body.labeler, body.stances)
    )
    if not recorded:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "listing not in this queue")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
