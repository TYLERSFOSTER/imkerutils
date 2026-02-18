from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Tuple

from PIL import Image

Corner = Literal["tl", "tr", "bl", "br"]

TILE = 1024

def rect_from_corner(x: int, y: int, corner: Corner, tile: int = TILE) -> Tuple[int, int, int, int]:
    corner = corner.lower()  # type: ignore
    if corner == "tl":
        left, top = x, y
    elif corner == "tr":
        left, top = x - (tile - 1), y
    elif corner == "bl":
        left, top = x, y - (tile - 1)
    elif corner == "br":
        left, top = x - (tile - 1), y - (tile - 1)
    else:
        raise ValueError("corner must be one of: tl, tr, bl, br")
    return left, top, left + tile, top + tile

def top_left_from_corner(x: int, y: int, corner: Corner, tile: int = TILE) -> Tuple[int, int]:
    left, top, _, _ = rect_from_corner(x, y, corner, tile=tile)
    return left, top

def _bounds_check(img: Image.Image, rect: Tuple[int, int, int, int]) -> None:
    w, h = img.size
    left, top, right, bottom = rect
    if left < 0 or top < 0 or right > w or bottom > h:
        raise ValueError(f"Rect out of bounds: {rect} for image size {w}×{h}")

def extract_tile(
    input_path: str | Path,
    output_path: str | Path,
    *,
    x: int,
    y: int,
    corner: Corner = "tl",
    tile: int = TILE,
) -> Tuple[int, int, int, int]:
    img = Image.open(input_path)
    rect = rect_from_corner(x, y, corner, tile=tile)
    _bounds_check(img, rect)
    out = img.crop(rect)  # exact crop
    out.save(output_path)
    return rect

def paste_tile(
    base_path: str | Path,
    tile_path: str | Path,
    output_path: str | Path,
    *,
    x: int,
    y: int,
    corner: Corner = "tl",
    tile: int = TILE,
) -> Tuple[int, int]:
    base = Image.open(base_path)
    patch = Image.open(tile_path)

    if patch.size != (tile, tile):
        raise ValueError(f"Tile must be exactly {tile}×{tile}, got {patch.size}")

    left, top = top_left_from_corner(x, y, corner, tile=tile)
    rect = (left, top, left + tile, top + tile)
    _bounds_check(base, rect)

    if patch.mode != base.mode:
        patch = patch.convert(base.mode)

    base.paste(patch, (left, top))  # exact paste (no blending)
    base.save(output_path)
    return (left, top)
