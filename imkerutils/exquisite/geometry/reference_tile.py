# imkerutils/exquisite/geometry/reference_tile.py
from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image

from imkerutils.exquisite.geometry.tile_mode import (
    ExtendMode,
    TILE_PX,
    BAND_PX,
)


@dataclass(frozen=True)
class ReferenceTileAndMask:
    reference_tile_rgb: Image.Image
    mask_rgba: Image.Image


def encode_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _alpha_ramp_for_band(*, mode: ExtendMode, length: int) -> list[int]:
    """
    Produce a 1D alpha ramp over the band thickness (length = 512).

    Semantics we assume (per your directive):
      - alpha=255 -> strongly "fix" / preserve
      - alpha=0   -> fully "free" / editable

    The ramp always goes:
      opposite-frontier boundary  ->  frontier boundary
      fix(255)                    ->  free(0)

    For x_ltr: band x=0..511, frontier at x=511        => 255 -> 0
    For x_rtl: band x=512..1023, frontier at x=512     => 0   -> 255 (so within band coords 0..511: 0->255)
    For y_ttb: band y=0..511, frontier at y=511        => 255 -> 0
    For y_btt: band y=512..1023, frontier at y=512     => 0   -> 255
    """
    if length <= 1:
        return [255]

    if mode in ("x_ltr", "y_ttb"):
        # 255 at far edge, 0 at frontier edge
        return [int(round(255 * (1.0 - (i / (length - 1))))) for i in range(length)]

    if mode in ("x_rtl", "y_btt"):
        # 0 at frontier edge, 255 at far edge
        return [int(round(255 * (i / (length - 1)))) for i in range(length)]

    raise ValueError(mode)


def build_reference_tile_and_mask(
    *,
    conditioning_band: Image.Image,
    mode: ExtendMode,
    background_rgb: tuple[int, int, int] = (0, 0, 0),
) -> ReferenceTileAndMask:
    """
    Convention B builder:

    - reference_tile_rgb is a 1024x1024 canvas containing the provided 512px band
      embedded into the correct half/edge for the given mode.
    - mask_rgba is a 1024x1024 RGBA image whose alpha encodes "fix->free" ramp
      *across the band thickness*, moving toward the frontier boundary.

    IMPORTANT: This assumes intermediate alpha values (0..255) have meaning.
    """
    band = conditioning_band.convert("RGB")

    if mode in ("x_ltr", "x_rtl"):
        if band.size != (BAND_PX, TILE_PX):
            raise ValueError(f"conditioning_band wrong size: got {band.size}, expected {(BAND_PX, TILE_PX)}")
    else:
        if band.size != (TILE_PX, BAND_PX):
            raise ValueError(f"conditioning_band wrong size: got {band.size}, expected {(TILE_PX, BAND_PX)}")

    # Reference canvas (RGB)
    ref = Image.new("RGB", (TILE_PX, TILE_PX), background_rgb)

    # Mask canvas (RGBA): start fully editable everywhere (alpha=0)
    # We'll write a ramp ONLY in the band region.
    mask = Image.new("RGBA", (TILE_PX, TILE_PX), (0, 0, 0, 0))
    r, g, b, a = mask.split()

    if mode in ("x_ltr", "x_rtl"):
        ramp = _alpha_ramp_for_band(mode=mode, length=BAND_PX)  # length 512
        # Build alpha image for the band: size (512, 1024)
        a_band = Image.new("L", (BAND_PX, TILE_PX), 0)
        # Fill columnwise using ramp
        # Data order for putdata is row-major; easiest is build a full list.
        pixels: list[int] = []
        for _y in range(TILE_PX):
            pixels.extend(ramp)
        a_band.putdata(pixels)

        if mode == "x_ltr":
            # band occupies left half [0..511], frontier at x=511
            ref.paste(band, (0, 0))
            a.paste(a_band, (0, 0))
        else:
            # x_rtl: band occupies right half [512..1023], frontier at x=512
            ref.paste(band, (TILE_PX - BAND_PX, 0))
            a.paste(a_band, (TILE_PX - BAND_PX, 0))

    else:
        ramp = _alpha_ramp_for_band(mode=mode, length=BAND_PX)  # length 512
        # Build alpha image for the band: size (1024, 512)
        a_band = Image.new("L", (TILE_PX, BAND_PX), 0)
        pixels = []
        for y in range(BAND_PX):
            pixels.extend([ramp[y]] * TILE_PX)
        a_band.putdata(pixels)

        if mode == "y_ttb":
            # band occupies top half [0..511], frontier at y=511
            ref.paste(band, (0, 0))
            a.paste(a_band, (0, 0))
        else:
            # y_btt: band occupies bottom half [512..1023], frontier at y=512
            ref.paste(band, (0, TILE_PX - BAND_PX))
            a.paste(a_band, (0, TILE_PX - BAND_PX))

    mask_rgba = Image.merge("RGBA", (r, g, b, a))
    return ReferenceTileAndMask(reference_tile_rgb=ref, mask_rgba=mask_rgba)