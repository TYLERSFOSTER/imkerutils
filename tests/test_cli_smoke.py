import subprocess
import sys
from pathlib import Path

from PIL import Image


def test_extract_tile_cli_smoke(tmp_path):
    # Make a deterministic PNG
    img_path = tmp_path / "img.png"
    Image.new("RGB", (2048, 2048), (10, 20, 30)).save(img_path)

    out_tile = tmp_path / "tile.png"

    # Call the console script via python -m to avoid PATH issues
    cmd = [
        sys.executable,
        "-m",
        "imkerutils.tiling_utils.extract_tile",
        str(img_path),
        str(out_tile),
        "--x",
        "0",
        "--y",
        "0",
        "--corner",
        "tl",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert out_tile.exists()
    assert Image.open(out_tile).size == (1024, 1024)


def test_paste_tile_cli_smoke(tmp_path):
    base_path = tmp_path / "base.png"
    Image.new("RGB", (2048, 2048), (1, 2, 3)).save(base_path)

    tile_path = tmp_path / "tile.png"
    Image.new("RGB", (1024, 1024), (200, 0, 0)).save(tile_path)

    out_path = tmp_path / "patched.png"

    cmd = [
        sys.executable,
        "-m",
        "imkerutils.tiling_utils.paste_tile",
        str(base_path),
        str(tile_path),
        str(out_path),
        "--x",
        "0",
        "--y",
        "0",
        "--corner",
        "tl",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert out_path.exists()
