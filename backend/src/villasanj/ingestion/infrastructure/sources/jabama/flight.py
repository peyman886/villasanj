"""Extract JSON objects from a Next.js App Router page (React Server Components "flight" data).

jabama embeds listing data as JSON inside ``self.__next_f.push([1, "<js string>"])`` scripts. The
strings are JS-escaped; concatenated, they form the flight stream, which contains plain JSON
objects.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from typing import Any

_PUSH = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', re.DOTALL)
_OBJECT_START = re.compile(r'\{"')
_DECODER = json.JSONDecoder()

type JsonObject = dict[str, Any]


def flight_text(html: str) -> str:
    return "".join(json.loads(f'"{chunk}"') for chunk in _PUSH.findall(html))


def iter_objects(flight: str, predicate: Callable[[JsonObject], bool]) -> Iterator[JsonObject]:
    """Yield each JSON object in the stream for which ``predicate`` holds (outermost match wins)."""
    position = 0
    while (match := _OBJECT_START.search(flight, position)) is not None:
        try:
            candidate, end = _DECODER.raw_decode(flight, match.start())
        except json.JSONDecodeError:
            position = match.start() + 1
            continue
        if isinstance(candidate, dict) and predicate(candidate):
            yield candidate
            position = end
        else:
            position = match.start() + 1
