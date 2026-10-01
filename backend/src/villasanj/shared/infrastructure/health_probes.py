"""Health probes for the database, blob store and LLM provider."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from villasanj.shared.application.blobs import BlobStore
from villasanj.shared.application.clock import Clock
from villasanj.shared.application.health import ProbeResult
from villasanj.shared.application.llm.ports import RawModelProvider
from villasanj.shared.infrastructure.db.tables import REQUIRED_EXTENSIONS

PROBE_PAYLOAD = b"villasanj-health-probe"
LLM_READINESS_TTL = timedelta(minutes=5)


class DatabaseProbe:
    name = "db"

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def check(self) -> ProbeResult:
        async with self._engine.connect() as conn:
            rows = await conn.execute(text("SELECT extname FROM pg_extension"))
            installed = {row.extname for row in rows}
        missing = sorted(set(REQUIRED_EXTENSIONS) - installed)
        if missing:
            return ProbeResult(ok=False, detail=f"missing-extensions:{','.join(missing)}")
        return ProbeResult(ok=True, detail="ok")


class BlobStoreProbe:
    name = "blob"

    def __init__(self, store: BlobStore) -> None:
        self._store = store

    async def check(self) -> ProbeResult:
        ref = await self._store.put(PROBE_PAYLOAD)
        ok = await self._store.get(ref.key) == PROBE_PAYLOAD
        return ProbeResult(ok=ok, detail="ok" if ok else "read-mismatch")


class LLMProviderProbe:
    """Caches readiness: the check is free, but there is no reason to call it on every request."""

    name = "llm"

    def __init__(self, provider: RawModelProvider, clock: Clock) -> None:
        self._provider = provider
        self._clock = clock
        self._cached: tuple[datetime, bool] | None = None

    async def check(self) -> ProbeResult:
        now = self._clock.now()
        if self._cached is None or now - self._cached[0] > LLM_READINESS_TTL:
            self._cached = (now, await self._provider.ready())
        ready = self._cached[1]
        return ProbeResult(ok=ready, detail=f"{self._provider.name}-{'ok' if ready else 'down'}")
