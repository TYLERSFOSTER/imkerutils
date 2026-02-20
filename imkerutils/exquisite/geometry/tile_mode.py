from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

from PIL import Image

ExtendMode = Literal["x_ltr", "x_rtl", "y_ttb", "y_btt"]

TILE_PX = 1024
EXT_PX = 512
BAND_PX = 512


@dataclass(frozen=True)
class TileModeSpec:
    mode: ExtendMode
    tile_px: int = TILE_PX
    ext_px: int = EXT_PX
    band_px: int = BAND_PX


def _require_rgb(img: Image.Image) -> Image.Image:
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def extract_conditioning_band(canvas: Image.Image, mode: ExtendMode) -> Image.Image:
    canvas = _require_rgb(canvas)
    w, h = canvas.size

    if mode in ("x_ltr", "x_rtl"):
        if h != TILE_PX:
            raise ValueError(f"Phase A requires canvas height == {TILE_PX}, got {h}")
        if w < BAND_PX:
            raise ValueError(f"Canvas width {w} too small for band {BAND_PX}")

        if mode == "x_ltr":
            box = (w - BAND_PX, 0, w, h)
        else:
            box = (0, 0, BAND_PX, h)

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
            box = (0, h - BAND_PX, w, h)
        else:
            box = (0, 0, w, BAND_PX)

        band = canvas.crop(box)

        if band.size != (TILE_PX, BAND_PX):
            raise AssertionError(f"Band size mismatch: {band.size}")

        return band

    raise ValueError(f"Unknown mode: {mode}")


def split_tile(tile: Image.Image, mode: ExtendMode) -> Tuple[Image.Image, Image.Image]:
    tile = _require_rgb(tile)

    if tile.size != (TILE_PX, TILE_PX):
        raise ValueError(f"Tile must be {TILE_PX}x{TILE_PX}, got {tile.size}")

    if mode == "x_ltr":
        cond = tile.crop((0, 0, EXT_PX, TILE_PX))
        new = tile.crop((EXT_PX, 0, TILE_PX, TILE_PX))
        return cond, new

    if mode == "x_rtl":
        new = tile.crop((0, 0, EXT_PX, TILE_PX))
        cond = tile.crop((EXT_PX, 0, TILE_PX, TILE_PX))
        return cond, new

    if mode == "y_ttb":
        cond = tile.crop((0, 0, TILE_PX, EXT_PX))
        new = tile.crop((0, EXT_PX, TILE_PX, TILE_PX))
        return cond, new

    if mode == "y_btt":
        new = tile.crop((0, 0, TILE_PX, EXT_PX))
        cond = tile.crop((0, EXT_PX, TILE_PX, TILE_PX))
        return cond, new

    raise ValueError(f"Unknown mode: {mode}")


def glue(canvas: Image.Image, new_half: Image.Image, mode: ExtendMode) -> Image.Image:
    canvas = _require_rgb(canvas)
    new_half = _require_rgb(new_half)

    w, h = canvas.size

    if mode in ("x_ltr", "x_rtl"):
        if new_half.size != (EXT_PX, TILE_PX):
            raise ValueError(f"new_half must be {EXT_PX}x{TILE_PX}, got {new_half.size}")

        out = Image.new("RGB", (w + EXT_PX, h))

        if mode == "x_ltr":
            out.paste(canvas, (0, 0))
            out.paste(new_half, (w, 0))
        else:
            out.paste(new_half, (0, 0))
            out.paste(canvas, (EXT_PX, 0))

        return out

    if mode in ("y_ttb", "y_btt"):
        if new_half.size != (TILE_PX, EXT_PX):
            raise ValueError(f"new_half must be {TILE_PX}x{EXT_PX}, got {new_half.size}")

        out = Image.new("RGB", (w, h + EXT_PX))

        if mode == "y_ttb":
            out.paste(canvas, (0, 0))
            out.paste(new_half, (0, h))
        else:
            out.paste(new_half, (0, 0))
            out.paste(canvas, (0, EXT_PX))

        return out

    raise ValueError(f"Unknown mode: {mode}")


def expected_next_canvas_size(canvas: Image.Image, mode: ExtendMode):
    w, h = canvas.size

    if mode in ("x_ltr", "x_rtl"):
        return (w + EXT_PX, h)

    if mode in ("y_ttb", "y_btt"):
        return (w, h + EXT_PX)

    raise ValueError(mode)