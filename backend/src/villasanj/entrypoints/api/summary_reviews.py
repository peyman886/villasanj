"""The owner's blind review of review summaries (M10 criterion 3; local tool, no auth).

A task names the listing; the page reads its summary and its raw reviews from the listing API,
so the reviewer sees exactly what users see, and nothing about how the summary was checked.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from villasanj.catalog.domain.listing import ListingId
from villasanj.enrichment.application.summary_review import Verdict
from villasanj.entrypoints.container import Container

router = APIRouter(prefix="/summary-reviews", tags=["summary-reviews"])


class SummaryReviewTaskOut(BaseModel):
    queue: str
    position: int
    total: int
    reviewed: int
    done: bool
    platform: str
    external_id: str
    faithful: bool | None  # this reviewer's verdict so far, if any
    note: str | None


class SummaryReviewIn(BaseModel):
    queue: str = Field(min_length=1, max_length=64)
    platform: str = Field(min_length=1, max_length=32)
    external_id: str = Field(min_length=1, max_length=64)
    faithful: bool
    note: str | None = Field(default=None, max_length=500)
    labeler: str = Field(default="owner", min_length=1, max_length=32)


def _container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


@router.get("/task")
async def get_task(
    request: Request,
    queue: str = "summaries-v1",
    labeler: str = "owner",
    position: Annotated[int | None, Query(ge=1)] = None,
) -> SummaryReviewTaskOut:
    task = await _container(request).summary_reviewing().task(queue, labeler, position)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no queue {queue}")
    return SummaryReviewTaskOut(
        queue=queue,
        position=task.item.position,
        total=task.total,
        reviewed=task.reviewed,
        done=task.done,
        platform=task.item.listing_id.platform,
        external_id=task.item.listing_id.external_id,
        faithful=task.current.faithful if task.current else None,
        note=task.current.note if task.current else None,
    )


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def post_verdict(body: SummaryReviewIn, request: Request) -> Response:
    note = body.note.strip() if body.note and body.note.strip() else None
    recorded = (
        await _container(request)
        .summary_reviewing()
        .record(
            body.queue,
            ListingId(body.platform, body.external_id),
            body.labeler,
            Verdict(body.faithful, note),
        )
    )
    if not recorded:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "listing not in this queue")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
