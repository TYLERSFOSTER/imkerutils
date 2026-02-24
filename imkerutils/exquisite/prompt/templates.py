from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from imkerutils.exquisite.geometry.tile_mode import ExtendMode


@dataclass(frozen=True)
class PlacementConvention:
    """
    Kept for compatibility / potential UI display, but NOT used to instruct the model.
    """
    mode: ExtendMode
    conditioning_where: str
    new_where: str


def placement_convention_for_mode(mode: ExtendMode) -> PlacementConvention:
    # These strings are load-bearing: tests may assert on them.
    if mode == "x_ltr":
        return PlacementConvention(
            mode=mode,
            conditioning_where="LEFT half (columns 0..511)",
            new_where="RIGHT half (columns 512..1023)",
        )
    if mode == "x_rtl":
        return PlacementConvention(
            mode=mode,
            conditioning_where="RIGHT half (columns 512..1023)",
            new_where="LEFT half (columns 0..511)",
        )
    if mode == "y_ttb":
        return PlacementConvention(
            mode=mode,
            conditioning_where="TOP half (rows 0..511)",
            new_where="BOTTOM half (rows 512..1023)",
        )
    if mode == "y_btt":
        return PlacementConvention(
            mode=mode,
            conditioning_where="BOTTOM half (rows 512..1023)",
            new_where="TOP half (rows 0..511)",
        )
    raise ValueError(f"Unknown mode: {mode}")


def _direction_word(mode: ExtendMode) -> str:
    # Human phrasing that matches what you want to prompt.
    if mode == "x_ltr":
        return "RIGHT"
    if mode == "x_rtl":
        return "LEFT"
    if mode == "y_ttb":
        return "DOWN"
    if mode == "y_btt":
        return "UP"
    raise ValueError(f"Unknown mode: {mode}")


SYSTEM_PREAMBLE = """\
You are given an image.

Your task is to EXTEND this image seamlessly in the specified direction.

Hard requirements:
- Preserve all existing pixels exactly as they appear in the given image.
- Continue the scene naturally into the new area.
- Do not redesign, restyle, re-render, reframe, zoom, rotate, or change perspective.
- Do not "clean up" or "enhance" the existing region (no denoise/sharpen/smoothing).
- The seam between existing and new content must be visually imperceptible.

If uncertain, choose the option that best preserves continuity with the given image.
"""


STYLE_LOCK_DEFAULT = """\
Style continuation requirements:
- Match the style already present in the given image (whatever it is).
- Match line weight / texture / detail density / lighting logic / palette (if any).
- Continue patterns, edges, and objects across the seam without discontinuity.
"""


NEGATIVE_DEFAULT = """\
Do NOT:
- introduce borders, frames, captions, logos, watermarks, or UI elements
- shift the image, warp it, crop it, or change camera/viewpoint
- reinterpret the existing content in a new artistic direction
"""


def render_prompt(
    *,
    mode: ExtendMode,
    user_prompt: str,
    style_lock: str | None,
    negative: str | None,
) -> str:
    direction = _direction_word(mode)

    style = STYLE_LOCK_DEFAULT if style_lock is None else style_lock.strip() + "\n"
    neg = NEGATIVE_DEFAULT if negative is None else negative.strip() + "\n"

    # Deterministic layout.
    return (
        f"{SYSTEM_PREAMBLE}\n"
        f"Direction: extend the image to the {direction}.\n\n"
        f"{style}\n"
        f"{neg}\n"
        f"User request:\n"
        f"{user_prompt}\n"
    )