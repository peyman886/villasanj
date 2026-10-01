"""Distance claims ("زیر ۵ دقیقه تا دریا") as ranges, and the truth-check rule (ROADMAP M9).

Platforms publish travel times, not distances, so a claim becomes a range of straight-line
distances using deliberately generous speeds. When the platform does not say walking or driving,
the claim has two readings. The verdict follows ADR-0007 decision 8: a claim is CONTRADICTED only
when every reading fails even in the best case (fastest speed, the nearest point the obfuscated
location allows), and SUPPORTED only when every reading holds wherever the villa is inside its
published circle; otherwise it is NOT_CONFIRMED («تأیید نشد»), never "false".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from villasanj.ingestion.domain.parsed import ParsedDistanceClaim, TravelMode
from villasanj.shared.domain.persian_text import ZWNJ, normalize_persian, to_latin_digits


class ClaimTarget(StrEnum):
    SEA = "sea"
    FOREST = "forest"
    CITY_CENTER = "city_center"
    SUPERMARKET = "supermarket"
    BAKERY = "bakery"
    RESTAURANT = "restaurant"
    SHOPPING = "shopping"
    RECREATION = "recreation"
    MEDICAL = "medical"
    SHRINE = "shrine"
    OTHER = "other"


# Checked in order: the first keyword found in the normalized target text wins.
_TARGET_KEYWORDS: tuple[tuple[str, ClaimTarget], ...] = (
    ("دریا", ClaimTarget.SEA),
    ("ساحل", ClaimTarget.SEA),
    ("جنگل", ClaimTarget.FOREST),
    ("مرکزشهر", ClaimTarget.CITY_CENTER),
    ("سوپرمارکت", ClaimTarget.SUPERMARKET),
    ("نانوایی", ClaimTarget.BAKERY),
    ("رستوران", ClaimTarget.RESTAURANT),
    ("مراکزخرید", ClaimTarget.SHOPPING),
    ("مراکزتفریحی", ClaimTarget.RECREATION),
    ("بیمارستان", ClaimTarget.MEDICAL),
    ("درمانگاه", ClaimTarget.MEDICAL),
    ("مراکزدرمانی", ClaimTarget.MEDICAL),
    ("حرم", ClaimTarget.SHRINE),
)

_UNDER = re.compile(r"^(زیر|کمتر از|حداکثر)\s*(\d+)\s*(دقیقه|متر|کیلومتر)$")
_OVER = re.compile(r"^(بیشتر از|بیش از|بالای)\s*(\d+)\s*(دقیقه|متر|کیلومتر)$")
_BETWEEN = re.compile(r"^(\d+)\s*(تا|-)\s*(\d+)\s*(دقیقه|متر|کیلومتر)$")
_EXACT = re.compile(r"^(\d+)\s*(دقیقه|متر|کیلومتر)$")

# Straight-line metres covered per minute, generous on purpose (best case for the listing).
WALK_M_PER_MIN = (40.0, 100.0)  # slow stroll .. brisk walk
DRIVE_M_PER_MIN = (150.0, 1000.0)  # village lanes .. 60 km/h on a straight road


class Unit(StrEnum):
    MINUTES = "minutes"
    METRES = "metres"


@dataclass(frozen=True, slots=True)
class DistanceClaim:
    target: ClaimTarget
    target_text: str
    mode: TravelMode
    unit: Unit
    low: float  # in ``unit``
    high: float | None  # ``None``: "more than ``low``"

    def readings(self) -> tuple[tuple[float, float | None], ...]:
        """The straight-line distances each reading of the claim allows (one per travel mode)."""
        if self.unit is Unit.METRES:
            return ((self.low, self.high),)
        modes = {
            TravelMode.WALK: (WALK_M_PER_MIN,),
            TravelMode.CAR: (DRIVE_M_PER_MIN,),
            TravelMode.UNKNOWN: (WALK_M_PER_MIN, DRIVE_M_PER_MIN),
        }[self.mode]
        return tuple(
            (self.low * slow, self.high * fast if self.high is not None else None)
            for slow, fast in modes
        )

    def metres(self) -> tuple[float, float | None]:
        """Every straight-line distance some reading allows."""
        readings = self.readings()
        highs = [high for _, high in readings]
        high = None if None in highs else max(h for h in highs if h is not None)
        return min(low for low, _ in readings), high


def target_of(text: str) -> ClaimTarget:
    key = normalize_persian(text).replace(" ", "").replace(ZWNJ, "")
    return next((target for word, target in _TARGET_KEYWORDS if word in key), ClaimTarget.OTHER)


def parse_claim(claim: ParsedDistanceClaim) -> DistanceClaim | None:
    """``None`` for wording we do not understand (never guessed)."""
    value = to_latin_digits(normalize_persian(claim.value_text)).replace(ZWNJ, "")
    target = target_of(claim.target_fa)
    if (m := _UNDER.match(value)) is not None:
        unit, scale = _unit(m.group(3))
        return DistanceClaim(
            target, claim.target_fa, claim.mode, unit, 0.0, int(m.group(2)) * scale
        )
    if (m := _OVER.match(value)) is not None:
        unit, scale = _unit(m.group(3))
        return DistanceClaim(
            target, claim.target_fa, claim.mode, unit, int(m.group(2)) * scale, None
        )
    if (m := _BETWEEN.match(value)) is not None:
        unit, scale = _unit(m.group(4))
        low, high = sorted((int(m.group(1)), int(m.group(3))))
        return DistanceClaim(target, claim.target_fa, claim.mode, unit, low * scale, high * scale)
    if (m := _EXACT.match(value)) is not None:
        unit, scale = _unit(m.group(2))
        amount = int(m.group(1)) * scale
        return DistanceClaim(target, claim.target_fa, claim.mode, unit, amount, amount)
    return None


def _unit(word: str) -> tuple[Unit, float]:
    if word == "دقیقه":
        return Unit.MINUTES, 1.0
    return Unit.METRES, 1000.0 if word == "کیلومتر" else 1.0


class Verdict(StrEnum):
    SUPPORTED = "supported"  # every possible true distance fits the claim
    NOT_CONFIRMED = "not_confirmed"  # «تأیید نشد»: the evidence cannot decide
    CONTRADICTED = "contradicted"  # even the best case cannot reach the claim


@dataclass(frozen=True, slots=True)
class Assessment:
    verdict: Verdict
    claimed_m: tuple[float, float | None]
    measured_m: tuple[float, float | None]


def assess(claim: DistanceClaim, measured_m: tuple[float, float | None]) -> Assessment:
    """Compare a claim with the measured straight-line distance range (obfuscation included)."""
    verdicts = {_reading_verdict(reading, measured_m) for reading in claim.readings()}
    verdict = verdicts.pop() if len(verdicts) == 1 else Verdict.NOT_CONFIRMED
    return Assessment(verdict, claim.metres(), measured_m)


def _reading_verdict(
    claimed: tuple[float, float | None], measured: tuple[float, float | None]
) -> Verdict:
    (claim_low, claim_high), (nearest, farthest) = claimed, measured
    if claim_high is not None and nearest > claim_high:
        return Verdict.CONTRADICTED  # even the nearest possible point is beyond the claim
    if farthest is not None and claim_low > farthest:
        return Verdict.CONTRADICTED  # "more than X" but every possible point is closer
    fits_high = claim_high is None or (farthest is not None and farthest <= claim_high)
    if fits_high and nearest >= claim_low:
        return Verdict.SUPPORTED
    return Verdict.NOT_CONFIRMED
