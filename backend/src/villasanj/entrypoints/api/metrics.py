"""Project metrics for reviewers (ROADMAP M11 dashboard; parts that need M3/M5 come later).

Everything here is computed from the database at request time by the same use cases the CLI
reports use: crawl politeness, catalog and photo coverage, offers, sea truth check, drive times,
LLM spend and labelling progress. Overlap, precision with CI and hidden nights need canonical
villas and the gold set, so they are not shown yet.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from villasanj.entrypoints.container import Container

router = APIRouter(tags=["metrics"])


class HostOut(BaseModel):
    platform: str
    host: str
    responses: int
    min_interval_s: float | None
    median_interval_s: float | None


class PlatformOut(BaseModel):
    platform: str
    listings: int
    photos_selected: int
    photos_downloaded: int
    photos_unfinished: int
    photo_coverage: float
    coast_measured: int
    drive_routed: int
    sea_claim_listings: int
    sea_measured_listings: int  # with a sea claim and a measured coast distance
    sea_contradicted_listings: int
    sea_contradicted_low: float  # Wilson 95% interval of the share among measured listings (H4)
    sea_contradicted_high: float
    sea_verdicts: dict[str, int]


class OffersOut(BaseModel):
    platform: str
    scenario: str
    guests: int
    listings: int
    by_status: dict[str, int]
    by_kind: dict[str, int]
    stale: int


class SpendOut(BaseModel):
    task: str
    model: str
    calls: int
    failed: int
    cost_usd: float


class LabellingOut(BaseModel):
    queue: str
    total: int
    labelled: int


class MetricsOut(BaseModel):
    computed_at: datetime
    hosts: list[HostOut]
    platforms: list[PlatformOut]
    offers: list[OffersOut]
    llm_spend: list[SpendOut]
    llm_total_usd: float
    llm_cap_usd: float
    labelling: list[LabellingOut]


@router.get("/metrics")
async def get_metrics(request: Request) -> MetricsOut:
    container: Container = request.app.state.container
    platforms = sorted(container.crawl.adapters)
    traffic = await container.crawl_stats().traffic()
    photos = {
        r.platform: r
        for r in await container.photo_pipeline().run(container.image_embedder().model_id)
    }
    truth = container.sea_truth()
    origin = container.routing_origin()
    rows = []
    for platform in platforms:
        photo = photos.get(platform)
        sea = await truth.run(platform)
        share = sea.contradicted_share()
        rows.append(
            PlatformOut(
                platform=platform,
                listings=len(await container.listings.listings(platform)),
                photos_selected=photo.selected if photo else 0,
                photos_downloaded=photo.downloaded if photo else 0,
                photos_unfinished=photo.unfinished if photo else 0,
                photo_coverage=round(photo.coverage, 4) if photo else 0.0,
                coast_measured=len(await container.coast_store().of_platform(platform)),
                drive_routed=sum(
                    d.routed_points > 0
                    for d in (
                        await container.drive_store().of_platform(platform, origin.slug)
                    ).values()
                ),
                sea_claim_listings=sea.listings_with_claim,
                sea_measured_listings=sea.listings_with_claim - sea.without_distance,
                sea_contradicted_listings=sea.listings_contradicted,
                sea_contradicted_low=round(share.low, 4),
                sea_contradicted_high=round(share.high, 4),
                sea_verdicts=dict(sea.verdicts),
            )
        )
    offers = await container.offers().distribution(platforms, container.scenarios())
    spend = await container.llm_spend().by_task_and_model()
    labelling = []
    gold = await container.labeling().task("gold-v1", "owner")
    if gold is not None:
        labelling.append(LabellingOut(queue="gold-v1", total=gold.total, labelled=gold.labeled))
    photos_task = await container.photo_labeling().task("photos-v1", "owner")
    if photos_task is not None:
        labelling.append(
            LabellingOut(queue="photos-v1", total=photos_task.total, labelled=photos_task.labelled)
        )
    return MetricsOut(
        computed_at=container.clock.now(),
        hosts=[
            HostOut(
                platform=h.platform,
                host=h.host,
                responses=h.responses,
                min_interval_s=h.min_interval_s,
                median_interval_s=h.median_interval_s,
            )
            for h in traffic
        ],
        platforms=rows,
        offers=[
            OffersOut(
                platform=o.platform,
                scenario=o.scenario,
                guests=o.guests,
                listings=o.listings,
                by_status=o.by_status,
                by_kind=o.by_kind,
                stale=o.stale,
            )
            for o in offers
        ],
        llm_spend=[
            SpendOut(
                task=s.task,
                model=s.model,
                calls=s.calls,
                failed=s.failed,
                cost_usd=float(s.cost_usd),
            )
            for s in spend
        ],
        llm_total_usd=float(sum((s.cost_usd for s in spend), Decimal(0))),
        llm_cap_usd=float(container.llm.routing.project_budget_usd),
        labelling=labelling,
    )
