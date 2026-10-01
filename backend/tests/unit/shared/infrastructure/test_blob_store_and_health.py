import asyncio
import hashlib
from datetime import timedelta
from pathlib import Path

import pytest

from tests.fakes.llm import FixedClock
from villasanj.shared.application.health import CheckHealth, ProbeResult
from villasanj.shared.infrastructure.blob_store import LocalFsBlobStore
from villasanj.shared.infrastructure.health_probes import BlobStoreProbe, LLMProviderProbe
from villasanj.shared.infrastructure.llm.fake import FakeLLMProvider


class TestLocalFsBlobStore:
    async def test_put_is_content_addressed_and_idempotent(self, tmp_path: Path) -> None:
        store = LocalFsBlobStore(tmp_path)
        ref = await store.put(b"snapshot")
        assert ref.key == hashlib.sha256(b"snapshot").hexdigest()
        assert ref.size == len(b"snapshot")
        assert await store.put(b"snapshot") == ref
        assert await store.get(ref.key) == b"snapshot"
        assert await store.exists(ref.key)
        assert (tmp_path / ref.key[:2] / ref.key[2:4] / ref.key).is_file()

    async def test_missing_and_malformed_keys(self, tmp_path: Path) -> None:
        store = LocalFsBlobStore(tmp_path)
        with pytest.raises(KeyError):
            await store.get("0" * 64)
        with pytest.raises(KeyError):
            await store.get("../../etc/passwd")


class _Probe:
    def __init__(self, name: str, result: ProbeResult | None = None, delay: float = 0) -> None:
        self.name = name
        self._result = result
        self._delay = delay

    async def check(self) -> ProbeResult:
        await asyncio.sleep(self._delay)
        if self._result is None:
            raise RuntimeError("probe exploded")
        return self._result


class TestCheckHealth:
    async def test_report_summary_and_failures(self, tmp_path: Path) -> None:
        check = CheckHealth(
            [
                _Probe("db", ProbeResult(True, "ok")),
                BlobStoreProbe(LocalFsBlobStore(tmp_path)),
                _Probe("slow", ProbeResult(True, "ok"), delay=1),
                _Probe("broken"),
            ],
            timeout_seconds=0.05,
        )
        report = await check()
        assert report.summary() == "db=ok blob=ok slow=timeout broken=error:RuntimeError"
        assert not report.ok

    async def test_llm_probe_caches_readiness(self) -> None:
        class CountingProvider(FakeLLMProvider):
            checks = 0

            async def ready(self) -> bool:
                CountingProvider.checks += 1
                return True

        clock = FixedClock()
        probe = LLMProviderProbe(CountingProvider(), clock)
        assert (await probe.check()).detail == "fake-ok"
        await probe.check()
        assert CountingProvider.checks == 1
        clock.current += timedelta(minutes=6)
        await probe.check()
        assert CountingProvider.checks == 2
