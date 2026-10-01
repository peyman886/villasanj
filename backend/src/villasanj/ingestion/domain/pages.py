"""What the crawler asks for and what it gets back. Platform-agnostic."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit

SUCCESS_RANGE = range(200, 300)
REDIRECT_RANGE = range(300, 400)


class PageKind(StrEnum):
    ROBOTS = "robots"
    SITEMAP = "sitemap"
    SEARCH = "search"
    LISTING = "listing"
    CALENDAR = "calendar"
    REVIEWS = "reviews"
    QUOTE = "quote"
    PHOTO = "photo"
    OTHER = "other"


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"


type Pairs = tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class PageRequest:
    """A request the crawler may make.

    ``context`` is provenance metadata (e.g. listing id, stay dates, guests). It is never sent.
    """

    platform: str
    kind: PageKind
    url: str
    method: HttpMethod = HttpMethod.GET
    body: bytes | None = None
    headers: Pairs = ()
    context: Pairs = ()

    @property
    def host(self) -> str:
        return urlsplit(self.url).hostname or ""

    @property
    def key(self) -> str:
        """Identity for de-duplication: same platform, method, URL, body and headers."""
        digest = hashlib.sha256()
        for part in (self.platform, self.method.value, self.url, repr(self.headers)):
            digest.update(part.encode("utf-8"))
            digest.update(b"\x00")
        digest.update(self.body or b"")
        return digest.hexdigest()

    def context_value(self, name: str) -> str | None:
        return next((value for key, value in self.context if key == name), None)

    def redirected_to(self, url: str) -> PageRequest:
        return PageRequest(
            self.platform, self.kind, url, HttpMethod.GET, None, self.headers, self.context
        )


@dataclass(frozen=True, slots=True)
class FetchedPage:
    request: PageRequest
    status: int
    final_url: str
    headers: Pairs
    body: bytes
    fetched_at: datetime
    fetcher: str

    def header(self, name: str) -> str | None:
        lowered = name.lower()
        return next((value for key, value in self.headers if key.lower() == lowered), None)

    @property
    def ok(self) -> bool:
        return self.status in SUCCESS_RANGE

    @property
    def is_redirect(self) -> bool:
        return self.status in REDIRECT_RANGE and self.header("location") is not None


@dataclass(frozen=True, slots=True)
class Snapshot:
    """An immutable stored response; parsing is a pure function of a snapshot."""

    id: str
    request: PageRequest
    status: int
    final_url: str
    headers: Pairs
    blob_key: str
    size: int
    fetched_at: datetime
    fetcher: str
    run_id: str | None = None

    @property
    def content_type(self) -> str:
        return next((v for k, v in self.headers if k.lower() == "content-type"), "")
