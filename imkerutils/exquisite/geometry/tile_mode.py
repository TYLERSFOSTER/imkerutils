# imkerutils/exquisite/geometry/tile_mode.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

from PIL import Image

ExtendMode = Literal["x_ltr", "x_rtl", "y_ttb", "y_btt"]

# Tile is fixed.
TILE_PX = 1024

# Internal tile split point (conditioning vs new) is fixed at half-tile.
HALF_PX = 512

# Conditioning band thickness (what we extract from the current canvas frontier).
BAND_PX = 512

# UPDATED CONTRACT: "paste full model output tile back in (no trimming)"
#
# Interpretation:
# - The model produces a full 1024x1024 tile.
# - The "conditioning half" is 512px thick (matches BAND_PX).
# - When gluing, we overlap by the full conditioning half (512px),
#   so we paste the full 1024px tile shifted so that:
#
#   x_ltr:
#     tile[0:512] overlaps canvas[w-512:w]
#     tile[512:1024] becomes new content beyond the frontier
#
# - Net growth per step remains 512px (ADVANCE_PX).
OVERLAP_PX = HALF_PX          # 512
ADVANCE_PX = 512              # each step grows by 512

# With OVERLAP=512 and ADVANCE=512, the pasted patch is the FULL TILE (1024).
PATCH_PX = OVERLAP_PX + ADVANCE_PX  # 1024

# Backward-compatible name: ext_px means "advance per step".
EXT_PX = ADVANCE_PX


@dataclass(frozen=True)
class TileModeSpec:
    mode: ExtendMode
    tile_px: int = TILE_PX
    band_px: int = BAND_PX
    overlap_px: int = OVERLAP_PX
    advance_px: int = ADVANCE_PX
    patch_px: int = PATCH_PX


def _require_rgb(img: Image.Image) -> Image.Image:
    return img if img.mode == "RGB" else img.convert("RGB")


def extract_conditioning_band(canvas: Image.Image, mode: ExtendMode) -> Image.Image:
    """
    Extract the extremal 512px strip from the current canvas.

    x_ltr: rightmost 512px of canvas
    x_rtl: leftmost  512px of canvas
    y_ttb: bottom    512px of canvas
    y_btt: top       512px of canvas
    """
    canvas = _require_rgb(canvas)
    w, h = canvas.size

    if mode in ("x_ltr", "x_rtl"):
        if h != TILE_PX:
            raise ValueError(f"Phase A requires canvas height == {TILE_PX}, got {h}")
        if w < BAND_PX:
            raise ValueError(f"Canvas width {w} too small for band {BAND_PX}")

        if mode == "x_ltr":
            box = (w - BAND_PX, 0, w, h)  # rightmost
        else:
            box = (0, 0, BAND_PX, h)      # leftmost

        band = canvas.crop(box)
        if band.size != (BAND_PX, TILE_PX):
            raise AssertionError(f"Band size mismatch: {band.size}")
        return band

    if mode in ("y_ttb", "y_btt"):
        if w != TILE_PX:
            raise ValueError(f"Phase A requires canvas width == {TILE_PX}, got {w}")
        if h < BAND_PX:
            raise ValueError(f"Canvas height {h} too small for band {BAND_PX}")

        if mode == "y_ttb":
            box = (0, h - BAND_PX, w, h)  # bottom
        else:
            box = (0, 0, w, BAND_PX)      # top

        band = canvas.crop(box)
        if band.size != (TILE_PX, BAND_PX):
            raise AssertionError(f"Band size mismatch: {band.size}")
        return band

    raise ValueError(f"Unknown mode: {mode}")


