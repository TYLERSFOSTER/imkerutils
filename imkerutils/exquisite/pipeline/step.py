from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PIL import Image

from imkerutils.exquisite.api.client import TileGeneratorClient, GeneratorError
from imkerutils.exquisite.geometry.tile_mode import (
    ExtendMode,
    TILE_PX,
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
    """
    Phase C: pure in-memory step with injected generator client.

    enforce_band_identity:
      - if True: reject if tile conditioning half != extracted band.

    post_enforce_band_identity:
      - if True: overwrite the conditioning half of the returned tile with the band
        BEFORE splitting/gluing, instead of rejecting.
      - This lets you tolerate slight model drift on the conditioning region if desired.
      - If both enforce_band_identity and post_enforce_band_identity are True,
        post-enforce happens first, then enforce is checked (so it always passes).
    """
    canvas = canvas.convert("RGB") if canvas.mode != "RGB" else canvas
    w, h = canvas.size

    # Phase A/B constraint: non-growing axis stays exactly 1024
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
        # We still reject safely; we just classify as unknown.
        return canvas, StepResult("rejected", mode, step_index, (w, h), (w, h), f"generator_error:unknown:{type(e).__name__}")

    # Hard invariant: tile must be 1024x1024
    if tile.size != (TILE_PX, TILE_PX):
        return canvas, StepResult("rejected", mode, step_index, (w, h), (w, h), "tile_dim_mismatch")

    tile = tile.convert("RGB") if tile.mode != "RGB" else tile

    if post_enforce_band_identity:
        # overwrite conditioning half in-place (by paste) according to convention
        if mode == "x_ltr":
            tile.paste(band, (0, 0))
        elif mode == "x_rtl":
            tile.paste(band, (512, 0))
        elif mode == "y_ttb":
            tile.paste(band, (0, 0))
        elif mode == "y_btt":
            tile.paste(band, (0, 512))
        else:
            return canvas, StepResult("rejected", mode, step_index, (w, h), (w, h), "unknown_mode")

    cond_half, new_half = split_tile(tile, mode)

    if enforce_band_identity:
        # pixel-equality (byte-identical at RGB tuple level)
        if list(cond_half.get_flattened_data()) != list(band.get_flattened_data()):
            return canvas, StepResult("rejected", mode, step_index, (w, h), (w, h), "band_identity_violation")

    canvas_next = glue(canvas, new_half, mode)

    exp_w, exp_h = expected_next_canvas_size(canvas, mode)
    if canvas_next.size != (exp_w, exp_h):
        return canvas, StepResult("rejected", mode, step_index, (w, h), (w, h), "canvas_dim_invariant_violation")

    return canvas_next, StepResult("committed", mode, step_index, (w, h), canvas_next.size, None)