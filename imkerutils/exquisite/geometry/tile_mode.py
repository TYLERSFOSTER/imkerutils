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

# Overlap/advance contract:
# - we overwrite OVERLAP_PX of existing canvas frontier
# - we advance (net growth) by ADVANCE_PX per step
OVERLAP_PX = 256
ADVANCE_PX = BAND_PX - OVERLAP_PX  # 256

# Backward-compatible name: ext_px now means "advance per step".
EXT_PX = ADVANCE_PX


@dataclass(frozen=True)
class TileModeSpec:
    mode: ExtendMode
    tile_px: int = TILE_PX
    band_px: int = BAND_PX
    overlap_px: int = OVERLAP_PX
    advance_px: int = ADVANCE_PX


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

    Split point is ALWAYS HALF_PX=512, regardless of ADVANCE_PX.
    """
    tile = _require_rgb(tile)
    if tile.size != (TILE_PX, TILE_PX):
        raise ValueError(f"Tile must be {TILE_PX}x{TILE_PX}, got {tile.size}")

    if mode == "x_ltr":
        cond = tile.crop((0, 0, HALF_PX, TILE_PX))          # left half
        new = tile.crop((HALF_PX, 0, TILE_PX, TILE_PX))     # right half
        return cond, new

    if mode == "x_rtl":
        new = tile.crop((0, 0, HALF_PX, TILE_PX))          # left half
        cond = tile.crop((HALF_PX, 0, TILE_PX, TILE_PX))   # right half
        return cond, new

    if mode == "y_ttb":
        cond = tile.crop((0, 0, TILE_PX, HALF_PX))         # top half
        new = tile.crop((0, HALF_PX, TILE_PX, TILE_PX))    # bottom half
        return cond, new

    if mode == "y_btt":
        new = tile.crop((0, 0, TILE_PX, HALF_PX))          # top half
        cond = tile.crop((0, HALF_PX, TILE_PX, TILE_PX))   # bottom half
        return cond, new

    raise ValueError(f"Unknown mode: {mode}")


def _tile_patch_for_overlap_glue(tile: Image.Image, mode: ExtendMode) -> Image.Image:
    """
    This returns the 512px-thick patch we paste into the output.

    IMPORTANT (Case A semantics):
      - advance is +256 per step
      - we overwrite the last 256 of the existing frontier
      - therefore we paste a 512-wide (or 512-tall) patch that straddles the seam:
            [conditioning-side overlap 256] + [generated-side advance 256]

    With current reference-tile conventions, the seam is always at HALF_PX=512 in tile-space.
    The correct “straddle window” is always:
        [HALF_PX-OVERLAP_PX, HALF_PX+ADVANCE_PX] = [256, 768]
    along the extension axis.

    That is TRUE for all modes given the chosen half-placement conventions.
    """
    tile = _require_rgb(tile)
    if tile.size != (TILE_PX, TILE_PX):
        raise ValueError(f"Tile must be {TILE_PX}x{TILE_PX}, got {tile.size}")

    a = HALF_PX - OVERLAP_PX      # 256
    b = HALF_PX + ADVANCE_PX      # 768

    if mode in ("x_ltr", "x_rtl"):
        patch = tile.crop((a, 0, b, TILE_PX))  # 512x1024
        if patch.size != (BAND_PX, TILE_PX):
            raise AssertionError(f"Patch size mismatch: {patch.size}")
        return patch

    if mode in ("y_ttb", "y_btt"):
        patch = tile.crop((0, a, TILE_PX, b))  # 1024x512
        if patch.size != (TILE_PX, BAND_PX):
            raise AssertionError(f"Patch size mismatch: {patch.size}")
        return patch

    raise ValueError(f"Unknown mode: {mode}")


def glue(canvas: Image.Image, tile: Image.Image, mode: ExtendMode) -> Image.Image:
    """
    GLUE CONTRACT (Case A):

    x_ltr:
      A_left = A[:, :w-ADVANCE]
      patch  = tile[:, 256:768]
      out    = cat(A_left, patch)   (implemented via paste onto a new canvas)

    x_rtl:
      out width grows by ADVANCE on the left, so old content shifts right by ADVANCE.
      patch is still tile[:, 256:768], pasted at x=0:
        - patch[:, 256:512] overlaps old frontier (after shift)
        - patch[:, 0:256] is new pixels beyond frontier

    y_ttb / y_btt analogous in Y.
    """
    canvas = _require_rgb(canvas)
    tile = _require_rgb(tile)
    w, h = canvas.size

    if mode in ("x_ltr", "x_rtl"):
        if h != TILE_PX:
            raise ValueError(f"Phase A requires canvas height == {TILE_PX}, got {h}")

        patch = _tile_patch_for_overlap_glue(tile, mode)  # 512x1024
        out = Image.new("RGB", (w + ADVANCE_PX, h))

        if mode == "x_ltr":
            out.paste(canvas, (0, 0))
            out.paste(patch, (w - OVERLAP_PX, 0))  # overwrite last 256 and append 256
        else:
            out.paste(canvas, (ADVANCE_PX, 0))     # shift old right
            out.paste(patch, (0, 0))               # new left + overlap onto shifted old
        return out

    if mode in ("y_ttb", "y_btt"):
        if w != TILE_PX:
            raise ValueError(f"Phase A requires canvas width == {TILE_PX}, got {w}")

        patch = _tile_patch_for_overlap_glue(tile, mode)  # 1024x512
        out = Image.new("RGB", (w, h + ADVANCE_PX))

        if mode == "y_ttb":
            out.paste(canvas, (0, 0))
            out.paste(patch, (0, h - OVERLAP_PX))
        else:
            out.paste(canvas, (0, ADVANCE_PX))
            out.paste(patch, (0, 0))
        return out

    raise ValueError(f"Unknown mode: {mode}")


def expected_next_canvas_size(canvas: Image.Image, mode: ExtendMode) -> tuple[int, int]:
    w, h = canvas.size
    if mode in ("x_ltr", "x_rtl"):
        return (w + ADVANCE_PX, h)
    if mode in ("y_ttb", "y_btt"):
        return (w, h + ADVANCE_PX)
    raise ValueError(mode)