from typing import cast

from fastapi.testclient import TestClient

from villasanj.entrypoints.api.app import create_app
from villasanj.entrypoints.container import Container
from villasanj.shared.application.health import CheckHealth, ProbeResult


class _Probe:
    def __init__(self, name: str, ok: bool) -> None:
        self.name = name
        self._ok = ok

    async def check(self) -> ProbeResult:
        return ProbeResult(self._ok, "ok" if self._ok else "down")


class _StubContainer:
    def __init__(self, healthy: bool) -> None:
        self.health = CheckHealth([_Probe("db", True), _Probe("llm", healthy)], timeout_seconds=1)
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def _client(healthy: bool) -> tuple[TestClient, _StubContainer]:
    stub = _StubContainer(healthy)
    return TestClient(create_app(lambda: cast(Container, stub))), stub


def test_health_ok() -> None:
    client, stub = _client(healthy=True)
    with client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "summary": "db=ok llm=ok",
            "checks": {"db": {"ok": True, "detail": "ok"}, "llm": {"ok": True, "detail": "ok"}},
        }
    assert stub.closed


def test_health_degraded_returns_503() -> None:
    client, _ = _client(healthy=False)
    with client:
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json()["status"] == "degraded"


def test_liveness_touches_nothing() -> None:
    client, _ = _client(healthy=False)
    with client:
        assert client.get("/health/live").json() == {"status": "ok"}
