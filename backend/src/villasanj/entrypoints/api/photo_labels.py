"""Photo-tag labelling API (M9 criterion 2; local tool, no auth, never exposed beyond localhost).

Scores and strata are deliberately absent, so the labeller is not anchored by the model.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from villasanj.enrichment.domain.photo_tags import PhotoTag
from villasanj.entrypoints.container import Container
from villasanj.shared.domain.persian_text import ZWNJ

router = APIRouter(prefix="/photo-labels", tags=["photo-labels"])

TAG_FA: dict[PhotoTag, str] = {
    PhotoTag.POOL: "استخر",
    PhotoTag.JACUZZI: "جکوزی",
    PhotoTag.SEA_VIEW: f"منظره{ZWNJ}ی دریا",
    PhotoTag.FOREST: "جنگل",
    PhotoTag.FIREPLACE: "شومینه",
    PhotoTag.BARBECUE: "باربیکیو یا منقل",
}


class TagOut(BaseModel):
    code: PhotoTag
    name: str


class PhotoTaskOut(BaseModel):
    queue: str
    position: int
    total: int
    labelled: int
    done: bool
    sha256: str
    url: str
    present: list[PhotoTag]
    tags: list[TagOut]


class PhotoLabelIn(BaseModel):
    queue: str = Field(min_length=1, max_length=64)
    sha256: str = Field(min_length=64, max_length=64)
    present: list[PhotoTag] = Field(max_length=len(PhotoTag))
    labeler: str = Field(default="owner", min_length=1, max_length=32)


def _container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


@router.get("/task")
async def get_task(
    request: Request,
    queue: str = "photos-v1",
    labeler: str = "owner",
    position: Annotated[int | None, Query(ge=1)] = None,
) -> PhotoTaskOut:
    task = await _container(request).photo_labeling().task(queue, labeler, position)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no photo queue {queue}")
    return PhotoTaskOut(
        queue=queue,
        position=task.item.position,
        total=task.total,
        labelled=task.labelled,
        done=task.done,
        sha256=task.item.sha256,
        url=task.item.url,
        present=sorted(task.present),
        tags=[TagOut(code=tag, name=TAG_FA[tag]) for tag in PhotoTag],
    )


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def post_label(body: PhotoLabelIn, request: Request) -> Response:
    labeling = _container(request).photo_labeling()
    task = await labeling.task(body.queue, body.labeler)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"no photo queue {body.queue}")
    await labeling.label(body.queue, body.sha256, frozenset(body.present), body.labeler)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
