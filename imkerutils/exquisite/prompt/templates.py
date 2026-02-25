from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from imkerutils.exquisite.geometry.tile_mode import ExtendMode, OVERLAP_PX, ADVANCE_PX, HALF_PX, TILE_PX


@dataclass(frozen=True)
class PlacementConvention:
    """
    Kept for compatibility / potential UI display.
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


def _overlap_contract_block(mode: ExtendMode) -> str:
    """
    A deterministic, overlap-aware instruction block that matches our glue contract.

    Key idea:
    - The model receives a 1024x1024 reference image where ONE HALF is context (preserved)
      and ONE HALF is to be regenerated.
    - Downstream glue keeps only a band around the seam:
        * last OVERLAP_PX of the context side are overwritten,
        * first ADVANCE_PX of the generated side become the net new growth.
    - Therefore: the highest-value continuity target is the generated strip adjacent to the seam.
    """
    # These are "human-readable coordinates" only; they must remain stable.
    # We do NOT promise pixel-perfect outcomes beyond what masking enforces.
    if mode == "x_ltr":
        seam = f"vertical seam at column {HALF_PX}"
        gen_strip = f"first {OVERLAP_PX}px of the generated side (columns {HALF_PX}..{HALF_PX + OVERLAP_PX - 1})"
        return (
            "Overlap-aware seam contract (IMPORTANT):\n"
            f"- The LEFT half (columns 0..{HALF_PX - 1}) is context; the RIGHT half (columns {HALF_PX}..{TILE_PX - 1}) is generated.\n"
            f"- Treat the {seam} as the seam boundary.\n"
            f"- Continuity priority: make the {gen_strip} continue edges/lines/texture from immediately left of the seam.\n"
            f"- Do NOT introduce a visible vertical boundary; any line/object that reaches the seam should continue into that first {OVERLAP_PX}px of generated area.\n"
        )

    if mode == "x_rtl":
        seam = f"vertical seam at column {HALF_PX}"
        gen_strip = f"last {OVERLAP_PX}px of the generated side (columns {HALF_PX - OVERLAP_PX}..{HALF_PX - 1})"
        return (
            "Overlap-aware seam contract (IMPORTANT):\n"
            f"- The RIGHT half (columns {HALF_PX}..{TILE_PX - 1}) is context; the LEFT half (columns 0..{HALF_PX - 1}) is generated.\n"
            f"- Treat the {seam} as the seam boundary.\n"
            f"- Continuity priority: make the {gen_strip} continue edges/lines/texture from immediately right of the seam.\n"
            f"- Do NOT introduce a visible vertical boundary; any line/object that reaches the seam should continue into that last {OVERLAP_PX}px of generated area.\n"
        )

    if mode == "y_ttb":
        seam = f"horizontal seam at row {HALF_PX}"
        gen_strip = f"first {OVERLAP_PX}px of the generated side (rows {HALF_PX}..{HALF_PX + OVERLAP_PX - 1})"
        return (
            "Overlap-aware seam contract (IMPORTANT):\n"
            f"- The TOP half (rows 0..{HALF_PX - 1}) is context; the BOTTOM half (rows {HALF_PX}..{TILE_PX - 1}) is generated.\n"
            f"- Treat the {seam} as the seam boundary.\n"
            f"- Continuity priority: make the {gen_strip} continue edges/lines/texture from immediately above the seam.\n"
            f"- Do NOT introduce a visible horizontal boundary; any line/object that reaches the seam should continue into that first {OVERLAP_PX}px of generated area.\n"
        )

    if mode == "y_btt":
        seam = f"horizontal seam at row {HALF_PX}"
        gen_strip = f"last {OVERLAP_PX}px of the generated side (rows {HALF_PX - OVERLAP_PX}..{HALF_PX - 1})"
        return (
            "Overlap-aware seam contract (IMPORTANT):\n"
            f"- The BOTTOM half (rows {HALF_PX}..{TILE_PX - 1}) is context; the TOP half (rows 0..{HALF_PX - 1}) is generated.\n"
            f"- Treat the {seam} as the seam boundary.\n"
            f"- Continuity priority: make the {gen_strip} continue edges/lines/texture from immediately below the seam.\n"
            f"- Do NOT introduce a visible horizontal boundary; any line/object that reaches the seam should continue into that last {OVERLAP_PX}px of generated area.\n"
        )

    raise ValueError(f"Unknown mode: {mode}")


SYSTEM_PREAMBLE = """\
You are given an image.

Your task is to EXTEND this image seamlessly in the specified direction.

Hard requirements:
- Preserve all existing pixels exactly as they appear in the given image (do not alter the context region).
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

    contract = _overlap_contract_block(mode)

    # Deterministic layout.
    return (
        f"{SYSTEM_PREAMBLE}\n"
        f"Direction: extend the image to the {direction}.\n\n"
        f"{contract}\n"
        f"{style}\n"
        f"{neg}\n"
        f"User request:\n"
        f"{user_prompt}\n"
    )