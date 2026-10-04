"""Machine-readable report artifacts (reports/*.json) beside the markdown reports.

Every generated report writes one: the documentation portal reads its numbers from them, never
from copies, and shows where each came from (the command, the data it ran on, when).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

ARTIFACT_VERSION = 1


def envelope(
    kind: str,
    command: str,
    generated_at: datetime,
    provenance: Mapping[str, object],
    data: Mapping[str, object],
) -> dict[str, object]:
    return {
        "version": ARTIFACT_VERSION,
        "kind": kind,
        "command": command,
        "generated_at": generated_at.isoformat(),
        "provenance": dict(provenance),
        "data": dict(data),
    }
