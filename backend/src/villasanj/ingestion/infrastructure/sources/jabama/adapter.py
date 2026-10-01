"""jabama.com adapter. Audit: robots.txt allows everything; ToS has no automated-access clause.

Structure (observed 2026-10-01): city pages ``/city-<slug>`` list ~35 stays per page as JSON in the
Next.js flight data, paginated with ``?page-number=N`` (``<link rel="next">``). Each stay page
``/stay/<type>-<code>`` embeds the full listing, a ~76-day calendar with nightly and extra-guest
prices, the rate card, cancellation policy, metrics, amenities and photo URLs.
"""

from __future__ import annotations

import html as html_lib
import re
from collections.abc import Sequence
from typing import Any

from villasanj.ingestion.application.errors import PageStructureChanged
from villasanj.ingestion.domain.pages import FetchedPage, PageKind, PageRequest
from villasanj.ingestion.domain.parsed import ParsedListing
from villasanj.ingestion.domain.policy import SourceProfile
from villasanj.ingestion.domain.region import Region
from villasanj.ingestion.infrastructure.sources.jabama.flight import (
    JsonObject,
    flight_text,
    iter_objects,
)
from villasanj.ingestion.infrastructure.sources.jabama.listing import (
    is_stay_object,
    to_parsed_listing,
)
from villasanj.shared.domain.errors import InvalidGeoPoint
from villasanj.shared.domain.geo import GeoPoint

SLUG = "jabama"
BASE_URL = "https://www.jabama.com"
LISTING_CODE = "listing_code"
_NEXT_LINK = re.compile(
    r'<link[^>]+href="([^"]+)"[^>]*rel="next"|<link[^>]+rel="next"[^>]*href="([^"]+)"'
)
_STAY_TYPE = re.compile(r"^[a-z]+$")

PROFILE = SourceProfile(
    slug=SLUG,
    display_name="جاباما",
    base_url=BASE_URL,
    allowed_hosts=frozenset({"www.jabama.com", "gw.jabama.com", "cdn.jabama.com"}),
    terms_url=f"{BASE_URL}/help/faq/policy/",
    notes=("ToS audit 2026-10-01: no automated-access clause; see docs/sources/README.md",),
)


def is_search_result(obj: JsonObject) -> bool:
    return "room_id" in obj and "code" in obj and isinstance(obj.get("location"), dict)


def stay_url(stay_type: str, code: int | str) -> str:
    return f"{BASE_URL}/stay/{stay_type}-{code}"


def search_results(html: str) -> list[JsonObject]:
    """Unique search results in page order (cards can repeat, e.g. promoted ones)."""
    unique: dict[str, JsonObject] = {}
    for obj in iter_objects(flight_text(html), is_search_result):
        unique.setdefault(str(obj["code"]), obj)
    return list(unique.values())


def _geo(obj: JsonObject) -> GeoPoint | None:
    geo: Any = obj["location"].get("geo") or {}
    try:
        return GeoPoint(float(geo["lat"]), float(geo["long"]))
    except (KeyError, TypeError, ValueError, InvalidGeoPoint):
        return None


class JabamaAdapter:
    profile = PROFILE

    def seed_requests(self, region: Region) -> Sequence[PageRequest]:
        return [
            PageRequest(SLUG, PageKind.SEARCH, f"{BASE_URL}/city-{place.slug}")
            for place in region.places
        ]

    def discover(self, page: FetchedPage, region: Region) -> Sequence[PageRequest]:
        if page.request.kind is not PageKind.SEARCH or not page.ok:
            return []
        html = page.body.decode("utf-8", errors="replace")
        if "self.__next_f.push" not in html:
            raise PageStructureChanged(f"no flight data on {page.final_url}")
        requests = [self._stay_request(obj) for obj in search_results(html) if _in(region, obj)]
        next_page = self._next_page(html)
        return [r for r in requests if r is not None] + ([next_page] if next_page else [])

    def parse_listing(self, page: FetchedPage) -> ParsedListing | None:
        if page.request.kind is not PageKind.LISTING or not page.ok:
            return None
        code = page.request.context_value(LISTING_CODE) or _code_from_url(page.final_url)
        if code is None:
            raise PageStructureChanged(f"cannot tell the listing code of {page.final_url}")
        html = page.body.decode("utf-8", errors="replace")
        stay = next(iter_objects(flight_text(html), is_stay_object(code)), None)
        if stay is None:
            raise PageStructureChanged(f"no stay object for code {code} on {page.final_url}")
        return to_parsed_listing(stay, SLUG, page.final_url)

    @staticmethod
    def _stay_request(obj: JsonObject) -> PageRequest | None:
        stay_type = str(obj.get("type") or "")
        if not _STAY_TYPE.match(stay_type):
            return None
        code = str(obj["code"])
        return PageRequest(
            SLUG, PageKind.LISTING, stay_url(stay_type, code), context=((LISTING_CODE, code),)
        )

    @staticmethod
    def _next_page(html: str) -> PageRequest | None:
        match = _NEXT_LINK.search(html)
        if match is None:
            return None
        url = html_lib.unescape(match.group(1) or match.group(2))
        if not url.startswith(f"{BASE_URL}/"):
            return None
        return PageRequest(SLUG, PageKind.SEARCH, url)


_CODE_IN_URL = re.compile(r"/stay/[a-z]+-(\d+)")


def _code_from_url(url: str) -> str | None:
    match = _CODE_IN_URL.search(url)
    return match.group(1) if match else None


def _in(region: Region, obj: JsonObject) -> bool:
    point = _geo(obj)
    return point is not None and region.contains(point)
