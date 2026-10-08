"""A vision model as a photo tagger for the two tags SigLIP could not make reliable (M9).

SigLIP 2 never reached 85% precision per photo for a sea view or a fireplace on the owner's
photos-v1 labels. This tagger asks a vision model the same two questions, one photo per call,
and stores its answers as tag scores under its own model id, so the existing pipeline decides
whether they are usable: the threshold is chosen on the same labels by the same rule (≥ 85%
precision), and a tag that does not reach it is not used. Photos only corroborate a feature the
description claims (A21), so production runs only on the photos of listings that claim one.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from villasanj.catalog.domain.listing import Listing
from villasanj.enrichment.application.photo_tags import PhotoTagStore, TagScore
from villasanj.enrichment.domain.features import Feature, Polarity, extract_claims
from villasanj.enrichment.domain.photo_tags import PhotoTag
from villasanj.shared.application.blobs import BlobStore
from villasanj.shared.application.clock import Clock
from villasanj.shared.application.errors import LLMError
from villasanj.shared.application.llm.ports import LLMClient
from villasanj.shared.application.llm.types import (
    ImagePart,
    JobContext,
    LLMRequest,
    LLMTask,
    Message,
)

VLM_PROMPT_ID = "photo_vlm_tags"
VLM_PROMPT_VERSION = "1"  # bump whenever SYSTEM_PROMPT or QUESTION changes (a test pins it)
VLM_TAGS = (PhotoTag.SEA_VIEW, PhotoTag.FIREPLACE)
FEATURE_TAGS = {Feature.SEA_VIEW: PhotoTag.SEA_VIEW, Feature.FIREPLACE: PhotoTag.FIREPLACE}

SYSTEM_PROMPT = """\
You look at one photo from a holiday villa listing and answer two questions about what is
visible in this photo only. Do not guess from the style of the house or the region.
- sea_view: open sea water is visible from the property (a sea or ocean surface, typically
  reaching the horizon). A pool, a lake, a river or a painting of the sea is not a sea view.
- fireplace: an indoor fireplace or hearth (wood, gas or electric fireplace built into a wall
  or standing in a room). A barbecue, an outdoor fire pit, a heater or a stove is not one.
For each, say whether it is visible and how confident you are (0 to 1)."""
QUESTION = "Answer for this photo."


class TagCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible: bool
    confidence: float = Field(ge=0, le=1)


class PhotoVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sea_view: TagCall
    fireplace: TagCall


def media_type(image: bytes) -> str | None:
    """The image type from its magic bytes; ``None``: not an image a model reads."""
    if image.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "image/webp"
    return None


def vlm_request(image: bytes, kind: str) -> LLMRequest[PhotoVerdict]:
    return LLMRequest(
        task=LLMTask.VISION_TAGGING,
        prompt_id=VLM_PROMPT_ID,
        prompt_version=VLM_PROMPT_VERSION,
        messages=(Message.system(SYSTEM_PROMPT), Message.user(QUESTION, ImagePart(image, kind))),
        output_schema=PhotoVerdict,
    )


def score(call: TagCall) -> float:
    """One number per tag, higher = more likely visible (what the threshold rule ranks)."""
    return 0.5 + call.confidence / 2 if call.visible else 0.5 - call.confidence / 2


def model_id(model: str) -> str:
    return f"vlm:{model}:{VLM_PROMPT_ID}@{VLM_PROMPT_VERSION}"


def claims_a_tag(listing: Listing) -> frozenset[PhotoTag]:
    """The VLM tags the listing's own description says it has (the only photos worth asking)."""
    claims = extract_claims(listing.description_norm or "")
    return frozenset(
        FEATURE_TAGS[c.feature]
        for c in claims
        if c.feature in FEATURE_TAGS and c.polarity is Polarity.HAS and not c.shared
    )


@dataclass(frozen=True, slots=True)
class VlmReport:
    model: str
    photos: int = 0
    already_scored: int = 0
    scored: int = 0
    unreadable: int = 0
    failed: int = 0


class TagPhotosWithVlm:
    """Score the given photos (by content hash) that this model has not scored yet."""

    def __init__(
        self,
        client: LLMClient,
        blobs: BlobStore,
        store: PhotoTagStore,
        clock: Clock,
        model: str,
        concurrency: int = 8,
    ) -> None:
        self._client = client
        self._blobs = blobs
        self._store = store
        self._clock = clock
        self._model = model_id(model)
        self._limit = asyncio.Semaphore(concurrency)

    @property
    def model(self) -> str:
        return self._model

    async def plan(self, sha256s: Sequence[str]) -> list[LLMRequest[PhotoVerdict]]:
        todo = sorted(set(sha256s) - await self._store.scored(self._model))
        requests = []
        for sha in todo:
            image = await self._blobs.get(sha)
            if (kind := media_type(image)) is not None:
                requests.append(vlm_request(image, kind))
        return requests

    async def run(self, sha256s: Sequence[str], ctx: JobContext) -> VlmReport:
        unique = sorted(set(sha256s))
        todo = sorted(set(unique) - await self._store.scored(self._model))
        report = VlmReport(self._model, photos=len(unique), already_scored=len(unique) - len(todo))
        results = await asyncio.gather(*(self._one(sha, ctx) for sha in todo))
        rows = [row for found in results if isinstance(found, list) for row in found]
        await self._store.save(rows)
        return replace(
            report,
            scored=sum(isinstance(r, list) for r in results),
            unreadable=sum(r == "unreadable" for r in results),
            failed=sum(r == "failed" for r in results),
        )

    async def _one(self, sha: str, ctx: JobContext) -> list[TagScore] | str:
        image = await self._blobs.get(sha)
        kind = media_type(image)
        if kind is None:
            return "unreadable"
        async with self._limit:
            try:
                response = await self._client.generate(vlm_request(image, kind), ctx)
            except LLMError:
                return "failed"  # counted, not guessed; a later run asks again
        now: datetime = self._clock.now()
        verdict = response.value
        return [
            TagScore(sha, self._model, PhotoTag.SEA_VIEW, score(verdict.sea_view), now),
            TagScore(sha, self._model, PhotoTag.FIREPLACE, score(verdict.fireplace), now),
        ]
