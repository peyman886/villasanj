"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from villasanj.entrypoints.api.claim_labels import router as claim_labels_router
from villasanj.entrypoints.api.labeling import router as labeling_router
from villasanj.entrypoints.api.listings import router as listings_router
from villasanj.entrypoints.api.listings import scenarios_router
from villasanj.entrypoints.api.metrics import router as metrics_router
from villasanj.entrypoints.api.photo_labels import router as photo_labels_router
from villasanj.entrypoints.api.reviews import router as reviews_router
from villasanj.entrypoints.api.search import router as search_router
from villasanj.entrypoints.api.summary_reviews import router as summary_reviews_router
from villasanj.entrypoints.api.villas import router as villas_router
from villasanj.entrypoints.container import Container, build_container
from villasanj.shared.application.errors import BudgetExceeded, LLMError


class ProbeOut(BaseModel):
    ok: bool
    detail: str


class HealthOut(BaseModel):
    status: str
    summary: str
    checks: dict[str, ProbeOut]


class LiveOut(BaseModel):
    status: str


log = structlog.get_logger(__name__)


def create_app(container_factory: Callable[[], Container] = build_container) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = container_factory()
        app.state.container = container
        try:
            yield
        finally:
            await container.aclose()

    app = FastAPI(title="Villasanj API", version="0.1.0", lifespan=lifespan)
    app.include_router(labeling_router)
    app.include_router(listings_router)
    app.include_router(scenarios_router)
    app.include_router(search_router)
    app.include_router(reviews_router)
    app.include_router(photo_labels_router)
    app.include_router(metrics_router)
    app.include_router(summary_reviews_router)
    app.include_router(claim_labels_router)
    app.include_router(villas_router)

    async def llm_unavailable(request: Request, error: Exception) -> JSONResponse:
        # Summaries, explanations and query understanding are optional parts of a page: a
        # model that cannot answer (quota, outage, output still invalid) is a 503, never a 500.
        log.warning("api.llm_unavailable", path=request.url.path, error=type(error).__name__)
        return JSONResponse(
            {"detail": "the language model is not available now"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    app.add_exception_handler(LLMError, llm_unavailable)
    app.add_exception_handler(BudgetExceeded, llm_unavailable)

    @app.get("/health/live")
    async def live() -> LiveOut:
        """Process liveness only (used by the container healthcheck; touches no dependency)."""
        return LiveOut(status="ok")

    @app.get("/health")
    async def health(request: Request, response: Response) -> HealthOut:
        """Readiness: database, blob store and LLM provider."""
        container: Container = request.app.state.container
        report = await container.health()
        if not report.ok:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthOut(
            status="ok" if report.ok else "degraded",
            summary=report.summary(),
            checks={
                name: ProbeOut(ok=result.ok, detail=result.detail)
                for name, result in report.results.items()
            },
        )

    return app


app = create_app()
