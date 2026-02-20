from __future__ import annotations

from PIL import Image

from imkerutils.exquisite.api.client import TileGeneratorClient
from imkerutils.exquisite.api.mock_gpt_client import generate_tile as _generate_tile
from imkerutils.exquisite.geometry.tile_mode import ExtendMode


class MockTileGeneratorClient(TileGeneratorClient):
    def generate_tile(
        self,
        *,
        conditioning_band: Image.Image,
        mode: ExtendMode,
        prompt: str,
        step_index: int,
    ) -> Image.Image:
        return _generate_tile(
            conditioning_band=conditioning_band,
            mode=mode,
            prompt=prompt,
            step_index=step_index,
        )