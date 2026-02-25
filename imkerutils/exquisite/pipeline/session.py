# imkerutils/exquisite/pipeline/session.py
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, Tuple

from PIL import Image, ImageChops, ImageFilter

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
# Scoring + blending utilities
# -----------------------------

def _extract_scoring_strips(
    *,
    canvas_rgb: Image.Image,
    tile_rgb: Image.Image,
    mode: ExtendMode,
) -> tuple[Image.Image, Image.Image]:
    """
    Score what actually matters: the GENERATED strip adjacent to the seam.

    We compare:
      - canvas frontier overlap strip (256px)  vs
      - tile generated-side strip adjacent to seam (256px)

    This is the strip that predicts continuity *beyond* the seam.

    x_ltr:
      canvas_strip = canvas[:, w-256:w]
      tile_strip   = tile[:, 512:768]   (generated side adjacent to seam)

    x_rtl:
      canvas_strip = canvas[:, 0:256]
      tile_strip   = tile[:, 256:512]   (generated side adjacent to seam)

    y_ttb:
      canvas_strip = canvas[h-256:h, :]
      tile_strip   = tile[512:768, :]

    y_btt:
      canvas_strip = canvas[0:256, :]
      tile_strip   = tile[256:512, :]
    """
    canvas_rgb = canvas_rgb.convert("RGB")
    tile_rgb = tile_rgb.convert("RGB")
    cw, ch = canvas_rgb.size

    if mode in ("x_ltr", "x_rtl"):
        if ch != TILE_PX:
            raise ValueError("canvas height must be TILE_PX for x_* modes")

        if mode == "x_ltr":
            c = canvas_rgb.crop((cw - OVERLAP_PX, 0, cw, TILE_PX))
            t = tile_rgb.crop((HALF_PX, 0, HALF_PX + OVERLAP_PX, TILE_PX))  # 512..768
            return c, t

        # x_rtl
        c = canvas_rgb.crop((0, 0, OVERLAP_PX, TILE_PX))
        t = tile_rgb.crop((HALF_PX - OVERLAP_PX, 0, HALF_PX, TILE_PX))      # 256..512
        return c, t

    if mode in ("y_ttb", "y_btt"):
        if cw != TILE_PX:
            raise ValueError("canvas width must be TILE_PX for y_* modes")

        if mode == "y_ttb":
            c = canvas_rgb.crop((0, ch - OVERLAP_PX, TILE_PX, ch))
            t = tile_rgb.crop((0, HALF_PX, TILE_PX, HALF_PX + OVERLAP_PX))   # 512..768
            return c, t

        # y_btt
        c = canvas_rgb.crop((0, 0, TILE_PX, OVERLAP_PX))
        t = tile_rgb.crop((0, HALF_PX - OVERLAP_PX, TILE_PX, HALF_PX))       # 256..512
        return c, t

    raise ValueError(mode)


def _edge_weight_vector(mode: ExtendMode, length: int) -> list[float]:
    """
    Weights along the axis normal to the seam.
    Highest weight at the seam boundary, decays into the strip.

    For the strips produced by _extract_scoring_strips():
      - x_ltr: seam is LEFT edge of tile_strip, RIGHT edge of canvas_strip
      - x_rtl: seam is RIGHT edge of tile_strip, LEFT edge of canvas_strip
      - y_ttb: seam is TOP edge of tile_strip, BOTTOM edge of canvas_strip
      - y_btt: seam is BOTTOM edge of tile_strip, TOP edge of canvas_strip

    We encode this by choosing “seam is at start” vs “seam is at end”
    depending on mode, for both x and y cases.
    """
    if length <= 1:
        return [1.0] * length

    hi = 1.0
    lo = 0.2

    # For the *tile generated strip*:
    # x_ltr / y_ttb seam is at START of tile strip (index 0).
    # x_rtl / y_btt seam is at END of tile strip (index length-1).
    if mode in ("x_ltr", "y_ttb"):
        return [hi - (hi - lo) * (i / (length - 1)) for i in range(length)]
    if mode in ("x_rtl", "y_btt"):
        return [lo + (hi - lo) * (i / (length - 1)) for i in range(length)]
    raise ValueError(mode)


def _edge_map_find_edges(img_rgb: Image.Image) -> Image.Image:
    """
    Cheap, stable edge proxy using Pillow's FIND_EDGES.
    Returns 'L'.
    """
    g = img_rgb.convert("L")
    e = g.filter(ImageFilter.FIND_EDGES)
    return e


