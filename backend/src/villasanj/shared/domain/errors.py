"""Domain error hierarchy. Messages must never contain secrets or raw external payloads."""


class VillasanjError(Exception):
    """Root of every error raised intentionally by villasanj code."""


class DomainError(VillasanjError):
    """A domain invariant was violated."""


class InvalidMoney(DomainError):
    """A money amount or money range is invalid (negative, non-integer, inverted range)."""


class InvalidDateRange(DomainError):
    """A stay date range is empty or inverted."""


class InvalidGuestCount(DomainError):
    """A guest count is outside the supported bounds."""


class InvalidGeoPoint(DomainError):
    """Coordinates are out of range or not finite."""


class InvalidJalaliDate(DomainError):
    """A Jalali (Solar Hijri) date does not exist or is outside the supported years."""


class InvalidProvenance(DomainError):
    """Provenance metadata is incomplete for the declared acquisition method."""
