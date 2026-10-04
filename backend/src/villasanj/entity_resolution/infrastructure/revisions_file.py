"""Reads a label revision file (TOML, committed under eval/labels/) for `er revise-labels`."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from villasanj.entity_resolution.application.revisions import PlannedRevision
from villasanj.entity_resolution.domain.labels import Label
from villasanj.entity_resolution.domain.pairs import PairKey
from villasanj.shared.application.errors import ConfigurationError


@dataclass(frozen=True, slots=True)
class RevisionFile:
    labeler: str
    revised_by: str
    revisions: tuple[PlannedRevision, ...]


def load_revisions(path: Path) -> RevisionFile:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        planned = tuple(
            PlannedRevision(
                PairKey.parse(str(row["pair"])),
                Label(row["from"]),
                Label(row["to"]),
                str(row["reason"]),
            )
            for row in data["revision"]
        )
        result = RevisionFile(str(data["labeler"]), str(data["revised_by"]), planned)
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError, ValueError) as error:
        raise ConfigurationError(f"invalid revision file {path}: {error}") from None
    keys = [p.key for p in planned]
    if len(set(keys)) != len(keys) or any(p.before is p.after for p in planned):
        raise ConfigurationError(f"invalid revision file {path}: a pair twice or a no-op")
    return result
