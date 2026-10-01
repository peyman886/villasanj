"""Composite photo grids for the LLM judge (one image per listing, Pillow)."""

from __future__ import annotations

import io
from collections.abc import Sequence

from PIL import Image, ImageOps, UnidentifiedImageError

TILE = (384, 288)  # 4:3
COLUMNS = 3
BACKGROUND = (255, 255, 255)
JPEG_QUALITY = 85


class PillowGridRenderer:
    def render(self, images: Sequence[bytes]) -> bytes:
        """Tiles in reading order, each letterboxed (never cropped: crops lose evidence)."""
        tiles = [tile for tile in (_tile(data) for data in images) if tile is not None]
        rows = max(1, -(-len(tiles) // COLUMNS))
        width, height = TILE
        grid = Image.new("RGB", (width * COLUMNS, height * rows), BACKGROUND)
        for index, tile in enumerate(tiles):
            grid.paste(tile, ((index % COLUMNS) * width, (index // COLUMNS) * height))
        buffer = io.BytesIO()
        grid.save(buffer, "JPEG", quality=JPEG_QUALITY, optimize=True)
        return buffer.getvalue()


def _tile(data: bytes) -> Image.Image | None:
    try:
        with Image.open(io.BytesIO(data)) as picture:
            rgb = picture.convert("RGB")
    except (UnidentifiedImageError, OSError):
        return None
    return ImageOps.pad(rgb, TILE, color=BACKGROUND)
