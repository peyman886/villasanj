"""Load ``config/features.toml``: which platform amenity codes state which feature."""

from __future__ import annotations

import tomllib
from pathlib import Path

from villasanj.enrichment.application.features import AmenityMap
from villasanj.enrichment.domain.features import Feature
from villasanj.shared.application.errors import ConfigurationError


def load_amenity_map(path: Path) -> AmenityMap:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        return AmenityMap(
            {
                platform: {code: Feature(feature) for code, feature in codes.items()}
                for platform, codes in data.items()
            }
        )
    except (OSError, tomllib.TOMLDecodeError, ValueError, AttributeError) as error:
        raise ConfigurationError(f"invalid features file {path}: {error}") from None
