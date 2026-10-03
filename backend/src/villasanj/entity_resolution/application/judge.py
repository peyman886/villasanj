"""LLM judge for gray-zone pairs (ADR-0009 stage 4), built ahead of M5 and not yet used.

Only pairs the rule score cannot decide go to the judge. It sees two composite photo grids (one
image per listing: Gemini bills ~1.1k tokens per image whatever its size) and the structured facts
of both listings, anonymised as A and B so platform names cannot bias it. It answers with a
structured verdict: match / non_match / unsure, a confidence, cited evidence codes and a short
rationale. UNSURE or low confidence goes to the human queue. Judge verdicts are never gold labels.

Which model, which threshold and whether the judge ships at all are decided by the M5 bake-off on
the gold set; until then this only builds requests and prices them (dry run).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import Listing, ListingId
from villasanj.entity_resolution.domain.evidence import PairEvidence
from villasanj.entity_resolution.domain.pairs import PairKey
from villasanj.shared.application.llm.ports import LLMClient
from villasanj.shared.application.llm.types import (
    ImagePart,
    JobContext,
    LLMRequest,
    LLMTask,
    Message,
)

JUDGE_PROMPT_ID = "er_judge"
JUDGE_PROMPT_VERSION = "1"  # bump whenever SYSTEM_PROMPT or FACTS_TEMPLATE changes (a test pins it)
MAX_GRID_PHOTOS = 6
MAX_DESCRIPTION_CHARS = 400

Evidence = Literal[
    "same_photos",
    "same_interior",
    "same_exterior",
    "same_view",
    "same_structure",
    "same_location",
    "shared_complex_photos",
    "different_photos",
    "different_interior",
    "different_structure",
    "different_location",
    "insufficient_photos",
]

SYSTEM_PROMPT = """\
You decide whether two rental listings, A and B, offer the same physical unit: the same building and
the same rooms a guest would stay in. They come from different booking platforms, so titles, prices,
capacities and descriptions can differ for the same villa; photos are the strongest evidence.
Rules:
- "match" only when the photos show the same interior or the same building and nothing
  contradicts it.
- Units of one complex share pool, garden or facade photos; shared areas alone are not a match. If
  only shared areas are visible, answer "unsure" and cite shared_complex_photos.
- Different rooms, furniture or layout mean "non_match" even when the location is the same.
- When the photos are too few or too unclear to tell, answer "unsure".
Answer with JSON only: verdict, confidence (0..1), evidence (codes), rationale (one or two short
sentences in English)."""

FACTS_TEMPLATE = """\
Listing A
{a}

Listing B
{b}

Location: {distance}
The first image shows listing A's photos, the second listing B's (up to {max_photos} each)."""


class JudgeVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Literal["match", "non_match", "unsure"]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(max_length=6)
    rationale: str = Field(max_length=400)


class PhotoGridRenderer(Protocol):
    def render(self, images: Sequence[bytes]) -> bytes:
        """One JPEG tiling the images in order (deterministic for the same inputs)."""
        ...


class ListingPhotoBytes(Protocol):
    async def photos(self, listing: ListingId, limit: int) -> list[bytes]:
        """The listing's stored photos, in page order."""
        ...


@dataclass(frozen=True, slots=True)
class JudgeInput:
    key: PairKey
    evidence: PairEvidence


def _facts(listing: Listing) -> str:
    def value(v: object) -> str:
        return "unknown" if v is None else str(v)

    description = (listing.description_norm or "")[:MAX_DESCRIPTION_CHARS]
    return "\n".join(
        [
            f"- title: {listing.title_norm}",
            f"- type: {value(listing.property_type)}",
            f"- bedrooms: {value(listing.bedrooms)}, bathrooms: {value(listing.bathrooms)}",
            f"- area m2: {value(listing.area_m2)}",
            f"- guests: base {value(listing.base_capacity)}, max {value(listing.max_capacity)}",
            f"- place: {value(listing.city_fa)} {listing.locality_fa or ''}".rstrip(),
            f"- description: {description or 'none'}",
        ]
    )


def _distance(evidence: PairEvidence) -> str:
    if evidence.distance_min_m is None:
        return "unknown (one listing publishes no location)"
    return f"the published points allow at least {evidence.distance_min_m:.0f} m apart"


def judge_request(
    left: Listing, right: Listing, evidence: PairEvidence, left_grid: bytes, right_grid: bytes
) -> LLMRequest[JudgeVerdict]:
    facts = FACTS_TEMPLATE.format(
        a=_facts(left), b=_facts(right), distance=_distance(evidence), max_photos=MAX_GRID_PHOTOS
    )
    return LLMRequest(
        task=LLMTask.ER_JUDGE,
        prompt_id=JUDGE_PROMPT_ID,
        prompt_version=JUDGE_PROMPT_VERSION,
        messages=(
            Message.system(SYSTEM_PROMPT),
            Message.user(
                facts,
                ImagePart(left_grid, "image/jpeg"),
                ImagePart(right_grid, "image/jpeg"),
            ),
        ),
        output_schema=JudgeVerdict,
    )


@dataclass(frozen=True, slots=True)
class Judgement:
    key: PairKey
    verdict: JudgeVerdict
    model: str
    cache_hit: bool
    cost_usd: Decimal = Decimal(0)
    latency_ms: int = 0


class JudgePairs:
    def __init__(
        self,
        listings: ListingReader,
        photos: ListingPhotoBytes,
        grids: PhotoGridRenderer,
        client: LLMClient,
    ) -> None:
        self._listings = listings
        self._photos = photos
        self._grids = grids
        self._client = client

    async def requests(self, inputs: Sequence[JudgeInput]) -> list[LLMRequest[JudgeVerdict]]:
        """The exact requests a run would send (also what ``--dry-run`` prices)."""
        return [r for _, r in await self._build(inputs)]

    async def run(self, inputs: Sequence[JudgeInput], ctx: JobContext) -> list[Judgement]:
        judgements = []
        for key, request in await self._build(inputs):
            response = await self._client.generate(request, ctx)
            judgements.append(
                Judgement(
                    key,
                    response.value,
                    response.model,
                    response.cache_hit,
                    response.cost_usd,
                    response.latency_ms,
                )
            )
        return judgements

    async def _build(
        self, inputs: Sequence[JudgeInput]
    ) -> list[tuple[PairKey, LLMRequest[JudgeVerdict]]]:
        built = []
        for item in inputs:
            left = await self._listings.get(item.key.left)
            right = await self._listings.get(item.key.right)
            if left is None or right is None:
                continue  # a listing left the catalog: nothing to judge
            left_grid = self._grids.render(await self._photos.photos(left.id, MAX_GRID_PHOTOS))
            right_grid = self._grids.render(await self._photos.photos(right.id, MAX_GRID_PHOTOS))
            built.append(
                (item.key, judge_request(left, right, item.evidence, left_grid, right_grid))
            )
        return built
