from __future__ import annotations

import pytest
from PIL import Image

from imkerutils.exquisite.api.mock_client import MockTileGeneratorClient
from imkerutils.exquisite.pipeline.step import execute_step_in_memory


def make_canvas() -> Image.Image:
    return Image.new("RGB", (1024, 1024))


@pytest.mark.parametrize("mode", ["x_ltr", "x_rtl", "y_ttb", "y_btt"])
def test_step_commits_with_mock_client(mode: str) -> None:
    canvas0 = make_canvas()
    client = MockTileGeneratorClient()

    canvas1, res = execute_step_in_memory(
        canvas=canvas0,
        mode=mode,
        prompt="test",
        step_index=0,
        client=client,
        enforce_band_identity=True,
    )

    assert res.status == "committed"

    w0, h0 = canvas0.size
    w1, h1 = canvas1.size

    if mode in ("x_ltr", "x_rtl"):
        assert h1 == h0
        assert w1 == w0 + 512
    else:
        assert w1 == w0
        assert h1 == h0 + 512