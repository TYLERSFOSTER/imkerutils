from __future__ import annotations

import os
import pytest
from PIL import Image

from imkerutils.exquisite.api.openai_client import OpenAITileGeneratorClient
from imkerutils.exquisite.api.client import GeneratorBillingLimitError


@pytest.mark.integration
def test_openai_client_smoke():
    """
    Opt-in integration test. Will be skipped unless explicitly enabled.
    """
    if os.environ.get("EXQUISITE_RUN_OPENAI_SMOKE") != "1":
        pytest.skip("set EXQUISITE_RUN_OPENAI_SMOKE=1 to run live OpenAI image smoke test")

    client = OpenAITileGeneratorClient()

    band = Image.new("RGB", (512, 1024))

    try:
        tile = client.generate_tile(
            conditioning_band=band,
            mode="x_ltr",
            prompt="extend as abstract grayscale pattern",
            step_index=0,
        )
    except GeneratorBillingLimitError as e:
        pytest.skip(f"OpenAI billing hard limit reached for this org/key: {e}")

    assert tile.size == (1024, 1024)