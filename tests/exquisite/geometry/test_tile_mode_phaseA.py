from __future__ import annotations

import pytest
from PIL import Image

from imkerutils.exquisite.geometry.tile_mode import (
    TILE_PX,
    EXT_PX,
    BAND_PX,
    extract_conditioning_band,
    split_tile,
    glue,
    expected_next_canvas_size,
)
from imkerutils.exquisite.api.mock_gpt_client import generate_tile

MODES = ["x_ltr", "x_rtl", "y_ttb", "y_btt"]


def make_canvas() -> Image.Image:
    # deterministic base canvas
    return Image.new("RGB", (TILE_PX, TILE_PX), (128, 128, 128))


@pytest.mark.parametrize("mode", MODES)
def test_extract_conditioning_band_shape(mode: str) -> None:
    canvas = make_canvas()
    band = extract_conditioning_band(canvas, mode)

    if mode in ("x_ltr", "x_rtl"):
        assert band.size == (BAND_PX, TILE_PX)
    else:
        assert band.size == (TILE_PX, BAND_PX)


@pytest.mark.parametrize("mode", MODES)
def test_generate_tile_is_fixed_1024(mode: str) -> None:
    canvas = make_canvas()
    band = extract_conditioning_band(canvas, mode)

    tile = generate_tile(conditioning_band=band, mode=mode, prompt="p", step_index=0)
    assert tile.size == (TILE_PX, TILE_PX)


@pytest.mark.parametrize("mode", MODES)
def test_tile_band_placement_convention(mode: str) -> None:
    canvas = make_canvas()
    band = extract_conditioning_band(canvas, mode)

    tile = generate_tile(conditioning_band=band, mode=mode, prompt="p", step_index=0)
    cond_half, new_half = split_tile(tile, mode)

    # conditioning half must match exactly (pixel-identical)
    assert cond_half.get_flattened_data() == band.get_flattened_data()

    # new half must be the expected size
    if mode in ("x_ltr", "x_rtl"):
        assert new_half.size == (EXT_PX, TILE_PX)
    else:
        assert new_half.size == (TILE_PX, EXT_PX)


@pytest.mark.parametrize("mode", MODES)
def test_glue_grows_canvas_by_512(mode: str) -> None:
    canvas0 = make_canvas()
    band = extract_conditioning_band(canvas0, mode)
    tile = generate_tile(conditioning_band=band, mode=mode, prompt="p", step_index=0)
    _, new_half = split_tile(tile, mode)

    canvas1 = glue(canvas0, new_half, mode)

    exp = expected_next_canvas_size(canvas0, mode)
    assert canvas1.size == exp

    w0, h0 = canvas0.size
    w1, h1 = canvas1.size

    if mode in ("x_ltr", "x_rtl"):
        assert h1 == h0
        assert w1 == w0 + EXT_PX
    else:
        assert w1 == w0
        assert h1 == h0 + EXT_PX


@pytest.mark.parametrize("mode", MODES)
def test_two_steps_compose(mode: str) -> None:
    canvas = make_canvas()

    # step 0
    band0 = extract_conditioning_band(canvas, mode)
    tile0 = generate_tile(conditioning_band=band0, mode=mode, prompt="a", step_index=0)
    _, new0 = split_tile(tile0, mode)
    canvas = glue(canvas, new0, mode)

    # step 1
    band1 = extract_conditioning_band(canvas, mode)
    tile1 = generate_tile(conditioning_band=band1, mode=mode, prompt="b", step_index=1)
    _, new1 = split_tile(tile1, mode)
    canvas2 = glue(canvas, new1, mode)

    w, h = canvas.size
    w2, h2 = canvas2.size

    if mode in ("x_ltr", "x_rtl"):
        assert h2 == h
        assert w2 == w + EXT_PX
    else:
        assert w2 == w
        assert h2 == h + EXT_PX