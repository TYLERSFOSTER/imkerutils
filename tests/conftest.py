import pytest
from PIL import Image


@pytest.fixture
def patterned_png(tmp_path):
    """
    Creates a deterministic 2048x2048 RGB PNG with a strong spatial pattern.
    Perfect for pixel-exact crop/paste tests.
    """
    w = h = 2048
    img = Image.new("RGB", (w, h))
    px = img.load()

    for y in range(h):
        for x in range(w):
            # deterministic, nontrivial pattern
            r = (x * 37 + y * 17) % 256
            g = (x * 13 + y * 53) % 256
            b = (x * 97 + y * 19) % 256
            px[x, y] = (r, g, b)

    path = tmp_path / "pattern.png"
    img.save(path)
    return path
