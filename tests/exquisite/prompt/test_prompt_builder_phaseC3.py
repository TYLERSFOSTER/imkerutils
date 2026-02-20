from __future__ import annotations

import pytest

from imkerutils.exquisite.prompt.builder import build_prompt_payload
from imkerutils.exquisite.prompt.templates import placement_convention_for_mode

MODES = ["x_ltr", "x_rtl", "y_ttb", "y_btt"]


@pytest.mark.parametrize("mode", MODES)
def test_prompt_builder_is_deterministic(mode: str) -> None:
    p1 = build_prompt_payload(mode=mode, user_prompt="extend as abstract grayscale pattern")
    p2 = build_prompt_payload(mode=mode, user_prompt="extend as abstract grayscale pattern")
    assert p1.full_prompt == p2.full_prompt
    assert p1.sha256_hex == p2.sha256_hex


@pytest.mark.parametrize("mode", MODES)
def test_prompt_includes_mode_and_convention(mode: str) -> None:
    payload = build_prompt_payload(mode=mode, user_prompt="x")
    conv = placement_convention_for_mode(mode)

    assert f"Extend mode: {mode}" in payload.full_prompt
    assert f"Conditioning band MUST be placed in: {conv.conditioning_where}" in payload.full_prompt
    assert f"Newly generated region MUST occupy: {conv.new_where}" in payload.full_prompt


def test_user_prompt_is_normalized_newlines_and_trimmed() -> None:
    payload = build_prompt_payload(
        mode="x_ltr",
        user_prompt="  hello\r\nworld  \r\n",
    )
    # user prompt is rendered under "User prompt:" block
    assert "User prompt:\nhello\nworld\n" in payload.full_prompt


def test_style_and_negative_override_are_respected() -> None:
    payload = build_prompt_payload(
        mode="y_ttb",
        user_prompt="extend",
        style_lock="Style constraints:\n- KEEP BW ONLY",
        negative="Negative constraints:\n- NO TEXT",
    )
    assert "- KEEP BW ONLY" in payload.full_prompt
    assert "- NO TEXT" in payload.full_prompt