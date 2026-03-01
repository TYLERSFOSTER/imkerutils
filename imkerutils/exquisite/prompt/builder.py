# imkerutils/exquisite/prompt/builder.py
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from imkerutils.exquisite.geometry.tile_mode import ExtendMode
from imkerutils.exquisite.prompt.templates import render_prompt


@dataclass(frozen=True)
class PromptPayload:
    """
    Deterministic prompt payload.

    - full_prompt: exact string to send to the generator
    - sha256_hex: content hash of full_prompt (utf-8) for step metadata / recovery
    """
    full_prompt: str
    sha256_hex: str


def _normalize_user_prompt(user_prompt: str) -> str:
    # Keep existing determinism policy.
    return user_prompt.replace("\r\n", "\n").strip()


def build_prompt_payload(
    *,
    mode: ExtendMode,
    user_prompt: str,
    style_lock: str | None = None,
    negative: str | None = None,
) -> PromptPayload:
    normalized_user = _normalize_user_prompt(user_prompt)

    full = render_prompt(
        mode=mode,
        user_prompt=normalized_user,
        style_lock=style_lock,
        negative=negative,
    )

    print("API FACING PROMPT:")
    print(full, "\n---END PROMPT---\n")

    h = hashlib.sha256(full.encode("utf-8")).hexdigest()
    return PromptPayload(full_prompt=full, sha256_hex=h)