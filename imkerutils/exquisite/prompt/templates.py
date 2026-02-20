from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from imkerutils.exquisite.geometry.tile_mode import ExtendMode


@dataclass(frozen=True)
class PlacementConvention:
    """
    Human-readable, deterministic placement convention for the fixed 1024x1024 tile.

    Conditioning band is always a 512px-thick strip taken from the current canvas.
    It must appear in exactly one half of the returned 1024x1024 tile.

    The other half is the newly-generated region.
    """
    mode: ExtendMode
    conditioning_where: str
    new_where: str


def placement_convention_for_mode(mode: ExtendMode) -> PlacementConvention:
    # These strings are load-bearing: tests assert on them.
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


SYSTEM_PREAMBLE = """\
You are an image generator operating in TILE MODE.

Hard contract:
- Output MUST be exactly 1024x1024 pixels.
- The conditioning band provided MUST appear exactly in the specified half of the tile.
- The other half MUST be newly generated content that extends the scene coherently.
"""


STYLE_LOCK_DEFAULT = """\
Style constraints:
- Preserve the overall visual style and local texture continuity across the seam.
- Do not introduce borders, frames, watermarks, or captions.
"""


NEGATIVE_DEFAULT = """\
Negative constraints:
- Do not resize, crop, rotate, or distort the conditioning region.
- Do not alter the conditioning region content.
"""


def render_prompt(
    *,
    mode: ExtendMode,
    user_prompt: str,
    style_lock: str | None,
    negative: str | None,
) -> str:
    conv = placement_convention_for_mode(mode)

    style = STYLE_LOCK_DEFAULT if style_lock is None else style_lock.strip() + "\n"
    neg = NEGATIVE_DEFAULT if negative is None else negative.strip() + "\n"

    # Deterministic layout (ordering matters: tests rely on stable formatting).
    return (
        f"{SYSTEM_PREAMBLE}\n"
        f"Extend mode: {mode}\n"
        f"Placement convention:\n"
        f"- Conditioning band MUST be placed in: {conv.conditioning_where}\n"
        f"- Newly generated region MUST occupy: {conv.new_where}\n"
        f"\n"
        f"{style}\n"
        f"{neg}\n"
        f"User prompt:\n"
        f"{user_prompt}\n"
    )