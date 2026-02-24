from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass

from PIL import Image
from openai import OpenAI

from imkerutils.exquisite.api.client import (
    TileGeneratorClient,
    GeneratorTransientError,
    GeneratorPermanentError,
    GeneratorSafetyRefusal,
    GeneratorBillingLimitError,
)
from imkerutils.exquisite.geometry.tile_mode import ExtendMode, TILE_PX, BAND_PX
from imkerutils.exquisite.geometry.reference_tile import (
    build_reference_tile_and_mask,
    encode_png_bytes,
)
from imkerutils.exquisite.prompt.builder import build_prompt_payload

MODEL_DEFAULT = "gpt-image-1"


@dataclass(frozen=True)
class OpenAITileGeneratorConfig:
    model: str = MODEL_DEFAULT
    timeout_s: float | None = None


class OpenAITileGeneratorClient(TileGeneratorClient):
    """
    Real OpenAI-backed generator client (image-conditioned).
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        config: OpenAITileGeneratorConfig | None = None,
    ) -> None:
        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key:
            raise GeneratorPermanentError("OPENAI_API_KEY not set")

        self._client = OpenAI(api_key=api_key)
        self._config = config or OpenAITileGeneratorConfig()

    def generate_tile(
        self,
        *,
        conditioning_band: Image.Image,
        mode: ExtendMode,
        prompt: str,          # NOTE: treat as RAW USER PROMPT TEXT
        step_index: int,
    ) -> Image.Image:
        conditioning_band = conditioning_band.convert("RGB")

        # validate conditioning band size
        if mode in ("x_ltr", "x_rtl"):
            if conditioning_band.size != (BAND_PX, TILE_PX):
                raise GeneratorPermanentError(f"conditioning_band must be {BAND_PX}x{TILE_PX}")
        else:
            if conditioning_band.size != (TILE_PX, BAND_PX):
                raise GeneratorPermanentError(f"conditioning_band must be {TILE_PX}x{BAND_PX}")

        # Build reference tile + mask so the model sees the conditioning pixels.
        ref = build_reference_tile_and_mask(conditioning_band=conditioning_band, mode=mode)
        ref_bytes = encode_png_bytes(ref.reference_tile_rgb)
        mask_bytes = encode_png_bytes(ref.mask_rgba)

        ref_file = io.BytesIO(ref_bytes)
        ref_file.name = f"ref_step_{step_index}.png"
        mask_file = io.BytesIO(mask_bytes)
        mask_file.name = f"mask_step_{step_index}.png"

        # Expand user prompt into our deterministic “extend to RIGHT/LEFT/UP/DOWN” instruction.
        payload = build_prompt_payload(mode=mode, user_prompt=prompt)

        try:
            edits_fn = getattr(self._client.images, "edits", None)
            if edits_fn is None:
                edits_fn = getattr(self._client.images, "edit", None)
            if edits_fn is None:
                raise GeneratorPermanentError("OpenAI SDK missing images.edits/images.edit method")

            result = edits_fn(
                model=self._config.model,
                image=[ref_file],
                mask=mask_file,
                prompt=payload.full_prompt,
                size="1024x1024",
            )

        except Exception as e:
            msg = str(e).lower()

            if (
                "billing_hard_limit" in msg
                or "billing hard limit" in msg
                or "billing_hard_limit_reached" in msg
            ):
                raise GeneratorBillingLimitError(str(e)) from e

            if "timeout" in msg or "rate limit" in msg:
                raise GeneratorTransientError(str(e)) from e

            if "safety" in msg or "policy" in msg:
                raise GeneratorSafetyRefusal(str(e)) from e

            raise GeneratorPermanentError(str(e)) from e

        try:
            image_base64 = result.data[0].b64_json
            tile = Image.open(io.BytesIO(base64.b64decode(image_base64)))
        except Exception as e:
            raise GeneratorPermanentError("Invalid image response") from e

        tile = tile.convert("RGB")

        if tile.size != (TILE_PX, TILE_PX):
            raise GeneratorPermanentError(f"Model returned wrong tile size {tile.size}")

        # Hard invariant: enforce conditioning band identity strictly.
        tile = self._post_enforce_conditioning_half(tile, conditioning_band, mode)

        return tile

    def _post_enforce_conditioning_half(
        self,
        tile: Image.Image,
        band: Image.Image,
        mode: ExtendMode,
    ) -> Image.Image:
        if mode == "x_ltr":
            tile.paste(band, (0, 0))
        elif mode == "x_rtl":
            tile.paste(band, (512, 0))
        elif mode == "y_ttb":
            tile.paste(band, (0, 0))
        elif mode == "y_btt":
            tile.paste(band, (0, 512))
        else:
            raise GeneratorPermanentError("Unknown mode")
        return tile