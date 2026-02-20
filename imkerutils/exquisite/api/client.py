from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from imkerutils.exquisite.geometry.tile_mode import ExtendMode


@dataclass(frozen=True)
class Usage:
    """
    Phase C: minimal usage/telemetry container.
    Keep optional, because mock won't have it and OpenAI adapter may.
    """
    provider: str
    request_id: str | None = None


class TileGeneratorClient(Protocol):
    """
    The ONLY contract Phase C needs:

    - input: conditioning band, mode, prompt, step_index
    - output: a full 1024x1024 tile (RGB) matching our placement convention.
    """

    def generate_tile(
        self,
        *,
        conditioning_band: Image.Image,
        mode: ExtendMode,
        prompt: str,
        step_index: int,
    ) -> Image.Image:
        ...


class GeneratorError(RuntimeError):
    """Base class for generator failures."""


class GeneratorTransientError(GeneratorError):
    """Retryable: network glitches, rate limits, timeouts (later)."""


class GeneratorPermanentError(GeneratorError):
    """Non-retryable: bad auth, bad request, unsupported model (later)."""


class GeneratorSafetyRefusal(GeneratorError):
    """Model refused due to safety policy (later)."""


class GeneratorBillingLimitError(GeneratorPermanentError):
    """Requests are blocked because the account/org is at a billing hard limit."""