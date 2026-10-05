"""The owner's remaining reviews (local tools, no auth): the M8 query set and search relevance,
plus the progress of every human queue for the review hub.

The relevance task never says which system ranked a villa or where: the review is blind.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from villasanj.discovery.application.reviews import InvalidIntent, QueryVerdict
from villasanj.entrypoints.container import Container

router = APIRouter(prefix="/reviews", tags=["reviews"])

QUERY_QUEUE = "queries-v1"
RELEVANCE_QUEUE = "relevance-v1"


def _container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


class QueryReviewTaskOut(BaseModel):
    queue: str
    position: int
    total: int
    reviewed: int
    done: bool
    query: str
    expected: dict[str, object]
    note: str
    correct: bool | None  # this reviewer's verdict so far
    corrected: dict[str, object] | None
    reviewer_note: str | None


class QueryReviewIn(BaseModel):
    queue: str = Field(default=QUERY_QUEUE, min_length=1, max_length=64)
    position: int = Field(ge=1)
    correct: bool
    corrected: dict[str, object] | None = None
    note: str | None = Field(default=None, max_length=1000)
    labeler: str = Field(default="owner", min_length=1, max_length=32)


@router.get("/queries/task")
async def query_task(
    request: Request,
    queue: str = QUERY_QUEUE,
    labeler: str = "owner",
    position: Annotated[int | None, Query(ge=1)] = None,
) -> QueryReviewTaskOut:
    task = await _container(request).query_reviewing().task(queue, labeler, position)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no queue {queue}")
    return QueryReviewTaskOut(
        queue=queue,
        position=task.position,
        total=task.total,
        reviewed=task.reviewed,
        done=task.done,
        query=task.query,
        expected=task.expected,
        note=task.note,
        correct=task.current.correct if task.current else None,
        corrected=task.current.corrected if task.current else None,
        reviewer_note=task.current.note if task.current else None,
    )


@router.post("/queries", status_code=status.HTTP_204_NO_CONTENT)
async def post_query_verdict(body: QueryReviewIn, request: Request) -> Response:
    note = body.note.strip() if body.note and body.note.strip() else None
    verdict = QueryVerdict(body.correct, None if body.correct else body.corrected, note)
    try:
        recorded = (
            await _container(request)
            .query_reviewing()
            .record(body.queue, body.position, body.labeler, verdict)
        )
    except InvalidIntent as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(error)) from None
    if not recorded:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "case not in this queue")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class RelevanceItemOut(BaseModel):
    listing: str
    villa: str | None
    title: str
    place: str
    bedrooms: int | None
    max_capacity: int | None
    total_low_toman: int | None
    total_high_toman: int | None
    per_person_night_toman: float | None
    rating: float | None
    features: list[str]
    coast_m: list[int] | None
    drive_min: list[int] | None
    other_platforms: list[str]
    grade: int | None  # this reviewer's grade so far


class RelevanceTaskOut(BaseModel):
    queue: str
    position: int
    total: int
    queries_done: int
    done: bool
    query: str
    check_in: str
    check_out: str
    guests: int | None
    intent: dict[str, object]
    items: list[RelevanceItemOut]


class RelevanceIn(BaseModel):
    queue: str = Field(default=RELEVANCE_QUEUE, min_length=1, max_length=64)
    position: int = Field(ge=1)
    listing: str = Field(min_length=3, max_length=96)
    grade: int = Field(ge=0, le=2)
    labeler: str = Field(default="owner", min_length=1, max_length=32)


@router.get("/relevance/task")
async def relevance_task(
    request: Request,
    queue: str = RELEVANCE_QUEUE,
    labeler: str = "owner",
    position: Annotated[int | None, Query(ge=1)] = None,
) -> RelevanceTaskOut:
    task = await _container(request).relevance_reviewing().task(queue, labeler, position)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no queue {queue}")
    p = task.payload
    items = p.get("items")
    intent = p.get("intent")
    return RelevanceTaskOut(
        queue=queue,
        position=task.position,
        total=task.total,
        queries_done=task.queries_done,
        done=task.done,
        query=str(p["query"]),
        check_in=str(p["check_in"]),
        check_out=str(p["check_out"]),
        guests=guests if isinstance(guests := p.get("guests"), int) else None,
        intent=dict(intent) if isinstance(intent, dict) else {},
        items=[
            RelevanceItemOut.model_validate({**i, "grade": task.grades.get(str(i["listing"]))})
            for i in (items if isinstance(items, list) else [])
            if isinstance(i, dict)
        ],
    )


@router.post("/relevance", status_code=status.HTTP_204_NO_CONTENT)
async def post_relevance(body: RelevanceIn, request: Request) -> Response:
    recorded = (
        await _container(request)
        .relevance_reviewing()
        .record(body.queue, body.position, body.listing, body.labeler, body.grade)
    )
    if not recorded:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "villa not in this query's pool")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class QueueProgressOut(BaseModel):
    queue: str
    total: int  # cases (pairs, queries, photos…) in the queue; 0 when it is not built yet
    done: int
    built: bool


@router.get("/progress")
async def progress(request: Request, labeler: str = "owner") -> list[QueueProgressOut]:
    """Every human queue the hub links to, built or not."""
    c = _container(request)
    out: list[QueueProgressOut] = []
    for queue in ("er-human", "gold-v1"):
        pairs = await c.labeling().progress(queue, labeler)
        out.append(
            QueueProgressOut(
                queue=queue,
                total=pairs[0] if pairs else 0,
                done=pairs[1] if pairs else 0,
                built=pairs is not None,
            )
        )
    query = await c.query_reviewing().task(QUERY_QUEUE, labeler)
    out.append(
        QueueProgressOut(
            queue=QUERY_QUEUE,
            total=query.total if query else 0,
            done=query.reviewed if query else 0,
            built=query is not None,
        )
    )
    relevance = await c.relevance_reviewing().task(RELEVANCE_QUEUE, labeler)
    out.append(
        QueueProgressOut(
            queue=RELEVANCE_QUEUE,
            total=relevance.total if relevance else 0,
            done=relevance.queries_done if relevance else 0,
            built=relevance is not None,
        )
    )
    summaries = await c.summary_reviewing().task("summaries-v1", labeler)
    claims = await c.claim_labeling().task("claims-v1", labeler)
    photos = await c.photo_labeling().task("photos-v1", labeler)
    out += [
        QueueProgressOut(
            queue="summaries-v1",
            total=summaries.total if summaries else 0,
            done=summaries.reviewed if summaries else 0,
            built=summaries is not None,
        ),
        QueueProgressOut(
            queue="claims-v1",
            total=claims.total if claims else 0,
            done=claims.labelled if claims else 0,
            built=claims is not None,
        ),
        QueueProgressOut(
            queue="photos-v1",
            total=photos.total if photos else 0,
            done=photos.labelled if photos else 0,
            built=photos is not None,
        ),
    ]
    return out
