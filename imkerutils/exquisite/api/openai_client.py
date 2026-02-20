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
)
from imkerutils.exquisite.geometry.tile_mode import (
    ExtendMode,
    TILE_PX,
    BAND_PX,
)

MODEL_DEFAULT = "gpt-image-1"


@dataclass(frozen=True)
class OpenAITileGeneratorConfig:
    model: str = MODEL_DEFAULT
    timeout_s: float | None = None


class OpenAITileGeneratorClient(TileGeneratorClient):
    """
    Phase C3: Real OpenAI-backed generator client.

    Contract enforced:

    - input conditioning_band must be correct BAND_PX dimensions
    - output tile MUST be exactly 1024x1024 RGB
    - conditioning half MUST be overwritten exactly to guarantee invariant
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
        prompt: str,
        step_index: int,
    ) -> Image.Image:

        conditioning_band = conditioning_band.convert("RGB")

        # validate conditioning band size
        if mode in ("x_ltr", "x_rtl"):
            if conditioning_band.size != (BAND_PX, TILE_PX):
                raise GeneratorPermanentError(
                    f"conditioning_band must be {BAND_PX}x{TILE_PX}"
                )
        else:
            if conditioning_band.size != (TILE_PX, BAND_PX):
                raise GeneratorPermanentError(
                    f"conditioning_band must be {TILE_PX}x{BAND_PX}"
                )

        try:

            band_bytes = self._encode_png(conditioning_band)

            full_prompt = self._build_prompt(
                mode=mode,
                user_prompt=prompt,
            )

            result = self._client.images.generate(
                model=self._config.model,
                prompt=full_prompt,
                size="1024x1024",
            )

        except Exception as e:

            msg = str(e).lower()

            if "billing_hard_limit" in msg or "billing hard limit" in msg or "billing_hard_limit_reached" in msg:
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
            raise GeneratorPermanentError(
                f"Model returned wrong tile size {tile.size}"
            )

        # enforce conditioning band identity strictly
        tile = self._post_enforce_conditioning_half(
            tile,
            conditioning_band,
            mode,
        )

        return tile

    def _encode_png(self, img: Image.Image) -> bytes:

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def _build_prompt(
        self,
        *,
        mode: ExtendMode,
        user_prompt: str,
    ) -> str:

        return (
            "You are extending an existing image.\n"
            "The conditioning region must remain pixel-identical.\n"
            "Generate new image content seamlessly.\n\n"
            f"Direction mode: {mode}\n\n"
            f"User prompt:\n{user_prompt}"
        )

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