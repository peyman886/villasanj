"""HttpxFetcher and the protego robots parser against a mocked transport."""

import httpx
import pytest

from tests.fakes.ingestion import PLATFORM
from tests.fakes.llm import FixedClock
from villasanj.ingestion.application.errors import TransientFetchError
from villasanj.ingestion.domain.pages import PageKind, PageRequest
from villasanj.ingestion.infrastructure.http import (
    DEFAULT_ACCEPT,
    HttpxFetcher,
    ProtegoRobotsParser,
)

UA = "VillasanjBot/0.1 (research prototype; contact: test@example.test)"


def fetcher(handler: httpx.MockTransport) -> HttpxFetcher:
    return HttpxFetcher(UA, FixedClock(), transport=handler)


async def test_sends_identity_and_keeps_only_useful_headers() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(
            200, html="<p>ok</p>", headers={"set-cookie": "secret=1", "etag": "abc"}
        )

    page = await fetcher(httpx.MockTransport(handler)).fetch(
        PageRequest(PLATFORM, PageKind.LISTING, "https://www.example.test/a")
    )
    assert seen["user-agent"] == UA
    assert seen["accept"] == DEFAULT_ACCEPT
    assert page.header("etag") == "abc"
    assert page.header("set-cookie") is None  # cookies are never stored
    assert page.body == b"<p>ok</p>"


async def test_per_request_headers_override_defaults() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"ok": True})

    request = PageRequest(
        PLATFORM,
        PageKind.CALENDAR,
        "https://api.example.test/calendar",
        headers=(("Accept", "application/json"),),
    )
    await fetcher(httpx.MockTransport(handler)).fetch(request)
    assert seen["accept"] == "application/json"


async def test_redirects_are_returned_not_followed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(301, headers={"location": "/elsewhere"})

    page = await fetcher(httpx.MockTransport(handler)).fetch(
        PageRequest(PLATFORM, PageKind.LISTING, "https://www.example.test/a")
    )
    assert page.is_redirect
    assert page.header("location") == "/elsewhere"


async def test_network_failures_are_transient() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    with pytest.raises(TransientFetchError, match="timeout"):
        await fetcher(httpx.MockTransport(handler)).fetch(
            PageRequest(PLATFORM, PageKind.LISTING, "https://www.example.test/a")
        )


def test_robots_parser_handles_wildcards_and_crawl_delay() -> None:
    rules = ProtegoRobotsParser().parse(
        "User-agent: *\nAllow: /\nDisallow: /i/*\nDisallow: *gstnum*\nCrawl-delay: 7\n"
    )
    assert rules.allows("https://x.test/stay/villa-1", "VillasanjBot")
    assert not rules.allows("https://x.test/i/abc", "VillasanjBot")
    assert not rules.allows("https://x.test/s?gstnum=8", "VillasanjBot")
    assert rules.crawl_delay("VillasanjBot") == 7
    assert ProtegoRobotsParser().allow_all().allows("https://x.test/any", "VillasanjBot")
    assert not ProtegoRobotsParser().disallow_all().allows("https://x.test/any", "VillasanjBot")