def split_tile(tile: Image.Image, mode: ExtendMode) -> Tuple[Image.Image, Image.Image]:
    """
    Split a 1024x1024 tile into:
      - cond_half: the half that must match conditioning pixels (after post-enforce)
      - new_half:  the other half (generated half)

    Split point is ALWAYS HALF_PX=512.
    """
    tile = _require_rgb(tile)
    if tile.size != (TILE_PX, TILE_PX):
        raise ValueError(f"Tile must be {TILE_PX}x{TILE_PX}, got {tile.size}")

    if mode == "x_ltr":
        cond = tile.crop((0, 0, HALF_PX, TILE_PX))          # left half
        new = tile.crop((HALF_PX, 0, TILE_PX, TILE_PX))     # right half
        return cond, new

    if mode == "x_rtl":
        new = tile.crop((0, 0, HALF_PX, TILE_PX))           # left half
        cond = tile.crop((HALF_PX, 0, TILE_PX, TILE_PX))    # right half
        return cond, new

    if mode == "y_ttb":
        cond = tile.crop((0, 0, TILE_PX, HALF_PX))          # top half
        new = tile.crop((0, HALF_PX, TILE_PX, TILE_PX))     # bottom half
        return cond, new

    if mode == "y_btt":
        new = tile.crop((0, 0, TILE_PX, HALF_PX))           # top half
        cond = tile.crop((0, HALF_PX, TILE_PX, TILE_PX))    # bottom half
        return cond, new

    raise ValueError(f"Unknown mode: {mode}")


def _tile_patch_for_overlap_glue(tile: Image.Image, mode: ExtendMode) -> Image.Image:
    """
    Returns the patch to paste into the output canvas.

    NEW CONTRACT: this patch is the FULL TILE.

    start = HALF_PX - OVERLAP_PX = 0
    end   = HALF_PX + ADVANCE_PX = 1024
    """
    tile = _require_rgb(tile)
    if tile.size != (TILE_PX, TILE_PX):
        raise ValueError(f"Tile must be {TILE_PX}x{TILE_PX}, got {tile.size}")

    a = HALF_PX - OVERLAP_PX  # 0
    b = HALF_PX + ADVANCE_PX  # 1024
    if a != 0 or b != TILE_PX:
        raise AssertionError(f"Unexpected patch bounds a={a}, b={b}, expected a=0, b={TILE_PX}")

    # Patch is the full tile for all modes.
    return tile


def glue(canvas: Image.Image, tile: Image.Image, mode: ExtendMode) -> Image.Image:
    """
    NEW GLUE CONTRACT: paste FULL TILE back in (no trimming).

    Canvas grows by ADVANCE_PX (=512) per step.

    x_ltr:
      out size = (w + 512, h)
      paste full 1024 tile at x = w - 512
      so tile[0:512] overlaps the frontier 512px of the existing canvas,
      tile[512:1024] is the new region.

    x_rtl:
      out size = (w + 512, h)
      shift old right by 512, paste full tile at x = 0.

    y modes analogous.
    """
    canvas = _require_rgb(canvas)
    tile = _require_rgb(tile)
    w, h = canvas.size

    if mode in ("x_ltr", "x_rtl"):
        if h != TILE_PX:
            raise ValueError(f"Phase A requires canvas height == {TILE_PX}, got {h}")

        out = Image.new("RGB", (w + ADVANCE_PX, h))

        if mode == "x_ltr":
            out.paste(canvas, (0, 0))
            paste_x = w - OVERLAP_PX  # w - 512
            out.paste(tile, (paste_x, 0))
        else:
            out.paste(canvas, (ADVANCE_PX, 0))
            out.paste(tile, (0, 0))

        return out

    if mode in ("y_ttb", "y_btt"):
        if w != TILE_PX:
            raise ValueError(f"Phase A requires canvas width == {TILE_PX}, got {w}")

        out = Image.new("RGB", (w, h + ADVANCE_PX))

        if mode == "y_ttb":
            out.paste(canvas, (0, 0))
            paste_y = h - OVERLAP_PX  # h - 512
            out.paste(tile, (0, paste_y))
        else:
            out.paste(canvas, (0, ADVANCE_PX))
            out.paste(tile, (0, 0))

        return out

    raise ValueError(f"Unknown mode: {mode}")


def expected_next_canvas_size(canvas: Image.Image, mode: ExtendMode) -> tuple[int, int]:
    w, h = canvas.size
    if mode in ("x_ltr", "x_rtl"):
        return (w + ADVANCE_PX, h)
    if mode in ("y_ttb", "y_btt"):
        return (w, h + ADVANCE_PX)
    raise ValueError(mode)