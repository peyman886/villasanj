"""System health: probes are ports, the check is a use case shared by the API and the CLI."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProbeResult:
    ok: bool
    detail: str


class HealthProbe(Protocol):
    @property
    def name(self) -> str: ...

    async def check(self) -> ProbeResult: ...


@dataclass(frozen=True, slots=True)
class HealthReport:
    results: dict[str, ProbeResult]

    @property
    def ok(self) -> bool:
        return all(result.ok for result in self.results.values())

    def summary(self) -> str:
        """One line such as ``db=ok blob=ok llm=avalai-ok``."""
        return " ".join(f"{name}={result.detail}" for name, result in self.results.items())


class CheckHealth:
    def __init__(self, probes: list[HealthProbe], timeout_seconds: float) -> None:
        self._probes = probes
        self._timeout = timeout_seconds

    async def __call__(self) -> HealthReport:
        results = await asyncio.gather(*(self._run(probe) for probe in self._probes))
        return HealthReport(
            {probe.name: result for probe, result in zip(self._probes, results, strict=True)}
        )

    async def _run(self, probe: HealthProbe) -> ProbeResult:
        try:
            return await asyncio.wait_for(probe.check(), timeout=self._timeout)
        except TimeoutError:
            return ProbeResult(ok=False, detail="timeout")
        except Exception as exc:  # a probe must never crash the report
            return ProbeResult(ok=False, detail=f"error:{type(exc).__name__}")
