"""Content-addressed blob storage port (snapshots, photos)."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BlobRef:
    """Identity of a stored blob: the hex SHA-256 of its bytes."""

    key: str
    size: int


class BlobStore(Protocol):
    async def put(self, data: bytes) -> BlobRef:
        """Store bytes (idempotent: same bytes, same key)."""
        ...

    async def get(self, key: str) -> bytes:
        """Return the bytes for ``key``; raises ``KeyError`` when absent."""
        ...

    async def exists(self, key: str) -> bool: ...
