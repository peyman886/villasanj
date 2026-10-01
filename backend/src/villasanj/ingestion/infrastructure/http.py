"""HTTP fetcher (httpx) and robots.txt parser (protego)."""

from __future__ import annotations

import httpx
from protego import Protego

from villasanj.ingestion.application.errors import TransientFetchError
from villasanj.ingestion.domain.pages import FetchedPage, PageRequest
from villasanj.shared.application.clock import Clock

KEPT_RESPONSE_HEADERS = frozenset(
    {
        "content-type",
        "content-length",
        "content-language",
        "location",
        "retry-after",
        "last-modified",
        "etag",
        "cache-control",
        "date",
    }
)
DEFAULT_TIMEOUT_SECONDS = 30.0
# Standard content negotiation. Some sites (observed: jabama) serve a reduced shell to "*/*".
# Adapters override it per request, e.g. "application/json" for JSON endpoints.
DEFAULT_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"


class HttpxFetcher:
    """One exchange per call; never follows redirects (PoliteFetcher checks every hop)."""

    name = "httpx"

    def __init__(
        self,
        user_agent: str,
        clock: Clock,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._clock = clock
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": user_agent,
                "Accept": DEFAULT_ACCEPT,
                "Accept-Language": "fa-IR,fa;q=0.9",
            },
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )

    async def fetch(self, request: PageRequest) -> FetchedPage:
        try:
            response = await self._client.request(
                request.method.value,
                request.url,
                content=request.body,
                headers=dict(request.headers),
            )
        except httpx.TimeoutException:
            raise TransientFetchError("timeout") from None
        except httpx.TransportError as error:
            raise TransientFetchError(f"transport:{type(error).__name__}") from None
        return FetchedPage(
            request=request,
            status=response.status_code,
            final_url=str(response.url),
            headers=tuple(
                (name.lower(), value)
                for name, value in response.headers.items()
                if name.lower() in KEPT_RESPONSE_HEADERS
            ),
            body=response.content,
            fetched_at=self._clock.now(),
            fetcher=self.name,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


class _ProtegoRules:
    def __init__(self, parsed: Protego | None, allow: bool) -> None:
        self._parsed = parsed
        self._allow = allow

    def allows(self, url: str, token: str) -> bool:
        if self._parsed is None:
            return self._allow
        return bool(self._parsed.can_fetch(url, token))

    def crawl_delay(self, token: str) -> float | None:
        if self._parsed is None:
            return None
        delay = self._parsed.crawl_delay(token)
        return float(delay) if delay is not None else None


class ProtegoRobotsParser:
    def parse(self, content: str) -> _ProtegoRules:
        return _ProtegoRules(Protego.parse(content), allow=True)

    def allow_all(self) -> _ProtegoRules:
        return _ProtegoRules(None, allow=True)

    def disallow_all(self) -> _ProtegoRules:
        return _ProtegoRules(None, allow=False)