def _edge_weighted_edge_mse_score(
    *,
    canvas_strip_rgb: Image.Image,
    tile_strip_rgb: Image.Image,
    mode: ExtendMode,
) -> float:
    """
    Higher is better (return negative weighted MSE on edge maps).
    Pure-Pillow implementation (no numpy dependency).
    """
    if canvas_strip_rgb.size != tile_strip_rgb.size:
        raise ValueError(f"strip mismatch: {canvas_strip_rgb.size} vs {tile_strip_rgb.size}")

    e0 = _edge_map_find_edges(canvas_strip_rgb)
    e1 = _edge_map_find_edges(tile_strip_rgb)

    w, h = e0.size
    p0 = list(e0.getdata())
    p1 = list(e1.getdata())

    # weight along the axis normal to seam:
    # for x modes: weight over x; for y modes: weight over y.
    if mode in ("x_ltr", "x_rtl"):
        weights = _edge_weight_vector(mode, w)
        denom = 0.0
        num = 0.0
        for y in range(h):
            off = y * w
            for x in range(w):
                ww = weights[x]
                d = float(p0[off + x]) - float(p1[off + x])
                num += ww * d * d
                denom += ww
        return -num / (denom + 1e-12)

    if mode in ("y_ttb", "y_btt"):
        weights = _edge_weight_vector(mode, h)
        denom = 0.0
        num = 0.0
        for y in range(h):
            ww = weights[y]
            off = y * w
            for x in range(w):
                d = float(p0[off + x]) - float(p1[off + x])
                num += ww * d * d
            denom += ww
        return -num / (denom + 1e-12)

    raise ValueError(mode)


