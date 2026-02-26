# imkerutils/exquisite/api/mock_gpt_client.py
from __future__ import annotations

import hashlib
from typing import Final

from PIL import Image

from imkerutils.exquisite.geometry.tile_mode import (
    ExtendMode,
    TILE_PX,
    EXT_PX,
    BAND_PX,
    split_tile,
)

def _rgb(img: Image.Image) -> Image.Image:
    return img.convert("RGB") if img.mode != "RGB" else img

def _fill_deterministic(img: Image.Image, seed_bytes: bytes) -> None:
    """
    Deterministically fills an image with a simple pattern derived from seed_bytes.
    No randomness; stable across runs/machines.
    """
    w, h = img.size
    digest = hashlib.sha256(seed_bytes).digest()
    px = img.load()
    n = len(digest)
    for y in range(h):
        for x in range(w):
            b = digest[(x + 7 * y) % n]
            px[x, y] = (b, b, b)

def generate_tile(
    *,
    conditioning_band: Image.Image,
    mode: ExtendMode,
    prompt: str,
    step_index: int,
) -> Image.Image:
    """
    Returns a 1024x1024 tile that respects the band placement convention:
      x_ltr: conditioning band is LEFT half  (cols 0:512)
      x_rtl: conditioning band is RIGHT half (cols 512:1024)
      y_ttb: conditioning band is TOP half   (rows 0:512)
      y_btt: conditioning band is BOTTOM half(rows 512:1024)

    The conditioning half is EXACTLY the provided band (pixel-identical).
    The new half is deterministic synthetic content.
    """
    conditioning_band = _rgb(conditioning_band)

    # Validate conditioning band dims by mode
    if mode in ("x_ltr", "x_rtl"):
        expected = (BAND_PX, TILE_PX)
    else:
        expected = (TILE_PX, BAND_PX)

    if conditioning_band.size != expected:
        raise ValueError(
            f"conditioning_band must be {expected[0]}x{expected[1]}, got {conditioning_band.size}"
        )

    # Create tile and fill with deterministic "new content"
    tile = Image.new("RGB", (TILE_PX, TILE_PX))
    seed = f"{mode}|{step_index}|{prompt}".encode("utf-8")
    _fill_deterministic(tile, seed)

    # Overwrite conditioning half exactly with the provided band
    if mode == "x_ltr":
        tile.paste(conditioning_band, (0, 0))
    elif mode == "x_rtl":
        tile.paste(conditioning_band, (EXT_PX, 0))
    elif mode == "y_ttb":
        tile.paste(conditioning_band, (0, 0))
    elif mode == "y_btt":
        tile.paste(conditioning_band, (0, EXT_PX))
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # Sanity: confirm convention is satisfied
    cond_half, _ = split_tile(tile, mode)
    if cond_half.size != conditioning_band.size:
        raise AssertionError("conditioning half size mismatch after paste")
    if cond_half.get_flattened_data() != conditioning_band.get_flattened_data():
        raise AssertionError("conditioning half != band")

    return tile