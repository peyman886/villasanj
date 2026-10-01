"""Jobs: every batch run (and its LLM spend) is attributed to a job."""

from collections.abc import Mapping
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from villasanj.shared.application.llm.types import JobContext


class JobStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobRepository(Protocol):
    async def start(
        self, kind: str, budget_usd: Decimal, params: Mapping[str, str]
    ) -> JobContext: ...

    async def finish(self, job_id: str, status: JobStatus) -> None: ...
