"""Load platform fee policies from ``config/fees.toml``."""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from villasanj.pricing.domain.quote import FeePolicy
from villasanj.shared.application.errors import ConfigurationError


class _Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: str
    fees_known: bool
    source: str


class _FeesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policies: list[_Policy]


def load_fee_policies(path: Path) -> dict[str, FeePolicy]:
    try:
        with path.open("rb") as handle:
            data = _FeesFile.model_validate(tomllib.load(handle))
    except (OSError, tomllib.TOMLDecodeError, ValueError) as error:
        raise ConfigurationError(f"invalid fees file {path}: {error}") from None
    return {p.platform: FeePolicy(p.platform, p.fees_known, p.source) for p in data.policies}
