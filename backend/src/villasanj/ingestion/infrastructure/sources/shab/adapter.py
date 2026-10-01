"""shab.ir adapter. Audit: robots.txt allows /houses/show/*; ToS ambiguous, owner approved.

Structure (observed 2026-10-01): per-city sitemaps list ``/houses/show/<id>``; a house page embeds
the listing in ``__NEXT_DATA__`` (money in **toman**, capacity as accommodates/max, no published
location radius); the calendar is a separate JSON endpoint on api.shab.ir keyed by **Jalali**
dates (api.shab.ir/robots.txt answers 404, i.e. no restrictions under RFC 9309).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import date
from typing import Any
from urllib.parse import quote

from villasanj.ingestion.application.errors import PageStructureChanged
from villasanj.ingestion.domain.pages import FetchedPage, PageKind, PageRequest
from villasanj.ingestion.domain.parsed import (
    Availability,
    ParsedAmenity,
    ParsedCalendar,
    ParsedCalendarDay,
    ParsedDistanceClaim,
    ParsedListing,
    ParsedRateCard,
    TravelMode,
)
from villasanj.ingestion.domain.policy import SourceProfile
from villasanj.ingestion.domain.region import Region
from villasanj.shared.domain.errors import InvalidGeoPoint, InvalidJalaliDate
from villasanj.shared.domain.geo import GeoPoint
from villasanj.shared.domain.jalali import JalaliDate
from villasanj.shared.domain.money import Money

SLUG = "shab"
BASE_URL = "https://www.shab.ir"
API_URL = "https://api.shab.ir/api/fa/sandbox/v_1_4"
HOUSE_ID = "listing_code"
CALENDAR_MONTHS = 3
MONTHS_PER_YEAR = 12
_HOUSE_URL = re.compile(r"^https://www\.shab\.ir/houses/show/(\d+)$")
_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_JSON_HEADERS = (("Accept", "application/json"),)
_MONTH_KEY = re.compile(r"^\d{4}-\d{2}$")
_CALENDAR_HOUSE = re.compile(r"/house/(\d+)/calendar")

PROFILE = SourceProfile(
    slug=SLUG,
    display_name="شب",
    base_url=BASE_URL,
    allowed_hosts=frozenset({"www.shab.ir", "api.shab.ir", "s3gw.shab.ir"}),
    terms_url=f"{BASE_URL}/terms",
    notes=("ToS audit 2026-10-01: no explicit clause; owner approved crawling (ADR-0011)",),
)

type Json = dict[str, Any]


class ShabAdapter:
    profile = PROFILE

    def seed_requests(self, region: Region) -> Sequence[PageRequest]:
        """Per-city sitemaps, as published in shab's robots.txt."""
        return [
            PageRequest(
                SLUG, PageKind.SITEMAP, f"{BASE_URL}/sitemaps/sitemap-{quote(place.name_fa)}.xml"
            )
            for place in region.places
        ]

    def discover(self, page: FetchedPage, region: Region) -> Sequence[PageRequest]:
        if not page.ok:
            return []
        if page.request.kind is PageKind.SITEMAP:
            return self._houses_in_sitemap(page)
        if page.request.kind is PageKind.LISTING:
            house = _house(page)
            point = _geo(house.get("location") or {})
            if point is None or not region.contains(point):
                return []
            return [_calendar_request(str(house["id"]), page.fetched_at.date())]
        return []

    def parse_listing(self, page: FetchedPage) -> ParsedListing | None:
        if page.request.kind is not PageKind.LISTING or not page.ok:
            return None
        return _to_parsed_listing(_house(page), page.final_url)

    def parse_calendar(self, page: FetchedPage) -> ParsedCalendar | None:
        if page.request.kind is not PageKind.CALENDAR or not page.ok:
            return None
        house_id = page.request.context_value(HOUSE_ID) or _house_id_in(page.request.url)
        try:
            records = json.loads(page.body)["data"]["records"]
        except (ValueError, KeyError, TypeError):
            raise PageStructureChanged(f"unexpected calendar payload at {page.final_url}") from None
        # Two observed shapes: months directly under "records", or under "records.calendar".
        months = records.get("calendar", records) if isinstance(records, dict) else None
        if house_id is None or not isinstance(months, dict):
            raise PageStructureChanged(f"unexpected calendar payload at {page.final_url}")
        return ParsedCalendar(SLUG, house_id, tuple(_calendar_days(months)))

    @staticmethod
    def _houses_in_sitemap(page: FetchedPage) -> list[PageRequest]:
        requests = []
        for url in _LOC.findall(page.body.decode("utf-8", errors="replace")):
            match = _HOUSE_URL.match(url)
            if match:
                requests.append(
                    PageRequest(SLUG, PageKind.LISTING, url, context=((HOUSE_ID, match.group(1)),))
                )
        return requests


