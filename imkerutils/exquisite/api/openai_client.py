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
from imkerutils.exquisite.geometry.reference_tile import (
    encode_png_bytes,
    build_reference_tile_and_mask,
)

MODEL_DEFAULT = "gpt-image-1.5"


@dataclass(frozen=True)
class OpenAITileGeneratorConfig:
    model: str = MODEL_DEFAULT
    timeout_s: float | None = None
    input_fidelity: str | None = "high"  # try to preserve given pixels


class OpenAITileGeneratorClient(TileGeneratorClient):
    """
    Convention B generator adapter.

    Contract intent:
      - Build a 1024x1024 reference canvas containing the 512px frontier band.
      - Provide a 1024x1024 RGBA mask with an alpha ramp over the band thickness:
          opposite-frontier boundary: alpha=255 (fix)
          frontier boundary:          alpha=0   (free)
      - Ask the model to produce a 1024x1024 tile consistent with this edit mask.
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

        # Sanity: band dimensions must match tile_mode contract.
        if mode in ("x_ltr", "x_rtl"):
            if band.size != (BAND_PX, TILE_PX):
                raise GeneratorPermanentError(
                    f"conditioning_band wrong size: got {band.size}, expected {(BAND_PX, TILE_PX)}"
                )
        else:
            if band.size != (TILE_PX, BAND_PX):
                raise GeneratorPermanentError(
                    f"conditioning_band wrong size: got {band.size}, expected {(TILE_PX, BAND_PX)}"
                )

        # Build 1024x1024 reference canvas + 1024x1024 RGBA mask (Convention B).
        ref_and_mask = build_reference_tile_and_mask(conditioning_band=band, mode=mode)
        ref_rgb = ref_and_mask.reference_tile_rgb.convert("RGB")
        mask_rgba = ref_and_mask.mask_rgba.convert("RGBA")

        ref_file = io.BytesIO(encode_png_bytes(ref_rgb))
        ref_file.name = f"ref_step_{step_index}.png"

        mask_file = io.BytesIO(encode_png_bytes(mask_rgba))
        mask_file.name = f"mask_step_{step_index}.png"

        simple_prompt = _build_simple_prompt(mode=mode, user_prompt=prompt)
        print(f"OpenAI API prompt for step {step_index}:\n{simple_prompt}\n---END PROMPT---\n")

        kwargs: dict = {}
        if self._config.input_fidelity is not None:
            kwargs["input_fidelity"] = self._config.input_fidelity

        result = self._client.images.edit(
            model=self._config.model,
            image=[ref_file],
            mask=mask_file,
            prompt=simple_prompt,
            size="1024x1024",
            **kwargs,
        )

        image_base64 = result.data[0].b64_json
        tile = Image.open(io.BytesIO(base64.b64decode(image_base64))).convert("RGB")

        if tile.size != (TILE_PX, TILE_PX):
            raise GeneratorPermanentError(f"Bad tile size: {tile.size}")

        # Preserve the far KEEP region (256px) exactly (existing behavior).
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
    user_prompt = (user_prompt or "").strip()

    if mode == "x_ltr":
        return (
            "Extend this image continuously to the right so that it becomes 1024x1024. "
            "Maintain the existing style and content. "
            f"The new region needs one new detail at least: {user_prompt}"
        )
    if mode == "x_rtl":
        return (
            "Extend this image continuously to the left so that it becomes 1024x1024. "
            "Maintain the existing style and content. "
            f"The new region needs one new detail at least: {user_prompt}"
        )
    if mode == "y_ttb":
        return (
            "Extend this image continuously downward so that it becomes 1024x1024. "
            "Maintain the existing style and content. "
            f"The new region needs one new detail at least: {user_prompt}"
        )
    if mode == "y_btt":
        return (
            "Extend this image continuously upward so that it becomes 1024x1024. "
            "Maintain the existing style and content. "
            f"The new region needs one new detail at least: {user_prompt}"
        )

    raise ValueError(f"Unknown mode: {mode}")