# imkerutils/exquisite/pipeline/session.py
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, Tuple

from PIL import Image

from imkerutils.exquisite.api.client import TileGeneratorClient, GeneratorError
from imkerutils.exquisite.api.mock_gpt_client import generate_tile
from imkerutils.exquisite.geometry.tile_mode import (
    ExtendMode,
    TILE_PX,
    EXT_PX,
    BAND_PX,
    OVERLAP_PX,
    ADVANCE_PX,
    HALF_PX,
    extract_conditioning_band,
    split_tile,
    glue,
    expected_next_canvas_size,
    _tile_patch_for_overlap_glue,
)
from imkerutils.exquisite.io.atomic_write import atomic_write_text, atomic_write_with
from imkerutils.exquisite.state.session_state import SessionState


def _default_artifact_root() -> Path:
    pkg_root = Path(__file__).resolve().parents[2]
    return pkg_root / "_generated" / "exquisite"


@dataclass(frozen=True)
class DiskStepResult:
    status: Literal["committed", "rejected"]
    session_id: str
    step_index: int
    canvas_before_size: Tuple[int, int]
    canvas_after_size: Tuple[int, int]
    step_dir: str


# -----------------------------
# Blending utilities (optional)
# -----------------------------

def _overlap_crops_for_blend(
    *,
    canvas_rgb: Image.Image,
    tile_rgb: Image.Image,
    mode: ExtendMode,
) -> tuple[Image.Image, Image.Image]:
    canvas_rgb = canvas_rgb.convert("RGB")
    tile_rgb = tile_rgb.convert("RGB")
    cw, ch = canvas_rgb.size

    if mode == "x_ltr":
        c = canvas_rgb.crop((cw - OVERLAP_PX, 0, cw, TILE_PX))
        t = tile_rgb.crop((HALF_PX - OVERLAP_PX, 0, HALF_PX, TILE_PX))        # 256..512
        return c, t

    if mode == "x_rtl":
        c = canvas_rgb.crop((0, 0, OVERLAP_PX, TILE_PX))
        t = tile_rgb.crop((HALF_PX, 0, HALF_PX + OVERLAP_PX, TILE_PX))        # 512..768
        return c, t

    if mode == "y_ttb":
        c = canvas_rgb.crop((0, ch - OVERLAP_PX, TILE_PX, ch))
        t = tile_rgb.crop((0, HALF_PX - OVERLAP_PX, TILE_PX, HALF_PX))        # 256..512
        return c, t

    if mode == "y_btt":
        c = canvas_rgb.crop((0, 0, TILE_PX, OVERLAP_PX))
        t = tile_rgb.crop((0, HALF_PX, TILE_PX, HALF_PX + OVERLAP_PX))        # 512..768
        return c, t

    raise ValueError(mode)


def _glue_with_feather(
    *,
    canvas: Image.Image,
    tile: Image.Image,
    mode: ExtendMode,
    feather_px: int,
) -> Image.Image:
    """
    Optional seam feathering over the OVERLAP_PX strip.
    If feather_px <= 0, falls back to hard glue() contract.
    """
    if feather_px <= 0:
        return glue(canvas, tile, mode)

    feather_px = int(feather_px)
    feather_px = max(1, min(feather_px, OVERLAP_PX))

    canvas = canvas.convert("RGB")
    tile = tile.convert("RGB")

    canvas_ov, tile_ov = _overlap_crops_for_blend(canvas_rgb=canvas, tile_rgb=tile, mode=mode)
    ov_w, ov_h = canvas_ov.size

    if mode in ("x_ltr", "x_rtl"):
        mask = Image.new("L", (ov_w, ov_h), 0)
        ramp = Image.new("L", (feather_px, ov_h), 0)

        ramp_pixels: list[int] = []
        for x in range(feather_px):
            a = int(round(255 * (x / max(1, feather_px - 1))))
            ramp_pixels.extend([a] * ov_h)
        ramp.putdata(ramp_pixels)

        if mode == "x_ltr":
            mask.paste(ramp, (ov_w - feather_px, 0))
        else:
            mask.paste(ramp, (0, 0))
    else:
        mask = Image.new("L", (ov_w, ov_h), 0)
        ramp = Image.new("L", (ov_w, feather_px), 0)

        ramp_pixels = []
        for y in range(feather_px):
            a = int(round(255 * (y / max(1, feather_px - 1))))
            ramp_pixels.extend([a] * ov_w)
        ramp.putdata(ramp_pixels)

        if mode == "y_ttb":
            mask.paste(ramp, (0, ov_h - feather_px))
        else:
            mask.paste(ramp, (0, 0))

    blended_ov = Image.composite(tile_ov, canvas_ov, mask)

    tile2 = tile.copy()
    if mode == "x_ltr":
        tile2.paste(blended_ov, (HALF_PX - OVERLAP_PX, 0))     # 256..512
    elif mode == "x_rtl":
        tile2.paste(blended_ov, (HALF_PX, 0))                  # 512..768
    elif mode == "y_ttb":
        tile2.paste(blended_ov, (0, HALF_PX - OVERLAP_PX))     # 256..512
    elif mode == "y_btt":
        tile2.paste(blended_ov, (0, HALF_PX))                  # 512..768
    else:
        raise ValueError(mode)

    return glue(canvas, tile2, mode)


