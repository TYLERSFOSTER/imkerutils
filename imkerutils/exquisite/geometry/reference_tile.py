from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFilter

from imkerutils.exquisite.geometry.tile_mode import ExtendMode, TILE_PX, BAND_PX


@dataclass(frozen=True)
class ReferenceTileAndMask:
    """
    Build an image-conditioned "reference tile" plus an RGBA mask.

    reference_tile_rgb:
      - 1024x1024 RGB image containing the conditioning band pasted into the
        correct half according to the placement convention for the given mode.
      - The other half can be any neutral fill; it will be regenerated (masked).

    mask_rgba:
      - 1024x1024 RGBA mask used for image edits/inpainting.
      - Convention (per classic OpenAI edits):
          alpha == 255 (opaque)     => preserve (NOT edited)
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
    # --- New, opt-in seam aids ---
    continuation_cue: bool = False,
    cue_px: int = 1,
    cue_rgb: tuple[int, int, int] = (64, 64, 64),
    scaffold_fill: bool = False,
    scaffold_downsample: int = 16,
    scaffold_blur_radius: float = 4.0,
) -> ReferenceTileAndMask:
    """
    Given the extracted conditioning band (512px thick strip),
    build:

      - a 1024x1024 reference image where the conditioning band is pasted
        into the correct half (based on mode), and

      - a 1024x1024 RGBA mask where the conditioning half is preserved (opaque),
        and the new half is regenerated (transparent).

    Optional upgrades (all default OFF):
      - continuation_cue: draw a faint seam-aligned cue *inside the conditioning half only*.
        This never pollutes the final canvas because conditioning pixels are overwritten post-gen.
      - scaffold_fill: fill the editable half with a low-frequency scaffold derived from the
        conditioning band (downsample->upsample + blur), giving the model an easy default to follow.
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

    # Helper: compute a low-frequency scaffold from the conditioning band resized to a target box.
    def _make_scaffold(target_size: tuple[int, int]) -> Image.Image:
        if not scaffold_fill:
            return Image.new("RGB", target_size, (0, 0, 0))

        # Clamp downsample factor to avoid zero sizes.
        ds = max(2, int(scaffold_downsample))
        w, h = target_size
        small_w = max(1, w // ds)
        small_h = max(1, h // ds)

        # Downsample -> upsample creates a low-frequency “shape hint”.
        small = band.resize((small_w, small_h), resample=Image.BILINEAR)
        up = small.resize((w, h), resample=Image.BILINEAR)

        if scaffold_blur_radius and scaffold_blur_radius > 0:
            up = up.filter(ImageFilter.GaussianBlur(radius=float(scaffold_blur_radius)))

        return up

    # Helper: draw a seam-aligned cue inside the conditioning region only.
    def _draw_cue_in_conditioning(*, conditioning_box: tuple[int, int, int, int], seam_line: tuple[int, int, int, int]) -> None:
        if not continuation_cue:
            return
        if cue_px <= 0:
            return

        # Ensure we only draw within the conditioning region (never in editable half).
        # We draw a faint line at the seam boundary, but inside conditioning_box by 0..cue_px-1 pixels.
        draw = ImageDraw.Draw(ref)

        x0, y0, x1, y1 = conditioning_box
        sx0, sy0, sx1, sy1 = seam_line

        # Clip seam line to conditioning box.
        sx0 = max(sx0, x0)
        sy0 = max(sy0, y0)
        sx1 = min(sx1, x1)
        sy1 = min(sy1, y1)

        # Draw cue_px-thick line by expanding orthogonally within conditioning region.
        # For vertical seam lines: vary x; for horizontal: vary y.
        if sx0 == sx1:
            # vertical
            for dx in range(cue_px):
                xx = sx0 - dx  # step inward from seam
                if x0 <= xx < x1:
                    draw.line([(xx, sy0), (xx, sy1 - 1)], fill=cue_rgb, width=1)
        elif sy0 == sy1:
            # horizontal
            for dy in range(cue_px):
                yy = sy0 - dy  # step inward from seam
                if y0 <= yy < y1:
                    draw.line([(sx0, yy), (sx1 - 1, yy)], fill=cue_rgb, width=1)
        else:
            # unexpected shape; ignore
            return

    if mode == "x_ltr":
        # Conditioning is LEFT half; new is RIGHT half.
        ref.paste(band, (0, 0))
        _set_alpha_rect(mask, (512, 0, 1024, 1024), alpha=0)

        # Scaffold fills editable half (masked anyway).
        scaffold = _make_scaffold((512, 1024))
        ref.paste(scaffold, (512, 0))

        # Cue inside conditioning at seam x=512, drawn at x=511.. inward.
        _draw_cue_in_conditioning(
            conditioning_box=(0, 0, 512, 1024),
            seam_line=(512, 0, 512, 1024),
        )

    elif mode == "x_rtl":
        # Conditioning is RIGHT half; new is LEFT half.
        ref.paste(band, (512, 0))
        _set_alpha_rect(mask, (0, 0, 512, 1024), alpha=0)

        scaffold = _make_scaffold((512, 1024))
        ref.paste(scaffold, (0, 0))

        # Seam is at x=512, cue inside conditioning region (right side) at x=512..513..,
        # but we draw inward from the seam toward the right (i.e., +dx) by negating the direction:
        # easiest is to flip the logic: supply seam at x=512 and conditioning box right-half;
        # _draw_cue_in_conditioning steps inward with negative dx from seam, so we offset seam to x=513.
        _draw_cue_in_conditioning(
            conditioning_box=(512, 0, 1024, 1024),
            seam_line=(513, 0, 513, 1024),
        )

    elif mode == "y_ttb":
        # Conditioning is TOP half; new is BOTTOM half.
        ref.paste(band, (0, 0))
        _set_alpha_rect(mask, (0, 512, 1024, 1024), alpha=0)

        scaffold = _make_scaffold((1024, 512))
        ref.paste(scaffold, (0, 512))

        _draw_cue_in_conditioning(
            conditioning_box=(0, 0, 1024, 512),
            seam_line=(0, 512, 1024, 512),
        )

    elif mode == "y_btt":
        # Conditioning is BOTTOM half; new is TOP half.
        ref.paste(band, (0, 512))
        _set_alpha_rect(mask, (0, 0, 1024, 512), alpha=0)

        scaffold = _make_scaffold((1024, 512))
        ref.paste(scaffold, (0, 0))

        _draw_cue_in_conditioning(
            conditioning_box=(0, 512, 1024, 1024),
            seam_line=(0, 513, 1024, 513),
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

    # Work in-place by editing the alpha channel crop.
    r, g, b, a = mask_rgba.split()
    a_crop = a.crop((left, top, right, bottom))
    a_crop = Image.new("L", a_crop.size, color=alpha)
    a.paste(a_crop, (left, top))
    mask_rgba.paste(Image.merge("RGBA", (r, g, b, a)))