def _overlap_crops_for_blend(
    *,
    canvas_rgb: Image.Image,
    tile_rgb: Image.Image,
    mode: ExtendMode,
) -> tuple[Image.Image, Image.Image]:
    """
    Crops for blending INSIDE the overlap that glue() overwrites (not the generated strip).

    This is the 256px region that must match existing canvas frontier.

    x_ltr: canvas w-256:w  vs tile 256:512
    x_rtl: canvas 0:256    vs tile 512:768
    y_ttb: canvas h-256:h  vs tile 256:512
    y_btt: canvas 0:256    vs tile 512:768
    """
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
    Feather-blend ONLY inside the 256px overlap region (optional).
    This hides micro-discontinuities while preserving the hard conditioning invariant.
    """
    if feather_px <= 0:
        return glue(canvas, tile, mode)

    feather_px = int(feather_px)
    feather_px = max(1, min(feather_px, OVERLAP_PX))

    canvas = canvas.convert("RGB")
    tile = tile.convert("RGB")

    canvas_ov, tile_ov = _overlap_crops_for_blend(canvas_rgb=canvas, tile_rgb=tile, mode=mode)
    ov_w, ov_h = canvas_ov.size

    # alpha mask: 0 uses canvas, 255 uses tile
    if mode in ("x_ltr", "x_rtl"):
        mask = Image.new("L", (ov_w, ov_h), 0)
        ramp = Image.new("L", (feather_px, ov_h), 0)

        ramp_pixels = []
        for x in range(feather_px):
            a = int(round(255 * (x / max(1, feather_px - 1))))
            ramp_pixels.extend([a] * ov_h)
        ramp.putdata(ramp_pixels)

        if mode == "x_ltr":
            # feather at frontier side = RIGHT end of overlap window
            mask.paste(ramp, (ov_w - feather_px, 0))
        else:
            # x_rtl: frontier side = LEFT end of overlap window
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
            # feather at frontier side = BOTTOM end of overlap window
            mask.paste(ramp, (0, ov_h - feather_px))
        else:
            # y_btt: frontier side = TOP end of overlap window
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
        num_candidates: int = 3,
        feather_px: int = 0,
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

        n = max(1, int(num_candidates))
        candidates: list[Image.Image] = []
        scores: list[float] = []

        canvas_strip_cached: Image.Image | None = None

        for k in range(n):
            tile = generate_tile(
                conditioning_band=band,
                mode=mode,
                prompt=prompt,
                step_index=(step_index_next * 1000) + k,
            ).convert("RGB")

            cond_half, _new_half = split_tile(tile, mode)
            if enforce_band_identity and (cond_half.tobytes() != band.tobytes()):
                candidates.append(tile)
                scores.append(float("-inf"))
                continue

            try:
                if canvas_strip_cached is None:
                    canvas_strip_cached, _ = _extract_scoring_strips(canvas_rgb=canvas, tile_rgb=tile, mode=mode)
                _c_strip, t_strip = _extract_scoring_strips(canvas_rgb=canvas, tile_rgb=tile, mode=mode)
                score = _edge_weighted_edge_mse_score(
                    canvas_strip_rgb=canvas_strip_cached,
                    tile_strip_rgb=t_strip,
                    mode=mode,
                )
            except Exception:
                score = float("-inf")

            candidates.append(tile)
            scores.append(score)

        best_i = max(range(len(scores)), key=lambda i: scores[i]) if scores else 0
        tile_best = candidates[best_i] if candidates else None
        if tile_best is None:
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        canvas_next = _glue_with_feather(canvas=canvas, tile=tile_best, mode=mode, feather_px=feather_px)
        w1, h1 = canvas_next.size

        exp_w, exp_h = expected_next_canvas_size(canvas, mode)
        if (w1, h1) != (exp_w, exp_h):
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        atomic_write_text(step_dir / "prompt.txt", prompt + "\n")
        atomic_write_with(step_dir / "conditioning_band.png", lambda p: band.save(p, format="PNG"))
        atomic_write_with(step_dir / "canvas_before.png", lambda p: canvas.save(p, format="PNG"))
        atomic_write_with(step_dir / "canvas_after.png", lambda p: canvas_next.save(p, format="PNG"))

        cand_dir = step_dir / "candidates"
        cand_dir.mkdir(parents=True, exist_ok=True)
        for i, t in enumerate(candidates):
            atomic_write_with(cand_dir / f"{i:02d}_tile_full.png", lambda p, _t=t: _t.save(p, format="PNG"))

        atomic_write_text(
            step_dir / "candidate_scores.json",
            json.dumps(
                {
                    "num_candidates": n,
                    "scores": scores,
                    "best_index": best_i,
                    "best_score": scores[best_i] if scores else None,
                    "metric": "edge_weighted_mse(find_edges) on GENERATED seam-adjacent strip",
                    "overlap_px": OVERLAP_PX,
                    "advance_px": ADVANCE_PX,
                    "feather_px": int(feather_px),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

        cond_half, new_half = split_tile(tile_best, mode)
        patch = _tile_patch_for_overlap_glue(tile_best, mode)
        print("DEBUG_PATCH", "mode=", mode, "tile_patch.size=", patch.size)
        atomic_write_with(step_dir / "tile_patch.png", lambda p: patch.save(p, format="PNG"))
        atomic_write_with(step_dir / "tile_full.png", lambda p: tile_best.save(p, format="PNG"))
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
        enforce_band_identity: bool = True,
        post_enforce_band_identity: bool = True,
        num_candidates: int = 3,
        feather_px: int = 0,
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

        n = max(1, int(num_candidates))
        candidates: list[Image.Image] = []
        scores: list[float] = []
        errors: list[str | None] = []

        canvas_strip_cached: Image.Image | None = None

        for k in range(n):
            try:
                tile = client.generate_tile(
                    conditioning_band=band,
                    mode=mode,
                    prompt=prompt,
                    step_index=(step_index_next * 1000) + k,
                )
            except GeneratorError as e:
                candidates.append(Image.new("RGB", (TILE_PX, TILE_PX), (0, 0, 0)))
                scores.append(float("-inf"))
                errors.append(f"GeneratorError: {e}")
                continue
            except Exception as e:
                candidates.append(Image.new("RGB", (TILE_PX, TILE_PX), (0, 0, 0)))
                scores.append(float("-inf"))
                errors.append(f"Exception: {e}")
                continue

            tile = tile.convert("RGB")

            if tile.size != (TILE_PX, TILE_PX):
                candidates.append(tile)
                scores.append(float("-inf"))
                errors.append(f"BadTileSize: {tile.size}")
                continue

            if post_enforce_band_identity:
                if mode == "x_ltr":
                    tile.paste(band, (0, 0))
                elif mode == "x_rtl":
                    tile.paste(band, (512, 0))
                elif mode == "y_ttb":
                    tile.paste(band, (0, 0))
                elif mode == "y_btt":
                    tile.paste(band, (0, 512))
                else:
                    candidates.append(tile)
                    scores.append(float("-inf"))
                    errors.append(f"UnknownMode: {mode}")
                    continue

            cond_half, _new_half = split_tile(tile, mode)
            if enforce_band_identity and (cond_half.tobytes() != band.tobytes()):
                candidates.append(tile)
                scores.append(float("-inf"))
                errors.append("BandIdentityMismatch")
                continue

            try:
                if canvas_strip_cached is None:
                    canvas_strip_cached, _ = _extract_scoring_strips(canvas_rgb=canvas, tile_rgb=tile, mode=mode)
                _c_strip, t_strip = _extract_scoring_strips(canvas_rgb=canvas, tile_rgb=tile, mode=mode)
                score = _edge_weighted_edge_mse_score(
                    canvas_strip_rgb=canvas_strip_cached,
                    tile_strip_rgb=t_strip,
                    mode=mode,
                )
            except Exception as e:
                candidates.append(tile)
                scores.append(float("-inf"))
                errors.append(f"ScoreError: {e}")
                continue

            candidates.append(tile)
            scores.append(score)
            errors.append(None)

        best_i = max(range(len(scores)), key=lambda i: scores[i]) if scores else 0
        tile_best = candidates[best_i] if candidates else None
        if tile_best is None:
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        canvas_next = _glue_with_feather(canvas=canvas, tile=tile_best, mode=mode, feather_px=feather_px)
        w1, h1 = canvas_next.size

        exp_w, exp_h = expected_next_canvas_size(canvas, mode)
        if (w1, h1) != (exp_w, exp_h):
            return DiskStepResult("rejected", self.state.session_id, step_index_next, (w0, h0), (w0, h0), str(step_dir))

        atomic_write_text(step_dir / "prompt.txt", prompt + "\n")
        atomic_write_with(step_dir / "conditioning_band.png", lambda p: band.save(p, format="PNG"))
        atomic_write_with(step_dir / "canvas_before.png", lambda p: canvas.save(p, format="PNG"))
        atomic_write_with(step_dir / "canvas_after.png", lambda p: canvas_next.save(p, format="PNG"))

        cand_dir = step_dir / "candidates"
        cand_dir.mkdir(parents=True, exist_ok=True)
        for i, t in enumerate(candidates):
            atomic_write_with(cand_dir / f"{i:02d}_tile_full.png", lambda p, _t=t: _t.save(p, format="PNG"))

        atomic_write_text(
            step_dir / "candidate_scores.json",
            json.dumps(
                {
                    "num_candidates": n,
                    "scores": scores,
                    "errors": errors,
                    "best_index": best_i,
                    "best_score": scores[best_i] if scores else None,
                    "metric": "edge_weighted_mse(find_edges) on GENERATED seam-adjacent strip",
                    "overlap_px": OVERLAP_PX,
                    "advance_px": ADVANCE_PX,
                    "feather_px": int(feather_px),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )

        cond_half, new_half = split_tile(tile_best, mode)

        # --- NEW: save the exact paste payload that glue() uses ---
        patch = _tile_patch_for_overlap_glue(tile_best, mode)
        print("DEBUG_PATCH", "mode=", mode, "tile_patch.size=", patch.size)
        atomic_write_with(step_dir / "tile_patch.png", lambda p: patch.save(p, format="PNG"))

        # --- Optional but highly useful: save cond_half too ---
        atomic_write_with(step_dir / "cond_half.png", lambda p: cond_half.save(p, format="PNG"))

        atomic_write_with(step_dir / "tile_full.png", lambda p: tile_best.save(p, format="PNG"))
        atomic_write_with(step_dir / "new_half.png", lambda p: new_half.save(p, format="PNG"))

        atomic_write_with(self.state.canvas_path, lambda p: canvas_next.save(p, format="PNG"))

        self.state.canvas_width_px_expected = w1
        self.state.canvas_height_px_expected = h1
        self.state.step_index_current = step_index_next
        atomic_write_text(self.state.state_path, json.dumps(self.state.to_dict(), indent=2, sort_keys=True) + "\n")
        atomic_write_text(step_dir / "committed.ok", "ok\n")

        return DiskStepResult("committed", self.state.session_id, step_index_next, (w0, h0), (w1, h1), str(step_dir))