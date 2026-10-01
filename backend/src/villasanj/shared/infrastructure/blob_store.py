"""Content-addressed blob store on the local filesystem (a Docker volume in compose)."""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from pathlib import Path

from villasanj.shared.application.blobs import BlobRef

_SHARD_WIDTH = 2


class LocalFsBlobStore:
    """``<root>/ab/cd/<sha256>``; writes are atomic (temp file + rename) and idempotent."""

    def __init__(self, root: Path) -> None:
        self._root = root

    async def put(self, data: bytes) -> BlobRef:
        key = hashlib.sha256(data).hexdigest()
        await asyncio.to_thread(self._write, key, data)
        return BlobRef(key=key, size=len(data))

    async def get(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError:
            raise KeyError(key) from None

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._path(key).is_file)

    def _path(self, key: str) -> Path:
        if len(key) != hashlib.sha256().digest_size * 2 or not key.isalnum():
            raise KeyError(key)
        return self._root / key[:_SHARD_WIDTH] / key[_SHARD_WIDTH : 2 * _SHARD_WIDTH] / key

    def _write(self, key: str, data: bytes) -> None:
        path = self._path(key)
        if path.is_file():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
