"""Feature claims the rules miss, read by an LLM (ROADMAP M9: deterministic first, the LLM for
the residue). Every claim must quote the description verbatim; a quote that is not in the text
is sent back once with the violations, then dropped. The rules keep every feature they found;
the LLM only fills features the rules say nothing about.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from villasanj.catalog.application.reading import ListingReader
from villasanj.catalog.domain.listing import Listing, ListingId
from villasanj.enrichment.domain.claim_eval import Stance
from villasanj.enrichment.domain.features import Feature, Polarity
from villasanj.shared.application.clock import Clock
from villasanj.shared.application.errors import LLMError
from villasanj.shared.application.llm.ports import LLMClient
from villasanj.shared.application.llm.types import (
    JobContext,
    LLMRequest,
    LLMTask,
    Message,
    Role,
    TextPart,
)
from villasanj.shared.domain.slots import verify_span

CLAIM_PROMPT_ID = "claim_extraction"
CLAIM_PROMPT_VERSION = "1"  # bump whenever SYSTEM_PROMPT or RETRY_TEMPLATE changes (a test pins it)

SYSTEM_PROMPT = """\
You read the description of a villa listed for rent in northern Iran, written in Persian, and say
what it claims about eight features of the villa itself, quoting the words that say so.

Features:
- pool: a swimming pool (استخر).
- jacuzzi: a jacuzzi or hot tub (جکوزی).
- near_sea: the villa is by the sea or the beach, or has its own way to the beach.
- sea_view: the sea can be seen from the villa.
- forest: the villa is in or beside a forest, or the forest can be seen from it.
- fireplace: a fireplace (شومینه).
- parking: a place to park cars.
- barbecue: a barbecue, grill or brazier (باربیکیو، کباب\N{ZERO WIDTH NON-JOINER}پز، منقل).

