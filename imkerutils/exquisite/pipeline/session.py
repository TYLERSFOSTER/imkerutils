from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, Tuple
from imkerutils.exquisite.api.client import TileGeneratorClient, GeneratorError

from PIL import Image

from imkerutils.exquisite.geometry.tile_mode import (
    ExtendMode,
    TILE_PX,
    EXT_PX,
    BAND_PX,
    extract_conditioning_band,
    split_tile,
    glue,
    expected_next_canvas_size,
)
from imkerutils.exquisite.api.mock_gpt_client import generate_tile
from imkerutils.exquisite.io.atomic_write import atomic_write_text, atomic_write_with
from imkerutils.exquisite.state.session_state import SessionState


def _default_artifact_root() -> Path:
    """
    Canonical in-package artifact root:
        imkerutils/_generated/exquisite

    This matches the repo layout you showed:
        imkerutils/_generated/exquisite
    """
    # .../imkerutils/exquisite/pipeline/session.py -> parents[2] is .../imkerutils
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


class ExquisiteSession:
    """
    Phase B: disk-backed session + step directories + atomic commit.

    Still uses mock generator (no network) but writes real artifacts.
    """

    def __init__(self, state: SessionState):
        self.state = state

    # ---------- creation / open ----------

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

        # load initial canvas
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

        # write canvas_latest.png atomically
        atomic_write_with(state.canvas_path, lambda p: img.save(p, format="PNG"))

        # step 0000: snapshot + committed marker
        step0 = state.step_dir(0)
        step0.mkdir(parents=True, exist_ok=True)
        atomic_write_with(step0 / "canvas_initial.png", lambda p: img.save(p, format="PNG"))
        atomic_write_text(step0 / "committed.ok", "ok\n")

        # write session_state.json atomically
        atomic_write_text(state.state_path, json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n")

        return cls(state)

    @classmethod
    def open(cls, *, session_root: Path) -> "ExquisiteSession":
        state_path = session_root / "session_state.json"
        if not state_path.exists():
            raise FileNotFoundError(f"Missing session state: {state_path}")
        d = json.loads(state_path.read_text(encoding="utf-8"))
        state = SessionState.from_dict(d)

        # minimal sanity: session_root matches
        if Path(state.session_root).resolve() != Path(session_root).resolve():
            raise ValueError("Session root mismatch between provided path and session_state.json")

        return cls(state)

    # ---------- core step execution ----------

    def execute_step_mock(
        self,
        *,
        prompt: str,
        enforce_band_identity: bool = True,
    ) -> DiskStepResult:
        """
        One committed step:
          - load canvas_latest.png
          - extract conditioning band
          - generate deterministic tile (mock)
          - (optional) verify conditioning half matches band
          - glue new half onto canvas
          - check dimension invariant
          - write step artifacts
          - atomically replace canvas_latest.png + session_state.json
        """
        # load authoritative canvas
        canvas = Image.open(self.state.canvas_path).convert("RGB")
        w0, h0 = canvas.size

        mode = self.state.mode
        step_index_next = self.state.step_index_current + 1
        step_dir = self.state.step_dir(step_index_next)
        step_dir.mkdir(parents=True, exist_ok=True)

        # Phase B invariant: non-growing axis remains 1024
        if mode in ("x_ltr", "x_rtl") and h0 != TILE_PX:
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))
        if mode in ("y_ttb", "y_btt") and w0 != TILE_PX:
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        # extract band, generate tile, split
        band = extract_conditioning_band(canvas, mode)
        tile = generate_tile(conditioning_band=band, mode=mode, prompt=prompt, step_index=step_index_next)
        cond_half, new_half = split_tile(tile, mode)

        if enforce_band_identity:
            # pixel-identity check (avoid deprecated getdata in Pillow 14+)
            if cond_half.tobytes() != band.tobytes():
                return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        # glue new region
        canvas_next = glue(canvas, new_half, mode)
        w1, h1 = canvas_next.size

        # dimension invariant check
        exp_w, exp_h = expected_next_canvas_size(canvas, mode)
        if (w1, h1) != (exp_w, exp_h):
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        # --- write step artifacts first (no authority changes yet) ---
        atomic_write_text(step_dir / "prompt.txt", prompt + "\n")
        atomic_write_with(step_dir / "conditioning_band.png", lambda p: band.save(p, format="PNG"))
        atomic_write_with(step_dir / "tile_full.png", lambda p: tile.save(p, format="PNG"))
        atomic_write_with(step_dir / "new_half.png", lambda p: new_half.save(p, format="PNG"))
        atomic_write_with(step_dir / "canvas_before.png", lambda p: canvas.save(p, format="PNG"))
        atomic_write_with(step_dir / "canvas_after.png", lambda p: canvas_next.save(p, format="PNG"))

        # --- atomically advance authority ---
        atomic_write_with(self.state.canvas_path, lambda p: canvas_next.save(p, format="PNG"))

        # update session state expectations + step index
        self.state.canvas_width_px_expected = w1
        self.state.canvas_height_px_expected = h1
        self.state.step_index_current = step_index_next
        atomic_write_text(self.state.state_path, json.dumps(self.state.to_dict(), indent=2, sort_keys=True) + "\n")

        # commit marker LAST (signals step dir is complete)
        atomic_write_text(step_dir / "committed.ok", "ok\n")

        return DiskStepResult("committed", self.state.session_id, step_index_next, (w0, h0), (w1, h1), str(step_dir))

    def execute_step_real(
        self,
        *,
        prompt: str,
        client: TileGeneratorClient,
        enforce_band_identity: bool = True,
        post_enforce_band_identity: bool = True,
    ) -> DiskStepResult:
        """
        Real generator step (networked via injected client), disk-authoritative.

        post_enforce_band_identity default True:
          - we overwrite the conditioning half in the returned tile with the extracted band
            BEFORE splitting/gluing, so slight model drift cannot break the invariant.
        """
        # load authoritative canvas
        canvas = Image.open(self.state.canvas_path).convert("RGB")
        w0, h0 = canvas.size

        mode = self.state.mode
        step_index_next = self.state.step_index_current + 1
        step_dir = self.state.step_dir(step_index_next)
        step_dir.mkdir(parents=True, exist_ok=True)

        # Phase B invariant: non-growing axis remains 1024
        if mode in ("x_ltr", "x_rtl") and h0 != TILE_PX:
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))
        if mode in ("y_ttb", "y_btt") and w0 != TILE_PX:
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        band = extract_conditioning_band(canvas, mode)

        try:
            tile = client.generate_tile(
                conditioning_band=band,
                mode=mode,
                prompt=prompt,
                step_index=step_index_next,
            )
        except GeneratorError:
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))
        except Exception:
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        tile = tile.convert("RGB")

        # Hard invariant: tile must be 1024x1024
        if tile.size != (TILE_PX, TILE_PX):
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        if post_enforce_band_identity:
            # overwrite conditioning half in-place according to convention
            if mode == "x_ltr":
                tile.paste(band, (0, 0))
            elif mode == "x_rtl":
                tile.paste(band, (512, 0))
            elif mode == "y_ttb":
                tile.paste(band, (0, 0))
            elif mode == "y_btt":
                tile.paste(band, (0, 512))
            else:
                return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        cond_half, new_half = split_tile(tile, mode)

        if enforce_band_identity:
            if cond_half.tobytes() != band.tobytes():
                return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        canvas_next = glue(canvas, new_half, mode)
        w1, h1 = canvas_next.size

        exp_w, exp_h = expected_next_canvas_size(canvas, mode)
        if (w1, h1) != (exp_w, exp_h):
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        # --- write step artifacts first (no authority changes yet) ---
        atomic_write_text(step_dir / "prompt.txt", prompt + "\n")
        atomic_write_with(step_dir / "conditioning_band.png", lambda p: band.save(p, format="PNG"))
        atomic_write_with(step_dir / "tile_full.png", lambda p: tile.save(p, format="PNG"))
        atomic_write_with(step_dir / "new_half.png", lambda p: new_half.save(p, format="PNG"))
        atomic_write_with(step_dir / "canvas_before.png", lambda p: canvas.save(p, format="PNG"))
        atomic_write_with(step_dir / "canvas_after.png", lambda p: canvas_next.save(p, format="PNG"))

        # --- atomically advance authority ---
        atomic_write_with(self.state.canvas_path, lambda p: canvas_next.save(p, format="PNG"))

        self.state.canvas_width_px_expected = w1
        self.state.canvas_height_px_expected = h1
        self.state.step_index_current = step_index_next
        atomic_write_text(self.state.state_path, json.dumps(self.state.to_dict(), indent=2, sort_keys=True) + "\n")

        atomic_write_text(step_dir / "committed.ok", "ok\n")

        return DiskStepResult("committed", self.state.session_id, step_index_next, (w0, h0), (w1, h1), str(step_dir))