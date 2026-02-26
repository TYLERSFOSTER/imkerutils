# imkerutils/exquisite/api/openai_client.py
from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass

from PIL import Image
from openai import OpenAI

from imkerutils.exquisite.api.client import (
    TileGeneratorClient,
    GeneratorPermanentError,
)

from imkerutils.exquisite.geometry.tile_mode import (
    ExtendMode,
    TILE_PX,
    BAND_PX,
    HALF_PX,
    OVERLAP_PX,
)

from imkerutils.exquisite.geometry.reference_tile import encode_png_bytes


MODEL_DEFAULT = "gpt-image-1"


@dataclass(frozen=True)
class OpenAITileGeneratorConfig:
    model: str = MODEL_DEFAULT
    timeout_s: float | None = None
    input_fidelity: str | None = "high"  # try to preserve given pixels


class OpenAITileGeneratorClient(TileGeneratorClient):
    """
    Mask-free generator adapter.

    Contract intent (x_ltr case):
      - Send ONLY the 512px frontier band (512x1024) as the image input.
      - Ask the model to extend it to a 1024x1024 tile.
      - LEFT half is context; RIGHT half is new.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        config: OpenAITileGeneratorConfig | None = None,
    ) -> None:
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise GeneratorPermanentError("OPENAI_API_KEY not set")

        self._client = OpenAI(api_key=api_key)
        self._config = config or OpenAITileGeneratorConfig()

    def generate_tile(
        self,
        *,
        conditioning_band: Image.Image,
        mode: ExtendMode,
        prompt: str,
        step_index: int,
    ) -> Image.Image:
        band = conditioning_band.convert("RGB")

        # Sanity: band dimensions must match your tile_mode contract.
        if mode in ("x_ltr", "x_rtl"):
            if band.size != (BAND_PX, TILE_PX):
                raise GeneratorPermanentError(f"conditioning_band wrong size: got {band.size}, expected {(BAND_PX, TILE_PX)}")
        else:
            if band.size != (TILE_PX, BAND_PX):
                raise GeneratorPermanentError(f"conditioning_band wrong size: got {band.size}, expected {(TILE_PX, BAND_PX)}")

        band_file = io.BytesIO(encode_png_bytes(band))
        band_file.name = f"band_step_{step_index}.png"

        simple_prompt = _build_simple_prompt(mode=mode, user_prompt=prompt)

        # Mask intentionally omitted.
        kwargs: dict = {}
        if self._config.input_fidelity is not None:
            kwargs["input_fidelity"] = self._config.input_fidelity

        result = self._client.images.edit(
            model=self._config.model,
            image=[band_file],
            prompt=simple_prompt,
            size="1024x1024",
            **kwargs,
        )

        image_base64 = result.data[0].b64_json
        tile = Image.open(io.BytesIO(base64.b64decode(image_base64))).convert("RGB")

        if tile.size != (TILE_PX, TILE_PX):
            raise GeneratorPermanentError(f"Bad tile size: {tile.size}")

        # Preserve the far KEEP region (256px) exactly (your existing behavior).
        return self._post_enforce_conditioning_keep(tile, band, mode)

    def _post_enforce_conditioning_keep(self, tile: Image.Image, band: Image.Image, mode: ExtendMode) -> Image.Image:
        KEEP_PX = HALF_PX - OVERLAP_PX  # 256

        if mode == "x_ltr":
            tile.paste(band.crop((0, 0, KEEP_PX, TILE_PX)), (0, 0))
        elif mode == "x_rtl":
            tile.paste(band.crop((BAND_PX - KEEP_PX, 0, BAND_PX, TILE_PX)), (TILE_PX - KEEP_PX, 0))
        elif mode == "y_ttb":
            tile.paste(band.crop((0, 0, TILE_PX, KEEP_PX)), (0, 0))
        elif mode == "y_btt":
            tile.paste(band.crop((0, BAND_PX - KEEP_PX, TILE_PX, BAND_PX)), (0, TILE_PX - KEEP_PX))
        else:
            raise GeneratorPermanentError("Unknown mode")

        return tile


def _build_simple_prompt(*, mode: ExtendMode, user_prompt: str) -> str:
    # This is intentionally “front-end simple”, matching your known-good UI prompt style.
    user_prompt = (user_prompt or "").strip()

    if mode == "x_ltr":
        return (
            "Extend this image *continuously* to the right so that it becomes 1024x1024. "
            f"In the new region, satisfy the prompt: {user_prompt}"
        )
    if mode == "x_rtl":
        return (
            "Extend this image *continuously* to the left so that it becomes 1024x1024. "
            f"In the new region, satisfy the prompt: {user_prompt}"
        )
    if mode == "y_ttb":
        return (
            "Extend this image *continuously* downward so that it becomes 1024x1024. "
            f"In the new region, satisfy the prompt: {user_prompt}"
        )
    if mode == "y_btt":
        return (
            "Extend this image *continuously* upward so that it becomes 1024x1024. "
            f"In the new region, satisfy the prompt: {user_prompt}"
        )

    raise ValueError(f"Unknown mode: {mode}")