For each feature the description talks about, give its stance:
- has: the villa has it (for near_sea, sea_view and forest: the villa is so);
- has_not: the description says the villa does not have it;
- shared: it belongs to the complex, the town or the neighbours, not to the villa alone.
Leave out the features the description does not talk about. A travel time or distance to the sea
alone («۵ دقیقه تا دریا») is not near_sea. quote is the shortest part of the description that says
it, copied character for character."""

RETRY_TEMPLATE = """\
These quotes are not in the description, character for character:
{violations}
Answer again: copy each quote exactly from the description, or leave that claim out."""


class ClaimOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature: Feature
    stance: Literal["has", "has_not", "shared"]
    quote: str = Field(min_length=1, max_length=160)


class ClaimsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[ClaimOut] = Field(default_factory=list, max_length=16)


@dataclass(frozen=True, slots=True)
class ReadClaim:
    feature: Feature
    stance: Stance
    quote: str  # verbatim from the description (checked)


@dataclass(frozen=True, slots=True)
class LLMClaims:
    claims: tuple[ReadClaim, ...]
    retried: bool
    dropped: int  # claims whose quote was not in the text, even after the retry
    cost_usd: Decimal
    models: tuple[str, ...]


def claim_request(description: str) -> LLMRequest[ClaimsOut]:
    return LLMRequest(
        task=LLMTask.CLAIM_EXTRACTION,
        prompt_id=CLAIM_PROMPT_ID,
        prompt_version=CLAIM_PROMPT_VERSION,
        messages=(Message.system(SYSTEM_PROMPT), Message.user(f"Description:\n{description}")),
        output_schema=ClaimsOut,
    )


class ReadClaimsWithLLM:
    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def plan(self, descriptions: Sequence[str]) -> list[LLMRequest[ClaimsOut]]:
        """One request per description (a retry, when needed, is one more)."""
        return [claim_request(d) for d in descriptions if d.strip()]

    async def run(self, description: str, ctx: JobContext) -> LLMClaims:
        request = claim_request(description)
        response = await self._client.generate(request, ctx)
        models, cost = [response.model], response.cost_usd
        out, retried = response.value, False
        bad = [c for c in out.claims if verify_span(c.quote, description)]
        if bad:
            listed = "\n".join(f"- {c.feature}: «{c.quote}»" for c in bad)
            again = await self._client.generate(
                LLMRequest(
                    task=request.task,
                    prompt_id=request.prompt_id,
                    prompt_version=request.prompt_version,
                    messages=(
                        *request.messages,
                        Message(Role.ASSISTANT, (TextPart(out.model_dump_json()),)),
                        Message.user(RETRY_TEMPLATE.format(violations=listed)),
                    ),
                    output_schema=ClaimsOut,
                ),
                ctx,
            )
            out, retried = again.value, True
            models.append(again.model)
            cost += again.cost_usd
        kept = [c for c in out.claims if not verify_span(c.quote, description)]
        return LLMClaims(
            tuple(ReadClaim(c.feature, Stance(c.stance), c.quote) for c in kept),
            retried,
            len(out.claims) - len(kept),
            cost,
            tuple(models),
        )


_PRECEDENCE = {Stance.HAS: 0, Stance.HAS_NOT: 1, Stance.SHARED: 2, Stance.NONE: 3}


def with_residue(
    rules: Mapping[Feature, Stance], read: Sequence[ReadClaim]
) -> dict[Feature, Stance]:
    """The rules' stances, and for the features they found nothing about, the LLM's (its own
    word first: has, then has not, then shared)."""
    merged = dict(rules)
    for feature in Feature:
        if merged.get(feature, Stance.NONE) is not Stance.NONE:
            continue
        found = sorted(
            (c.stance for c in read if c.feature is feature), key=lambda s: _PRECEDENCE[s]
        )
        merged[feature] = found[0] if found else Stance.NONE
    return merged


def as_read(claims: Sequence[ReadClaim]) -> list[tuple[Feature, Polarity, bool, str]]:
    """LLM claims in the shape the feature domain merges (shared means "has", shared)."""
    shapes = {
        Stance.HAS: (Polarity.HAS, False),
        Stance.HAS_NOT: (Polarity.HAS_NOT, False),
        Stance.SHARED: (Polarity.HAS, True),
    }
    return [(c.feature, *shapes[c.stance], c.quote) for c in claims if c.stance in shapes]


class ReadClaimStore(Protocol):
    async def replace(
        self,
        listing_id: ListingId,
        claims: Sequence[ReadClaim],
        model: str,
        at: datetime,
    ) -> None: ...

    async def get(self, listing_id: ListingId) -> list[ReadClaim]: ...

    async def of_platform(self, platform: str) -> dict[ListingId, list[ReadClaim]]: ...


@dataclass(slots=True)
class ReadAllReport:
    platform: str
    descriptions: int = 0
    claims: int = 0
    dropped: int = 0
    retried: int = 0
    failed: int = 0
    cost_usd: Decimal = Decimal(0)


class ReadAllClaims:
    """The LLM pass over every description of a platform (cached: a re-run costs nothing)."""

    def __init__(
        self,
        listings: ListingReader,
        reader: ReadClaimsWithLLM,
        store: ReadClaimStore,
        clock: Clock,
        concurrency: int = 8,
    ) -> None:
        self._listings = listings
        self._reader = reader
        self._store = store
        self._clock = clock
        self._concurrency = concurrency

    async def descriptions(self, platform: str) -> list[str]:
        return [
            x.description_norm
            for x in await self._listings.listings(platform)
            if x.description_norm and x.description_norm.strip()
        ]

    async def run(self, platform: str, ctx: JobContext) -> ReadAllReport:
        report = ReadAllReport(platform)
        todo = [
            x
            for x in await self._listings.listings(platform)
            if x.description_norm and x.description_norm.strip()
        ]
        gate = asyncio.Semaphore(self._concurrency)

        async def one(listing: Listing) -> None:
            async with gate:
                try:
                    read = await self._reader.run(listing.description_norm or "", ctx)
                except LLMError:
                    report.failed += 1
                    return
            await self._store.replace(listing.id, read.claims, read.models[-1], self._clock.now())
            report.descriptions += 1
            report.claims += len(read.claims)
            report.dropped += read.dropped
            report.retried += read.retried
            report.cost_usd += read.cost_usd

        await asyncio.gather(*(one(x) for x in todo))
        return report
