import pytest
from PIL import Image, ImageChops

from imkerutils.tiling_utils.core import extract_tile, paste_tile, TILE


def _assert_images_equal(a: Image.Image, b: Image.Image):
    diff = ImageChops.difference(a, b)
    assert diff.getbbox() is None, "Images differ (nonzero diff bbox)"


def test_extract_tile_pixel_exact(patterned_png, tmp_path):
    out_tile = tmp_path / "tile.png"

    # Choose a TL corner safely inside 2048x2048
    rect = extract_tile(patterned_png, out_tile, x=512, y=256, corner="tl")

    base = Image.open(patterned_png)
    tile = Image.open(out_tile)

    assert tile.size == (TILE, TILE)
    expected = base.crop(rect)
    _assert_images_equal(tile, expected)


def test_paste_tile_replaces_region_only(patterned_png, tmp_path):
    base_path = patterned_png
    base = Image.open(base_path)

    # Extract a tile
    tile_path = tmp_path / "tile.png"
    rect = extract_tile(base_path, tile_path, x=256, y=256, corner="tl")

    tile = Image.open(tile_path).copy()
    # Modify interior of the tile (but not required for this test)
    px = tile.load()
    px[10, 10] = (255, 0, 0)
    edited_tile_path = tmp_path / "tile_edited.png"
    tile.save(edited_tile_path)

    # Paste back
    out_path = tmp_path / "patched.png"
    paste_tile(base_path, edited_tile_path, out_path, x=256, y=256, corner="tl")

    patched = Image.open(out_path)

    # 1) Outside rect should equal original
    mask = Image.new("L", base.size, 0)
    # PIL uses box (left, top, right, bottom) with right/bottom exclusive
    mask.paste(255, rect)
    outside_orig = Image.composite(base, Image.new(base.mode, base.size), mask)  # rect from base
    outside_new = Image.composite(patched, Image.new(base.mode, base.size), mask)
    # Since mask selects rect, compare inverse to test outside:
    inv = ImageChops.invert(mask)
    outside_orig2 = Image.composite(base, Image.new(base.mode, base.size), inv)
    outside_new2 = Image.composite(patched, Image.new(base.mode, base.size), inv)
    _assert_images_equal(outside_orig2, outside_new2)

    # 2) Inside rect should equal the edited tile
    pasted_region = patched.crop(rect)
    edited_tile = Image.open(edited_tile_path)
    _assert_images_equal(pasted_region, edited_tile)


def test_extract_out_of_bounds_raises(patterned_png, tmp_path):
    out_tile = tmp_path / "tile.png"
    # 2048x2048 image: x=2000 means right edge will exceed 2048 for a 1024 tile
    with pytest.raises(ValueError):
        extract_tile(patterned_png, out_tile, x=2000, y=0, corner="tl")


def test_paste_wrong_tile_size_raises(patterned_png, tmp_path):
    base_path = patterned_png
    small_tile = tmp_path / "small.png"
    Image.new("RGB", (256, 256)).save(small_tile)

    out_path = tmp_path / "patched.png"
    with pytest.raises(ValueError):
        paste_tile(base_path, small_tile, out_path, x=0, y=0, corner="tl")
