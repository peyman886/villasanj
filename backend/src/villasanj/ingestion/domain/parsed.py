"""Published language of Ingestion: what an adapter extracts from a snapshot, platform-agnostic.

Values are typed (Money, GeoPoint, dates) but not yet reconciled: Catalog normalizes text, maps
places through the gazetteer and attaches provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from villasanj.shared.domain.geo import GeoPoint
from villasanj.shared.domain.money import Money


class Availability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"  # booked or closed: the platform does not say which
    BOOKED = "booked"
    BLOCKED = "blocked"  # explicitly closed by the host
    UNKNOWN = "unknown"


class TravelMode(StrEnum):
    WALK = "walk"
    CAR = "car"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ParsedCalendarDay:
    night: date
    availability: Availability
    nightly_price: Money | None
    extra_guest_price: Money | None
    min_nights: int | None
    is_holiday: bool | None


@dataclass(frozen=True, slots=True)
class ParsedRateCard:
    """The listing's standing prices per night, as published (before date-specific overrides)."""

    base: Money | None = None
    weekend: Money | None = None
    holiday: Money | None = None
    extra_guest_base: Money | None = None
    extra_guest_weekend: Money | None = None
    extra_guest_holiday: Money | None = None


@dataclass(frozen=True, slots=True)
class ParsedAmenity:
    code: str
    label_fa: str
    present: bool


@dataclass(frozen=True, slots=True)
class ParsedDistanceClaim:
    """A platform-published proximity statement, e.g. "sea: under 5 minutes by car"."""

    target_fa: str
    value_text: str
    mode: TravelMode


@dataclass(frozen=True, slots=True)
class ParsedListing:
    platform: str
    external_id: str
    url: str
    title: str
    description: str | None
    property_type: str | None
    city_fa: str | None
    city_slug: str | None
    locality_fa: str | None  # village or neighbourhood, when published
    location: GeoPoint | None
    location_radius_m: int | None
    bedrooms: int | None
    bathrooms: int | None
    area_m2: int | None
    base_capacity: int | None
    extra_capacity: int | None
    rating_avg: float | None
    rating_count: int | None
    check_in_time: str | None
    check_out_time: str | None
    min_nights: int | None
    instant_booking: bool | None
    host_ref: str | None
    cancellation_policy_text: str | None
    vat_applies: bool | None
    rate_card: ParsedRateCard
    photos: tuple[str, ...] = field(default=())
    amenities: tuple[ParsedAmenity, ...] = field(default=())
    distance_claims: tuple[ParsedDistanceClaim, ...] = field(default=())
    calendar: tuple[ParsedCalendarDay, ...] = field(default=())


@dataclass(frozen=True, slots=True)
class ParsedCalendar:
    """Calendar published on its own page (some platforms serve it separately from the listing)."""

    platform: str
    external_id: str
    days: tuple[ParsedCalendarDay, ...]