def _post_enforce_keep_into_tile(*, tile: Image.Image, band: Image.Image, mode: ExtendMode) -> Image.Image:
    """
    Session-side post-enforce to match OpenAITileGeneratorClient:
    paste ONLY the far KEEP region (256px), not the full band.
    """
    keep_px = HALF_PX - OVERLAP_PX  # 256

    if mode == "x_ltr":
        src = band.crop((0, 0, keep_px, TILE_PX))
        tile.paste(src, (0, 0))
        return tile
    if mode == "x_rtl":
        src = band.crop((BAND_PX - keep_px, 0, BAND_PX, TILE_PX))
        tile.paste(src, (TILE_PX - keep_px, 0))
        return tile
    if mode == "y_ttb":
        src = band.crop((0, 0, TILE_PX, keep_px))
        tile.paste(src, (0, 0))
        return tile
    if mode == "y_btt":
        src = band.crop((0, BAND_PX - keep_px, TILE_PX, BAND_PX))
        tile.paste(src, (0, TILE_PX - keep_px))
        return tile

    raise ValueError(mode)


class ExquisiteSession:
    def __init__(self, state: SessionState):
        self.state = state

    @classmethod
    def create(
        cls,
        *,
        initial_canvas_path: Path,
        mode: ExtendMode,
        artifact_root: Optional[Path] = None,
    ) -> "ExquisiteSession":
        artifact_root = artifact_root or _default_artifact_root()
        session_id = str(uuid.uuid4())
        session_root = (artifact_root / session_id).resolve()

        session_root.mkdir(parents=True, exist_ok=True)
        (session_root / "steps").mkdir(parents=True, exist_ok=True)

        img = Image.open(initial_canvas_path).convert("RGB")
        w, h = img.size
        if (w, h) != (TILE_PX, TILE_PX):
            raise ValueError(f"Initial canvas must be {TILE_PX}x{TILE_PX}, got {w}x{h}")

        state = SessionState(
            session_id=session_id,
            session_root=str(session_root),
            mode=mode,
            tile_px=TILE_PX,
            ext_px=EXT_PX,
            band_px=BAND_PX,
            canvas_width_px_expected=w,
            canvas_height_px_expected=h,
            step_index_current=0,
        )

        atomic_write_with(state.canvas_path, lambda p: img.save(p, format="PNG"))

        step0 = state.step_dir(0)
        step0.mkdir(parents=True, exist_ok=True)
        atomic_write_with(step0 / "canvas_initial.png", lambda p: img.save(p, format="PNG"))
        atomic_write_text(step0 / "committed.ok", "ok\n")

        atomic_write_text(state.state_path, json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n")
        return cls(state)

    @classmethod
    def open(cls, *, session_root: Path) -> "ExquisiteSession":
        state_path = session_root / "session_state.json"
        if not state_path.exists():
            raise FileNotFoundError(f"Missing session state: {state_path}")
        d = json.loads(state_path.read_text(encoding="utf-8"))
        state = SessionState.from_dict(d)

        if Path(state.session_root).resolve() != Path(session_root).resolve():
            raise ValueError("Session root mismatch between provided path and session_state.json")

        return cls(state)

    def execute_step_mock(
        self,
        *,
        prompt: str,
        enforce_band_identity: bool = True,
        num_candidates: int = 1,  # kept for caller compatibility; ignored (single-sample only)
        feather_px: int = 0,
    ) -> DiskStepResult:
        _ = num_candidates  # intentionally unused (single-sample pipeline)

        canvas = Image.open(self.state.canvas_path).convert("RGB")
        w0, h0 = canvas.size

        mode = self.state.mode
        step_index_next = self.state.step_index_current + 1
        step_dir = self.state.step_dir(step_index_next)
        step_dir.mkdir(parents=True, exist_ok=True)

        if mode in ("x_ltr", "x_rtl") and h0 != TILE_PX:
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))
        if mode in ("y_ttb", "y_btt") and w0 != TILE_PX:
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        band = extract_conditioning_band(canvas, mode)

        # Single tile only (no multi-candidate scoring).
        tile = generate_tile(
            conditioning_band=band,
            mode=mode,
            prompt=prompt,
            step_index=(step_index_next * 1000),
        ).convert("RGB")

        cond_half, _new_half = split_tile(tile, mode)
        if enforce_band_identity and (cond_half.tobytes() != band.tobytes()):
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        canvas_next = _glue_with_feather(canvas=canvas, tile=tile, mode=mode, feather_px=feather_px)
        w1, h1 = canvas_next.size

        exp_w, exp_h = expected_next_canvas_size(canvas, mode)
        if (w1, h1) != (exp_w, exp_h):
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        atomic_write_text(step_dir / "prompt.txt", prompt + "\n")
        atomic_write_with(step_dir / "conditioning_band.png", lambda p: band.save(p, format="PNG"))
        atomic_write_with(step_dir / "canvas_before.png", lambda p: canvas.save(p, format="PNG"))
        atomic_write_with(step_dir / "canvas_after.png", lambda p: canvas_next.save(p, format="PNG"))

        patch = _tile_patch_for_overlap_glue(tile, mode)
        atomic_write_with(step_dir / "tile_patch.png", lambda p: patch.save(p, format="PNG"))
        atomic_write_with(step_dir / "tile_full.png", lambda p: tile.save(p, format="PNG"))

        _cond_half, new_half = split_tile(tile, mode)
        atomic_write_with(step_dir / "new_half.png", lambda p: new_half.save(p, format="PNG"))

        atomic_write_with(self.state.canvas_path, lambda p: canvas_next.save(p, format="PNG"))

        self.state.canvas_width_px_expected = w1
        self.state.canvas_height_px_expected = h1
        self.state.step_index_current = step_index_next
        atomic_write_text(self.state.state_path, json.dumps(self.state.to_dict(), indent=2, sort_keys=True) + "\n")
        atomic_write_text(step_dir / "committed.ok", "ok\n")

        return DiskStepResult("committed", self.state.session_id, step_index_next, (w0, h0), (w1, h1), str(step_dir))

    def execute_step_real(
        self,
        *,
        prompt: str,
        client: TileGeneratorClient,
        enforce_band_identity: bool = False,          # default OFF for now
        post_enforce_band_identity: bool = True,      # keep your KEEP-only paste if you want
        feather_px: int = 128,
    ) -> DiskStepResult:
        canvas = Image.open(self.state.canvas_path).convert("RGB")
        w0, h0 = canvas.size

        mode = self.state.mode
        step_index_next = self.state.step_index_current + 1
        step_dir = self.state.step_dir(step_index_next)
        step_dir.mkdir(parents=True, exist_ok=True)

        if mode in ("x_ltr", "x_rtl") and h0 != TILE_PX:
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))
        if mode in ("y_ttb", "y_btt") and w0 != TILE_PX:
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        band = extract_conditioning_band(canvas, mode)

        # Persist inputs up-front so you can diff even if generation crashes.
        atomic_write_text(step_dir / "prompt.txt", prompt + "\n")
        atomic_write_with(step_dir / "conditioning_band.png", lambda p: band.save(p, format="PNG"))
        atomic_write_with(step_dir / "canvas_before.png", lambda p: canvas.save(p, format="PNG"))

        try:
            tile = client.generate_tile(
                conditioning_band=band,
                mode=mode,
                prompt=prompt,
                step_index=step_index_next,
            ).convert("RGB")
        except GeneratorError as e:
            atomic_write_text(step_dir / "rejected.err", f"GeneratorError: {e}\n")
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))
        except Exception as e:
            atomic_write_text(step_dir / "rejected.err", f"Exception: {type(e).__name__}: {e}\n")
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        if tile.size != (TILE_PX, TILE_PX):
            atomic_write_text(step_dir / "rejected.err", f"BadTileSize: {tile.size}\n")
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        if post_enforce_band_identity:
            tile = _post_enforce_keep_into_tile(tile=tile, band=band, mode=mode)

        # Optional identity check, but DO NOT block committing right now.
        if enforce_band_identity:
            cond_half, _ = split_tile(tile, mode)
            if cond_half.size == band.size and cond_half.tobytes() != band.tobytes():
                atomic_write_text(step_dir / "warn.txt", "BandIdentityMismatch\n")

        # Save outputs
        atomic_write_with(step_dir / "tile_full.png", lambda p: tile.save(p, format="PNG"))
        _cond_half, new_half = split_tile(tile, mode)
        atomic_write_with(step_dir / "new_half.png", lambda p: new_half.save(p, format="PNG"))

        canvas_next = _glue_with_feather(canvas=canvas, tile=tile, mode=mode, feather_px=feather_px)
        w1, h1 = canvas_next.size

        exp_w, exp_h = expected_next_canvas_size(canvas, mode)
        if (w1, h1) != (exp_w, exp_h):
            atomic_write_text(step_dir / "rejected.err", f"CanvasDimInvariantViolation: got {(w1,h1)} expected {(exp_w,exp_h)}\n")
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        atomic_write_with(step_dir / "canvas_after.png", lambda p: canvas_next.save(p, format="PNG"))
        atomic_write_with(self.state.canvas_path, lambda p: canvas_next.save(p, format="PNG"))

        self.state.canvas_width_px_expected = w1
        self.state.canvas_height_px_expected = h1
        self.state.step_index_current = step_index_next
        atomic_write_text(self.state.state_path, json.dumps(self.state.to_dict(), indent=2, sort_keys=True) + "\n")
        atomic_write_text(step_dir / "committed.ok", "ok\n")

        return DiskStepResult("committed", self.state.session_id, step_index_next, (w0, h0), (w1, h1), str(step_dir))