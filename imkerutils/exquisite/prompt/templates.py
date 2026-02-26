# imkerutils/exquisite/prompt/templates.py
from __future__ import annotations

from dataclasses import dataclass

from imkerutils.exquisite.geometry.tile_mode import ExtendMode


@dataclass(frozen=True)
class PlacementConvention:
    """
    Kept for compatibility / potential UI display.
    These strings are load-bearing: tests may assert on them.
    """
    mode: ExtendMode
    conditioning_where: str
    new_where: str


def placement_convention_for_mode(mode: ExtendMode) -> PlacementConvention:
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


def render_prompt(
    *,
    mode: ExtendMode,
    user_prompt: str,
    style_lock: str | None,  # kept for signature stability; intentionally ignored
    negative: str | None,    # kept for signature stability; intentionally ignored
) -> str:
    """
    Minimal prompt, matching the known-good ChatGPT UI phrasing.

    Note: style_lock/negative are accepted only to preserve the public API,
    but are intentionally not used.
    """
    user_prompt = (user_prompt or "").strip()

    base_prompt = " -- This image is being glued back into a large image, so it is important to try to keep existing region as is. Use your genertion tool, but try to get good match on these existing pixels."

    if mode == "x_ltr":
        return (
            "Extend this image *continuously* to the right so that it becomes 1024x1024. "
            f"In the new region, satisfy the prompt: {user_prompt}" + base_prompt
        )
    if mode == "x_rtl":
        return (
            "Extend this image *continuously* to the left so that it becomes 1024x1024. "
            f"In the new region, satisfy the prompt: {user_prompt}" + base_prompt
        )
    if mode == "y_ttb":
        return (
            "Extend this image *continuously* downward so that it becomes 1024x1024. "
            f"In the new region, satisfy the prompt: {user_prompt}" + base_prompt
        )
    if mode == "y_btt":
        return (
            "Extend this image *continuously* upward so that it becomes 1024x1024. "
            f"In the new region, satisfy the prompt: {user_prompt}" + base_prompt
        )

    raise ValueError(f"Unknown mode: {mode}")