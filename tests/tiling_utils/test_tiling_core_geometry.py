import pytest
from imkerutils.tiling_utils.core import rect_from_corner, top_left_from_corner, TILE


@pytest.mark.parametrize(
    "corner,x,y,expected_left,expected_top",
    [
        ("tl", 100, 200, 100, 200),
        ("tr", 100, 200, 100 - (TILE - 1), 200),
        ("bl", 100, 200, 100, 200 - (TILE - 1)),
        ("br", 100, 200, 100 - (TILE - 1), 200 - (TILE - 1)),
    ],
)
def test_top_left_from_corner(corner, x, y, expected_left, expected_top):
    left, top = top_left_from_corner(x, y, corner)
    assert (left, top) == (expected_left, expected_top)


def test_rect_from_corner_shape():
    left, top, right, bottom = rect_from_corner(0, 0, "tl")
    assert (right - left, bottom - top) == (TILE, TILE)


def test_invalid_corner_raises():
    with pytest.raises(ValueError):
        rect_from_corner(0, 0, "nope")  # type: ignore
