"""Errors raised while fetching. None of them carries response bodies."""

from villasanj.shared.application.errors import ApplicationError


class CrawlError(ApplicationError):
    """Base class for crawl failures."""


class CrawlDisallowed(CrawlError):
    """robots.txt (or the platform's host allow-list) forbids this URL. Never retried."""


class SourceBlocked(CrawlError):
    """The platform shows signs of blocking us. The run stops; we never try to get around it."""


class TransientFetchError(CrawlError):
    """Network failure, 429 or 5xx: retry later, honouring ``retry_after_seconds``."""

    def __init__(self, code: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after_seconds = retry_after_seconds


class SnapshotNotFound(CrawlError):
    """Offline mode: no stored snapshot answers this request."""


class PageStructureChanged(CrawlError):
    """A page no longer has the structure its adapter expects (e.g. a site redesign)."""
