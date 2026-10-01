"""Perceptual hashing with imagehash/Pillow."""

from __future__ import annotations

import io

import imagehash
from PIL import Image, UnidentifiedImageError

from villasanj.catalog.domain.photo import HASH_BITS, PerceptualFingerprint

_SIGN_BIT = 1 << (HASH_BITS - 1)


def _signed64(image_hash: imagehash.ImageHash) -> int:
    """Postgres BIGINT is signed; store the 64 hash bits as two's complement."""
    value = int(str(image_hash), 16)
    return value - (1 << HASH_BITS) if value & _SIGN_BIT else value


class ImagehashHasher:
    def fingerprint(self, image: bytes) -> PerceptualFingerprint | None:
        try:
            with Image.open(io.BytesIO(image)) as picture:
                picture.load()
                rgb = picture.convert("RGB")
        except (UnidentifiedImageError, OSError):
            return None
        return PerceptualFingerprint(
            phash=_signed64(imagehash.phash(rgb)),
            dhash=_signed64(imagehash.dhash(rgb)),
            width=rgb.width,
            height=rgb.height,
        )
