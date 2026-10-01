"""Politeness guarantees of ADR-0008, exercised against a scripted network and a stepping clock."""

from itertools import pairwise

import pytest

from tests.fakes.ingestion import (
    BASE,
    POLICY,
    PROFILE,
    ScriptedFetcher,
    SteppingClock,
    page,
    request,
)
from villasanj.ingestion.application.errors import (
    CrawlDisallowed,
    SourceBlocked,
    TransientFetchError,
)
from villasanj.ingestion.application.polite_fetcher import PoliteFetcher
from villasanj.ingestion.domain.pages import FetchedPage, PageKind
from villasanj.ingestion.domain.policy import CrawlPolicy, InvalidCrawlPolicy
from villasanj.ingestion.infrastructure.http import ProtegoRobotsParser


def polite(
    network: ScriptedFetcher, clock: SteppingClock, sink: list[FetchedPage] | None = None
) -> PoliteFetcher:
    async def robots_sink(robots_page: FetchedPage) -> None:
        if sink is not None:
            sink.append(robots_page)

    return PoliteFetcher(
        network,
        ProtegoRobotsParser(),
        POLICY,
        {PROFILE.slug: PROFILE},
        clock,
        clock.sleep,
        jitter=lambda: 0.0,
        robots_sink=robots_sink,
    )


@pytest.fixture
def clock() -> SteppingClock:
    return SteppingClock()


async def test_robots_disallow_blocks_the_request(clock: SteppingClock) -> None:
    network = ScriptedFetcher(
        clock, robots="User-agent: *\nDisallow: /private\nDisallow: *gstnum*\n"
    )
    fetcher = polite(network, clock)
    with pytest.raises(CrawlDisallowed):
        await fetcher.fetch(request("/private/1"))
    with pytest.raises(CrawlDisallowed):
        await fetcher.fetch(request("/search?city=x&gstnum=8"))
    assert network.urls() == [f"{BASE}/robots.txt"]  # only robots.txt was ever requested


async def test_hosts_outside_the_profile_are_never_contacted(clock: SteppingClock) -> None:
    network = ScriptedFetcher(clock)
    with pytest.raises(CrawlDisallowed, match="not allowed"):
        await polite(network, clock).fetch(request("/x", host="evil.test"))
    assert network.calls == []


async def test_requests_to_one_host_are_spaced_by_min_delay(clock: SteppingClock) -> None:
    network = ScriptedFetcher(clock)
    network.on(f"{BASE}/a", page(request("/a")))
    network.on(f"{BASE}/b", page(request("/b")))
    fetcher = polite(network, clock)
    await fetcher.fetch(request("/a"))
    await fetcher.fetch(request("/b"))
    times = [t for _, t in network.calls]  # robots, /a, /b
    gaps = [(b - a).total_seconds() for a, b in pairwise(times)]
    assert gaps == [POLICY.min_delay_seconds, POLICY.min_delay_seconds]


async def test_site_crawl_delay_wins_when_larger(clock: SteppingClock) -> None:
    network = ScriptedFetcher(clock, robots="User-agent: *\nCrawl-delay: 10\n")
    network.on(f"{BASE}/a", page(request("/a")))
    network.on(f"{BASE}/b", page(request("/b")))
    fetcher = polite(network, clock)
    await fetcher.fetch(request("/a"))
    await fetcher.fetch(request("/b"))
    assert clock.sleeps == [10, 10]  # also right after robots.txt itself was read


async def test_robots_is_cached_then_refreshed_after_ttl(clock: SteppingClock) -> None:
    network = ScriptedFetcher(clock)
    network.on(f"{BASE}/a", page(request("/a")))
    sink: list[FetchedPage] = []
    fetcher = polite(network, clock, sink)
    await fetcher.fetch(request("/a"))
    await fetcher.fetch(request("/a"))
    assert network.urls().count(f"{BASE}/robots.txt") == 1
    clock.advance(POLICY.robots_ttl.total_seconds() + 1)
    await fetcher.fetch(request("/a"))
    assert network.urls().count(f"{BASE}/robots.txt") == 2
    assert [p.request.kind for p in sink] == [PageKind.ROBOTS, PageKind.ROBOTS]


