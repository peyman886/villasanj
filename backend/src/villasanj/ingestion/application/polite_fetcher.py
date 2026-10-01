"""Politeness as a decorator around any Fetcher (ADR-0008).

Guarantees: host allow-list per platform; robots.txt per RFC 9309 (cached, re-checked on every
redirect hop); one request in flight per host with at least ``min_delay`` (or the site's
Crawl-delay, whichever is larger) plus jitter between requests; stop on block signals.
"""

from __future__ import annotations

import asyncio
import random
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlsplit

import structlog

from villasanj.ingestion.application.errors import (
    CrawlDisallowed,
    SourceBlocked,
    TransientFetchError,
)
from villasanj.ingestion.application.ports import Fetcher, RobotsParser, RobotsRules
from villasanj.ingestion.domain.pages import FetchedPage, PageKind, PageRequest
from villasanj.ingestion.domain.policy import CrawlPolicy, SourceProfile
from villasanj.shared.application.clock import Clock

log = structlog.get_logger(__name__)

type Sleep = Callable[[float], Awaitable[None]]
type RobotsSink = Callable[[FetchedPage], Awaitable[object]]

HTTP_FORBIDDEN = 403
HTTP_TOO_MANY_REQUESTS = 429
HTTP_CLIENT_ERROR = range(400, 500)
HTTP_SERVER_ERROR_MIN = 500
MARKER_SCAN_BYTES = 200_000


@dataclass(frozen=True, slots=True)
class _CachedRules:
    rules: RobotsRules
    fetched_at: datetime


class PoliteFetcher:
    name = "polite"

    def __init__(
        self,
        inner: Fetcher,
        robots_parser: RobotsParser,
        policy: CrawlPolicy,
        profiles: Mapping[str, SourceProfile],
        clock: Clock,
        sleep: Sleep,
        jitter: Callable[[], float] = random.random,
        robots_sink: RobotsSink | None = None,
    ) -> None:
        self._inner = inner
        self._parser = robots_parser
        self._policy = policy
        self._profiles = profiles
        self._clock = clock
        self._sleep = sleep
        self._jitter = jitter
        self._robots_sink = robots_sink
        self._robots: dict[str, _CachedRules] = {}
        self._host_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._next_slot: dict[str, datetime] = {}
        self._forbidden_streak: defaultdict[str, int] = defaultdict(int)

    async def fetch(self, request: PageRequest) -> FetchedPage:
        current = request
        for _ in range(self._policy.max_redirects + 1):
            page = await self._fetch_one(current)
            if not page.is_redirect:
                return page
            location = page.header("location") or ""
            current = current.redirected_to(urljoin(current.url, location))
        raise TransientFetchError("too-many-redirects")

    async def _fetch_one(self, request: PageRequest) -> FetchedPage:
        profile = self._profile(request.platform)
        if not profile.allows_host(request.host):
            raise CrawlDisallowed(f"host {request.host} is not allowed for {profile.slug}")
        rules = await self._rules_for(request)
        if not rules.allows(request.url, self._policy.robots_token):
            raise CrawlDisallowed(f"robots.txt disallows {request.url}")
        page = await self._paced(request, rules.crawl_delay(self._policy.robots_token))
        self._check_block(request.platform, page)
        if page.status == HTTP_TOO_MANY_REQUESTS or page.status >= HTTP_SERVER_ERROR_MIN:
            raise TransientFetchError(f"http-{page.status}", _retry_after(page))
        return page

    def _profile(self, platform: str) -> SourceProfile:
        try:
            return self._profiles[platform]
        except KeyError:
            raise CrawlDisallowed(f"no source profile for platform {platform!r}") from None

    async def _paced(self, request: PageRequest, crawl_delay: float | None) -> FetchedPage:
        host = request.host
        async with self._host_locks[host]:
            slot = self._next_slot.get(host)
            if slot is not None:
                wait = (slot - self._clock.now()).total_seconds()
                if wait > 0:
                    await self._sleep(wait)
            try:
                return await self._inner.fetch(request)
            finally:
                delay = max(self._policy.min_delay_seconds, crawl_delay or 0.0)
                delay += self._jitter() * self._policy.jitter_seconds
                self._next_slot[host] = self._clock.now() + timedelta(seconds=delay)

    async def _rules_for(self, request: PageRequest) -> RobotsRules:
        parts = urlsplit(request.url)
        origin = f"{parts.scheme}://{parts.netloc}"
        cached = self._robots.get(origin)
        if cached and self._clock.now() - cached.fetched_at < self._policy.robots_ttl:
            return cached.rules
        rules = await self._fetch_rules(request, origin)
        self._robots[origin] = _CachedRules(rules, self._clock.now())
        self._apply_crawl_delay(request.host, rules)
        return rules

    def _apply_crawl_delay(self, host: str, rules: RobotsRules) -> None:
        """The robots.txt request was paced before its Crawl-delay was known; honour it now."""
        crawl_delay = rules.crawl_delay(self._policy.robots_token)
        slot = self._next_slot.get(host)
        if crawl_delay and slot is not None:
            earliest = self._clock.now() + timedelta(seconds=crawl_delay)
            self._next_slot[host] = max(slot, earliest)

    async def _fetch_rules(self, request: PageRequest, origin: str) -> RobotsRules:
        robots = PageRequest(request.platform, PageKind.ROBOTS, f"{origin}/robots.txt")
        for _ in range(self._policy.max_redirects + 1):
            page = await self._paced(robots, None)
            if not page.is_redirect:
                break
            robots = robots.redirected_to(urljoin(robots.url, page.header("location") or ""))
        if self._robots_sink is not None:
            await self._robots_sink(page)
        if page.ok:
            return self._parser.parse(page.body.decode("utf-8", errors="replace"))
        if page.status in HTTP_CLIENT_ERROR and page.status != HTTP_TOO_MANY_REQUESTS:
            return self._parser.allow_all()  # RFC 9309: robots.txt "unavailable"
        # RFC 9309: "unreachable" means assume complete disallow; retry later.
        raise TransientFetchError(f"robots-http-{page.status}", _retry_after(page))

    def _check_block(self, platform: str, page: FetchedPage) -> None:
        if self._has_block_marker(page):
            log.warning("crawl.blocked", platform=platform, url=page.final_url, reason="marker")
            raise SourceBlocked(f"{platform}: bot-challenge marker on {page.final_url}")
        if page.status == HTTP_FORBIDDEN:
            self._forbidden_streak[platform] += 1
            if self._forbidden_streak[platform] >= self._policy.forbidden_threshold:
                raise SourceBlocked(
                    f"{platform}: {self._forbidden_streak[platform]} consecutive 403s"
                )
            raise TransientFetchError("http-403")
        self._forbidden_streak[platform] = 0

    def _has_block_marker(self, page: FetchedPage) -> bool:
        if "html" not in (page.header("content-type") or "").lower():
            return False
        head = page.body[:MARKER_SCAN_BYTES].decode("utf-8", errors="ignore").lower()
        return any(marker in head for marker in self._policy.block_markers)


def _retry_after(page: FetchedPage) -> float | None:
    value = page.header("retry-after")
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None
