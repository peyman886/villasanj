"""Contract tests for the jabama adapter on trimmed real pages (tests/fixtures/jabama)."""

from pathlib import Path

import pytest

from tests.fakes.ingestion import REGION
from tests.fakes.llm import NOW
from villasanj.ingestion.application.errors import PageStructureChanged
from villasanj.ingestion.domain.pages import FetchedPage, PageKind, PageRequest
from villasanj.ingestion.domain.region import Place, Region
from villasanj.ingestion.infrastructure.sources.jabama.adapter import (
    LISTING_CODE,
    SLUG,
    JabamaAdapter,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "jabama"
CITY_URL = "https://www.jabama.com/city-ramsar"
REGION_BOUNDS = (REGION.south_west, REGION.north_east)


def fetched(name: str, kind: PageKind = PageKind.SEARCH, status: int = 200) -> FetchedPage:
    request = PageRequest(SLUG, kind, CITY_URL)
    return FetchedPage(
        request=request,
        status=status,
        final_url=request.url,
        headers=(("content-type", "text/html; charset=utf-8"),),
        body=(FIXTURES / name).read_bytes(),
        fetched_at=NOW,
        fetcher="fixture",
    )


def stay(path: str, code: str) -> PageRequest:
    return PageRequest(
        SLUG,
        PageKind.LISTING,
        f"https://www.jabama.com/stay/{path}",
        context=((LISTING_CODE, code),),
    )


def test_seeds_are_city_pages_for_each_place() -> None:
    region = Region(
        "r", "منطقه", (Place("ramsar", "رامسر"), Place("tonekabon", "تنکابن")), *REGION_BOUNDS
    )
    assert [r.url for r in JabamaAdapter().seed_requests(region)] == [
        "https://www.jabama.com/city-ramsar",
        "https://www.jabama.com/city-tonekabon",
    ]


def test_search_page_yields_in_region_stays_once_and_the_next_page() -> None:
    discovered = JabamaAdapter().discover(fetched("search_page.html"), REGION)
    assert discovered == [
        stay("villa-800749", "800749"),
        stay("cottage-768339", "768339"),
        stay("apartment-595153", "595153"),
        PageRequest(SLUG, PageKind.SEARCH, "https://www.jabama.com/city-ramsar?page-number=2"),
    ]


def test_last_page_has_no_next_link() -> None:
    discovered = JabamaAdapter().discover(fetched("search_last_page.html"), REGION)
    assert discovered == [stay("villa-800749", "800749")]


def test_redesigned_page_is_reported_not_silently_ignored() -> None:
    with pytest.raises(PageStructureChanged):
        JabamaAdapter().discover(fetched("search_without_flight.html"), REGION)


@pytest.mark.parametrize(("kind", "status"), [(PageKind.LISTING, 200), (PageKind.SEARCH, 404)])
def test_other_pages_discover_nothing(kind: PageKind, status: int) -> None:
    assert JabamaAdapter().discover(fetched("search_page.html", kind, status), REGION) == []
