"""Crawl politeness policy and the identity of a source platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from villasanj.shared.domain.errors import DomainError

DEFAULT_MIN_DELAY_SECONDS = 3.0
DEFAULT_JITTER_SECONDS = 1.0
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_FORBIDDEN_THRESHOLD = 3
DEFAULT_ROBOTS_TTL = timedelta(hours=24)
# Strong signals of a bot wall. We stop on them; we never try to get around them. Extend the list
# when a real challenge page is observed (false positives only make us stop early, never pass).
DEFAULT_BLOCK_MARKERS = (
    "g-recaptcha",
    "h-captcha",
    "hcaptcha.com",
    "cf-chl",
    "challenge-platform",
    "/cdn-cgi/challenge",
    "arvan-challenge",
    "ar-challenge",
)


class InvalidCrawlPolicy(DomainError):
    """Politeness settings that would make the crawler impolite."""


@dataclass(frozen=True, slots=True)
class CrawlPolicy:
    user_agent: str
    robots_token: str
    min_delay_seconds: float = DEFAULT_MIN_DELAY_SECONDS
    jitter_seconds: float = DEFAULT_JITTER_SECONDS
    max_redirects: int = DEFAULT_MAX_REDIRECTS
    forbidden_threshold: int = DEFAULT_FORBIDDEN_THRESHOLD
    robots_ttl: timedelta = DEFAULT_ROBOTS_TTL
    block_markers: tuple[str, ...] = DEFAULT_BLOCK_MARKERS

    def __post_init__(self) -> None:
        if self.min_delay_seconds < DEFAULT_MIN_DELAY_SECONDS:
            raise InvalidCrawlPolicy(
                f"min delay below the {DEFAULT_MIN_DELAY_SECONDS}s floor set by ADR-0008"
            )
        if not self.robots_token or self.robots_token not in self.user_agent:
            raise InvalidCrawlPolicy("the user agent must contain its robots.txt token")


@dataclass(frozen=True, slots=True)
class SourceProfile:
    """Static facts about a platform, supplied by its adapter (the core never names platforms)."""

    slug: str
    display_name: str
    base_url: str
    allowed_hosts: frozenset[str]
    terms_url: str
    notes: tuple[str, ...] = field(default=())

    def allows_host(self, host: str) -> bool:
        return host in self.allowed_hosts
