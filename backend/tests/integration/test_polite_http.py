"""The real HTTP stack (httpx + protego) behind PoliteFetcher, against a local server (ADR-0008)."""

import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.fakes.ingestion import SteppingClock
from villasanj.ingestion.application.errors import (
    CrawlDisallowed,
    SourceBlocked,
    TransientFetchError,
)
from villasanj.ingestion.application.polite_fetcher import PoliteFetcher
from villasanj.ingestion.domain.pages import PageKind, PageRequest
from villasanj.ingestion.domain.policy import CrawlPolicy, SourceProfile
from villasanj.ingestion.infrastructure.http import HttpxFetcher, ProtegoRobotsParser

pytestmark = pytest.mark.integration

ROBOTS = b"User-agent: *\nDisallow: /private\nCrawl-delay: 5\n"
USER_AGENT = "VillasanjBot/0.1 (integration test; contact: test@example.test)"
SLUG = "local"


@dataclass
class Site:
    base: str
    seen: list[tuple[str, str]] = field(default_factory=list)  # (path, user agent)

    def paths(self) -> list[str]:
        return [path for path, _ in self.seen]


@pytest.fixture
def site() -> Iterator[Site]:
    log: list[tuple[str, str]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            log.append((self.path, self.headers.get("User-Agent", "")))
            if self.path == "/robots.txt":
                self._reply(200, ROBOTS, "text/plain")
            elif self.path == "/moved":
                self.send_response(302)
                self.send_header("Location", "/private/target")
                self.end_headers()
            elif self.path.startswith("/forbidden"):
                self._reply(403, b"no", "text/plain")
            else:
                self._reply(200, b"<html>ok</html>", "text/html")

        def _reply(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Site(f"http://127.0.0.1:{server.server_address[1]}", log)
    finally:
        server.shutdown()
        server.server_close()


async def test_real_http_stack_honours_robots_crawl_delay_and_blocks(site: Site) -> None:
    clock = SteppingClock()
    http = HttpxFetcher(USER_AGENT, clock)
    profile = SourceProfile(SLUG, "Local", site.base, frozenset({"127.0.0.1"}), f"{site.base}/t")
    fetcher = PoliteFetcher(
        http,
        ProtegoRobotsParser(),
        CrawlPolicy(user_agent=USER_AGENT, robots_token="VillasanjBot"),
        {SLUG: profile},
        clock,
        clock.sleep,
        jitter=lambda: 0.0,
    )

    def get(path: str) -> PageRequest:
        return PageRequest(SLUG, PageKind.LISTING, f"{site.base}{path}")

    try:
        assert (await fetcher.fetch(get("/public"))).status == 200
        with pytest.raises(CrawlDisallowed):
            await fetcher.fetch(get("/private/page"))
        with pytest.raises(CrawlDisallowed):
            await fetcher.fetch(get("/moved"))  # redirect into a disallowed path
        for path in ("/forbidden/1", "/forbidden/2"):
            with pytest.raises(TransientFetchError):
                await fetcher.fetch(get(path))
        with pytest.raises(SourceBlocked):
            await fetcher.fetch(get("/forbidden/3"))
    finally:
        await http.aclose()

    assert site.paths() == [
        "/robots.txt",
        "/public",
        "/moved",
        "/forbidden/1",
        "/forbidden/2",
        "/forbidden/3",
    ]  # nothing under /private was ever requested
    assert all(agent == USER_AGENT for _, agent in site.seen)
    assert clock.sleeps == [5.0] * (len(site.seen) - 1)  # Crawl-delay 5 s beats the 3 s floor
