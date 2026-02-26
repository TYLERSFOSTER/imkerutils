# imkerutils/exquisite/pipeline/step.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PIL import Image

from imkerutils.exquisite.api.client import TileGeneratorClient, GeneratorError
from imkerutils.exquisite.geometry.tile_mode import (
    ExtendMode,
    TILE_PX,
    HALF_PX,
    OVERLAP_PX,
    BAND_PX,
    extract_conditioning_band,
    expected_next_canvas_size,
    glue,
    split_tile,
)


@dataclass(frozen=True)
class StepResult:
    status: Literal["committed", "rejected"]
    mode: ExtendMode
    step_index: int
    canvas_before_size: tuple[int, int]
    canvas_after_size: tuple[int, int]
    rejection_reason: str | None = None


def _cond_region_for_identity(mode: ExtendMode) -> tuple[int, int, int, int]:
    """
    Returns crop box (l,t,r,b) inside the conditioning half that must be identical,
    excluding the overlap strip. (This keeps your existing identity check semantics.)
    """
    keep_px = HALF_PX - OVERLAP_PX  # 256

    if mode == "x_ltr":
        return (0, 0, keep_px, TILE_PX)
    if mode == "x_rtl":
        # conditioning half is right; preserve far-right 256: x=256..512 within cond_half coords
        return (OVERLAP_PX, 0, HALF_PX, TILE_PX)
    if mode == "y_ttb":
        return (0, 0, TILE_PX, keep_px)
    if mode == "y_btt":
        # conditioning half is bottom; preserve far-bottom 256: y=256..512 within cond_half coords
        return (0, OVERLAP_PX, TILE_PX, HALF_PX)
    raise ValueError(mode)


def _post_enforce_keep_into_tile(*, tile: Image.Image, band: Image.Image, mode: ExtendMode) -> Image.Image:
    """
    In-memory-step post-enforce: paste ONLY the far KEEP region (256px).
    band is the extracted conditioning band (512px thick strip).
    """
    keep_px = HALF_PX - OVERLAP_PX  # 256

    if mode == "x_ltr":
        src = band.crop((0, 0, keep_px, TILE_PX))
        tile.paste(src, (0, 0))
        return tile

    if mode == "x_rtl":
        src = band.crop((BAND_PX - keep_px, 0, BAND_PX, TILE_PX))
        tile.paste(src, (TILE_PX - keep_px, 0))
        return tile

    if mode == "y_ttb":
        src = band.crop((0, 0, TILE_PX, keep_px))
        tile.paste(src, (0, 0))
        return tile

    if mode == "y_btt":
        src = band.crop((0, BAND_PX - keep_px, TILE_PX, BAND_PX))
        tile.paste(src, (0, TILE_PX - keep_px))
        return tile

    raise ValueError(mode)


def execute_step_in_memory(
    *,
    canvas: Image.Image,
    mode: ExtendMode,
    prompt: str,
    step_index: int,
    client: TileGeneratorClient,
    enforce_band_identity: bool = True,
    post_enforce_band_identity: bool = False,
) -> tuple[Image.Image, StepResult]:
    canvas = canvas.convert("RGB") if canvas.mode != "RGB" else canvas
    w, h = canvas.size

    if mode in ("x_ltr", "x_rtl") and h != TILE_PX:
        return canvas, StepResult("rejected", mode, step_index, (w, h), (w, h), "non_growing_axis_not_1024")
    if mode in ("y_ttb", "y_btt") and w != TILE_PX:
        return canvas, StepResult("rejected", mode, step_index, (w, h), (w, h), "non_growing_axis_not_1024")

    band = extract_conditioning_band(canvas, mode)

    try:
        tile = client.generate_tile(conditioning_band=band, mode=mode, prompt=prompt, step_index=step_index)
    except GeneratorError as e:
        return canvas, StepResult("rejected", mode, step_index, (w, h), (w, h), f"generator_error:{type(e).__name__}")
    except Exception as e:
        return canvas, StepResult("rejected", mode, step_index, (w, h), (w, h), f"generator_error:unknown:{type(e).__name__}")

    if tile.size != (TILE_PX, TILE_PX):
        return canvas, StepResult("rejected", mode, step_index, (w, h), (w, h), "tile_dim_mismatch")

    tile = tile.convert("RGB") if tile.mode != "RGB" else tile

    # If enabled, must match the KEEP-only paste contract.
    if post_enforce_band_identity:
        try:
            tile = _post_enforce_keep_into_tile(tile=tile, band=band, mode=mode)
        except Exception:
            return canvas, StepResult("rejected", mode, step_index, (w, h), (w, h), "unknown_mode")

    cond_half, _new_half = split_tile(tile, mode)

    if enforce_band_identity:
        box = _cond_region_for_identity(mode)
        # NOTE: leaving your existing style; if this raises, fix separately.
        if list(cond_half.crop(box).get_flattened_data()) != list(band.crop(box).get_flattened_data()):
            return canvas, StepResult("rejected", mode, step_index, (w, h), (w, h), "band_identity_violation")

    canvas_next = glue(canvas, tile, mode)

    exp_w, exp_h = expected_next_canvas_size(canvas, mode)
    if canvas_next.size != (exp_w, exp_h):
        return canvas, StepResult("rejected", mode, step_index, (w, h), (w, h), "canvas_dim_invariant_violation")

    return canvas_next, StepResult("committed", mode, step_index, (w, h), canvas_next.size, None)