def _house_id_in(url: str) -> str | None:
    match = _CALENDAR_HOUSE.search(url)
    return match.group(1) if match else None


def _calendar_request(house_id: str, today: date) -> PageRequest:
    start = JalaliDate.from_gregorian(today)
    end_year, end_month = divmod(start.month - 1 + CALENDAR_MONTHS, MONTHS_PER_YEAR)
    end = JalaliDate(start.year + end_year, end_month + 1, 1)
    url = (
        f"{API_URL}/house/{house_id}/calendar"
        f"?from_date={start.year:04d}-{start.month:02d}-01"
        f"&to_date={end.year:04d}-{end.month:02d}-01"
    )
    return PageRequest(
        SLUG, PageKind.CALENDAR, url, headers=_JSON_HEADERS, context=((HOUSE_ID, house_id),)
    )


def _house(page: FetchedPage) -> Json:
    match = _NEXT_DATA.search(page.body.decode("utf-8", errors="replace"))
    try:
        house: Json = json.loads(match.group(1))["props"]["pageProps"]["data"] if match else {}
    except (ValueError, KeyError, TypeError):
        house = {}
    if not house.get("id"):
        raise PageStructureChanged(f"no house data on {page.final_url}")
    return house


def _to_parsed_listing(house: Json, url: str) -> ParsedListing:
    location = house.get("location") or {}
    rules = (house.get("rules") or {}).get("records") or {}
    spaces = house.get("spaces") or {}
    base = _int(rules.get("accommodates"))
    maximum = _int(rules.get("max_accommodates"))
    rooms = [_int(spaces.get(key)) for key in ("master_rooms", "normal_rooms")]
    return ParsedListing(
        platform=SLUG,
        external_id=str(house["id"]),
        url=url,
        title=str(house.get("title") or "").strip(),
        description=_text(house.get("about")),
        property_type=_text(house.get("type")),
        city_fa=_text(location.get("city")),
        city_slug=(_text(location.get("city_en")) or "").lower() or None,
        locality_fa=_text(location.get("village")),
        location=_geo(location),
        location_radius_m=None,  # shab does not publish its obfuscation radius
        bedrooms=sum(r for r in rooms if r is not None)
        if any(r is not None for r in rooms)
        else None,
        bathrooms=None,
        area_m2=_positive(house.get("building_area")),
        base_capacity=base,
        extra_capacity=maximum - base
        if base is not None and maximum is not None and maximum >= base
        else None,
        rating_avg=_rating((house.get("rates") or {}).get("rank")),
        rating_count=_int(house.get("reviews_count")),
        check_in_time=_text(rules.get("checkin")),
        check_out_time=_text(rules.get("checkout")),
        min_nights=None,  # varies per night: see the calendar
        instant_booking=house.get("is_instant")
        if isinstance(house.get("is_instant"), bool)
        else None,
        host_ref=_text((house.get("host") or {}).get("id")),  # never the host's name
        cancellation_policy_text=_cancellation(rules.get("cancellation_plan")),
        vat_applies=None,
        rate_card=_rate_card(house.get("pricing") or {}),
        photos=tuple(_photos(house.get("pictures") or {})),
        amenities=tuple(_amenities(house.get("features") or {})),
        distance_claims=tuple(_distances(house.get("distances") or {})),
        calendar=(),  # served separately: see parse_calendar
    )


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _positive(value: Any) -> int | None:
    number = _int(value)
    return number if number else None


