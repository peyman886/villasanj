"""The Listing aggregate: our current, sourced knowledge of one platform listing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from villasanj.ingestion.domain.parsed import (
    Availability,
    ParsedAmenity,
    ParsedCalendarDay,
    ParsedDistanceClaim,
    ParsedListing,
    ParsedRateCard,
)
from villasanj.shared.domain.geo import GeoPoint
from villasanj.shared.domain.money import Money
from villasanj.shared.domain.persian_text import normalize_persian
from villasanj.shared.domain.provenance import Provenance, ProvenanceMethod, SourceRef
from villasanj.shared.domain.stay import GuestCount


@dataclass(frozen=True, slots=True, order=True)
class ListingId:
    platform: str
    external_id: str

    def __str__(self) -> str:
        return f"{self.platform}:{self.external_id}"


@dataclass(frozen=True, slots=True)
class LocationEvidence:
    """A published point and how far the true location may be from it (obfuscation radius)."""

    point: GeoPoint
    radius_m: int | None

    def distance_range_m(self, other: GeoPoint) -> tuple[float, float | None]:
        """Possible distance to ``other``: exact if the radius is 0, open-ended if unknown."""
        centre = self.point.distance_m(other)
        if self.radius_m is None:
            return (0.0, None)
        return (max(0.0, centre - self.radius_m), centre + self.radius_m)


@dataclass(frozen=True, slots=True)
class Listing:
    id: ListingId
    url: str
    title: str
    title_norm: str
    description: str | None
    description_norm: str | None
    property_type: str | None
    city_fa: str | None
    city_slug: str | None
    locality_fa: str | None
    location: LocationEvidence | None
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
    provenance: Provenance
    photos: tuple[str, ...] = field(default=())
    amenities: tuple[ParsedAmenity, ...] = field(default=())
    distance_claims: tuple[ParsedDistanceClaim, ...] = field(default=())

    @classmethod
    def from_parsed(cls, parsed: ParsedListing, snapshot_id: str, observed_at: datetime) -> Listing:
        return cls(
            id=ListingId(parsed.platform, parsed.external_id),
            url=parsed.url,
            title=parsed.title,
            title_norm=normalize_persian(parsed.title),
            description=parsed.description,
            description_norm=normalize_persian(parsed.description) if parsed.description else None,
            property_type=parsed.property_type,
            city_fa=normalize_persian(parsed.city_fa) if parsed.city_fa else None,
            city_slug=parsed.city_slug,
            locality_fa=normalize_persian(parsed.locality_fa) if parsed.locality_fa else None,
            location=(
                LocationEvidence(parsed.location, parsed.location_radius_m)
                if parsed.location
                else None
            ),
            bedrooms=parsed.bedrooms,
            bathrooms=parsed.bathrooms,
            area_m2=parsed.area_m2,
            base_capacity=parsed.base_capacity,
            extra_capacity=parsed.extra_capacity,
            rating_avg=parsed.rating_avg,
            rating_count=parsed.rating_count,
            check_in_time=parsed.check_in_time,
            check_out_time=parsed.check_out_time,
            min_nights=parsed.min_nights,
            instant_booking=parsed.instant_booking,
            host_ref=parsed.host_ref,
            cancellation_policy_text=parsed.cancellation_policy_text,
            vat_applies=parsed.vat_applies,
            rate_card=parsed.rate_card,
            provenance=Provenance(
                method=ProvenanceMethod.OBSERVED,
                observed_at=observed_at,
                source=SourceRef(parsed.platform, parsed.url),
                snapshot_id=snapshot_id,
            ),
            photos=parsed.photos,
            amenities=parsed.amenities,
            distance_claims=tuple(
                ParsedDistanceClaim(
                    normalize_persian(c.target_fa), normalize_persian(c.value_text), c.mode
                )
                for c in parsed.distance_claims
            ),
        )

    @property
    def max_capacity(self) -> int | None:
        if self.base_capacity is None:
            return None
        return self.base_capacity + (self.extra_capacity or 0)

    def capacity_allows(self, guests: GuestCount) -> bool | None:
        """``None`` when the listing does not publish its capacity."""
        maximum = self.max_capacity
        return None if maximum is None else guests.value <= maximum

    def is_stale(self, now: datetime, max_age: timedelta) -> bool:
        return now - self.provenance.observed_at > max_age


@dataclass(frozen=True, slots=True)
class CalendarObservation:
    """What the platform showed for one night at one moment (never "is available")."""

    listing_id: ListingId
    night: date
    availability: Availability
    nightly_price: Money | None
    extra_guest_price: Money | None
    min_nights: int | None
    is_holiday: bool | None
    snapshot_id: str
    observed_at: datetime

    @classmethod
    def from_parsed(
        cls, listing_id: ListingId, day: ParsedCalendarDay, snapshot_id: str, observed_at: datetime
    ) -> CalendarObservation:
        return cls(
            listing_id=listing_id,
            night=day.night,
            availability=day.availability,
            nightly_price=day.nightly_price,
            extra_guest_price=day.extra_guest_price,
            min_nights=day.min_nights,
            is_holiday=day.is_holiday,
            snapshot_id=snapshot_id,
            observed_at=observed_at,
        )
