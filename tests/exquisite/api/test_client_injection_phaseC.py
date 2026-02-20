from __future__ import annotations

import pytest
from PIL import Image

from imkerutils.exquisite.api.client import TileGeneratorClient, GeneratorTransientError
from imkerutils.exquisite.geometry.tile_mode import ExtendMode, TILE_PX
from imkerutils.exquisite.pipeline.step import execute_step_in_memory


class FailingClient(TileGeneratorClient):
    def generate_tile(self, *, conditioning_band: Image.Image, mode: ExtendMode, prompt: str, step_index: int) -> Image.Image:
        raise GeneratorTransientError("simulated timeout")


class WrongSizeClient(TileGeneratorClient):
    def generate_tile(self, *, conditioning_band: Image.Image, mode: ExtendMode, prompt: str, step_index: int) -> Image.Image:
        return Image.new("RGB", (TILE_PX, TILE_PX - 1))  # wrong height


def make_canvas() -> Image.Image:
    return Image.new("RGB", (1024, 1024))


@pytest.mark.parametrize("mode", ["x_ltr", "x_rtl", "y_ttb", "y_btt"])
def test_client_failure_rejects_without_advancing(mode: str) -> None:
    canvas0 = make_canvas()
    canvas1, res = execute_step_in_memory(
        canvas=canvas0,
        mode=mode,
        prompt="hi",
        step_index=0,
        client=FailingClient(),
    )
    assert res.status == "rejected"
    assert canvas1.size == canvas0.size
    assert res.rejection_reason is not None
    assert res.rejection_reason.startswith("generator_error:")


@pytest.mark.parametrize("mode", ["x_ltr", "x_rtl", "y_ttb", "y_btt"])
def test_wrong_tile_size_rejects(mode: str) -> None:
    canvas0 = make_canvas()
    canvas1, res = execute_step_in_memory(
        canvas=canvas0,
        mode=mode,
        prompt="hi",
        step_index=0,
        client=WrongSizeClient(),
    )
    assert res.status == "rejected"
    assert canvas1.size == canvas0.size
    assert res.rejection_reason == "tile_dim_mismatch"