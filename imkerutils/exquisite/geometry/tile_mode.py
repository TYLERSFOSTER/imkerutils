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

# Overlap/advance contract (YOUR WHITE-DIAGRAM CONTRACT):
# - we overwrite OVERLAP_PX of existing canvas frontier
# - we advance (net growth) by ADVANCE_PX per step
#
# With BAND_PX=512 and OVERLAP_PX=256, the "trimmed extension" we splice back in
# has thickness (1024 - 256) = 768 along the extension axis:
#   [overlap 256 (conditioning-side)] + [advance 512 (generated-side)]
OVERLAP_PX = 256
ADVANCE_PX = 512  # each step grows by 512

PATCH_PX = OVERLAP_PX + ADVANCE_PX  # 768

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
    Returns the "trimmed extension" patch to paste into the output canvas.

    WHITE-DIAGRAM CONTRACT:
      start = HALF_PX - OVERLAP_PX = 256
      end   = HALF_PX + ADVANCE_PX = 1024
      width = 768 = OVERLAP(256) + ADVANCE(512)
    """
    tile = _require_rgb(tile)
    if tile.size != (TILE_PX, TILE_PX):
        raise ValueError(f"Tile must be {TILE_PX}x{TILE_PX}, got {tile.size}")

    a = HALF_PX - OVERLAP_PX              # 256
    b = HALF_PX + ADVANCE_PX              # 1024
    if b != TILE_PX:
        raise AssertionError(f"Unexpected patch end b={b} (expected {TILE_PX})")

    if mode in ("x_ltr", "x_rtl"):
        patch = tile.crop((a, 0, b, TILE_PX))  # 768x1024
        print("PATCH_CROP", "mode=", mode, "a=", a, "b=", b, "patch.size=", patch.size)
        if patch.size != (PATCH_PX, TILE_PX):
            raise AssertionError(f"Patch size mismatch: {patch.size}")
        return patch

    if mode in ("y_ttb", "y_btt"):
        patch = tile.crop((0, a, TILE_PX, b))  # 1024x768
        print("PATCH_CROP", "mode=", mode, "a=", a, "b=", b, "patch.size=", patch.size)
        if patch.size != (TILE_PX, PATCH_PX):
            raise AssertionError(f"Patch size mismatch: {patch.size}")
        return patch

    raise ValueError(f"Unknown mode: {mode}")


def glue(canvas: Image.Image, tile: Image.Image, mode: ExtendMode) -> Image.Image:
    """
    GLUE CONTRACT (WHITE-DIAGRAM CONTRACT):

    x_ltr (grow RIGHT by +512):
      paste 768px patch at x = w - 256  (ends at w + 512)

    x_rtl (grow LEFT by +512):
      shift old right by 512 then paste 768px patch at x = 0

    y modes analogous.
    """
    canvas = _require_rgb(canvas)
    tile = _require_rgb(tile)
    w, h = canvas.size

    print(
        "GLUE",
        "mode=", mode,
        "canvas=", canvas.size,
        "tile=", tile.size,
        "OVERLAP=", OVERLAP_PX,
        "ADVANCE=", ADVANCE_PX,
        "PATCH=", PATCH_PX,
    )

    if mode in ("x_ltr", "x_rtl"):
        if h != TILE_PX:
            raise ValueError(f"Phase A requires canvas height == {TILE_PX}, got {h}")

        patch = _tile_patch_for_overlap_glue(tile, mode)  # 768x1024
        out = Image.new("RGB", (w + ADVANCE_PX, h))

        if mode == "x_ltr":
            paste_x = w - OVERLAP_PX
            print(
                "GLUE_PASTE",
                "mode=x_ltr",
                "paste_x=", paste_x,
                "patch_end_x=", paste_x + patch.size[0],
                "out_w=", out.size[0],
            )
            out.paste(canvas, (0, 0))
            out.paste(patch, (paste_x, 0))
        else:
            print(
                "GLUE_PASTE",
                "mode=x_rtl",
                "shift_old_x=", ADVANCE_PX,
                "patch_end_x=", patch.size[0],
                "out_w=", out.size[0],
            )
            out.paste(canvas, (ADVANCE_PX, 0))
            out.paste(patch, (0, 0))
        return out

    if mode in ("y_ttb", "y_btt"):
        if w != TILE_PX:
            raise ValueError(f"Phase A requires canvas width == {TILE_PX}, got {w}")

        patch = _tile_patch_for_overlap_glue(tile, mode)  # 1024x768
        out = Image.new("RGB", (w, h + ADVANCE_PX))

        if mode == "y_ttb":
            paste_y = h - OVERLAP_PX
            print(
                "GLUE_PASTE",
                "mode=y_ttb",
                "paste_y=", paste_y,
                "patch_end_y=", paste_y + patch.size[1],
                "out_h=", out.size[1],
            )
            out.paste(canvas, (0, 0))
            out.paste(patch, (0, paste_y))
        else:
            print(
                "GLUE_PASTE",
                "mode=y_btt",
                "shift_old_y=", ADVANCE_PX,
                "patch_end_y=", patch.size[1],
                "out_h=", out.size[1],
            )
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