async def test_missing_robots_allows_but_unreachable_robots_waits(clock: SteppingClock) -> None:
    allowing = ScriptedFetcher(clock, robots=404)
    allowing.on(f"{BASE}/a", page(request("/a")))
    assert (await polite(allowing, clock).fetch(request("/a"))).ok

    unreachable = ScriptedFetcher(clock, robots=503)
    with pytest.raises(TransientFetchError, match="robots-http-503"):
        await polite(unreachable, clock).fetch(request("/a"))
    assert unreachable.urls() == [f"{BASE}/robots.txt"]


async def test_redirects_are_followed_and_rechecked_against_robots(clock: SteppingClock) -> None:
    network = ScriptedFetcher(clock, robots="User-agent: *\nDisallow: /private\n")
    network.on(f"{BASE}/old", page(request("/old"), status=301, headers=[("location", "/new")]))
    network.on(f"{BASE}/new", page(request("/new"), body=b"moved"))
    network.on(
        f"{BASE}/sneaky", page(request("/sneaky"), status=302, headers=[("location", "/private/x")])
    )
    fetcher = polite(network, clock)
    assert (await fetcher.fetch(request("/old"))).body == b"moved"
    with pytest.raises(CrawlDisallowed):
        await fetcher.fetch(request("/sneaky"))


async def test_redirect_loops_are_cut(clock: SteppingClock) -> None:
    network = ScriptedFetcher(clock)
    network.on(f"{BASE}/loop", page(request("/loop"), status=302, headers=[("location", "/loop")]))
    with pytest.raises(TransientFetchError, match="too-many-redirects"):
        await polite(network, clock).fetch(request("/loop"))


async def test_rate_limit_responses_carry_retry_after(clock: SteppingClock) -> None:
    network = ScriptedFetcher(clock)
    network.on(f"{BASE}/a", page(request("/a"), status=429, headers=[("retry-after", "120")]))
    with pytest.raises(TransientFetchError) as caught:
        await polite(network, clock).fetch(request("/a"))
    assert caught.value.retry_after_seconds == 120


async def test_consecutive_403s_mean_blocked(clock: SteppingClock) -> None:
    network = ScriptedFetcher(clock)
    for path in ("/a", "/b", "/c"):
        network.on(f"{BASE}{path}", page(request(path), status=403))
    network.on(f"{BASE}/ok", page(request("/ok")))
    fetcher = polite(network, clock)
    with pytest.raises(TransientFetchError):
        await fetcher.fetch(request("/a"))
    await fetcher.fetch(request("/ok"))  # a success resets the streak
    for path in ("/a", "/b"):
        with pytest.raises(TransientFetchError):
            await fetcher.fetch(request(path))
    with pytest.raises(SourceBlocked, match="consecutive 403"):
        await fetcher.fetch(request("/c"))


async def test_challenge_pages_stop_the_crawl(clock: SteppingClock) -> None:
    network = ScriptedFetcher(clock)
    network.on(f"{BASE}/a", page(request("/a"), body=b'<div class="g-recaptcha"></div>'))
    network.on(
        f"{BASE}/api",
        page(request("/api"), body=b'{"note":"g-recaptcha"}', content_type="application/json"),
    )
    fetcher = polite(network, clock)
    assert (await fetcher.fetch(request("/api"))).ok  # markers only count on HTML pages
    with pytest.raises(SourceBlocked, match="marker"):
        await fetcher.fetch(request("/a"))


def test_policy_refuses_impolite_settings() -> None:
    with pytest.raises(InvalidCrawlPolicy, match="floor"):
        CrawlPolicy(user_agent="VillasanjBot/0.1", robots_token="VillasanjBot", min_delay_seconds=1)
    with pytest.raises(InvalidCrawlPolicy, match="token"):
        CrawlPolicy(user_agent="SomethingElse/1.0", robots_token="VillasanjBot")