def _rating(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and value > 0 else None


def _toman(value: Any) -> Money | None:
    amount = value.get("amount") if isinstance(value, dict) else None
    return Money.from_toman(int(amount)) if isinstance(amount, int | float) and amount > 0 else None


def _geo(location: Json) -> GeoPoint | None:
    try:
        return GeoPoint(float(location["latitude"]), float(location["longitude"]))
    except (KeyError, TypeError, ValueError, InvalidGeoPoint):
        return None


def _rate_card(pricing: Json) -> ParsedRateCard:
    records = pricing.get("records") or [{}]
    record = records[0] if isinstance(records, list) and records else {}
    return ParsedRateCard(
        base=_toman(record.get("workweek_days")),
        weekend=_toman(record.get("weekend_days")),
        holiday=_toman(record.get("peak_days")),
        extra_guest_base=_toman(record.get("extra_person")),
        extra_guest_weekend=_toman(record.get("extra_person")),
        extra_guest_holiday=_toman(record.get("peak_extra_person")),
    )


def _photos(pictures: Json) -> list[str]:
    records = [r for r in pictures.get("records") or [] if r.get("path")]
    return [str(r["path"]) for r in sorted(records, key=lambda r: _int(r.get("order")) or 0)]


def _amenities(features: Json) -> list[ParsedAmenity]:
    amenities = []
    for items in (features.get("filled_categories") or {}).values():
        for item in items or []:
            if item.get("feature_name"):
                amenities.append(
                    ParsedAmenity(
                        code=str(item["feature_name"]),
                        label_fa=str(item.get("feature_label") or ""),
                        present=bool(item.get("is_active")),
                    )
                )
    return amenities


def _distances(distances: Json) -> list[ParsedDistanceClaim]:
    claims = []
    for record in distances.get("records") or []:
        target = _text(record.get("destination"))
        if target is None:
            continue
        for key, mode in (("walking_time", TravelMode.WALK), ("driving_time", TravelMode.CAR)):
            minutes = _int(record.get(key))
            if minutes is not None:
                claims.append(ParsedDistanceClaim(target, f"{minutes} دقیقه", mode))
        meters = _int(record.get("distance"))
        if meters is not None:
            claims.append(ParsedDistanceClaim(target, f"{meters} متر", TravelMode.UNKNOWN))
    return claims


def _cancellation(plan: Any) -> str | None:
    """Only human-readable text: a bare plan code (e.g. 3) means nothing without shab's table."""
    if isinstance(plan, dict):
        plan = plan.get("description") or plan.get("title") or plan.get("name")
    text = _text(plan)
    return None if text is None or text.isdigit() else text


def _calendar_days(months: Json) -> list[ParsedCalendarDay]:
    days = []
    for month_key, entries in months.items():
        if not _MONTH_KEY.match(str(month_key)) or not isinstance(entries, list):
            continue
        year, month = (int(part) for part in str(month_key).split("-"))
        for entry in entries or []:
            try:
                night = JalaliDate(year, month, int(entry["day"])).to_gregorian()
            except (KeyError, TypeError, ValueError, InvalidJalaliDate):
                continue
            bookable = entry.get("is_bookable")
            days.append(
                ParsedCalendarDay(
                    night=night,
                    availability=(
                        Availability.AVAILABLE
                        if bookable is True
                        else Availability.UNAVAILABLE
                        if bookable is False
                        else Availability.UNKNOWN
                    ),
                    nightly_price=_toman(entry.get("price")),
                    extra_guest_price=None,  # not published per night
                    min_nights=_positive(entry.get("min_book_day")),
                    # shab marks "peak" nights (holidays and high season), priced at the peak rate.
                    is_holiday=entry.get("is_peak")
                    if isinstance(entry.get("is_peak"), bool)
                    else None,
                )
            )
    return sorted(days, key=lambda d: d.night)
