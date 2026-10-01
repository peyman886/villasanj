import math
from datetime import UTC, datetime

import pytest

from villasanj.shared.domain.errors import InvalidGeoPoint, InvalidProvenance
from villasanj.shared.domain.geo import GeoPoint
from villasanj.shared.domain.provenance import Provenance, ProvenanceMethod, Sourced, SourceRef

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
SOURCE = SourceRef(platform="example", url="https://example.test/listing/1")


class TestGeoPoint:
    def test_distance_ramsar_to_tonekabon_is_about_21_km(self) -> None:
        ramsar = GeoPoint(36.9031, 50.6583)
        tonekabon = GeoPoint(36.8164, 50.8738)
        assert 20_000 < ramsar.distance_m(tonekabon) < 25_000

    def test_distance_to_self_is_zero(self) -> None:
        point = GeoPoint(36.9, 50.6)
        assert point.distance_m(point) == 0

    @pytest.mark.parametrize(("lat", "lon"), [(91, 0), (0, -181), (math.nan, 0), (0, math.inf)])
    def test_rejects_invalid(self, lat: float, lon: float) -> None:
        with pytest.raises(InvalidGeoPoint):
            GeoPoint(lat, lon)


class TestProvenance:
    def test_observed_requires_source_and_snapshot(self) -> None:
        with pytest.raises(InvalidProvenance):
            Provenance(ProvenanceMethod.OBSERVED, NOW, source=SOURCE)
        observed = Provenance(ProvenanceMethod.OBSERVED, NOW, source=SOURCE, snapshot_id="s1")
        assert Sourced(42, observed).value == 42

    def test_requires_timezone(self) -> None:
        with pytest.raises(InvalidProvenance):
            Provenance(ProvenanceMethod.HUMAN, datetime(2026, 10, 1))

    @pytest.mark.parametrize("method", [ProvenanceMethod.DERIVED, ProvenanceMethod.LLM_EXTRACTED])
    def test_derived_values_reference_inputs(self, method: ProvenanceMethod) -> None:
        with pytest.raises(InvalidProvenance):
            Provenance(method, NOW)

    def test_age_is_the_oldest_input(self) -> None:
        old = Provenance(
            ProvenanceMethod.OBSERVED,
            datetime(2026, 9, 1, tzinfo=UTC),
            source=SOURCE,
            snapshot_id="s0",
        )
        derived = Provenance(ProvenanceMethod.DERIVED, NOW, derived_from=(old,))
        assert derived.oldest_observation == datetime(2026, 9, 1, tzinfo=UTC)
