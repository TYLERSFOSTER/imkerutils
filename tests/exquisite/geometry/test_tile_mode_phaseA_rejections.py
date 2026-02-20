from __future__ import annotations

import pytest
from PIL import Image

from imkerutils.exquisite.geometry.tile_mode import (
    extract_conditioning_band,
    split_tile,
    glue,
    TILE_PX,
    EXT_PX,
    BAND_PX,
)

MODES = ["x_ltr", "x_rtl", "y_ttb", "y_btt"]


def make_canvas(size=(TILE_PX, TILE_PX)) -> Image.Image:
    return Image.new("RGB", size)


@pytest.mark.parametrize("mode", MODES)
def test_extract_conditioning_band_rejects_wrong_non_growing_dimension(mode: str) -> None:
    """
    In Phase A we require the non-growing dimension to be exactly 1024:
      x_* : height must be 1024
      y_* : width  must be 1024
    """
    if mode in ("x_ltr", "x_rtl"):
        canvas = make_canvas((TILE_PX, TILE_PX + 1))  # width ok, height wrong
    else:
        canvas = make_canvas((TILE_PX + 1, TILE_PX))  # width wrong, height ok

    with pytest.raises(ValueError):
        extract_conditioning_band(canvas, mode)


@pytest.mark.parametrize("mode", MODES)
def test_split_tile_rejects_wrong_tile_size(mode: str) -> None:
    tile = Image.new("RGB", (TILE_PX, TILE_PX - 1))
    with pytest.raises(ValueError):
        split_tile(tile, mode)


@pytest.mark.parametrize("mode", MODES)
def test_glue_rejects_wrong_new_half_size(mode: str) -> None:
    canvas = make_canvas()
    if mode in ("x_ltr", "x_rtl"):
        bad_new = Image.new("RGB", (EXT_PX - 1, TILE_PX))  # wrong width
    else:
        bad_new = Image.new("RGB", (TILE_PX, EXT_PX - 1))  # wrong height

    with pytest.raises(ValueError):
        glue(canvas, bad_new, mode)


@pytest.mark.parametrize("mode", MODES)
def test_extract_conditioning_band_rejects_too_small_canvas(mode: str) -> None:
    """
    Band thickness is 512 in v1 Phase A. If canvas is smaller than that along the growing axis,
    extraction must fail.
    """
    if mode in ("x_ltr", "x_rtl"):
        # width < 512 should fail
        canvas = make_canvas((BAND_PX - 1, TILE_PX))
    else:
        # height < 512 should fail
        canvas = make_canvas((TILE_PX, BAND_PX - 1))

    with pytest.raises(ValueError):
        extract_conditioning_band(canvas, mode)