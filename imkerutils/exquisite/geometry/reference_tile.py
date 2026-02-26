# imkerutils/exquisite/geometry/reference_tile.py
from __future__ import annotations

import io
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFilter

from imkerutils.exquisite.geometry.tile_mode import (
    ExtendMode,
    TILE_PX,
    BAND_PX,
    HALF_PX,
    OVERLAP_PX,
)


@dataclass(frozen=True)
class ReferenceTileAndMask:
    reference_tile_rgb: Image.Image
    mask_rgba: Image.Image


def encode_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_reference_tile_and_mask(
    *,
    conditioning_band: Image.Image,
    mode: ExtendMode,
    continuation_cue: bool = False,
    cue_px: int = 1,
    cue_rgb: tuple[int, int, int] = (64, 64, 64),
    scaffold_fill: bool = False,
    scaffold_downsample: int = 16,
    scaffold_blur_radius: float = 4.0,
) -> ReferenceTileAndMask:

    band = conditioning_band.convert("RGB")

    if mode in ("x_ltr", "x_rtl"):
        if band.size != (BAND_PX, TILE_PX):
            raise ValueError("conditioning_band wrong size")
    else:
        if band.size != (TILE_PX, BAND_PX):
            raise ValueError("conditioning_band wrong size")

    KEEP_PX = HALF_PX - OVERLAP_PX  # 256

    ref = Image.new("RGB", (TILE_PX, TILE_PX), (0, 0, 0))
    mask = Image.new("RGBA", (TILE_PX, TILE_PX), (0, 0, 0, 0))  # fully editable initially

    def _set_keep_alpha(box):
        r, g, b, a = mask.split()
        keep = Image.new("L", (box[2] - box[0], box[3] - box[1]), 128)
        a.paste(keep, (box[0], box[1]))
        mask.paste(Image.merge("RGBA", (r, g, b, a)))

    if mode == "x_ltr":
        ref.paste(band, (0, 0))
        _set_keep_alpha((0, 0, KEEP_PX, TILE_PX))

    elif mode == "x_rtl":
        ref.paste(band, (HALF_PX, 0))
        _set_keep_alpha((TILE_PX - KEEP_PX, 0, TILE_PX, TILE_PX))

    elif mode == "y_ttb":
        ref.paste(band, (0, 0))
        _set_keep_alpha((0, 0, TILE_PX, KEEP_PX))

    elif mode == "y_btt":
        ref.paste(band, (0, HALF_PX))
        _set_keep_alpha((0, TILE_PX - KEEP_PX, TILE_PX, TILE_PX))

    else:
        raise ValueError(mode)

    return ReferenceTileAndMask(reference_tile_rgb=ref, mask_rgba=mask)