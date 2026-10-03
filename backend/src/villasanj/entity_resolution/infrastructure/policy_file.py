"""Reads the entity resolution decision policy from ``config/er.toml`` (ADR-0014)."""

from __future__ import annotations

import tomllib
from pathlib import Path

from villasanj.entity_resolution.application.villas import DecisionPolicy, ErConfig
from villasanj.shared.application.errors import ConfigurationError


def load_er_config(path: Path) -> ErConfig:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        policy = data["policy"]
        config = ErConfig(
            DecisionPolicy(
                float(policy["threshold"]),
                float(policy["judge_low"]),
                float(policy["judge_high"]),
                float(policy["judge_min_confidence"]),
            ),
            str(data["human"]["queue"]),
        )
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError, ValueError) as error:
        raise ConfigurationError(f"invalid ER policy file {path}: {error}") from None
    if not config.policy.judge_low <= config.policy.judge_high or not config.human_queue:
        raise ConfigurationError(f"invalid ER policy file {path}: empty judge zone or queue")
    return config
