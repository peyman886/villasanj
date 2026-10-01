"""Map a jabama stay-page object to the platform-agnostic ParsedListing.

Facts (observed 2026-10-01): money is in **rial**; ``0`` means "not set"; calendar status
``disabled`` does not say whether a night is booked or closed by the host; the location carries an
explicit obfuscation radius in metres.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from datetime import date, timedelta
from typing import Any

from villasanj.ingestion.domain.parsed import (
    Availability,
    DatePrecision,
    ParsedAmenity,
    ParsedCalendarDay,
    ParsedDistanceClaim,
    ParsedListing,
    ParsedRateCard,
    ParsedReview,
    TravelMode,
)
from villasanj.ingestion.infrastructure.sources.jabama.flight import JsonObject
from villasanj.shared.domain.errors import InvalidGeoPoint
from villasanj.shared.domain.geo import GeoPoint
from villasanj.shared.domain.jalali import MONTH_NAMES, JalaliDate
from villasanj.shared.domain.money import Money
from villasanj.shared.domain.persian_text import normalize_persian, to_latin_digits

_AVAILABILITY = {
    "available": Availability.AVAILABLE,
    "disabled": Availability.UNAVAILABLE,
}
_MODES = {"car": TravelMode.CAR, "walk": TravelMode.WALK}


def is_stay_object(code: str) -> Callable[[JsonObject], bool]:
    return lambda obj: "calendar" in obj and str(obj.get("code")) == code


def to_parsed_listing(
    obj: JsonObject, platform: str, url: str, reviews: Sequence[ParsedReview] = ()
) -> ParsedListing:
    metrics = obj.get("accommodationMetrics") or {}
    guests = (obj.get("capacity") or {}).get("guests") or {}
    rating = obj.get("rateAndReview") or {}
    residence = obj.get("placeOfResidence") or {}
    area = residence.get("area") or {}
    city_name = (area.get("city") or {}).get("name") or {}
    neighbourhood = (area.get("neighborhood") or {}).get("name") or {}
    location = residence.get("location") or {}
    return ParsedListing(
        platform=platform,
        external_id=str(obj["code"]),
        url=url,
        title=str(obj.get("title") or "").strip(),
        description=_text(obj.get("description")),
        property_type=_text(obj.get("type")),
        city_fa=_text(city_name.get("fa")),
        city_slug=_text(city_name.get("en")),
        locality_fa=_text(neighbourhood.get("fa")),
        location=_geo(location),
        location_radius_m=_positive(location.get("radius")),
        bedrooms=_count(metrics, "bedroomsCount"),
        bathrooms=_count(metrics, "bathroomsCount"),
        area_m2=_positive(metrics.get("areaSize")),
        base_capacity=_count(guests, "base"),
        extra_capacity=_count(guests, "extra"),
        rating_avg=_rating(rating.get("score")),
        rating_count=_count(rating, "count"),
        check_in_time=_text(obj.get("checkIn")),
        check_out_time=_text(obj.get("checkOut")),
        min_nights=_positive(obj.get("minNight")),
        instant_booking=_instant(obj.get("reservationType")),
        host_ref=_text(obj.get("host")),
        cancellation_policy_text=_text(obj.get("cancellationPolicyText")),
        vat_applies=obj.get("vatStatus") if isinstance(obj.get("vatStatus"), bool) else None,
        rate_card=_rate_card(obj.get("price") or {}),
        photos=tuple(
            str(image["url"]) for image in obj.get("placeImages") or [] if image.get("url")
        ),
        amenities=tuple(_amenities(obj.get("amenitiesV2") or [])),
        distance_claims=tuple(_distance_claims(obj.get("nearbyCentersV2") or [])),
        calendar=tuple(_calendar(obj.get("calendar") or [])),
        reviews=tuple(reviews),
    )


def _text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _positive(value: Any) -> int | None:
    return int(value) if isinstance(value, int | float) and value > 0 else None


def _count(source: dict[str, Any], key: str) -> int | None:
    value = source.get(key)
    return int(value) if isinstance(value, int | float) and value >= 0 else None


def _rating(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) and value > 0 else None


def _instant(value: Any) -> bool | None:
    return None if value is None else value == "instant"


def _rial(value: Any) -> Money | None:
    return Money.from_rial(int(value)) if isinstance(value, int | float) and value > 0 else None


def _geo(location: dict[str, Any]) -> GeoPoint | None:
    try:
        return GeoPoint(float(location["lat"]), float(location["lng"]))
    except (KeyError, TypeError, ValueError, InvalidGeoPoint):
        return None


def _rate_card(price: dict[str, Any]) -> ParsedRateCard:
    extra = price.get("extraPeople") or {}
    return ParsedRateCard(
        base=_rial(price.get("base")),
        weekend=_rial(price.get("weekend")),
        holiday=_rial(price.get("holiday")),
        extra_guest_base=_rial(extra.get("base")),
        extra_guest_weekend=_rial(extra.get("weekend")),
        extra_guest_holiday=_rial(extra.get("holiday")),
    )


def _amenities(items: list[Any]) -> list[ParsedAmenity]:
    amenities = []
    for item in items:
        title = item.get("title") or {}
        if title.get("en"):
            amenities.append(
                ParsedAmenity(
                    code=str(title["en"]),
                    label_fa=str(title.get("fa") or ""),
                    present=bool(item.get("state")),
                )
            )
    return amenities


def _distance_claims(groups: list[Any]) -> list[ParsedDistanceClaim]:
    return [
        ParsedDistanceClaim(
            target_fa=str(item.get("key") or ""),
            value_text=str(item.get("value") or ""),
            mode=_MODES.get(str(item.get("accessibleBy")), TravelMode.UNKNOWN),
        )
        for group in groups
        for item in group.get("items") or []
        if item.get("key") and item.get("value")
    ]


def _calendar(days: list[Any]) -> list[ParsedCalendarDay]:
    parsed = []
    for day in days:
        try:
            night = date.fromisoformat(str(day["date"]))
        except (KeyError, ValueError):
            continue
        parsed.append(
            ParsedCalendarDay(
                night=night,
                availability=_AVAILABILITY.get(str(day.get("status")), Availability.UNKNOWN),
                nightly_price=_rial(day.get("price")),
                extra_guest_price=_rial(day.get("extraPeople")),
                min_nights=_positive(day.get("minNight")),
                is_holiday=day.get("isHoliday") if isinstance(day.get("isHoliday"), bool) else None,
            )
        )
    return parsed


_DAYS_AGO = re.compile(r"(\d+)\s*روز\s*پیش")
_JALALI_MONTH = re.compile(r"^(" + "|".join(MONTH_NAMES) + r")\s+(\d{4})$")


def is_review_list(obj: JsonObject) -> bool:
    reviews = obj.get("reviews")
    return (
        isinstance(reviews, list)
        and bool(reviews)
        and isinstance(reviews[0], dict)
        and "comment" in reviews[0]
    )


def parse_reviews(
    containers: Iterable[JsonObject], place_id: str, fetched_on: date
) -> list[ParsedReview]:
    """Reviews of one stay (matched by ``placeId``); names of reviewers and hosts are not kept."""
    reviews: dict[str, ParsedReview] = {}
    for container in containers:
        for record in container.get("reviews") or []:
            if not isinstance(record, dict) or record.get("placeId") != place_id:
                continue
            if record.get("id") is None:
                continue
            stayed_on, precision = _stay_date(record.get("subTitles") or [], fetched_on)
            response = record.get("response")
            reviews.setdefault(
                str(record["id"]),
                ParsedReview(
                    review_id=str(record["id"]),
                    rating=_rating(record.get("rating")),
                    text=_text(record.get("comment")),
                    stayed_on=stayed_on,
                    stayed_precision=precision,
                    host_replied=isinstance(response, dict) and bool(_text(response.get("body"))),
                ),
            )
    return list(reviews.values())


def _stay_date(
    subtitles: Sequence[Any], fetched_on: date
) -> tuple[date | None, DatePrecision | None]:
    """ "اقامت 23 روز پیش" is relative to the page's fetch; "مرداد 1404" names a Jalali month."""
    for subtitle in subtitles:
        text = to_latin_digits(normalize_persian(str(subtitle)))
        if (days := _DAYS_AGO.search(text)) is not None:
            return fetched_on - timedelta(days=int(days.group(1))), DatePrecision.DAY
        if (month := _JALALI_MONTH.match(text)) is not None:
            jalali = JalaliDate(int(month.group(2)), MONTH_NAMES.index(month.group(1)) + 1, 1)
            return jalali.to_gregorian(), DatePrecision.MONTH
    return None, None
