from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PIL import Image

from imkerutils.exquisite.api.mock_gpt_client import generate_tile
from imkerutils.exquisite.geometry.tile_mode import (
    ExtendMode,
    TILE_PX,
    expected_next_canvas_size,
    extract_conditioning_band,
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
    reason: str | None = None


def execute_step_mock(
    *,
    canvas: Image.Image,
    mode: ExtendMode,
    prompt: str,
    step_index: int,
    enforce_band_identity: bool = True,
) -> tuple[Image.Image, StepResult]:
    """
    Phase A: pure in-memory step (no filesystem, no network).
      1) Extract conditioning band from current canvas
      2) Mock-generate a 1024x1024 tile with correct band placement
      3) (Optional) enforce byte-identical conditioning-half == extracted band
      4) Glue the new-half onto the canvas
      5) Enforce dimension invariant
    """
    canvas = canvas.convert("RGB") if canvas.mode != "RGB" else canvas
    w0, h0 = canvas.size

    # Phase A assumes initial canvas is 1024x1024 and the non-growing dimension remains 1024.
    if mode in ("x_ltr", "x_rtl") and h0 != TILE_PX:
        return canvas, StepResult(
            status="rejected",
            mode=mode,
            step_index=step_index,
            canvas_before_size=(w0, h0),
            canvas_after_size=(w0, h0),
            reason=f"Phase A requires height == {TILE_PX} for x-modes; got {h0}",
        )
    if mode in ("y_ttb", "y_btt") and w0 != TILE_PX:
        return canvas, StepResult(
            status="rejected",
            mode=mode,
            step_index=step_index,
            canvas_before_size=(w0, h0),
            canvas_after_size=(w0, h0),
            reason=f"Phase A requires width == {TILE_PX} for y-modes; got {w0}",
        )

    band = extract_conditioning_band(canvas, mode)
    tile = generate_tile(conditioning_band=band, mode=mode, prompt=prompt, step_index=step_index)

    cond_half, new_half = split_tile(tile, mode)

    if enforce_band_identity:
        # Pillow-14-safe: use flattened data
        if cond_half.get_flattened_data() != band.get_flattened_data():
            return canvas, StepResult(
                status="rejected",
                mode=mode,
                step_index=step_index,
                canvas_before_size=(w0, h0),
                canvas_after_size=(w0, h0),
                reason="conditioning-half != extracted band (identity enforcement failed)",
            )

    canvas_next = glue(canvas, new_half, mode)

    exp_w, exp_h = expected_next_canvas_size(canvas, mode)
    act_w, act_h = canvas_next.size
    if (act_w, act_h) != (exp_w, exp_h):
        return canvas, StepResult(
            status="rejected",
            mode=mode,
            step_index=step_index,
            canvas_before_size=(w0, h0),
            canvas_after_size=(w0, h0),
            reason=f"dimension invariant failed: expected {(exp_w, exp_h)} got {(act_w, act_h)}",
        )

    return canvas_next, StepResult(
        status="committed",
        mode=mode,
        step_index=step_index,
        canvas_before_size=(w0, h0),
        canvas_after_size=(act_w, act_h),
        reason=None,
    )