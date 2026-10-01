"""Search API (ROADMAP M8/M10 groundwork, listing level until M5's canonical villas).

One request makes at most three LLM calls (query understanding, one retry if a rule broke, the
explanation; cached answers are free). Every number in the response carries provenance, and the
explanation comes as segments so the UI can link each filled slot to its source.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from villasanj.discovery.application.explanation import ExplainChoice, Explanation, explain_first
from villasanj.discovery.application.routing import Origin
from villasanj.discovery.application.search import SearchResult
from villasanj.discovery.domain.dates import describe_fa
from villasanj.discovery.domain.ranking import Ranked
from villasanj.entrypoints.api.listings import GeoOut, MoneyOut, ProvenanceOut, geo_out
from villasanj.entrypoints.container import Container
from villasanj.shared.application.jobs import JobStatus
from villasanj.shared.domain.slots import SLOT

MAX_RESULTS = 20
SEARCH_BUDGET_USD = Decimal("0.02")

router = APIRouter(tags=["search"])


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=300)


class DatesOut(BaseModel):
    check_in: str
    check_out: str
    text: str  # Persian, e.g. «پنجشنبه ۱۶ مهر تا شنبه ۱۸ مهر»
    flexible: bool
    caveats: list[str]


class ContributionOut(BaseModel):
    component: str
    normalized: float
    weight: float
    points: float


class ResultOut(BaseModel):
    listing_id: str
    platform: str
    external_id: str
    platform_name: str
    title: str
    photo: str | None
    total: MoneyOut | None
    total_provenance: ProvenanceOut
    price_per_person_night_toman: float | None
    confirmed_features: int
    score: float
    contributions: list[ContributionOut]
    cautions: list[str]
    geo: GeoOut | None


class SegmentOut(BaseModel):
    text: str
    slot: str | None  # the fact or comparison this text fills, if any
    provenance: ProvenanceOut | None


class ExplanationOut(BaseModel):
    source: Literal["llm", "template"]
    text: str
    segments: list[SegmentOut]


class SearchOut(BaseModel):
    query: str
    intent: dict[str, object]
    dates: DatesOut | None
    missing: list[str]
    places: list[str]
    unresolved_places: list[str]
    budget_readings: dict[str, int] | None
    excluded: dict[str, int]
    total_results: int
    results: list[ResultOut]
    explanation: ExplanationOut | None


def _result_out(
    container: Container, ranked: Ranked, result: SearchResult, origin: Origin | None
) -> ResultOut:
    key = ranked.candidate.id
    listing, offer = result.listings[key], result.offers[key]
    adapter = container.crawl.adapters.get(listing.id.platform)
    total = offer.quote.total
    return ResultOut(
        listing_id=key,
        platform=listing.id.platform,
        external_id=listing.id.external_id,
        platform_name=adapter.profile.display_name if adapter else listing.id.platform,
        title=listing.title_norm,
        photo=listing.photos[0] if listing.photos else None,
        total=MoneyOut.of(total) if total else None,
        total_provenance=ProvenanceOut.of(offer.quote.provenance),
        price_per_person_night_toman=ranked.price_per_person_night_toman,
        confirmed_features=ranked.confirmed,
        score=round(ranked.score, 4),
        contributions=[
            ContributionOut(
                component=c.component,
                normalized=round(c.normalized, 4),
                weight=c.weight,
                points=round(c.points, 4),
            )
            for c in ranked.contributions
        ],
        cautions=sorted(ranked.warnings),
        geo=_geo(result, key, origin),
    )


def _geo(result: SearchResult, key: str, origin: Origin | None) -> GeoOut | None:
    geo = result.geo.get(key)
    if geo is None or origin is None:
        return None
    return geo_out(result.listings[key], geo.coast, geo.drive, origin)


def _segments(explanation: Explanation) -> list[SegmentOut]:
    slots = explanation.slots
    segments: list[SegmentOut] = []
    position = 0
    for match in SLOT.finditer(explanation.slotted):
        if match.start() > position:
            segments.append(
                SegmentOut(
                    text=explanation.slotted[position : match.start()], slot=None, provenance=None
                )
            )
        slot = match.group(1)
        value = slots.facts.get(slot) or slots.comparisons[slot]
        segments.append(
            SegmentOut(text=value.text, slot=slot, provenance=ProvenanceOut.of(value.provenance))
        )
        position = match.end()
    if position < len(explanation.slotted):
        segments.append(SegmentOut(text=explanation.slotted[position:], slot=None, provenance=None))
    return segments


@router.post("/search")
async def search(body: SearchIn, request: Request) -> SearchOut:
    """A Persian query to ranked listings with reasons, and why the first one fits."""
    container: Container = request.app.state.container
    ctx = await container.jobs.start("search", SEARCH_BUDGET_USD, {})
    status = JobStatus.FAILED
    try:
        result = await container.search().run(body.query, ctx)
        names = {p: a.profile.display_name for p, a in container.crawl.adapters.items()}
        why = await explain_first(
            ExplainChoice(container.llm.client), result, names, container.clock.now(), ctx
        )
        status = JobStatus.SUCCEEDED
    finally:
        await container.jobs.finish(ctx.job_id, status)
    ranking = result.ranking
    dates = result.dates
    origin = container.routing_origin() if result.geo else None
    return SearchOut(
        query=body.query,
        intent=result.understanding.intent.model_dump(exclude_none=True),
        dates=DatesOut(
            check_in=dates.window.check_in.isoformat(),
            check_out=dates.window.check_out.isoformat(),
            text=describe_fa(dates.window),
            flexible=dates.flexible,
            caveats=sorted(dates.caveats),
        )
        if dates
        else None,
        missing=list(result.missing),
        places=[p.name_fa for p in result.places],
        unresolved_places=list(result.unresolved_places),
        budget_readings=dict(ranking.budget_readings)
        if ranking and ranking.budget_readings
        else None,
        excluded=dict(ranking.excluded) if ranking else {},
        total_results=len(ranking.results) if ranking else 0,
        results=[_result_out(container, r, result, origin) for r in ranking.results[:MAX_RESULTS]]
        if ranking
        else [],
        explanation=ExplanationOut(
            source=why.source.value, text=why.rendered.text, segments=_segments(why)
        )
        if why
        else None,
    )
