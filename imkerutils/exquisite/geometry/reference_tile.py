from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image

from imkerutils.exquisite.geometry.tile_mode import ExtendMode, TILE_PX, BAND_PX


@dataclass(frozen=True)
class ReferenceTileAndMask:
    """
    Build an image-conditioned "reference tile" plus an RGBA mask.

    reference_tile_rgb:
      - 1024x1024 RGB image containing the conditioning band pasted into the
        correct half according to the placement convention for the given mode.
      - The other half can be any neutral fill; it will be regenerated.

    mask_rgba:
      - 1024x1024 RGBA mask used for image edits/inpainting.
      - Convention (per classic OpenAI edits):
          alpha == 255 (opaque)   => preserve (NOT edited)
          alpha == 0   (transparent) => editable (regenerated)
    """
    reference_tile_rgb: Image.Image
    mask_rgba: Image.Image


def encode_png_bytes(img: Image.Image) -> bytes:
    """
    Deterministic PNG encoder for multipart upload.
    """
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_reference_tile_and_mask(
    *,
    conditioning_band: Image.Image,
    mode: ExtendMode,
) -> ReferenceTileAndMask:
    """
    Given the extracted conditioning band (512px thick strip),
    build:

      - a 1024x1024 reference image where the conditioning band is pasted
        into the correct half (based on mode), and

      - a 1024x1024 RGBA mask where the conditioning half is preserved (opaque),
        and the new half is regenerated (transparent).

    This makes the seam constraint physically possible because the model
    sees the real pixels it must continue.
    """
    band = conditioning_band.convert("RGB")

    # Validate band size matches our contract.
    if mode in ("x_ltr", "x_rtl"):
        if band.size != (BAND_PX, TILE_PX):
            raise ValueError(f"conditioning_band must be {BAND_PX}x{TILE_PX}, got {band.size}")
    else:
        if band.size != (TILE_PX, BAND_PX):
            raise ValueError(f"conditioning_band must be {TILE_PX}x{BAND_PX}, got {band.size}")

    # Start with a neutral RGB tile. (Black is safe for B/W; for photos it’s fine because masked.)
    ref = Image.new("RGB", (TILE_PX, TILE_PX), (0, 0, 0))

    # Mask starts fully "preserve" (opaque alpha=255), then we carve out editable half.
    mask = Image.new("RGBA", (TILE_PX, TILE_PX), (0, 0, 0, 255))

    if mode == "x_ltr":
        # Conditioning is LEFT half; new is RIGHT half.
        ref.paste(band, (0, 0))
        _set_alpha_rect(mask, (512, 0, 1024, 1024), alpha=0)

    elif mode == "x_rtl":
        # Conditioning is RIGHT half; new is LEFT half.
        ref.paste(band, (512, 0))
        _set_alpha_rect(mask, (0, 0, 512, 1024), alpha=0)

    elif mode == "y_ttb":
        # Conditioning is TOP half; new is BOTTOM half.
        ref.paste(band, (0, 0))
        _set_alpha_rect(mask, (0, 512, 1024, 1024), alpha=0)

    elif mode == "y_btt":
        # Conditioning is BOTTOM half; new is TOP half.
        ref.paste(band, (0, 512))
        _set_alpha_rect(mask, (0, 0, 1024, 512), alpha=0)

    else:
        raise ValueError(f"Unknown mode: {mode}")

    return ReferenceTileAndMask(reference_tile_rgb=ref, mask_rgba=mask)


def _set_alpha_rect(mask_rgba: Image.Image, box: tuple[int, int, int, int], *, alpha: int) -> None:
    """
    Set alpha channel to `alpha` within (left, top, right, bottom).
    """
    if mask_rgba.mode != "RGBA":
        raise ValueError("mask_rgba must be RGBA")

    left, top, right, bottom = box
    if not (0 <= left <= right <= TILE_PX and 0 <= top <= bottom <= TILE_PX):
        raise ValueError(f"Invalid alpha rect box: {box}")

    # Work in-place by editing the alpha channel crop.
    r, g, b, a = mask_rgba.split()
    a_crop = a.crop((left, top, right, bottom))
    a_crop = Image.new("L", a_crop.size, color=alpha)
    a.paste(a_crop, (left, top))
    mask_rgba.paste(Image.merge("RGBA", (r, g, b, a)))