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
    """
    Build an image-conditioned "reference tile" plus an RGBA mask.

    reference_tile_rgb:
      - 1024x1024 RGB image containing the conditioning band pasted into the
        correct half according to the placement convention for the given mode.
      - The other region is masked (editable) and will be regenerated.

    mask_rgba:
      - 1024x1024 RGBA mask used for image edits/inpainting.
      - Convention (per classic OpenAI edits):
          alpha == 255 (opaque)      => preserve (NOT edited)
          alpha == 0   (transparent) => editable (regenerated)

    IMPORTANT (overlap contract):
      We intentionally make the OVERLAP strip editable so the model can blend
      across the seam. Only the "non-overlap" part of the conditioning region is
      preserved.
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
    # --- Optional seam aids ---
    continuation_cue: bool = False,
    cue_px: int = 1,
    cue_rgb: tuple[int, int, int] = (64, 64, 64),
    scaffold_fill: bool = False,
    scaffold_downsample: int = 16,
    scaffold_blur_radius: float = 4.0,
) -> ReferenceTileAndMask:
    """
    Given the extracted conditioning band (512px thick strip),
    build a 1024x1024 reference image + mask.

    Overlap-editable contract:
      KEEP_PX = HALF_PX - OVERLAP_PX = 256
      - preserve only the "far" 256px of the conditioning side
      - allow the model to edit the overlap strip (256px) + all new content
    """
    band = conditioning_band.convert("RGB")

    # Validate band size matches our contract.
    if mode in ("x_ltr", "x_rtl"):
        if band.size != (BAND_PX, TILE_PX):
            raise ValueError(f"conditioning_band must be {BAND_PX}x{TILE_PX}, got {band.size}")
    else:
        if band.size != (TILE_PX, BAND_PX):
            raise ValueError(f"conditioning_band must be {TILE_PX}x{BAND_PX}, got {band.size}")

    # Only preserve the non-overlap part of the conditioning region.
    KEEP_PX = HALF_PX - OVERLAP_PX  # 512 - 256 = 256

    # Start with a neutral RGB tile.
    ref = Image.new("RGB", (TILE_PX, TILE_PX), (0, 0, 0))

    # Mask starts fully "preserve", then we carve out editable region(s).
    mask = Image.new("RGBA", (TILE_PX, TILE_PX), (0, 0, 0, 255))

    def _make_scaffold(target_size: tuple[int, int]) -> Image.Image:
        if not scaffold_fill:
            return Image.new("RGB", target_size, (0, 0, 0))

        ds = max(2, int(scaffold_downsample))
        w, h = target_size
        small_w = max(1, w // ds)
        small_h = max(1, h // ds)

        small = band.resize((small_w, small_h), resample=Image.BILINEAR)
        up = small.resize((w, h), resample=Image.BILINEAR)

        if scaffold_blur_radius and scaffold_blur_radius > 0:
            up = up.filter(ImageFilter.GaussianBlur(radius=float(scaffold_blur_radius)))

        return up

    def _draw_cue_in_preserved(*, preserved_box: tuple[int, int, int, int], seam_line: tuple[int, int, int, int]) -> None:
        if not continuation_cue or cue_px <= 0:
            return

        draw = ImageDraw.Draw(ref)

        x0, y0, x1, y1 = preserved_box
        sx0, sy0, sx1, sy1 = seam_line

        # Clip seam line to preserved box.
        sx0 = max(sx0, x0)
        sy0 = max(sy0, y0)
        sx1 = min(sx1, x1)
        sy1 = min(sy1, y1)

        # Draw inward from seam into preserved region.
        if sx0 == sx1:
            for dx in range(cue_px):
                xx = sx0 - dx
                if x0 <= xx < x1:
                    draw.line([(xx, sy0), (xx, sy1 - 1)], fill=cue_rgb, width=1)
        elif sy0 == sy1:
            for dy in range(cue_px):
                yy = sy0 - dy
                if y0 <= yy < y1:
                    draw.line([(sx0, yy), (sx1 - 1, yy)], fill=cue_rgb, width=1)

    if mode == "x_ltr":
        # Conditioning is LEFT 512, new is RIGHT 512.
        ref.paste(band, (0, 0))

        # Editable starts at x=KEEP_PX (256): includes overlap strip 256..512 and all new.
        _set_alpha_rect(mask, (KEEP_PX, 0, TILE_PX, TILE_PX), alpha=0)

        scaffold = _make_scaffold((TILE_PX - KEEP_PX, TILE_PX))
        ref.paste(scaffold, (KEEP_PX, 0))

        # Cue near seam (x=512) but drawn inside preserved region only (0..255).
        _draw_cue_in_preserved(
            preserved_box=(0, 0, KEEP_PX, TILE_PX),
            seam_line=(KEEP_PX, 0, KEEP_PX, TILE_PX),
        )

    elif mode == "x_rtl":
        # Conditioning is RIGHT 512 (tile x=512..1024), new is LEFT.
        ref.paste(band, (HALF_PX, 0))

        # Preserve only far-right KEEP_PX = 256: tile x=768..1024.
        # Editable is everything left of 768.
        editable_right_edge = TILE_PX - KEEP_PX  # 768
        _set_alpha_rect(mask, (0, 0, editable_right_edge, TILE_PX), alpha=0)

        scaffold = _make_scaffold((editable_right_edge, TILE_PX))
        ref.paste(scaffold, (0, 0))

        _draw_cue_in_preserved(
            preserved_box=(editable_right_edge, 0, TILE_PX, TILE_PX),
            seam_line=(editable_right_edge, 0, editable_right_edge, TILE_PX),
        )

    elif mode == "y_ttb":
        # Conditioning is TOP 512, new is BOTTOM.
        ref.paste(band, (0, 0))

        # Editable starts at y=KEEP_PX (256): includes overlap strip 256..512 and all new.
        _set_alpha_rect(mask, (0, KEEP_PX, TILE_PX, TILE_PX), alpha=0)

        scaffold = _make_scaffold((TILE_PX, TILE_PX - KEEP_PX))
        ref.paste(scaffold, (0, KEEP_PX))

        _draw_cue_in_preserved(
            preserved_box=(0, 0, TILE_PX, KEEP_PX),
            seam_line=(0, KEEP_PX, TILE_PX, KEEP_PX),
        )

    elif mode == "y_btt":
        # Conditioning is BOTTOM 512 (tile y=512..1024), new is TOP.
        ref.paste(band, (0, HALF_PX))

        # Preserve only far-bottom KEEP_PX = 256: tile y=768..1024.
        editable_bottom_edge = TILE_PX - KEEP_PX  # 768
        _set_alpha_rect(mask, (0, 0, TILE_PX, editable_bottom_edge), alpha=0)

        scaffold = _make_scaffold((TILE_PX, editable_bottom_edge))
        ref.paste(scaffold, (0, 0))

        _draw_cue_in_preserved(
            preserved_box=(0, editable_bottom_edge, TILE_PX, TILE_PX),
            seam_line=(0, editable_bottom_edge, TILE_PX, editable_bottom_edge),
        )

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

    r, g, b, a = mask_rgba.split()
    a_crop = a.crop((left, top, right, bottom))
    a_crop = Image.new("L", a_crop.size, color=alpha)
    a.paste(a_crop, (left, top))
    mask_rgba.paste(Image.merge("RGBA", (r, g, b, a)))